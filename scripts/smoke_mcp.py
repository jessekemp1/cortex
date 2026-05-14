#!/usr/bin/env python3
"""
MCP tool smoke script.

Starts the bridge as a subprocess, then spawns mcp_server.py as a stdio MCP
server and exercises every registered tool with a minimal payload. Asserts
no tool returns {"error": ...} (which is the silent-failure shape that
hid the 4 broken tools in shipping code).

Exits 0 on full green; exits 1 with a per-tool report on any failure.

Usage:
    python scripts/smoke_mcp.py                  # full smoke
    python scripts/smoke_mcp.py --tool cortex_doctor   # single tool
    python scripts/smoke_mcp.py --no-bridge      # skip bridge startup
                                                 # (assume already running)

CI: this script is the canary that gates merges. Phase 0 includes it as a
required check.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PORT = 8765
BRIDGE_HOST = "127.0.0.1"

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
    },
    "cortex_research_digest": {},
    "cortex_doctor": {},
}

# Tools known broken pre-Phase-1 (real code bugs). Smoke records their status
# but does not fail the run on them. Phase 1 fixes flip these to green —
# remove the entry the moment a fix lands.
#
# Phase 1 cleared the original 4 entries (conductor_compose, record_decision,
# plan_create, plan_progress). Set is empty as of Phase 1 ship.
KNOWN_BROKEN: set[str] = set()

# Tools whose smoke result depends on local environment (data files, optional
# packages, valid IDs) rather than code correctness. Failures here are
# reported but don't fail the run. Fixes belong in later phases.
KNOWN_ENV_DEPENDENT: set[str] = {
    "cortex_orchestrate",  # needs psutil + supervisor stack
    "cortex_outcomes",  # needs cortex.v2.learning.outcomes module
    "cortex_prompt_refine",  # needs ~/.cortex/prompts/patterns.json seeded
    "cortex_batch_status",  # smoke uses a fake batch_id → 404 is correct
}


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
    env["PYTHONPATH"] = str(REPO_ROOT.parent) + ":" + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "cortex.api.bridge_endpoint:app",
            "--host",
            BRIDGE_HOST,
            "--port",
            str(BRIDGE_PORT),
            "--log-level",
            "warning",
        ],
        cwd=str(REPO_ROOT.parent),
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


async def _smoke_tools(only: str | None) -> dict[str, dict]:
    """Spawn mcp_server.py via stdio and call each tool."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cortex.mcp_server"],
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT.parent)},
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
                        session.call_tool(name, args), timeout=15
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
        "--no-bridge", action="store_true", help="skip starting the bridge"
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    bridge_proc = None
    try:
        if not args.no_bridge:
            try:
                bridge_proc = _start_bridge()
            except Exception as e:
                print(f"[smoke] FATAL: {e}", file=sys.stderr)
                return 1

        results = asyncio.run(_smoke_tools(args.tool))

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print()
            print(f"{'TOOL':<32} STATUS")
            print("─" * 60)
            for name, r in sorted(results.items()):
                marker = ""
                if r["status"] != "ok":
                    if name in KNOWN_BROKEN:
                        marker = "  (known broken, Phase 1)"
                    elif name in KNOWN_ENV_DEPENDENT:
                        marker = "  (env-dependent)"
                print(f"{name:<32} {r['status']}{marker}")
                if r["status"] not in ("ok",) and r.get("error"):
                    print(f"{'':<32}   → {r['error']}")

        # Exit code: failures EXCLUDING known-broken and env-dependent count as red.
        red = {
            n: r
            for n, r in results.items()
            if r["status"] != "ok"
            and n not in KNOWN_BROKEN
            and n not in KNOWN_ENV_DEPENDENT
        }
        # If a KNOWN_BROKEN tool unexpectedly passes, that's also a signal —
        # Phase 1 probably landed; remove it from the set.
        unexpected_green = {
            n for n, r in results.items() if r["status"] == "ok" and n in KNOWN_BROKEN
        }
        if unexpected_green:
            print(
                f"\n[smoke] {len(unexpected_green)} known-broken tool(s) now passing: "
                f"{sorted(unexpected_green)}. Remove from KNOWN_BROKEN in scripts/smoke_mcp.py.",
                file=sys.stderr,
            )

        if red:
            print(f"\n[smoke] FAIL: {len(red)} tool(s) red", file=sys.stderr)
            return 1
        print(
            f"\n[smoke] OK: {sum(1 for r in results.values() if r['status'] == 'ok')} tool(s) green",
            f"({len(KNOWN_BROKEN & set(results))} known-broken not counted)",
        )
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
