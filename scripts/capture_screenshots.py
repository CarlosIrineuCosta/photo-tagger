#!/usr/bin/env python3
"""
Script to capture screenshots and logs for the Photo Tagger UI features.
This script helps document the new tag promotion features.
"""

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Configuration
SCREENSHOT_DIR = Path("docs/screenshots")
LOG_DIR = Path("docs/logs")
TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")

# Feature descriptions for documentation
FEATURES = {
    "hybrid_promotion": {
        "title": "Hybrid Promotion UI",
        "description": "Single-click promotion with ML suggestions",
        "steps": [
            "Open TagsPage",
            "View orphan tags table with suggestion metadata",
            "Click 'Get Suggestion' for a tag without suggestions",
            "Use 'Quick Promote' for one-click promotion",
            "View optimistic update and undo notification"
        ]
    },
    "bulk_promotion": {
        "title": "Bulk Promotion Drawer",
        "description": "Multi-select table for promoting multiple tags",
        "steps": [
            "Select orphan tags using checkboxes",
            "Click 'Bulk Promote' button",
            "Review selected tags in drawer",
            "Customize target groups if needed",
            "Execute bulk promotion",
            "Review results with success/failure status"
        ]
    },
    "graduation_panel": {
        "title": "Graduation Review Panel",
        "description": "Review and resolve pending graduations grouped by canonical label",
        "steps": [
            "Open graduation review drawer",
            "Review graduations grouped by canonical label",
            "Use Resolve/Skip actions for each group",
            "View updated statistics"
        ]
    }
}


def ensure_directories():
    """Create necessary directories for screenshots and logs."""
    SCREENSHOT_DIR.mkdir(exist_ok=True, parents=True)
    LOG_DIR.mkdir(exist_ok=True, parents=True)

    # Create feature-specific subdirectories
    for feature in FEATURES:
        (SCREENSHOT_DIR / feature).mkdir(exist_ok=True)
        (LOG_DIR / feature).mkdir(exist_ok=True)


def capture_screenshot(feature: str, step: str, description: str) -> Path:
    """
    Capture a screenshot for a specific feature and step.

    Args:
        feature: Feature name (key from FEATURES)
        step: Step number/name
        description: Description of what's being captured

    Returns:
        Path to the saved screenshot
    """
    filename = f"{step}_{description.replace(' ', '_').lower()}.png"
    output_path = SCREENSHOT_DIR / feature / filename

    try:
        # Try to capture screenshot using system tools
        if os.name == "posix":  # macOS/Linux
            # Use screencapture on macOS, import on Linux
            if subprocess.run(["which", "screencapture"], capture_output=True).returncode == 0:
                subprocess.run(["screencapture", "-x", str(output_path)], check=True)
            else:
                # Try using import on Linux
                subprocess.run(["import", "-window", "root", str(output_path)], check=True)
        elif os.name == "nt":  # Windows
            # Use PowerShell on Windows
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms,System.Drawing
            $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
            $bmp = New-Object System.Drawing.Bitmap $bounds.width, $bounds.height
            $graphics = [System.Drawing.Graphics]::FromImage($bmp)
            $graphics.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bounds.size)
            $bmp.Save("{output_path}")
            $graphics.Dispose()
            $bmp.Dispose()
            '''
            subprocess.run(["powershell", "-Command", ps_script], check=True)

        print(f"Screenshot saved: {output_path}")
        return output_path
    except Exception as e:
        print(f"Failed to capture screenshot: {e}")
        return Path("")


def capture_browser_logs(feature: str) -> Path:
    """
    Capture browser console logs for debugging.

    Args:
        feature: Feature name

    Returns:
        Path to the saved log file
    """
    log_path = LOG_DIR / feature / f"browser_logs_{TIMESTAMP}.txt"

    try:
        # This would need to be implemented based on the browser being used
        # For now, we'll create a placeholder file with instructions
        with open(log_path, "w") as f:
            f.write(f"# Browser Logs for {FEATURES[feature]['title']}\n")
            f.write(f"# Captured at: {datetime.now().isoformat()}\n\n")
            f.write("# Instructions:\n")
            f.write("# 1. Open browser developer tools (F12)\n")
            f.write("# 2. Reproduce the feature steps\n")
            f.write("# 3. Save console output to this file\n")

        print(f"Browser log template created: {log_path}")
        return log_path
    except Exception as e:
        print(f"Failed to create browser log template: {e}")
        return Path("")


def generate_screenshot_markdown() -> Path:
    """
    Generate a markdown file documenting the screenshots.

    Returns:
        Path to the generated markdown file
    """
    md_path = SCREENSHOT_DIR / f"screenshots_{TIMESTAMP}.md"

    with open(md_path, "w") as f:
        f.write(f"# Photo Tagger UI Screenshots\n\n")
        f.write(f"Generated at: {datetime.now().isoformat()}\n\n")

        for feature_id, feature_info in FEATURES.items():
            f.write(f"## {feature_info['title']}\n\n")
            f.write(f"{feature_info['description']}\n\n")

            feature_dir = SCREENSHOT_DIR / feature_id
            if feature_dir.exists():
                screenshots = sorted(feature_dir.glob("*.png"))
                if screenshots:
                    f.write("### Screenshots\n\n")
                    for i, screenshot in enumerate(screenshots):
                        rel_path = screenshot.relative_to(SCREENSHOT_DIR)
                        f.write(f"{i+1}. {screenshot.stem.replace('_', ' ').title()}\n")
                        f.write(f"   ![]({rel_path})\n\n")

            f.write("### Steps\n\n")
            for step in feature_info["steps"]:
                f.write(f"- {step}\n")
            f.write("\n")

    print(f"Screenshot documentation created: {md_path}")
    return md_path


def main():
    parser = argparse.ArgumentParser(description="Capture screenshots for Photo Tagger UI features")
    parser.add_argument("--feature", choices=list(FEATURES.keys()),
                       help="Capture screenshots for a specific feature only")
    parser.add_argument("--step", help="Capture a specific step only")
    parser.add_argument("--description", help="Description for the step being captured")
    parser.add_argument("--auto", action="store_true",
                       help="Automatically capture all features (requires manual interaction)")

    args = parser.parse_args()

    ensure_directories()

    if args.feature:
        if args.step and args.description:
            # Capture a specific step
            print(f"Capturing screenshot for {args.feature}, step {args.step}")
            capture_screenshot(args.feature, args.step, args.description)
        else:
            # Capture all steps for a specific feature
            print(f"Capturing all steps for {args.feature}")
            feature_info = FEATURES[args.feature]
            for i, step in enumerate(feature_info["steps"]):
                print(f"Step {i+1}: {step}")
                input("Press Enter to capture screenshot after setting up the UI...")
                capture_screenshot(args.feature, f"step_{i+1}", step)
            capture_browser_logs(args.feature)
    elif args.auto:
        # Capture all features
        print("Capturing all features (requires manual interaction)")
        for feature_id, feature_info in FEATURES.items():
            print(f"\n=== {feature_info['title']} ===")
            print(f"Description: {feature_info['description']}")
            input("Press Enter to start capturing this feature...")

            for i, step in enumerate(feature_info["steps"]):
                print(f"Step {i+1}: {step}")
                input("Press Enter to capture screenshot after setting up the UI...")
                capture_screenshot(feature_id, f"step_{i+1}", step)

            capture_browser_logs(feature_id)
    else:
        print("Please specify either --feature, --step with --description, or --auto")
        print("Example: python scripts/capture_screenshots.py --feature hybrid_promotion --auto")
        print("Example: python scripts/capture_screenshots.py --feature bulk_promotion --step 1 --description 'Select orphan tags'")

    # Generate documentation
    generate_screenshot_markdown()


if __name__ == "__main__":
    main()
