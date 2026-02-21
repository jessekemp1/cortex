import os
"""Phase 2 Agent: Add Integration Layer between Cortex and local-orchestrator"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Add cortex to path
CORTEX_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(CORTEX_DIR))

from agents.integration.base_coordination_agent import BaseCoordinationAgent

# Try to import AgentResult
try:
    sys.path.insert(0, str(CORTEX_DIR.parent / "local-orchestrator"))
    from orchestrator_models import AgentResult
except ImportError:
    from dataclasses import dataclass
    from typing import Optional as Opt

    @dataclass
    class AgentResult:
        success: bool
        message: str
        data: Opt[Dict[str, Any]] = None
        execution_time: Opt[float] = None
        timestamp: datetime = None


class Phase2Agent(BaseCoordinationAgent):
    """Agent team for Phase 2: Add Integration Layer"""

    def __init__(self, root_dir: Path = None):
        super().__init__(phase_name="Add Integration Layer", phase_number=2, root_dir=root_dir)
        self.root_dir = root_dir or Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))
        self.cortex_dir = self.root_dir / "cortex"
        self.integration_dir = self.cortex_dir / "integration"

        # Initialize task tracking
        self.progress["tasks_total"] = 6

    def execute_phase(self) -> AgentResult:
        """Execute Phase 2: Add integration layer"""
        try:
            # Task 2.1: Create integration module (already created)
            self.update_progress("2.1", "in_progress")
            integration_module = self.integration_dir / "local_orchestrator.py"
            if not integration_module.exists():
                return AgentResult(
                    success=False,
                    message="Integration module not found. Run Phase 2 setup first.",
                    data={"phase": 2, "task": "2.1"},
                )
            self.update_progress("2.1", "completed")

            # Task 2.2: Verify adapter class exists
            self.update_progress("2.2", "in_progress")
            adapter_works = self._verify_adapter()
            if not adapter_works:
                return AgentResult(
                    success=False,
                    message="Adapter class verification failed",
                    data={"phase": 2, "task": "2.2"},
                )
            self.update_progress("2.2", "completed")

            # Task 2.3: Add optional import to Cortex orchestrator
            self.update_progress("2.3", "in_progress")
            self._add_integration_to_orchestrator()
            self.update_progress("2.3", "completed")

            # Task 2.4: Add schedule command to CLI
            self.update_progress("2.4", "in_progress")
            self._add_schedule_command()
            self.update_progress("2.4", "completed")

            # Task 2.5: Create integration tests
            self.update_progress("2.5", "in_progress")
            self._create_integration_tests()
            self.update_progress("2.5", "completed")

            # Task 2.6: Update documentation
            self.update_progress("2.6", "in_progress")
            self._update_documentation()
            self.update_progress("2.6", "completed")

            self.complete_phase(True, "Phase 2 completed successfully")

            return AgentResult(
                success=True,
                message="Phase 2: Integration layer added successfully",
                data={
                    "phase": 2,
                    "tasks_completed": self.progress["tasks_completed"],
                    "tasks_total": self.progress["tasks_total"],
                },
            )

        except Exception as e:
            error_msg = f"Phase 2 execution failed: {str(e)}"
            self.update_progress("execution", "failed", error_msg)
            self.complete_phase(False, error_msg)
            return AgentResult(success=False, message=error_msg, data={"phase": 2, "error": str(e)})

    def _verify_adapter(self) -> bool:
        """Verify adapter class can be imported and instantiated"""
        try:
            from integration.local_orchestrator import (
                CortexLocalOrchestratorIntegration,
            )

            # Try to create integration instance (may fail if local-orchestrator not available, that's OK)
            try:
                CortexLocalOrchestratorIntegration()
                # Just verify the class exists, availability check is separate
                return True
            except ImportError:
                # local-orchestrator not available, but adapter class exists
                return True

        except Exception as e:
            print(f"Adapter verification failed: {e}")
            return False

    def _add_integration_to_orchestrator(self):
        """Add optional local-orchestrator integration to Cortex orchestrator"""
        orchestrator_file = self.cortex_dir / "orchestrator.py"
        if not orchestrator_file.exists():
            return

        content = orchestrator_file.read_text()

        # Check if integration already added
        if "CortexLocalOrchestratorIntegration" in content:
            return  # Already added

        # Add import at the top (after other imports)
        import_section = """# Optional local-orchestrator integration
try:
    from integration.local_orchestrator import CortexLocalOrchestratorIntegration
    LOCAL_ORCHESTRATOR_INTEGRATION_AVAILABLE = True
except ImportError:
    CortexLocalOrchestratorIntegration = None
    LOCAL_ORCHESTRATOR_INTEGRATION_AVAILABLE = False
"""

        # Find insertion point (after context intelligence imports)
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if "ContextIntelligence = None" in line:
                insert_idx = i + 1
                break

        lines.insert(insert_idx, import_section)

        # Add integration instance to __init__
        if "self.context_intel" in content:
            # Add after context_intel initialization
            init_addition = """        # Optional local-orchestrator integration
        self.local_orchestrator_integration = (
            CortexLocalOrchestratorIntegration(root_dir)
            if LOCAL_ORCHESTRATOR_INTEGRATION_AVAILABLE and CortexLocalOrchestratorIntegration
            else None
        )
"""
            # Find __init__ method and add after context_intel
            for i, line in enumerate(lines):
                if "self.context_intel = ContextIntelligence" in line:
                    lines.insert(i + 1, init_addition)
                    break

        orchestrator_file.write_text("\n".join(lines))

    def _add_schedule_command(self):
        """Add schedule command to Cortex CLI"""
        cli_file = self.cortex_dir / "cli.py"
        if not cli_file.exists():
            return

        content = cli_file.read_text()

        # Check if schedule command already exists
        if (
            "cmd_schedule" in content
            or "schedule" in content
            and "subparsers.add_parser('schedule')" in content
        ):
            return  # Already added

        # Add import for integration
        if "from integration.local_orchestrator import" not in content:
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("from feedback import"):
                    lines.insert(
                        i + 1,
                        "from integration.local_orchestrator import CortexLocalOrchestratorIntegration",
                    )
                    break
            content = "\n".join(lines)

        # Add cmd_schedule function before main()
        schedule_function = '''
def cmd_schedule(args):
    """Schedule a recommendation as a local-orchestrator agent."""
    from orchestrator import CortexOrchestrator

    orchestrator = CortexOrchestrator(root_dir=Path(args.root))

    # Get next recommendation
    try:
        response = orchestrator.get_next_action(
            project_filter=args.project,
            limit=1
        )

        if not response.next_action:
            print("No recommendations available to schedule.")
            return

        recommendation = response.next_action

        # Initialize integration
        integration = CortexLocalOrchestratorIntegration(root_dir=Path(args.root))

        if not integration.is_available():
            print("Error: local-orchestrator integration not available.")
            print("Make sure local-orchestrator is installed and dependencies are met.")
            sys.exit(1)

        # Schedule the recommendation
        schedule = args.schedule or "0 8 * * *"  # Default: daily at 8 AM

        success = integration.schedule_recommendation(recommendation, schedule)

        if success:
            print(f"✓ Scheduled: {recommendation.action_title}")
            print(f"  Schedule: {schedule}")
            print(f"  Rationale: {recommendation.rationale}")
        else:
            print("✗ Failed to schedule recommendation.")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
'''

        # Insert before main() function
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("def main():"):
                lines.insert(i, schedule_function)
                break
        content = "\n".join(lines)

        # Add schedule subparser in main()
        if "schedule_parser = subparsers.add_parser('schedule')" not in content:
            # Find where subparsers are added
            for i, line in enumerate(lines):
                if "feedback_parser = subparsers.add_parser('feedback')" in line:
                    # Add schedule parser after feedback
                    schedule_parser_code = """
    schedule_parser = subparsers.add_parser(
        'schedule',
        help='Schedule a recommendation as a local-orchestrator agent'
    )
    schedule_parser.add_argument(
        '--project',
        type=str,
        help='Filter by project name'
    )
    schedule_parser.add_argument(
        '--schedule',
        type=str,
        default="0 8 * * *",
        help='Cron schedule (default: "0 8 * * *" for daily at 8 AM)'
    )
    schedule_parser.set_defaults(func=cmd_schedule)
"""
                    lines.insert(i + 20, schedule_parser_code)  # Insert after feedback parser setup
                    break

        cli_file.write_text("\n".join(lines))

    def _create_integration_tests(self):
        """Create integration tests"""
        tests_dir = self.cortex_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        test_file = tests_dir / "test_integration_local_orchestrator.py"

        test_content = '''"""Tests for Cortex-local-orchestrator integration"""
import pytest
from pathlib import Path
import sys

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.local_orchestrator import (
    RecommendationToAgentAdapter,
    CortexLocalOrchestratorIntegration,
    LOCAL_ORCHESTRATOR_AVAILABLE
)


def test_adapter_import():
    """Test that adapter can be imported"""
    assert RecommendationToAgentAdapter is not None
    assert CortexLocalOrchestratorIntegration is not None


def test_integration_initialization():
    """Test integration can be initialized"""
    if not LOCAL_ORCHESTRATOR_AVAILABLE:
        pytest.skip("local-orchestrator not available")

    integration = CortexLocalOrchestratorIntegration()
    # Should not raise exception
    assert integration is not None


def test_integration_availability_check():
    """Test availability check"""
    integration = CortexLocalOrchestratorIntegration()
    # Should return boolean
    assert isinstance(integration.is_available(), bool)
'''

        test_file.write_text(test_content)

    def _update_documentation(self):
        """Update README with integration documentation"""
        readme_file = self.cortex_dir / "README.md"
        if not readme_file.exists():
            return

        content = readme_file.read_text()

        # Check if integration section already exists
        if "## Local-Orchestrator Integration" in content:
            return  # Already documented

        # Add integration section before "## Installation"
        integration_section = """
## Local-Orchestrator Integration

Cortex can optionally integrate with `local-orchestrator` to schedule recommended actions as automated agents.

### Schedule a Recommendation

```bash
# Schedule the current top recommendation
cortex schedule

# Schedule with custom cron schedule
cortex schedule --schedule "0 9 * * *"  # Daily at 9 AM

# Schedule recommendation for specific project
cortex schedule --project vortexv2
```

### Requirements

- `local-orchestrator` must be installed and configured
- Dependencies: `apscheduler`, `fastapi`, `uvicorn`

### How It Works

1. Cortex generates a recommendation
2. Integration adapter converts recommendation to local-orchestrator agent
3. Agent is registered with local-orchestrator scheduler
4. Agent executes on the specified schedule

---
"""

        # Insert before "## Installation" section
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("## Installation"):
                lines.insert(i, integration_section)
                break

        readme_file.write_text("\n".join(lines))
