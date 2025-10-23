# Tags Page QA Process

This document explains the QA process for the new Tags page features: hybrid promotion UI, bulk promotion drawer, and graduation review panel.

## Overview

The QA process consists of three main parts:

1. **QA Checklist** (`docs/tags_page_qa_checklist.md`): A comprehensive checklist of all tests to perform
2. **Screenshot Capture** (`scripts/capture_screenshots.py`): A script to capture screenshots and logs
3. **QA Findings** (`docs/tags_page_qa_findings.md`): A template to document test results and issues

## Before You Begin

1. Ensure the latest version of the application is running
2. Have test data ready (images with various tags)
3. Make sure you have the necessary permissions to test all features
4. Prepare your testing environment (browser, screen capture tools, etc.)

## Step 1: Run the QA Checklist

Follow the comprehensive checklist in `docs/tags_page_qa_checklist.md`:

1. Open the checklist file
2. Go through each section systematically
3. Check off items as you complete them
4. Make notes of any issues or unexpected behavior
5. Pay special attention to edge cases and error conditions

## Step 2: Capture Screenshots and Logs

Use the screenshot capture script to document the UI:

1. Run the script with the desired options:
   ```bash
   # Capture all features (requires manual interaction)
   python scripts/capture_screenshots.py --auto

   # Capture a specific feature
   python scripts/capture_screenshots.py --feature hybrid_promotion --auto

   # Capture a specific step
   python scripts/capture_screenshots.py --feature bulk_promotion --step 1 --description "Select orphan tags"
   ```

2. Follow the on-screen prompts to set up each screenshot
3. The script will create:
   - Screenshots in `docs/screenshots/`
   - Browser log templates in `docs/logs/`
   - A markdown file documenting all screenshots

## Step 3: Document Your Findings

Use the QA findings template to document your test results:

1. Open `docs/tags_page_qa_findings.md`
2. Fill in the test environment information
3. Update the overall status for each feature
4. Document any issues found during testing
5. Include screenshots and logs where relevant
6. Provide recommendations for next steps

## What to Test

### Hybrid Promotion UI
- ML suggestions with confidence scores
- "Get Suggestion" functionality
- "Quick Promote" one-click promotion
- Optimistic updates and rollback
- Undo notifications

### Bulk Promotion Drawer
- Multi-select checkboxes
- "Select All" functionality
- Custom group assignments
- Bulk promotion execution
- Results display with status indicators

### Graduation Review Panel
- Graduation review indicator
- Grouping by canonical label
- Resolve and skip actions
- Statistics updates
- Drawer functionality

## Special Cases to Test

### Error Conditions
- Network failures during API calls
- Invalid server responses
- Empty data sets
- Large data sets (performance testing)

### Edge Cases
- Special characters in tag names
- Very long tag names
- Duplicate tag names
- Tags with no suggestions
- Tags with multiple suggestions

### Cross-Browser Testing
- Test in at least Chrome, Firefox, and Safari
- Verify responsive design on mobile and tablet
- Test keyboard navigation and accessibility

## After Testing

1. Complete the QA findings document
2. Review all screenshots and logs
3. Identify any critical issues that need immediate attention
4. Create GitHub issues for any bugs found
5. Provide feedback on UX improvements
6. Sign off on the testing completion

## Tips for Effective Testing

1. **Be systematic**: Follow the checklist in order to ensure comprehensive coverage
2. **Document everything**: Take screenshots and notes for all issues, even minor ones
3. **Think like a user**: Try workflows that real users might follow
4. **Test boundaries**: Push the limits of the system with large data sets and rapid actions
5. **Verify persistence**: Make sure changes persist after page refresh and browser restart

## Troubleshooting

### Screenshot Capture Issues
- Ensure you have the necessary permissions for screen capture
- On macOS, grant screen recording permissions to your terminal
- On Linux, ensure you have the `import` command installed
- On Windows, ensure PowerShell execution policy allows scripts

### Browser Issues
- Clear browser cache before testing
- Disable browser extensions that might interfere
- Check browser console for errors
- Try incognito/private mode if issues persist

### Application Issues
- Check the backend logs for errors
- Verify the frontend is properly connected
- Ensure all API endpoints are responding
- Check for any recent changes that might affect functionality

## Resources

- [User Guide](docs/user_guide.md): Comprehensive documentation of all features
- [Medoids Workflow](docs/user_guide/medoids_workflow.md): Specific documentation for medoid features
- [API Documentation](backend/api/): Details of all API endpoints
- [GitHub Issues](https://github.com/your-repo/issues): Report bugs and feature requests

## Questions

If you have any questions about the QA process or need clarification on testing procedures, please:

1. Check this documentation first
2. Review the user guide for feature details
3. Check existing GitHub issues for similar problems
4. Create a new issue with the "question" label
