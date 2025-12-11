#!/usr/bin/env python3
"""
Week 1 Foundation Calibration - Automated Tracking

Automates Week 1 calibration by:
1. Running converx next daily
2. Detecting action execution via git activity
3. Auto-logging feedback based on patterns
4. Generating progress reports
5. Detecting value points and friction automatically
"""

import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Add paths for imports
script_dir = Path(__file__).parent
dev_root = script_dir.parent
scripts_dir = dev_root / "scripts"
sys.path.insert(0, str(dev_root))
sys.path.insert(0, str(scripts_dir))
sys.path.insert(0, str(script_dir))

try:
    from feedback import FeedbackLogger
    from orchestrator import CortexOrchestrator
    from formatter import CortexFormatter
except ImportError as e:
    print(f"Warning: Could not import Converx modules: {e}", file=sys.stderr)
    FeedbackLogger = None
    CortexOrchestrator = None
    CortexFormatter = None

# Try to import project activity tracking
try:
    from ai_intelligence import ProjectScanner, ProjectActivity
except ImportError:
    ProjectScanner = None
    ProjectActivity = None

try:
    from goal_parser import GoalParser, Goal
except ImportError:
    GoalParser = None
    Goal = None


@dataclass
class DayActivity:
    """Activity for a single day."""
    date: str
    recommendation_id: Optional[str]
    recommendation_title: str
    executed: bool
    execution_evidence: List[str]  # Git commits, file changes, etc.
    useful: Optional[bool] = None
    notes: Optional[str] = None
    value_points: List[str] = None
    friction_points: List[str] = None


class Week1Automation:
    """Automated Week 1 tracking and calibration."""
    
    def __init__(self, root_dir: Path = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
        self.root_dir = root_dir
        self.cortex_dir = root_dir / "cortex"
        
        # Initialize components
        self.feedback_logger = FeedbackLogger() if FeedbackLogger else None
        self.orchestrator = CortexOrchestrator(root_dir) if CortexOrchestrator else None
        self.project_scanner = ProjectScanner(str(root_dir)) if ProjectScanner else None
        self.goal_parser = GoalParser() if GoalParser else None
        
        # Tracking data
        self.week_data_file = self.cortex_dir / "week1_data.json"
        self._load_week_data()
    
    def _load_week_data(self):
        """Load existing week data."""
        if self.week_data_file.exists():
            try:
                with open(self.week_data_file, 'r') as f:
                    data = json.load(f)
                    self.week_data = data
            except (json.JSONDecodeError, IOError):
                self.week_data = {"days": [], "start_date": datetime.now().isoformat()}
        else:
            self.week_data = {"days": [], "start_date": datetime.now().isoformat()}
    
    def _save_week_data(self):
        """Save week data."""
        self.week_data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.week_data_file, 'w') as f:
            json.dump(self.week_data, f, indent=2)
    
    def run_daily(self) -> Dict[str, Any]:
        """Run daily automation: get recommendation and track activity."""
        today = datetime.now().date().isoformat()
        
        print(f"╔══════════════════════════════════════════════════════╗")
        print(f"║     WEEK 1 AUTOMATION - Day {len(self.week_data.get('days', [])) + 1}     ║")
        print(f"╚══════════════════════════════════════════════════════╝")
        print(f"")
        print(f"Date: {today}")
        print(f"")
        
        # 1. Get recommendation
        recommendation = self._get_recommendation()
        
        # 2. Show recommendation
        if recommendation:
            print(f"🎯 RECOMMENDED ACTION")
            print(f"────────────────────")
            print(f"{recommendation.get('title', 'No title')}")
            print(f"")
            print(f"Rationale: {recommendation.get('rationale', 'N/A')}")
            print(f"")
        
        # 3. Check for previous day's execution
        if len(self.week_data.get('days', [])) > 0:
            self._analyze_previous_day()
        
        # 4. Store today's recommendation
        day_activity = DayActivity(
            date=today,
            recommendation_id=recommendation.get('id') if recommendation else None,
            recommendation_title=recommendation.get('title', 'No recommendation') if recommendation else 'No recommendation',
            executed=False,
            execution_evidence=[],
            value_points=[],
            friction_points=[]
        )
        
        self.week_data.setdefault('days', []).append(asdict(day_activity))
        self._save_week_data()
        
        return {
            "date": today,
            "recommendation": recommendation,
            "day_number": len(self.week_data.get('days', []))
        }
    
    def _get_recommendation(self) -> Optional[Dict[str, Any]]:
        """Get today's recommendation from Converx."""
        if not self.orchestrator:
            print("Warning: Orchestrator not available")
            return None
        
        try:
            response = self.orchestrator.get_next_action(limit=1)
            if response.next_action:
                rec = response.next_action
                return {
                    "id": getattr(rec, 'id', None),
                    "title": getattr(rec, 'title', 'Unknown'),
                    "rationale": getattr(rec, 'rationale', ''),
                    "priority": getattr(rec, 'priority', 'medium'),
                    "estimated_effort": getattr(rec, 'estimated_effort', 'Unknown'),
                    "related_projects": getattr(rec, 'related_projects', [])
                }
        except Exception as e:
            print(f"Warning: Could not get recommendation: {e}", file=sys.stderr)
        
        return None
    
    def _analyze_previous_day(self):
        """Analyze previous day's activity to detect execution."""
        if not self.week_data.get('days'):
            return
        
        previous_day = self.week_data['days'][-1]
        prev_date = datetime.fromisoformat(previous_day['date']).date()
        today = datetime.now().date()
        
        # Only analyze if previous day was yesterday
        if (today - prev_date).days != 1:
            return
        
        print(f"📊 ANALYZING YESTERDAY'S ACTIVITY")
        print(f"─────────────────────────────────")
        print(f"")
        
        # Check git activity
        execution_evidence = []
        if self.project_scanner:
            try:
                repos = self.project_scanner.find_git_repos()
                yesterday = prev_date
                
                for repo in repos:
                    # Check commits from yesterday
                    commits = self._get_commits_on_date(repo, yesterday)
                    if commits:
                        execution_evidence.append(f"Git commits in {repo.name}: {len(commits)}")
                        for commit in commits[:3]:  # Show first 3
                            execution_evidence.append(f"  - {commit}")
            except Exception as e:
                print(f"Warning: Could not analyze git activity: {e}", file=sys.stderr)
        
        # Update previous day with evidence
        previous_day['execution_evidence'] = execution_evidence
        previous_day['executed'] = len(execution_evidence) > 0
        
        # Auto-log feedback if executed
        if previous_day['executed'] and self.feedback_logger:
            # Assume useful if executed (user can override)
            useful = True
            notes = f"Auto-detected execution: {len(execution_evidence)} evidence points"
            
            self.feedback_logger.log_feedback(
                action_title=previous_day['recommendation_title'],
                useful=useful,
                action_id=previous_day.get('recommendation_id'),
                notes=notes
            )
            
            print(f"✓ Auto-logged feedback: Executed (assumed useful)")
            print(f"")
        
        self._save_week_data()
    
    def _get_commits_on_date(self, repo_path: Path, date) -> List[str]:
        """Get commit messages from a specific date."""
        try:
            date_str = date.isoformat()
            result = subprocess.run(
                ['git', 'log', '--since', f'{date_str} 00:00:00', '--until', f'{date_str} 23:59:59', '--format=%s'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        except Exception:
            pass
        return []
    
    def generate_report(self) -> str:
        """Generate Week 1 progress report."""
        days = self.week_data.get('days', [])
        
        if not days:
            return "No data yet. Run daily automation first."
        
        report = []
        report.append("╔══════════════════════════════════════════════════════╗")
        report.append("║        WEEK 1 FOUNDATION CALIBRATION REPORT          ║")
        report.append("╚══════════════════════════════════════════════════════╝")
        report.append("")
        
        # Statistics
        total_days = len(days)
        executed_days = sum(1 for d in days if d.get('executed', False))
        execution_rate = (executed_days / total_days * 100) if total_days > 0 else 0
        
        report.append(f"📊 STATISTICS")
        report.append(f"─────────────")
        report.append(f"Days tracked: {total_days}")
        report.append(f"Actions executed: {executed_days}/{total_days} ({execution_rate:.0f}%)")
        report.append(f"")
        
        # Feedback stats
        if self.feedback_logger:
            stats = self.feedback_logger.get_stats()
            report.append(f"📝 FEEDBACK STATISTICS")
            report.append(f"─────────────────────")
            report.append(f"Total entries: {stats['total_entries']}")
            report.append(f"Useful: {stats['useful_count']}")
            report.append(f"Not useful: {stats['not_useful_count']}")
            if stats['total_entries'] > 0:
                report.append(f"Useful rate: {stats['useful_rate']:.1%}")
            report.append(f"")
        
        # Daily breakdown
        report.append(f"📅 DAILY BREAKDOWN")
        report.append(f"─────────────────")
        for i, day in enumerate(days, 1):
            date = day['date']
            title = day['recommendation_title'][:50]
            executed = "✓" if day.get('executed') else "○"
            report.append(f"Day {i} ({date}): {executed} {title}")
        
        report.append(f"")
        report.append(f"✅ SUCCESS CRITERIA CHECK")
        report.append(f"─────────────────────────")
        
        # Check success criteria
        used_daily = total_days >= 7
        actionable_rate = stats['useful_rate'] if self.feedback_logger and stats['total_entries'] > 0 else 0
        actionable_70pct = actionable_rate >= 0.7
        
        report.append(f"[{'✓' if used_daily else '○'}] Used daily for 7 days ({total_days}/7)")
        report.append(f"[{'✓' if actionable_70pct else '○'}] Recommendations actionable 70%+ ({actionable_rate:.0%})")
        report.append(f"[ ] Identified at least 3 value points")
        report.append(f"[ ] Documented at least 2 friction points")
        
        return "\n".join(report)
    
    def auto_detect_value_friction(self):
        """Auto-detect value points and friction from patterns."""
        # This would analyze patterns in:
        # - Git commit frequency
        # - Project activity
        # - Feedback patterns
        # - Goal progress
        
        value_points = []
        friction_points = []
        
        # Check system health
        if self.orchestrator:
            try:
                response = self.orchestrator.get_next_action(limit=0)
                health = response.system_health
                
                if not health.all_active:
                    friction_points.append(f"System health: {health.active_count}/4 integrations active")
                else:
                    value_points.append("All system integrations active")
            except Exception:
                pass
        
        # Check feedback patterns
        if self.feedback_logger:
            stats = self.feedback_logger.get_stats()
            if stats['total_entries'] > 0:
                if stats['useful_rate'] >= 0.7:
                    value_points.append(f"High useful rate: {stats['useful_rate']:.0%}")
                elif stats['useful_rate'] < 0.5:
                    friction_points.append(f"Low useful rate: {stats['useful_rate']:.0%}")
        
        return value_points, friction_points


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Week 1 Foundation Calibration Automation")
    parser.add_argument("--daily", action="store_true", help="Run daily automation")
    parser.add_argument("--report", action="store_true", help="Generate progress report")
    parser.add_argument("--auto-detect", action="store_true", help="Auto-detect value/friction points")
    
    args = parser.parse_args()
    
    automation = Week1Automation()
    
    if args.daily:
        automation.run_daily()
    elif args.report:
        print(automation.generate_report())
    elif args.auto_detect:
        value, friction = automation.auto_detect_value_friction()
        print("Value Points:")
        for v in value:
            print(f"  ✓ {v}")
        print("")
        print("Friction Points:")
        for f in friction:
            print(f"  ⚠ {f}")
    else:
        # Default: run daily
        automation.run_daily()
        print("")
        print("💡 TIP: Run with --report to see progress")
        print("💡 TIP: Run with --auto-detect to find value/friction points")


if __name__ == "__main__":
    main()

