# Gallery Status Features Documentation

## Overview
The Gallery Status features provide comprehensive filtering and inventory management capabilities for the Photo Tagger application.

## Features Tested

### 1. Stage Filtering
- **All**: Shows all images regardless of stage
- **New**: Shows only newly added images
- **Needs tags**: Shows images that require tagging
- **Draft**: Shows images with draft tags
- **Saved**: Shows images with saved tags
- **Blocked**: Shows images that are blocked from processing

### 2. Summary Chips
When "All" stage is selected, summary chips display:
- **New**: Count of new images (blue chip)
- **Needs Tags**: Count of images needing tags (yellow chip)
- **Draft**: Count of images with draft tags (orange chip)
- **Saved**: Count of saved images (green chip)
- **Blocked**: Count of blocked images (red chip)

### 3. Filter Toggles
- **Medoids only**: Shows only representative images from clusters
- **Only unapproved**: Shows only images that haven't been approved
- **Hide saved**: Hides images that have been saved
- **Center-crop**: Applies center cropping to thumbnail display

## Test Coverage
Automated tests verify:
- All stage filter options render correctly
- Summary chips display correct counts
- Stage filter changes trigger appropriate callbacks
- Filter toggles work as expected
- Controls are properly disabled during processing
- Zero counts display correctly

## Notes
- Screenshots would be captured using: `python scripts/capture_screenshots.py --feature gallery_status --auto`
- Interactive screenshot capture requires manual setup of each UI state
- All UI components are tested with React Testing Library
