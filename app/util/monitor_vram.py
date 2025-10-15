#!/usr/bin/env python3
"""
Utility for watching GPU (VRAM) usage with nvidia-smi.

Launch via:

    python -m app.util.monitor_vram

Run this in a dedicated terminal/VS Code panel if you want it visible while
the pipeline executes; it refreshes every 30 seconds by default.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime


DEFAULT_INTERVAL = 30


def ensure_nvidia_smi() -> str:
    exe = shutil.which("nvidia-smi")
    if not exe:
        raise RuntimeError("nvidia-smi not found on PATH. Install NVIDIA drivers first.")
    return exe


def run_once(nvidia_smi: str) -> int:
    try:
        return subprocess.call([nvidia_smi])
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # pragma: no cover - runtime guardrail
        print(f"[monitor_vram] failed to execute nvidia-smi: {exc}", file=sys.stderr)
        return 1


def watch(interval: float, no_clear: bool) -> None:
    nvidia_smi = ensure_nvidia_smi()
    print(f"[monitor_vram] watching GPU every {interval:.1f}s using {nvidia_smi}")

    try:
        while True:
            if not no_clear:
                # ANSI clear; harmless if piped.
                sys.stdout.write("\033[2J\033[H")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"==== {timestamp} ====")
            exit_code = run_once(nvidia_smi)
            if exit_code != 0:
                print(f"[monitor_vram] nvidia-smi exited with code {exit_code}", file=sys.stderr)
            print()  # spacer between refreshes
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[monitor_vram] stopping.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch GPU VRAM usage via nvidia-smi")
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Refresh interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Disable clearing the terminal each refresh.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.interval <= 0:
        raise SystemExit("interval must be positive")
    watch(interval=args.interval, no_clear=args.no_clear)


if __name__ == "__main__":
    main()
