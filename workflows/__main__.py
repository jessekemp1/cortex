"""CLI entry point for running Cortex YAML workflows.

Usage:
    python -m cortex.workflows <workflow.yaml> [--dry-run]
    python -m cortex.workflows --list
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cortex.workflows.runner import run_workflow_file

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="cortex.workflows",
        description="Run a Cortex YAML-defined workflow.",
    )
    parser.add_argument(
        "workflow",
        nargs="?",
        help="Path to the workflow YAML file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview steps without executing them",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_workflows",
        help="List available workflows in cortex/workflows/",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # List mode
    if args.list_workflows or args.workflow is None:
        return _list_workflows()

    # Resolve workflow path
    workflow_path = Path(args.workflow)
    if not workflow_path.is_absolute():
        workflow_path = Path.cwd() / workflow_path

    if not workflow_path.exists():
        print(f"Error: Workflow file not found: {workflow_path}", file=sys.stderr)
        return 1

    # Run
    if args.dry_run:
        print(f"[dry-run] Loading workflow: {workflow_path.name}\n")

    try:
        result = run_workflow_file(
            path=workflow_path,
            working_dir=Path.home() / "Dev",
            dry_run=args.dry_run,
        )
    except Exception as e:
        print(f"Error loading/running workflow: {e}", file=sys.stderr)
        logger.debug("Full traceback:", exc_info=True)
        return 1

    # Print summary
    print()
    print(result.summary())

    return 0 if result.success else 1


def _list_workflows() -> int:
    """Scan cortex/workflows/*.yaml and print available workflows."""
    import yaml

    workflows_dir = Path(__file__).parent
    yamls = sorted(workflows_dir.glob("*.yaml"))

    if not yamls:
        print("No workflows found in cortex/workflows/")
        return 0

    print("Available workflows:\n")
    print(f"  {'Name':<30} {'Description'}")
    print(f"  {'----':<30} {'-----------'}")

    for yf in yamls:
        try:
            with open(yf) as f:
                data = yaml.safe_load(f)
            name = data.get("name", yf.stem)
            desc = data.get("description", "")[:60]
        except Exception:
            name = yf.stem
            desc = "(error reading file)"
        print(f"  {name:<30} {desc}")

    print("\nRun with: python -m cortex.workflows cortex/workflows/<name>.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
