# Enhanced Tagging System

This document describes the enhanced tagging system for Photo Tagger, which provides advanced features for tag review, synonym handling, and user tag management.

## Overview

The enhanced tagging system builds upon the existing CLIP-based tagging to provide:

1. **Tag Review Mechanism**: Users can exclude tags with an "x" button, which automatically surfaces the next best tag from a stack
2. **Tag Stack System**: Maintains a backup pool of tags (user max * 2) that can be accessed when excluding tags
3. **Synonym Handling**: Automatically resolves synonyms to canonical forms to prevent duplicates
4. **User Tag Post-Processing**: Processes user-added tags to ensure consistency and prevent duplicates

## Architecture

### Backend Components

#### EnhancedTagManager (`app/core/tag_enhanced_v2.py`)
The core class that manages enhanced tagging features:

- Processes tag scores into display tags and tag stack
- Handles synonym resolution
- Manages excluded tags
- Provides equivalence reduction

#### EnhancedTagConfig (`app/core/tag_enhanced_v2.py`)
Configuration class for enhanced tagging features:

- `max_display_tags`: Number of tags to initially display (default: 10)
- `tag_stack_multiplier`: Multiplier for tag stack size (default: 2)
- `enable_synonym_handling`: Enable automatic synonym resolution
- `enable_user_tag_processing`: Enable post-processing of user tags
- `synonym_map`: Dictionary mapping synonyms to canonical forms
- `excluded_tags`: Set of tags to automatically exclude

#### Enhanced Configuration Loader (`app/core/enhanced_config.py`)
Handles loading and saving of enhanced tagging configuration:

- Loads from `config/enhanced_tagging.yaml`
- Merges with label pack equivalences from `labels/equivalences.yaml`
- Provides default values if configuration is missing

#### Enhanced API Endpoints (`backend/api/enhanced_tagging.py`)
REST API endpoints for enhanced tagging:

- `POST /api/enhanced/process-tags`: Process tag scores with enhanced system
- `POST /api/enhanced/exclude-tag`: Exclude a tag and get next from stack
- `POST /api/enhanced/add-user-tag`: Add a user tag with post-processing
- `GET /api/enhanced/synonyms`: Get current synonym map
- `POST /api/enhanced/update-synonyms`: Update synonym map

### Frontend Components

#### EnhancedTagGallery (`frontend/src/components/EnhancedTagGallery.tsx`)
React component that displays the enhanced tagging interface:

- Shows display tags with exclude buttons
- Provides user tag input field
- Displays tag stack when requested
- Shows excluded tags

#### Enhanced API Client (`frontend/src/lib/enhanced_api.ts`)
TypeScript client for interacting with enhanced API endpoints:

- Provides type-safe interfaces for all API calls
- Handles error cases and response parsing
- Includes helper function to convert regular gallery items to enhanced items

#### Enhanced Gallery Page (`frontend/src/pages/EnhancedGalleryPage.tsx`)
Complete page implementation using enhanced components:

- Toggles between enhanced and standard mode
- Manages state for all enhanced features
- Provides comprehensive logging of user actions

## Configuration

### Enhanced Tagging Configuration (`config/enhanced_tagging.yaml`)

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

### Integration with Existing Labels

The enhanced system automatically integrates with your existing `/labels` directory:

1. **Label Pack Loading**: The system loads your existing `labels/objects.txt`, `labels/scenes.txt`, and `labels/styles.txt` files
2. **Equivalence Merging**: Synonyms from `labels/equivalences.yaml` are automatically merged with the enhanced config
3. **Prompt Integration**: Uses your existing `labels/prompts.yaml` templates for CLIP text encoding
4. **Threshold Application**: Applies your `labels/thresholds.yaml` settings for filtering

### How It Works with CLIP Prompting

The enhanced system doesn't change your existing CLIP prompting workflow:

1. **Original Process**: Your current system creates text prompts using templates like `"a photo of {label}"` from `prompts.yaml`
2. **Enhanced Layer**: The enhanced system works AFTER CLIP scoring, just organizing and filtering the existing results
3. **No Prompt Changes**: Your existing prompts.yaml continues to work exactly as before
4. **Same Embeddings**: The system uses the same CLIP text embeddings you're already generating

#### Example Flow:
```
1. Your existing system:
   - Loads labels from labels/objects.txt, scenes.txt, styles.txt
   - Creates prompts using prompts.yaml (e.g., "a photo of portrait")
   - Generates CLIP text embeddings
   - Scores images against these embeddings

2. Enhanced system (new layer):
   - Takes the scored results from step 1
   - Applies synonym resolution (e.g., "headshot" → "portrait")
   - Filters out excluded tags
   - Creates display tags and tag stack
   - Handles user interactions (exclude, add tags)
```

### Configuration Recommendations

#### For Your Current Setup:

1. **Add Custom Synonyms**: Add terms specific to your photo collection to the synonyms section
2. **Adjust Display Count**: If you want more/fewer initial tags, change `max_display_tags`
3. **Tune Stack Size**: Increase `tag_stack_multiplier` if users often exclude many tags
4. **Custom Exclusions**: Add tags that are never relevant to your collection

#### Example Customization:
```yaml
# If you photograph mostly food:
synonyms:
  "meal": "food"
  "dish": "food"
  "cuisine": "food"
  "edible": "food"

# If you don't want certain terms:
excluded_tags:
  - "the"
  - "a"
  - "an"
  - "and"
  - "or"
  - "unknown"
  - "untitled"
```

## Usage

### Basic Workflow

1. **Initial Tag Display**: The system shows the top N tags (default: 10) based on CLIP scores
2. **Tag Review**: Users can click the "x" button to exclude a tag
3. **Tag Stack Access**: When a tag is excluded, the next best tag from the stack automatically appears
4. **User Tags**: Users can add custom tags through the input field
5. **Synonym Resolution**: Both system and user tags are processed through the synonym map

### Advanced Features

#### Tag Stack
- Maintains a pool of backup tags (max_display_tags * multiplier)
- Automatically surfaces the next best tag when excluding
- Provides visual indication of remaining stack size

#### Synonym Handling
- Resolves both system and user tags to canonical forms
- Prevents duplicate tags with different spellings
- Can be configured through the config file or equivalences.yaml

#### User Tag Post-Processing
- Normalizes user tags (lowercase, trim whitespace)
- Resolves synonyms to canonical forms
- Prevents duplicate user tags

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

## Troubleshooting

### Common Issues

1. **Tags not appearing**: Check that `max_display_tags` is set appropriately
2. **Synonyms not working**: Verify synonym map is loaded correctly
3. **Tag stack empty**: Increase `tag_stack_multiplier` or check score thresholds
4. **User tags being ignored**: Ensure `enable_user_tag_processing` is enabled

### Debug Information

- Enhanced API provides detailed error messages
- Frontend logs all user actions to status log
- Configuration loading reports warnings for missing files

## Migration

### From Standard Tagging

1. Install enhanced configuration file
2. Update API to include enhanced endpoints
3. Update frontend to use enhanced components
4. Gradually enable features through configuration

### Backward Compatibility

- Standard tagging continues to work without changes
- Enhanced features can be toggled on/off
- Existing data formats remain compatible
