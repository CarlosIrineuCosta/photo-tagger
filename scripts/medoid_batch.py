#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from app.jobs import Pipeline


def main():
    parser = argparse.ArgumentParser(description="Run medoid tagging batch")
    parser.add_argument("-c", "--config", default="config/config.yaml")
    parser.add_argument("--openai", action="store_true", help="Enable OpenAI Vision for medoids")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text("utf-8"))
    pipeline = Pipeline(cfg)

    required = {
        "index": pipeline.index_path,
        "proxies": pipeline.proxies_path,
        "embeds": pipeline.embeds_path,
        "clusters": pipeline.clusters_path,
    }
    missing = [name for name, path in required.items() if not Path(path).exists()]
    if missing:
        raise FileNotFoundError(f"Missing prerequisite caches: {', '.join(missing)}")

    index_df = pd.read_parquet(pipeline.index_path)
    proxies_df = pd.read_parquet(pipeline.proxies_path)
    embeds_df = pd.read_parquet(pipeline.embeds_path)
    clusters_df = pd.read_parquet(pipeline.clusters_path)

    tags_df = pipeline.medoid_tags(clusters_df, embeds_df, proxies_df, index_df, use_openai=args.openai)
    audit_path = pipeline.export_audit(clusters_df, tags_df)
    print(f"Audit written to {audit_path}")


if __name__ == "__main__":
    main()
