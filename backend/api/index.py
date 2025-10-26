from __future__ import annotations

import base64
import csv
import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.api.enhanced_tagging import router as enhanced_router
from backend.api.tags import router as tags_router
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

from app.core import export as export_core
from app.core import label_pack as label_pack_core
from app.core import labels as labels_core
from app.core import scan as scan_core
from app.core import thumbs as thumbs_core
from app.state.models import ImageState, ReviewStage
from app.util.telemetry import TelemetryEvent, append_event, read_events, run_telemetry_path

app = FastAPI(title="Photo Tagger API", version="0.1.0")

logger = logging.getLogger("backend.api.index")
app.include_router(enhanced_router)
app.include_router(tags_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LabelEntry(BaseModel):
    name: str
    score: float = Field(..., ge=0.0, le=1.0)


class TagRequest(BaseModel):
    filename: str
    approved_labels: List[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    mode: str = Field("both", pattern="^(csv|sidecars|both)$")


class ConfigUpdate(BaseModel):
    root: str | None = None
    labels_file: str | None = None
    run_dir: str | None = None
    thumb_cache: str | None = None
    max_images: int | None = None
    topk: int | None = None
    model_name: str | None = None


class ProcessResponse(BaseModel):
    status: str
    run_id: str | None = None
    detail: str | None = None


class GallerySummaryResponse(BaseModel):
    total: int
    counts: Dict[str, int]
    medoid: Dict[str, object] | None = None
    blocked: Dict[str, object] | None = None


class GalleryPageResponse(BaseModel):
    items: List[dict]
    next_cursor: str | None = None
    has_more: bool = False
    total: int
    summary: GallerySummaryResponse


def _build_gallery_labels(
    base_labels: List[str],
    selected: List[str],
    topk: int,
    filename: str,
) -> List[LabelEntry]:
    entries: List[LabelEntry] = []
    used: set[str] = set()
    for idx, name in enumerate(selected):
        clean = name.strip()
        if not clean or clean in used:
            continue
        used.add(clean)
        score = max(0.1, 0.99 - idx * 0.03)
        entries.append(LabelEntry(name=clean, score=round(score, 2)))

    filename_lower = filename.lower()
    suggestion_target = max(topk, len(entries) + topk)
    suggestion_index = 0
    for name in base_labels:
        clean = name.strip()
        if not clean or clean in used:
            continue
        used.add(clean)
        base_score = 0.65 - 0.05 * suggestion_index
        if clean in filename_lower or clean.replace(" ", "") in filename_lower:
            base_score += 0.2
        score = max(0.1, min(0.95, base_score))
        entries.append(LabelEntry(name=clean, score=round(score, 2)))
        suggestion_index += 1
        if len(entries) >= suggestion_target:
            break
    return entries


class ProcessStatusResponse(BaseModel):
    status: str
    run_id: str | None = None
    started: float | None = None
    detail: str | None = None
    last_event: dict | None = None
    telemetry: List[dict] = Field(default_factory=list)


class ThumbPrefetchRequest(BaseModel):
    paths: List[str] = Field(default_factory=list)
    overwrite: bool = False


class ThumbPrefetchResponse(BaseModel):
    job_id: str
    scheduled: int


class ThumbPrefetchStatusResponse(BaseModel):
    job_id: str
    status: str
    processed: int
    total: int
    errors: List[str] = Field(default_factory=list)


class LLMEnhanceRequest(BaseModel):
    tags: List[str] = Field(default_factory=list)
    language: str | None = None
    max_suggestions: int = 5


class LLMEnhanceResponse(BaseModel):
    original_tags: List[str]
    enhanced_tags: List[str]
    notes: str


class BenchmarkRequest(BaseModel):
    image_count: int = Field(100, ge=1)
    device: str = Field("cpu", min_length=1)


class BenchmarkResponse(BaseModel):
    status: str
    detail: str
    duration_ms: float

CONFIG_PATH = Path("config.yaml")
STATE_LOCK = threading.Lock()
STATE_DATA: Dict[str, dict] | None = None
LABEL_CACHE: List[str] | None = None
LABEL_SOURCE: Path | None = None
LABEL_SIGNATURE: float | None = None
LABEL_PACK: label_pack_core.LabelPack | None = None
THUMB_CACHE: Dict[str, dict] = {}
THUMB_PREFETCH_JOBS: Dict[str, dict] = {}
STATE_VERSION = 1
PROCESS_STATUS: Dict[str, object] = {
    "status": "idle",
    "run_id": None,
    "started": None,
    "detail": None,
    "last_event": None,
}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/routes")
def list_routes() -> List[str]:
    return sorted(route.path for route in app.routes if isinstance(route, APIRoute))


@app.get("/api/diag")
def diag() -> dict:
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    return {
        "cwd": str(Path().resolve()),
        "repo_root_guess": str(repo_root),
        "has_app_dir": (repo_root / "app").is_dir(),
        "pythonpath": os.environ.get("PYTHONPATH", ""),
    }


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _label_signature(path: Path) -> float:
    try:
        if path.is_dir():
            latest = 0.0
            for candidate in path.glob("**/*"):
                try:
                    latest = max(latest, candidate.stat().st_mtime)
                except OSError:
                    continue
            return latest
        return path.stat().st_mtime
    except OSError:
        return 0.0


def load_config() -> dict:
    data = _load_yaml(CONFIG_PATH)
    cwd = Path.cwd()
    data.setdefault("root", str(cwd))
    data.setdefault("labels_file", "")
    data.setdefault("run_dir", "runs")
    data.setdefault("thumb_cache", "thumb_cache")
    data.setdefault("max_images", 100)
    data.setdefault("topk", 6)
    data.setdefault("model_name", "ViT-L-14")
    data.setdefault("max_tiff_mb", 1024)
    data.setdefault("apply_xmp_light", False)
    # ensure labels_file defaults to <root>/labels.txt if not provided or missing
    labels_value = data.get("labels_file")
    root_path = Path(data.get("root", ".")).expanduser()
    fallback_labels = root_path / "labels.txt"
    repo_labels_dir = Path("labels")
    if not labels_value:
        if repo_labels_dir.exists():
            data["labels_file"] = str(repo_labels_dir)
        else:
            data["labels_file"] = str(fallback_labels)
    else:
        labels_path = Path(labels_value).expanduser()
        if not labels_path.exists():
            if repo_labels_dir.exists():
                data["labels_file"] = str(repo_labels_dir)
            elif fallback_labels.exists():
                data["labels_file"] = str(fallback_labels)
    return data


def save_config(update: dict) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(update, handle, sort_keys=True)


def _state_path(cfg: dict) -> Path:
    run_dir = Path(cfg.get("run_dir", "runs"))
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / "api_state.json"


def _load_state_from_disk(cfg: dict) -> Dict[str, dict]:
    path = _state_path(cfg)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    return {"images": {}}


def get_state(cfg: dict) -> Dict[str, dict]:
    global STATE_DATA
    with STATE_LOCK:
        if STATE_DATA is None:
            raw_state = _load_state_from_disk(cfg)
            state, changed = _ensure_state_schema(raw_state)
            STATE_DATA = state
            if changed:
                save_state(cfg, state)
        return STATE_DATA


def save_state(cfg: dict, state: Dict[str, dict]) -> None:
    global STATE_DATA
    state["_version"] = STATE_VERSION
    path = _state_path(cfg)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
    STATE_DATA = state


def _ensure_state_schema(state: Dict[str, dict]) -> Tuple[Dict[str, dict], bool]:
    changed = False
    images = state.get("images")
    if not isinstance(images, dict):
        images = {}
        state["images"] = images
        changed = True

    directory_index = state.get("directory_index")
    if not isinstance(directory_index, dict):
        directory_index = {}
        state["directory_index"] = directory_index
        changed = True

    for path, entry in list(images.items()):
        if not isinstance(entry, dict):
            entry = {}
            images[path] = entry
            changed = True
        image_state = ImageState.from_dict(entry)
        image_state.selected = labels_core.normalize_labels(image_state.selected)
        if image_state.saved:
            image_state.stage = ReviewStage.SAVED
        elif image_state.stage == ReviewStage.SAVED and not image_state.saved:
            image_state.stage = ReviewStage.HAS_DRAFT if image_state.selected else ReviewStage.NEEDS_TAGS
        images[path] = image_state.to_dict()

    if state.get("_version") != STATE_VERSION:
        state["_version"] = STATE_VERSION
        changed = True

    return state, changed


def _get_image_state(images_state: Dict[str, dict], path: str) -> ImageState:
    entry = images_state.get(path)
    if not isinstance(entry, dict):
        return ImageState(stage=ReviewStage.NEW)
    return ImageState.from_dict(entry)


def _set_image_state(images_state: Dict[str, dict], path: str, image_state: ImageState) -> None:
    images_state[path] = image_state.to_dict()


def _scan_with_metadata(root: Path, include_exts: Iterable[str], max_images: Optional[int]) -> Tuple[List[str], Dict[str, dict]]:
    paths = scan_core.scan_directory(root=root, include_exts=include_exts, max_images=max_images)
    metadata: Dict[str, dict] = {}
    for raw_path in paths:
        path = Path(raw_path)
        try:
            stat = path.stat()
        except OSError:
            continue
        metadata[raw_path] = {
            "mtime": float(stat.st_mtime),
            "size": int(stat.st_size),
        }
    return paths, metadata


def _detect_directory_changes(
    previous_index: Mapping[str, Mapping[str, float | int]],
    current_index: Mapping[str, Mapping[str, float | int]],
) -> Tuple[set[str], set[str], set[str]]:
    previous_paths = set(previous_index.keys())
    current_paths = set(current_index.keys())
    new_paths = current_paths - previous_paths
    removed_paths = previous_paths - current_paths
    modified_paths: set[str] = set()
    for path in current_paths & previous_paths:
        previous = previous_index.get(path) or {}
        current = current_index.get(path) or {}
        if (previous.get("mtime"), previous.get("size")) != (current.get("mtime"), current.get("size")):
            modified_paths.add(path)
    return new_paths, modified_paths, removed_paths


def _detect_blocked_files(
    file_index: Mapping[str, Mapping[str, float | int]],
    max_tiff_mb: float,
) -> Dict[str, str]:
    blocked: Dict[str, str] = {}
    limit_bytes = max_tiff_mb * 1024 * 1024
    for path, meta in file_index.items():
        suffix = Path(path).suffix.lower()
        size = int(meta.get("size", 0))
        if suffix in {".tif", ".tiff"} and size > limit_bytes:
            blocked[path] = "oversized_tiff"
    return blocked


def _encode_cursor(index: int) -> str:
    raw = str(max(index, 0)).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(value: Optional[str]) -> int:
    if not value:
        return 0
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii"))
        return max(int(decoded.decode("utf-8")), 0)
    except Exception:
        return 0


def _prune_removed_paths(state: Dict[str, dict], removed_paths: Iterable[str]) -> None:
    images_state = state.setdefault("images", {})
    directory_index = state.setdefault("directory_index", {})
    for path in removed_paths:
        images_state.pop(path, None)
        directory_index.pop(path, None)


def _resolve_review_stage(
    path: str,
    image_state: ImageState,
    *,
    blocked_reason: Optional[str],
    is_new_path: bool,
    is_modified_path: bool,
) -> ReviewStage:
    if blocked_reason:
        return ReviewStage.BLOCKED
    if is_new_path or (image_state.stage == ReviewStage.NEW and image_state.last_processed is None):
        return ReviewStage.NEW
    if image_state.saved:
        if is_modified_path:
            return ReviewStage.NEEDS_TAGS
        return ReviewStage.SAVED
    if image_state.selected:
        return ReviewStage.HAS_DRAFT
    return ReviewStage.NEEDS_TAGS


def _prepare_gallery_records(cfg: dict) -> Tuple[List[dict], Dict[str, int], Dict[str, dict]]:
    root = Path(cfg.get("root", ".")).expanduser()
    max_images = cfg.get("max_images")
    include_exts = scan_core.IMAGE_EXTENSIONS

    paths, metadata = _scan_with_metadata(root, include_exts, max_images)
    state = get_state(cfg)
    images_state = state.setdefault("images", {})
    directory_index = state.setdefault("directory_index", {})

    new_paths, modified_paths, removed_paths = _detect_directory_changes(directory_index, metadata)
    _prune_removed_paths(state, removed_paths)
    blocked_map = _detect_blocked_files(metadata, float(cfg.get("max_tiff_mb", 1024)))

    summary_counts = {stage.value: 0 for stage in ReviewStage}
    blocked_reason_counts: Dict[str, int] = {}
    records: List[dict] = []

    for path in paths:
        meta = metadata.get(path)
        if meta is None:
            continue

        image_state = _get_image_state(images_state, path)

        blocked_reason = blocked_map.get(path)
        image_state.blocked_reason = blocked_reason
        if blocked_reason:
            blocked_reason_counts[blocked_reason] = blocked_reason_counts.get(blocked_reason, 0) + 1

        pending_reasons = [reason for reason in image_state.pending_reasons if reason != "modified"]
        if path in modified_paths:
            pending_reasons.append("modified")
        image_state.pending_reasons = pending_reasons

        stage = _resolve_review_stage(
            path,
            image_state,
            blocked_reason=blocked_reason,
            is_new_path=path in new_paths,
            is_modified_path=path in modified_paths,
        )

        if stage != ReviewStage.SAVED:
            image_state.saved = False
        image_state.stage = stage

        summary_counts[stage.value] = summary_counts.get(stage.value, 0) + 1
        _set_image_state(images_state, path, image_state)
        records.append(
            {
                "path": path,
                "metadata": meta,
                "state": image_state,
                "is_new": path in new_paths,
                "is_modified": path in modified_paths,
            }
        )

    state["directory_index"] = metadata
    state["blocked_reason_counts"] = blocked_reason_counts
    return records, summary_counts, state


def _load_run_context(
    cfg: dict,
    root: Path,
) -> Tuple[Optional[Dict[str, dict]], Dict[str, Dict[str, object]], Path]:
    run_dir = Path(cfg.get("run_dir", "runs"))
    run_path = _latest_run_path(run_dir)
    scores_map: Dict[str, dict] | None = None
    medoid_map: Dict[str, Dict[str, object]] = {}
    run_root_path = root
    if run_path is not None:
        run_meta = _load_run_metadata(run_path)
        raw_root = run_meta.get("root")
        if isinstance(raw_root, str) and raw_root:
            try:
                run_root_path = Path(raw_root).expanduser()
            except Exception:
                run_root_path = root
        else:
            run_root_path = root
        scores_file = run_path / "scores.json"
        if scores_file.exists():
            try:
                with scores_file.open("r", encoding="utf-8") as handle:
                    entries = json.load(handle)
                if isinstance(entries, list):
                    scores_map = _build_scores_lookup(entries)
            except json.JSONDecodeError:
                scores_map = None
        medoid_map = _load_medoid_map(run_path, run_root_path, run_meta)
    return scores_map, medoid_map, run_root_path


def _build_gallery_items(
    records: List[dict],
    *,
    cfg: dict,
    request: Request,
    images_state: Dict[str, dict],
    label_pool: List[str],
    scores_map: Optional[Dict[str, dict]],
    medoid_map: Dict[str, Dict[str, object]],
    run_root_path: Path,
) -> List[dict]:
    cache_root = cfg.get("thumb_cache", "thumb_cache")
    topk = int(cfg.get("topk", 6))
    results: List[dict] = []

    for record in records:
        path = record["path"]
        image_state: ImageState = record["state"]
        is_new = bool(record.get("is_new"))
        is_modified = bool(record.get("is_modified"))

        if not Path(path).exists():
            continue

        thumb_info = _ensure_thumbnail(path, cache_root=cache_root)
        thumb_url = str(request.url_for("get_thumbnail", thumb_name=f"{thumb_info['sha1']}.jpg"))
        sidecar_labels = _extract_sidecar_keywords(path)

        if not image_state.selected and sidecar_labels:
            image_state.selected = sidecar_labels
            image_state.saved = True
            image_state.last_saved = image_state.last_saved or time.time()
            image_state.stage = ReviewStage.SAVED

        selected = labels_core.normalize_labels(image_state.selected)

        thumb_path = thumb_info.get("thumbnail")
        score_entry = None
        if scores_map:
            candidates = [path, str(Path(path).resolve()), Path(path).name]
            if thumb_path:
                candidates.extend([thumb_path, Path(thumb_path).name])
            for candidate in candidates:
                if candidate in scores_map:
                    score_entry = scores_map[candidate]
                    break

        candidate_labels = label_pool
        label_source = "fallback"
        if score_entry:
            topk_labels = score_entry.get("topk_labels")
            if isinstance(topk_labels, list) and topk_labels:
                candidate_labels = [str(label) for label in topk_labels if isinstance(label, str)]
                label_source = "scores"
        elif selected:
            label_source = "sidecar"

        requires_processing = label_source == "fallback" and not selected
        if requires_processing:
            labels = []
        else:
            labels = _build_gallery_labels(candidate_labels, selected, topk, Path(path).name.lower())

        medoid_info = None
        try:
            absolute_path = str(Path(path).resolve())
            medoid_info = medoid_map.get(absolute_path)
        except Exception:
            absolute_path = path
        if medoid_info is None:
            try:
                relative_path = str(Path(path).resolve().relative_to(run_root_path.resolve())).replace("\\", "/")
                medoid_info = medoid_map.get(relative_path)
            except Exception:
                medoid_info = medoid_map.get(path)

        medoid_clusters = medoid_info.get("clusters", []) if medoid_info else []
        medoid_folder = medoid_info.get("folder") if medoid_info else ""
        medoid_cosine = medoid_info.get("cosine_to_centroid") if medoid_info else None
        medoid_cluster_size = medoid_info.get("cluster_size") if medoid_info else None

        # Persist any changes back into state
        _set_image_state(images_state, path, image_state)

        results.append(
            {
                "id": thumb_info["sha1"],
                "filename": Path(path).name,
                "path": path,
                "thumb": thumb_url,
                "width": thumb_info.get("width"),
                "height": thumb_info.get("height"),
                "medoid": bool(medoid_info),
                "medoid_folder": medoid_folder,
                "medoid_clusters": medoid_clusters,
                "medoid_cluster_size": medoid_cluster_size,
                "medoid_cosine_to_centroid": medoid_cosine,
                "saved": image_state.saved,
                "selected": selected,
                "label_source": label_source,
                "requires_processing": requires_processing,
                "labels": [label.dict() for label in labels],
                "stage": image_state.stage.value,
                "first_seen": image_state.first_seen,
                "last_processed": image_state.last_processed,
                "last_saved": image_state.last_saved,
                "blocked_reason": image_state.blocked_reason,
                "pending": list(image_state.pending_reasons),
                "is_new": is_new,
                "is_modified": is_modified,
            }
        )

    return results


def get_label_pool(cfg: dict) -> List[str]:
    global LABEL_CACHE, LABEL_SOURCE, LABEL_PACK
    global LABEL_SIGNATURE
    label_path = Path(cfg.get("labels_file", "")).expanduser()
    resolved_path: Path | None = None

    if label_path.exists():
        resolved_path = label_path
    else:
        repo_labels_dir = Path("labels")
        if repo_labels_dir.exists():
            resolved_path = repo_labels_dir.resolve()
        else:
            resolved_path = None

    signature = _label_signature(resolved_path) if resolved_path else 0.0

    if LABEL_CACHE is not None and LABEL_SOURCE == resolved_path and LABEL_SIGNATURE == signature:
        return LABEL_CACHE

    LABEL_CACHE = None
    LABEL_PACK = None

    if resolved_path and resolved_path.exists():
        try:
            if resolved_path.is_dir():
                LABEL_PACK = label_pack_core.load_label_pack(resolved_path)
                LABEL_CACHE = LABEL_PACK.labels
            else:
                LABEL_CACHE = labels_core.load_labels(resolved_path)
        except Exception:
            LABEL_CACHE = None
            LABEL_PACK = None

    if LABEL_CACHE is None:
        LABEL_CACHE = [
            "portrait",
            "street",
            "night",
            "urban",
            "candid",
            "landscape",
        ]
    LABEL_SOURCE = resolved_path
    LABEL_SIGNATURE = signature
    return LABEL_CACHE


def _normalize_labels(labels: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for label in labels:
        if label is None:
            continue
        text = str(label).strip()
        if not text:
            continue
        if text not in seen:
            seen.add(text)
            normalized.append(text)
    return normalized


def _extract_sidecar_keywords(image_path: str) -> List[str]:
    sidecar = Path(image_path).with_suffix(".xmp")
    if not sidecar.exists():
        return []
    try:
        tree = ET.parse(sidecar)
    except ET.ParseError:
        return []
    root = tree.getroot()
    namespace_subject = "{http://purl.org/dc/elements/1.1/}subject"
    namespace_bag = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Bag"
    namespace_li = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li"

    keywords: List[str] = []
    for subject in root.findall(f".//{namespace_subject}"):
        for bag in subject.findall(f"./{namespace_bag}"):
            for li in bag.findall(f"./{namespace_li}"):
                if li.text:
                    keywords.append(li.text.strip())
    return _normalize_labels(keywords)


def _collect_runs(run_dir: Path) -> List[Path]:
    if not run_dir.exists():
        return []
    runs: List[Path] = []
    for candidate in run_dir.iterdir():
        if not candidate.is_dir():
            continue
        if (candidate / "run.json").exists():
            runs.append(candidate)
    return runs


def _latest_run_path(run_dir: Path) -> Optional[Path]:
    candidates = _collect_runs(run_dir)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _build_scores_lookup(entries: Iterable[dict]) -> Dict[str, dict]:
    lookup: Dict[str, dict] = {}
    for entry in entries:
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        variants = {raw_path}
        try:
            variants.add(str(Path(raw_path).resolve()))
        except Exception:
            pass
        variants.add(Path(raw_path).name)
        for variant in variants:
            lookup[variant] = entry
    return lookup


def _load_run_metadata(run_path: Path) -> Dict[str, object]:
    record_path = run_path / "run.json"
    if not record_path.exists():
        return {}
    try:
        with record_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return {}
    return {}


def _safe_int(value: object) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return 0


def _safe_float(value: object) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _resolve_medoids_csv(
    run_path: Path,
    metadata: Mapping[str, object],
) -> Optional[Path]:
    candidates: List[Path] = []
    default_csv = run_path / "medoids.csv"
    candidates.append(default_csv)

    meta_path = metadata.get("medoids_file")
    if isinstance(meta_path, str) and meta_path.strip():
        candidate = Path(meta_path).expanduser()
        if not candidate.is_absolute():
            candidate = (run_path.parent / candidate).resolve()
        candidates.insert(0, candidate)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_medoid_map(
    run_path: Path,
    root_path: Path,
    metadata: Mapping[str, object],
) -> Dict[str, Dict[str, object]]:
    medoids_csv = _resolve_medoids_csv(run_path, metadata)
    if medoids_csv is None:
        return {}

    medoid_lookup: Dict[str, Dict[str, object]] = {}
    try:
        with medoids_csv.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
    except Exception:
        return {}

    for row in rows:
        rel_path = row.get("medoid_rel_path") or row.get("medoid_path") or row.get("medoid")
        if not isinstance(rel_path, str) or not rel_path.strip():
            continue
        rel_path = rel_path.strip()
        try:
            abs_path = (root_path / rel_path).resolve()
        except Exception:
            continue

        cluster_type = (row.get("cluster_type") or "folder").strip().lower()
        if cluster_type not in {"folder", "tag", "embedding"}:
            cluster_type = "folder"
        cluster_tag = (row.get("cluster_tag") or "").strip()
        label_hint = (row.get("label_hint") or cluster_tag).strip()
        cluster_size = _safe_int(row.get("cluster_size"))
        cosine = _safe_float(row.get("cosine_to_centroid"))
        folder_name = (row.get("folder") or "").strip()

        key = str(abs_path)
        entry = medoid_lookup.setdefault(
            key,
            {
                "folder": folder_name,
                "clusters": [],
            },
        )
        if folder_name and not entry.get("folder"):
            entry["folder"] = folder_name
        cluster_entry = {
            "cluster_type": cluster_type,
            "cluster_tag": cluster_tag,
            "label_hint": label_hint,
            "cluster_size": cluster_size,
            "cosine_to_centroid": cosine,
        }
        clusters = entry.get("clusters", [])
        if isinstance(clusters, list):
            clusters.append(cluster_entry)
            entry["clusters"] = clusters
        if cluster_type == "folder":
            entry["cluster_size"] = cluster_size
            entry["cosine_to_centroid"] = cosine
        rel_key = rel_path.replace("\\", "/")
        medoid_lookup.setdefault(rel_key, entry)

    for entry in medoid_lookup.values():
        clusters = entry.get("clusters", [])
        if isinstance(clusters, list):
            clusters.sort(
                key=lambda cluster: (
                    {"folder": 0, "tag": 1, "embedding": 2}.get(cluster.get("cluster_type", ""), 3),
                    cluster.get("label_hint") or "",
                )
            )
            entry["clusters"] = clusters

    return medoid_lookup





def _ensure_thumbnail(path: str, cache_root: str) -> dict:
    resolved = str(Path(path).resolve())
    cached = THUMB_CACHE.get(resolved)
    if cached and Path(cached["thumbnail"]).exists():
        return cached
    info = thumbs_core.build_thumbnail(path, cache_root=cache_root)
    THUMB_CACHE[resolved] = info
    return info


@app.get("/api/gallery", response_model=GalleryPageResponse)
def get_gallery(request: Request, cursor: str | None = None, limit: int = 25, stage: str | None = None):
    cfg = load_config()
    root = Path(cfg.get("root", ".")).expanduser()
    label_pool = get_label_pool(cfg)

    records, summary_counts, state = _prepare_gallery_records(cfg)
    images_state = state.setdefault("images", {})
    blocked_reason_counts = state.get("blocked_reason_counts", {})
    scores_map, medoid_map, run_root_path = _load_run_context(cfg, root)

    items = _build_gallery_items(
        records,
        cfg=cfg,
        request=request,
        images_state=images_state,
        label_pool=label_pool,
        scores_map=scores_map,
        medoid_map=medoid_map,
        run_root_path=run_root_path,
    )

    if stage:
        try:
            stage_value = ReviewStage(stage).value
            items = [item for item in items if item["stage"] == stage_value]
        except ValueError:
            pass

    save_state(cfg, state)

    start_index = _decode_cursor(cursor)
    page_size = max(1, min(limit or 25, 200))
    end_index = min(len(items), start_index + page_size)
    page_items = items[start_index:end_index]
    has_more = end_index < len(items)
    next_cursor = _encode_cursor(end_index) if has_more else None

    medoid_total = sum(1 for item in items if item.get("medoid"))
    cluster_type_counts: Dict[str, int] = {}
    for item in items:
        if not item.get("medoid"):
            continue
        for cluster in item.get("medoid_clusters") or []:
            kind = str(cluster.get("cluster_type", "unknown"))
            cluster_type_counts[kind] = cluster_type_counts.get(kind, 0) + 1

    summary = GallerySummaryResponse(
        total=len(items),
        counts=summary_counts,
        medoid={
            "total": medoid_total,
            "cluster_types": cluster_type_counts,
        },
        blocked={
            "reasons": blocked_reason_counts,
        },
    )
    return GalleryPageResponse(
        items=page_items,
        next_cursor=next_cursor,
        has_more=has_more,
        total=len(items),
        summary=summary,
    )


@app.post("/api/thumbs/prefetch", response_model=ThumbPrefetchResponse)
def prefetch_thumbnails(request_data: ThumbPrefetchRequest):
    cfg = load_config()
    state = get_state(cfg)
    images_state = state.get("images", {})
    raw_paths = request_data.paths or []
    unique_paths = [path for path in dict.fromkeys(raw_paths) if Path(path).exists()]

    if not unique_paths:
        for path, payload in images_state.items():
            if not isinstance(payload, dict):
                continue
            image_state = ImageState.from_dict(payload)
            if image_state.stage == ReviewStage.NEW:
                if Path(path).exists():
                    unique_paths.append(path)

    unique_paths = [path for path in dict.fromkeys(unique_paths)]

    job_id = uuid.uuid4().hex[:12]
    scheduled = len(unique_paths)
    THUMB_PREFETCH_JOBS[job_id] = {
        "status": "queued",
        "processed": 0,
        "total": scheduled,
        "errors": [],
    }

    cache_root = cfg.get("thumb_cache", "thumb_cache")
    processed = 0
    errors: List[str] = []
    for path in unique_paths:
        try:
            thumbs_core.build_thumbnail(path, cache_root=cache_root, overwrite=request_data.overwrite)
            processed += 1
        except Exception as exc:  # pragma: no cover - best effort utility
            errors.append(f"{path}: {exc}")

    status = "complete" if not errors else "error"
    THUMB_PREFETCH_JOBS[job_id] = {
        "status": status,
        "processed": processed,
        "total": scheduled,
        "errors": errors,
    }

    if errors:
        logger.warning("Thumbnail prefetch job %s completed with errors: %s", job_id, errors)
    else:
        logger.info("Thumbnail prefetch job %s completed successfully (%s/%s)", job_id, processed, scheduled)

    return ThumbPrefetchResponse(job_id=job_id, scheduled=scheduled)


@app.get("/api/thumbs/prefetch/{job_id}", response_model=ThumbPrefetchStatusResponse)
def get_prefetch_job_status(job_id: str):
    job = THUMB_PREFETCH_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Prefetch job not found")
    return ThumbPrefetchStatusResponse(job_id=job_id, **job)


@app.get("/api/thumbs/{thumb_name}")
def get_thumbnail(thumb_name: str):
    cfg = load_config()
    cache_root = Path(cfg.get("thumb_cache", "thumb_cache"))
    path = cache_root / thumb_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(path)


@app.post("/api/tag")
def save_tag(request: TagRequest):
    cfg = load_config()
    state = get_state(cfg)
    filename = request.filename
    approved = _normalize_labels(request.approved_labels)
    approved = _normalize_labels(approved)
    with STATE_LOCK:
        images_state = state.setdefault("images", {})
        images_state[filename] = {
            "selected": approved,
            "saved": bool(approved),
        }
        save_state(cfg, state)
    return {"status": "ok", "saved": bool(approved)}


@app.post("/api/export")
def export_data(request: ExportRequest):
    cfg = load_config()
    state = get_state(cfg)
    root = Path(cfg.get("root", ".")).expanduser()
    run_dir = Path(cfg.get("run_dir", "runs"))
    run_dir.mkdir(parents=True, exist_ok=True)
    saved_entries = {
        path: data for path, data in state.get("images", {}).items() if data.get("saved") and data.get("selected")
    }
    if not saved_entries:
        return {"status": "ok", "files": []}

    rows = []
    for path, data in saved_entries.items():
        full_path = Path(path)
        rel_path = full_path.name
        try:
            rel_path = str(full_path.relative_to(root))
        except ValueError:
            pass
        labels = data.get("selected", [])
        row = {
            "path": str(full_path),
            "rel_path": rel_path,
            "width": None,
            "height": None,
            "top1": labels[0] if labels else None,
            "top1_score": None,
            "top5_labels": labels,
            "top5_scores": [],
            "approved_labels": labels,
            "run_id": "api-session",
            "model_name": cfg.get("model_name"),
        }
        rows.append(row)

    export_path = run_dir / "api_export.csv"
    export_core.write_csv(rows, export_path)
    files = [str(export_path)]

    if request.mode in {"sidecars", "both"}:
        try:
            export_core.write_sidecars(
                list(saved_entries.keys()),
                [entry["selected"] for entry in saved_entries.values()],
            )
        except Exception as exc:  # pragma: no cover - optional dependency
            files.append(f"sidecars_error: {exc}")

    return {"status": "ok", "files": files}


@app.get("/api/config")
def get_config():
    cfg = load_config()
    return cfg


@app.post("/api/config")
def update_config(update: ConfigUpdate):
    cfg = load_config()
    data = cfg.copy()
    for key, value in update.model_dump(exclude_none=True).items():
        data[key] = value
    save_config(data)



@app.post("/api/process", response_model=ProcessResponse)
def process_images():
    cfg = load_config()
    root = cfg.get("root")
    if not root:
        raise HTTPException(status_code=400, detail="Root path not configured")
    labels_value = cfg.get("labels_file") or ""
    run_dir = Path(cfg.get("run_dir", "runs"))
    run_dir.mkdir(parents=True, exist_ok=True)

    run_id = uuid.uuid4().hex[:8]
    labels_path = Path(labels_value).expanduser()
    if not labels_path.exists():
        fallback = Path(root).expanduser() / "labels.txt"
        if fallback.exists():
            labels_path = fallback
        else:
            raise HTTPException(status_code=400, detail=f"labels file not found: {labels_path}")
    cmd = [
        sys.executable,
        "-m",
        "app.cli.tagger",
        "--run-dir",
        str(run_dir),
        "run",
        "--root",
        str(root),
        "--run-id",
        run_id,
        "--labels",
        str(labels_path),
        "--cache-root",
        str(cfg.get("thumb_cache", "thumb_cache")),
        "--model-name",
        str(cfg.get("model_name", "ViT-L-14")),
        "--pretrained",
        str(cfg.get("pretrained", "openai")),
        "--topk",
        str(cfg.get("topk", 5)),
    ]

    max_images = cfg.get("max_images")
    if max_images:
        cmd.extend(["--max-images", str(max_images)])

    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"

    start_time = time.time()
    _update_process_status(status="running", run_id=run_id, started=start_time, detail="Processing images", last_event=None)
    telemetry_path = run_telemetry_path(run_dir, run_id)
    append_event(
        telemetry_path,
        TelemetryEvent(stage="process", event="start", duration_ms=0.0, item_count=None, run_id=run_id),
    )

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        append_event(
            telemetry_path,
            TelemetryEvent(
                stage="process",
                event="error",
                duration_ms=(time.time() - start_time) * 1000.0,
                item_count=None,
                run_id=run_id,
                details={"detail": detail},
            ),
        )
        _update_process_status(status="error", run_id=run_id, detail=detail, last_event={"event": "error"})
        raise HTTPException(status_code=500, detail=detail)
    finally:
        global STATE_DATA
        with STATE_LOCK:
            STATE_DATA = None
        THUMB_CACHE.clear()

    duration_ms = (time.time() - start_time) * 1000.0
    completion_event = TelemetryEvent(
        stage="process",
        event="complete",
        duration_ms=duration_ms,
        item_count=None,
        run_id=run_id,
        details={"stdout": (result.stdout or "").strip()},
    )
    append_event(telemetry_path, completion_event)
    _update_process_status(status="idle", run_id=run_id, detail="Completed", last_event=asdict(completion_event))

    return ProcessResponse(status="ok", run_id=run_id, detail=(result.stdout or "").strip())


def _update_process_status(**updates) -> None:
    PROCESS_STATUS.update(updates)


@app.get("/api/process/status", response_model=ProcessStatusResponse)
def get_process_status():
    cfg = load_config()
    run_dir = Path(cfg.get("run_dir", "runs"))
    run_id = PROCESS_STATUS.get("run_id")
    telemetry_events: List[dict] = []
    if isinstance(run_id, str):
        telemetry_path = run_telemetry_path(run_dir, run_id)
        telemetry_events = [asdict(event) for event in read_events(telemetry_path, limit=20)]
    return ProcessStatusResponse(
        status=str(PROCESS_STATUS.get("status")),
        run_id=run_id if isinstance(run_id, str) else None,
        started=PROCESS_STATUS.get("started"),
        detail=PROCESS_STATUS.get("detail"),
        last_event=PROCESS_STATUS.get("last_event"),
        telemetry=telemetry_events,
    )


@app.post("/api/llm/tags/enhance", response_model=LLMEnhanceResponse)
def enhance_tags_with_llm(request_data: LLMEnhanceRequest):
    cleaned = [label for label in (_normalize_labels(request_data.tags)) if label]
    notes = (
        "LLM enhancement not yet implemented. "
        "This stub simply returns the normalized tags and appends placeholder suggestions."
    )
    suggestions = cleaned[: request_data.max_suggestions]
    if not suggestions:
        suggestions = ["sample-tag"]
    return LLMEnhanceResponse(
        original_tags=request_data.tags,
        enhanced_tags=suggestions,
        notes=notes,
    )


@app.post("/api/process/benchmark", response_model=BenchmarkResponse)
def benchmark_process(request_data: BenchmarkRequest):
    cfg = load_config()
    root = cfg.get("root")
    if not root:
        raise HTTPException(status_code=400, detail="Root path not configured")
    run_dir = Path(cfg.get("run_dir", "runs"))
    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "app.cli.tagger",
        "--run-dir",
        str(run_dir),
        "benchmark",
        "--root",
        str(root),
        "--image_count",
        str(request_data.image_count),
        "--device",
        request_data.device,
    ]
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise HTTPException(status_code=500, detail=detail)

    duration_ms = (time.time() - start) * 1000.0
    detail = (result.stdout or "").strip()
    return BenchmarkResponse(status="ok", detail=detail, duration_ms=duration_ms)
