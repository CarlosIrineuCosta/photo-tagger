"""
Enhanced API endpoints for the improved tagging system.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import label_pack as label_pack_core
from app.core.tag_enhanced_v2 import EnhancedTagConfig, EnhancedTagManager, TagCandidate

router = APIRouter(prefix="/api/enhanced", tags=["enhanced-tagging"])


class TagScore(BaseModel):
    """Single tag score coming from the frontend."""
    tag: str = Field(..., description="Tag name")
    score: float = Field(..., description="Confidence score")


class TagPayload(BaseModel):
    """Serialized TagCandidate for responses."""
    name: str
    score: float
    is_excluded: bool = False
    is_user_added: bool = False
    original_synonym: Optional[str] = None


class EnhancedTagRequest(BaseModel):
    """Request for enhanced tag processing."""
    image_path: str
    tag_scores: List[TagScore] = Field(..., description="List of tag scores from CLIP")
    user_tags: List[str] = Field(default_factory=list, description="User-added tags")
    max_display_tags: int = Field(default=10, description="Number of tags to display")
    tag_stack_multiplier: int = Field(default=2, description="Multiplier for tag stack size")


class EnhancedTagResponse(BaseModel):
    """Response from enhanced tag processing."""
    display_tags: List[TagPayload] = Field(..., description="Tags to display to the user")
    tag_stack: List[TagPayload] = Field(..., description="Backup tags in the stack")
    excluded_tags: List[str] = Field(..., description="Currently excluded tags")


class ExcludeTagRequest(BaseModel):
    """Request to exclude a tag."""
    image_path: str
    tag_name: str


class ExcludeTagResponse(BaseModel):
    """Response after excluding a tag."""
    status: str
    next_tag: Optional[TagPayload] = Field(None, description="Next tag from the stack if available")


class AddUserTagRequest(BaseModel):
    """Request to add a user tag."""
    image_path: str
    tag_name: str


class AddUserTagResponse(BaseModel):
    """Response after adding a user tag."""
    status: str
    processed_tag: TagPayload = Field(..., description="The processed tag after synonym resolution")


# In-memory storage for tag stacks (in production, this would be persisted)
_tag_stacks: Dict[str, List[TagCandidate]] = {}
_tag_managers: Dict[str, EnhancedTagManager] = {}


def _get_image_key(image_path: str) -> str:
    """Generate a unique key for an image path."""
    return str(Path(image_path).resolve())


def _get_or_create_tag_manager(config: EnhancedTagConfig) -> EnhancedTagManager:
    """Get or create a tag manager for the given configuration."""
    config_key = str(hash(str(config)))
    if config_key not in _tag_managers:
        # Try to load the label pack if available
        label_pack = None
        try:
            label_pack = label_pack_core.load_label_pack("labels")
        except Exception:
            pass

        _tag_managers[config_key] = EnhancedTagManager(config, label_pack)

    return _tag_managers[config_key]


@router.post("/process-tags", response_model=EnhancedTagResponse)
def process_tags(request: EnhancedTagRequest):
    """
    Process tag scores using the enhanced tagging system.
    """
    # Create configuration
    config = EnhancedTagConfig(
        max_display_tags=request.max_display_tags,
        tag_stack_multiplier=request.tag_stack_multiplier
    )

    # Get or create tag manager
    manager = _get_or_create_tag_manager(config)

    # Convert tag scores to tuple format
    tag_scores: List[Tuple[str, float]] = [
        (item.tag, item.score)
        for item in request.tag_scores
    ]

    # Process tags
    display_tags, tag_stack = manager.process_tag_scores(
        tag_scores=tag_scores,
        user_tags=request.user_tags
    )

    # Store tag stack for later use
    image_key = _get_image_key(request.image_path)
    _tag_stacks[image_key] = tag_stack

    # Convert to response format
    def _serialize(candidate: TagCandidate) -> TagPayload:
        return TagPayload(
            name=candidate.name,
            score=candidate.score,
            is_excluded=candidate.is_excluded,
            is_user_added=candidate.is_user_added,
            original_synonym=candidate.original_synonym,
        )

    return EnhancedTagResponse(
        display_tags=[_serialize(tag) for tag in display_tags],
        tag_stack=[_serialize(tag) for tag in tag_stack],
        excluded_tags=list(manager.excluded_tags),
    )


@router.post("/exclude-tag", response_model=ExcludeTagResponse)
def exclude_tag(request: ExcludeTagRequest):
    """
    Exclude a tag and return the next best candidate from the stack.
    """
    image_key = _get_image_key(request.image_path)

    if image_key not in _tag_stacks:
        raise HTTPException(status_code=404, detail="No tag stack found for this image")

    # Get the tag stack
    tag_stack = _tag_stacks[image_key]

    if not tag_stack:
        return ExcludeTagResponse(status="no_more_tags", next_tag=None)

    # Get the next tag from the stack
    next_tag = tag_stack.pop(0)

    # Update the stack
    _tag_stacks[image_key] = tag_stack

    # Convert to response format
    return ExcludeTagResponse(
        status="success",
        next_tag=TagPayload(
            name=next_tag.name,
            score=next_tag.score,
            is_excluded=next_tag.is_excluded,
            is_user_added=next_tag.is_user_added,
            original_synonym=next_tag.original_synonym,
        )
    )


@router.post("/add-user-tag", response_model=AddUserTagResponse)
def add_user_tag(request: AddUserTagRequest):
    """
    Add a user tag and process it through the post-processor.
    """
    # Create configuration
    config = EnhancedTagConfig()
    manager = _get_or_create_tag_manager(config)

    # Process the user tag
    processed_tag = manager.include_user_tag(request.tag_name)

    # Convert to response format
    return AddUserTagResponse(
        status="success",
        processed_tag=TagPayload(
            name=processed_tag.name,
            score=processed_tag.score,
            is_excluded=processed_tag.is_excluded,
            is_user_added=processed_tag.is_user_added,
            original_synonym=processed_tag.original_synonym,
        )
    )


@router.get("/synonyms")
def get_synonyms():
    """
    Get the current synonym map.
    """
    # Get a default manager to access the synonym map
    config = EnhancedTagConfig()
    manager = _get_or_create_tag_manager(config)

    return {
        "synonym_map": manager.synonym_map,
        "reverse_synonym_map": {
            canonical: list(synonyms)
            for canonical, synonyms in manager.reverse_synonym_map.items()
        }
    }


@router.post("/update-synonyms")
def update_synonyms(synonym_map: Dict[str, str]):
    """
    Update the synonym map.
    """
    # Get a default manager to update the synonym map
    config = EnhancedTagConfig()
    manager = _get_or_create_tag_manager(config)

    # Update the synonym map
    manager.update_synonym_map(synonym_map)

    return {"status": "success", "updated_count": len(synonym_map)}


__all__ = ["router"]
