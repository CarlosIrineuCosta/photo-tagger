#!/usr/bin/env python3
"""
Prepare a tag analysis brief from pipeline export and label pack.

This script analyzes a CSV export from the photo-tagger pipeline and generates
a brief with information about orphan tags, canonical groups, alias mappings,
and suggested questions for label refinement.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.label_pack import load_label_pack, LabelPack


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a tag analysis brief from pipeline export and label pack"
    )
    parser.add_argument(
        "--export",
        type=str,
        required=True,
        help="Path to pipeline export CSV file",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        required=True,
        help="Path to label pack directory or YAML manifest",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="Maximum number of frequent orphan tags to include (default: 50)",
    )
    parser.add_argument(
        "--include-canonical",
        action="store_true",
        help="Include canonical tags in the analysis sorted by frequency",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output path for the brief (JSON or Markdown)",
    )
    return parser.parse_args()


def load_export_data(file_path: str) -> List[Dict[str, str]]:
    """Load and parse the export file (CSV or JSON)."""
    path = Path(file_path)

    if path.suffix.lower() == ".json":
        # Load JSON file
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Convert JSON format to CSV-like format
        result = []
        for item in data:
            # Extract tags from topk_labels and over_threshold
            topk_labels = item.get("topk_labels", [])
            over_threshold = item.get("over_threshold", [])

            # Get approved labels (those over threshold)
            approved_labels = [label_item["label"] for label_item in over_threshold]

            # Get top5 labels
            top5_labels = "|".join(topk_labels[:5]) if topk_labels else ""

            # Get top5 scores
            top5_scores = item.get("topk_scores", [])[:5]
            top5_scores_str = "|".join(str(score) for score in top5_scores) if top5_scores else ""

            # Get top1 and score
            top1 = item.get("top1", "")
            top1_score = item.get("top1_score", 0)

            result.append({
                "path": item.get("path", ""),
                "rel_path": Path(item.get("path", "")).name,
                "width": "",
                "height": "",
                "top1": top1,
                "top1_score": top1_score,
                "top5_labels": top5_labels,
                "top5_scores": top5_scores_str,
                "approved_labels": "|".join(approved_labels),
                "run_id": "",
                "model_name": ""
            })

        return result
    else:
        # Load CSV file
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)


def extract_all_tags(export_data: List[Dict[str, str]]) -> List[str]:
    """Extract all tags from the export data."""
    all_tags = []

    for row in export_data:
        # Extract from approved_labels column
        approved = row.get("approved_labels", "")
        if approved:
            all_tags.extend(tag.strip() for tag in approved.split("|") if tag.strip())

        # Extract from top5_labels column
        top5 = row.get("top5_labels", "")
        if top5:
            all_tags.extend(tag.strip() for tag in top5.split("|") if tag.strip())

    return all_tags


def find_orphan_tags(
    all_tags: List[str],
    label_pack: LabelPack,
    top_n: int = 50
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """
    Find orphan tags (tags not in the canonical label set) and their frequencies.
    Also return all tags sorted by frequency for analysis.
    """
    # Count tag occurrences
    tag_counter = Counter(all_tags)

    # Filter out tags that are in the canonical label set
    canonical_tags = set(label_pack.labels)
    orphan_tags = {
        tag: count for tag, count in tag_counter.items()
        if tag not in canonical_tags
    }

    # Get the top N most frequent orphan tags
    top_orphans = Counter(orphan_tags).most_common(top_n)

    orphan_result = []
    for tag, count in top_orphans:
        # Try to suggest a group based on similarity to existing groups
        suggested_group = suggest_group_for_tag(tag, label_pack)

        # Calculate some simple scores
        scores = {
            "frequency": count,
            "frequency_ratio": count / len(all_tags),
        }

        orphan_result.append({
            "tag": tag,
            "occurrences": count,
            "suggested_group": suggested_group,
            "scores": scores,
        })

    # Get all tags sorted by frequency (including canonical ones)
    all_tags_sorted = tag_counter.most_common()
    all_tags_result = []
    for tag, count in all_tags_sorted:
        is_canonical = tag in canonical_tags
        suggested_group = suggest_group_for_tag(tag, label_pack) if not is_canonical else None

        scores = {
            "frequency": count,
            "frequency_ratio": count / len(all_tags),
        }

        all_tags_result.append({
            "tag": tag,
            "occurrences": count,
            "is_canonical": is_canonical,
            "suggested_group": suggested_group,
            "scores": scores,
        })

    return orphan_result, all_tags_result


def suggest_group_for_tag(tag: str, label_pack: LabelPack) -> str:
    """
    Suggest a group for an orphan tag based on simple heuristics.
    """
    tag_lower = tag.lower()

    # Simple keyword-based heuristics
    object_keywords = ["car", "person", "animal", "building", "tree", "flower", "food"]
    scene_keywords = ["indoor", "outdoor", "landscape", "city", "nature", "beach", "mountain"]
    style_keywords = ["black and white", "vintage", "modern", "blur", "sharp", "bright", "dark"]

    for keyword in object_keywords:
        if keyword in tag_lower:
            return "objects"

    for keyword in scene_keywords:
        if keyword in tag_lower:
            return "scenes"

    for keyword in style_keywords:
        if keyword in tag_lower:
            return "styles"

    # Default to the largest group
    if label_pack.groups:
        largest_group = max(
            label_pack.groups.items(),
            key=lambda x: len([l for l in label_pack.labels if label_pack.tier_for_label.get(l) == x[0]])
        )
        return largest_group[0]

    return "objects"


def get_canonical_groups(label_pack: LabelPack) -> List[Dict[str, object]]:
    """Get information about canonical groups."""
    result = []

    # Count labels per group
    group_counts = {}
    for label in label_pack.labels:
        group = label_pack.tier_for_label.get(label, "unknown")
        group_counts[group] = group_counts.get(group, 0) + 1

    for group_id, info in label_pack.groups.items():
        # Get aliases for this group
        aliases = []
        for label_id, metadata in label_pack.label_metadata.items():
            if metadata.group == group_id and metadata.aliases:
                aliases.extend(metadata.aliases)

        result.append({
            "id": group_id,
            "label": info.label,
            "size": group_counts.get(group_id, 0),
            "aliases": aliases,
        })

    # Sort by size (largest first)
    result.sort(key=lambda x: x["size"], reverse=True)
    return result


def get_alias_map(label_pack: LabelPack) -> Dict[str, str]:
    """Create a mapping of aliases to canonical labels."""
    alias_map = {}

    for label_id, metadata in label_pack.label_metadata.items():
        canonical = metadata.text_label
        for alias in metadata.aliases:
            alias_map[alias] = canonical

    return alias_map


def generate_questions(
    orphan_tags: List[Dict[str, object]],
    label_pack: LabelPack
) -> List[str]:
    """Generate questions about the label set based on analysis."""
    questions = []

    # Check if there are many orphan tags
    if len(orphan_tags) > 20:
        questions.append(f"Found {len(orphan_tags)} orphan tags - should we add more canonical labels?")

    # Check for groups that might need splitting
    for group_id, info in label_pack.groups.items():
        group_labels = [l for l in label_pack.labels if label_pack.tier_for_label.get(l) == group_id]
        if len(group_labels) > 50:
            questions.append(f"Should we split {info.label} into subgroups?")

    # Check specific patterns in orphan tags
    orphan_text = []
    for tag in orphan_tags:
        if isinstance(tag, dict) and "tag" in tag and isinstance(tag["tag"], str):
            orphan_text.append(tag["tag"].lower())

    if any("indoor" in tag or "outdoor" in tag for tag in orphan_text):
        questions.append("Should we split scenes into indoor/outdoor?")

    if any("person" in tag or "people" in tag for tag in orphan_text):
        questions.append("Should we add a dedicated people/person group?")

    if any("night" in tag or "dark" in tag for tag in orphan_text):
        questions.append("Should we add lighting conditions (day/night) as a separate dimension?")

    # Check for potential style keywords
    style_keywords = ["vintage", "modern", "blur", "sharp", "bright", "dark"]
    if any(keyword in " ".join(orphan_text) for keyword in style_keywords):
        questions.append("Should we expand the styles category with more attributes?")

    return questions


def write_brief(
    brief_data: Dict[str, object],
    output_path: str,
) -> None:
    """Write the brief to the specified output path."""
    output = Path(output_path)

    if output.suffix.lower() == ".json":
        with output.open("w", encoding="utf-8") as f:
            json.dump(brief_data, f, indent=2)
    else:
        # Write as Markdown
        with output.open("w", encoding="utf-8") as f:
            f.write("# Tag Analysis Brief\n\n")

            # Top orphan tags
            f.write("## Top Orphan Tags\n\n")
            f.write("| Tag | Occurrences | Suggested Group |\n")
            f.write("|-----|-------------|------------------|\n")
            top_orphans = brief_data.get("top_orphans", [])
            if isinstance(top_orphans, list):
                for tag in top_orphans:
                    f.write(f"| {tag['tag']} | {tag['occurrences']} | {tag['suggested_group']} |\n")
            f.write("\n")

            # All tags sorted by frequency (if available)
            all_tags = brief_data.get("all_tags_sorted", [])
            if all_tags and isinstance(all_tags, list):
                f.write("## All Tags Sorted by Frequency\n\n")
                f.write("| Tag | Occurrences | Canonical | Suggested Group |\n")
                f.write("|-----|-------------|-----------|------------------|\n")
                for tag in all_tags:
                    canonical = "✓" if tag["is_canonical"] else "✗"
                    suggested = tag["suggested_group"] or ""
                    f.write(f"| {tag['tag']} | {tag['occurrences']} | {canonical} | {suggested} |\n")
                f.write("\n")

            # Canonical groups
            f.write("## Canonical Groups\n\n")
            f.write("| ID | Label | Size | Aliases |\n")
            f.write("|----|-------|------|----------|\n")
            canonical_groups = brief_data.get("canonical_groups", [])
            if isinstance(canonical_groups, list):
                for group in canonical_groups:
                    aliases = ", ".join(group["aliases"][:3])  # Show first 3 aliases
                    if len(group["aliases"]) > 3:
                        aliases += f" (+{len(group['aliases']) - 3} more)"
                    f.write(f"| {group['id']} | {group['label']} | {group['size']} | {aliases} |\n")
            f.write("\n")

            # Alias map
            f.write("## Alias Mappings\n\n")
            f.write("| Alias | Canonical |\n")
            f.write("|-------|-----------|\n")
            alias_map = brief_data.get("alias_map", {})
            if isinstance(alias_map, dict):
                for alias, canonical in alias_map.items():
                    f.write(f"| {alias} | {canonical} |\n")
            f.write("\n")

            # Questions
            f.write("## Suggested Questions\n\n")
            questions = brief_data.get("questions", [])
            if isinstance(questions, list):
                for question in questions:
                    f.write(f"- {question}\n")
            f.write("\n")


def main() -> None:
    args = parse_args()

    # Load export data
    export_data = load_export_data(args.export)
    print(f"Loaded {len(export_data)} rows from {args.export}")

    # Load label pack
    label_pack = load_label_pack(args.manifest)
    print(f"Loaded label pack with {len(label_pack.labels)} labels from {args.manifest}")

    # Extract all tags
    all_tags = extract_all_tags(export_data)
    print(f"Extracted {len(all_tags)} total tag instances")

    # Find orphan tags and get all tags sorted
    orphan_tags, all_tags_sorted = find_orphan_tags(all_tags, label_pack, args.top_n)

    # Print informative messages
    total_orphans = len([t for t in all_tags_sorted if not t["is_canonical"]])
    if total_orphans == 0:
        print("No orphan tags found - all tags are in the canonical label set")
    elif total_orphans < args.top_n:
        print(f"Found {total_orphans} orphan tags total (fewer than requested {args.top_n})")
    else:
        print(f"Found {total_orphans} orphan tags total, showing top {len(orphan_tags)}")

    # Get canonical groups
    canonical_groups = get_canonical_groups(label_pack)

    # Get alias map
    alias_map = get_alias_map(label_pack)

    # Generate questions
    questions = generate_questions(orphan_tags, label_pack)

    # Create brief data
    brief_data = {
        "top_orphans": orphan_tags,
        "canonical_groups": canonical_groups,
        "alias_map": alias_map,
        "questions": questions,
    }

    # Include all tags sorted if requested
    if args.include_canonical:
        brief_data["all_tags_sorted"] = all_tags_sorted[:100]  # Include top 100 tags for analysis

    # Write brief
    write_brief(brief_data, args.output)
    print(f"Wrote brief to {args.output}")


if __name__ == "__main__":
    main()
