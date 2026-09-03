# orchestrator.entrypoint — DSH chat → ProductionRun front door (V1)
#
# Phase 5 / Front Door V1. Package init re-exports the public API:
#
#   run_from_chat(...)     the thin adapter (chat/script/CLI → ProductionRun)
#   FrontDoorRequest       validated request contract (DATA, never authority)
#   FrontDoorResult        structured terminal result envelope
#   resolve_delegation     read-only delegation resolution (fail-closed)
#   run_front_door         internal adapter (deprecated, use run_from_chat)
#
# Exceptions
# ----------
#   FrontDoorError         shape validation failure (fail-closed)
#
# Statuses
# --------
#   COMPLETE / BLOCKED / ESCALATED / ERROR
#
# Envelope schema
# ---------------
#   SCHEMA = "run-result@1"

from .entry import (
    SCHEMA,
    COMPLETE,
    BLOCKED,
    ESCALATED,
    ERROR,
    STATUSES,
    FrontDoorError,
    FrontDoorRequest,
    FrontDoorResult,
    resolve_delegation,
    run_front_door,
    run_from_chat,
)

__all__ = [
    "SCHEMA",
    "COMPLETE", "BLOCKED", "ESCALATED", "ERROR", "STATUSES",
    "FrontDoorError",
    "FrontDoorRequest",
    "FrontDoorResult",
    "resolve_delegation",
    "run_front_door",
    "run_from_chat",
]