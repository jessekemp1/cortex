#!/usr/bin/env python3
"""
Migration script to fix permissions on existing Cortex config files.

This script:
1. Finds all sensitive files in ~/.cortex
2. Sets secure permissions (600 for files, 700 for directories)
3. Reports what was changed

Usage:
    python scripts/fix_config_permissions.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path so we can import from cortex
sys.path.insert(0, str(Path(__file__).parent.parent))

from security import (
    SECURE_DIR_MODE,
    SECURE_FILE_MODE,
    get_file_permissions,
    get_permission_string,
    is_permission_secure,
    set_secure_permissions,
)

# Files that should have secure permissions
SENSITIVE_FILE_PATTERNS = [
    "*.yaml",
    "*.yml",
    "*.json",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    ".env",
    "*_key*",
    "*_secret*",
    "*credentials*",
    "*token*",
]

# Files to skip (system files)
SKIP_FILES = {
    ".DS_Store",
    ".gitkeep",
    "README.md",
}


def should_secure_file(path: Path) -> bool:
    """Determine if a file should have secure permissions."""
    # Skip system files
    if path.name in SKIP_FILES:
        return False

    # Check if matches sensitive patterns
    for pattern in SENSITIVE_FILE_PATTERNS:
        if path.match(pattern):
            return True

    # Default: secure all files in .cortex
    return True


def fix_permissions(config_dir: Path, dry_run: bool = False) -> dict:
    """
    Fix permissions on all files in the config directory.

    Args:
        config_dir: Path to the .cortex directory
        dry_run: If True, only report what would be changed

    Returns:
        dict with statistics about changes made
    """
    stats = {
        "files_checked": 0,
        "files_fixed": 0,
        "files_already_secure": 0,
        "files_skipped": 0,
        "dirs_checked": 0,
        "dirs_fixed": 0,
        "dirs_already_secure": 0,
        "errors": 0,
    }

    if not config_dir.exists():
        print(f"❌ Config directory does not exist: {config_dir}")
        return stats

    print(f"🔍 Scanning {config_dir}")
    print()

    # Fix directory permissions first
    if not is_permission_secure(config_dir, is_directory=True):
        current_mode = get_file_permissions(config_dir)
        print(f"📁 {config_dir}")
        print(f"   Current: {get_permission_string(current_mode)}")
        print(f"   Target:  {get_permission_string(SECURE_DIR_MODE)}")

        if not dry_run:
            try:
                set_secure_permissions(config_dir, is_directory=True)
                print("   ✅ Fixed")
                stats["dirs_fixed"] += 1
            except Exception as e:
                print(f"   ❌ Error: {e}")
                stats["errors"] += 1
        else:
            print("   🔧 Would fix (dry-run)")
            stats["dirs_fixed"] += 1
    else:
        stats["dirs_already_secure"] += 1

    stats["dirs_checked"] += 1
    print()

    # Process all files and subdirectories
    for item in sorted(config_dir.rglob("*")):
        if item.is_file():
            stats["files_checked"] += 1

            # Skip files that don't need securing
            if not should_secure_file(item):
                stats["files_skipped"] += 1
                continue

            # Check if already secure
            if is_permission_secure(item, is_directory=False):
                stats["files_already_secure"] += 1
                continue

            # File needs fixing
            current_mode = get_file_permissions(item)
            print(f"📄 {item.relative_to(config_dir)}")
            print(f"   Current: {get_permission_string(current_mode)}")
            print(f"   Target:  {get_permission_string(SECURE_FILE_MODE)}")

            if not dry_run:
                try:
                    set_secure_permissions(item, is_directory=False)
                    print("   ✅ Fixed")
                    stats["files_fixed"] += 1
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    stats["errors"] += 1
            else:
                print("   🔧 Would fix (dry-run)")
                stats["files_fixed"] += 1

            print()

        elif item.is_dir() and item != config_dir:
            stats["dirs_checked"] += 1

            if not is_permission_secure(item, is_directory=True):
                current_mode = get_file_permissions(item)
                print(f"📁 {item.relative_to(config_dir)}/")
                print(f"   Current: {get_permission_string(current_mode)}")
                print(f"   Target:  {get_permission_string(SECURE_DIR_MODE)}")

                if not dry_run:
                    try:
                        set_secure_permissions(item, is_directory=True)
                        print("   ✅ Fixed")
                        stats["dirs_fixed"] += 1
                    except Exception as e:
                        print(f"   ❌ Error: {e}")
                        stats["errors"] += 1
                else:
                    print("   🔧 Would fix (dry-run)")
                    stats["dirs_fixed"] += 1

                print()
            else:
                stats["dirs_already_secure"] += 1

    return stats


def print_summary(stats: dict, dry_run: bool):
    """Print summary of changes made."""
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()

    print(f"Files checked:        {stats['files_checked']}")
    print(f"Files already secure: {stats['files_already_secure']}")
    print(f"Files skipped:        {stats['files_skipped']}")
    print(f"Files fixed:          {stats['files_fixed']}")
    print()

    print(f"Directories checked:        {stats['dirs_checked']}")
    print(f"Directories already secure: {stats['dirs_already_secure']}")
    print(f"Directories fixed:          {stats['dirs_fixed']}")
    print()

    if stats["errors"] > 0:
        print(f"❌ Errors encountered: {stats['errors']}")
        print()

    if dry_run and (stats["files_fixed"] > 0 or stats["dirs_fixed"] > 0):
        print("⚠️  This was a dry-run. No changes were made.")
        print("   Run without --dry-run to apply changes.")
    elif stats["files_fixed"] > 0 or stats["dirs_fixed"] > 0:
        print("✅ All permissions have been secured!")
    elif stats["files_already_secure"] == stats["files_checked"] - stats["files_skipped"]:
        print("✅ All files already have secure permissions!")


def main():
    parser = argparse.ArgumentParser(description="Fix permissions on Cortex config files")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be changed without making changes"
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path.home() / ".cortex",
        help="Path to Cortex config directory (default: ~/.cortex)",
    )

    args = parser.parse_args()

    print("🔐 Cortex Config Permission Fixer")
    print("=" * 60)
    print()

    if args.dry_run:
        print("⚠️  DRY-RUN MODE - No changes will be made")
        print()

    stats = fix_permissions(args.config_dir, dry_run=args.dry_run)
    print_summary(stats, args.dry_run)

    # Exit code based on results
    if stats["errors"] > 0:
        sys.exit(1)
    elif args.dry_run and (stats["files_fixed"] > 0 or stats["dirs_fixed"] > 0):
        sys.exit(2)  # Changes needed
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
