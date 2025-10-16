from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
import time
import base64
import math
from io import BytesIO
from PIL import Image
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
STATUS_LOG_KEY = "status_log"
STATUS_MAX_ITEMS = 20
FILTER_MEDOIDS_KEY = "filter_medoids_only"
FILTER_UNAPPROVED_KEY = "filter_unapproved_only"
HIDE_AFTER_SAVE_KEY = "hide_after_save"
MEDOID_PATHS_KEY = "medoid_paths"
GALLERY_PAGE_KEY = "gallery_page"
GALLERY_PAGE_SIZE_KEY = "gallery_page_size"
THUMB_CROP_KEY = "thumb_crop_center"
PAGE_SIZE_OPTIONS = [24, 48, 96]
PAGE_SIZE_DEFAULT = PAGE_SIZE_OPTIONS[0]

DEFAULT_RUN_DIR = Path("runs")
DEFAULT_CACHE_DIR = Path("thumb_cache")
PRETRAINED_DEFAULT = "openai"
PROMPT_TEMPLATE = "a photo of {}"
MODEL_NAME_DEFAULT = "ViT-L-14"

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
THUMB_TARGET_PX = 320


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
    st.session_state.setdefault(STATUS_LOG_KEY, [])
    st.session_state.setdefault(FILTER_MEDOIDS_KEY, False)
    st.session_state.setdefault(FILTER_UNAPPROVED_KEY, False)
    st.session_state.setdefault(HIDE_AFTER_SAVE_KEY, False)
    st.session_state.setdefault(MEDOID_PATHS_KEY, [])
    st.session_state.setdefault(GALLERY_PAGE_KEY, 0)
    st.session_state.setdefault(GALLERY_PAGE_SIZE_KEY, PAGE_SIZE_DEFAULT)
    st.session_state.setdefault(THUMB_CROP_KEY, False)


@st.cache_resource(show_spinner=True)
def load_clip_resource(model_name: str, pretrained: str = PRETRAINED_DEFAULT):
    return clip_model.load_clip(model_name=model_name, pretrained=pretrained, device=None)


def load_styles() -> None:
    styles_path = Path(__file__).with_name("_styles.css")
    if styles_path.exists():
        st.markdown(f"<style>{styles_path.read_text()}</style>", unsafe_allow_html=True)


def append_status(level: str, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {"time": timestamp, "level": level, "message": message}
    log: List[dict] = st.session_state.get(STATUS_LOG_KEY, [])
    log.append(entry)
    st.session_state[STATUS_LOG_KEY] = log[-STATUS_MAX_ITEMS:]


def render_status_strip() -> None:
    log: List[dict] = st.session_state.get(STATUS_LOG_KEY, [])
    status_container = st.container()
    if not log:
        status_container.markdown("<div class='pt-status pt-status--empty'>No activity yet.</div>", unsafe_allow_html=True)
        return
    entries = "\n".join(
        f"<div class='pt-status pt-status--{item['level']}'><span class='pt-status__time'>{item['time']}</span>"
        f"<span class='pt-status__msg'>{item['message']}</span></div>"
        for item in reversed(log)
    )
    status_container.markdown(f"<div class='pt-status-strip'>{entries}</div>", unsafe_allow_html=True)


def get_medoid_paths() -> set[str]:
    stored = st.session_state.get(MEDOID_PATHS_KEY, [])
    if stored:
        return set(stored)

    meta = st.session_state.get(RUN_META_KEY, {})
    run_dir = meta.get("run_dir")
    root = meta.get("root")
    if not run_dir or not root:
        return set()

    medoid_csv = Path(run_dir) / MEDOIDS_FILENAME
    if not medoid_csv.exists():
        return set()

    medoid_paths: set[str] = set()
    root_path = Path(root)
    try:
        with medoid_csv.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rel_path = row.get("medoid_rel_path")
                if not rel_path:
                    continue
                abs_path = (root_path / rel_path).resolve()
                medoid_paths.add(str(abs_path))
    except Exception as exc:
        append_status("warning", f"Failed to read medoids.csv: {exc}")
        return set()

    st.session_state[MEDOID_PATHS_KEY] = sorted(medoid_paths)
    return medoid_paths


def get_thumbnail_uri(path: Path, crop_center: bool) -> str | None:
    try:
        if crop_center:
            with Image.open(path) as img:
                img = img.convert("RGB")
                width, height = img.size
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                img = img.crop((left, top, left + size, top + size))
                if size != THUMB_TARGET_PX:
                    resample = getattr(Image, "Resampling", Image).LANCZOS
                    img = img.resize((THUMB_TARGET_PX, THUMB_TARGET_PX), resample)
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=90)
                encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
                return f"data:image/jpeg;base64,{encoded}"

        data = path.read_bytes()
        encoded = base64.b64encode(data).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except (FileNotFoundError, OSError):
        return None

def sidebar_controls() -> Dict[str, object]:
    st.sidebar.header("Run configuration")
    meta = st.session_state.get(RUN_META_KEY, {})
    root = st.sidebar.text_input("Root path", value=str(Path.cwd()), key="sidebar_root")
    labels_file = st.sidebar.text_input("Labels file", value="labels.txt", key="sidebar_labels_file")
    model_default = meta.get("model_name", MODEL_NAME_DEFAULT)
    model_name = st.sidebar.text_input(
        "Model name",
        value=model_default,
        key="sidebar_model_name",
        disabled=True,
        help="Model selection is controlled by the run metadata.",
    )
    batch_size = int(st.sidebar.number_input("Batch size", min_value=1, value=64, step=1, key="sidebar_batch_size"))
    topk = int(
        st.sidebar.number_input(
            "Labels per image",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            key="sidebar_topk",
        )
    )
    max_images = int(st.sidebar.number_input("Max images", min_value=1, value=100, step=1, key="sidebar_max_images"))

    if meta.get("run_id"):
        st.sidebar.caption(f"Run: {meta['run_id']}  \nRoot: {meta['root']}")

    return {
        "root": root,
        "labels_file": labels_file,
        "model_name": model_name,
        "batch_size": batch_size,
        "topk": topk,
        "max_images": max_images,
    }


def render_command_bar(config: Dict[str, object]) -> None:
    st.markdown("<div class='pt-command-bar'>", unsafe_allow_html=True)
    header_col, meta_col = st.columns([2.2, 3])
    with header_col:
        st.markdown("<div class='pt-brand'>Photo Tagger</div>", unsafe_allow_html=True)
        st.markdown("<div class='pt-subtitle'>Process · Review · Save</div>", unsafe_allow_html=True)
    with meta_col:
        meta = st.session_state.get(RUN_META_KEY, {})
        if meta.get("run_id"):
            st.markdown(
                f"<div class='pt-run-meta'>Run: <code>{meta['run_id']}</code><br/>Root: <code>{meta['root']}</code></div>",
                unsafe_allow_html=True,
            )

    primary_cols = st.columns([2.0, 1.6, 2.2])
    with primary_cols[0]:
        process_clicked = st.button("Process images", key="cmd_process", width="stretch")
    with primary_cols[1]:
        save_clicked = st.button("Save approved & clear", key="cmd_save_clear", width="stretch")
    with primary_cols[2]:
        export_mode = st.selectbox(
            "Export mode",
            options=["CSV + Sidecars", "CSV only", "Sidecars only"],
            key="select_export_mode",
            label_visibility="collapsed",
        )
        export_clicked = st.button("Export", key="cmd_export", width="stretch")

    toggle_cols = st.columns([1, 1, 1, 1])
    with toggle_cols[0]:
        prev_medoids = st.session_state[FILTER_MEDOIDS_KEY]
        medoids_only = st.toggle("Medoids only", value=prev_medoids, key="toggle_medoids_only")
        if medoids_only != prev_medoids:
            st.session_state[GALLERY_PAGE_KEY] = 0
        st.session_state[FILTER_MEDOIDS_KEY] = medoids_only
    with toggle_cols[1]:
        prev_unapproved = st.session_state[FILTER_UNAPPROVED_KEY]
        unapproved_only = st.toggle(
            "Only unapproved", value=prev_unapproved, key="toggle_unapproved_only"
        )
        if unapproved_only != prev_unapproved:
            st.session_state[GALLERY_PAGE_KEY] = 0
        st.session_state[FILTER_UNAPPROVED_KEY] = unapproved_only
    with toggle_cols[2]:
        hide_after_save = st.toggle(
            "Hide after save", value=st.session_state[HIDE_AFTER_SAVE_KEY], key="toggle_hide_after_save"
        )
        st.session_state[HIDE_AFTER_SAVE_KEY] = hide_after_save
    with toggle_cols[3]:
        crop_mode = st.toggle(
            "Center crop thumbs", value=st.session_state[THUMB_CROP_KEY], key="toggle_thumb_crop"
        )
        st.session_state[THUMB_CROP_KEY] = crop_mode

    st.markdown("</div>", unsafe_allow_html=True)

    if process_clicked:
        handle_process_images(config)
    if save_clicked:
        handle_save_and_clear()
    if export_clicked:
        handle_export_actions(config, export_mode)

    render_status_strip()


def render_gallery(topk: int) -> None:
    gallery_items: List[Dict] = st.session_state.get(GALLERY_KEY, [])
    approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})
    medoid_paths = get_medoid_paths()

    for item in gallery_items:
        path = item.get("path")
        if path:
            resolved = str(Path(path).resolve())
            item["is_medoid"] = resolved in medoid_paths
    st.session_state[GALLERY_KEY] = gallery_items

    st.subheader("Gallery")
    st.write("Approve or adjust labels per image. Use filters, pagination, and quick actions to stay in flow.")

    if st.button("Clear selections", key="btn_clear_selections", width="stretch"):
        approved_map.clear()
        st.session_state[APPROVED_KEY] = approved_map
        append_status("info", "Cleared all selections.")

    if not gallery_items:
        st.info("Run through the pipeline to populate the gallery.")
        return

    medoids_only = st.session_state.get(FILTER_MEDOIDS_KEY, False)
    unapproved_only = st.session_state.get(FILTER_UNAPPROVED_KEY, False)
    filtered: List[Dict] = []
    for item in gallery_items:
        path = item.get("path", "")
        if medoids_only and not item.get("is_medoid"):
            continue
        if unapproved_only and approved_map.get(path):
            continue
        filtered.append(item)

    if not filtered:
        st.info("No images match the current filters.")
        return

    page_size = st.session_state.get(GALLERY_PAGE_SIZE_KEY, PAGE_SIZE_DEFAULT)
    if page_size not in PAGE_SIZE_OPTIONS:
        page_size = PAGE_SIZE_DEFAULT
        st.session_state[GALLERY_PAGE_SIZE_KEY] = page_size

    total = len(filtered)
    max_page = max(0, math.ceil(total / page_size) - 1)
    page = min(st.session_state.get(GALLERY_PAGE_KEY, 0), max_page)
    st.session_state[GALLERY_PAGE_KEY] = page

    ctrl_cols = st.columns([0.8, 1.4, 0.8, 1.6])
    with ctrl_cols[0]:
        if st.button("◀ Prev", disabled=page <= 0, key="btn_gallery_prev", width="stretch"):
            page = max(page - 1, 0)
            st.session_state[GALLERY_PAGE_KEY] = page
    with ctrl_cols[1]:
        page_display = f"Page {page + 1} of {max_page + 1} · {total} images"
        st.markdown(f"<div class='pt-page-info'>{page_display}</div>", unsafe_allow_html=True)
    with ctrl_cols[2]:
        if st.button("Next ▶", disabled=page >= max_page, key="btn_gallery_next", width="stretch"):
            page = min(page + 1, max_page)
            st.session_state[GALLERY_PAGE_KEY] = page
    with ctrl_cols[3]:
        current_index = PAGE_SIZE_OPTIONS.index(page_size)
        selected_size = st.selectbox(
            "Cards per page",
            PAGE_SIZE_OPTIONS,
            index=current_index,
            key="select_gallery_page_size",
        )
        if selected_size != page_size:
            st.session_state[GALLERY_PAGE_SIZE_KEY] = selected_size
            st.session_state[GALLERY_PAGE_KEY] = 0
            page = 0
            page_size = selected_size
            max_page = max(0, math.ceil(total / page_size) - 1)

    page = st.session_state.get(GALLERY_PAGE_KEY, 0)
    page_size = st.session_state.get(GALLERY_PAGE_SIZE_KEY, PAGE_SIZE_DEFAULT)
    max_page = max(0, math.ceil(total / page_size) - 1)
    if page > max_page:
        page = max_page
        st.session_state[GALLERY_PAGE_KEY] = page

    start = page * page_size
    end = start + page_size
    page_items = filtered[start:end]

    crop_center = st.session_state.get(THUMB_CROP_KEY, False)

    st.markdown("<div class='pt-gallery-wrapper'><div class='pt-gallery'>", unsafe_allow_html=True)
    columns = st.columns(6)
    for idx, item in enumerate(page_items):
        column = columns[idx % 6]
        with column:
            render_gallery_item(
                idx=idx,
                item=item,
                approved_map=approved_map,
                topk=topk,
                crop_center=crop_center,
            )
    st.markdown("</div></div>", unsafe_allow_html=True)

    st.session_state[APPROVED_KEY] = approved_map


def render_gallery_item(
    idx: int,
    item: Dict,
    approved_map: Dict[str, List[str]],
    topk: int,
    crop_center: bool,
) -> None:
    image_path = item.get("path", "")
    thumbnail_path = item.get("thumbnail")
    top_labels: Sequence[str] = item.get("topk_labels", [])[:topk]
    top_scores: Sequence[float] = item.get("topk_scores", [])[:topk]
    is_medoid = item.get("is_medoid", False)

    thumb_html = ""
    if thumbnail_path:
        data_uri = get_thumbnail_uri(Path(thumbnail_path), crop_center)
        if data_uri is None and crop_center:
            data_uri = get_thumbnail_uri(Path(thumbnail_path), False)
        if data_uri:
            fit_mode = "cover" if crop_center else "contain"
            thumb_html = (
                f"<div class='pt-thumb'><img src='{data_uri}' style='object-fit:{fit_mode};' alt='thumbnail'/></div>"
            )
    if not thumb_html:
        thumb_html = "<div class='pt-thumb pt-thumb--missing'>(no thumbnail)</div>"

    name = Path(image_path).name or "Image"
    header_html = (
        f"<div class='pt-card-header'><span class='pt-title' title='{image_path}'>{name}</span>"
    )
    if is_medoid:
        header_html += "<span class='pt-tag pt-tag--medoid'>Medoid</span>"
    header_html += "</div>"

    top_html = ""
    if top_labels and top_scores:
        top_html = (
            f"<div class='pt-top1'>Top label: <strong>{top_labels[0]}</strong> "
            f"({top_scores[0]:.2f})</div>"
        )

    card_classes = ["pt-card"]
    if is_medoid:
        card_classes.append("pt-card--medoid")
    st.markdown(f"<div class='{ ' '.join(card_classes) }'>", unsafe_allow_html=True)
    st.markdown(thumb_html, unsafe_allow_html=True)
    st.markdown(header_html, unsafe_allow_html=True)
    if top_html:
        st.markdown(top_html, unsafe_allow_html=True)
    else:
        st.markdown("<div class='pt-top1 pt-top1--empty'>(no scores yet)</div>", unsafe_allow_html=True)

    current = set(approved_map.get(image_path, []))
    selections: List[str] = []
    if top_labels and top_scores:
        checkbox_container = st.container()
        with checkbox_container:
            for label, score in zip(top_labels, top_scores):
                checked = st.checkbox(
                    f"{label} ({score:.2f})",
                    value=label in current,
                    key=f"approved_{idx}_{label}",
                )
                if checked:
                    selections.append(label)
    approved_map[image_path] = selections
    st.markdown("</div>", unsafe_allow_html=True)



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


def handle_scan(config: Dict[str, object]) -> bool:
    try:
        root_path = ensure_root_path(config["root"])
        if not root_path.exists():
            append_status("error", f"Root not found: {root_path}")
            return False
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
        st.session_state[MEDOID_PATHS_KEY] = []
        st.session_state[GALLERY_PAGE_KEY] = 0

        run_dir = get_run_dir(meta)
        run_dir.joinpath(IMAGES_FILENAME).write_text("\n".join(image_paths), encoding="utf-8")
        update_run_record(
            meta,
            model_name=config["model_name"],
            max_images=max_images,
            batch_size=config["batch_size"],
            topk=config["topk"],
        )
        log_run(meta, f"scan completed ({len(image_paths)} files)")
        append_status("success", f"Scanned {len(image_paths)} images.")
        return True
    except Exception as exc:  # pragma: no cover - UI feedback
        append_status("error", f"Scan failed: {exc}")
        return False


def handle_thumbs() -> bool:
    try:
        meta = get_active_run_meta()
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        if not image_paths:
            append_status("warning", "Run a scan before generating thumbnails.")
            return False
        thumbs = thumbs_core.build_thumbnails(image_paths=image_paths, cache_root=DEFAULT_CACHE_DIR)
        st.session_state[THUMBS_KEY] = thumbs
        update_gallery_items()

        run_dir = get_run_dir(meta)
        run_dir.joinpath(THUMBS_FILENAME).write_text(json.dumps(thumbs, indent=2), encoding="utf-8")
        update_run_record(meta, thumbnail_cache=str(DEFAULT_CACHE_DIR.resolve()))
        log_run(meta, f"thumbnails generated ({len(thumbs)} images)")
        append_status("success", f"Generated {len(thumbs)} thumbnails.")
        return True
    except Exception as exc:
        append_status("error", f"Thumbnail generation failed: {exc}")
        return False


def handle_embed(config: Dict[str, object]) -> bool:
    try:
        meta = get_active_run_meta()
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        if not image_paths:
            append_status("warning", "Scan images before embedding.")
            return False

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
        append_status("success", f"Embedded {len(image_paths)} images.")
        return True
    except Exception as exc:
        append_status("error", f"Embedding failed: {exc}")
        return False


def handle_score(config: Dict[str, object]) -> bool:
    try:
        meta = get_active_run_meta()
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        embeddings = st.session_state.get(EMBED_KEY)
        if embeddings is None or len(image_paths) == 0:
            append_status("warning", "Embed images before scoring.")
            return False

        root_path = Path(meta["root"])
        labels_path = Path(config["labels_file"])
        if not labels_path.is_absolute():
            labels_path = root_path / labels_path
        if not labels_path.exists():
            append_status("error", f"Labels file not found: {labels_path}")
            return False
        labels = labels_core.load_labels(labels_path)
        if not labels:
            append_status("warning", "No labels loaded; check labels file.")
            return False

        model, _, tokenizer, device = load_clip_resource(meta["model_name"], meta.get("pretrained", PRETRAINED_DEFAULT))
        label_embeddings = load_or_create_label_embeddings(labels, tokenizer, model, device, meta)

        results = score_core.score_labels(
            img_emb=embeddings,
            txt_emb=label_embeddings,
            labels=labels,
            topk=config["topk"],
        )

        scores: List[Dict[str, object]] = []
        for path, entry in zip(image_paths, results):
            scores.append(
                {
                    "path": path,
                    "top1": entry["top1"],
                    "top1_score": float(entry["top1_score"]),
                    "topk_labels": list(entry["topk_labels"]),
                    "topk_scores": [float(v) for v in entry["topk_scores"]],
                }
            )

        st.session_state[LABELS_KEY] = labels
        st.session_state[LABEL_EMBED_KEY] = label_embeddings
        st.session_state[SCORES_KEY] = scores
        update_gallery_items()

        run_dir = get_run_dir(meta)
        run_dir.joinpath(SCORES_FILENAME).write_text(json.dumps(scores, indent=2), encoding="utf-8")
        update_run_record(meta, labels_file=str(labels_path), topk=config["topk"])
        log_run(meta, f"score completed ({len(scores)} images, {len(labels)} labels)")
        append_status("success", f"Scored {len(scores)} images against {len(labels)} labels.")
        return True
    except Exception as exc:
        append_status("error", f"Scoring failed: {exc}")
        return False


def handle_medoids() -> bool:
    try:
        meta = get_active_run_meta()
        embeddings = st.session_state.get(EMBED_KEY)
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        if embeddings is None or not image_paths:
            append_status("warning", "Embed images before computing medoids.")
            return False

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
        medoid_paths: set[str] = set()
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
                medoid_paths.add(str(medoid_path.resolve()))

        log_run(meta, f"medoids exported ({len(medoid_info)} folders)")
        st.session_state[MEDOID_PATHS_KEY] = sorted(medoid_paths)
        update_gallery_items()
        append_status("success", f"Medoids saved to {csv_path}")
        return True
    except Exception as exc:
        append_status("error", f"Medoids failed: {exc}")
        return False


def handle_save_approved() -> bool:
    try:
        meta = get_active_run_meta()
        approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        if not image_paths:
            append_status("warning", "Nothing to save yet.")
            return False

        run_dir = get_run_dir(meta)
        csv_path = run_dir / APPROVED_FILENAME
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["path", "approved_labels"])
            for path in image_paths:
                labels = approved_map.get(path, [])
                writer.writerow([path, "|".join(labels)])

        log_run(meta, "approved labels saved")
        append_status("success", f"Approved labels saved to {csv_path}")
        return True
    except Exception as exc:
        append_status("error", f"Saving approved labels failed: {exc}")
        return False


def handle_export(config: Dict[str, object]) -> bool:
    try:
        meta = get_active_run_meta()
        image_paths: List[str] = st.session_state.get(IMAGE_PATHS_KEY, [])
        scores: List[Dict[str, object]] = st.session_state.get(SCORES_KEY, [])
        thumbs: List[Dict[str, object]] = st.session_state.get(THUMBS_KEY, [])
        approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})
        if not scores:
            append_status("warning", "Score images before exporting.")
            return False

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
        append_status("success", f"Exported CSV to {export_path}")
        return True
    except Exception as exc:
        append_status("error", f"Export failed: {exc}")
        return False


def handle_sidecars() -> bool:
    try:
        meta = get_active_run_meta()
        approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})
        if not approved_map:
            append_status("warning", "No approved labels to write.")
            return False

        paths: List[str] = []
        keywords: List[List[str]] = []
        for path, labels in approved_map.items():
            clean_labels = [label.strip() for label in labels if label.strip()]
            if not clean_labels:
                continue
            paths.append(path)
            keywords.append(clean_labels)
        if not paths:
            append_status("warning", "No approved labels to write.")
            return False

        export_core.write_sidecars(paths, keywords)
        log_run(meta, f"sidecars written ({len(paths)} files)")
        append_status("success", f"Wrote sidecars for {len(paths)} images.")
        return True
    except Exception as exc:
        append_status("error", f"Sidecar writing failed: {exc}")
        return False


def handle_process_images(config: Dict[str, object]) -> None:
    start = time.time()
    append_status("info", "Process images started.")
    steps = [
        ("Scan", lambda: handle_scan(config)),
        ("Thumbnails", handle_thumbs),
        ("Embed", lambda: handle_embed(config)),
        ("Score", lambda: handle_score(config)),
        ("Medoids", handle_medoids),
    ]
    for label, action in steps:
        if not action():
            append_status("warning", f"Process images aborted during {label}.")
            return

    duration = time.time() - start
    image_count = len(st.session_state.get(IMAGE_PATHS_KEY, []))
    thumb_count = len(st.session_state.get(THUMBS_KEY, []))
    medoid_path = Path(st.session_state.get(RUN_META_KEY, {}).get("run_dir", ".")) / MEDOIDS_FILENAME
    medoid_rows = 0
    if medoid_path.exists():
        try:
            medoid_rows = sum(1 for _ in medoid_path.read_text(encoding="utf-8").splitlines()[1:] if _)
        except Exception:
            medoid_rows = 0
    st.session_state[GALLERY_PAGE_KEY] = 0
    append_status(
        "success",
        f"Process complete — {image_count} images, {thumb_count} thumbs, {medoid_rows} medoids in {duration:.2f}s.",
    )


def handle_save_and_clear() -> None:
    success = handle_save_approved()
    if not success:
        return

    approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})
    approved_paths = {path for path, labels in approved_map.items() if labels}

    st.session_state[APPROVED_KEY] = {}

    if st.session_state.get(HIDE_AFTER_SAVE_KEY) and approved_paths:
        gallery = [
            item for item in st.session_state.get(GALLERY_KEY, []) if item.get("path") not in approved_paths
        ]
        st.session_state[GALLERY_KEY] = gallery
        append_status("info", f"Removed {len(approved_paths)} cards from the gallery after save.")
        st.session_state[GALLERY_PAGE_KEY] = 0


def handle_export_actions(config: Dict[str, object], mode: str) -> None:
    if mode == "CSV only":
        handle_export(config)
    elif mode == "Sidecars only":
        handle_sidecars()
    else:
        if handle_export(config):
            handle_sidecars()


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
    approved_map: Dict[str, List[str]] = st.session_state.get(APPROVED_KEY, {})
    thumb_map = {entry["path"]: entry for entry in thumbs}
    score_map = {entry["path"]: entry for entry in scores}
    medoid_paths = get_medoid_paths()

    gallery = []
    medoid_paths = get_medoid_paths()

    for path in image_paths:
        thumb_entry = thumb_map.get(path, {})
        score_entry = score_map.get(path, {})
        resolved = str(Path(path).resolve())
        gallery.append(
            {
                "path": path,
                "thumbnail": thumb_entry.get("thumbnail"),
                "topk_labels": score_entry.get("topk_labels", []),
                "topk_scores": score_entry.get("topk_scores", []),
                "width": thumb_entry.get("width"),
                "height": thumb_entry.get("height"),
                "is_medoid": resolved in medoid_paths,
                "approved": approved_map.get(path, []),
            }
        )
    st.session_state[GALLERY_KEY] = gallery


def main() -> None:
    st.set_page_config(page_title="Photo Tagger", layout="wide")
    load_styles()
    init_session_state()
    config = sidebar_controls()
    render_command_bar(config)
    render_gallery(topk=int(config["topk"]))


if __name__ == "__main__":  # pragma: no cover
    main()
