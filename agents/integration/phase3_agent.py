"""Phase 3 Agent: Enhanced Integration with Learning and Feedback Loop"""

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


class Phase3Agent(BaseCoordinationAgent):
    """Agent team for Phase 3: Enhanced Integration with Learning"""

    def __init__(self, root_dir: Path = None):
        super().__init__(
            phase_name="Enhanced Integration", phase_number=3, root_dir=root_dir
        )
        self.root_dir = root_dir or Path("/Users/jesse.kemp/Dev")
        self.cortex_dir = self.root_dir / "cortex"
        self.integration_dir = self.cortex_dir / "integration"

        # Initialize task tracking
        self.progress["tasks_total"] = 6

    def execute_phase(self) -> AgentResult:
        """Execute Phase 3: Enhanced integration with learning"""
        try:
            # Task 3.1: Create execution history analyzer (already created)
            self.update_progress("3.1", "in_progress")
            analyzer_file = self.integration_dir / "history_analyzer.py"
            if not analyzer_file.exists():
                return AgentResult(
                    success=False,
                    message="History analyzer not found. Run Phase 3 setup first.",
                    data={"phase": 3, "task": "3.1"},
                )
            self.update_progress("3.1", "completed")

            # Task 3.2: Add learning mechanism to Cortex orchestrator
            self.update_progress("3.2", "in_progress")
            self._add_learning_to_orchestrator()
            self.update_progress("3.2", "completed")

            # Task 3.3: Implement feedback loop (already created)
            self.update_progress("3.3", "in_progress")
            feedback_file = self.integration_dir / "feedback_loop.py"
            if not feedback_file.exists():
                return AgentResult(
                    success=False,
                    message="Feedback loop not found. Run Phase 3 setup first.",
                    data={"phase": 3, "task": "3.3"},
                )
            self.update_progress("3.3", "completed")

            # Task 3.4: Add metrics tracking
            self.update_progress("3.4", "in_progress")
            self._add_metrics_tracking()
            self.update_progress("3.4", "completed")

            # Task 3.5: Create adaptation tests
            self.update_progress("3.5", "in_progress")
            self._create_adaptation_tests()
            self.update_progress("3.5", "completed")

            # Task 3.6: Update documentation
            self.update_progress("3.6", "in_progress")
            self._update_documentation()
            self.update_progress("3.6", "completed")

            self.complete_phase(True, "Phase 3 completed successfully")

            return AgentResult(
                success=True,
                message="Phase 3: Enhanced integration with learning completed",
                data={
                    "phase": 3,
                    "tasks_completed": self.progress["tasks_completed"],
                    "tasks_total": self.progress["tasks_total"],
                },
            )

        except Exception as e:
            error_msg = f"Phase 3 execution failed: {str(e)}"
            self.update_progress("execution", "failed", error_msg)
            self.complete_phase(False, error_msg)
            return AgentResult(
                success=False, message=error_msg, data={"phase": 3, "error": str(e)}
            )

    def _add_learning_to_orchestrator(self):
        """Add learning mechanism to Cortex orchestrator"""
        orchestrator_file = self.cortex_dir / "orchestrator.py"
        if not orchestrator_file.exists():
            return

        content = orchestrator_file.read_text()

        # Check if learning already added
        if "FeedbackLoop" in content or "ExecutionHistoryAnalyzer" in content:
            return  # Already added

        # Add imports
        import_section = """# Enhanced integration: Learning and feedback
try:
    from integration.feedback_loop import FeedbackLoop
    from integration.history_analyzer import ExecutionHistoryAnalyzer
    LEARNING_AVAILABLE = True
except ImportError:
    FeedbackLoop = None
    ExecutionHistoryAnalyzer = None
    LEARNING_AVAILABLE = False
"""

        # Find insertion point (after local-orchestrator imports)
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if "LOCAL_ORCHESTRATOR_INTEGRATION_AVAILABLE" in line:
                insert_idx = i + 1
                break

        lines.insert(insert_idx, import_section)

        # Add feedback loop to __init__
        if "self.local_orchestrator_integration" in content:
            # Add after local_orchestrator_integration
            learning_addition = """        # Learning and feedback loop
        self.feedback_loop = (
            FeedbackLoop(root_dir)
            if LEARNING_AVAILABLE and FeedbackLoop
            else None
        )
        self.history_analyzer = (
            ExecutionHistoryAnalyzer(root_dir)
            if LEARNING_AVAILABLE and ExecutionHistoryAnalyzer
            else None
        )
"""
            for i, line in enumerate(lines):
                if "self.local_orchestrator_integration = (" in line:
                    # Find end of that block
                    j = i + 1
                    while j < len(lines) and (
                        lines[j].strip().startswith("(")
                        or lines[j].strip().startswith(")")
                        or lines[j].strip() == ""
                        or "else None" in lines[j]
                    ):
                        j += 1
                    lines.insert(j, learning_addition)
                    break

        # Modify get_next_action to use learning
        if "def get_next_action" in content and "self.feedback_loop" not in content:
            # Find the recommendation generation part
            for i, line in enumerate(lines):
                if "recommendations = self.recommendation_engine.generate" in line:
                    # Add learning adjustment after recommendations are generated
                    learning_code = """                # Apply learning adjustments if available
                if self.feedback_loop and recommendations:
                    adjusted_recommendations = []
                    for rec in recommendations:
                        adjusted = self.feedback_loop.adjust_recommendation_priority(rec, rec.priority)
                        adjusted_recommendations.append(adjusted)
                    recommendations = adjusted_recommendations
"""
                    # Find where recommendations are used
                    j = i + 1
                    while j < len(lines) and "recommendations" not in lines[j]:
                        j += 1
                    if j < len(lines):
                        lines.insert(j, learning_code)
                    break

        orchestrator_file.write_text("\n".join(lines))

    def _add_metrics_tracking(self):
        """Add metrics tracking for recommendation quality"""
        # Create metrics module
        metrics_file = self.integration_dir / "metrics.py"

        metrics_content = '''"""Metrics tracking for recommendation quality"""
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime
import json


class RecommendationMetrics:
    """Track metrics for recommendation quality"""

    def __init__(self, metrics_file: Path = None):
        """
        Initialize metrics tracker.

        Args:
            metrics_file: Path to metrics storage file
        """
        if metrics_file is None:
            metrics_file = Path.home() / ".cortex" / "recommendation_metrics.json"

        self.metrics_file = metrics_file
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_metrics()

    def _load_metrics(self):
        """Load metrics from file"""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    self.metrics = json.load(f)
            except:
                self.metrics = {"recommendations": [], "statistics": {}}
        else:
            self.metrics = {"recommendations": [], "statistics": {}}

    def _save_metrics(self):
        """Save metrics to file"""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)

    def record_recommendation(
        self,
        action_title: str,
        priority: str,
        scheduled: bool = False
    ):
        """Record a recommendation"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action_title": action_title,
            "priority": priority,
            "scheduled": scheduled
        }
        self.metrics["recommendations"].append(entry)
        self._save_metrics()

    def get_statistics(self) -> Dict[str, Any]:
        """Get recommendation statistics"""
        recommendations = self.metrics.get("recommendations", [])

        if not recommendations:
            return {
                "total": 0,
                "scheduled": 0,
                "scheduled_rate": 0.0
            }

        scheduled = sum(1 for r in recommendations if r.get("scheduled", False))

        return {
            "total": len(recommendations),
            "scheduled": scheduled,
            "scheduled_rate": scheduled / len(recommendations) if recommendations else 0.0
        }
'''

        metrics_file.write_text(metrics_content)

    def _create_adaptation_tests(self):
        """Create tests for adaptation and learning"""
        tests_dir = self.cortex_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        test_file = tests_dir / "test_integration_learning.py"

        test_content = '''"""Tests for learning and adaptation"""
import pytest
from pathlib import Path
import sys

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.history_analyzer import ExecutionHistoryAnalyzer
from integration.feedback_loop import FeedbackLoop


def test_history_analyzer_import():
    """Test that history analyzer can be imported"""
    assert ExecutionHistoryAnalyzer is not None


def test_feedback_loop_import():
    """Test that feedback loop can be imported"""
    assert FeedbackLoop is not None


def test_analyzer_initialization():
    """Test analyzer can be initialized"""
    analyzer = ExecutionHistoryAnalyzer()
    assert analyzer is not None
    # Should handle missing history gracefully
    assert isinstance(analyzer.is_available(), bool)


def test_feedback_loop_initialization():
    """Test feedback loop can be initialized"""
    feedback = FeedbackLoop()
    assert feedback is not None


def test_get_learning_metrics():
    """Test learning metrics can be retrieved"""
    feedback = FeedbackLoop()
    metrics = feedback.get_learning_metrics()
    assert isinstance(metrics, dict)
    assert "available" in metrics
'''

        test_file.write_text(test_content)

    def _update_documentation(self):
        """Update documentation with enhanced integration features"""
        readme_file = self.cortex_dir / "README.md"
        if not readme_file.exists():
            return

        content = readme_file.read_text()

        # Check if learning section already exists
        if "## Learning and Adaptation" in content:
            return  # Already documented

        # Add learning section after integration section
        learning_section = """
## Learning and Adaptation

Cortex learns from local-orchestrator execution history to improve recommendations over time.

### How Learning Works

1. **Execution Tracking**: Local-orchestrator tracks all agent executions
2. **History Analysis**: Cortex analyzes execution success rates and durations
3. **Priority Adjustment**: Recommendations are adjusted based on historical performance
4. **Confidence Updates**: Confidence scores reflect actual success rates

### Learning Metrics

Cortex tracks:
- Success rates for each action type
- Average execution durations
- Failure patterns
- Recommendation-to-execution conversion rates

### Feedback Loop

The bidirectional feedback loop:
- **Cortex → Local-Orchestrator**: Recommendations scheduled as agents
- **Local-Orchestrator → Cortex**: Execution results inform future recommendations

---
"""

        # Insert after "## Local-Orchestrator Integration" section
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("## Local-Orchestrator Integration"):
                # Find end of that section (next ## or end of file)
                j = i + 1
                while j < len(lines) and not lines[j].startswith("##"):
                    j += 1
                lines.insert(j, learning_section)
                break

        readme_file.write_text("\n".join(lines))
