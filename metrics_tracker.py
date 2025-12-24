#!/usr/bin/env python3
"""
Agent 8: Metrics Infrastructure

Tracks 4 key metrics to measure Parallel Convergence effectiveness:
1. Velocity: Development time savings (baseline vs current)
2. Mistakes: Lessons applied vs repeated mistakes
3. Calibration: Prediction accuracy (confidence vs outcome)
4. ROI: Time invested in system vs time saved

All metrics stored in ~/.claude/portfolio/metrics.json
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class MetricsTracker:
    """Track and analyze Cortex performance metrics"""

    def __init__(self, metrics_path: Path = Path.home() / ".claude" / "portfolio" / "metrics.json"):
        self.metrics_path = metrics_path
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load_metrics()

    def _load_metrics(self) -> Dict[str, Any]:
        """Load metrics from disk"""
        if not self.metrics_path.exists():
            return {
                "meta": {
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "version": "1.0"
                },
                "velocity": [],
                "mistakes": [],
                "calibration": [],
                "roi": []
            }

        with open(self.metrics_path, 'r') as f:
            return json.load(f)

    def _save_metrics(self):
        """Save metrics to disk"""
        self.data["meta"]["last_updated"] = datetime.now().isoformat()
        with open(self.metrics_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    # === VELOCITY METRICS ===

    def record_velocity(
        self,
        task: str,
        time_without_cortex: int,  # minutes
        time_with_cortex: int,      # minutes
        project: str,
        notes: str = ""
    ):
        """
        Record development velocity improvement

        Args:
            task: Description of task
            time_without_cortex: Estimated time without Cortex (minutes)
            time_with_cortex: Actual time with Cortex (minutes)
            project: Project name
            notes: Additional context
        """
        savings = time_without_cortex - time_with_cortex
        improvement_pct = (savings / time_without_cortex * 100) if time_without_cortex > 0 else 0

        self.data["velocity"].append({
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "project": project,
            "baseline_minutes": time_without_cortex,
            "actual_minutes": time_with_cortex,
            "savings_minutes": savings,
            "improvement_pct": round(improvement_pct, 1),
            "notes": notes
        })

        self._save_metrics()
        return savings

    def get_velocity_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get velocity statistics for last N days"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [
            v for v in self.data["velocity"]
            if datetime.fromisoformat(v["timestamp"]) > cutoff
        ]

        if not recent:
            return {
                "total_tasks": 0,
                "total_savings_minutes": 0,
                "total_savings_hours": 0,
                "avg_improvement_pct": 0,
                "by_project": {}
            }

        total_savings = sum(v["savings_minutes"] for v in recent)
        avg_improvement = sum(v["improvement_pct"] for v in recent) / len(recent)

        # By project
        by_project = defaultdict(lambda: {"tasks": 0, "savings": 0})
        for v in recent:
            by_project[v["project"]]["tasks"] += 1
            by_project[v["project"]]["savings"] += v["savings_minutes"]

        return {
            "total_tasks": len(recent),
            "total_savings_minutes": total_savings,
            "total_savings_hours": round(total_savings / 60, 1),
            "avg_improvement_pct": round(avg_improvement, 1),
            "by_project": dict(by_project)
        }

    # === MISTAKE METRICS ===

    def record_mistake(
        self,
        mistake_type: str,
        was_prevented: bool,
        lesson_id: Optional[str] = None,
        project: str = "",
        impact_minutes: int = 0,
        notes: str = ""
    ):
        """
        Record a mistake (prevented or not)

        Args:
            mistake_type: Category (e.g., 'data_validation', 'api_integration')
            was_prevented: True if Cortex helped prevent it
            lesson_id: Reference to lesson in lessons.json
            project: Project name
            impact_minutes: Time cost if not prevented
            notes: Additional context
        """
        self.data["mistakes"].append({
            "timestamp": datetime.now().isoformat(),
            "mistake_type": mistake_type,
            "was_prevented": was_prevented,
            "lesson_id": lesson_id,
            "project": project,
            "impact_minutes": impact_minutes,
            "notes": notes
        })

        self._save_metrics()

    def get_mistake_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get mistake prevention statistics"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [
            m for m in self.data["mistakes"]
            if datetime.fromisoformat(m["timestamp"]) > cutoff
        ]

        if not recent:
            return {
                "total_mistakes": 0,
                "prevented": 0,
                "repeated": 0,
                "prevention_rate": 0,
                "time_saved_minutes": 0
            }

        prevented = sum(1 for m in recent if m["was_prevented"])
        repeated = len(recent) - prevented
        prevention_rate = (prevented / len(recent) * 100) if recent else 0
        time_saved = sum(m["impact_minutes"] for m in recent if m["was_prevented"])

        return {
            "total_mistakes": len(recent),
            "prevented": prevented,
            "repeated": repeated,
            "prevention_rate": round(prevention_rate, 1),
            "time_saved_minutes": time_saved,
            "time_saved_hours": round(time_saved / 60, 1)
        }

    # === CALIBRATION METRICS ===

    def record_prediction(
        self,
        prediction_id: str,
        task: str,
        predicted_outcome: str,
        confidence: float,  # 0.0 to 1.0
        predicted_time: int,  # minutes
        project: str = "",
        notes: str = ""
    ) -> str:
        """
        Record a prediction for later validation

        Returns:
            prediction_id for later outcome recording
        """
        self.data["calibration"].append({
            "id": prediction_id,
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "predicted_outcome": predicted_outcome,
            "confidence": confidence,
            "predicted_time_minutes": predicted_time,
            "project": project,
            "notes": notes,
            "outcome_recorded": False,
            "actual_outcome": None,
            "actual_time_minutes": None,
            "was_correct": None,
            "outcome_timestamp": None
        })

        self._save_metrics()
        return prediction_id

    def record_outcome(
        self,
        prediction_id: str,
        actual_outcome: str,
        actual_time: int  # minutes
    ):
        """Record actual outcome for a prediction"""
        for calibration in self.data["calibration"]:
            if calibration["id"] == prediction_id:
                calibration["outcome_recorded"] = True
                calibration["actual_outcome"] = actual_outcome
                calibration["actual_time_minutes"] = actual_time
                calibration["was_correct"] = (calibration["predicted_outcome"] == actual_outcome)
                calibration["outcome_timestamp"] = datetime.now().isoformat()
                self._save_metrics()
                return True

        return False

    def get_calibration_stats(self) -> Dict[str, Any]:
        """Get calibration curve statistics"""
        predictions = [
            c for c in self.data["calibration"]
            if c["outcome_recorded"]
        ]

        if not predictions:
            return {
                "total_predictions": 0,
                "accuracy": 0,
                "avg_confidence": 0,
                "calibration_error": 0,
                "by_confidence_bucket": {}
            }

        # Overall accuracy
        correct = sum(1 for p in predictions if p["was_correct"])
        accuracy = correct / len(predictions)

        # Average confidence
        avg_confidence = sum(p["confidence"] for p in predictions) / len(predictions)

        # Calibration error (difference between confidence and accuracy)
        calibration_error = abs(avg_confidence - accuracy)

        # By confidence bucket (0-0.2, 0.2-0.4, etc.)
        buckets = defaultdict(lambda: {"total": 0, "correct": 0})
        for p in predictions:
            bucket = int(p["confidence"] * 5) / 5  # Round to nearest 0.2
            buckets[bucket]["total"] += 1
            if p["was_correct"]:
                buckets[bucket]["correct"] += 1

        bucket_stats = {}
        for bucket, data in buckets.items():
            bucket_stats[f"{bucket:.1f}-{bucket+0.2:.1f}"] = {
                "predictions": data["total"],
                "accuracy": round(data["correct"] / data["total"], 2)
            }

        return {
            "total_predictions": len(predictions),
            "accuracy": round(accuracy, 3),
            "avg_confidence": round(avg_confidence, 3),
            "calibration_error": round(calibration_error, 3),
            "by_confidence_bucket": bucket_stats
        }

    def get_pending_predictions(self) -> List[Dict]:
        """Get predictions awaiting outcomes"""
        return [
            p for p in self.data.get("calibration", [])
            if not p.get("outcome_recorded", False)
        ]

    def get_calibration_data(self) -> Dict[str, Any]:
        """Get raw calibration data for analysis"""
        predictions = self.data.get("calibration", [])
        outcomes_dict = {
            p["id"]: p for p in predictions
            if p.get("outcome_recorded")
        }
        return {
            "predictions": predictions,
            "outcomes": outcomes_dict,
            "pending_count": len(predictions) - len(outcomes_dict)
        }

    def get_time_estimation_stats(self) -> Dict[str, float]:
        """Analyze time estimation accuracy"""
        completed = [
            p for p in self.data.get("calibration", [])
            if p.get("outcome_recorded")
        ]

        if not completed:
            return {"count": 0}

        errors = []
        for p in completed:
            predicted = p["predicted_time_minutes"]
            actual = p["actual_time_minutes"]
            if predicted and predicted > 0:
                error_pct = abs(actual - predicted) / predicted * 100
                errors.append(error_pct)

        underestimates = sum(
            1 for p in completed
            if p["actual_time_minutes"] > p["predicted_time_minutes"]
        )
        overestimates = sum(
            1 for p in completed
            if p["actual_time_minutes"] < p["predicted_time_minutes"]
        )

        return {
            "count": len(errors),
            "mean_error_pct": sum(errors) / len(errors) if errors else 0,
            "underestimates": underestimates,
            "overestimates": overestimates
        }

    # === ROI METRICS ===

    def record_investment(
        self,
        activity: str,
        time_minutes: int,
        category: str,  # 'setup', 'maintenance', 'learning', 'documentation'
        notes: str = ""
    ):
        """Record time invested in Cortex system"""
        # Find or create ROI tracker
        if not self.data.get("roi"):
            self.data["roi"] = []

        self.data["roi"].append({
            "timestamp": datetime.now().isoformat(),
            "type": "investment",
            "activity": activity,
            "time_minutes": time_minutes,
            "category": category,
            "notes": notes
        })

        self._save_metrics()

    def record_benefit(
        self,
        source: str,  # 'velocity', 'mistake_prevention', 'faster_decision'
        time_saved_minutes: int,
        notes: str = ""
    ):
        """Record time saved from using Cortex"""
        if not self.data.get("roi"):
            self.data["roi"] = []

        self.data["roi"].append({
            "timestamp": datetime.now().isoformat(),
            "type": "benefit",
            "source": source,
            "time_saved_minutes": time_saved_minutes,
            "notes": notes
        })

        self._save_metrics()

    def get_roi_stats(self) -> Dict[str, Any]:
        """Calculate ROI: (time saved / time invested)"""
        if not self.data.get("roi"):
            return {
                "total_investment_minutes": 0,
                "total_benefit_minutes": 0,
                "roi_ratio": 0,
                "roi_percentage": 0,
                "break_even": False
            }

        investments = [r for r in self.data["roi"] if r["type"] == "investment"]
        benefits = [r for r in self.data["roi"] if r["type"] == "benefit"]

        total_investment = sum(i["time_minutes"] for i in investments)
        total_benefit = sum(b["time_saved_minutes"] for b in benefits)

        roi_ratio = (total_benefit / total_investment) if total_investment > 0 else 0
        roi_percentage = ((total_benefit - total_investment) / total_investment * 100) if total_investment > 0 else 0

        return {
            "total_investment_minutes": total_investment,
            "total_investment_hours": round(total_investment / 60, 1),
            "total_benefit_minutes": total_benefit,
            "total_benefit_hours": round(total_benefit / 60, 1),
            "net_savings_minutes": total_benefit - total_investment,
            "net_savings_hours": round((total_benefit - total_investment) / 60, 1),
            "roi_ratio": round(roi_ratio, 2),
            "roi_percentage": round(roi_percentage, 1),
            "break_even": total_benefit >= total_investment
        }

    # === DASHBOARD ===

    def get_dashboard(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive metrics dashboard"""
        return {
            "period_days": days,
            "velocity": self.get_velocity_stats(days),
            "mistakes": self.get_mistake_stats(days),
            "calibration": self.get_calibration_stats(),
            "roi": self.get_roi_stats()
        }


def main():
    """Demo metrics tracking"""
    tracker = MetricsTracker()

    print("="*60)
    print("AGENT 8: METRICS INFRASTRUCTURE")
    print("="*60)

    # Record initial investment in Cortex setup
    print("\n📊 Recording initial setup investment...")
    tracker.record_investment(
        activity="Week 1 implementation (Agents 1-5)",
        time_minutes=40,
        category="setup",
        notes="Core modules: Portfolio, Session, Specs, Bridge, Migration"
    )
    print("  ✅ Recorded 40 minutes setup investment")

    # Record a sample velocity improvement
    print("\n⚡ Recording sample velocity improvement...")
    tracker.record_velocity(
        task="Find similar GRIB processing code",
        time_without_cortex=30,  # Would take 30 min without Cortex
        time_with_cortex=5,       # Took 5 min with spec search
        project="VortexV2",
        notes="Used spec knowledge base to find existing implementation"
    )
    print("  ✅ Recorded 25 minutes saved (83% improvement)")

    # Record a prevented mistake
    print("\n🛡️ Recording prevented mistake...")
    tracker.record_mistake(
        mistake_type="data_validation",
        was_prevented=True,
        lesson_id="grib_index_check",
        project="VortexV2",
        impact_minutes=240,  # Would have wasted 4 hours
        notes="Remembered lesson: check GRIB index before download"
    )
    print("  ✅ Recorded prevented mistake (4 hours saved)")

    # Record a prediction
    print("\n🎯 Recording sample prediction...")
    prediction_id = tracker.record_prediction(
        prediction_id="pred_001",
        task="Implement Alpha Arena integration",
        predicted_outcome="success",
        confidence=0.85,
        predicted_time=15,
        project="Cortex",
        notes="Based on similar VortexV2 integration pattern"
    )
    print(f"  ✅ Recorded prediction {prediction_id} (85% confidence, 15 min estimate)")

    # Get dashboard
    print("\n" + "="*60)
    print("METRICS DASHBOARD")
    print("="*60)

    dashboard = tracker.get_dashboard()

    print("\n⚡ VELOCITY:")
    print(f"  Tasks completed: {dashboard['velocity']['total_tasks']}")
    print(f"  Time saved: {dashboard['velocity']['total_savings_hours']} hours")
    print(f"  Avg improvement: {dashboard['velocity']['avg_improvement_pct']}%")

    print("\n🛡️ MISTAKE PREVENTION:")
    print(f"  Total mistakes: {dashboard['mistakes']['total_mistakes']}")
    print(f"  Prevented: {dashboard['mistakes']['prevented']}")
    print(f"  Prevention rate: {dashboard['mistakes']['prevention_rate']}%")
    print(f"  Time saved: {dashboard['mistakes']['time_saved_hours']} hours")

    print("\n🎯 CALIBRATION:")
    print(f"  Predictions: {dashboard['calibration']['total_predictions']}")
    print(f"  Accuracy: {dashboard['calibration']['accuracy']}")
    print(f"  Avg confidence: {dashboard['calibration']['avg_confidence']}")

    print("\n💰 ROI:")
    print(f"  Investment: {dashboard['roi']['total_investment_hours']} hours")
    print(f"  Benefits: {dashboard['roi']['total_benefit_hours']} hours")
    print(f"  Net savings: {dashboard['roi']['net_savings_hours']} hours")
    print(f"  ROI ratio: {dashboard['roi']['roi_ratio']}x")
    print(f"  Break-even: {dashboard['roi']['break_even']}")

    print("\n" + "="*60)
    print("METRICS TRACKING OPERATIONAL ✅")
    print("="*60)
    print(f"\nMetrics stored: {tracker.metrics_path}")
    print("\nUse this tracker to measure Cortex effectiveness over time!")


if __name__ == '__main__':
    main()
