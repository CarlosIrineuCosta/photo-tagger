#!/usr/bin/env python3
"""
Interactive helper for running the medoids CLI with sensible defaults.
"""

from __future__ import annotations

import shlex
import subprocess
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"
DEFAULT_CLUSTER_MIN_SIZE = 3
DEFAULT_EMBEDDING_THRESHOLD = 0.86
DEFAULT_MAX_EMBEDDING_CLUSTERS = 4


def _latest_run_id(run_dir: Path) -> Optional[str]:
    if not run_dir.exists():
        return None
    candidates = [path for path in run_dir.iterdir() if path.is_dir() and (path / "run.json").exists()]
    if not candidates:
        return None
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    return latest.name


def _prompt(message: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{message}{suffix}: ").strip()
    return value or (default or "")


def _prompt_float(message: str, default: float) -> float:
    while True:
        value = _prompt(message, str(default))
        try:
            return float(value)
        except ValueError:
            print("Please enter a valid number.")


def _prompt_int(message: str, default: int) -> int:
    while True:
        value = _prompt(message, str(default))
        try:
            return max(0, int(value))
        except ValueError:
            print("Please enter a valid integer.")


def _prompt_cluster_mode() -> str:
    options = {
        "1": "simple",
        "2": "tag",
        "3": "hybrid",
    }
    print("Cluster mode options:")
    print("  [1] simple  – folder medoid only")
    print("  [2] tag     – folder + tag clusters")
    print("  [3] hybrid  – folder + tag + embedding clusters")
    choice = _prompt("Select mode", "3")
    return options.get(choice, "hybrid")


def build_command(params: Dict[str, object]) -> str:
    bits = [shlex.quote(sys.executable), "-m", "app.cli.tagger", "medoids", f"--run-id {params['run_id']}"]
    if params.get("output"):
        bits.append(f"--output {shlex.quote(str(params['output']))}")
    if params.get("cluster_mode") == "tag":
        bits.append("--tag-aware")
    if params.get("cluster_mode") == "hybrid":
        bits.extend(["--tag-aware", "--cluster-mode hybrid"])
        bits.append(f"--embedding-threshold {params['embedding_threshold']}")
        if params["max_embedding_clusters"] > 0:
            bits.append(f"--max-embedding-clusters {params['max_embedding_clusters']}")
    if params.get("cluster_min_size") > 0:
        bits.append(f"--cluster-min-size {params['cluster_min_size']}")
    return " ".join(bits)


def main() -> None:
    latest_run = _latest_run_id(RUNS_DIR)
    if latest_run is None:
        print("No runs available. Run the pipeline first.")
        return

    print("Medoids Helper")
    print("--------------")
    run_id = _prompt("Run ID", latest_run)
    cluster_mode = _prompt_cluster_mode()
    cluster_min_size = _prompt_int("Minimum cluster size", DEFAULT_CLUSTER_MIN_SIZE)
    embedding_threshold = DEFAULT_EMBEDDING_THRESHOLD
    max_embedding_clusters = DEFAULT_MAX_EMBEDDING_CLUSTERS
    if cluster_mode == "hybrid":
        while True:
            embedding_threshold = _prompt_float("Embedding cosine threshold (0 < t ≤ 1)", DEFAULT_EMBEDDING_THRESHOLD)
            if 0 < embedding_threshold <= 1:
                break
            print("Threshold must be between 0 and 1.")
        max_embedding_clusters = _prompt_int("Maximum embedding clusters per folder (0 = unlimited)", DEFAULT_MAX_EMBEDDING_CLUSTERS)

    run_output_dir = RUNS_DIR / run_id
    run_output_dir.mkdir(parents=True, exist_ok=True)
    default_output = run_output_dir / "medoids.csv"
    output_path_input = _prompt("Output CSV path", str(default_output))
    output_path_path = Path(output_path_input).expanduser()
    output_path_path.parent.mkdir(parents=True, exist_ok=True)
    output_path = str(output_path_path)

    params = {
        "run_id": run_id,
        "cluster_mode": cluster_mode,
        "cluster_min_size": cluster_min_size,
        "embedding_threshold": embedding_threshold,
        "max_embedding_clusters": max_embedding_clusters,
        "output": output_path,
    }
    command = build_command(params)
    print(f"\nRunning: {command}\n")
    result = subprocess.run(command, shell=True, cwd=str(REPO_ROOT), env=os.environ.copy())

    if result.returncode == 0:
        print(f"\nMedoids written to {output_path}")
        docs_copy = REPO_ROOT / "docs" / "runs" / f"{run_id}_medoids.csv"
        try:
            docs_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output_path, docs_copy)
            print(f"Copied reference CSV to {docs_copy}")
        except Exception as exc:  # pragma: no cover - best effort copy
            print(f"[warn] Unable to copy medoids to docs: {exc}")
        print("You can now use the 'Medoids only' filter in the gallery to review the clusters.")
    else:
        print("Medoids command failed. Check the output above for details.")


if __name__ == "__main__":
    main()
