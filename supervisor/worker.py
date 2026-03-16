"""
Remote worker — polls supervisor for tasks, executes, reports results.

Usage:
    cortex worker start --supervisor-url http://host:8766 \\
                        --capabilities sonnet,haiku \\
                        --providers deepseek,groq

The worker is a standalone process that:
1. Registers with the supervisor
2. Polls for available tasks matching its capabilities
3. Executes tasks using its configured providers
4. Reports results back to the supervisor
5. Sends heartbeats to avoid task reclamation
"""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DEFAULT_POLL_INTERVAL = 5.0  # seconds
_HEARTBEAT_INTERVAL = 30.0  # seconds


@dataclass
class WorkerConfig:
    """Configuration for a remote worker."""

    supervisor_url: str  # e.g. "http://localhost:8766"
    auth_token: str = ""
    capabilities: List[str] = field(default_factory=lambda: ["sonnet", "haiku"])
    providers: List[str] = field(default_factory=lambda: ["anthropic"])
    max_concurrent: int = 2
    poll_interval: float = _DEFAULT_POLL_INTERVAL
    heartbeat_interval: float = _HEARTBEAT_INTERVAL
    worker_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hostname: str = field(default_factory=socket.gethostname)


class CortexWorker:
    """Remote worker that polls supervisor for tasks.

    Lifecycle:
    1. register() — announce to supervisor
    2. run() — main poll loop
    3. On each poll: claim_task() → execute() → report_result()
    4. Background: heartbeat every 30s
    """

    def __init__(self, config: WorkerConfig) -> None:
        self._config = config
        self._running = False
        self._active_tasks: Dict[str, Any] = {}

    async def register(self) -> bool:
        """Register this worker with the supervisor."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._config.supervisor_url}/workers/register",
                    json={
                        "worker_id": self._config.worker_id,
                        "hostname": self._config.hostname,
                        "capabilities": self._config.capabilities,
                        "providers": self._config.providers,
                        "max_concurrent": self._config.max_concurrent,
                    },
                    headers=self._auth_headers(),
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    log.info(
                        "Registered with supervisor: worker=%s host=%s",
                        self._config.worker_id[:8],
                        self._config.hostname,
                    )
                    return True
                log.error("Registration failed: %d %s", resp.status_code, resp.text)
                return False
        except Exception as exc:
            log.error("Failed to register: %s", exc)
            return False

    async def run(self) -> None:
        """Main worker loop: poll → claim → execute → report → heartbeat."""
        self._running = True

        if not await self.register():
            log.error("Failed to register, exiting")
            return

        # Start heartbeat in background
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            while self._running:
                try:
                    task = await self._poll_for_task()
                    if task:
                        result = await self._execute(task)
                        await self._report_result(task["task_id"], result)
                    else:
                        await asyncio.sleep(self._config.poll_interval)
                except Exception as exc:
                    log.error("Worker loop error: %s", exc)
                    await asyncio.sleep(self._config.poll_interval)
        finally:
            self._running = False
            heartbeat_task.cancel()

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False

    async def _poll_for_task(self) -> Optional[Dict]:
        """Poll supervisor for an available task."""
        try:
            import httpx

            capabilities = ",".join(self._config.capabilities)
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._config.supervisor_url}/tasks/next",
                    params={"capabilities": capabilities},
                    headers=self._auth_headers(),
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("task_id"):
                        return data
                return None
        except Exception as exc:
            log.debug("Poll failed: %s", exc)
            return None

    async def _execute(self, task: Dict) -> Dict:
        """Execute a claimed task using local dispatch."""
        task_id = task.get("task_id", "unknown")
        log.info("Executing task %s", task_id[:8])

        # Placeholder: actual execution would use MultiProviderDispatcher
        # For now, return a result structure
        return {
            "task_id": task_id,
            "success": True,
            "output": f"Executed by worker {self._config.worker_id[:8]}",
            "tokens_used": 0,
            "duration_seconds": 0.0,
        }

    async def _report_result(self, task_id: str, result: Dict) -> bool:
        """Report execution result to supervisor."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._config.supervisor_url}/tasks/{task_id}/result",
                    json=result,
                    headers=self._auth_headers(),
                    timeout=10.0,
                )
                return resp.status_code == 200
        except Exception as exc:
            log.error("Failed to report result: %s", exc)
            return False

    async def _heartbeat_loop(self) -> None:
        """Send heartbeats to prevent task reclamation."""
        while self._running:
            await asyncio.sleep(self._config.heartbeat_interval)
            for task_id in list(self._active_tasks.keys()):
                try:
                    import httpx

                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"{self._config.supervisor_url}/tasks/{task_id}/heartbeat",
                            json={"worker_id": self._config.worker_id},
                            headers=self._auth_headers(),
                            timeout=5.0,
                        )
                except Exception:
                    pass  # Best effort

    def _auth_headers(self) -> Dict[str, str]:
        """Build auth headers."""
        if self._config.auth_token:
            return {"Authorization": f"Bearer {self._config.auth_token}"}
        return {}
