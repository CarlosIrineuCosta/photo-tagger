"""
Enhanced tagging system with review mechanism, synonym handling, and tag stack management.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from app.core import label_pack


@dataclass
class EnhancedTagConfig:
    """Configuration for enhanced tagging features."""
    max_display_tags: int = 10  # Number of tags to initially display
    tag_stack_multiplier: int = 2  # Multiplier for the tag stack (max_display * multiplier)
    enable_synonym_handling: bool = True
    enable_user_tag_processing: bool = True
    excluded_tags: Set[str] = field(default_factory=set)
    synonym_map: Dict[str, str] = field(default_factory=dict)


@dataclass
class TagCandidate:
    """Represents a tag candidate with score and metadata."""
    name: str
    score: float
    is_excluded: bool = False
    is_user_added: bool = False
    original_synonym: Optional[str] = None  # If this tag is a synonym of another


class EnhancedTagManager:
    """Manages enhanced tagging features including review, synonyms, and tag stacking."""

    def __init__(self, config: EnhancedTagConfig, label_pack: Optional[label_pack.LabelPack] = None):
        self.config = config
        self.label_pack = label_pack
        self.excluded_tags: Set[str] = set(config.excluded_tags)
        self.synonym_map: Dict[str, str] = config.synonym_map.copy()
        self.reverse_synonym_map: Dict[str, Set[str]] = {}

        # Build reverse synonym map for faster lookups
        for synonym, canonical in self.synonym_map.items():
            if canonical not in self.reverse_synonym_map:
                self.reverse_synonym_map[canonical] = set()
            self.reverse_synonym_map[canonical].add(synonym)

    def process_tag_scores(
        self,
        tag_scores: List[Tuple[str, float]],
        user_tags: Optional[List[str]] = None
    ) -> Tuple[List[TagCandidate], List[TagCandidate]]:
        """
        Process tag scores to create display tags and a tag stack.

        Returns:
            Tuple of (display_tags, tag_stack)
        """
        # Process initial tag scores
        candidates = []
        for name, score in tag_scores:
            # Skip if tag is in excluded list
            if name.lower() in self.excluded_tags:
                continue

            # Handle synonyms
            canonical_name = self._resolve_synonym(name)
            if canonical_name != name:
                # This is a synonym of a canonical tag
                candidates.append(TagCandidate(
                    name=canonical_name,
                    score=score,
                    original_synonym=name
                ))
            else:
                candidates.append(TagCandidate(name=name, score=score))

        # Add user tags if provided
        if user_tags:
            for tag in user_tags:
                canonical_name = self._resolve_synonym(tag)
                # Check if already in candidates
                existing = next((c for c in candidates if c.name == canonical_name), None)
                if existing:
                    existing.is_user_added = True
                else:
                    candidates.append(TagCandidate(
                        name=canonical_name,
                        score=1.0,  # User tags get highest score
                        is_user_added=True
                    ))

        # Sort by score (highest first)
        candidates.sort(key=lambda t: t.score, reverse=True)

        # Split into display tags and tag stack
        max_display = self.config.max_display_tags
        max_stack_size = max_display * self.config.tag_stack_multiplier

        display_tags = candidates[:max_display]
        tag_stack = candidates[max_display:max_stack_size]

        return display_tags, tag_stack

    def exclude_tag(self, tag_name: str) -> Optional[TagCandidate]:
        """
        Exclude a tag and return the next best candidate from the stack if available.

        Returns:
            The next tag candidate from the stack if available, None otherwise.
        """
        tag_name = tag_name.lower()
        self.excluded_tags.add(tag_name)

        # This would be called from the API layer with access to the current stack
        # The actual implementation would need access to the current tag stack
        return None

    def include_user_tag(self, tag_name: str) -> TagCandidate:
        """
        Process a user-added tag through the post-processor.
        """
        canonical_name = self._resolve_synonym(tag_name)
        return TagCandidate(
            name=canonical_name,
            score=1.0,
            is_user_added=True,
            original_synonym=tag_name if canonical_name != tag_name else None
        )

    def _resolve_synonym(self, tag_name: str) -> str:
        """
        Resolve a tag name to its canonical form using the synonym map.
        """
        tag_name = tag_name.lower().strip()

        # Direct synonym lookup
        if tag_name in self.synonym_map:
            return self.synonym_map[tag_name]

        # Reverse lookup - check if this is a canonical form with known synonyms
        # This ensures consistency in the canonical form
        for canonical, synonyms in self.reverse_synonym_map.items():
            if tag_name in synonyms:
                return canonical

        return tag_name

    def update_synonym_map(self, new_synonyms: Dict[str, str]) -> None:
        """
        Update the synonym map with new entries.
        """
        self.synonym_map.update(new_synonyms)

        # Rebuild reverse map
        self.reverse_synonym_map = {}
        for synonym, canonical in self.synonym_map.items():
            if canonical not in self.reverse_synonym_map:
                self.reverse_synonym_map[canonical] = set()
            self.reverse_synonym_map[canonical].add(synonym)

    def get_equivalence_reduced_tags(
        self,
        tag_candidates: List[TagCandidate]
    ) -> List[TagCandidate]:
        """
        Apply equivalence reduction from the label pack if available.
        """
        if not self.label_pack or not self.label_pack.equivalence_groups:
            return tag_candidates

        # Convert to format expected by reduce_equivalences
        score_map = {tag.name: tag.score for tag in tag_candidates}

        # Apply equivalence reduction
        reduced_scores = label_pack.reduce_equivalences(
            [{"label": str(name), "score": float(score)} for name, score in score_map.items()],
            self.label_pack.equivalence_groups
        )

        # Convert back to TagCandidate objects, preserving metadata
        reduced_tags = []
        reduced_names = {entry["label"] for entry in reduced_scores}

        for entry in reduced_scores:
            name = entry["label"]
            score = entry["score"]

            # Find original candidate to preserve metadata
            original = next((t for t in tag_candidates if t.name == name), None)
            if original:
                original.score = score
                reduced_tags.append(original)
            else:
                reduced_tags.append(TagCandidate(name=name, score=score))

        return reduced_tags


def create_enhanced_config_from_label_pack(
    label_pack: label_pack.LabelPack,
    max_display_tags: int = 10,
    tag_stack_multiplier: int = 2
) -> EnhancedTagConfig:
    """
    Create an EnhancedTagConfig from a LabelPack, extracting synonym information.
    """
    synonym_map = {}

    # Build synonym map from equivalence groups
    for group in label_pack.equivalence_groups:
        if len(group) < 2:
            continue

        # Use the first item as the canonical form
        canonical = group[0]
        for synonym in group[1:]:
            synonym_map[synonym.lower()] = canonical.lower()

    return EnhancedTagConfig(
        max_display_tags=max_display_tags,
        tag_stack_multiplier=tag_stack_multiplier,
        synonym_map=synonym_map
    )


__all__ = [
    "EnhancedTagConfig",
    "TagCandidate",
    "EnhancedTagManager",
    "create_enhanced_config_from_label_pack"
]
