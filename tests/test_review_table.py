import pandas as pd

from app.util.review_table import format_review_rows


def test_format_review_rows_lists():
    tags_df = pd.DataFrame(
        [
            {
                "cluster_id": 1,
                "medoid_id": 10,
                "ck_tags": ["CK:sun", "CK:tree"],
                "ai_tags": ["AI:sky", "AI:cloud"],
                "selected": True,
                "apply_cluster": False,
                "is_people": True,
                "is_nude_assumed": False,
                "openai_used": True,
                "hand_suppressed": False,
            }
        ]
    )
    review_df = format_review_rows(tags_df.iterrows())
    assert list(review_df.columns) == [
        "cluster_id",
        "medoid_id",
        "selected",
        "apply_cluster",
        "ck_tags",
        "ai_tags",
        "flags",
    ]
    assert review_df.iloc[0]["cluster_id"] == 1
    assert review_df.iloc[0]["medoid_id"] == 10
    selected = review_df.iloc[0]["selected"]
    apply_cluster = review_df.iloc[0]["apply_cluster"]
    assert bool(selected) is True
    assert bool(apply_cluster) is False
    assert review_df.iloc[0]["ck_tags"] == "CK:sun, CK:tree"
    assert review_df.iloc[0]["ai_tags"] == "AI:sky, AI:cloud"
    assert review_df.iloc[0]["flags"] == "people, vision"


def test_format_review_rows_scalar_and_strings():
    tags_df = pd.DataFrame(
        [
            {
                "cluster_id": 2,
                "medoid_id": 20,
                "ck_tags": "CK:one;CK:two",
                "ai_tags": "AI:one, AI:two",
                "selected": "yes",
                "apply_cluster": "false",
                "is_people": False,
                "is_nude_assumed": True,
                "openai_used": False,
                "hand_suppressed": True,
            }
        ]
    )
    review_df = format_review_rows(tags_df.iterrows())
    assert review_df.iloc[0]["ck_tags"] == "CK:one, CK:two"
    assert review_df.iloc[0]["ai_tags"] == "AI:one, AI:two"
    selected = review_df.iloc[0]["selected"]
    apply_cluster = review_df.iloc[0]["apply_cluster"]
    assert bool(selected) is True
    assert bool(apply_cluster) is True
    assert review_df.iloc[0]["flags"] == "nude-sensitive, hand-suppressed"


def test_format_review_rows_empty():
    tags_df = pd.DataFrame(columns=[
        "cluster_id",
        "medoid_id",
        "ck_tags",
        "ai_tags",
        "selected",
        "apply_cluster",
        "is_people",
        "is_nude_assumed",
        "openai_used",
        "hand_suppressed",
    ])
    review_df = format_review_rows(tags_df.iterrows())
    assert review_df.empty
