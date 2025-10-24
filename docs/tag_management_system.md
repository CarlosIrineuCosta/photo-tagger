# Tag Management System

This document describes the comprehensive tag management system for Photo Tagger, including enhanced tagging features, bulk promotion workflows, and label pack structure.

## Enhanced Tagging System

The enhanced tagging system builds upon the existing CLIP-based tagging to provide advanced features for tag review, synonym handling, and user tag management.

### Overview

The enhanced tagging system provides:

1. **Tag Review Mechanism**: Users can exclude tags with an "x" button, which automatically surfaces the next best tag from a stack
2. **Tag Stack System**: Maintains a backup pool of tags (user max * 2) that can be accessed when excluding tags
3. **Synonym Handling**: Automatically resolves synonyms to canonical forms to prevent duplicates
4. **User Tag Post-Processing**: Processes user-added tags to ensure consistency and prevent duplicates

### Architecture

#### Backend Components

##### EnhancedTagManager (`app/core/tag_enhanced_v2.py`)
The core class that manages enhanced tagging features:

- Processes tag scores into display tags and tag stack
- Handles synonym resolution
- Manages excluded tags
- Provides equivalence reduction

##### EnhancedTagConfig (`app/core/tag_enhanced_v2.py`)
Configuration class for enhanced tagging features:

- `max_display_tags`: Number of tags to initially display (default: 10)
- `tag_stack_multiplier`: Multiplier for tag stack size (default: 2)
- `enable_synonym_handling`: Enable automatic synonym resolution
- `enable_user_tag_processing`: Enable post-processing of user tags
- `synonym_map`: Dictionary mapping synonyms to canonical forms
- `excluded_tags`: Set of tags to automatically exclude

##### Enhanced Configuration Loader (`app/core/enhanced_config.py`)
Handles loading and saving of enhanced tagging configuration:

- Loads from `config/enhanced_tagging.yaml`
- Merges with label pack equivalences from `labels/equivalences.yaml`
- Provides default values if configuration is missing

##### Enhanced API Endpoints (`backend/api/enhanced_tagging.py`)
REST API endpoints for enhanced tagging:

- `POST /api/enhanced/process-tags`: Process tag scores with enhanced system
- `POST /api/enhanced/exclude-tag`: Exclude a tag and get next from stack
- `POST /api/enhanced/add-user-tag`: Add a user tag with post-processing
- `GET /api/enhanced/synonyms`: Get current synonym map
- `POST /api/enhanced/update-synonyms`: Update synonym map

### Configuration

#### Enhanced Tagging Configuration (`config/enhanced_tagging.yaml`)

The enhanced tagging configuration file controls all aspects of the enhanced system:

```yaml
# Basic settings
max_display_tags: 10          # Number of tags to initially display
tag_stack_multiplier: 2       # Multiplier for the tag stack (max_display * multiplier)

# Feature toggles
enable_synonym_handling: true     # Enable automatic synonym resolution
enable_user_tag_processing: true  # Enable post-processing of user-added tags

# Synonym handling
synonyms:
  # Photography terms
  "pic": "photo"
  "photograph": "photo"
  "picture": "photo"
  "snapshot": "photo"

  # Location terms
  "restaurant": "food"
  "cafe": "food"
  "bar": "food"
  "pub": "food"

  # Style terms
  "monochrome": "black and white"
  "grayscale": "black and white"
  "b&w": "black and white"

  # People terms
  "headshot": "portrait"
  "face": "portrait"

  # Urban terms
  "road": "street"
  "alley": "street"
  "avenue": "street"

# Excluded tags
excluded_tags:
  - "photo"
  - "image"
  - "picture"
  - "the"
  - "a"
  - "an"
  - "and"
  - "or"
  - "of"
  - "in"
  - "on"
  - "at"
  - "with"
```

## Bulk Promotion System

The bulk promotion system enables efficient management of multiple orphan tags through single-click promotion, multi-select queues, and batch operations.

### API Endpoints

#### Bulk Promotion Endpoint
```typescript
POST /api/tags/bulk-promote
```

##### Request Payload
```typescript
interface BulkPromoteRequest {
  promotions: Array<{
    tag: string                    // Orphan tag name
    suggested_group_id?: string    // Pre-selected group (from ML heuristic)
    label_hint?: string            // UI-provided hint for grouping
  }>
  default_group_id?: string        // Fallback group for unspecified targets
  create_new_groups?: boolean      // Allow auto-creation of new groups
}
```

##### Response Payload
```typescript
interface BulkPromoteResponse {
  results: Array<{
    tag: string
    status: "promoted" | "skipped" | "failed"
    group_id?: string
    group_label?: string
    created_group?: boolean
    error?: string
  }>
  summary: {
    total: number
    promoted: number
    skipped: number
    failed: number
  }
}
```

#### Group Suggestion Endpoint
```typescript
GET /api/tags/suggest-group?tag={tag}&context={context}
```

##### Response
```typescript
interface SuggestGroupResponse {
  suggested_group_id: string
  confidence: number              // 0-1 score
  reasoning?: string              // ML heuristic explanation
  alternatives: Array<{
    group_id: string
    confidence: number
  }>
}
```

### UI Flow

#### 1. Single-Click Promote
- **Trigger**: Quick-action button on each orphan tag row
- **Behavior**: Promotes immediately to a pre-selected group (ML-suggested or user's last-used group)
- **Feedback**: Toast notification with undo option (5-second window)
- **Optimistic Update**: Tag immediately removed from orphan list, added to target group

#### 2. Multi-Select Queue
- **Selection**: Checkbox column in orphan tags table with "select all" functionality
- **Queue Display**: Floating panel showing selected tags count and bulk actions
- **Batch Operations**:
  - Promote all to selected group
  - Promote to suggested groups (mixed destinations)
  - Export selected as CSV
  - Dismiss selected (mark as reviewed)

#### 3. Graduation Surface
- **Bulk Dialog**: Modal/sheet with grouped promotion preview
- **Grouping Preview**: Visual organization showing which tags will go to which groups
- **Conflict Resolution**: UI for handling tags that already exist in target groups
- **Confirmation**: Summary of changes before execution with "Apply Changes" button

## Structured Label Pack

The tagging pipeline keeps the newline-delimited tier files in `labels/*.txt` as the writable source of truth for CLIP prompts. We are adding `labels/label_pack.yaml` as a manifest that records canonical identifiers, display metadata, and migration hints for automation.

### Goals
- Provide deterministic IDs for every canonical label.
- Capture human-friendly names, descriptions, and tier ordering without hard-coding them in the frontend.
- Track aliases/synonyms used for suggestion matching and review tooling.
- Store per-label overrides (thresholds, prompts, notes) alongside the existing `thresholds.yaml` and `prompts.yaml` data to reduce fragmentation.
- Record promotion history so orphan graduations can be audited.

### File Layout

```yaml
version: 1
updated_at: 2024-04-01T12:00:00Z

groups:
  - id: objects
    label: Objects
    description: Physical items, props, and distinct subjects.
    path: objects.txt                # text file that mirrors this group
    default_threshold: 0.23
    supports_bulk: true
    allow_user_labels: true
    display_order: 10
  - id: scenes
    label: Scenes
    description: Locations or environmental context.
    path: scenes.txt
    default_threshold: 0.24
    supports_bulk: true
    allow_user_labels: false
    display_order: 20

labels:
  sunflower-field:
    name: Sunflower Field
    group: scenes
    text_label: sunflower field      # canonical string pushed into the .txt file
    prompt_templates:
      - "a photo taken in a {}"
      - "a {} scene"
    threshold: 0.26
    aliases:
      - field of sunflowers
      - sunflower meadow
    equivalence_group: flora-bold    # optional handle shared by related labels
    disambiguation:
      - "Use for wide outdoor vistas containing many sunflowers."
    notes: "Popular synonym in recent user tags."
  macro-closeup:
    name: Macro Close-up
    group: styles
    text_label: macro closeup
    threshold: 0.20
    aliases:
      - macro shot
      - macro photography

promotions:
  - tag: neon nightscape
    promoted_at: 2024-03-21T18:05:00Z
    user: jdoe
    group: scenes
    label_id: neon-nightscape
    source: orphan-review-20240321
```

### Field Notes

- `version` enables future schema migrations.
- `groups[].path` keeps the loader aligned with the legacy text file layout.
- `labels[...].text_label` is the normalized string persisted in the text file; use the canonical ID (`sunflower-field`) when cross-referencing in the API.
- `aliases` feed both equivalence reduction and orphan matching heuristics.
- `equivalence_group` is optional; the existing `equivalences.yaml` will be merged into explicit groups keyed by their canonical IDs during migration.
- `promotions` acts as a lightweight ledger until we replace it with a dedicated audit log. Entries mirror the existing `runs/tag_events.log` data and include a `status` field (default `pending`) so the UI can highlight items that still need graduation review.

### Loader Expectations

1. When `label_pack.yaml` exists the loader should:
   - build the tier → labels mapping from `groups` and `labels[*].text_label`.
   - expose canonical IDs, human labels, aliases, and thresholds on the resulting `LabelPack` object.
   - merge/override any `prompts.yaml` and `thresholds.yaml` data with the values embedded in the manifest.
2. If the manifest is absent we read the current text/yaml files exactly as we do today.
3. Any new label added through the API writes to `labels/<group>.txt` and appends a `promotions` entry so downstream tooling can reconstruct the manifest entry.

### API Contract Touchpoints

- `GET /api/tags/summary` will return:
  ```json
  {
    "groups": [
      {
        "id": "objects",
        "label": "Objects",
        "description": "...",
        "path": "labels/objects.txt",
        "canonical_count": 120,
        "supports_bulk": true,
        "tags": ["camera", "lens", "..."]
      }
    ],
    "orphan_tags": [
      {
        "name": "macro shot",
        "occurrences": 8,
        "suggested_group_id": "styles",
        "suggested_label_id": "macro-closeup",
        "confidence": 0.82
      }
    ],
    "stats": {
      "pending_graduations": 5,
      "groups": 4,
      "total_labels": 300,
      "orphan_labels": 18
    }
  }
  ```
- `POST /api/tags/promote` continues to accept the simple payload, but the response will now include `label_id` and `group_label`.
- `POST /api/tags/promote/bulk` will accept `{ "actions": [...] }` where each action contains the source tag, destination group ID, optional canonical label ID, and flags (e.g., `create_label: true`). Responses return per-action status, logging context, and any manifest updates.

## Implementation Details

### Tag Processing Flow

1. **Input**: Raw CLIP scores and optional user tags
2. **Filtering**: Remove excluded tags and apply thresholds
3. **Synonym Resolution**: Convert all tags to canonical forms
4. **Sorting**: Sort by score (highest first)
5. **Splitting**: Separate into display tags and tag stack
6. **Equivalence Reduction**: Apply label pack equivalences if available

### State Management

- Backend maintains in-memory tag stacks for each image
- Frontend manages local state for UI interactions
- API calls synchronize state between frontend and backend

### Error Handling

- Graceful fallback to standard tagging if enhanced features fail
- Comprehensive error logging and user feedback
- Type-safe interfaces prevent runtime errors

## Performance Considerations

### Compute Impact

- **Initial Processing**: Minimal overhead - just sorting and filtering existing scores
- **Tag Exclusion**: Very low - just pops from pre-computed stack
- **Synonym Resolution**: Low - simple dictionary lookups
- **User Tag Processing**: Low - string normalization and lookup

### Memory Usage

- Tag stacks store (max_display_tags * multiplier) tags per image
- Synonym maps are shared across all images
- State is maintained only for actively viewed images

## Future Enhancements

### Potential Improvements

1. **Persistent State**: Save tag stacks and excluded tags to database
2. **Learning System**: Learn from user exclusions to improve future suggestions
3. **Batch Operations**: Allow excluding/adding tags across multiple images
4. **Advanced Synonyms**: Support for context-dependent synonyms
5. **Tag Hierarchies**: Support for parent/child tag relationships

### Integration with AI Features

- The enhanced system is designed to work alongside future AI filtering
- Exclusion patterns could inform AI training data
- User tags could be used as positive examples for AI learning
