#!/usr/bin/env python3
"""
Integration Example: Implicit Feedback Collection

Shows how to integrate the implicit feedback collector with existing Cortex components.
"""

from datetime import datetime
from typing import Dict, List

from cortex.intelligence.feedback import ImplicitFeedbackCollector


class BriefingIntegrationExample:
    """Example integration with briefing.py"""

    def __init__(self):
        self.implicit_collector = ImplicitFeedbackCollector()

    def generate_and_track_recommendations(self, project: str) -> List[Dict]:
        """
        Generate recommendations and track them.

        This simulates how briefing.py would integrate.
        """
        # Generate recommendations (existing logic)
        recommendations = self._generate_recommendations(project)

        # NEW: Track each recommendation shown
        for rec in recommendations:
            self.implicit_collector.track_recommendation_shown(
                rec_id=rec["id"],
                recommendation={
                    "title": rec["title"],
                    "description": rec.get("description", ""),
                    "files": rec.get("files", []),
                    "priority": rec.get("priority", "medium"),
                    "confidence": rec.get("confidence", 0.5),
                },
                context={
                    "source": "briefing",
                    "project": project,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        return recommendations

    def _generate_recommendations(self, project: str) -> List[Dict]:
        """Placeholder for existing recommendation generation."""
        return [
            {
                "id": "rec_001",
                "title": "Fix failing tests",
                "priority": "high",
                "confidence": 0.85,
                "files": ["tests/test_data.py"],
            },
            {
                "id": "rec_002",
                "title": "Update documentation",
                "priority": "medium",
                "confidence": 0.7,
                "files": ["README.md"],
            },
        ]


class BridgeIntegrationExample:
    """Example integration with bridge.py"""

    def __init__(self):
        self.implicit_collector = ImplicitFeedbackCollector()

    def trigger_action(self, action: str, files: List[str] = None) -> Dict:
        """
        Execute action and track for implicit feedback.

        This simulates how bridge.py trigger_action would integrate.
        """
        files = files or []

        # NEW: Track action taken
        self.implicit_collector.track_action_taken(
            action=action,
            files=files,
            context={
                "agent": "bridge",
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Execute action (existing logic)
        result = self._execute_action(action, files)

        return result

    def _execute_action(self, action: str, files: List[str]) -> Dict:
        """Placeholder for existing action execution."""
        return {
            "success": True,
            "action": action,
            "files": files,
            "timestamp": datetime.now().isoformat(),
        }


class SessionManagerIntegrationExample:
    """Example integration with session_manager.py"""

    def __init__(self):
        self.implicit_collector = ImplicitFeedbackCollector()
        self.session_active = False

    def start_session(self):
        """Start new session."""
        self.session_active = True
        print("Session started")

    def end_session(self):
        """End session and mark ignored recommendations."""
        if not self.session_active:
            return

        # NEW: Mark ignored recommendations and get stats
        self.implicit_collector.session_end()

        stats = self.implicit_collector.get_session_stats()
        print(
            f"Session ended: {stats['followed']}/{stats['total_shown']} "
            f"recommendations followed"
        )

        self.session_active = False


def demo_complete_workflow():
    """Demo complete workflow with all integration points."""
    print("\n" + "=" * 60)
    print("Complete Workflow Demo")
    print("=" * 60)

    # Initialize components
    briefing = BriefingIntegrationExample()
    bridge = BridgeIntegrationExample()
    session_mgr = SessionManagerIntegrationExample()

    # Share the same collector across components
    collector = ImplicitFeedbackCollector()
    briefing.implicit_collector = collector
    bridge.implicit_collector = collector
    session_mgr.implicit_collector = collector

    # 1. Start session
    print("\n1. Starting session...")
    session_mgr.start_session()

    # 2. Generate briefing with recommendations
    print("\n2. Generating briefing...")
    recommendations = briefing.generate_and_track_recommendations(project="cortex")
    print(f"   Generated {len(recommendations)} recommendations")
    for rec in recommendations:
        print(f"   - [{rec['priority']}] {rec['title']}")

    # 3. User takes actions
    print("\n3. User takes actions...")
    print("   $ pytest tests/test_data.py")
    bridge.trigger_action(action="Run pytest on test_data.py", files=["tests/test_data.py"])

    print("   $ vim README.md")
    bridge.trigger_action(action="Edit README.md", files=["README.md"])

    # 4. End session
    print("\n4. Ending session...")
    session_mgr.end_session()

    # 5. Show statistics
    print("\n5. Session statistics:")
    stats = collector.get_stats(days=1)
    print(f"   Total signals: {stats['total_signals']}")
    print(f"   Follows: {stats['follows']}")
    print(f"   Ignores: {stats['ignores']}")
    print(f"   Follow rate: {stats['follow_rate']:.1%}")

    # 6. Show stored signals
    print("\n6. Stored signals:")
    signals = collector.load_signals()
    for signal in signals:
        print(
            f"   - {signal.signal_type}: {signal.recommendation_id} "
            f"(similarity: {signal.similarity:.2f})"
        )


def demo_shared_collector_pattern():
    """
    Demo recommended pattern: shared collector across components.

    This is the cleanest integration approach.
    """
    print("\n" + "=" * 60)
    print("Shared Collector Pattern (Recommended)")
    print("=" * 60)

    # Single collector instance
    collector = ImplicitFeedbackCollector()

    # Option 1: Dependency injection
    class BriefingService:
        def __init__(self, collector: ImplicitFeedbackCollector):
            self.collector = collector

        def show_recommendation(self, rec):
            self.collector.track_recommendation_shown(rec["id"], rec)

    class ActionService:
        def __init__(self, collector: ImplicitFeedbackCollector):
            self.collector = collector

        def execute_action(self, action, files):
            self.collector.track_action_taken(action, files)

    # Wire up services
    briefing_svc = BriefingService(collector)
    action_svc = ActionService(collector)

    print("\n1. Services initialized with shared collector")

    # Use services
    briefing_svc.show_recommendation({"id": "rec_001", "title": "Fix tests"})
    print("2. Recommendation shown via BriefingService")

    action_svc.execute_action("Fix tests", ["tests/test_data.py"])
    print("3. Action executed via ActionService")

    # End session
    collector.session_end()
    print("4. Session ended")

    # Show results
    signals = collector.load_signals()
    print(f"\n5. Result: {len(signals)} signals collected")


def demo_singleton_pattern():
    """
    Demo alternative: singleton pattern.

    Use this if dependency injection is too complex for your codebase.
    """
    print("\n" + "=" * 60)
    print("Singleton Pattern (Alternative)")
    print("=" * 60)

    # Global singleton instance (use class attribute for scope)
    class CollectorSingleton:
        _instance = None

        @classmethod
        def get_instance(cls) -> ImplicitFeedbackCollector:
            """Get or create singleton collector instance."""
            if cls._instance is None:
                cls._instance = ImplicitFeedbackCollector()
            return cls._instance

    # Use in different modules
    class BriefingModule:
        def show_recommendation(self, rec):
            CollectorSingleton.get_instance().track_recommendation_shown(rec["id"], rec)

    class BridgeModule:
        def execute_action(self, action, files):
            CollectorSingleton.get_instance().track_action_taken(action, files)

    # Use modules
    briefing = BriefingModule()
    bridge = BridgeModule()

    briefing.show_recommendation({"id": "rec_001", "title": "Fix tests"})
    print("1. Recommendation shown via BriefingModule")

    bridge.execute_action("Fix tests", ["tests/test_data.py"])
    print("2. Action executed via BridgeModule")

    CollectorSingleton.get_instance().session_end()
    print("3. Session ended via singleton")

    signals = CollectorSingleton.get_instance().load_signals()
    print(f"\n4. Result: {len(signals)} signals collected")


if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  Implicit Feedback Collection - Integration Examples    ║")
    print("╚══════════════════════════════════════════════════════════╝")

    demo_complete_workflow()
    demo_shared_collector_pattern()
    demo_singleton_pattern()

    print("\n" + "=" * 60)
    print("Integration examples complete!")
    print("=" * 60)
    print("\nRecommended approach: Shared collector with dependency injection")
    print("See intelligence/feedback/README.md for full documentation")
    print()
