from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

import hashlib

import numpy as np

from app.core import clip_model, export as export_core, label_pack as label_pack_core, labels as labels_core
from app.core import medoid as medoid_core
from app.core import scan as scan_core
from app.core import score as score_core
from app.core import thumbs as thumbs_core
from app.util import metrics as metrics_core


RUN_RECORD = "run.json"
IMAGES_FILE = "images.txt"
THUMBS_FILE = "thumbnails.json"
IMAGE_EMBED_FILE = "image_embeddings.npy"
LABEL_EMBED_FILE = "label_embeddings.npy"
LABEL_META_FILE = "label_embeddings.json"
SCORES_FILE = "scores.json"
MEDOIDS_FILE = "medoids.csv"
EXPORT_FILE = "results.csv"
APPROVED_FILE = "approved.csv"
LOG_FILE = "log.txt"
NEW_TAGS_FILE = "new_tags.csv"
AUTO_NEW_TAGS = "__AUTO_NEW_TAGS__"


def _now() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _generate_run_id() -> str:
    return _now()


def _ensure_run_path(run_dir: str | Path, run_id: str, create: bool = True) -> Path:
    run_path = Path(run_dir) / run_id
    if create:
        run_path.mkdir(parents=True, exist_ok=True)
    return run_path


def _run_record_path(run_path: Path) -> Path:
    return run_path / RUN_RECORD


def _load_run_record(run_path: Path) -> Dict:
    record_path = _run_record_path(run_path)
    if record_path.exists():
        return json.loads(record_path.read_text(encoding="utf-8"))
    return {}


def _save_run_record(run_path: Path, record: Mapping[str, object]) -> None:
    record_path = _run_record_path(run_path)
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")


def _update_run_record(run_path: Path, **updates) -> Dict:
    record = _load_run_record(run_path)
    record.update(updates)
    _save_run_record(run_path, record)
    return record


def _append_log(run_path: Path, message: str) -> None:
    log_path = run_path / LOG_FILE
    timestamp = datetime.now().isoformat(timespec="seconds")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def _paths_file(run_path: Path) -> Path:
    return run_path / IMAGES_FILE


def _thumbs_file(run_path: Path) -> Path:
    return run_path / THUMBS_FILE


def _scores_file(run_path: Path) -> Path:
    return run_path / SCORES_FILE


def _image_embeddings_file(run_path: Path) -> Path:
    return run_path / IMAGE_EMBED_FILE


def _label_embeddings_file(run_path: Path) -> Path:
    return run_path / LABEL_EMBED_FILE


def _label_meta_file(run_path: Path) -> Path:
    return run_path / LABEL_META_FILE


def _medoids_file(run_path: Path) -> Path:
    return run_path / MEDOIDS_FILE


def _export_file(run_path: Path) -> Path:
    return run_path / EXPORT_FILE


def _approved_file(run_path: Path) -> Path:
    return run_path / APPROVED_FILE


def _read_image_paths(run_path: Path) -> List[str]:
    paths_file = _paths_file(run_path)
    if not paths_file.exists():
        raise FileNotFoundError(f"No scan results found at {paths_file}")
    return [line.strip() for line in paths_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_image_paths(run_path: Path, paths: Sequence[str]) -> None:
    paths_file = _paths_file(run_path)
    paths_file.write_text("\n".join(paths) + ("\n" if paths else ""), encoding="utf-8")


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _duration(start: float) -> float:
    return time.time() - start


def _relative_path(full_path: Path, root: Path) -> str:
    try:
        rel = full_path.relative_to(root)
        return str(rel)
    except ValueError:
        return full_path.name


def _api_state_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / "api_state.json"


def _load_api_state(run_dir: str | Path) -> Dict[str, object]:
    path = _api_state_path(run_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _label_set_from_source(source: str | Path) -> Set[str]:
    path = Path(source).expanduser()
    if path.is_dir():
        pack = label_pack_core.load_label_pack(path)
        return set(pack.labels)
    return set(labels_core.load_labels(path))


def _collect_new_tags(
    state: Mapping[str, object],
    known_labels: Set[str],
    root: Path,
    sample_limit: int = 5,
) -> List[Dict[str, object]]:
    images = state.get("images") if isinstance(state, Mapping) else None
    if not isinstance(images, Mapping):
        return []

    counts: Counter[str] = Counter()
    examples: Dict[str, List[str]] = defaultdict(list)

    for image_path, entry in images.items():
        if not isinstance(entry, Mapping):
            continue
        selected = entry.get("selected")
        if not isinstance(selected, Sequence):
            continue
        normalized = labels_core.normalize_labels(selected)
        if not normalized:
            continue
        relative_hint = _relative_path(Path(image_path), root)
        for tag in normalized:
            counts[tag] += 1
            bucket = examples[tag]
            if len(bucket) < sample_limit:
                bucket.append(relative_hint)

    rows: List[Dict[str, object]] = []
    for tag, count in counts.items():
        if tag in known_labels:
            continue
        rows.append(
            {
                "tag": tag,
                "occurrences": count,
                "examples": examples.get(tag, []),
            }
        )
    rows.sort(key=lambda item: (-int(item["occurrences"]), item["tag"]))
    return rows


def _export_new_tags_csv(
    labels_source: str | Path,
    run_dir: str | Path,
    run_path: Path,
    root: Path,
    output: Optional[str | Path],
) -> Optional[Path]:
    try:
        known_labels = _label_set_from_source(labels_source)
    except FileNotFoundError:
        known_labels = set()
    state = _load_api_state(run_dir)
    new_tags = _collect_new_tags(state, known_labels, root)
    if not new_tags:
        return None

    dest = Path(output) if output and output != AUTO_NEW_TAGS else run_path / NEW_TAGS_FILE
    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tag", "occurrences", "example_images"])
        for row in new_tags:
            examples = row["examples"]
            serialized = "|".join(examples) if isinstance(examples, Sequence) else ""
            writer.writerow([row["tag"], row["occurrences"], serialized])

    return dest


def cmd_scan(args: argparse.Namespace) -> str:
    run_id = args.run_id or _generate_run_id()
    run_path = _ensure_run_path(args.run_dir, run_id, create=True)
    include_exts = args.include or sorted(scan_core.IMAGE_EXTENSIONS)
    start = time.time()
    image_paths = scan_core.scan_directory(
        root=args.root,
        include_exts=include_exts,
        max_images=args.max_images,
    )
    _write_image_paths(run_path, image_paths)
    record = _update_run_record(
        run_path,
        run_id=run_id,
        root=str(Path(args.root).expanduser().resolve()),
        include_exts=list(include_exts),
        image_count=len(image_paths),
    )
    _append_log(run_path, f"scan completed ({len(image_paths)} files) in {_duration(start):.2f}s")
    print(f"[scan] run_id={run_id} files={len(image_paths)}")
    if args.run_id is None:
        print(f"[scan] run directory: {run_path}")
    return run_id


def cmd_thumbs(args: argparse.Namespace) -> None:
    run_path = _ensure_run_path(args.run_dir, args.run_id, create=True)
    image_paths = _read_image_paths(run_path)
    if not image_paths:
        raise RuntimeError("No images available. Run 'scan' first.")

    start = time.time()
    thumbs = thumbs_core.build_thumbnails(
        image_paths=image_paths,
        cache_root=args.cache_root,
        max_edge=args.max_edge,
        overwrite=args.overwrite,
    )
    _write_json(_thumbs_file(run_path), thumbs)
    _update_run_record(run_path, thumbnail_cache=str(Path(args.cache_root).resolve()))
    _append_log(run_path, f"thumbs completed ({len(thumbs)} thumbnails) in {_duration(start):.2f}s")
    print(f"[thumbs] generated {len(thumbs)} thumbnails")


def _load_or_create_label_embeddings(
    run_path: Path,
    labels_list: Sequence[str],
    model: object,
    tokenizer: object,
    device: str | None,
    prompt: str,
    prompts_per_label: Mapping[str, Sequence[str]] | None,
    model_name: str,
    pretrained: str,
) -> np.ndarray:
    label_emb_path = _label_embeddings_file(run_path)
    meta_path = _label_meta_file(run_path)
    expected_meta = {
        "labels_hash": _hash_labels(labels_list),
        "prompt": prompt,
        "model_name": model_name,
        "pretrained": pretrained,
    }
    if prompts_per_label:
        expected_meta["prompt_map_hash"] = label_pack_core.hash_prompt_map(prompts_per_label)
    if label_emb_path.exists() and meta_path.exists():
        cached_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if cached_meta == expected_meta:
            return np.load(label_emb_path)

    embeddings = clip_model.embed_labels(
        labels=labels_list,
        model=model,
        tokenizer=tokenizer,
        device=device,
        prompt=prompt,
        prompts_per_label=dict(prompts_per_label) if prompts_per_label else None,
    )
    np.save(label_emb_path, embeddings)
    meta_path.write_text(json.dumps(expected_meta, indent=2), encoding="utf-8")
    return embeddings


def _hash_labels(labels_list: Sequence[str]) -> str:
    joined = "\n".join(labels_list).encode("utf-8")
    return hashlib.sha1(joined).hexdigest()


def cmd_embed(args: argparse.Namespace) -> None:
    run_path = _ensure_run_path(args.run_dir, args.run_id, create=True)
    image_paths = _read_image_paths(run_path)
    if not image_paths:
        raise RuntimeError("No images available. Run 'scan' first.")

    start = time.time()
    model, preprocess, _, device = clip_model.load_clip(
        model_name=args.model_name,
        pretrained=args.pretrained,
        device=args.device,
    )
    embeddings = clip_model.embed_images(
        paths=image_paths,
        model=model,
        preprocess=preprocess,
        batch_size=args.batch_size,
        device=device,
    )
    np.save(_image_embeddings_file(run_path), embeddings)
    _update_run_record(
        run_path,
        model_name=args.model_name,
        pretrained=args.pretrained,
        device=str(device),
        image_embedding_shape=list(embeddings.shape),
    )
    _append_log(run_path, f"embed completed ({len(image_paths)} images) in {_duration(start):.2f}s")
    print(f"[embed] saved embeddings shape={embeddings.shape}")


def cmd_score(args: argparse.Namespace) -> None:
    run_path = _ensure_run_path(args.run_dir, args.run_id, create=True)
    image_paths = _read_image_paths(run_path)
    if not image_paths:
        raise RuntimeError("No images available. Run 'scan' first.")

    embed_path = _image_embeddings_file(run_path)
    if not embed_path.exists():
        raise FileNotFoundError(f"No image embeddings found at {embed_path}. Run 'embed' first.")
    image_embeddings = np.load(embed_path)

    record = _load_run_record(run_path)
    model_name = args.model_name or record.get("model_name") or "ViT-L-14"
    pretrained = args.pretrained or record.get("pretrained") or "openai"

    prompts_per_label: Mapping[str, Sequence[str]] | None = None
    label_thresholds: Dict[str, float] | None = None
    equivalence_groups: Sequence[Sequence[str]] | None = None
    labels_source = Path(args.labels).expanduser()
    label_pack_dir: str | None = None

    if labels_source.is_dir():
        pack = label_pack_core.load_label_pack(labels_source)
        labels_list = pack.labels
        prompts_per_label = pack.prompts_per_label
        label_thresholds = pack.label_thresholds
        equivalence_groups = pack.equivalence_groups
        label_pack_dir = str(pack.source_dir)
    else:
        labels_list = labels_core.load_labels(labels_source)

    if not labels_list:
        raise RuntimeError(f"No labels loaded from {args.labels}")

    start = time.time()
    model, _, tokenizer, device = clip_model.load_clip(
        model_name=model_name,
        pretrained=pretrained,
        device=args.device,
    )

    label_embeddings = _load_or_create_label_embeddings(
        run_path=run_path,
        labels_list=labels_list,
        model=model,
        tokenizer=tokenizer,
        device=device,
        prompt=args.prompt,
        prompts_per_label=prompts_per_label,
        model_name=model_name,
        pretrained=pretrained,
    )

    results = score_core.score_labels(
        img_emb=image_embeddings,
        txt_emb=label_embeddings,
        labels=labels_list,
        topk=args.topk,
        threshold=args.threshold,
        label_thresholds=label_thresholds,
    )
    serialized = []
    for image_path, entry in zip(image_paths, results):
        serialized.append(
            {
                "path": image_path,
                "top1": entry["top1"],
                "top1_score": float(entry["top1_score"]),
                "topk_labels": entry["topk_labels"],
                "topk_scores": [float(v) for v in entry["topk_scores"]],
                "over_threshold": [
                    {"label": label, "score": float(score)} for label, score in entry["over_threshold"]
                ],
            }
        )
        if equivalence_groups:
            filtered = label_pack_core.reduce_equivalences(serialized[-1]["over_threshold"], equivalence_groups)
            serialized[-1]["over_threshold"] = filtered

    _write_json(_scores_file(run_path), serialized)
    record_update = {
        "labels_file": str(Path(args.labels).expanduser().resolve()),
        "topk": args.topk,
        "threshold": args.threshold,
    }
    if label_pack_dir:
        record_update["label_pack"] = label_pack_dir
    _update_run_record(run_path, **record_update)
    _append_log(run_path, f"score completed ({len(serialized)} images) in {_duration(start):.2f}s")
    print(f"[score] scored {len(serialized)} images using {len(labels_list)} labels")


def cmd_medoids(args: argparse.Namespace) -> None:
    run_path = _ensure_run_path(args.run_dir, args.run_id, create=True)
    image_paths = _read_image_paths(run_path)
    if not image_paths:
        raise RuntimeError("No images available. Run 'scan' first.")
    embed_path = _image_embeddings_file(run_path)
    if not embed_path.exists():
        raise FileNotFoundError(f"No image embeddings found at {embed_path}. Run 'embed' first.")

    record = _load_run_record(run_path)
    root_path = Path(record.get("root", args.root or ".")).expanduser().resolve()

    start = time.time()
    embeddings = np.load(embed_path)
    folder_map: Dict[str, List[int]] = {}
    for idx, path_str in enumerate(image_paths):
        folder = _relative_path(Path(path_str).parent, root_path)
        folder_map.setdefault(folder, []).append(idx)

    tag_lookup: Optional[Dict[int, Sequence[str]]] = None
    if getattr(args, "tag_aware", False):
        scores_map = _load_scores_map(run_path)
        tag_lookup = {}
        for idx, path_str in enumerate(image_paths):
            score_entry = scores_map.get(path_str, {})
            top_labels = []
            if isinstance(score_entry, Mapping):
                over_threshold = score_entry.get("over_threshold")
                if isinstance(over_threshold, Sequence) and over_threshold and isinstance(over_threshold[0], Mapping):
                    top_labels = [item.get("label") for item in over_threshold if isinstance(item, Mapping)]
                if not top_labels:
                    raw_topk = score_entry.get("top5_labels")
                    if isinstance(raw_topk, Sequence):
                        top_labels = [str(label) for label in raw_topk if isinstance(label, str)]
            normalized = labels_core.normalize_labels(top_labels)
            if normalized:
                tag_lookup[idx] = normalized

    medoid_info = medoid_core.compute_folder_medoids(
        folder_map,
        embeddings,
        tags_per_index=tag_lookup,
        use_tag_clusters=bool(getattr(args, "tag_aware", False)),
        min_cluster_size=max(1, getattr(args, "cluster_min_size", 3)),
        cluster_mode=str(getattr(args, "cluster_mode", "simple")).lower(),
        embedding_cluster_threshold=float(
            getattr(args, "embedding_threshold", medoid_core.DEFAULT_EMBEDDING_THRESHOLD)
        ),
        max_embedding_clusters=getattr(args, "max_embedding_clusters", medoid_core.DEFAULT_MAX_EMBEDDING_CLUSTERS),
    )

    rows: List[Tuple[str, str, str, str, int, str, float]] = []

    def _append_row(
        folder_name: str,
        medoid_idx: int,
        cosine: float,
        cluster_type: str,
        cluster_tag: str,
        label_hint: str,
        cluster_size: int,
    ) -> None:
        medoid_path = Path(image_paths[medoid_idx])
        rel_path = _relative_path(medoid_path, root_path)
        rows.append((folder_name, cluster_type, cluster_tag, label_hint, cluster_size, rel_path, cosine))

    for folder, info in medoid_info.items():
        _append_row(
            folder,
            info["medoid_index"],
            info["cosine_to_centroid"],
            "folder",
            "",
            "",
            info.get("size", 0),
        )
        for cluster in info.get("clusters", []):
            cluster_type = str(cluster.get("cluster_type", "tag") or "tag")
            cluster_tag = str(cluster.get("tag", "") or "")
            label_hint = str(cluster.get("label_hint") or cluster_tag)
            _append_row(
                folder,
                cluster["medoid_index"],
                cluster["cosine_to_centroid"],
                cluster_type,
                cluster_tag,
                label_hint,
                cluster.get("size", 0),
            )

    output_path = Path(args.output or _medoids_file(run_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["folder", "cluster_type", "cluster_tag", "label_hint", "cluster_size", "medoid_rel_path", "cosine_to_centroid"]
        )
        for (
            folder,
            cluster_type,
            cluster_tag,
            label_hint,
            cluster_size,
            rel_path,
            cosine,
        ) in sorted(rows, key=lambda item: (item[0], 0 if item[1] == "folder" else 1, item[1], item[2], item[3])):
            writer.writerow([folder, cluster_type, cluster_tag, label_hint, cluster_size, rel_path, f"{cosine:.6f}"])

    _update_run_record(run_path, medoids_file=str(output_path))
    _append_log(run_path, f"medoids completed ({len(rows)} folders) in {_duration(start):.2f}s")
    print(f"[medoids] wrote {len(rows)} rows to {output_path}")


def _load_thumbnail_map(run_path: Path) -> Dict[str, Dict]:
    thumbs_path = _thumbs_file(run_path)
    if not thumbs_path.exists():
        raise FileNotFoundError(f"No thumbnails found at {thumbs_path}. Run 'thumbs' first.")
    thumbnails = _load_json(thumbs_path)
    return {entry["path"]: entry for entry in thumbnails}


def _load_scores_map(run_path: Path) -> Dict[str, Dict]:
    scores_path = _scores_file(run_path)
    if not scores_path.exists():
        raise FileNotFoundError(f"No scores found at {scores_path}. Run 'score' first.")
    entries = _load_json(scores_path)
    return {entry["path"]: entry for entry in entries}


def _load_approved_map(path: Path | None) -> Dict[str, List[str]]:
    approved_map: Dict[str, List[str]] = {}
    if path is None or not path.exists():
        return approved_map
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw = (row.get("approved_labels") or "").split("|")
            labels_list = [label.strip() for label in raw if label.strip()]
            approved_map[row["path"]] = labels_list
    return approved_map


def cmd_export(args: argparse.Namespace) -> None:
    run_path = _ensure_run_path(args.run_dir, args.run_id, create=True)
    image_paths = _read_image_paths(run_path)
    if not image_paths:
        raise RuntimeError("No images available. Run 'scan' first.")

    record = _load_run_record(run_path)
    root_path = Path(record.get("root", args.root or ".")).expanduser().resolve()
    run_id = record.get("run_id", args.run_id)
    model_name = record.get("model_name", "unknown")

    thumbs_map = _load_thumbnail_map(run_path)
    scores_map = _load_scores_map(run_path)

    approved_csv = Path(args.approved) if args.approved else _approved_file(run_path)
    approved_map = _load_approved_map(approved_csv if approved_csv.exists() else None)

    start = time.time()
    rows = []
    for path_str in image_paths:
        thumb_info = thumbs_map.get(path_str, {})
        score_info = scores_map.get(path_str, {})

        topk_labels = score_info.get("topk_labels", [])
        topk_scores = score_info.get("topk_scores", [])
        over_threshold = score_info.get("over_threshold", [])

        approved_labels = approved_map.get(path_str, [])

        rows.append(
            {
                "path": path_str,
                "rel_path": _relative_path(Path(path_str), root_path),
                "width": thumb_info.get("width", 0),
                "height": thumb_info.get("height", 0),
                "top1": score_info.get("top1", ""),
                "top1_score": score_info.get("top1_score", 0.0),
                "top5_labels": topk_labels,
                "top5_scores": [f"{score:.6f}" for score in topk_scores],
                "approved_labels": approved_labels,
                "run_id": run_id,
                "model_name": model_name,
                "over_threshold": over_threshold,
            }
        )

    export_path = Path(args.output or _export_file(run_path))
    export_core.write_csv(rows, export_path)
    _update_run_record(run_path, export_csv=str(export_path))
    _append_log(run_path, f"export completed ({len(rows)} rows) in {_duration(start):.2f}s")
    print(f"[export] wrote {export_path}")


def cmd_sidecars(args: argparse.Namespace) -> None:
    run_path = _ensure_run_path(args.run_dir, args.run_id, create=True)
    source_csv = Path(args.source or _export_file(run_path))
    if not source_csv.exists():
        raise FileNotFoundError(f"Export CSV not found at {source_csv}. Run 'export' first.")

    paths: List[str] = []
    keywords: List[List[str]] = []

    with source_csv.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        column = args.column
        for row in reader:
            labels_raw = row.get(column, "")
            labels_list = [label.strip() for label in labels_raw.split("|") if label.strip()]
            if not labels_list:
                continue
            paths.append(row["path"])
            keywords.append(labels_list)

    if not paths:
        print("[sidecars] no labels to write; skipping")
        return

    start = time.time()
    export_core.write_sidecars(paths, keywords, batch_size=args.batch_size)
    _append_log(run_path, f"sidecars completed ({len(paths)} files) in {_duration(start):.2f}s")
    print(f"[sidecars] wrote metadata for {len(paths)} files")


def cmd_metrics(args: argparse.Namespace) -> None:
    """Compute and display evaluation metrics."""
    try:
        dataset = metrics_core.load_eval_dataset(args.dataset)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading dataset: {e}", file=sys.stderr)
        sys.exit(1)

    if not dataset:
        print("Warning: Dataset is empty", file=sys.stderr)
        return

    # Compute metrics
    precision_at_k = metrics_core.compute_precision_at_k(dataset, k=args.k)
    stack_coverage = metrics_core.compute_stack_coverage(dataset)

    # Display results in a tidy table
    print(f"Evaluation Metrics (n={len(dataset)} images)")
    print("-" * 40)
    print(f"Precision@{args.k}:   {precision_at_k:.4f}")
    print(f"Stack Coverage:       {stack_coverage:.4f}")


def cmd_run(args: argparse.Namespace) -> None:
    run_id = args.run_id or _generate_run_id()
    run_path = _ensure_run_path(args.run_dir, run_id, create=True)

    print(f"[run] starting run_id={run_id}")
    scan_args = argparse.Namespace(
        root=args.root,
        include=args.include,
        max_images=args.max_images,
        run_id=run_id,
        run_dir=args.run_dir,
    )
    cmd_scan(scan_args)

    thumbs_args = argparse.Namespace(
        run_id=run_id,
        run_dir=args.run_dir,
        cache_root=args.cache_root,
        max_edge=args.max_edge,
        overwrite=args.overwrite_thumbs,
    )
    cmd_thumbs(thumbs_args)

    embed_args = argparse.Namespace(
        run_id=run_id,
        run_dir=args.run_dir,
        model_name=args.model_name,
        pretrained=args.pretrained,
        batch_size=args.batch_size,
        device=args.device,
    )
    cmd_embed(embed_args)

    score_args = argparse.Namespace(
        run_id=run_id,
        run_dir=args.run_dir,
        labels=args.labels,
        topk=args.topk,
        threshold=args.threshold,
        model_name=args.model_name,
        pretrained=args.pretrained,
        device=args.device,
        prompt=args.prompt,
    )
    cmd_score(score_args)

    medoid_args = argparse.Namespace(
        run_id=run_id,
        run_dir=args.run_dir,
        output=None,
        root=args.root,
        tag_aware=getattr(args, "tag_aware_medoids", False),
        cluster_min_size=getattr(args, "medoid_cluster_min_size", 3),
        cluster_mode=getattr(args, "medoid_cluster_mode", "simple"),
        embedding_threshold=getattr(args, "medoid_embedding_threshold", medoid_core.DEFAULT_EMBEDDING_THRESHOLD),
        max_embedding_clusters=getattr(
            args, "medoid_max_embedding_clusters", medoid_core.DEFAULT_MAX_EMBEDDING_CLUSTERS
        ),
    )
    cmd_medoids(medoid_args)

    export_args = argparse.Namespace(
        run_id=run_id,
        run_dir=args.run_dir,
        output=None,
        approved=None,
        root=args.root,
    )
    cmd_export(export_args)

    if args.write_sidecars:
        sidecar_args = argparse.Namespace(
            run_id=run_id,
            run_dir=args.run_dir,
            source=None,
            column=args.sidecar_column,
            batch_size=args.batch_size_sidecar,
        )
        cmd_sidecars(sidecar_args)

    if args.export_new_tags:
        record = _load_run_record(run_path)
        root_hint = record.get("root", args.root)
        root_path = Path(root_hint).expanduser().resolve()
        export_dest = _export_new_tags_csv(
            labels_source=args.labels,
            run_dir=args.run_dir,
            run_path=run_path,
            root=root_path,
            output=args.export_new_tags,
        )
        if export_dest:
            print(f"[run] new tags exported to {export_dest}")
        else:
            print("[run] no new user-added tags discovered")

    _append_log(run_path, "run completed")
    print(f"[run] completed run_id={run_id}")


def cmd_benchmark(args: argparse.Namespace) -> None:
    """
    Run a benchmark of the core pipeline stages.
    """
    import random
    
    print(f"Starting benchmark on device: {args.device}")
    
    # 1. Get image list
    all_images = scan_core.scan_directory(root=args.root, include_exts=scan_core.IMAGE_EXTENSIONS)
    if len(all_images) < args.image_count:
        print(f"Warning: Requested {args.image_count} images, but only {len(all_images)} found.")
        images_to_benchmark = all_images
    else:
        images_to_benchmark = random.sample(all_images, args.image_count)
    
    print(f"Using {len(images_to_benchmark)} images for benchmark.")

    # 2. Create benchmark run
    run_id = f"benchmark_{_now()}"
    run_path = _ensure_run_path(args.run_dir, run_id)
    _write_image_paths(run_path, images_to_benchmark)
    
    timings = {}

    # 3. Benchmark thumbnail generation
    print("Benchmarking thumbnail generation...")
    start_thumbs = time.time()
    thumbs_core.build_thumbnails(
        image_paths=images_to_benchmark,
        cache_root=Path(args.run_dir) / "thumb_cache", # Use a dedicated cache for benchmark
        overwrite=True,
    )
    timings["thumbnails"] = time.time() - start_thumbs
    print(f"  -> Thumbnails took: {timings['thumbnails']:.2f}s")

    # 4. Benchmark embedding
    print("Benchmarking embedding...")
    start_embed = time.time()
    model, preprocess, _, device = clip_model.load_clip(device=args.device)
    embeddings = clip_model.embed_images(
        paths=images_to_benchmark,
        model=model,
        preprocess=preprocess,
        device=device,
    )
    np.save(_image_embeddings_file(run_path), embeddings)
    timings["embedding"] = time.time() - start_embed
    print(f"  -> Embedding took: {timings['embedding']:.2f}s")

    # 5. Benchmark scoring
    print("Benchmarking scoring...")
    # For scoring, we need labels. We'll use the default labels.
    labels_list = labels_core.load_labels("labels.txt")
    start_score = time.time()
    _, _, tokenizer, _ = clip_model.load_clip(device=args.device)
    label_embeddings = clip_model.embed_labels(labels=labels_list, model=model, tokenizer=tokenizer, device=device)
    score_core.score_labels(
        img_emb=embeddings,
        txt_emb=label_embeddings,
        labels=labels_list,
    )
    timings["scoring"] = time.time() - start_score
    print(f"  -> Scoring took: {timings['scoring']:.2f}s")

    # 6. Log results
    total_time = sum(timings.values())
    timings["total"] = total_time
    timings["image_count"] = len(images_to_benchmark)
    timings["device"] = args.device

    benchmark_results_path = run_path / "benchmark_results.json"
    _write_json(benchmark_results_path, timings)

    print("\n--- Benchmark Summary ---")
    for stage, duration in timings.items():
        if isinstance(duration, float):
            print(f"- {stage}: {duration:.2f}s")
    print("-------------------------")
    print(f"Results saved to: {benchmark_results_path}")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Photo Tagger CLI")
    parser.add_argument("--run-dir", default="runs", help="Directory where run artifacts are stored")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan directories for images")
    scan_parser.add_argument("--root", required=True, help="Root directory to scan")
    scan_parser.add_argument("--include", nargs="*", help="Additional file extensions to include")
    scan_parser.add_argument("--max-images", type=int, default=None, help="Limit the number of images scanned")
    scan_parser.add_argument("--run-id", help="Existing run identifier (defaults to new timestamp)")
    scan_parser.set_defaults(func=cmd_scan)

    thumbs_parser = subparsers.add_parser("thumbs", help="Generate thumbnails for scanned images")
    thumbs_parser.add_argument("--run-id", required=True, help="Run identifier")
    thumbs_parser.add_argument("--cache-root", default=str(thumbs_core.DEFAULT_CACHE_ROOT), help="Thumbnail cache dir")
    thumbs_parser.add_argument("--max-edge", type=int, default=thumbs_core.DEFAULT_MAX_EDGE, help="Max thumbnail edge")
    thumbs_parser.add_argument("--overwrite", action="store_true", help="Regenerate thumbnails even if cached")
    thumbs_parser.set_defaults(func=cmd_thumbs)

    embed_parser = subparsers.add_parser("embed", help="Embed images using CLIP")
    embed_parser.add_argument("--run-id", required=True, help="Run identifier")
    embed_parser.add_argument("--model-name", default="ViT-L-14", help="CLIP model name")
    embed_parser.add_argument("--pretrained", default="openai", help="CLIP pretrained weights identifier")
    embed_parser.add_argument("--batch-size", type=int, default=64, help="Batch size for embedding")
    embed_parser.add_argument("--device", default=None, help="Device override (cpu/cuda)")
    embed_parser.set_defaults(func=cmd_embed)

    score_parser = subparsers.add_parser("score", help="Score images against labels")
    score_parser.add_argument("--run-id", required=True, help="Run identifier")
    score_parser.add_argument("--labels", default="labels.txt", help="Path to labels file")
    score_parser.add_argument("--topk", type=int, default=5, help="Top-k labels to keep")
    score_parser.add_argument("--threshold", type=float, default=0.25, help="Score threshold for over-threshold list")
    score_parser.add_argument("--model-name", default=None, help="Override CLIP model name")
    score_parser.add_argument("--pretrained", default=None, help="Override pretrained weights identifier")
    score_parser.add_argument("--device", default=None, help="Device override (cpu/cuda)")
    score_parser.add_argument("--prompt", default="a photo of {}", help="Prompt template for label embeddings")
    score_parser.set_defaults(func=cmd_score)

    medoid_parser = subparsers.add_parser("medoids", help="Compute folder medoids")
    medoid_parser.add_argument("--run-id", required=True, help="Run identifier")
    medoid_parser.add_argument("--output", help="Optional output CSV path")
    medoid_parser.add_argument("--root", help="Root directory (defaults to run metadata)")
    medoid_parser.add_argument(
        "--tag-aware",
        action="store_true",
        help="Enable tag-aware clustering before medoid selection",
    )
    medoid_parser.add_argument(
        "--cluster-min-size",
        type=int,
        default=3,
        help="Minimum images per tag cluster when --tag-aware is enabled",
    )
    medoid_parser.add_argument(
        "--cluster-mode",
        choices=("simple", "hybrid"),
        default="simple",
        help="Clustering strategy: simple (tags only) or hybrid (tags plus embedding groups)",
    )
    medoid_parser.add_argument(
        "--embedding-threshold",
        type=float,
        default=medoid_core.DEFAULT_EMBEDDING_THRESHOLD,
        help="Cosine similarity threshold for embedding clusters in hybrid mode",
    )
    medoid_parser.add_argument(
        "--max-embedding-clusters",
        type=int,
        default=medoid_core.DEFAULT_MAX_EMBEDDING_CLUSTERS,
        help="Maximum embedding clusters per folder (0 for unlimited)",
    )
    medoid_parser.set_defaults(func=cmd_medoids)

    export_parser = subparsers.add_parser("export", help="Export results to CSV")
    export_parser.add_argument("--run-id", required=True, help="Run identifier")
    export_parser.add_argument("--output", help="Path to export CSV (defaults to runs/<id>/results.csv)")
    export_parser.add_argument("--approved", help="Optional approved labels CSV path")
    export_parser.add_argument("--root", help="Root directory (defaults to run metadata)")
    export_parser.set_defaults(func=cmd_export)

    sidecar_parser = subparsers.add_parser("sidecars", help="Write .xmp sidecars using ExifTool")
    sidecar_parser.add_argument("--run-id", required=True, help="Run identifier")
    sidecar_parser.add_argument("--source", help="CSV source (defaults to export CSV)")
    sidecar_parser.add_argument("--column", default="approved_labels", help="CSV column containing keywords")
    sidecar_parser.add_argument("--batch-size", type=int, default=256, help="Batch size for ExifTool calls")
    sidecar_parser.set_defaults(func=cmd_sidecars)

    run_parser = subparsers.add_parser("run", help="Execute the full pipeline")
    run_parser.add_argument("--root", required=True, help="Root directory to scan")
    run_parser.add_argument("--include", nargs="*", help="Additional file extensions to include")
    run_parser.add_argument("--max-images", type=int, default=None, help="Limit the number of images")
    run_parser.add_argument("--cache-root", default=str(thumbs_core.DEFAULT_CACHE_ROOT), help="Thumbnail cache dir")
    run_parser.add_argument("--max-edge", type=int, default=thumbs_core.DEFAULT_MAX_EDGE, help="Max thumbnail edge")
    run_parser.add_argument("--overwrite-thumbs", action="store_true", help="Force regenerate thumbnails")
    run_parser.add_argument("--model-name", default="ViT-L-14", help="CLIP model name")
    run_parser.add_argument("--pretrained", default="openai", help="CLIP pretrained weights identifier")
    run_parser.add_argument("--batch-size", type=int, default=64, help="Batch size for CLIP embedding")
    run_parser.add_argument("--device", default=None, help="Device override (cpu/cuda)")
    run_parser.add_argument("--labels", default="labels.txt", help="Labels file path")
    run_parser.add_argument("--topk", type=int, default=5, help="Top-k labels to keep")
    run_parser.add_argument("--threshold", type=float, default=0.25, help="Score threshold")
    run_parser.add_argument("--prompt", default="a photo of {}", help="Prompt template for label embeddings")
    run_parser.add_argument("--run-id", help="Optional existing run identifier")
    run_parser.add_argument("--write-sidecars", action="store_true", help="Write sidecars after export")
    run_parser.add_argument("--sidecar-column", default="approved_labels", help="Column to use for sidecar keywords")
    run_parser.add_argument("--batch-size-sidecar", type=int, default=256, help="Sidecar batch size")
    run_parser.add_argument(
        "--tag-aware-medoids",
        action="store_true",
        help="Enable tag-aware clustering when computing medoids during run",
    )
    run_parser.add_argument(
        "--medoid-cluster-min-size",
        type=int,
        default=3,
        help="Minimum images required per tag cluster when tag-aware medoids are enabled",
    )
    run_parser.add_argument(
        "--medoid-cluster-mode",
        choices=("simple", "hybrid"),
        default="simple",
        help="Clustering strategy for medoids during run (default: simple)",
    )
    run_parser.add_argument(
        "--medoid-embedding-threshold",
        type=float,
        default=medoid_core.DEFAULT_EMBEDDING_THRESHOLD,
        help="Cosine threshold for embedding clusters in hybrid medoid mode",
    )
    run_parser.add_argument(
        "--medoid-max-embedding-clusters",
        type=int,
        default=medoid_core.DEFAULT_MAX_EMBEDDING_CLUSTERS,
        help="Maximum embedding clusters per folder when computing medoids during run (0 for unlimited)",
    )
    run_parser.add_argument(
        "--export-new-tags",
        nargs="?",
        const=AUTO_NEW_TAGS,
        help="Write CSV of user-added tags not in the label pack (optional path overrides default runs/<id>/new_tags.csv)",
    )
    run_parser.set_defaults(func=cmd_run)

    metrics_parser = subparsers.add_parser("metrics", help="Compute evaluation metrics")
    metrics_parser.add_argument("--dataset", required=True, help="Path to JSONL evaluation dataset")
    metrics_parser.add_argument("--k", type=int, default=5, help="K value for Precision@K computation")
    metrics_parser.set_defaults(func=cmd_metrics)

    benchmark_parser = subparsers.add_parser("benchmark", help="Run pipeline performance benchmarks")
    benchmark_parser.add_argument("--root", required=True, help="Root directory of images for benchmarking")
    benchmark_parser.add_argument("--image_count", type=int, default=100, help="Number of images to use for benchmark")
    benchmark_parser.add_argument("--device", default="cpu", help="Device to run benchmarks on (e.g., 'cpu', 'cuda')")
    benchmark_parser.add_argument("--run-dir", default="runs", help="Directory where run artifacts are stored")
    benchmark_parser.set_defaults(func=cmd_benchmark)

    benchmark_parser = subparsers.add_parser("benchmark", help="Run pipeline performance benchmarks")
    benchmark_parser.add_argument("--root", required=True, help="Root directory of images for benchmarking")
    benchmark_parser.add_argument("--image_count", type=int, default=100, help="Number of images to use for benchmark")
    benchmark_parser.add_argument("--device", default="cpu", help="Device to run benchmarks on (e.g., 'cpu', 'cuda')")
    benchmark_parser.add_argument("--run-dir", default="runs", help="Directory where run artifacts are stored")
    benchmark_parser.set_defaults(func=cmd_benchmark)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
        if isinstance(result, str):
            # some commands (scan/run) return run_id for convenience
            print(result)
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
