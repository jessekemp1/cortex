#!/usr/bin/env python3
"""
Cortex MVP CLI

Command-line interface for the Cortex Intelligence Platform.

Commands:
- scan: Detect signals across the monorepo
- contract: Generate contract for a signal
- health: Show system health metrics
- list: List recent signals and contracts
- approve: Approve and queue a contract for execution

This is the primary interface for interacting with the system.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from batch.orchestrator import BatchOrchestrator
from health.monitor import HealthMonitor
from intelligence.contracts import ContractGenerator, TaskContract
from intelligence.executor import ContractExecutor
from intelligence.risk import RiskClassifier
from intelligence.signals import Signal, SignalDetector, SignalType


class CortexCLI:
    """Main CLI controller."""

    def __init__(self):
        self.signal_detector = SignalDetector()
        self.contract_generator = ContractGenerator()
        self.risk_classifier = RiskClassifier()
        self.executor = ContractExecutor()
        self.health_monitor = HealthMonitor()
        self.batch_orchestrator = BatchOrchestrator()
        self.cache_dir = Path.home() / ".cortex"

    def cmd_scan(self, args):
        """Scan for signals."""
        print("🔍 Scanning for signals...\n")

        signals = self.signal_detector.detect_all()

        if not signals:
            print("No signals detected.")
            return

        # Group by severity
        by_severity = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
        }

        for signal in signals:
            by_severity[signal.severity].append(signal)

        # Print grouped signals
        print(f"Found {len(signals)} signals:\n")

        for severity in ["critical", "high", "medium", "low"]:
            signals_in_severity = by_severity[severity]
            if not signals_in_severity:
                continue

            icon = {"critical": "🚨", "high": "⚠️", "medium": "💡", "low": "ℹ️"}[severity]
            print(f"{icon} {severity.upper()} ({len(signals_in_severity)})")
            print("─" * 80)

            for signal in signals_in_severity:
                print(f"  [{signal.type.value}] {signal.title}")
                print(f"  Impact: {signal.estimated_impact}")
                print(f"  ID: {signal.id}")
                print()

        # Save summary
        summary_file = self.cache_dir / "latest_scan.json"
        summary_data = {
            "scanned_at": datetime.now().isoformat(),
            "count": len(signals),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "signals": [s.to_dict() for s in signals],
        }
        summary_file.write_text(json.dumps(summary_data, indent=2))

        print(f"💾 Saved to: {summary_file}")
        print("\n💡 Next: Generate contract for a signal: cortex contract <signal_id>")

    async def cmd_contract(self, args):
        """Generate contract for a signal."""
        signal_id = args.signal_id

        # Load latest signals
        summary_file = self.cache_dir / "latest_scan.json"
        if not summary_file.exists():
            print("❌ No scan results found. Run 'cortex scan' first.")
            return

        data = json.loads(summary_file.read_text())
        signals_data = data.get("signals", [])

        # Find matching signal
        signal_dict = None
        for s in signals_data:
            if s["id"] == signal_id:
                signal_dict = s
                break

        if not signal_dict:
            print(f"❌ Signal not found: {signal_id}")
            print("\nAvailable signals:")
            for s in signals_data[:5]:
                print(f"  - {s['id']}: {s['title']}")
            return

        # Reconstruct Signal object
        signal = Signal(
            id=signal_dict["id"],
            type=SignalType(signal_dict["type"]),
            severity=signal_dict["severity"],
            title=signal_dict["title"],
            description=signal_dict["description"],
            context=signal_dict["context"],
            evidence=signal_dict["evidence"],
            estimated_impact=signal_dict["estimated_impact"],
            detected_at=datetime.fromisoformat(signal_dict["detected_at"]),
        )

        print(f"📋 Generating contract for: {signal.title}\n")
        print("⏳ This may take 30-60 seconds (using Opus 4.5)...\n")

        # Generate contract
        try:
            contract = await self.contract_generator.generate_contract(signal)

            print("✅ Contract generated!\n")
            print("=" * 80)
            print("TASK CONTRACT")
            print("=" * 80)
            print(f"Contract ID: {contract.contract_id}")
            print(f"Risk Level: {contract.risk_level}")
            print(f"Auto-executable: {contract.auto_executable}")
            print()

            print("REQUIREMENTS:")
            for i, req in enumerate(contract.requirements, 1):
                print(f"  {i}. {req}")
            print()

            print("CONSTRAINTS:")
            for constraint in contract.constraints:
                print(f"  - {constraint}")
            print()

            print("SUCCESS CRITERIA:")
            tests = contract.success_criteria.get("tests", [])
            if tests:
                print("  Tests:")
                for test in tests:
                    print(f"    - {test}")

            metrics = contract.success_criteria.get("metrics", {})
            if metrics:
                print("  Metrics:")
                for metric, threshold in metrics.items():
                    print(f"    - {metric}: {threshold}")
            print()

            print("HUMAN GATES:")
            for gate in contract.human_gates:
                print(f"  - {gate}")
            print()

            print("BUDGET:")
            print(f"  Max attempts: {contract.max_attempts}")
            print(f"  Max cost: ${contract.max_cost_usd:.2f}")
            print()

            # Classify risk
            assessment = self.risk_classifier.classify(contract)
            print("RISK ASSESSMENT:")
            print(f"  {assessment.rationale}")
            if assessment.concerns:
                print("  Concerns:")
                for concern in assessment.concerns:
                    print(f"    - {concern}")
            print()

            print("=" * 80)

            # Ask for approval
            if contract.auto_executable and assessment.auto_executable:
                print("\n✨ This contract can AUTO-EXECUTE (low/medium risk)")
                response = input("Approve and start execution? (y/n): ")
            else:
                print("\n⚠️ This contract requires MANUAL APPROVAL (high risk)")
                response = input("Approve and queue for execution? (y/n): ")

            if response.lower() == "y":
                self._execute_contract(contract, assessment)
            else:
                print("\n📋 Contract saved but not queued.")
                print(f"Contract ID: {contract.contract_id}")
                print("To approve later: cortex approve <contract_id>")

        except Exception as e:
            print(f"❌ Error generating contract: {e}")
            import traceback

            traceback.print_exc()

    def cmd_health(self, args):
        """Show system health."""
        print("🏥 System Health Check\n")

        metrics, alerts = self.health_monitor.health_status()

        # Print metrics
        print("=" * 80)
        print("METRICS")
        print("=" * 80)

        # Queue depth
        status = "✅" if 3 <= metrics.queue_depth <= 8 else "⚠️"
        print(f"{status} Queue Depth: {metrics.queue_depth} (optimal: 3-8)")

        # Success rate
        status = "✅" if metrics.success_rate >= 0.85 else "⚠️"
        print(f"{status} Success Rate: {metrics.success_rate:.1%} (optimal: >85%)")

        # Cycle time
        status = "✅" if metrics.avg_cycle_time_hours <= 4.0 else "⚠️"
        print(f"{status} Avg Cycle Time: {metrics.avg_cycle_time_hours:.1f}h (optimal: <4h)")

        # Blocked tasks
        status = "✅" if metrics.blocked_tasks == 0 else "⚠️"
        print(f"{status} Blocked Tasks: {metrics.blocked_tasks} (optimal: 0)")

        # Cost
        threshold = self.health_monitor.OPTIMAL_THRESHOLDS["cost_per_day_max_usd"]
        status = "✅" if metrics.cost_per_day_usd <= threshold else "⚠️"
        print(f"{status} Cost/Day: ${metrics.cost_per_day_usd:.2f} (optimal: <${threshold:.0f})")
        print()

        print(f"Active Executors: {metrics.active_executors}")
        print(f"Completed (24h): {metrics.tasks_completed_24h}")
        print(f"Failed (24h): {metrics.tasks_failed_24h}")
        print()

        # Print alerts
        print("=" * 80)
        print("ALERTS")
        print("=" * 80)

        if not alerts:
            print("✅ No alerts - system healthy")
        else:
            for alert in alerts:
                icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}[alert.severity]
                print(f"{icon} [{alert.severity.upper()}] {alert.message}")
                print(f"   Action: {alert.action}")
                print()

    def cmd_list(self, args):
        """List signals and contracts."""
        list_type = args.type or "all"

        if list_type in ["signals", "all"]:
            print("📋 Recent Signals\n")
            summary_file = self.cache_dir / "latest_scan.json"

            if summary_file.exists():
                data = json.loads(summary_file.read_text())
                signals = data.get("signals", [])[:10]

                for signal in signals:
                    severity_icon = {"critical": "🚨", "high": "⚠️", "medium": "💡", "low": "ℹ️"}[
                        signal["severity"]
                    ]
                    print(f"{severity_icon} {signal['title']}")
                    print(f"   ID: {signal['id']} | Type: {signal['type']}")
                    print()
            else:
                print("No signals found. Run 'cortex scan' first.\n")

        if list_type in ["contracts", "all"]:
            print("📝 Recent Contracts\n")
            contracts_dir = self.cache_dir / "contracts"

            if contracts_dir.exists():
                contract_files = sorted(contracts_dir.glob("*.json"), reverse=True)[:10]

                for contract_file in contract_files:
                    try:
                        contract_data = json.loads(contract_file.read_text())
                        print(f"📄 {contract_data['title']}")
                        print(f"   ID: {contract_data['contract_id']}")
                        print(
                            f"   Risk: {contract_data['risk_level']} | Auto-exec: {contract_data['auto_executable']}"
                        )
                        print()
                    except (json.JSONDecodeError, KeyError):
                        continue
            else:
                print("No contracts found.\n")

    async def cmd_execute(self, args):
        """Execute a contract directly (not via batch queue)."""
        contract_id = args.contract_id

        # Load contract
        contracts_dir = self.cache_dir / "contracts"
        contract_file = contracts_dir / f"{contract_id}.json"

        if not contract_file.exists():
            print(f"❌ Contract not found: {contract_id}")
            print(f"Looking in: {contract_file}")
            return

        try:
            # Load contract data
            contract_data = json.loads(contract_file.read_text())

            # Reconstruct TaskContract
            contract = TaskContract(
                contract_id=contract_data["contract_id"],
                signal_id=contract_data["signal_id"],
                title=contract_data["title"],
                description=contract_data["description"],
                requirements=contract_data["requirements"],
                constraints=contract_data["constraints"],
                success_criteria=contract_data["success_criteria"],
                dependencies=contract_data["dependencies"],
                human_gates=contract_data["human_gates"],
                risk_level=contract_data["risk_level"],
                auto_executable=contract_data["auto_executable"],
                max_attempts=contract_data.get("max_attempts", 3),
                max_cost_usd=contract_data.get("max_cost_usd", 5.0),
                escalate_conditions=contract_data.get("escalate_conditions", []),
                relevant_files=contract_data.get("relevant_files", []),
                relevant_docs=contract_data.get("relevant_docs", []),
                similar_past_work=contract_data.get("similar_past_work", []),
                created_at=datetime.fromisoformat(contract_data["created_at"]),
            )

            print(f"📋 Loaded contract: {contract.title}")
            print(f"Risk: {contract.risk_level} | Auto-exec: {contract.auto_executable}\n")

            # Dry run first
            if not args.no_dry_run:
                print("=== DRY RUN ===")
                dry_result = await self.executor.execute_contract(contract, dry_run=True)
                print(f"Would execute {dry_result.steps_total} steps\n")

                # Show steps
                response = input("Proceed with execution? (y/n): ")
                if response.lower() != "y":
                    print("❌ Execution cancelled")
                    return

            # Execute contract
            print("\n=== EXECUTING ===\n")
            result = await self.executor.execute_contract(contract, dry_run=False)

            # Display results
            print(f"\n{'='*80}")
            print("EXECUTION RESULT")
            print(f"{'='*80}")
            print(f"Status: {result.status.value}")
            print(f"Success: {'✅' if result.success else '❌'}")
            print(f"Steps: {result.steps_completed}/{result.steps_total}")
            print(f"Time: {result.execution_time_seconds:.1f}s")
            print()

            print("VERIFICATION:")
            print(f"  Tests: {'✅ Passed' if result.tests_passed else '❌ Failed'}")
            print(f"  Metrics: {'✅ Met' if result.metrics_met else '❌ Not Met'}")
            print(
                f"  Benchmarks: {'✅ Met' if result.benchmarks_met else '⚠️ Manual Check Required'}"
            )
            print()

            if result.error_message:
                print(f"Error: {result.error_message}\n")

            if result.test_output:
                print("Test Output (first 500 chars):")
                print("-" * 80)
                print(result.test_output[:500])
                print()

            # Update health monitor
            print("💾 Result saved to: ~/.cortex/execution_results/")
            print("📊 View health: cortex health")

        except Exception as e:
            print(f"❌ Error executing contract: {e}")
            import traceback

            traceback.print_exc()

    def _execute_contract(self, contract: TaskContract, assessment):
        """Queue contract for execution."""
        print("\n⚙️ Queuing contract for execution...")

        # Convert contract to batch job
        job_data = {
            "id": contract.contract_id,
            "description": contract.title,
            "priority": "high" if contract.risk_level == "high" else "normal",
            "tasks": [
                {
                    "task_id": f"{contract.contract_id}_main",
                    "title": contract.title,
                    "prompt": self._build_execution_prompt(contract),
                    "context": json.dumps(contract.context if hasattr(contract, "context") else {}),
                    "files_affected": contract.relevant_files,
                    "estimated_tokens": 5000,
                }
            ],
            "estimated_total_tokens": 5000,
            "source": "intelligence",
            "project": contract.context.get("project") if hasattr(contract, "context") else None,
        }

        try:
            job_id = self.batch_orchestrator.submit_job(job_data, auto_detect=True)
            print(f"✅ Contract queued! Job ID: {job_id}")
            print("\n📊 Check status: cortex health")
            print("📋 View jobs: python cortex/batch/orchestrator.py list")
        except Exception as e:
            print(f"❌ Error queuing contract: {e}")

    def _build_execution_prompt(self, contract: TaskContract) -> str:
        """Build execution prompt from contract."""
        prompt = f"""Execute this task according to the contract:

TITLE: {contract.title}

DESCRIPTION: {contract.description}

REQUIREMENTS:
{chr(10).join(f'{i}. {req}' for i, req in enumerate(contract.requirements, 1))}

CONSTRAINTS:
{chr(10).join(f'- {c}' for c in contract.constraints)}

SUCCESS CRITERIA:
Tests: {contract.success_criteria.get('tests', [])}
Metrics: {contract.success_criteria.get('metrics', {})}

Implement the requirements, respecting all constraints, and verify against success criteria."""

        return prompt


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cortex Intelligence Platform - MVP CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # scan command
    subparsers.add_parser("scan", help="Detect signals across monorepo")

    # contract command
    parser_contract = subparsers.add_parser("contract", help="Generate contract for signal")
    parser_contract.add_argument("signal_id", help="Signal ID from scan results")

    # health command
    subparsers.add_parser("health", help="Show system health metrics")

    # list command
    parser_list = subparsers.add_parser("list", help="List signals and contracts")
    parser_list.add_argument(
        "--type", choices=["signals", "contracts", "all"], default="all", help="What to list"
    )

    # execute command
    parser_execute = subparsers.add_parser("execute", help="Execute a contract directly")
    parser_execute.add_argument("contract_id", help="Contract ID to execute")
    parser_execute.add_argument(
        "--no-dry-run", action="store_true", help="Skip dry run and execute immediately"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli = CortexCLI()

    if args.command == "scan":
        cli.cmd_scan(args)
    elif args.command == "contract":
        asyncio.run(cli.cmd_contract(args))
    elif args.command == "health":
        cli.cmd_health(args)
    elif args.command == "list":
        cli.cmd_list(args)
    elif args.command == "execute":
        asyncio.run(cli.cmd_execute(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
