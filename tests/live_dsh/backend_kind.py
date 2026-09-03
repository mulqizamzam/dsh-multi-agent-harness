# tests/live_dsh/backend_kind.py — FAKE vs REAL backend discrimination (Phase 3 / Session E)
#
# TEST-SUPPORT ONLY. NOT production code.
#
# The harness must EXPLICITLY distinguish the two specialist-execution paths:
#
#   FAKE  — the deterministic in-process FakeSubagentBackend that ships with
#           the runtime (orchestrator/dsh/backend.py). Always available; used
#           by the existing INT-01/07 evidence harness. It models the DSH
#           tool-subagent contract but never touches a live session.
#
#   REAL  — the actual mounted `subagent_<id>` tool instances (D4/D7 approved
#           composition). Only available after the Human-approved controlled
#           composition exception is mounted and the session is restarted.
#           NEVER assumed present; never dispatched by this harness.
#
# `probe_backend_kind()` reports which kind is usable in the current process.

from __future__ import annotations

import enum
import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from .discovery import DISCOVERY_MARKER_ENV, check_instance_mounted


class BackendKind(enum.Enum):
    """The backend the harness may use for specialist execution."""

    FAKE = "fake"               # deterministic in-process backend (always usable)
    REAL = "real-dsh"           # mounted D4/D7 subagent_<id> instances (gated)
    UNAVAILABLE = "unavailable" # no live bridge marker — REAL not usable


def probe_backend_kind() -> BackendKind:
    """Report the usable backend kind in the current process.

    REAL is reported only when the D4/D7 composition mount marker is set.
    Without the marker the harness reports UNAVAILABLE for the real bridge —
    it NEVER assumes a live bridge exists and NEVER falls back silently.
    """
    if check_instance_mounted("subagent_probe"):
        # The marker is instance-agnostic: it gates the whole composition.
        return BackendKind.REAL
    return BackendKind.UNAVAILABLE


def is_real_bridge_available() -> bool:
    """True only when the D4/D7 composition mount marker is present."""
    return os.environ.get(DISCOVERY_MARKER_ENV, "").strip().lower() in (
        "1", "true", "yes")


def require_real_bridge():
    """Refuse a REAL-backend path unless the live bridge is available.

    Raises RuntimeError (fail-closed) — the harness never silently degrades
    to the fake backend when a REAL execution was requested.
    """
    if not is_real_bridge_available():
        raise RuntimeError(
            f"REAL DSH bridge not available: set {DISCOVERY_MARKER_ENV}=1 only "
            "after the D4/D7 composition is approved and mounted. Do NOT "
            "assume a live bridge exists.")


__all__ = [
    "BackendKind", "probe_backend_kind", "is_real_bridge_available",
    "require_real_bridge",
]