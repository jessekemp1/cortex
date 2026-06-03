"""Cortex Bridge route modules — one APIRouter per concern.

The Bridge endpoint historically defined ~58 routes inline in
`api/bridge_endpoint.py` (3158 LOC, intimidating to read and review). This
package extracts those routes into focused router modules so each concern
fits in a reviewable file.

This is an incremental extraction: a router lands here when its routes
share state, models, and dependencies tightly enough that moving them
together produces a clean module. Routes that aren't yet extracted remain
in `bridge_endpoint.py`. See `docs/AUDIT_FINDINGS.md` for the planned
remaining extractions.
"""
