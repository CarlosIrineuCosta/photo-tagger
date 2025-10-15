from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import math

import numpy as np
import pandas as pd
from tqdm import tqdm

from app import proxy, scanner
from app.cluster import cluster_time_windowed
from app.config import load_config
from app.embed import ClipEmbedder
from app.openai_vision import call_openai_vision_on_image
from app.person import PersonDetector, PersonDetectorConfig
from app.store import CacheStore
from app.tag_ai import AiTagConfig, ai_tags_local
from app.tag_ck import CkConfig, CkTagger
from app.utils import ensure_dir
from app.write_xmp import write_keywords


class Pipeline:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        runtime = cfg.get("runtime", {})
        cache_root = runtime.get("cache_root", "./cache")
        self.store = CacheStore(cache_root)
        self.reuse_cache = runtime.get("reuse_cache", True)
        self.index_path = self.store.parquet("index")
        self.proxies_path = self.store.parquet("proxies")
        self.embeds_path = self.store.parquet("embeds")
        self.clusters_path = self.store.parquet("clusters")
        self.medoid_ai_path = self.store.parquet("medoid_ai")
        review_cfg = cfg.get("review", {})
        self.audit_path = self.store.path(review_cfg.get("audit_csv", "audit.csv"))
        ensure_dir(self.audit_path.parent)
        self._clip_embedder: Optional[ClipEmbedder] = None
        self._ck_tagger: Optional[CkTagger] = None
        self._person_detector: Optional[PersonDetector] = None

    def close(self):
        if self._clip_embedder is not None:
            del self._clip_embedder
            self._clip_embedder = None
        if self._ck_tagger is not None:
            del self._ck_tagger
            self._ck_tagger = None
        if self._person_detector is not None:
            del self._person_detector
            self._person_detector = None
        import torch
        torch.cuda.empty_cache()

    # ----------- helpers -----------
    def _load_index_df(self) -> pd.DataFrame:
        return pd.read_parquet(self.index_path)

    def _load_proxies_df(self) -> pd.DataFrame:
        return pd.read_parquet(self.proxies_path)

    def _load_embeds_df(self) -> pd.DataFrame:
        return pd.read_parquet(self.embeds_path)

    def _load_clusters_df(self) -> pd.DataFrame:
        return pd.read_parquet(self.clusters_path)

    def load_medoid_tags_df(self) -> pd.DataFrame:
        path = Path(self.medoid_ai_path)
        if path.exists():
            return pd.read_parquet(path)
        return pd.DataFrame()

    def _clip(self) -> ClipEmbedder:
        if self._clip_embedder is None:
            emb_cfg = self.cfg.get("embeddings", {})
            self._clip_embedder = ClipEmbedder(
                emb_cfg.get("model", "ViT-L-14"),
                emb_cfg.get("pretrained", "openai"),
                emb_cfg.get("device", "cuda"),
                emb_cfg.get("batch_size", 128),
            )
        return self._clip_embedder

    def _ck(self) -> Optional[CkTagger]:
        ck_cfg = self.cfg.get("ck_tagging")
        if not ck_cfg:
            return None
        if self._ck_tagger is None:
            vocab_path = Path(ck_cfg.get("vocab_file", "config/ck_vocab.yaml"))
            if not vocab_path.exists():
                raise FileNotFoundError(f"CK vocab file not found: {vocab_path}")
            vocab = load_config(vocab_path)
            ck_config = CkConfig(
                vocab=vocab,
                max_ck_tags=ck_cfg.get("max_ck_tags", 10),
                prefix=self.cfg.get("xmp", {}).get("prefix_ck", "CK:"),
                clip_model=ck_cfg.get("clip_model", "ViT-L-14"),
                clip_pretrained=ck_cfg.get("clip_pretrained", "openai"),
                device=self.cfg.get("embeddings", {}).get("device", "cuda"),
            )
            self._ck_tagger = CkTagger(ck_config, self.cfg.get("heuristics", {}))
        return self._ck_tagger

    def _ai_config(self) -> AiTagConfig:
        ai_cfg = self.cfg.get("ai_tagging", {})
        return AiTagConfig(
            max_ai_tags=ai_cfg.get("max_ai_tags", 12),
            ai_prefix=self.cfg.get("xmp", {}).get("prefix_ai", ai_cfg.get("ai_prefix", "AI:")),
            concept_bank_extra=tuple(ai_cfg.get("concept_bank_extra", [])),
            city_whitelist=tuple(ai_cfg.get("city_whitelist", [])),
            ocr_enable=bool(self.cfg.get("ocr", {}).get("enable", False)),
            ocr_min_conf=float(self.cfg.get("ocr", {}).get("min_confidence", 0.75)),
            clip_model=self.cfg.get("embeddings", {}).get("model", "ViT-L-14"),
            clip_pretrained=self.cfg.get("embeddings", {}).get("pretrained", "openai"),
            clip_device=self.cfg.get("embeddings", {}).get("device", "cuda"),
        )

    def _person(self) -> Optional[PersonDetector]:
        if self._person_detector is not None:
            return self._person_detector
        det_cfg = PersonDetectorConfig(
            threshold=self.cfg.get("people_policy", {}).get("person_threshold", 0.6),
            device=self.cfg.get("embeddings", {}).get("device", "cuda"),
        )
        try:
            self._person_detector = PersonDetector(det_cfg)
        except Exception:
            self._person_detector = None
        return self._person_detector

    # ----------- pipeline steps -----------
    def run_scan(self) -> pd.DataFrame:
        if self.reuse_cache and Path(self.index_path).exists():
            return self._load_index_df()

        rows = scanner.crawl(
            self.cfg.get("roots", []),
            self.cfg.get("index", {}).get("include_ext", []),
            self.cfg.get("index", {}).get("exclude_regex", []),
            self.cfg.get("date_resolver", {}),
        )
        df = pd.DataFrame(rows)
        if not df.empty:
            df.to_parquet(self.index_path, index=False)
        return df

    def run_proxies(self, index_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        if self.reuse_cache and Path(self.proxies_path).exists():
            return self._load_proxies_df()
        if index_df is None:
            index_df = self._load_index_df()
        proxies_dir = self.store.proxies_dir()
        settings = self.cfg.get("proxy", {})
        records: List[Dict] = []
        for row in tqdm(index_df.itertuples(index=False), total=len(index_df), desc="proxies"):
            result = proxy.build_proxy(
                row.path,
                row.sha1,
                proxies_dir,
                settings.get("max_size", 1024),
                settings.get("jpeg_quality", 90),
            )
            result.update({"id": row.id, "sha1": row.sha1})
            records.append(result)
        df = pd.DataFrame(records)
        if not df.empty:
            df.to_parquet(self.proxies_path, index=False)
        return df

    def run_embed(self, proxies_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        if self.reuse_cache and Path(self.embeds_path).exists():
            return self._load_embeds_df()
        if proxies_df is None:
            proxies_df = self._load_proxies_df()
        clipper = self._clip()
        embeds = clipper.encode_paths(list(proxies_df["proxy_path"]))
        df = pd.DataFrame(
            {
                "id": proxies_df["id"],
                "emb": [vec.tolist() for vec in embeds],
            }
        )
        if not df.empty:
            df.to_parquet(self.embeds_path, index=False)
        return df

    def run_cluster(
        self,
        index_df: Optional[pd.DataFrame] = None,
        embeds_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        if self.reuse_cache and Path(self.clusters_path).exists():
            return self._load_clusters_df()
        if index_df is None:
            index_df = self._load_index_df()
        if embeds_df is None:
            embeds_df = self._load_embeds_df()
        clusters_df = cluster_time_windowed(index_df, embeds_df, self.cfg.get("clustering", {}), self.cfg.get("date_resolver", {}))
        if not clusters_df.empty:
            clusters_df.to_parquet(self.clusters_path, index=False)
        return clusters_df

    def medoid_tags(
        self,
        clusters_df: Optional[pd.DataFrame] = None,
        embeds_df: Optional[pd.DataFrame] = None,
        proxies_df: Optional[pd.DataFrame] = None,
        index_df: Optional[pd.DataFrame] = None,
        use_openai: bool = True,
    ) -> pd.DataFrame:
        if clusters_df is None:
            clusters_df = self._load_clusters_df()
        else:
            clusters_df = clusters_df.copy()
        if embeds_df is None:
            embeds_df = self._load_embeds_df()
        if proxies_df is None:
            proxies_df = self._load_proxies_df()
        if index_df is None:
            index_df = self._load_index_df()

        embed_map = {row["id"]: np.asarray(row["emb"], dtype="float32") for _, row in embeds_df.iterrows()}
        proxy_map = {row["id"]: row for _, row in proxies_df.iterrows()}
        index_map = {row["id"]: row for _, row in index_df.iterrows()}

        ai_conf = self._ai_config()
        ck_tagger = self._ck()
        ck_prefix = self.cfg.get("xmp", {}).get("prefix_ck", "CK:")
        people_detector = self._person()
        people_policy = self.cfg.get("people_policy", {})
        allow_openai_people = people_policy.get("allow_openai_on_people_sets", False)
        treat_people_as_nude = people_policy.get("treat_people_sets_as_nude", True)

        records: List[Dict] = []

        for _, cluster_row in clusters_df.iterrows():
            cid = int(cluster_row["cluster_id"])
            mid = int(cluster_row["medoid_id"])
            emb = embed_map.get(mid)
            proxy_row = proxy_map.get(mid)
            index_row = index_map.get(mid)
            if emb is None or proxy_row is None or index_row is None:
                continue
            proxy_path = proxy_row["proxy_path"]

            is_people = False
            if people_detector is not None:
                try:
                    is_people = people_detector.person_present(proxy_path)
                except Exception:
                    is_people = False

            ck_tags: List[str] = []
            if ck_tagger is not None:
                is_nude = bool(is_people and treat_people_as_nude)
                ck_tags = ck_tagger.tags_for_image(
                    emb,
                    metadata=index_row,
                    proxy_meta=proxy_row,
                    has_person=is_people,
                    is_nude=is_nude,
                )
            else:
                is_nude = bool(is_people and treat_people_as_nude)

            ai_tags = ai_tags_local(proxy_path, emb, ai_conf)
            vision_tags: List[str] = []
            if use_openai and self.cfg.get("ai_tagging", {}).get("use_openai_vision", False):
                if not is_people or allow_openai_people:
                    try:
                        vision_tags = call_openai_vision_on_image(
                            proxy_path,
                            ai_conf.city_whitelist,
                            ai_conf.max_ai_tags,
                            self.cfg.get("ai_tagging", {}).get("openai_model", "gpt-4o-mini"),
                        )
                    except Exception:
                        vision_tags = []

            merged_ai_tags = []
            seen = set()
            for tag in vision_tags + ai_tags:
                if tag not in seen:
                    seen.add(tag)
                    merged_ai_tags.append(tag)
                if len(merged_ai_tags) >= ai_conf.max_ai_tags:
                    break

            clusters_df.loc[clusters_df["cluster_id"] == cid, "is_people"] = bool(is_people)
            clusters_df.loc[clusters_df["cluster_id"] == cid, "openai_allowed"] = bool(
                (not is_people) or allow_openai_people
            )

            hand_tag = f"{ck_prefix}hand"
            hand_suppressed = bool(is_nude and hand_tag not in ck_tags)

            records.append(
                {
                    "cluster_id": cid,
                    "medoid_id": mid,
                    "ck_tags": ck_tags,
                    "ai_tags": merged_ai_tags,
                    "is_people": is_people,
                    "is_nude_assumed": is_nude,
                    "openai_used": bool(vision_tags),
                    "hand_suppressed": hand_suppressed,
                }
            )

        df = pd.DataFrame(records)
        if not df.empty:
            df["apply_cluster"] = self.cfg.get("review", {}).get("default_apply_to_cluster", True)
            df["selected"] = False
            df.to_parquet(self.medoid_ai_path, index=False)
        if not clusters_df.empty:
            clusters_df.to_parquet(self.clusters_path, index=False)
        return df

    def export_audit(self, clusters_df: Optional[pd.DataFrame] = None, tags_df: Optional[pd.DataFrame] = None) -> Path:
        if clusters_df is None:
            clusters_df = self._load_clusters_df()
        if tags_df is None:
            tags_df = pd.read_parquet(self.medoid_ai_path)
        index_df = self._load_index_df()
        out = clusters_df.merge(tags_df, on=["cluster_id", "medoid_id"], how="left")
        out = out.merge(index_df[["id", "path"]], left_on="medoid_id", right_on="id", how="left")
        out = out.drop(columns=["id"])
        out = out.rename(columns={"path": "filename"})
        out.to_csv(self.audit_path, index=False)
        return self.audit_path

    def update_medoid_tags(self, df: pd.DataFrame) -> pd.DataFrame:
        existing = self.load_medoid_tags_df()
        if existing.empty or df.empty:
            return existing

        prefix_ck = self.cfg.get("xmp", {}).get("prefix_ck", "CK:")
        prefix_ai = self.cfg.get("xmp", {}).get("prefix_ai", "AI:")

        existing = existing.set_index("cluster_id")

        def _parse(value: Sequence, prefix: str) -> List[str]:
            tags: List[str] = []
            for item in value:
                if item is None:
                    continue
                if isinstance(item, str):
                    parts = [p.strip() for p in item.replace(";", ",").split(",")]
                else:
                    parts = [str(item).strip()]
                for part in parts:
                    if not part:
                        continue
                    if prefix and not part.lower().startswith(prefix.lower()):
                        part = f"{prefix}{part.lstrip(':')}"
                    if part not in tags:
                        tags.append(part)
            return tags

        for _, row in df.iterrows():
            cid = row.get("cluster_id")
            if cid not in existing.index:
                continue
            ck_raw = row.get("ck_tags")
            ai_raw = row.get("ai_tags")
            if ck_raw is not None:
                existing.at[cid, "ck_tags"] = _parse([ck_raw], prefix_ck)
            if ai_raw is not None:
                existing.at[cid, "ai_tags"] = _parse([ai_raw], prefix_ai)
            if "apply_cluster" in row and pd.notna(row["apply_cluster"]):
                existing.at[cid, "apply_cluster"] = bool(row["apply_cluster"])
            if "selected" in row and pd.notna(row["selected"]):
                existing.at[cid, "selected"] = bool(row["selected"])

        existing = existing.reset_index()
        existing.to_parquet(self.medoid_ai_path, index=False)
        return existing

    def write_clusters(
        self,
        cluster_ids: List[int],
        clusters_df: Optional[pd.DataFrame] = None,
        tags_df: Optional[pd.DataFrame] = None,
        index_df: Optional[pd.DataFrame] = None,
        dry_run: bool = False,
    ) -> List[Dict]:
        if clusters_df is None:
            clusters_df = self._load_clusters_df()
        if tags_df is None:
            tags_df = pd.read_parquet(self.medoid_ai_path)
        if index_df is None:
            index_df = self._load_index_df()
        tags_map = {row["cluster_id"]: row for _, row in tags_df.iterrows()}
        index_map = {row["id"]: row["path"] for _, row in index_df.iterrows()}

        write_targets: List[str] = []
        keyword_lists: List[List[str]] = []
        operations: List[Dict] = []

        def _as_list(value) -> List[str]:
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            if value is None:
                return []
            if isinstance(value, float) and math.isnan(value):
                return []
            if isinstance(value, str):
                parts = [p.strip() for p in value.replace(";", ",").split(",")]
                return [p for p in parts if p]
            return [str(value).strip()]

        for cid in cluster_ids:
            row = clusters_df.loc[clusters_df["cluster_id"] == cid]
            if row.empty:
                continue
            members = row.iloc[0]["member_ids"]
            if not isinstance(members, list):
                members = list(members)
            tags = tags_map.get(cid)
            if tags is None:
                continue
            keywords = []
            for seq in (_as_list(tags.get("ck_tags", [])), _as_list(tags.get("ai_tags", []))):
                for tag in seq:
                    if tag and tag not in keywords:
                        keywords.append(tag)
            if not keywords:
                continue
            cluster_apply = bool(tags.get("apply_cluster", self.cfg.get("review", {}).get("default_apply_to_cluster", True)))
            if cluster_apply:
                paths = [index_map[mid] for mid in members if mid in index_map]
            else:
                paths = [index_map.get(row.iloc[0]["medoid_id"])]
            for path in paths:
                if path:
                    write_targets.append(path)
                    keyword_lists.append(keywords)
                    operations.append(
                        {
                            "cluster_id": cid,
                            "path": path,
                            "keywords": keywords,
                            "apply_cluster": cluster_apply,
                        }
                    )

        if dry_run:
            return operations

        if write_targets:
            write_keywords(
                write_targets,
                keyword_lists,
                self.cfg.get("xmp", {}).get("prefix_ck", "CK:"),
                self.cfg.get("xmp", {}).get("prefix_ai", "AI:"),
                workers=self.cfg.get("xmp", {}).get("write_concurrency", 4),
            )
        return operations


__all__ = ["Pipeline"]
