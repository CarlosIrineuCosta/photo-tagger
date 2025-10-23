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
        help="Number of frequent orphan tags to include (default: 50)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output path for the brief (JSON or Markdown)",
    )
    return parser.parse_args()


def load_export_data(csv_path: str) -> List[Dict[str, str]]:
    """Load and parse the CSV export file."""
    with open(csv_path, "r", encoding="utf-8") as f:
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
) -> List[Dict[str, object]]:
    """
    Find orphan tags (tags not in the canonical label set) and their frequencies.
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

    result = []
    for tag, count in top_orphans:
        # Try to suggest a group based on similarity to existing groups
        suggested_group = suggest_group_for_tag(tag, label_pack)

        # Calculate some simple scores
        scores = {
            "frequency": count,
            "frequency_ratio": count / len(all_tags),
        }

        result.append({
            "tag": tag,
            "occurrences": count,
            "suggested_group": suggested_group,
            "scores": scores,
        })

    return result


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
    orphan_text = [tag["tag"].lower() for tag in orphan_tags]
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
            for tag in brief_data["top_orphans"]:
                f.write(f"| {tag['tag']} | {tag['occurrences']} | {tag['suggested_group']} |\n")
            f.write("\n")

            # Canonical groups
            f.write("## Canonical Groups\n\n")
            f.write("| ID | Label | Size | Aliases |\n")
            f.write("|----|-------|------|----------|\n")
            for group in brief_data["canonical_groups"]:
                aliases = ", ".join(group["aliases"][:3])  # Show first 3 aliases
                if len(group["aliases"]) > 3:
                    aliases += f" (+{len(group['aliases']) - 3} more)"
                f.write(f"| {group['id']} | {group['label']} | {group['size']} | {aliases} |\n")
            f.write("\n")

            # Alias map
            f.write("## Alias Mappings\n\n")
            f.write("| Alias | Canonical |\n")
            f.write("|-------|-----------|\n")
            for alias, canonical in brief_data["alias_map"].items():
                f.write(f"| {alias} | {canonical} |\n")
            f.write("\n")

            # Questions
            f.write("## Suggested Questions\n\n")
            for question in brief_data["questions"]:
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

    # Find orphan tags
    orphan_tags = find_orphan_tags(all_tags, label_pack, args.top_n)
    print(f"Found {len(orphan_tags)} top orphan tags")

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

    # Write brief
    write_brief(brief_data, args.output)
    print(f"Wrote brief to {args.output}")


if __name__ == "__main__":
    main()
