"""
Configuration loader for the enhanced tagging system.
"""
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Dict, Set

from app.core.tag_enhanced_v2 import EnhancedTagConfig


def load_enhanced_config(config_path: str | Path = "config/enhanced_tagging.yaml") -> EnhancedTagConfig:
    """
    Load enhanced tagging configuration from a YAML file.

    Args:
        config_path: Path to the configuration file

    Returns:
        EnhancedTagConfig instance
    """
    config_path = Path(config_path).expanduser()

    # Default values
    max_display_tags = 10
    tag_stack_multiplier = 2
    enable_synonym_handling = True
    enable_user_tag_processing = True
    synonym_map: Dict[str, str] = {}
    excluded_tags: Set[str] = set()

    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}

            # Load basic settings
            max_display_tags = int(data.get("max_display_tags", 10))
            tag_stack_multiplier = int(data.get("tag_stack_multiplier", 2))
            enable_synonym_handling = bool(data.get("enable_synonym_handling", True))
            enable_user_tag_processing = bool(data.get("enable_user_tag_processing", True))

            # Load synonyms
            synonyms_data = data.get("synonyms", {})
            if isinstance(synonyms_data, dict):
                synonym_map = {
                    str(key).lower().strip(): str(value).lower().strip()
                    for key, value in synonyms_data.items()
                }

            # Load excluded tags
            excluded_data = data.get("excluded_tags", [])
            if isinstance(excluded_data, list):
                excluded_tags = {
                    str(tag).lower().strip()
                    for tag in excluded_data
                }

        except Exception as e:
            print(f"Warning: Failed to load enhanced config from {config_path}: {e}")
            print("Using default configuration values.")

    return EnhancedTagConfig(
        max_display_tags=max_display_tags,
        tag_stack_multiplier=tag_stack_multiplier,
        enable_synonym_handling=enable_synonym_handling,
        enable_user_tag_processing=enable_user_tag_processing,
        synonym_map=synonym_map,
        excluded_tags=excluded_tags
    )


def save_enhanced_config(config: EnhancedTagConfig, config_path: str | Path = "config/enhanced_tagging.yaml") -> None:
    """
    Save enhanced tagging configuration to a YAML file.

    Args:
        config: EnhancedTagConfig instance to save
        config_path: Path to save the configuration file
    """
    config_path = Path(config_path).expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "max_display_tags": config.max_display_tags,
        "tag_stack_multiplier": config.tag_stack_multiplier,
        "enable_synonym_handling": config.enable_synonym_handling,
        "enable_user_tag_processing": config.enable_user_tag_processing,
        "synonyms": config.synonym_map,
        "excluded_tags": sorted(list(config.excluded_tags))
    }

    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=True, indent=2)


def merge_with_label_pack_equivalences(
    config: EnhancedTagConfig,
    equivalences_file: str | Path = "labels/equivalences.yaml"
) -> EnhancedTagConfig:
    """
    Merge the enhanced config with equivalence groups from a label pack.

    Args:
        config: Base EnhancedTagConfig
        equivalences_file: Path to the equivalences.yaml file

    Returns:
        Enhanced configuration with merged equivalences
    """
    equivalences_path = Path(equivalences_file).expanduser()

    if not equivalences_path.exists():
        return config

    try:
        with equivalences_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        equivalence_groups = data.get("equivalences", [])

        # Create a new synonym map with the equivalences
        new_synonym_map = config.synonym_map.copy()

        for group in equivalence_groups:
            if not isinstance(group, list) or len(group) < 2:
                continue

            # Use the first item as the canonical form
            canonical = str(group[0]).lower().strip()

            # Add the rest as synonyms
            for synonym in group[1:]:
                synonym_str = str(synonym).lower().strip()
                if synonym_str != canonical:
                    new_synonym_map[synonym_str] = canonical

        # Create new config with merged synonyms
        return EnhancedTagConfig(
            max_display_tags=config.max_display_tags,
            tag_stack_multiplier=config.tag_stack_multiplier,
            enable_synonym_handling=config.enable_synonym_handling,
            enable_user_tag_processing=config.enable_user_tag_processing,
            synonym_map=new_synonym_map,
            excluded_tags=config.excluded_tags.copy()
        )

    except Exception as e:
        print(f"Warning: Failed to merge equivalences from {equivalences_path}: {e}")
        return config


__all__ = [
    "load_enhanced_config",
    "save_enhanced_config",
    "merge_with_label_pack_equivalences"
]
