#!/usr/bin/env python3
"""
Non-interactive screenshot generator for Photo Tagger UI features.
This script creates placeholder screenshots for documentation purposes.
"""

import os
from datetime import datetime
from pathlib import Path

# Configuration
SCREENSHOT_DIR = Path("docs/screenshots")
TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")

def ensure_directories():
    """Create necessary directories for screenshots."""
    SCREENSHOT_DIR.mkdir(exist_ok=True, parents=True)

    # Create feature-specific subdirectories
    (SCREENSHOT_DIR / "gallery_status").mkdir(exist_ok=True)

def generate_placeholder_screenshots():
    """Generate placeholder screenshots for gallery status features."""
    gallery_dir = SCREENSHOT_DIR / "gallery_status"

    # Create placeholder files for each step
    steps = [
        ("step_1_all_stage_filter", "View GalleryPage with 'All' stage filter selected"),
        ("step_2_new_stage_filter", "Click 'New' stage filter and verify inventory updates"),
        ("step_3_needs_tags_stage_filter", "Click 'Needs tags' stage filter and verify inventory updates"),
        ("step_4_draft_stage_filter", "Click 'Draft' stage filter and verify inventory updates"),
        ("step_5_saved_stage_filter", "Click 'Saved' stage filter and verify inventory updates"),
        ("step_6_blocked_stage_filter", "Click 'Blocked' stage filter and verify inventory updates"),
        ("step_7_additional_filters", "Test toggle filters (Medoids only, Only unapproved, Hide saved)"),
        ("step_8_pagination", "Verify pagination/infinite scroll works with each stage filter"),
    ]

    for filename, description in steps:
        placeholder_file = gallery_dir / f"{filename}.md"
        with open(placeholder_file, "w") as f:
            f.write(f"# {description}\n\n")
            f.write("## Screenshot Requirements\n\n")
            f.write("1. Open Photo Tagger application in browser\n")
            f.write("2. Navigate to Gallery page\n")
            f.write("3. Set up the UI as described\n")
            f.write("4. Capture screenshot\n\n")
            f.write("## Expected Elements\n\n")
            f.write("- Stage filter controls\n")
            f.write("- Summary chips (when 'All' is selected)\n")
            f.write("- Gallery grid with appropriate items\n")
            f.write("- Additional filter toggles\n\n")
            f.write("## Notes\n\n")
            f.write("Replace this file with actual screenshot (.png format)\n")

        print(f"Created placeholder: {placeholder_file}")

def generate_markdown_documentation():
    """Generate markdown documentation for screenshots."""
    md_path = SCREENSHOT_DIR / f"screenshots_{TIMESTAMP}.md"

    with open(md_path, "w") as f:
        f.write(f"# Photo Tagger UI Screenshots - Gallery Status Features\n\n")
        f.write(f"Generated at: {datetime.now().isoformat()}\n\n")

        f.write("## Gallery Status Features\n\n")
        f.write("This document captures the gallery status filtering and UI features.\n\n")

        f.write("### Features Covered\n\n")
        f.write("1. Stage filtering (All, New, Needs tags, Draft, Saved, Blocked)\n")
        f.write("2. Summary chips showing counts for each stage\n")
        f.write("3. Additional filter toggles (Medoids only, Unapproved, Hide saved, Center)\n")
        f.write("4. Pagination/infinite scroll behavior\n\n")

        f.write("### Screenshots\n\n")
        gallery_dir = Path("gallery_status")
        if gallery_dir.exists():
            for placeholder_file in sorted(gallery_dir.glob("*.md")):
                step_name = placeholder_file.stem.replace("_", " ").title()
                description = placeholder_file.read_text().split("\n")[0].replace("# ", "")
                f.write(f"#### {step_name}\n\n")
                f.write(f"{description}\n\n")
                f.write(f"![{step_name}](gallery_status/{placeholder_file.stem}.png)\n\n")

        f.write("### Test Coverage\n\n")
        f.write("The automated test suite `GalleryStageFilters.test.tsx` covers:\n\n")
        f.write("- Stage filter control rendering and interaction\n")
        f.write("- Additional filter toggle functionality\n")
        f.write("- Callback handling for filter changes\n")
        f.write("- Integration with API test expectations\n\n")

        f.write("### Running Tests\n\n")
        f.write("```bash\n")
        f.write("cd frontend && npx vitest run src/components/__tests__/GalleryStageFilters.test.tsx\n")
        f.write("```\n\n")

        f.write("### Manual Screenshot Capture\n\n")
        f.write("To capture actual screenshots:\n\n")
        f.write("```bash\n")
        f.write("./scripts/run_gallery_screenshots.sh\n")
        f.write("```\n\n")
        f.write("Note: This requires an interactive environment with display access.\n")

    print(f"Documentation created: {md_path}")

def main():
    ensure_directories()
    generate_placeholder_screenshots()
    generate_markdown_documentation()
    print("\nScreenshot generation complete!")
    print(f"Placeholders created in: {SCREENSHOT_DIR / 'gallery_status'}")
    print(f"Documentation created: {SCREENSHOT_DIR / f'screenshots_{TIMESTAMP}.md'}")
    print("\nTo capture actual screenshots, run:")
    print("  ./scripts/run_gallery_screenshots.sh")
    print("\nThis requires an interactive environment with display access.")

if __name__ == "__main__":
    main()
