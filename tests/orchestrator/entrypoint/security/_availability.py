# tests/orchestrator/entrypoint/security/_availability.py — Availability guard
#
# The package must remain valid even before Session Front Door V1 exists.
# Missing implementation is reported as NOT_YET_AVAILABLE, never fabricated:
#   - when orchestrator.entrypoint is not importable, every dependent test is
#     skipped with this module's reason (pytest.importorskip).
#   - the static/behavioural probes below only ever assert the *absence* of a
#     control or the *observed* outcome of a running adapter — they never
#     invent a PASS for a module that is not there.

from __future__ import annotations

import importlib.util

_NOT_YET_AVAILABLE = (
    "NOT_YET_AVAILABLE: orchestrator.entrypoint (DSH Chat → ProductionRun "
    "front door V1) is not implemented in this checkout; nothing fabricated."
)


def front_door_available() -> bool:
    """True when the front-door package is importable in this workspace."""
    return importlib.util.find_spec("orchestrator.entrypoint") is not None


def import_front_door():
    """Import the front-door package, or raise ImportError with the
    NOT_YET_AVAILABLE marker (consumed by pytest.importorskip)."""
    if not front_door_available():
        raise ImportError(_NOT_YET_AVAILABLE)
    import orchestrator.entrypoint  # noqa: F401
    import orchestrator.entrypoint.entry  # noqa: F401
    return __import__("orchestrator.entrypoint", fromlist=["*"])


__all__ = ["front_door_available", "import_front_door",
           "_NOT_YET_AVAILABLE"]
