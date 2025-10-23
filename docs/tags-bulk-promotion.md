# Tags Page Bulk Promotion Implementation Brief

## Overview
This brief outlines the implementation of bulk promotion functionality for orphan tags on the Tags page, enabling users to efficiently manage multiple orphan tags through single-click promotion, multi-select queues, and batch operations.

## Wire-Level API Assumptions

### Bulk Promotion Endpoint
```typescript
POST /api/tags/bulk-promote
```

#### Request Payload
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

#### Response Payload
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

### Group Suggestion Endpoint
```typescript
GET /api/tags/suggest-group?tag={tag}&context={context}
```

#### Response
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

## UI Flow Notes

### 1. Single-Click Promote
- **Trigger**: Quick-action button on each orphan tag row
- **Behavior**: Promotes immediately to a pre-selected group (ML-suggested or user's last-used group)
- **Feedback**: Toast notification with undo option (5-second window)
- **Optimistic Update**: Tag immediately removed from orphan list, added to target group

### 2. Multi-Select Queue
- **Selection**: Checkbox column in orphan tags table with "select all" functionality
- **Queue Display**: Floating panel showing selected tags count and bulk actions
- **Batch Operations**:
  - Promote all to selected group
  - Promote to suggested groups (mixed destinations)
  - Export selected as CSV
  - Dismiss selected (mark as reviewed)

### 3. Graduation Surface
- **Bulk Dialog**: Modal/sheet with grouped promotion preview
- **Grouping Preview**: Visual organization showing which tags will go to which groups
- **Conflict Resolution**: UI for handling tags that already exist in target groups
- **Confirmation**: Summary of changes before execution with "Apply Changes" button

## Component Reuse

### Existing Components
- `Sheet` component for promotion dialogs
- `Button` variants for different action states
- `ScrollArea` for large tag lists
- `BlockingOverlay` during bulk operations
- Status toast system for feedback

### New Components
- `BulkPromoteSheet` - Main bulk promotion interface
- `TagSelectionTable` - Enhanced orphan tags table with selection
- `GroupPreview` - Visual preview of tag-to-group assignments
- `BulkOperationProgress` - Progress indicator for long-running operations

## Validation & Optimistic Updates

### Client-Side Validation
- Verify selected tags exist in current orphan list
- Validate group IDs against available groups
- Check for duplicate promotions
- Validate new group names if creation enabled

### Optimistic Update Strategy
1. **Immediate UI Updates**: Remove promoted tags from orphan list, add to target groups
2. **Rollback Mechanism**: Store previous state for undo operations
3. **Conflict Detection**: Highlight tags that already exist in target groups
4. **Progressive Updates**: Show real-time progress during bulk operations

### Error Handling
- Partial failures with detailed error reporting
- Automatic retry for network-related failures
- Manual retry options for validation failures
- Graceful degradation for ML suggestion failures

## Open Questions & Data Dependencies

### Data Dependencies
- **ML Heuristics**: Need clarification on tag-to-group suggestion algorithm
- **Tag Context**: Determine what context data is available for suggestions (frequency, co-occurrence, image context)
- **User Preferences**: Should we remember user's promotion patterns for better suggestions?

### UX Questions
- **Batch Size Limits**: What's the maximum number of tags for bulk operations?
- **Group Creation Limits**: Should users be able to create multiple new groups in one batch?
- **Undo Window**: How long should the undo option be available (currently 5 seconds)?
- **Permission Model**: Are there any restrictions on which groups users can modify?

### Technical Questions
- **Performance**: How should we handle large orphan tag sets (1000+ items)?
- **Concurrency**: How to handle multiple users promoting tags simultaneously?
- **Audit Trail**: Should bulk promotions be logged as individual events or batch events?
- **API Rate Limiting**: Are there any rate limits for bulk operations?

### Implementation Dependencies
- **Backend Changes**: New bulk promotion endpoint and group suggestion API
- **Database Schema**: May need to store user promotion preferences/patterns
- **ML Integration**: Integration point for tag-to-group suggestion system
- **File System**: Ensure atomic updates to label pack files during bulk operations

## Implementation Priority
1. **Phase 1**: Single-click promote with basic bulk selection
2. **Phase 2**: Group suggestion integration and preview interface
3. **Phase 3**: Advanced features (undo, conflict resolution, user preferences)
