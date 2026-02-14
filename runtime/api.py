"""FastAPI server for runtime event triggers and monitoring.

Provides REST API endpoints for:
- Health checks
- Agent status and metrics
- Manual agent triggering
- Webhook handling
- Execution history
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

import structlog
from cortex.intelligence.counterfactual_learning import CounterfactualLedger
from cortex.intelligence.decision_twin import DecisionTwinEngine, PlanScenario, PlanTask
from cortex.intelligence.memory_distiller import MemoryDistiller
from cortex.intelligence.portfolio_allocator import PortfolioAllocator, ProjectSignal
from cortex.intelligence.pre_mortem import Initiative, PreMortemEngine
from cortex.intelligence.trust_governor import TrustGovernor
from cortex.runtime.models import WebhookEvent
from cortex.runtime.storage.metrics import MetricsCollector
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    from cortex.runtime.executor import RuntimeExecutor

logger = structlog.get_logger()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


def create_api_app(executor: "RuntimeExecutor") -> FastAPI:
    """Create FastAPI app with executor integration.

    Args:
        executor: The RuntimeExecutor instance

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Cortex Runtime API",
        version="2.0.0",
        description="Agent execution and monitoring API",
    )

    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    webhook_handlers: Dict[str, str] = {}  # webhook_path -> agent_id

    # ==================== Health & Status ====================

    @app.get("/api/v1/runtime/health")
    @limiter.limit("120/minute")
    async def health(request: Request):
        """
        Comprehensive health check endpoint.

        Checks:
        - Runtime service status
        - Supervisor health (if available)
        - Task queue status
        - Detected issues with auto-healing status
        """
        health_status = {
            "status": "healthy",
            "service": "cortex-runtime",
            "timestamp": (
                getattr(executor.history, "metrics", {}).get("last_run_timestamp", None)
                if hasattr(executor.history, "metrics")
                else None
            ),
        }

        # Try to integrate with supervisor health monitoring
        try:
            from intelligence.process_monitor.batch_queue import BatchTaskQueue
            from supervisor import CortexSupervisor, HealthMonitor

            # Create health monitor instance
            shell_queue = BatchTaskQueue()
            health_monitor = HealthMonitor(shell_queue=shell_queue)

            # Run health check
            issues = health_monitor.check()

            # Add health monitoring results
            health_status["health_monitor"] = {
                "enabled": True,
                "issues_detected": len(issues),
                "issues": [
                    {
                        "type": issue.issue_type,
                        "target": (
                            issue.target_id[:8] if len(issue.target_id) > 8 else issue.target_id
                        ),
                        "severity": issue.severity,
                        "description": issue.description,
                        "auto_healable": issue.auto_healable,
                    }
                    for issue in issues
                ],
            }

            # Check if there are critical issues
            critical_issues = [i for i in issues if i.severity == "critical"]
            if critical_issues:
                health_status["status"] = "degraded"
                health_status["critical_issues"] = len(critical_issues)
            elif issues:
                health_status["status"] = "healthy_with_warnings"
                health_status["warnings"] = len(issues)

            # Add queue stats
            try:
                queue_stats = shell_queue.get_queue_stats()
                health_status["queue"] = queue_stats
            except Exception:
                pass

        except ImportError:
            # Supervisor not available - basic health only
            health_status["health_monitor"] = {
                "enabled": False,
                "reason": "supervisor module not available",
            }
        except Exception as e:
            # Health check failed but runtime is still up
            health_status["health_monitor"] = {
                "enabled": True,
                "error": str(e),
                "status": "check_failed",
            }
            logger.warning(f"Health monitoring check failed: {e}")

        return health_status

    # Backward compatibility alias
    @app.get("/api/v1/health", deprecated=True)
    async def health_legacy():
        """Health check endpoint (legacy path)."""
        # Return simplified health for backward compatibility
        full_health = await health()
        return {"status": full_health.get("status", "healthy"), "service": "cortex-runtime"}

    # ==================== Metrics ====================

    @app.get("/api/v1/runtime/metrics")
    @limiter.limit("60/minute")
    async def get_metrics(request: Request):
        """Get system-wide metrics."""
        metrics_collector = MetricsCollector(executor.history)
        return {
            "system": metrics_collector.get_system_metrics(),
            "agents": metrics_collector.get_agent_list_metrics(),
        }

    @app.get("/api/v1/runtime/metrics/{agent_id}")
    async def get_agent_metrics(agent_id: str):
        """Get metrics for a specific agent."""
        if agent_id not in executor.agents:
            raise HTTPException(status_code=404, detail="Agent not found")

        metrics_collector = MetricsCollector(executor.history)
        return metrics_collector.get_agent_metrics(agent_id)

    @app.get("/api/v1/runtime/co-navigator/status")
    @limiter.limit("30/minute")
    async def co_navigator_status(request: Request):
        """Get co-navigator status snapshot and key decision signals."""
        twin = DecisionTwinEngine()
        scenarios = [
            PlanScenario(
                scenario_id="balanced",
                name="Balanced Build",
                tasks=(
                    PlanTask("Ship routing integration", 9, 7, 3, 1),
                    PlanTask("Harden tests", 6, 4, 2, 1),
                ),
            ),
            PlanScenario(
                scenario_id="aggressive",
                name="Aggressive Expansion",
                tasks=(PlanTask("Ship 3 new modules", 12, 12, 8, 3),),
            ),
        ]
        ranked = twin.rank_scenarios(scenarios)

        allocator = PortfolioAllocator()
        allocations = allocator.allocate(
            [
                ProjectSignal("vortex", 0.8, 0.9, 0.95),
                ProjectSignal("cortex", 0.6, 0.85, 0.9),
                ProjectSignal("alpha_arena", 0.5, 0.7, 0.75),
                ProjectSignal("winfield", 0.45, 0.65, 0.7),
            ],
            total_hours=40.0,
        )

        ledger_summary = CounterfactualLedger().summarize()
        trust = TrustGovernor().evaluate(current_level=1)
        premortem_engine = PreMortemEngine()
        premortem = premortem_engine.generate(
            [
                Initiative(
                    name="co-navigator rollout",
                    complexity=0.75,
                    dependency_risk=0.7,
                    deadline_pressure=0.65,
                )
            ]
        )
        distilled = MemoryDistiller().distill()

        return {
            "status": "active",
            "decision_twin": {
                "best": ranked[0].__dict__ if ranked else None,
                "ranked_count": len(ranked),
            },
            "portfolio_allocator": {
                "top_project": allocations[0].__dict__ if allocations else None,
                "count": len(allocations),
            },
            "counterfactual": ledger_summary,
            "trust_governor": trust,
            "premortem": [entry.__dict__ for entry in premortem],
            "memory_distiller": distilled,
        }

    # ==================== Agents ====================

    @app.get("/api/v1/runtime/agents")
    @limiter.limit("60/minute")
    async def list_agents(request: Request):
        """List all registered agents."""
        return {"agents": executor.list_agents()}

    # Backward compatibility alias
    @app.get("/api/v1/tasks", deprecated=True)
    async def list_tasks_legacy():
        """List all registered agents (legacy path)."""
        return {"tasks": executor.list_agents()}

    @app.get("/api/v1/runtime/agents/{agent_id}/status")
    async def get_agent_status(agent_id: str):
        """Get status of a specific agent."""
        if agent_id not in executor.agents:
            raise HTTPException(status_code=404, detail="Agent not found")

        status = executor.get_agent_status(agent_id)
        return {"agent_id": agent_id, "status": status.value}

    @app.post("/api/v1/runtime/agents/{agent_id}/trigger")
    @limiter.limit("10/minute")
    async def trigger_agent(
        request: Request, agent_id: str, context: Optional[Dict[str, Any]] = None
    ):
        """Manually trigger an agent."""
        if agent_id not in executor.agents:
            raise HTTPException(status_code=404, detail="Agent not found")

        try:
            result = executor.trigger_agent(agent_id, context or {})
            return result.model_dump()
        except Exception as e:
            logger.error("agent_trigger_error", agent_id=agent_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    # ==================== History ====================

    @app.get("/api/v1/runtime/history")
    @limiter.limit("60/minute")
    async def get_history(request: Request, limit: int = 50, agent_id: Optional[str] = None):
        """Get recent execution history."""
        executions = executor.history.get_recent_executions(limit=limit, agent_id=agent_id)
        return {"executions": executions, "count": len(executions)}

    @app.get("/api/v1/runtime/history/{agent_id}")
    async def get_agent_history(agent_id: str, limit: int = 50):
        """Get execution history for a specific agent."""
        if agent_id not in executor.agents:
            raise HTTPException(status_code=404, detail="Agent not found")

        executions = executor.history.get_recent_executions(limit=limit, agent_id=agent_id)
        statistics = executor.history.get_agent_statistics(agent_id)
        return {
            "agent_id": agent_id,
            "executions": executions,
            "statistics": statistics,
        }

    @app.get("/api/v1/runtime/history/execution/{execution_id}")
    async def get_execution_detail(execution_id: int):
        """Get detailed information about a specific execution."""
        execution = executor.history.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        return execution

    # ==================== Webhooks ====================

    @app.post("/api/v1/runtime/webhooks/{webhook_path:path}")
    @limiter.limit("10/minute")
    async def webhook_handler(request: Request, webhook_path: str, event: WebhookEvent):
        """Handle webhook events."""
        if webhook_path not in webhook_handlers:
            raise HTTPException(status_code=404, detail="Webhook not found")

        agent_id = webhook_handlers[webhook_path]

        try:
            result = executor.trigger_agent(agent_id, context={"event": event.model_dump()})
            return result.model_dump()
        except Exception as e:
            logger.error("webhook_error", webhook_path=webhook_path, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    # ==================== Dashboard ====================

    @app.get("/api/v1/runtime/dashboard", response_class=HTMLResponse)
    async def dashboard():
        """Simple HTML dashboard with auto-refresh."""
        agents = executor.list_agents()
        metrics = MetricsCollector(executor.history).get_system_metrics()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cortex Runtime Dashboard</title>
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f4f4f4; }}
                .success {{ color: green; }}
                .failed {{ color: red; }}
                .idle {{ color: gray; }}
                .running {{ color: blue; }}
            </style>
        </head>
        <body>
            <h1>Cortex Runtime Dashboard</h1>

            <h2>System Metrics</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Executions</td><td>{metrics.get("total_executions", 0)}</td></tr>
                <tr><td>Success Rate</td><td>{metrics.get("success_rate", 0):.1f}%</td></tr>
                <tr><td>Active Agents</td><td>{metrics.get("agents_active", 0)}</td></tr>
                <tr><td>Last 24h</td><td>{metrics.get("last_24_hours", 0)}</td></tr>
            </table>

            <h2>Registered Agents ({len(agents)})</h2>
            <table>
                <tr><th>Agent ID</th><th>Name</th><th>Status</th></tr>
                {"".join(f'<tr><td>{a["agent_id"]}</td><td>{a["name"]}</td><td class="{a["status"]}">{a["status"]}</td></tr>' for a in agents)}
            </table>

            <p><small>Auto-refreshes every 30 seconds</small></p>
        </body>
        </html>
        """
        return html

    # ==================== Webhook Registration ====================

    def add_webhook_handler(webhook_path: str, agent_id: str):
        """Register a webhook handler."""
        webhook_handlers[webhook_path] = agent_id
        logger.info("webhook_registered", webhook_path=webhook_path, agent_id=agent_id)

    app.add_webhook_handler = add_webhook_handler

    return app
