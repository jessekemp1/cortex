#!/usr/bin/env python3
"""
MCP tool smoke script.

Spawns mcp_server.py as a stdio MCP server and exercises every registered
tool with a minimal payload, asserting no tool returns {"error": ...} —
the silent-failure shape that once hid four broken tools in shipping code.

Two modes:

    python scripts/smoke_mcp.py              # full smoke: starts the bridge
                                             # if not already up; all 18 tools
                                             # must be green
    python scripts/smoke_mcp.py --no-bridge  # crash-proof drill: bridge NOT
                                             # started; the core-8 in-process
                                             # tools must still be green;
                                             # passthrough errors are tolerated

The MCP child process runs with CORTEX_STATE_DIR pointed at a throwaway tmp
dir, so smoke runs never write decisions/plans into the live ~/.cortex.

Exits 0 on green; exits 1 with a per-tool report on any failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PORT = 8765
BRIDGE_HOST = "127.0.0.1"

# The in-process core: must succeed with the bridge down (crash-proof contract,
# pinned by tests/contract/test_mcp_direct.py).
CORE_TOOLS = {
    "cortex_record_decision",
    "cortex_intelligence",
    "cortex_recommendations",
    "cortex_outcomes",
    "cortex_plan_create",
    "cortex_plan_progress",
    "cortex_projects",
    "cortex_doctor",
}

# Minimal arguments per MCP tool. For tools that read state, args are chosen
# to produce a meaningful (or empty-but-shaped) response — never a 4xx/5xx.
TOOL_ARGS: dict[str, dict] = {
    "cortex_service_health": {},
    "cortex_intelligence": {"query": "smoke test", "query_type": "research"},
    "cortex_recommendations": {},
    "cortex_anomalies": {},
    "cortex_projects": {},
    "cortex_sessions": {"active_only": False},
    "cortex_taskboard": {},
    "cortex_orchestrate": {"dry_run": True, "max_items": 1},
    "cortex_prompt_refine": {"prompt": "smoke test prompt"},
    "cortex_conductor_compose": {
        "intent": "smoke test",
        "project": "cortex",
        "intent_level": "advisory",
        "include_context": False,
    },
    "cortex_graph_query": {"node_type": "pattern", "limit": 1},
    "cortex_plan_create": {"project": "cortex"},
    "cortex_plan_progress": {},
    "cortex_batch_status": {"batch_id": "smoke_test_batch_id"},
    "cortex_outcomes": {"limit": 1},
    "cortex_record_decision": {
        "decision": "smoke test decision",
        "context": "smoke",
        "alternatives": "none",
        "rationale": "smoke",
        "project": "cortex",
    },
    "cortex_research_digest": {},
    "cortex_doctor": {},
}

# Tools whose smoke result depends on local environment (data files, optional
# packages, valid IDs) rather than code correctness. Failures here are
# reported but don't fail the run.
KNOWN_ENV_DEPENDENT: set[str] = {
    "cortex_batch_status",  # needs ANTHROPIC_API_KEY (returns a clear message without)
    "cortex_doctor",  # reports env facts (API key set, launchd) — red env, not red code
}

# First call on the core intelligence tools pays the ~16s lazy CortexBridge
# init; give them headroom. Everything else answers fast.
SLOW_TOOLS = {"cortex_intelligence": 60, "cortex_recommendations": 60}
DEFAULT_TIMEOUT = 15


# ──────────────────────────────────────────────────────────────────────


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _start_bridge() -> subprocess.Popen | None:
    """Start the bridge in a subprocess. Return Popen (or None if already up)."""
    if _port_open(BRIDGE_HOST, BRIDGE_PORT):
        print(f"[smoke] bridge already up on {BRIDGE_HOST}:{BRIDGE_PORT}")
        return None

    print(f"[smoke] starting bridge on {BRIDGE_HOST}:{BRIDGE_PORT}…")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + ":" + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.bridge_endpoint:app",
            "--host",
            BRIDGE_HOST,
            "--port",
            str(BRIDGE_PORT),
            "--log-level",
            "warning",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait up to 20s for the bridge to bind.
    deadline = time.time() + 20
    while time.time() < deadline:
        if _port_open(BRIDGE_HOST, BRIDGE_PORT):
            print("[smoke] bridge up")
            return proc
        if proc.poll() is not None:
            err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(f"bridge exited early: {err}")
        time.sleep(0.3)
    proc.kill()
    raise RuntimeError("bridge failed to start within 20s")


async def _smoke_tools(only: str | None, state_dir: str) -> dict[str, dict]:
    """Spawn mcp_server.py via stdio and call each tool."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server"],
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT),
            "CORTEX_STATE_DIR": state_dir,
            # Register all 18 tools (the 10 non-core are gated by default) so
            # smoke exercises the full inventory in both modes.
            "CORTEX_EXPERIMENTAL": "1",
        },
    )

    results: dict[str, dict] = {}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tool_list = await session.list_tools()
            registered = {t.name for t in tool_list.tools}

            targets = (
                {only}
                if only
                else {name for name in TOOL_ARGS if name in registered}
            )

            for name in sorted(targets):
                if name not in registered:
                    results[name] = {"status": "not_registered"}
                    continue
                args = TOOL_ARGS.get(name, {})
                try:
                    result = await asyncio.wait_for(
                        session.call_tool(name, args),
                        timeout=SLOW_TOOLS.get(name, DEFAULT_TIMEOUT),
                    )
                    text = "".join(
                        getattr(c, "text", "")
                        for c in result.content
                        if hasattr(c, "text")
                    )
                    try:
                        body = json.loads(text) if text else {}
                    except json.JSONDecodeError:
                        body = {"_raw": text[:200]}

                    if isinstance(body, dict) and "error" in body:
                        results[name] = {
                            "status": "error_response",
                            "error": str(body["error"])[:200],
                        }
                    else:
                        results[name] = {"status": "ok"}
                except asyncio.TimeoutError:
                    results[name] = {"status": "timeout"}
                except Exception as e:
                    results[name] = {"status": "exception", "error": str(e)[:200]}

    return results


# ──────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", help="exercise only this tool")
    ap.add_argument(
        "--no-bridge",
        action="store_true",
        help="crash-proof drill: don't start the bridge; only the core-8 "
        "in-process tools must be green",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    bridge_proc = None
    try:
        if args.no_bridge:
            if _port_open(BRIDGE_HOST, BRIDGE_PORT):
                print(
                    "[smoke] NOTE: bridge is UP — passthrough results won't reflect "
                    "a real outage, but core-8 assertions remain valid.",
                    file=sys.stderr,
                )
        else:
            try:
                bridge_proc = _start_bridge()
            except Exception as e:
                print(f"[smoke] FATAL: {e}", file=sys.stderr)
                return 1

        with tempfile.TemporaryDirectory(prefix="cortex-smoke-") as state_dir:
            results = asyncio.run(_smoke_tools(args.tool, state_dir))

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print()
            print(f"{'TOOL':<32} STATUS")
            print("─" * 60)
            for name, r in sorted(results.items()):
                marker = ""
                if r["status"] != "ok":
                    if name in KNOWN_ENV_DEPENDENT:
                        marker = "  (env-dependent)"
                    elif args.no_bridge and name not in CORE_TOOLS:
                        marker = "  (bridge down — passthrough, tolerated)"
                print(f"{name:<32} {r['status']}{marker}")
                if r["status"] not in ("ok",) and r.get("error"):
                    print(f"{'':<32}   → {r['error']}")

        # Exit code: in --no-bridge mode only core-8 failures are red;
        # otherwise every non-env-dependent failure is red.
        red = {
            n: r
            for n, r in results.items()
            if r["status"] != "ok"
            and n not in KNOWN_ENV_DEPENDENT
            and (not args.no_bridge or n in CORE_TOOLS)
        }

        if red:
            print(f"\n[smoke] FAIL: {len(red)} tool(s) red: {sorted(red)}", file=sys.stderr)
            return 1
        green = sum(1 for r in results.values() if r["status"] == "ok")
        mode = "core-8 drill" if args.no_bridge else "full"
        print(f"\n[smoke] OK ({mode}): {green} tool(s) green")
        return 0
    finally:
        if bridge_proc is not None:
            bridge_proc.terminate()
            try:
                bridge_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bridge_proc.kill()


if __name__ == "__main__":
    sys.exit(main())
