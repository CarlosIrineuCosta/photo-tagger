# Enhanced Frontend Implementation

This document explains the enhanced frontend files for the Photo Tagger app.

## Files Created

### Enhanced App Component
- **File**: `frontend/src/App.tsx` (enhanced default)
- **Changes**: Router now uses `GalleryPage_enhanced` as the landing page
- **Purpose**: Entry point for the enhanced version of the app

### Standard App Reference
- **File**: `frontend/src/App_standard.tsx`
- **Purpose**: Snapshot of the pre-enhanced router for easy rollback

### Enhanced Gallery Page
- **File**: `frontend/src/pages/GalleryPage_enhanced.tsx`
- **Changes**:
  - Added enhanced mode toggle
  - Integrated with EnhancedTaggingAPI
  - Added handlers for tag exclusion and user tag addition
  - Added enhanced workflow step
- **Purpose**: Main page component with enhanced tagging features

### Enhanced Gallery Grid
- **File**: `frontend/src/components/GalleryGrid_enhanced.tsx`
- **Changes**:
  - Added "x" buttons for tag exclusion
  - Added user tag input field
  - Added tag stack visualization
  - Added excluded tags display
- **Purpose**: Grid component with enhanced tagging UI

## How to Use

### Current Layout (default enhanced)
- `frontend/src/App.tsx` → Enhanced router
- `frontend/src/App_standard.tsx` → Original router snapshot (unused)
- `frontend/src/pages/GalleryPage_enhanced.tsx` / `frontend/src/components/GalleryGrid_enhanced.tsx` → Enhanced view + grid

The standard gallery (`GalleryPage.tsx` + `GalleryGrid.tsx`) remains untouched and can be referenced or reused as needed.

### Switching Between Enhanced and Standard Modes
To revert to the original router:
1. Replace the enhanced entry point with the standard snapshot:
   ```bash
   cp frontend/src/App_standard.tsx frontend/src/App.tsx
   ```
2. Restart Vite / the tagger frontend.

To restore the enhanced router after reverting:
   ```bash
   git checkout -- frontend/src/App.tsx
   ```

### Option 2: Use as Separate Components
1. Import the enhanced components directly in your app
2. Add a route or toggle to switch between standard and enhanced views

## Features

### Tag Exclusion
- Click the "x" button next to any tag to exclude it
- The next best tag from the stack automatically appears
- Excluded tags are tracked and displayed

### User Tag Addition
- Use the input field to add custom tags
- Tags are processed through the synonym resolution system
- User tags get highest priority in the display

### Tag Stack Visualization
- Click "Show backup tags" to see the tag stack
- Shows how many tags are available as replacements
- Displays scores for stack items

### Mode Toggle
- Switch between "Enhanced Mode" and "Standard Mode"
- Enhanced mode uses the new API endpoints
- Standard mode uses the original behavior

## API Integration

The enhanced frontend integrates with these new API endpoints:
- `POST /api/enhanced/process-tags` - Process tags with enhanced system
- `POST /api/enhanced/exclude-tag` - Exclude a tag and get replacement
- `POST /api/enhanced/add-user-tag` - Add a user tag with processing

## Dependencies

The enhanced frontend requires:
- The enhanced API endpoints to be registered
- The enhanced configuration file (`config/enhanced_tagging.yaml`)
- The enhanced backend modules

## Backward Compatibility

The enhanced frontend is designed to be backward compatible:
- Falls back to standard mode if enhanced features fail
- Works with existing data formats
- Can be toggled on/off through configuration

## Testing

To test the enhanced frontend:
1. Ensure the backend enhanced endpoints are running
2. Use the enhanced App component or add routes to enhanced pages
3. Test tag exclusion, user tag addition, and mode toggling
4. Verify fallback behavior when enhanced features are unavailable
