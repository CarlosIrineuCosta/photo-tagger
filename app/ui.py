from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import gradio as gr
import pandas as pd
import yaml

from app.jobs import Pipeline


def _load_cfg(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_ui():

    def load_config(path: str, state_value: Dict):
        try:
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
        cfg.setdefault("people_policy", {})["allow_openai_on_people_sets"] = bool(value)
        state_value["cfg"] = cfg
        state_value["pipeline"] = Pipeline(cfg)
        return ("Updated people policy", state_value)

    def toggle_apply_cluster(value: bool, state_value: Dict):
        cfg = state_value.get("cfg")
        if cfg is None:
            return "Load config first", state_value
        cfg.setdefault("review", {})["default_apply_to_cluster"] = bool(value)
        state_value["cfg"] = cfg
        state_value["pipeline"] = Pipeline(cfg)
        return ("Updated apply-to-cluster", state_value)

    def run_step(step: str, state_value: Dict):
        pipeline: Pipeline = state_value.get("pipeline")
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
        pipeline: Pipeline = state_value.get("pipeline")
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
        return f"Tagged {len(df)} medoids", state_value

    def export_audit(state_value: Dict):
        pipeline: Pipeline = state_value.get("pipeline")
        if pipeline is None:
            return "Load config first", state_value
        dfs = state_value.get("dfs", {})
        clusters = dfs.get("clusters")
        tags = dfs.get("medoid_tags")
        path = pipeline.export_audit(clusters, tags)
        return f"Audit written: {path}", state_value

    def _get_proxy_map(state_value: Dict, pipeline: Pipeline) -> Dict[int, str]:
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

    def prepare_review(state_value: Dict):
        pipeline: Pipeline = state_value.get("pipeline")
        review_columns = [
            "cluster_id",
            "medoid_id",
            "selected",
            "apply_cluster",
            "ck_tags",
            "ai_tags",
            "flags",
        ]
        empty_df = pd.DataFrame(columns=review_columns)
        if pipeline is None:
            return "Load config first", state_value, gr.update(value=empty_df), gr.Gallery.update(value=[])
        dfs = state_value.get("dfs", {})
        tags_df = dfs.get("medoid_tags")
        if tags_df is None or tags_df.empty:
            tags_df = pipeline.load_medoid_tags_df()
        if tags_df is None or tags_df.empty:
            return "Run medoid tagging first", state_value, gr.update(value=empty_df), gr.Gallery.update(value=[])

        proxy_map = _get_proxy_map(state_value, pipeline)
        review_rows = []
        for _, row in tags_df.iterrows():
            cid = int(row.get("cluster_id"))
            mid = int(row.get("medoid_id"))
            ck_tags = ", ".join(row.get("ck_tags", []))
            ai_tags = ", ".join(row.get("ai_tags", []))
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
        review_df = pd.DataFrame(review_rows, columns=review_columns)
        state_value.setdefault("review", {})["table"] = review_df
        return "Review table ready", state_value, gr.update(value=review_df), gr.Gallery.update(value=[])

    def save_review(table: pd.DataFrame, state_value: Dict):
        pipeline: Pipeline = state_value.get("pipeline")
        if pipeline is None:
            return "Load config first", state_value
        if table is None or table.empty:
            return "Review table is empty", state_value
        table = table.dropna(subset=["cluster_id"]).copy()
        if table.empty:
            return "Review table is empty", state_value
        table["cluster_id"] = table["cluster_id"].astype(int)
        if "medoid_id" in table.columns:
            table["medoid_id"] = table["medoid_id"].fillna(-1).astype(int)
        for col in ["ck_tags", "ai_tags"]:
            if col in table.columns:
                table[col] = table[col].fillna("").astype(str)
        cols = [c for c in ["cluster_id", "ck_tags", "ai_tags", "apply_cluster", "selected"] if c in table.columns]
        if "cluster_id" not in cols:
            return "Review table missing cluster_id", state_value
        pipeline.update_medoid_tags(table[cols])
        state_value.setdefault("review", {})["table"] = table
        return f"Saved review edits for {len(table)} clusters", state_value

    def refresh_gallery(table: pd.DataFrame, state_value: Dict):
        pipeline: Pipeline = state_value.get("pipeline")
        if pipeline is None:
            return gr.update(value=[]), "Load config first", state_value
        if table is None or table.empty:
            return gr.Gallery.update(value=[]), "Review table is empty", state_value
        proxy_map = _get_proxy_map(state_value, pipeline)
        gallery_items = []
        for _, row in table.iterrows():
            if not bool(row.get("selected", False)):
                continue
            cid = int(row.get("cluster_id"))
            mid = int(row.get("medoid_id"))
            proxy_path = proxy_map.get(mid)
            if not proxy_path or not Path(proxy_path).exists():
                continue
            lines = [f"Cluster {cid} (medoid {mid})"]
            ck_tags = row.get("ck_tags")
            ai_tags = row.get("ai_tags")
            if ck_tags:
                lines.append(f"CK: {ck_tags}")
            if ai_tags:
                lines.append(f"AI: {ai_tags}")
            flags = row.get("flags")
            if flags:
                lines.append(f"Flags: {flags}")
            apply_cluster = bool(row.get("apply_cluster", True))
            lines.append(f"Apply to cluster: {'yes' if apply_cluster else 'medoid only'}")
            gallery_items.append([proxy_path, "\n".join(lines)])
        status_msg = (
            f"Showing {len(gallery_items)} selected medoids"
            if gallery_items
            else "No clusters selected"
        )
        state_value.setdefault("review", {})["table"] = table
        return gr.update(value=gallery_items), status_msg, state_value

    def write_selected(table: pd.DataFrame, dry_run: bool, state_value: Dict):
        pipeline: Pipeline = state_value.get("pipeline")
        if pipeline is None:
            return "Load config first", state_value
        if table is None or table.empty:
            return "Review table is empty", state_value
        table = table.dropna(subset=["cluster_id"]).copy()
        if table.empty:
            return "Review table is empty", state_value
        table["cluster_id"] = table["cluster_id"].astype(int)
        selected_ids = [int(row["cluster_id"]) for _, row in table.iterrows() if bool(row.get("selected", False))]
        if not selected_ids:
            return "Select at least one cluster", state_value
        operations = pipeline.write_clusters(selected_ids, dry_run=dry_run)
        state_value.setdefault("review", {})["table"] = table
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
                "Load the review table to edit CK/AI tags, mark clusters for writing, and preview medoids before committing XMP keywords."
            )
            review_btn = gr.Button("Load review table")
            review_table = gr.DataFrame(
                headers=[
                    "cluster_id",
                    "medoid_id",
                    "selected",
                    "apply_cluster",
                    "ck_tags",
                    "ai_tags",
                    "flags",
                ],
                datatype=["number", "number", "bool", "bool", "str", "str", "str"],
                row_count=(0, "dynamic"),
                col_count=7,
                interactive=True,
                type="pandas",
                label="Medoid review table",
            )
            with gr.Row():
                save_btn = gr.Button("Save review edits")
                gallery_btn = gr.Button("Refresh gallery from selection")
            gallery = gr.Gallery(label="Selected medoids", columns=4, height=400)
            dry_run_chk = gr.Checkbox(label="Dry run (no XMP writes)", value=True)
            write_btn = gr.Button("Write selected clusters")

            review_btn.click(prepare_review, [state], [status, state, review_table, gallery])
            save_btn.click(save_review, [review_table, state], [status, state])
            gallery_btn.click(refresh_gallery, [review_table, state], [gallery, status, state])
            write_btn.click(write_selected, [review_table, dry_run_chk, state], [status, state])
    return demo


__all__ = ["build_ui"]
