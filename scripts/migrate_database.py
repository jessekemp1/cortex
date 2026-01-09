#!/usr/bin/env python3
"""Database migration script for Cortex runtime.

Migrates SQLite databases from local-orchestrator to Cortex runtime.

Usage:
    python scripts/migrate_database.py [--dry-run]
"""

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def migrate_databases(dry_run: bool = False) -> dict:
    """Migrate databases from local-orchestrator to cortex runtime.

    Args:
        dry_run: If True, only report what would be done

    Returns:
        Migration results dict
    """
    # Source locations (local-orchestrator)
    old_data_dir = Path.home() / "Dev" / "local-orchestrator" / "data"

    # Target locations (cortex runtime)
    new_data_dir = Path.home() / ".cortex" / "data"

    # Files to migrate
    migrations = [
        ("execution_history.db", "Execution history"),
        ("batch_queue.db", "Batch queue (if separate)"),
    ]

    results = {
        "dry_run": dry_run,
        "timestamp": datetime.now().isoformat(),
        "migrations": [],
        "errors": [],
    }

    # Ensure target directory exists
    if not dry_run:
        new_data_dir.mkdir(parents=True, exist_ok=True)

    for db_file, description in migrations:
        old_path = old_data_dir / db_file
        new_path = new_data_dir / db_file
        backup_path = new_data_dir / f"{db_file}.backup"

        migration_result = {
            "file": db_file,
            "description": description,
            "source": str(old_path),
            "target": str(new_path),
            "status": "pending",
        }

        # Check if source exists
        if not old_path.exists():
            migration_result["status"] = "skipped"
            migration_result["reason"] = "Source file not found"
            results["migrations"].append(migration_result)
            continue

        # Check if target already exists
        if new_path.exists():
            if dry_run:
                migration_result["status"] = "would_backup"
                migration_result["backup"] = str(backup_path)
            else:
                # Create backup
                try:
                    shutil.copy2(new_path, backup_path)
                    migration_result["backup"] = str(backup_path)
                except Exception as e:
                    migration_result["status"] = "error"
                    migration_result["error"] = f"Backup failed: {e}"
                    results["errors"].append(migration_result)
                    continue

        # Perform migration
        if dry_run:
            migration_result["status"] = "would_migrate"
            migration_result["size_mb"] = old_path.stat().st_size / (1024 * 1024)
        else:
            try:
                shutil.copy2(old_path, new_path)
                migration_result["status"] = "migrated"
                migration_result["size_mb"] = new_path.stat().st_size / (1024 * 1024)
                print(f"Migrated {db_file} ({migration_result['size_mb']:.2f} MB)")
            except Exception as e:
                migration_result["status"] = "error"
                migration_result["error"] = str(e)
                results["errors"].append(migration_result)
                continue

        results["migrations"].append(migration_result)

    return results


def print_results(results: dict):
    """Print migration results."""
    print("\n" + "=" * 60)
    print("Cortex Runtime Database Migration")
    print("=" * 60)

    if results["dry_run"]:
        print("\n*** DRY RUN - No changes made ***\n")

    print(f"Timestamp: {results['timestamp']}")
    print(f"Migrations: {len(results['migrations'])}")
    print(f"Errors: {len(results['errors'])}")

    print("\nDetails:")
    for m in results["migrations"]:
        status = m["status"]
        icon = {
            "migrated": "OK",
            "would_migrate": "WOULD",
            "skipped": "SKIP",
            "error": "ERR",
            "would_backup": "BAK",
        }.get(status, "?")

        size = f" ({m.get('size_mb', 0):.2f} MB)" if "size_mb" in m else ""
        print(f"  [{icon}] {m['file']}: {m['description']}{size}")

        if "reason" in m:
            print(f"       Reason: {m['reason']}")
        if "backup" in m:
            print(f"       Backup: {m['backup']}")
        if "error" in m:
            print(f"       Error: {m['error']}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate databases from local-orchestrator to cortex runtime"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    results = migrate_databases(dry_run=args.dry_run)
    print_results(results)

    # Exit with error if any migrations failed
    if results["errors"]:
        exit(1)


if __name__ == "__main__":
    main()
