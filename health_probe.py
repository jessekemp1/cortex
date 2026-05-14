"""
Cortex service health probes (stdlib-only).

Extracted from api/bridge_endpoint.py during Phase 5 of the slim-down so the
MCP server can compute service health WITHOUT going through the HTTP bridge.

Has NO heavy imports — pure stdlib. Safe to import at MCP server module load.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Dict


def _probe_json(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """GET a URL and return parsed JSON, or raise on any failure."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _probe_status(url: str, timeout: float = 2.0) -> int:
    """GET a URL and return HTTP status code, or raise on any failure."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def compute_service_health() -> Dict[str, Any]:
    """Probe all known cortex ecosystem services and return their status.

    Returns a dict keyed by service name. Each value is a dict with at
    minimum `status` (healthy/degraded/offline) and `port`.
    """
    services: Dict[str, Any] = {
        "bridge": {"status": "healthy", "port": 8765},
    }

    # Vortex Backend (:8000)
    try:
        data = _probe_json("http://localhost:8000/api/v2/health")
        services["vortex_backend"] = {
            "status": "healthy" if data.get("status") == "healthy" else "degraded",
            "port": 8000,
            "scheduler_jobs": data.get("scheduler", {}).get("jobs_count", 0),
            "version": data.get("version", "unknown"),
        }
    except Exception:
        services["vortex_backend"] = {"status": "offline", "port": 8000}

    # Navigator (subsystem of Vortex Backend)
    try:
        data = _probe_json("http://localhost:8000/api/v2/navigator/health", timeout=5)
        checks = data.get("checks", {})
        subsystems = {
            k: v.get("status", "unknown") for k, v in checks.items() if isinstance(v, dict)
        }
        services["navigator"] = {
            "status": data.get("status", "unknown"),
            "port": 8000,
            "subsystems": subsystems,
            "version": data.get("version", "unknown"),
        }
    except Exception:
        services["navigator"] = {"status": "offline", "port": 8000}

    # Vortex Frontend (:5173 dev / :3000 prod)
    for port in (5173, 3000):
        try:
            if _probe_status(f"http://localhost:{port}/", timeout=2) == 200:
                services["vortex_frontend"] = {
                    "status": "healthy",
                    "port": port,
                    "label": "Vortex UI (React)",
                }
                break
        except Exception:
            continue
    services.setdefault(
        "vortex_frontend",
        {"status": "offline", "port": 5173, "label": "Vortex UI (React)"},
    )

    # Alpha Arena (:8502)
    try:
        status = _probe_status("http://localhost:8502/healthz", timeout=2)
        services["alpha_arena"] = {
            "status": "healthy" if status == 200 else "degraded",
            "port": 8502,
            "label": "Alpha Arena (Streamlit)",
        }
    except Exception:
        try:
            status = _probe_status("http://localhost:8502/", timeout=2)
            services["alpha_arena"] = {
                "status": "healthy" if status == 200 else "degraded",
                "port": 8502,
                "label": "Alpha Arena (Streamlit)",
            }
        except Exception:
            services["alpha_arena"] = {
                "status": "offline",
                "port": 8502,
                "label": "Alpha Arena (Streamlit)",
            }

    # Cortex Runtime API (:8003)
    try:
        data = _probe_json("http://localhost:8003/api/v1/runtime/health", timeout=2)
        services["cortex_runtime"] = {
            "status": "healthy" if data.get("status") == "healthy" else "degraded",
            "port": 8003,
            "label": "Cortex Runtime API",
        }
    except Exception:
        services["cortex_runtime"] = {
            "status": "offline",
            "port": 8003,
            "label": "Cortex Runtime API",
        }

    # Mission Control (:3001)
    try:
        status = _probe_status("http://localhost:3001/", timeout=2)
        services["mission_control"] = {
            "status": "healthy" if status == 200 else "degraded",
            "port": 3001,
        }
    except Exception:
        services["mission_control"] = {"status": "offline", "port": 3001}

    # Test metrics from ~/.cortex/metrics/tests.json
    tests_file = Path.home() / ".cortex" / "metrics" / "tests.json"
    if tests_file.exists():
        try:
            test_data = json.loads(tests_file.read_text())
            total_failed = sum(
                v.get("failed", 0) for v in test_data.values() if isinstance(v, dict)
            )
            services["tests"] = {
                "total_failures": total_failed,
                "projects": {
                    k: {"passed": v.get("passed", 0), "failed": v.get("failed", 0)}
                    for k, v in test_data.items()
                    if isinstance(v, dict)
                },
            }
        except Exception:
            pass

    # EMOS readiness from ~/.cortex/metrics/emos.json
    emos_file = Path.home() / ".cortex" / "metrics" / "emos.json"
    if emos_file.exists():
        try:
            emos_data = json.loads(emos_file.read_text())
            pairs = emos_data.get("pairs", {})
            threshold = 2000
            services["emos"] = {
                "pairs": pairs,
                "threshold": threshold,
                "ready_models": [m for m, c in pairs.items() if c >= threshold],
                "timestamp": emos_data.get("timestamp"),
            }
        except Exception:
            pass

    return services
