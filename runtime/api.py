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
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from cortex.runtime.models import WebhookEvent
from cortex.runtime.storage.metrics import MetricsCollector

if TYPE_CHECKING:
    from cortex.runtime.executor import RuntimeExecutor

logger = structlog.get_logger()


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

    webhook_handlers: Dict[str, str] = {}  # webhook_path -> agent_id

    # ==================== Health & Status ====================

    @app.get("/api/v1/runtime/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "service": "cortex-runtime"}

    # Backward compatibility alias
    @app.get("/api/v1/health", deprecated=True)
    async def health_legacy():
        """Health check endpoint (legacy path)."""
        return {"status": "healthy", "service": "cortex-runtime"}

    # ==================== Metrics ====================

    @app.get("/api/v1/runtime/metrics")
    async def get_metrics():
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

    # ==================== Agents ====================

    @app.get("/api/v1/runtime/agents")
    async def list_agents():
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
    async def trigger_agent(agent_id: str, context: Optional[Dict[str, Any]] = None):
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
    async def get_history(limit: int = 50, agent_id: Optional[str] = None):
        """Get recent execution history."""
        executions = executor.history.get_recent_executions(
            limit=limit, agent_id=agent_id
        )
        return {"executions": executions, "count": len(executions)}

    @app.get("/api/v1/runtime/history/{agent_id}")
    async def get_agent_history(agent_id: str, limit: int = 50):
        """Get execution history for a specific agent."""
        if agent_id not in executor.agents:
            raise HTTPException(status_code=404, detail="Agent not found")

        executions = executor.history.get_recent_executions(
            limit=limit, agent_id=agent_id
        )
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
    async def webhook_handler(webhook_path: str, event: WebhookEvent):
        """Handle webhook events."""
        if webhook_path not in webhook_handlers:
            raise HTTPException(status_code=404, detail="Webhook not found")

        agent_id = webhook_handlers[webhook_path]

        try:
            result = executor.trigger_agent(
                agent_id, context={"event": event.model_dump()}
            )
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
                <tr><td>Total Executions</td><td>{metrics.get('total_executions', 0)}</td></tr>
                <tr><td>Success Rate</td><td>{metrics.get('success_rate', 0):.1f}%</td></tr>
                <tr><td>Active Agents</td><td>{metrics.get('agents_active', 0)}</td></tr>
                <tr><td>Last 24h</td><td>{metrics.get('last_24_hours', 0)}</td></tr>
            </table>

            <h2>Registered Agents ({len(agents)})</h2>
            <table>
                <tr><th>Agent ID</th><th>Name</th><th>Status</th></tr>
                {''.join(f'<tr><td>{a["agent_id"]}</td><td>{a["name"]}</td><td class="{a["status"]}">{a["status"]}</td></tr>' for a in agents)}
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
