from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import streamlit as st

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import clip_model, export as export_core, labels as labels_core, medoid as medoid_core  # noqa: E402
from app.core import scan as scan_core  # noqa: E402
from app.core import score as score_core  # noqa: E402
from app.core import thumbs as thumbs_core  # noqa: E402

RUN_META_KEY = "run_meta"
IMAGE_PATHS_KEY = "image_paths"
THUMBS_KEY = "thumbs"
EMBED_KEY = "image_embeddings"
LABELS_KEY = "labels"
LABEL_EMBED_KEY = "label_embeddings"
GALLERY_KEY = "gallery_items"
APPROVED_KEY = "approved_labels"
SCORES_KEY = "score_rows"

DEFAULT_RUN_DIR = Path("runs")
DEFAULT_CACHE_DIR = Path("thumb_cache")
PRETRAINED_DEFAULT = "openai"
PROMPT_TEMPLATE = "a photo of {}"

IMAGES_FILENAME = "images.txt"
THUMBS_FILENAME = "thumbnails.json"
EMB_FILENAME = "image_embeddings.npy"
LABEL_EMB_FILENAME = "label_embeddings.npy"
LABEL_META_FILENAME = "label_embeddings.json"
SCORES_FILENAME = "scores.json"
APPROVED_FILENAME = "approved.csv"
MEDOIDS_FILENAME = "medoids.csv"
EXPORT_FILENAME = "results.csv"
RUN_RECORD_FILENAME = "run.json"
LOG_FILENAME = "log.txt"


def init_session_state() -> None:
    st.session_state.setdefault(RUN_META_KEY, {})
    st.session_state.setdefault(IMAGE_PATHS_KEY, [])
    st.session_state.setdefault(THUMBS_KEY, [])
    st.session_state.setdefault(EMBED_KEY, None)
    st.session_state.setdefault(LABELS_KEY, [])
    st.session_state.setdefault(LABEL_EMBED_KEY, None)
    st.session_state.setdefault(GALLERY_KEY, [])
    st.session_state.setdefault(APPROVED_KEY, {})
    st.session_state.setdefault(SCORES_KEY, [])


@st.cache_resource(show_spinner=True)
def load_clip_resource(model_name: str, pretrained: str = PRETRAINED_DEFAULT):
    return clip_model.load_clip(model_name=model_name, pretrained=pretrained, device=None)


def sidebar_controls() -> Dict[str, object]:
    st.sidebar.header("Run configuration")
    root = st.sidebar.text_input("Root path", value=str(Path.cwd()), key="sidebar_root")
    labels_file = st.sidebar.text_input("Labels file", value="labels.txt", key="sidebar_labels_file")
    model_name = st.sidebar.text_input("Model name", value="ViT-L-14", key="sidebar_model_name")
    batch_size = int(st.sidebar.number_input("Batch size", min_value=1, value=64, step=1, key="sidebar_batch_size"))
    threshold = float(
        st.sidebar.slider("Threshold", min_value=0.0, max_value=1.0, value=0.25, step=0.01, key="sidebar_threshold")
    )
    topk = int(st.sidebar.number_input("Top-K", min_value=1, max_value=20, value=5, step=1, key="sidebar_topk"))
    max_images = int(st.sidebar.number_input("Max images", min_value=1, value=100, step=1, key="sidebar_max_images"))

    st.sidebar.markdown("---")
    trigger_scan = st.sidebar.button("1) Scan", key="btn_scan", use_container_width=True)
    trigger_thumbs = st.sidebar.button("2) Thumbs", key="btn_thumbs", use_container_width=True)
    trigger_embed = st.sidebar.button("3) Embed", key="btn_embed", use_container_width=True)
    trigger_score = st.sidebar.button("4) Score", key="btn_score", use_container_width=True)
    trigger_medoids = st.sidebar.button("5) Medoids", key="btn_medoids", use_container_width=True)
    trigger_save = st.sidebar.button("6) Save Approved", key="btn_save", use_container_width=True)
    trigger_export = st.sidebar.button("7) Export CSV", key="btn_export", use_container_width=True)
    trigger_sidecars = st.sidebar.button("8) Write Sidecars", key="btn_sidecars", use_container_width=True)

    meta = st.session_state.get(RUN_META_KEY, {})
    if meta.get("run_id"):
        st.sidebar.caption(f"Run: {meta['run_id']}  \nRoot: {meta['root']}")

    return {
        "root": root,
        "labels_file": labels_file,
        "model_name": model_name,
        "batch_size": batch_size,
        "threshold": threshold,
        "topk": topk,
        "max_images": max_images,
        "scan": trigger_scan,
        "thumbs": trigger_thumbs,
        "embed": trigger_embed,
        "score": trigger_score,
        "medoids": trigger_medoids,
        "save": trigger_save,
        "export": trigger_export,
        "sidecars": trigger_sidecars,
    }


def render_control_panel(config: Dict[str, object]) -> None:
    st.header("Photo Tagger (Streamlit)")
    st.caption("Stream the pipeline: scan, embed, score, approve, and export metadata.")

    if config["scan"]:
        handle_scan(config)
    if config["thumbs"]:
        handle_thumbs()
    if config["embed"]:
        handle_embed(config)
    if config["score"]:
        handle_score(config)
    if config["medoids"]:
        handle_medoids()
    if config["save"]:
        handle_save_approved()
    if config["export"]:
        handle_export(config)
    if config["sidecars"]:
        handle_sidecars()


def render_gallery(threshold: float, topk: int) -> None:
    gallery_items: List[Dict] = st.session_state.get(GALLERY_KEY, [])
    approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})

    st.subheader("Gallery")
    st.write("Approve or adjust labels per image. Use bulk actions as needed.")

    select_col, clear_col = st.columns([1, 1])
    with select_col:
        if st.button("Select all over threshold"):
            apply_select_all_over_threshold(approved_map)
    with clear_col:
        if st.button("Clear selections"):
            approved_map.clear()

    st.session_state[APPROVED_KEY] = approved_map

    if not gallery_items:
        st.info("Run through the pipeline to populate the gallery.")
        return

    columns = st.columns(6)
    for idx, item in enumerate(gallery_items):
        column = columns[idx % 6]
        with column:
            render_gallery_item(idx, item, approved_map, topk)


def render_gallery_item(idx: int, item: Dict, approved_map: Dict[str, List[str]], topk: int) -> None:
    image_path = item.get("path", "")
    thumbnail_path = item.get("thumbnail")
    top_labels: Sequence[str] = item.get("topk_labels", [])[:topk]
    top_scores: Sequence[float] = item.get("topk_scores", [])[:topk]

    if thumbnail_path and Path(thumbnail_path).exists():
        st.image(str(thumbnail_path), use_container_width=True)
    else:
        st.markdown("`(no thumbnail)`")

    st.caption(Path(image_path).name or "Image")

    if top_labels and top_scores:
        chips = " ".join(f"`{label}` ({score:.2f})" for label, score in zip(top_labels, top_scores))
        st.markdown(chips)
    else:
        st.markdown("`no scores yet`")

    current = approved_map.get(image_path, [])
    options = list(dict.fromkeys(list(top_labels) + current))
    selection = st.multiselect(
        "Approved labels",
        options=options,
        default=current,
        key=f"approved_{idx}",
    )
    approved_map[image_path] = list(selection)


def apply_select_all_over_threshold(approved_map: Dict[str, List[str]]) -> None:
    score_rows: List[Dict[str, object]] = st.session_state.get(SCORES_KEY, [])
    for row in score_rows:
        path = row.get("path")
        over_threshold: Sequence[Tuple[str, float]] = row.get("over_threshold", [])
        if not path or not over_threshold:
            continue
        labels = [label for label, _ in over_threshold]
        approved_map[path] = sorted(set(labels + approved_map.get(path, [])))


def ensure_root_path(raw_root: str) -> Path:
    root_path = Path(raw_root).expanduser()
    if not root_path.is_absolute():
        root_path = (Path.cwd() / root_path).resolve()
    return root_path


def start_new_run(root_path: Path, model_name: str) -> Dict[str, str]:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = (DEFAULT_RUN_DIR / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "root": str(root_path),
        "model_name": model_name,
        "pretrained": PRETRAINED_DEFAULT,
    }
    st.session_state[RUN_META_KEY] = meta
    return meta


def get_active_run_meta() -> Dict[str, str]:
    meta = st.session_state.get(RUN_META_KEY, {})
    if not meta.get("run_dir"):
        raise RuntimeError("Run not initialized. Scan first.")
    return meta


def get_run_dir(meta: Dict[str, str]) -> Path:
    return Path(meta["run_dir"])


def log_run(meta: Dict[str, str], message: str) -> None:
    run_dir = get_run_dir(meta)
    log_path = run_dir / LOG_FILENAME
    timestamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def update_run_record(meta: Dict[str, str], **updates: object) -> None:
    run_dir = get_run_dir(meta)
    record_path = run_dir / RUN_RECORD_FILENAME
    if record_path.exists():
        record = json.loads(record_path.read_text(encoding="utf-8"))
    else:
        record = {"run_id": meta["run_id"], "root": meta["root"]}
    record.update(updates)
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")


def handle_scan(config: Dict[str, object]) -> None:
    try:
        root_path = ensure_root_path(config["root"])
        if not root_path.exists():
            st.error(f"Root not found: {root_path}")
            return
        meta = start_new_run(root_path, config["model_name"])
        max_images = config.get("max_images")
        image_paths = scan_core.scan_directory(root_path, max_images=max_images)
        st.session_state[IMAGE_PATHS_KEY] = image_paths
        st.session_state[THUMBS_KEY] = []
        st.session_state[EMBED_KEY] = None
        st.session_state[LABELS_KEY] = []
        st.session_state[LABEL_EMBED_KEY] = None
        st.session_state[GALLERY_KEY] = []
        st.session_state[APPROVED_KEY] = {}
        st.session_state[SCORES_KEY] = []

        run_dir = get_run_dir(meta)
        run_dir.joinpath(IMAGES_FILENAME).write_text("\n".join(image_paths), encoding="utf-8")
        update_run_record(
            meta,
            model_name=config["model_name"],
            max_images=max_images,
            batch_size=config["batch_size"],
            threshold=config["threshold"],
            topk=config["topk"],
        )
        log_run(meta, f"scan completed ({len(image_paths)} files)")
        st.success(f"Scanned {len(image_paths)} images.")
    except Exception as exc:  # pragma: no cover - UI feedback
        st.error(f"Scan failed: {exc}")


def handle_thumbs() -> None:
    try:
        meta = get_active_run_meta()
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        if not image_paths:
            st.warning("Scan images first.")
            return
        thumbs = thumbs_core.build_thumbnails(image_paths=image_paths, cache_root=DEFAULT_CACHE_DIR)
        st.session_state[THUMBS_KEY] = thumbs
        update_gallery_items()

        run_dir = get_run_dir(meta)
        run_dir.joinpath(THUMBS_FILENAME).write_text(json.dumps(thumbs, indent=2), encoding="utf-8")
        update_run_record(meta, thumbnail_cache=str(DEFAULT_CACHE_DIR.resolve()))
        log_run(meta, f"thumbnails generated ({len(thumbs)} images)")
        st.success(f"Generated {len(thumbs)} thumbnails.")
    except Exception as exc:
        st.error(f"Thumbnail generation failed: {exc}")


def handle_embed(config: Dict[str, object]) -> None:
    try:
        meta = get_active_run_meta()
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        if not image_paths:
            st.warning("Scan images first.")
            return

        model, preprocess, _, device = load_clip_resource(meta["model_name"], meta.get("pretrained", PRETRAINED_DEFAULT))
        embeddings = clip_model.embed_images(
            paths=image_paths,
            model=model,
            preprocess=preprocess,
            batch_size=config["batch_size"],
            device=device,
        )
        st.session_state[EMBED_KEY] = embeddings

        run_dir = get_run_dir(meta)
        np.save(run_dir / EMB_FILENAME, embeddings)
        update_run_record(meta, image_embedding_shape=list(embeddings.shape))
        log_run(meta, f"embed completed ({len(image_paths)} images)")
        st.success(f"Embedded {len(image_paths)} images.")
    except Exception as exc:
        st.error(f"Embedding failed: {exc}")


def handle_score(config: Dict[str, object]) -> None:
    try:
        meta = get_active_run_meta()
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        embeddings = st.session_state.get(EMBED_KEY)
        if embeddings is None or len(image_paths) == 0:
            st.warning("Embed images before scoring.")
            return

        root_path = Path(meta["root"])
        labels_path = Path(config["labels_file"])
        if not labels_path.is_absolute():
            labels_path = root_path / labels_path
        if not labels_path.exists():
            st.error(f"Labels file not found: {labels_path}")
            return
        labels = labels_core.load_labels(labels_path)
        if not labels:
            st.warning("No labels loaded; check labels file.")
            return

        model, _, tokenizer, device = load_clip_resource(meta["model_name"], meta.get("pretrained", PRETRAINED_DEFAULT))
        label_embeddings = load_or_create_label_embeddings(labels, tokenizer, model, device, meta)

        results = score_core.score_labels(
            img_emb=embeddings,
            txt_emb=label_embeddings,
            labels=labels,
            topk=config["topk"],
            threshold=config["threshold"],
        )

        scores: List[Dict[str, object]] = []
        for path, entry in zip(image_paths, results):
            over_threshold = [(label, float(score)) for label, score in entry["over_threshold"]]
            scores.append(
                {
                    "path": path,
                    "top1": entry["top1"],
                    "top1_score": float(entry["top1_score"]),
                    "topk_labels": list(entry["topk_labels"]),
                    "topk_scores": [float(v) for v in entry["topk_scores"]],
                    "over_threshold": over_threshold,
                }
            )

        st.session_state[LABELS_KEY] = labels
        st.session_state[LABEL_EMBED_KEY] = label_embeddings
        st.session_state[SCORES_KEY] = scores
        update_gallery_items()

        run_dir = get_run_dir(meta)
        run_dir.joinpath(SCORES_FILENAME).write_text(json.dumps(scores, indent=2), encoding="utf-8")
        update_run_record(meta, labels_file=str(labels_path), topk=config["topk"], threshold=config["threshold"])
        log_run(meta, f"score completed ({len(scores)} images, {len(labels)} labels)")
        st.success(f"Scored {len(scores)} images.")
    except Exception as exc:
        st.error(f"Scoring failed: {exc}")


def handle_medoids() -> None:
    try:
        meta = get_active_run_meta()
        embeddings = st.session_state.get(EMBED_KEY)
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        if embeddings is None or not image_paths:
            st.warning("Embed images before computing medoids.")
            return

        root_path = Path(meta["root"])
        folder_to_indices: Dict[str, List[int]] = {}
        for idx, path_str in enumerate(image_paths):
            img_path = Path(path_str)
            try:
                rel_folder = str(img_path.parent.relative_to(root_path))
            except ValueError:
                rel_folder = img_path.parent.name
            folder_to_indices.setdefault(rel_folder, []).append(idx)

        medoid_info = medoid_core.compute_folder_medoids(folder_to_indices, embeddings)

        run_dir = get_run_dir(meta)
        csv_path = run_dir / MEDOIDS_FILENAME
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["folder", "medoid_rel_path", "cosine_to_centroid"])
            for folder, info in sorted(medoid_info.items()):
                medoid_idx = info["medoid_index"]
                medoid_path = Path(image_paths[medoid_idx])
                try:
                    rel_path = medoid_path.relative_to(root_path)
                except ValueError:
                    rel_path = Path(medoid_path.name)
                writer.writerow([folder, str(rel_path), f"{info['cosine_to_centroid']:.6f}"])

        log_run(meta, f"medoids exported ({len(medoid_info)} folders)")
        st.success(f"Medoids saved to {csv_path}")
    except Exception as exc:
        st.error(f"Medoids failed: {exc}")


def handle_save_approved() -> None:
    try:
        meta = get_active_run_meta()
        approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        if not image_paths:
            st.warning("Nothing to save yet.")
            return

        run_dir = get_run_dir(meta)
        csv_path = run_dir / APPROVED_FILENAME
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["path", "approved_labels"])
            for path in image_paths:
                labels = approved_map.get(path, [])
                writer.writerow([path, "|".join(labels)])

        log_run(meta, "approved labels saved")
        st.success(f"Approved labels saved to {csv_path}")
    except Exception as exc:
        st.error(f"Saving approved labels failed: {exc}")


def handle_export(config: Dict[str, object]) -> None:
    try:
        meta = get_active_run_meta()
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        scores: List[Dict[str, object]] = st.session_state.get(SCORES_KEY, [])
        thumbs: List[Dict[str, object]] = st.session_state.get(THUMBS_KEY, [])
        approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})
        if not scores:
            st.warning("Score images before exporting.")
            return

        thumb_map = {entry["path"]: entry for entry in thumbs}
        score_map = {entry["path"]: entry for entry in scores}
        root_path = Path(meta["root"])

        rows = []
        for path in image_paths:
            score_entry = score_map.get(path, {})
            thumb_entry = thumb_map.get(path, {})
            try:
                rel_path = Path(path).relative_to(root_path)
            except ValueError:
                rel_path = Path(path).name
            rows.append(
                {
                    "path": path,
                    "rel_path": str(rel_path),
                    "width": thumb_entry.get("width", 0),
                    "height": thumb_entry.get("height", 0),
                    "top1": score_entry.get("top1", ""),
                    "top1_score": score_entry.get("top1_score", 0.0),
                    "top5_labels": score_entry.get("topk_labels", [])[: config["topk"]],
                    "top5_scores": [f"{score:.6f}" for score in score_entry.get("topk_scores", [])[: config["topk"]]],
                    "approved_labels": approved_map.get(path, []),
                    "run_id": meta["run_id"],
                    "model_name": meta.get("model_name", ""),
                }
            )

        run_dir = get_run_dir(meta)
        export_path = run_dir / EXPORT_FILENAME
        export_core.write_csv(rows, export_path)
        log_run(meta, f"exported CSV ({len(rows)} rows)")
        st.success(f"Exported CSV to {export_path}")
    except Exception as exc:
        st.error(f"Export failed: {exc}")


def handle_sidecars() -> None:
    try:
        meta = get_active_run_meta()
        approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})
        if not approved_map:
            st.warning("No approved labels to write.")
            return

        paths: List[str] = []
        keywords: List[List[str]] = []
        for path, labels in approved_map.items():
            clean_labels = [label.strip() for label in labels if label.strip()]
            if not clean_labels:
                continue
            paths.append(path)
            keywords.append(clean_labels)
        if not paths:
            st.warning("No approved labels to write.")
            return

        export_core.write_sidecars(paths, keywords)
        log_run(meta, f"sidecars written ({len(paths)} files)")
        st.success(f"Wrote sidecars for {len(paths)} images.")
    except Exception as exc:
        st.error(f"Sidecar writing failed: {exc}")


def load_or_create_label_embeddings(
    labels: Sequence[str],
    tokenizer,
    model,
    device,
    meta: Dict[str, str],
) -> np.ndarray:
    run_dir = get_run_dir(meta)
    meta_path = run_dir / LABEL_META_FILENAME
    emb_path = run_dir / LABEL_EMB_FILENAME
    meta_payload = {
        "labels_hash": hash_labels(labels),
        "model_name": meta.get("model_name"),
        "pretrained": meta.get("pretrained"),
        "prompt": PROMPT_TEMPLATE,
    }

    if meta_path.exists() and emb_path.exists():
        cached_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if cached_meta == meta_payload:
            return np.load(emb_path)

    label_embeddings = clip_model.embed_labels(
        labels=labels,
        model=model,
        tokenizer=tokenizer,
        device=device,
        prompt=PROMPT_TEMPLATE,
    )
    np.save(emb_path, label_embeddings)
    meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")
    return label_embeddings


def hash_labels(labels: Sequence[str]) -> str:
    joined = "\n".join(labels).encode("utf-8")
    return hashlib.sha1(joined).hexdigest()


def update_gallery_items() -> None:
    image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
    thumbs: List[Dict[str, object]] = st.session_state.get(THUMBS_KEY, [])
    scores: List[Dict[str, object]] = st.session_state.get(SCORES_KEY, [])
    thumb_map = {entry["path"]: entry for entry in thumbs}
    score_map = {entry["path"]: entry for entry in scores}

    gallery = []
    for path in image_paths:
        thumb_entry = thumb_map.get(path, {})
        score_entry = score_map.get(path, {})
        gallery.append(
            {
                "path": path,
                "thumbnail": thumb_entry.get("thumbnail"),
                "topk_labels": score_entry.get("topk_labels", []),
                "topk_scores": score_entry.get("topk_scores", []),
            }
        )
    st.session_state[GALLERY_KEY] = gallery


def main() -> None:
    st.set_page_config(page_title="Photo Tagger", layout="wide")
    init_session_state()
    config = sidebar_controls()
    render_control_panel(config)
    render_gallery(threshold=float(config["threshold"]), topk=int(config["topk"]))


if __name__ == "__main__":  # pragma: no cover
    main()
