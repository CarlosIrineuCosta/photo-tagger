#!/usr/bin/env python3
"""Minimal smoke test for photo-tag-pipeline.

Creates synthetic JPEGs, runs the pipeline end-to-end, and performs a dry-run
of XMP writing (unless --write is supplied).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from PIL import Image

from app.jobs import Pipeline


def make_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Run smoke test with synthetic images")
    ap.add_argument(
        "--config",
        default="config/config.example.yaml",
        help="Base config file to load (values overridden for smoke test)",
    )
    ap.add_argument(
        "--root",
        default="tests/smoke/photos",
        help="Directory where synthetic images will be written",
    )
    ap.add_argument(
        "--cache",
        default="tests/smoke/cache",
        help="Cache directory for smoke test (proxies/embeds/etc.)",
    )
    ap.add_argument("--num-images", type=int, default=8, help="Number of synthetic images to create")
    ap.add_argument("--write", action="store_true", help="Perform real XMP writes (default: dry run)")
    ap.add_argument(
        "--wipe",
        action="store_true",
        help="Remove existing smoke-test root/cache directories before running",
    )
    return ap


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def create_synthetic_images(root: Path, count: int) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    rng = np.random.default_rng(42)
    palette = [
        (230, 57, 70),
        (29, 53, 87),
        (244, 162, 97),
        (42, 157, 143),
        (253, 231, 76),
        (214, 93, 177),
        (0, 119, 182),
        (65, 72, 51),
    ]
    for idx in range(count):
        color = palette[idx % len(palette)]
        img = Image.new("RGB", (640, 480), color=color)
        # draw a gradient stripe for variability
        arr = np.array(img)
        arr[:, :, 0] = np.clip(arr[:, :, 0] + rng.integers(-30, 30), 0, 255)
        arr[:, :, 1] = np.clip(arr[:, :, 1] + rng.integers(-30, 30), 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] + rng.integers(-30, 30), 0, 255)
        img = Image.fromarray(arr.astype(np.uint8))
        out_path = root / f"smoke_{idx:03d}.jpg"
        img.save(out_path, quality=95)
        paths.append(out_path)
    return paths


def run_pipeline(cfg: dict, write: bool) -> None:
    pipeline = Pipeline(cfg)
    index_df = pipeline.run_scan()
    proxies_df = pipeline.run_proxies(index_df)
    embeds_df = pipeline.run_embed(proxies_df)
    clusters_df = pipeline.run_cluster(index_df, embeds_df)
    tags_df = pipeline.medoid_tags(clusters_df, embeds_df, proxies_df, index_df, use_openai=False)

    if tags_df.empty:
        print("No clusters produced during smoke test.")
        return

    # Prepare review dataframe: select every cluster, set simple tags.
    review_df = pd.DataFrame(
        {
            "cluster_id": tags_df["cluster_id"],
            "ck_tags": ["CK:smoke"] * len(tags_df),
            "ai_tags": ["AI:test"] * len(tags_df),
            "apply_cluster": False,
            "selected": True,
        }
    )
    pipeline.update_medoid_tags(review_df)
    updated_tags = pipeline.load_medoid_tags_df()
    operations = pipeline.write_clusters(
        cluster_ids=list(updated_tags["cluster_id"]),
        clusters_df=clusters_df,
        tags_df=updated_tags,
        index_df=index_df,
        dry_run=not write,
    )
    action = "dry run" if not write else "write"
    print(f"Smoke test {action} complete: {len(operations)} file(s) across {len(updated_tags)} cluster(s).")
    if operations:
        sample = operations[0]
        print(f"Example → cluster {sample['cluster_id']} → {sample['path']} → {sample['keywords']}")


def main() -> None:
    ap = make_argparser()
    args = ap.parse_args()

    root = Path(args.root)
    cache = Path(args.cache)
    if args.wipe:
        if root.exists():
            shutil.rmtree(root)
        if cache.exists():
            shutil.rmtree(cache)
    root.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    create_synthetic_images(root, args.num_images)

    cfg = load_config(Path(args.config))
    cfg.setdefault("runtime", {})["cache_root"] = str(cache)
    cfg["roots"] = [str(root)]
    cfg.setdefault("runtime", {})["reuse_cache"] = False
    cfg.setdefault("people_policy", {})["allow_openai_on_people_sets"] = False
    cfg.setdefault("ai_tagging", {})["use_openai_vision"] = False

    run_pipeline(cfg, write=args.write)


if __name__ == "__main__":
    main()
