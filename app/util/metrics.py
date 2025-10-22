"""Metrics utilities for evaluating photo tagging performance.

This module provides functions to compute evaluation metrics for photo tagging,
including Precision@K and stack coverage, as well as utilities to load
evaluation datasets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


@dataclass
class EvaluationItem:
    """Represents a single evaluation item with predicted and expected tags."""
    image_id: str
    predicted_tags: List[str]
    expected_tags: List[str]


def load_eval_dataset(path: str | Path) -> List[EvaluationItem]:
    """Load evaluation dataset from a JSONL file.

    Args:
        path: Path to the JSONL file containing evaluation data.
            Each line should have fields: image_id, predicted_tags, expected_tags.

    Returns:
        List of evaluation items.

    Raises:
        FileNotFoundError: If the specified file doesn't exist.
        ValueError: If a line in the file is not valid JSON or missing required fields.
    """
    dataset = []
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {line_num}: {e}")

            if not all(field in data for field in ["image_id", "predicted_tags", "expected_tags"]):
                raise ValueError(f"Missing required fields on line {line_num}")

            dataset.append(
                EvaluationItem(
                    image_id=str(data["image_id"]),
                    predicted_tags=list(data["predicted_tags"]),
                    expected_tags=list(data["expected_tags"]),
                )
            )

    return dataset


def compute_precision_at_k(dataset: List[EvaluationItem], k: int = 5) -> float:
    """Compute Precision@K for the evaluation dataset.

    Precision@K measures the proportion of correct tags among the top-k predicted tags.

    Args:
        dataset: List of evaluation items.
        k: Number of top predictions to consider.

    Returns:
        Precision@K score as a float between 0 and 1.
    """
    if not dataset:
        return 0.0

    total_precision = 0.0
    evaluated_items = 0

    for item in dataset:
        if not item.predicted_tags or not item.expected_tags:
            continue

        # Get top-k predictions
        top_k_predictions = item.predicted_tags[:k]

        # Count correct predictions
        correct = sum(1 for tag in top_k_predictions if tag in item.expected_tags)

        # Calculate precision for this item
        precision = correct / min(k, len(top_k_predictions))
        total_precision += precision
        evaluated_items += 1

    if evaluated_items == 0:
        return 0.0
    return total_precision / evaluated_items


def compute_stack_coverage(dataset: List[EvaluationItem]) -> float:
    """Compute stack coverage for the evaluation dataset.

    Stack coverage measures the proportion of expected tags that appear anywhere
    in the predicted tags list (not just top-k).

    Args:
        dataset: List of evaluation items.

    Returns:
        Stack coverage score as a float between 0 and 1.
    """
    if not dataset:
        return 0.0

    total_coverage = 0.0
    evaluated_items = 0

    for item in dataset:
        if not item.predicted_tags or not item.expected_tags:
            continue

        # Count expected tags that appear in predictions
        covered = sum(1 for tag in item.expected_tags if tag in item.predicted_tags)

        # Calculate coverage for this item
        coverage = covered / len(item.expected_tags)
        total_coverage += coverage
        evaluated_items += 1

    if evaluated_items == 0:
        return 0.0
    return total_coverage / evaluated_items


__all__ = [
    "EvaluationItem",
    "load_eval_dataset",
    "compute_precision_at_k",
    "compute_stack_coverage",
]
