"""
Q-Learning Task Router for Cortex

Learns optimal task routing decisions from historical outcomes.
Used by /foresight to score batch job candidates and decide:
- queue_now: Execute immediately
- defer_morning: Queue for next morning batch
- investigate_first: Needs research before action
- skip: Low value, don't queue

State features:
  project    — vortex, cortex, alpha_arena, winfield, other
  task_type  — bug_fix, feature, investigation, validation, optimization, other
  time_slot  — morning (6-12), afternoon (12-18), evening (18-24), night (0-6)
  priority   — A, B, C

Action space:
  queue_now, defer_morning, investigate_first, skip

Rewards (from outcomes.jsonl):
  success     → +1.0
  partial     → +0.3
  failed      → -0.5
  not_followed → -0.1

Training: call train() to learn from ~/.cortex/outcomes.jsonl
Inference: call recommend(state) to get action + confidence

Persistence: Q-table saved to ~/.cortex/q_table.json
"""

import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

CORTEX_DIR = Path.home() / ".cortex"
Q_TABLE_FILE = CORTEX_DIR / "q_table.json"
OUTCOMES_FILE = CORTEX_DIR / "outcomes.jsonl"

# State discretization
PROJECTS = ["vortex", "cortex", "alpha_arena", "winfield", "other"]
TASK_TYPES = ["bug_fix", "feature", "investigation", "validation", "optimization", "other"]
TIME_SLOTS = ["morning", "afternoon", "evening", "night"]
PRIORITIES = ["A", "B", "C"]

# Action space
ACTIONS = ["queue_now", "defer_morning", "investigate_first", "skip"]

# Q-learning hyperparameters
ALPHA = 0.1  # Learning rate
GAMMA = 0.9  # Discount factor
EPSILON = 0.15  # Exploration rate (after initial training)
INITIAL_EPSILON = 0.3  # Exploration rate during training

# Reward mapping
REWARD_MAP = {
    "success": 1.0,
    "partial": 0.3,
    "failed": -0.5,
    "not_followed": -0.1,
}

# Prior knowledge: map recommendation_type → likely best action
TYPE_TO_ACTION_PRIOR = {
    "blocker_resolution": "queue_now",
    "goal_progress": "queue_now",
    "optimization": "defer_morning",
    "investigation": "investigate_first",
    "maintenance": "defer_morning",
    "documentation": "skip",
}


class TaskRouter:
    """Q-learning router for batch task decisions."""

    def __init__(self):
        self.q_table: dict[str, dict[str, float]] = defaultdict(lambda: {a: 0.0 for a in ACTIONS})
        self.visit_count: dict[str, int] = defaultdict(int)
        self._load()

    def _state_key(
        self,
        project: str = "other",
        task_type: str = "other",
        time_slot: str = "morning",
        priority: str = "B",
    ) -> str:
        """Discretize state into a hashable key."""
        p = project if project in PROJECTS else "other"
        t = task_type if task_type in TASK_TYPES else "other"
        ts = time_slot if time_slot in TIME_SLOTS else "morning"
        pr = priority if priority in PRIORITIES else "B"
        return f"{p}|{t}|{ts}|{pr}"

    def _load(self):
        """Load Q-table from disk."""
        try:
            if Q_TABLE_FILE.exists():
                data = json.loads(Q_TABLE_FILE.read_text())
                for state, actions in data.get("q_table", {}).items():
                    self.q_table[state] = actions
                for state, count in data.get("visit_count", {}).items():
                    self.visit_count[state] = count
        except Exception:
            pass

    def save(self):
        """Persist Q-table to disk."""
        CORTEX_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "q_table": dict(self.q_table),
            "visit_count": dict(self.visit_count),
            "updated_at": datetime.now(tz=None).isoformat(),
            "states_explored": len(self.q_table),
            "total_visits": sum(self.visit_count.values()),
        }
        Q_TABLE_FILE.write_text(json.dumps(data, indent=2))

    def _get_time_slot(self, timestamp: Optional[str] = None) -> str:
        """Map timestamp to time slot."""
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp)
            else:
                dt = datetime.now()
            hour = dt.hour
            if 6 <= hour < 12:
                return "morning"
            elif 12 <= hour < 18:
                return "afternoon"
            elif 18 <= hour < 24:
                return "evening"
            else:
                return "night"
        except Exception:
            return "morning"

    def _classify_project(self, context) -> str:
        """Classify project from context string or dict."""
        if isinstance(context, dict):
            context = json.dumps(context)
        ctx = str(context).lower() if context else ""
        if "vortex" in ctx or "grib" in ctx or "forecast" in ctx or "weather" in ctx:
            return "vortex"
        elif "cortex" in ctx or "guardian" in ctx or "hook" in ctx:
            return "cortex"
        elif "alpha" in ctx or "arena" in ctx or "trading" in ctx:
            return "alpha_arena"
        elif "winfield" in ctx or "nowcast" in ctx or "ndbc" in ctx:
            return "winfield"
        return "other"

    def _classify_task(self, rec_type: str, title: str = "") -> str:
        """Map recommendation_type to task_type."""
        type_map = {
            "blocker_resolution": "bug_fix",
            "bug_fix": "bug_fix",
            "goal_progress": "feature",
            "feature": "feature",
            "optimization": "optimization",
            "refactor": "optimization",
            "investigation": "investigation",
            "research": "investigation",
            "validation": "validation",
            "test": "validation",
            "maintenance": "optimization",
        }
        task = type_map.get(rec_type, "")
        if task:
            return task

        # Fallback: keyword matching on title
        title_lower = title.lower()
        if any(w in title_lower for w in ["fix", "bug", "error", "broken"]):
            return "bug_fix"
        elif any(w in title_lower for w in ["add", "implement", "create", "new"]):
            return "feature"
        elif any(w in title_lower for w in ["investigate", "research", "analyze"]):
            return "investigation"
        elif any(w in title_lower for w in ["test", "validate", "verify"]):
            return "validation"
        elif any(w in title_lower for w in ["optimize", "refactor", "clean"]):
            return "optimization"
        return "other"

    def update(
        self,
        state_key: str,
        action: str,
        reward: float,
        next_state_key: Optional[str] = None,
    ):
        """Q-learning update rule."""
        if action not in ACTIONS:
            return

        # Ensure state exists
        if state_key not in self.q_table:
            self.q_table[state_key] = {a: 0.0 for a in ACTIONS}

        old_q = self.q_table[state_key][action]

        # Max Q-value for next state (0 if terminal)
        max_next_q = 0.0
        if next_state_key and next_state_key in self.q_table:
            max_next_q = max(self.q_table[next_state_key].values())

        # Q-learning update: Q(s,a) += α * (r + γ * max Q(s',a') - Q(s,a))
        new_q = old_q + ALPHA * (reward + GAMMA * max_next_q - old_q)
        self.q_table[state_key][action] = round(new_q, 4)
        self.visit_count[state_key] = self.visit_count.get(state_key, 0) + 1

    def recommend(
        self,
        project: str = "other",
        task_type: str = "other",
        priority: str = "B",
        timestamp: Optional[str] = None,
        context: str = "",
    ) -> dict:
        """
        Get routing recommendation for a task.

        Returns:
            {
                "action": "queue_now"|"defer_morning"|"investigate_first"|"skip",
                "confidence": 0.0-1.0,
                "q_values": {action: q_value, ...},
                "state": "project|task_type|time|priority",
                "exploration": bool  # True if action was explored (random)
            }
        """
        # Classify inputs
        if project == "auto":
            project = self._classify_project(context)
        if task_type == "auto":
            task_type = self._classify_task("", context)

        time_slot = self._get_time_slot(timestamp)
        state_key = self._state_key(project, task_type, time_slot, priority)

        q_values = dict(self.q_table[state_key])
        visits = self.visit_count.get(state_key, 0)

        # For unseen states, use prior knowledge
        if visits == 0:
            # Seed with type-based prior
            prior_action = TYPE_TO_ACTION_PRIOR.get(task_type, "queue_now")
            q_values[prior_action] = 0.5  # Mild prior
            best_action = prior_action
            confidence = 0.3
            explored = False
        elif random.random() < EPSILON:
            # Explore
            best_action = random.choice(ACTIONS)
            confidence = 0.2
            explored = True
        else:
            # Exploit
            best_action = max(q_values, key=q_values.get)
            q_range = max(q_values.values()) - min(q_values.values())
            confidence = min(1.0, 0.3 + 0.7 * (q_range / 2.0) * min(visits / 10, 1.0))
            explored = False

        return {
            "action": best_action,
            "confidence": round(confidence, 2),
            "q_values": q_values,
            "state": state_key,
            "visits": visits,
            "exploration": explored,
        }

    def train(self, epochs: int = 5) -> dict:
        """
        Train Q-table from historical outcomes.

        Reads ~/.cortex/outcomes.jsonl and performs multiple passes
        over the data to converge Q-values.

        Returns training summary.
        """
        if not OUTCOMES_FILE.exists():
            return {"error": "No outcomes file found", "trained": 0}

        outcomes = []
        for line in OUTCOMES_FILE.read_text().splitlines():
            if not line.strip():
                continue
            try:
                outcomes.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        if not outcomes:
            return {"error": "No valid outcomes", "trained": 0}

        total_updates = 0
        for epoch in range(epochs):
            # Shuffle for stochastic training
            random.shuffle(outcomes)
            for outcome in outcomes:
                rec_type = outcome.get("recommendation_type", "other")
                title = outcome.get("recommendation_title", "")
                priority = outcome.get("priority", "B")
                result = outcome.get("outcome", "")
                followed = outcome.get("followed", True)
                timestamp = outcome.get("timestamp", "")
                context = outcome.get("context", "") or title

                # Skip invalid entries
                if not result:
                    continue

                # Build state
                task_type = self._classify_task(rec_type, title)
                project = self._classify_project(context)
                time_slot = self._get_time_slot(timestamp)
                state_key = self._state_key(project, task_type, time_slot, priority)

                # Determine what action was taken
                if not followed:
                    # User didn't follow → the recommendation was poor
                    action = TYPE_TO_ACTION_PRIOR.get(task_type, "queue_now")
                    reward = REWARD_MAP.get("not_followed", -0.1)
                else:
                    # User followed → use the prior action mapping
                    action = TYPE_TO_ACTION_PRIOR.get(task_type, "queue_now")
                    reward = REWARD_MAP.get(result, 0.0)

                self.update(state_key, action, reward)
                total_updates += 1

        self.save()

        return {
            "trained": len(outcomes),
            "epochs": epochs,
            "total_updates": total_updates,
            "states_explored": len(self.q_table),
            "total_visits": sum(self.visit_count.values()),
        }

    def score_candidates(self, candidates: list[dict]) -> list[dict]:
        """
        Score a list of batch job candidates.

        Each candidate: {
            "name": str,
            "project": str,
            "task_type": str,
            "priority": str,
            "context": str (optional),
        }

        Returns candidates sorted by Q-value (best first), with
        routing recommendation attached.
        """
        scored = []
        for candidate in candidates:
            rec = self.recommend(
                project=candidate.get("project", "auto"),
                task_type=candidate.get("task_type", "auto"),
                priority=candidate.get("priority", "B"),
                context=candidate.get("context", candidate.get("name", "")),
            )
            scored.append(
                {
                    **candidate,
                    "recommendation": rec,
                    "score": rec["q_values"].get(rec["action"], 0.0),
                }
            )

        # Sort by: queue_now first, then by score descending
        action_priority = {"queue_now": 0, "defer_morning": 1, "investigate_first": 2, "skip": 3}
        scored.sort(
            key=lambda x: (
                action_priority.get(x["recommendation"]["action"], 4),
                -x["score"],
            )
        )
        return scored

    def report(self) -> str:
        """Generate a human-readable Q-table summary."""
        if not self.q_table:
            return "Q-table empty. Run train() first."

        lines = ["Q-Learning Task Router Report", "=" * 40]

        # Group by project
        by_project = defaultdict(list)
        for state_key, q_vals in self.q_table.items():
            parts = state_key.split("|")
            if len(parts) == 4:
                by_project[parts[0]].append((state_key, q_vals))

        for project in sorted(by_project.keys()):
            lines.append(f"\n## {project}")
            for state_key, q_vals in sorted(by_project[project]):
                visits = self.visit_count.get(state_key, 0)
                best = max(q_vals, key=q_vals.get)
                lines.append(f"  {state_key} (visits={visits})")
                lines.append(f"    Best: {best} (Q={q_vals[best]:.3f})")

        lines.append(f"\nTotal states: {len(self.q_table)}")
        lines.append(f"Total visits: {sum(self.visit_count.values())}")
        return "\n".join(lines)


def train_and_report():
    """Convenience function: train from outcomes and print report."""
    router = TaskRouter()
    result = router.train()
    print(json.dumps(result, indent=2))
    print()
    print(router.report())
    return router


def recommend_for_foresight(candidates: list[dict]) -> list[dict]:
    """API for /foresight: score candidates and return sorted recommendations."""
    router = TaskRouter()
    return router.score_candidates(candidates)


if __name__ == "__main__":
    train_and_report()
