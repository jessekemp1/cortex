"""Bridge API authentication — shared by HTTP middleware and WebSocket routes.

Policy (same as the original /signal/absorb gate):
  - If CORTEX_API_KEY (env or ~/.cortex/api_key) is set, require Bearer token match.
  - If no key is configured, allow localhost-only (127.0.0.1 / ::1 / testclient).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import FrozenSet, Optional, Tuple

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket

_LOCAL_HOSTS: FrozenSet[str] = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})

# Health probes only — no auth required.
_AUTH_EXEMPT: FrozenSet[Tuple[str, str]] = frozenset(
    {
        ("GET", "/"),
        ("GET", "/health"),
        ("GET", "/service-health"),
    }
)


def get_api_key() -> Optional[str]:
    """Read configured API key from env or ~/.cortex/api_key."""
    key = os.environ.get("CORTEX_API_KEY")
    if key:
        return key
    key_file = Path.home() / ".cortex" / "api_key"
    if key_file.is_file():
        return key_file.read_text().strip() or None
    return None


def _client_host(request: Request) -> Optional[str]:
    if request.client:
        return request.client.host
    return None


def verify_bridge_auth(request: Request) -> None:
    """Verify caller is authorised for Bridge API access.

    Raises HTTPException(401) on failure.
    """
    api_key = get_api_key()
    if api_key:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        if auth_header[7:] != api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return

    client_host = _client_host(request)
    if client_host not in _LOCAL_HOSTS:
        raise HTTPException(
            status_code=401,
            detail="No API key configured; only localhost access allowed",
        )


def is_auth_exempt(method: str, path: str) -> bool:
    if method == "OPTIONS":
        return True
    return (method, path.split("?", 1)[0]) in _AUTH_EXEMPT


def verify_websocket_auth(websocket: WebSocket) -> None:
    """Verify WebSocket caller before accept(). Raises HTTPException(401)."""
    api_key = get_api_key()
    if api_key:
        auth_header = websocket.headers.get("authorization", "")
        token: Optional[str] = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = websocket.query_params.get("token")
        if not token or token != api_key:
            raise HTTPException(status_code=401, detail="Missing or invalid API key")
        return

    client_host = websocket.client.host if websocket.client else None
    if client_host not in _LOCAL_HOSTS:
        raise HTTPException(
            status_code=401,
            detail="No API key configured; only localhost access allowed",
        )


class BridgeAuthMiddleware(BaseHTTPMiddleware):
    """Apply verify_bridge_auth to all non-exempt HTTP routes."""

    async def dispatch(self, request: Request, call_next):
        if is_auth_exempt(request.method, request.url.path):
            return await call_next(request)
        try:
            verify_bridge_auth(request)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return await call_next(request)
