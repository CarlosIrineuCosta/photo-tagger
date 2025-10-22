#!/usr/bin/env python3
"""
Setup script for the enhanced tagging system.
This script helps configure and integrate the enhanced tagging features.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Setup enhanced tagging system")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if enhanced tagging is properly configured"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install enhanced tagging configuration"
    )
    parser.add_argument(
        "--update-api",
        action="store_true",
        help="Update the main API to include enhanced endpoints"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    if args.check:
        check_setup(args.verbose)
    elif args.install:
        install_setup(args.verbose)
    elif args.update_api:
        update_api(args.verbose)
    else:
        parser.print_help()


def check_setup(verbose: bool = False):
    """Check if enhanced tagging is properly configured."""
    print("Checking enhanced tagging setup...")

    issues = []

    # Check configuration file
    config_path = Path("config/enhanced_tagging.yaml")
    if not config_path.exists():
        issues.append("Enhanced tagging configuration file not found")
    elif verbose:
        print(f"✓ Configuration file found at {config_path}")

    # Check core module
    core_path = Path("app/core/tag_enhanced_v2.py")
    if not core_path.exists():
        issues.append("Enhanced tagging core module not found")
    elif verbose:
        print(f"✓ Core module found at {core_path}")

    # Check API module
    api_path = Path("backend/api/enhanced_tagging.py")
    if not api_path.exists():
        issues.append("Enhanced tagging API module not found")
    elif verbose:
        print(f"✓ API module found at {api_path}")

    # Check frontend components
    frontend_path = Path("frontend/src/components/EnhancedTagGallery.tsx")
    if not frontend_path.exists():
        issues.append("Enhanced tagging frontend component not found")
    elif verbose:
        print(f"✓ Frontend component found at {frontend_path}")

    # Check if enhanced endpoints are registered
    main_api_path = Path("backend/api/index.py")
    if main_api_path.exists():
        content = main_api_path.read_text()
        if "enhanced_tagging" not in content:
            issues.append("Enhanced tagging endpoints not registered in main API")
        elif verbose:
            print("✓ Enhanced endpoints registered in main API")

    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(f"  ✗ {issue}")
        print("\nRun with --install to fix these issues.")
        return 1
    else:
        print("\n✓ Enhanced tagging is properly configured!")
        return 0


def install_setup(verbose: bool = False):
    """Install enhanced tagging configuration."""
    print("Installing enhanced tagging setup...")

    # Create config directory if it doesn't exist
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)

    # Copy configuration file if it doesn't exist
    config_path = Path("config/enhanced_tagging.yaml")
    if not config_path.exists():
        # Create a default configuration
        default_config = """# Enhanced Tagging Configuration

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

# Excluded tags
excluded_tags:
  - "photo"
  - "image"
  - "picture"
  - "the"
  - "a"
  - "an"
"""
        config_path.write_text(default_config)
        if verbose:
            print(f"✓ Created configuration file at {config_path}")
    elif verbose:
        print(f"✓ Configuration file already exists at {config_path}")

    print("\n✓ Enhanced tagging setup complete!")
    print("\nNext steps:")
    print("1. Run with --update-api to register the enhanced endpoints")
    print("2. Update your frontend to use the EnhancedTagGallery component")
    print("3. Restart your application")


def update_api(verbose: bool = False):
    """Update the main API to include enhanced endpoints."""
    print("Updating main API to include enhanced endpoints...")

    main_api_path = Path("backend/api/index.py")
    if not main_api_path.exists():
        print("✗ Main API file not found")
        return 1

    content = main_api_path.read_text()

    # Check if enhanced endpoints are already registered
    if "enhanced_tagging" in content:
        if verbose:
            print("✓ Enhanced endpoints already registered")
        return 0

    # Find the import section
    import_end = content.find("from fastapi.responses import FileResponse")
    if import_end == -1:
        print("✗ Could not find import section in main API")
        return 1

    import_end = content.find("\n", import_end) + 1

    # Add the enhanced tagging import
    enhanced_import = "\nfrom backend.api.enhanced_tagging import router as enhanced_router\n"
    content = content[:import_end] + enhanced_import + content[import_end:]

    # Find the app creation
    app_creation = content.find("app = FastAPI")
    if app_creation == -1:
        print("✗ Could not find FastAPI app creation")
        return 1

    # Find the next line after app creation
    next_line = content.find("\n", app_creation) + 1

    # Add the enhanced router
    enhanced_router = "\napp.include_router(enhanced_router)\n"
    content = content[:next_line] + enhanced_router + content[next_line:]

    # Write the updated content
    main_api_path.write_text(content)

    if verbose:
        print(f"✓ Updated {main_api_path}")

    print("\n✓ Enhanced endpoints registered in main API!")
    print("\nNext steps:")
    print("1. Restart your application")
    print("2. Test the enhanced endpoints at /api/enhanced/process-tags")

    return 0


if __name__ == "__main__":
    sys.exit(main())
