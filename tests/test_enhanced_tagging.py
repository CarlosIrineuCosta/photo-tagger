"""
Tests for the enhanced tagging system.
"""
from __future__ import annotations

import pytest
from app.core.enhanced_config import load_enhanced_config, merge_with_label_pack_equivalences
from app.core.tag_enhanced_v2 import EnhancedTagConfig, EnhancedTagManager, TagCandidate


class TestEnhancedTagConfig:
    """Test the EnhancedTagConfig class."""

    def test_default_config(self):
        """Test creating a default configuration."""
        config = EnhancedTagConfig()
        assert config.max_display_tags == 10
        assert config.tag_stack_multiplier == 2
        assert config.enable_synonym_handling is True
        assert config.enable_user_tag_processing is True
        assert config.synonym_map == {}
        assert config.excluded_tags == set()

    def test_custom_config(self):
        """Test creating a custom configuration."""
        config = EnhancedTagConfig(
            max_display_tags=5,
            tag_stack_multiplier=3,
            synonym_map={"pic": "photo"},
            excluded_tags={"test"}
        )
        assert config.max_display_tags == 5
        assert config.tag_stack_multiplier == 3
        assert config.synonym_map == {"pic": "photo"}
        assert config.excluded_tags == {"test"}


class TestEnhancedTagManager:
    """Test the EnhancedTagManager class."""

    def test_process_tag_scores(self):
        """Test basic tag score processing."""
        config = EnhancedTagConfig(max_display_tags=3, tag_stack_multiplier=2)
        manager = EnhancedTagManager(config)

        tag_scores = [
            ("photo", 0.9),
            ("portrait", 0.8),
            ("street", 0.7),
            ("night", 0.6),
            ("urban", 0.5),
            ("landscape", 0.4)
        ]

        display_tags, tag_stack = manager.process_tag_scores(tag_scores)

        # Should have 3 display tags
        assert len(display_tags) == 3
        assert display_tags[0].name == "photo"
        assert display_tags[0].score == 0.9

        # Should have 3 tags in stack (3 * 2 - 3 already displayed)
        assert len(tag_stack) == 3
        assert tag_stack[0].name == "night"

    def test_synonym_resolution(self):
        """Test synonym resolution."""
        config = EnhancedTagConfig(
            synonym_map={"pic": "photo", "portrait": "headshot"}
        )
        manager = EnhancedTagManager(config)

        tag_scores = [
            ("pic", 0.9),
            ("portrait", 0.8),
            ("photo", 0.7)
        ]

        display_tags, tag_stack = manager.process_tag_scores(tag_scores)

        # "pic" should be resolved to "photo"
        assert display_tags[0].name == "photo"
        assert display_tags[0].original_synonym == "pic"

        # "portrait" should be resolved to "headshot"
        assert display_tags[1].name == "headshot"
        assert display_tags[1].original_synonym == "portrait"

        # Original "photo" should remain unchanged
        assert display_tags[2].name == "photo"
        assert display_tags[2].original_synonym is None

    def test_excluded_tags(self):
        """Test tag exclusion."""
        config = EnhancedTagConfig(excluded_tags={"photo", "portrait"})
        manager = EnhancedTagManager(config)

        tag_scores = [
            ("photo", 0.9),
            ("portrait", 0.8),
            ("street", 0.7)
        ]

        display_tags, tag_stack = manager.process_tag_scores(tag_scores)

        # Excluded tags should not appear
        assert len(display_tags) == 1
        assert display_tags[0].name == "street"

    def test_user_tags(self):
        """Test user tag processing."""
        config = EnhancedTagConfig(synonym_map={"pic": "photo"})
        manager = EnhancedTagManager(config)

        tag_scores = [
            ("street", 0.7),
            ("night", 0.6)
        ]

        user_tags = ["pic", "custom"]

        display_tags, tag_stack = manager.process_tag_scores(tag_scores, user_tags)

        # User tags should be included and processed
        user_tag_names = [tag.name for tag in display_tags if tag.is_user_added]
        assert "photo" in user_tag_names  # "pic" resolved to "photo"
        assert "custom" in user_tag_names

    def test_include_user_tag(self):
        """Test adding a user tag."""
        config = EnhancedTagConfig(synonym_map={"pic": "photo"})
        manager = EnhancedTagManager(config)

        processed_tag = manager.include_user_tag("pic")

        assert processed_tag.name == "photo"
        assert processed_tag.original_synonym == "pic"
        assert processed_tag.is_user_added is True
        assert processed_tag.score == 1.0


class TestEnhancedConfigLoader:
    """Test the enhanced configuration loader."""

    def test_load_default_config(self, tmp_path):
        """Test loading default config when file doesn't exist."""
        config_path = tmp_path / "nonexistent.yaml"
        config = load_enhanced_config(config_path)

        assert config.max_display_tags == 10
        assert config.tag_stack_multiplier == 2
        assert config.enable_synonym_handling is True

    def test_load_custom_config(self, tmp_path):
        """Test loading custom config from file."""
        config_path = tmp_path / "test_config.yaml"
        config_content = """
max_display_tags: 5
tag_stack_multiplier: 3
enable_synonym_handling: false
synonyms:
  pic: photo
  portrait: headshot
excluded_tags:
  - test
  - example
"""
        config_path.write_text(config_content)

        config = load_enhanced_config(config_path)

        assert config.max_display_tags == 5
        assert config.tag_stack_multiplier == 3
        assert config.enable_synonym_handling is False
        assert config.synonym_map == {"pic": "photo", "portrait": "headshot"}
        assert config.excluded_tags == {"test", "example"}

    def test_merge_with_equivalences(self, tmp_path):
        """Test merging with label pack equivalences."""
        equivalences_path = tmp_path / "equivalences.yaml"
        equivalences_content = """
equivalences:
  - [photo, pic, picture]
  - [portrait, headshot, face]
"""
        equivalences_path.write_text(equivalences_content)

        config = EnhancedTagConfig(synonym_map={"custom": "value"})
        merged_config = merge_with_label_pack_equivalences(config, equivalences_path)

        # Should include original synonyms
        assert "custom" in merged_config.synonym_map

        # Should include equivalences
        assert "pic" in merged_config.synonym_map
        assert merged_config.synonym_map["pic"] == "photo"
        assert "picture" in merged_config.synonym_map
        assert merged_config.synonym_map["picture"] == "photo"
        assert "headshot" in merged_config.synonym_map
        assert merged_config.synonym_map["headshot"] == "portrait"


if __name__ == "__main__":
    pytest.main([__file__])
