from __future__ import annotations

from typing import Iterable

import pandas as pd


def _coerce_tag_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace(";", ",").split(",")]
        return [part for part in parts if part]
    if pd.isna(value):
        return []
    return [str(value)]


def format_review_rows(rows: Iterable[pd.Series]) -> pd.DataFrame:
    """
    Convert medoid tagging rows into the flattened review table expected by the
    legacy audit/export steps.
    """
    review_rows = []
    for row in rows:
        if isinstance(row, tuple):
            _, row = row

        ck_tags = ", ".join(_coerce_tag_list(row.get("ck_tags")))
        ai_tags = ", ".join(_coerce_tag_list(row.get("ai_tags")))

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
                "cluster_id": int(row.get("cluster_id")),
                "medoid_id": int(row.get("medoid_id")),
                "selected": row.get("selected", False),
                "apply_cluster": row.get("apply_cluster", True),
                "ck_tags": ck_tags,
                "ai_tags": ai_tags,
                "flags": ", ".join(flags),
            }
        )

    return pd.DataFrame(
        review_rows,
        columns=[
            "cluster_id",
            "medoid_id",
            "selected",
            "apply_cluster",
            "ck_tags",
            "ai_tags",
            "flags",
        ],
    )


__all__ = ["format_review_rows"]
