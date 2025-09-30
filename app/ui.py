from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable

import time

import gradio as gr
import pandas as pd
import yaml
import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from app.jobs import Pipeline


def _load_cfg(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def format_review_rows(rows: Iterable[pd.Series]) -> pd.DataFrame:
    review_rows = []
    for row in rows:
        if isinstance(row, tuple):
            _, row = row
        cid = int(row.get("cluster_id"))
        mid = int(row.get("medoid_id"))
        ck_raw = row.get("ck_tags")
        ai_raw = row.get("ai_tags")

        def _as_list(value) -> list[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v) for v in value if str(v).strip()]
            if isinstance(value, str):
                parts = [part.strip() for part in value.replace(";", ",").split(",")]
                return [part for part in parts if part]
            if pd.isna(value):
                return []
            return [str(value)]

        ck_tags = ", ".join(_as_list(ck_raw))
        ai_tags = ", ".join(_as_list(ai_raw))
        flags = []
        if row.get("is_people"):
            flags.append("people")
        if row.get("is_nude_assumed"):
            flags.append("nude-sensitive")
        if row.get("openai_used"):
            flags.append("vision")
        if row.get("hand_suppressed"):
            flags.append("hand-suppressed")
        review_rows.append(
            {
                "cluster_id": cid,
                "medoid_id": mid,
                "selected": bool(row.get("selected", False)),
                "apply_cluster": bool(row.get("apply_cluster", True)),
                "ck_tags": ck_tags,
                "ai_tags": ai_tags,
                "flags": ", ".join(flags),
            }
        )
    return pd.DataFrame(
        review_rows,
        columns=[
            "cluster_id",
            "medoid_id",
            "selected",
            "apply_cluster",
            "ck_tags",
            "ai_tags",
            "flags",
        ],
    )


def build_ui():
    from app.jobs import Pipeline  # local import to avoid heavy deps on import

    def load_config(path: str, state_value: Dict):
        try:
            old_pipeline = state_value.get("pipeline")
            if old_pipeline is not None:
                old_pipeline.close()

            cfg_path = Path(path).expanduser()
            if not cfg_path.is_absolute():
                cfg_path = Path.cwd() / cfg_path
            if not cfg_path.exists():
                raise FileNotFoundError(f"Config not found: {cfg_path}")
            cfg = _load_cfg(cfg_path)
            pipeline = Pipeline(cfg)
        except Exception as exc:  # broad to surface helpful message
            return (
                f"Failed to load config: {exc}",
                state_value,
                gr.update(),
                gr.update(),
            )

        state_value.update({"cfg": cfg, "pipeline": pipeline, "dfs": {}, "review": {}, "cfg_path": str(cfg_path)})
        allow_people = cfg.get("people_policy", {}).get("allow_openai_on_people_sets", False)
        apply_cluster = cfg.get("review", {}).get("default_apply_to_cluster", True)
        return (
            f"Config loaded: {cfg_path}",
            state_value,
            gr.update(value=allow_people),
            gr.update(value=apply_cluster),
        )

    def toggle_people_allow(value: bool, state_value: Dict):
        cfg = state_value.get("cfg")
        if cfg is None:
            return "Load config first", state_value

        old_pipeline = state_value.get("pipeline")
        if old_pipeline is not None:
            old_pipeline.close()

        cfg.setdefault("people_policy", {})["allow_openai_on_people_sets"] = bool(value)
        state_value["cfg"] = cfg
        state_value["pipeline"] = Pipeline(cfg)
        return ("Updated people policy", state_value)

    def toggle_apply_cluster(value: bool, state_value: Dict):
        cfg = state_value.get("cfg")
        if cfg is None:
            return "Load config first", state_value

        old_pipeline = state_value.get("pipeline")
        if old_pipeline is not None:
            old_pipeline.close()

        cfg.setdefault("review", {})["default_apply_to_cluster"] = bool(value)
        state_value["cfg"] = cfg
        state_value["pipeline"] = Pipeline(cfg)
        return ("Updated apply-to-cluster", state_value)

    def run_step(step: str, state_value: Dict):
        pipeline: "Pipeline" = state_value.get("pipeline")
        if pipeline is None:
            return "Load config first", state_value
        dfs = state_value.get("dfs", {})
        if step == "scan":
            df = pipeline.run_scan()
            dfs["index"] = df
            msg = f"Indexed {len(df)} files"
        elif step == "proxies":
            base = dfs.get("index")
            df = pipeline.run_proxies(base)
            dfs["proxies"] = df
            msg = f"Built {len(df)} proxies"
        elif step == "embed":
            base = dfs.get("proxies")
            df = pipeline.run_embed(base)
            dfs["embeds"] = df
            msg = f"Embedded {len(df)} images"
        elif step == "cluster":
            idx = dfs.get("index")
            emb = dfs.get("embeds")
            df = pipeline.run_cluster(idx, emb)
            dfs["clusters"] = df
            msg = f"Clusters: {df['cluster_id'].nunique()}"
        else:
            msg = "Unknown step"
        state_value["dfs"] = dfs
        return msg, state_value

    def medoid_ai(use_openai: bool, state_value: Dict):
        pipeline: "Pipeline" = state_value.get("pipeline")
        if pipeline is None:
            return "Load config first", state_value
        dfs = state_value.get("dfs", {})
        clusters = dfs.get("clusters")
        embeds = dfs.get("embeds")
        proxies = dfs.get("proxies")
        index_df = dfs.get("index")
        df = pipeline.medoid_tags(clusters, embeds, proxies, index_df, use_openai=use_openai)
        dfs["medoid_tags"] = df
        state_value["dfs"] = dfs
        pipeline.close()
        return f"Tagged {len(df)} medoids", state_value

    def export_audit(state_value: Dict):
        pipeline: "Pipeline" = state_value.get("pipeline")
        if pipeline is None:
            return "Load config first", state_value
        dfs = state_value.get("dfs", {})
        clusters = dfs.get("clusters")
        tags = dfs.get("medoid_tags")
        path = pipeline.export_audit(clusters, tags)
        return f"Audit written: {path}", state_value

    def _get_proxy_map(state_value: Dict, pipeline: "Pipeline") -> Dict[int, str]:
        review_state = state_value.setdefault("review", {})
        proxy_map = review_state.get("proxy_map")
        if proxy_map:
            return proxy_map
        dfs = state_value.get("dfs", {})
        proxies_df = dfs.get("proxies")
        if proxies_df is None:
            try:
                proxies_df = pipeline._load_proxies_df()
            except Exception:
                proxies_df = None
        proxy_map = {}
        if proxies_df is not None and not proxies_df.empty:
            proxy_map = {row["id"]: row["proxy_path"] for _, row in proxies_df.iterrows()}
        review_state["proxy_map"] = proxy_map
        return proxy_map

    def _review_state(state_value: Dict) -> Dict:
        return state_value.setdefault("review", {})

    def _split_tags(raw: str) -> list[str]:
        values: list[str] = []
        for part in raw.replace(";", ",").split(","):
            tag = part.strip()
            if tag:
                values.append(tag)
        return values

    def _as_tag_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, (pd.Series, np.ndarray)):
            return [str(v).strip() for v in value.tolist() if str(v).strip()]
        if isinstance(value, str):
            return _split_tags(value)
        if isinstance(value, (set, tuple)):
            return [str(v).strip() for v in value if str(v).strip()]
        try:
            if pd.isna(value):
                return []
        except TypeError:
            pass
        return [str(value).strip()]

    def _tag_choices(values: Iterable[str]) -> list[str]:
        # Preserve input order but drop duplicates
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                ordered.append(value)
        return ordered

    def _safe_list(value) -> list:
        """Safely convert to list, handling None, numpy arrays, and lists."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (tuple, set)):
            return list(value)
        return []

    def _format_timestamp(data: Dict[str, Any]) -> str | None:
        for key in ("capture_time", "captured_at", "taken_at", "taken_time", "datetime", "date"):
            value = data.get(key)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _trim_filename(path_str: str, limit: int = 32) -> str:
        name = Path(path_str).name if path_str else ""
        if len(name) <= limit:
            return name
        head = name[: int(limit / 2) - 1]
        tail = name[-(limit - len(head) - 1) :]
        return f"{head}…{tail}"

    def _gallery_caption(item: Dict[str, Any]) -> str:
        lines: list[str] = []
        prefix = "✓ " if item.get("selected") else ""
        cluster_size = item.get("cluster_size") or 0
        lines.append(f"{prefix}Cluster {item['cluster_id']} • {cluster_size} images")
        if item.get("timestamp"):
            lines.append(str(item["timestamp"]))
        if item.get("filename"):
            lines.append(item["filename"])
        if item.get("flags"):
            lines.append(f"Flags: {', '.join(item['flags'])}")
        return "\n".join(lines)

    def _members_gallery(item: Dict[str, Any], review_state: Dict[str, Any]) -> list[list[str]]:
        proxy_map = review_state.get("proxy_map", {})
        index_map = review_state.get("index_map", {})
        gallery: list[list[str]] = []
        medoid_id = item.get("medoid_id")
        medoid_proxy = item.get("proxy_path")
        if medoid_proxy:
            gallery.append([str(medoid_proxy), f"Medoid {medoid_id}"])
        member_ids = _safe_list(item.get("member_ids"))
        for mid in member_ids:
            if mid == medoid_id:
                continue
            proxy_path = proxy_map.get(mid)
            if not proxy_path:
                continue
            idx = index_map.get(mid, {})
            caption = _trim_filename(idx.get("path", "")) or f"ID {mid}"
            gallery.append([str(proxy_path), caption])
        return gallery

    def _detail_outputs(
        state_value: Dict,
        cluster_id: int,
        status_msg: str,
        update_gallery: bool = False,
    ):
        review_state = _review_state(state_value)
        items = review_state.get("items", {})
        item = items.get(cluster_id)
        if item is None:
            return (
                status_msg,
                state_value,
                (gr.update() if not update_gallery else gr.update(value=review_state.get("gallery", []))),
                gr.update(value="Select a cluster to begin."),
                gr.update(value=None),
                gr.update(value=""),
                gr.update(choices=[], value=[]),
                gr.update(value=""),
                gr.update(choices=[], value=[]),
                gr.update(value=""),
                gr.update(value=True),
                gr.update(value=False),
                gr.update(value=[]),
            )

        review_state["current"] = cluster_id
        detail_heading = _gallery_caption(item)
        metadata_lines = [f"**Filename:** {item.get('filename', '—')} ({item.get('medoid_id')})"]
        if item.get("path"):
            folder = str(Path(item["path"]).parent)
            metadata_lines.append(f"**Folder:** {folder}")
        if item.get("timestamp"):
            metadata_lines.append(f"**Capture:** {item['timestamp']}")
        if item.get("cluster_size"):
            metadata_lines.append(f"**Cluster size:** {item['cluster_size']}")
        if item.get("flags"):
            metadata_lines.append(f"**Flags:** {', '.join(item['flags'])}")
        metadata_md = "\n".join(metadata_lines)

        ck_tags = _tag_choices(item.get("ck_tags", []))
        ai_tags = _tag_choices(item.get("ai_tags", []))

        members = _members_gallery(item, review_state)

        cluster_gallery_update = (
            gr.update(value=review_state.get("gallery", [])) if update_gallery else gr.update()
        )

        return (
            status_msg,
            state_value,
            cluster_gallery_update,
            gr.update(value=detail_heading),
            gr.update(value=item.get("proxy_path")),
            gr.update(value=metadata_md),
            gr.update(choices=ck_tags, value=ck_tags),
            gr.update(value=""),
            gr.update(choices=ai_tags, value=ai_tags),
            gr.update(value=""),
            gr.update(value=bool(item.get("apply_cluster", True))),
            gr.update(value=bool(item.get("selected", False))),
            gr.update(value=members),
        )

    def _review_dataframe(review_state: Dict[str, Any]) -> pd.DataFrame:
        items = review_state.get("items", {})
        if not items:
            return pd.DataFrame()
        rows = []
        for cid, item in items.items():
            rows.append(
                {
                    "cluster_id": int(cid),
                    "medoid_id": int(item.get("medoid_id", -1)),
                    "ck_tags": list(item.get("ck_tags", [])),
                    "ai_tags": list(item.get("ai_tags", [])),
                    "apply_cluster": bool(item.get("apply_cluster", True)),
                    "selected": bool(item.get("selected", False)),
                }
            )
        return pd.DataFrame(rows)

    def _sync_items_from_df(review_state: Dict[str, Any], df: pd.DataFrame):
        if df is None or df.empty:
            return
        items = review_state.get("items", {})
        for record in df.to_dict("records"):
            cid = int(record.get("cluster_id"))
            item = items.get(cid)
            if not item:
                continue
            if "ck_tags" in record:
                item["ck_tags"] = _as_tag_list(record.get("ck_tags"))
            if "ai_tags" in record:
                item["ai_tags"] = _as_tag_list(record.get("ai_tags"))
            if "apply_cluster" in record:
                item["apply_cluster"] = bool(record.get("apply_cluster", True))
            if "selected" in record:
                item["selected"] = bool(record.get("selected", False))

    def prepare_review(state_value: Dict):
        pipeline: "Pipeline" = state_value.get("pipeline")
        review_state = _review_state(state_value)
        if pipeline is None:
            return _detail_outputs(state_value, -1, "Load config first", update_gallery=False)

        dfs = state_value.get("dfs", {})
        tags_df = dfs.get("medoid_tags")
        if tags_df is None or tags_df.empty:
            tags_df = pipeline.load_medoid_tags_df()
        if tags_df is None or tags_df.empty:
            return _detail_outputs(state_value, -1, "Run medoid tagging first", update_gallery=False)

        clusters_df = dfs.get("clusters")
        if clusters_df is None or clusters_df.empty:
            try:
                clusters_df = pipeline._load_clusters_df()
            except Exception:
                clusters_df = pd.DataFrame()
        index_df = dfs.get("index")
        if index_df is None or index_df.empty:
            try:
                index_df = pipeline._load_index_df()
            except Exception:
                index_df = pd.DataFrame()

        proxy_map = _get_proxy_map(state_value, pipeline)
        cluster_map = {}
        if clusters_df is not None and not clusters_df.empty:
            cluster_map = {int(row["cluster_id"]): row.to_dict() for _, row in clusters_df.iterrows()}
        index_map = {}
        if index_df is not None and not index_df.empty:
            index_map = {int(row["id"]): row.to_dict() for _, row in index_df.iterrows()}

        review_state["proxy_map"] = proxy_map
        review_state["cluster_map"] = cluster_map
        review_state["index_map"] = index_map

        items: Dict[int, Dict[str, Any]] = {}
        order: list[int] = []
        gallery_entries: list[list[str]] = []

        start_time = time.perf_counter()
        for record in tags_df.to_dict("records"):
            cid = int(record.get("cluster_id"))
            mid = int(record.get("medoid_id", -1))
            cluster_row = cluster_map.get(cid, {})
            index_row = index_map.get(mid, {})
            proxy_path = proxy_map.get(mid)
            if not proxy_path:
                continue
            flags = []
            if record.get("is_people"):
                flags.append("people")
            if record.get("is_nude_assumed"):
                flags.append("nude-sensitive")
            if record.get("openai_used"):
                flags.append("vision")
            if record.get("hand_suppressed"):
                flags.append("hand-suppressed")

            member_ids = _safe_list(cluster_row.get("member_ids"))
            cluster_size = len(member_ids)
            timestamp = _format_timestamp(index_row or {})
            filename = _trim_filename((index_row or {}).get("path", ""))

            items[cid] = {
                "cluster_id": cid,
                "medoid_id": mid,
                "proxy_path": str(proxy_path),
                "ck_tags": _as_tag_list(record.get("ck_tags")),
                "ai_tags": _as_tag_list(record.get("ai_tags")),
                "selected": bool(record.get("selected", False)),
                "apply_cluster": bool(record.get("apply_cluster", True)),
                "flags": flags,
                "path": (index_row or {}).get("path"),
                "filename": filename,
                "timestamp": timestamp,
                "cluster_size": cluster_size or 1,
                "member_ids": member_ids,
            }
            order.append(cid)
            caption = _gallery_caption(items[cid])
            gallery_entries.append([str(proxy_path), caption])

        review_state["items"] = items
        review_state["order"] = order
        review_state["gallery"] = gallery_entries
        review_state["current"] = order[0] if order else None

        elapsed = time.perf_counter() - start_time
        status_msg = f"Loaded {len(order)} clusters for review ({elapsed:.1f}s)"
        if not order:
            return _detail_outputs(state_value, -1, "No clusters available", update_gallery=True)
        return _detail_outputs(state_value, review_state["current"], status_msg, update_gallery=True)

    def select_cluster(*args):
        if not args:
            return _detail_outputs({}, -1, "Select a cluster first", update_gallery=False)
        if len(args) == 1:
            evt = None
            state_value = args[0]
        else:
            evt, state_value = args[0], args[1]
        if state_value is None:
            return _detail_outputs({}, -1, "Select a cluster first", update_gallery=False)
        review_state = _review_state(state_value)
        order = review_state.get("order", [])
        if not order:
            return _detail_outputs(state_value, -1, "No clusters loaded", update_gallery=False)
        index = getattr(evt, "index", None) if evt is not None else None
        if index is None or index >= len(order):
            return _detail_outputs(state_value, -1, "Invalid cluster selection", update_gallery=False)
        cid = order[index]
        return _detail_outputs(state_value, cid, f"Reviewing cluster {cid}", update_gallery=False)

    def _update_tags(state_value: Dict, key: str, values: list[str]):
        review_state = _review_state(state_value)
        current = review_state.get("current")
        if current is None:
            return None
        item = review_state.get("items", {}).get(current)
        if item is None:
            return None
        item[key] = _tag_choices(values)
        return current

    def update_ck_tags(values: list[str], state_value: Dict):
        cid = _update_tags(state_value, "ck_tags", values or [])
        if cid is None:
            return _detail_outputs(state_value, -1, "Select a cluster first", update_gallery=False)
        refresh_gallery(state_value)
        return _detail_outputs(state_value, cid, "Updated CK tags", update_gallery=True)

    def update_ai_tags(values: list[str], state_value: Dict):
        cid = _update_tags(state_value, "ai_tags", values or [])
        if cid is None:
            return _detail_outputs(state_value, -1, "Select a cluster first", update_gallery=False)
        refresh_gallery(state_value)
        return _detail_outputs(state_value, cid, "Updated AI tags", update_gallery=True)

    def add_ck_tag(new_tag: str, state_value: Dict):
        review_state = _review_state(state_value)
        current = review_state.get("current")
        if current is None:
            return _detail_outputs(state_value, -1, "Select a cluster first", update_gallery=False)
        tags = review_state.get("items", {}).get(current, {}).get("ck_tags", [])
        additions = _split_tags(new_tag)
        if not additions:
            return _detail_outputs(state_value, current, "No CK tags added", update_gallery=False)
        for tag in additions:
            if tag not in tags:
                tags.append(tag)
        review_state["items"][current]["ck_tags"] = _tag_choices(tags)
        refresh_gallery(state_value)
        return _detail_outputs(state_value, current, f"Added {len(additions)} CK tag(s)", update_gallery=True)

    def add_ai_tag(new_tag: str, state_value: Dict):
        review_state = _review_state(state_value)
        current = review_state.get("current")
        if current is None:
            return _detail_outputs(state_value, -1, "Select a cluster first", update_gallery=False)
        tags = review_state.get("items", {}).get(current, {}).get("ai_tags", [])
        additions = _split_tags(new_tag)
        if not additions:
            return _detail_outputs(state_value, current, "No AI tags added", update_gallery=False)
        for tag in additions:
            if tag not in tags:
                tags.append(tag)
        review_state["items"][current]["ai_tags"] = _tag_choices(tags)
        refresh_gallery(state_value)
        return _detail_outputs(state_value, current, f"Added {len(additions)} AI tag(s)", update_gallery=True)

    def set_apply_cluster(value: bool, state_value: Dict):
        review_state = _review_state(state_value)
        current = review_state.get("current")
        if current is None:
            return _detail_outputs(state_value, -1, "Select a cluster first", update_gallery=False)
        review_state.get("items", {}).get(current, {})["apply_cluster"] = bool(value)
        refresh_gallery(state_value)
        return _detail_outputs(state_value, current, "Updated cluster scope", update_gallery=True)

    def set_selected(value: bool, state_value: Dict):
        review_state = _review_state(state_value)
        current = review_state.get("current")
        if current is None:
            return _detail_outputs(state_value, -1, "Select a cluster first", update_gallery=False)
        review_state.get("items", {}).get(current, {})["selected"] = bool(value)
        refresh_gallery(state_value)
        return _detail_outputs(state_value, current, "Updated selection", update_gallery=True)

    def mark_cluster(selected: bool, state_value: Dict):
        review_state = _review_state(state_value)
        current = review_state.get("current")
        if current is None:
            return _detail_outputs(state_value, -1, "Select a cluster first", update_gallery=False)
        review_state.get("items", {}).get(current, {})["selected"] = selected
        message = "Marked for write" if selected else "Skipped cluster"
        refresh_gallery(state_value)
        return _detail_outputs(state_value, current, message, update_gallery=True)

    def refresh_gallery(state_value: Dict):
        review_state = _review_state(state_value)
        gallery_entries = []
        for cid in review_state.get("order", []):
            item = review_state.get("items", {}).get(cid)
            if not item:
                continue
            gallery_entries.append([str(item.get("proxy_path")), _gallery_caption(item)])
        review_state["gallery"] = gallery_entries
        return (
            f"Gallery refreshed ({len(gallery_entries)} clusters)",
            state_value,
            gr.update(value=gallery_entries),
        )

    def save_review(state_value: Dict):
        pipeline: "Pipeline" = state_value.get("pipeline")
        if pipeline is None:
            return "Load config first", state_value
        review_state = _review_state(state_value)
        df = _review_dataframe(review_state)
        if df.empty:
            return "No review data to save", state_value
        updated_df = pipeline.update_medoid_tags(df)
        _sync_items_from_df(review_state, updated_df)
        refresh_gallery(state_value)
        return f"Saved edits for {len(df)} clusters", state_value

    def write_selected(dry_run: bool, state_value: Dict):
        pipeline: "Pipeline" = state_value.get("pipeline")
        if pipeline is None:
            return "Load config first", state_value
        review_state = _review_state(state_value)
        df = _review_dataframe(review_state)
        if df.empty:
            return "No review data available", state_value
        selected_df = df[df["selected"]]
        if selected_df.empty:
            return "Select at least one cluster", state_value
        selected_ids = selected_df["cluster_id"].astype(int).tolist()
        operations = pipeline.write_clusters(
            selected_ids,
            tags_df=df,
            dry_run=dry_run,
        )
        msg = (
            f"Dry run: would update {len(operations)} files across {len(selected_ids)} clusters"
            if dry_run
            else f"Wrote keywords to {len(operations)} files across {len(selected_ids)} clusters"
        )
        return msg, state_value

    with gr.Blocks(title="photo-tag-pipeline") as demo:
        state = gr.State({"cfg": None, "pipeline": None, "dfs": {}, "review": {}})
        status = gr.Textbox(label="Status", interactive=False)
        cfg_path = gr.Textbox(label="config.yaml", value="config/config.yaml")
        allow_people_chk = gr.Checkbox(label="Allow OpenAI on people sets", value=False)
        apply_cluster_chk = gr.Checkbox(label="Apply tags to whole cluster", value=True)

        gr.Button("Load config").click(
            load_config,
            [cfg_path, state],
            [status, state, allow_people_chk, apply_cluster_chk],
        )

        allow_people_chk.change(toggle_people_allow, [allow_people_chk, state], [status, state])
        apply_cluster_chk.change(toggle_apply_cluster, [apply_cluster_chk, state], [status, state])

        with gr.Row():
            gr.Button("1) Scan").click(run_step, [gr.Textbox(value="scan", visible=False), state], [status, state])
            gr.Button("2) Proxies").click(run_step, [gr.Textbox(value="proxies", visible=False), state], [status, state])
            gr.Button("3) Embeddings").click(run_step, [gr.Textbox(value="embed", visible=False), state], [status, state])
            gr.Button("4) Cluster").click(run_step, [gr.Textbox(value="cluster", visible=False), state], [status, state])
        with gr.Row():
            gr.Button("5) Medoid AI (local)").click(medoid_ai, [gr.Checkbox(value=False, visible=False), state], [status, state])
            gr.Button("5b) Medoid AI (+Vision)").click(medoid_ai, [gr.Checkbox(value=True, visible=False), state], [status, state])
        gr.Button("6) Export Audit CSV").click(export_audit, [state], [status, state])

        with gr.Accordion("Review & Write", open=False):
            gr.Markdown(
                "Load clusters, browse medoids visually, adjust CK/AI tags, and choose which clusters to write before exporting keywords."
            )
            review_btn = gr.Button("Load review workspace")
            with gr.Row():
                with gr.Column(scale=2):
                    cluster_gallery = gr.Gallery(
                        label="Cluster medoids",
                        columns=3,
                        height=600,
                        allow_preview=False,
                    )
                with gr.Column(scale=1):
                    detail_heading = gr.Markdown("Select a cluster to begin.")
                    medoid_image = gr.Image(label="Medoid preview", interactive=False, height=320, type="filepath")
                    metadata_md = gr.Markdown(visible=True)
                    ck_tags_group = gr.CheckboxGroup(label="CK tags", choices=[], value=[])
                    with gr.Row():
                        ck_add_input = gr.Textbox(label="Add CK tag", placeholder="CK:sunset")
                        ck_add_btn = gr.Button("Add", min_width=80)
                    ai_tags_group = gr.CheckboxGroup(label="AI tags", choices=[], value=[])
                    with gr.Row():
                        ai_add_input = gr.Textbox(label="Add AI tag", placeholder="AI:sunset")
                        ai_add_btn = gr.Button("Add", min_width=80)
                    apply_cluster_detail = gr.Checkbox(label="Apply tags to whole cluster", value=True)
                    select_cluster_detail = gr.Checkbox(label="Select cluster for write", value=False)
                    with gr.Row():
                        mark_keep_btn = gr.Button("Mark for write", variant="primary")
                        mark_skip_btn = gr.Button("Skip cluster")
            members_gallery = gr.Gallery(label="Cluster members", columns=6, height=220, allow_preview=True)
            with gr.Row():
                save_btn = gr.Button("Save review edits", variant="primary")
                refresh_btn = gr.Button("Refresh gallery captions")
            with gr.Row():
                dry_run_chk = gr.Checkbox(label="Dry run (no XMP writes)", value=True)
                write_btn = gr.Button("Write selected clusters")

            review_outputs = [
                status,
                state,
                cluster_gallery,
                detail_heading,
                medoid_image,
                metadata_md,
                ck_tags_group,
                ck_add_input,
                ai_tags_group,
                ai_add_input,
                apply_cluster_detail,
                select_cluster_detail,
                members_gallery,
            ]

            review_btn.click(prepare_review, [state], review_outputs)
            cluster_gallery.select(select_cluster, [state], review_outputs)
            ck_tags_group.change(update_ck_tags, [ck_tags_group, state], review_outputs)
            ai_tags_group.change(update_ai_tags, [ai_tags_group, state], review_outputs)
            ck_add_btn.click(add_ck_tag, [ck_add_input, state], review_outputs)
            ai_add_btn.click(add_ai_tag, [ai_add_input, state], review_outputs)
            apply_cluster_detail.change(set_apply_cluster, [apply_cluster_detail, state], review_outputs)
            select_cluster_detail.change(set_selected, [select_cluster_detail, state], review_outputs)

            def _mark_true(state_value: Dict):
                return mark_cluster(True, state_value)

            def _mark_false(state_value: Dict):
                return mark_cluster(False, state_value)

            mark_keep_btn.click(_mark_true, [state], review_outputs)
            mark_skip_btn.click(_mark_false, [state], review_outputs)

            save_btn.click(save_review, [state], [status, state])
            refresh_btn.click(refresh_gallery, [state], [status, state, cluster_gallery])
            write_btn.click(write_selected, [dry_run_chk, state], [status, state])
    return demo


__all__ = ["build_ui", "format_review_rows"]
