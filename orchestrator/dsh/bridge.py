# orchestrator.dsh.bridge — REAL DSH bridge backend (production-owned)
#
# Phase 4 / Session A (G1). Scope: multi-agent-harness/ only.
#
# The production DelegationBackend over the ACTUAL mounted D4/D7 `subagent_<id>`
# tool instances — the REAL replacement for FakeSubagentBackend once the
# Human-approved composition is active.
#
# This module is the production copy of the proven Phase-3 test-support
# implementation (tests/live_dsh/real_backend.py). It keeps the same names and
# behavior so integration can reconcile the two copies; the test-support copy is
# left untouched and remains the live-contract harness's authority. Known
# duplication (production bridge.py <-> tests/live_dsh/real_backend.py) is
# intentional and flagged for reconciliation in a later session.
#
# SAFETY:
#   - A REAL start() refuses with BridgeNotAvailable unless the D4/D7 mount
#     marker (DSH_LIVE_BRIDGE_ACTIVE) is present AND a dispatch bridge is
#     injected (or the caller is an explicit contract test with
#     require_marker=False).
#   - It NEVER silently falls back to the fake backend.
#
# The dispatch bridge is the ONLY place a live tool call happens. This module
# never performs a live dispatch on its own; the orchestrator session injects
# the dispatch once the composition is mounted. Tests inject a stub dispatch to
# exercise the mapping logic only.

from __future__ import annotations

import enum
import json
import os
import sys
import uuid
from dataclasses import dataclass, field as dc_field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import SPECIALIST_ROLES

from .backend import (
    DelegationBackend,
    DelegationResult,
    DelegationRun,
    STOP_COMPLETED,
)

# Environment variable the orchestrator session sets when the D4/D7 composition
# is mounted and the `subagent_<id>` tools are available for delegation (same
# convention as tests/live_dsh/discovery.py).
BRIDGE_MARKER_ENV = "DSH_LIVE_BRIDGE_ACTIVE"

# DSH stop-reason vocabulary (mirrors SubagentStopReasonMap in 0.1.1-rc.2).
STOP_REASONS = ("completed", "aborted", "error", "max-tokens", "refusal")


class BackendKind(enum.Enum):
    """The explicit three-state delegation-backend selection (G1).

    Mirrors the Phase-3 test-support vocabulary (tests/live_dsh/backend_kind.py)
    so live-contract harness and production runtime agree on the states:

      FAKE        — the deterministic in-process FakeSubagentBackend (always
                    usable; the unit-test deterministic default).
      REAL        — the live D4/D7 `subagent_<id>` bridge (requires the
                    DSH_LIVE_BRIDGE_ACTIVE marker AND an injected dispatch).
      UNAVAILABLE — a REAL execution was requested but the bridge is not
                    available (no marker / no dispatch). Fail-closed: the flow
                    must STOP/BLOCK — NEVER a silent fallback to fake.
    """

    FAKE = "fake"
    REAL = "real-dsh"
    UNAVAILABLE = "unavailable"


def probe_backend_kind() -> BackendKind:
    """Report whether the live DSH bridge is usable in this process.

    REAL is reported only when the D4/D7 composition mount marker is set.
    Without the marker, the bridge is UNAVAILABLE — this probe NEVER assumes
    a live bridge exists. It does NOT dispatch.
    """
    if check_instance_mounted("subagent_probe"):
        # The marker is instance-agnostic: it gates the whole composition.
        return BackendKind.REAL
    return BackendKind.UNAVAILABLE


def check_instance_mounted(tool_name: str) -> bool:
    """Probe whether one `subagent_<id>` instance is mounted.

    Without a live session probe this returns True ONLY when the
    BRIDGE_MARKER_ENV environment variable is set — the orchestrator session
    sets it when the D4/D7 composition is active. The harness NEVER assumes a
    live bridge exists.
    """
    return os.environ.get(BRIDGE_MARKER_ENV, "").strip().lower() in (
        "1", "true", "yes")


class BridgeNotAvailable(RuntimeError):
    """The real DSH bridge is not available for this path.

    Raised when a REAL dispatch is requested without the D4/D7 mount marker
    (or without an injected dispatch). Fail-closed: the harness never silently
    runs the fake backend in place of a requested REAL run.
    """


@dataclass(frozen=True)
class DSHBridgeResponse:
    """The settled outcome of one REAL `subagent_<id>` call.

    Mirrors DSH SubagentResult:
      - output      : final assistant text (ContentBlock text joined)
      - structured  : the validated value from `structured_output`, or None
      - stop_reason : DSH vocabulary (completed/aborted/error/max-tokens/refusal)
      - diagnostic  : provider-authored failure detail (non-completed only)
    """
    run_id: str
    output: str = ""
    structured: dict | None = None
    stop_reason: str = STOP_COMPLETED
    diagnostic: str = ""

    def to_delegation_result(self) -> DelegationResult:
        return DelegationResult(
            output=self.output,
            structured=self.structured,
            stop_reason=self.stop_reason,
            diagnostic=self.diagnostic,
        )


@dataclass(frozen=True)
class DSHInvocation:
    """The exact DSH tool-subagent call the real bridge issues.

    - `description`: short (3-5 word) display label (tool param).
    - `prompt`: the standalone task prompt handed to the child. It must be
      SELF-CONTAINED (the child does NOT see the parent conversation for a
      spawn provider; inheritsParentContext=false).
    - `run_in_background`: False for the orchestrator's foreground delegation.
    - `output_schema`: the JSON Schema the child must satisfy through the
      `structured_output` tool so the bridge can capture a structured
      TaskResult from `SubagentResult.structured`.
    - `persona` / `tool_filter` / `max_depth`: composition the mounted instance
      already carries; the bridge does NOT re-declare them.
    """
    description: str
    prompt: str
    role: str = ""
    run_in_background: bool = False
    output_schema: dict = dc_field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "prompt": self.prompt,
            "role": self.role,
            "run_in_background": self.run_in_background,
            "output_schema": self.output_schema,
        }


# The TaskResult JSON Schema the child must satisfy when no schema is carried
# in the prompt. This CANNOT be a hand-maintained copy: it is loaded verbatim
# from the canonical schemas/task-result.schema.json, so the schema handed to
# every live child is exactly the schema the collector (orchestrator.dsh.result)
# validates against and the TaskResult contract accepts. The previous value was
# a stale Phase-3 snapshot (7 roles / 3 statuses) that contradicted the file its
# own comment claimed to mirror; loading the file makes that drift impossible.
#
# NOTE: a top-level `from orchestrator.runtime.collection import
# FAILING_STATUSES` here would be a circular import (this module is
# orchestrator.dsh; runtime.__init__ imports flow, which imports
# `from orchestrator.dsh import RealDSHBackend` — still being defined). The role
# list therefore comes from the authoritative contracts.SPECIALIST_ROLES and the
# six statuses are the documented PRD v0.2 §13 vocabulary, used only if the
# canonical file is somehow unreadable.
_TASK_RESULT_SCHEMA_PATH = os.path.join(
    _PROJECT_ROOT, "schemas", "task-result.schema.json")
_FALLBACK_TASK_RESULT_STATUSES = (
    "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "TIMEOUT", "INCOMPLETE")


def _load_task_result_schema() -> dict:
    try:
        with open(_TASK_RESULT_SCHEMA_PATH, "r", encoding="utf-8") as _f:
            return json.load(_f)
    except (OSError, ValueError):  # pragma: no cover - canonical file is shipped
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["task_id", "assigned_role", "status",
                         "confidence", "reported_at"],
            "properties": {
                "task_id": {"type": "string", "minLength": 1},
                "assigned_role": {"enum": list(SPECIALIST_ROLES)},
                "status": {"enum": list(_FALLBACK_TASK_RESULT_STATUSES)},
                "findings": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string"},
                "confidence": {"enum": ["LOW", "MEDIUM", "HIGH"]},
                "unresolved_items": {"type": "array", "items": {"type": "string"}},
                "actions_taken": {"type": "array", "items": {"type": "string"}},
                "reported_at": {"type": "string", "format": "date-time"},
            },
        }


DEFAULT_TASK_RESULT_SCHEMA = _load_task_result_schema()


class DSHBridgeDispatch:
    """The injected bridge that performs the ACTUAL `subagent_<id>` tool call.

    The orchestrator session supplies an implementation when the D4/D7
    composition is mounted. The contract:
        dispatch(invocation, instance) -> DSHBridgeResponse

    The dispatch is the ONLY place a live tool call happens. This module never
    provides a live dispatch; tests inject a recording/dispatch stub.
    """

    def __init__(self, fn):
        self._fn = fn

    def __call__(self, invocation: DSHInvocation, instance):
        if self._fn is None:
            raise BridgeNotAvailable(
                "no live dispatch injected — the D4/D7 composition is not "
                "mounted; no live tool call is performed here")
        return self._fn(invocation, instance)


class _RealDSHRun(DelegationRun):
    """One settled REAL delegation run handle (DelegationRun contract)."""

    def __init__(self, backend, run_id, outcome: DSHBridgeResponse):
        self._backend = backend
        self._run_id = run_id
        self._outcome = outcome
        self._disposed = False

    @property
    def run_id(self) -> str:
        return self._run_id

    def result(self) -> DelegationResult:
        return self._outcome.to_delegation_result()

    def dispose(self) -> None:
        self._disposed = True


class RealDSHBackend(DelegationBackend):
    """DelegationBackend over the REAL mounted `subagent_<id>` instances.

    Parameters
    ----------
    dispatch:
        The injected DSHBridgeDispatch that performs the actual tool call.
        Tests inject a stub dispatch; the orchestrator session injects the live
        bridge once the composition is active.
    require_marker:
        When True (default), a REAL start() also requires the D4/D7 mount
        marker (DSH_LIVE_BRIDGE_ACTIVE). Contract tests set False to exercise
        the mapping without a mounted composition.
    """

    name = "real-dsh-bridge"

    def __init__(self, dispatch=None, *, require_marker: bool = True):
        self._dispatch = DSHBridgeDispatch(dispatch)
        self._require_marker = require_marker
        self._children: dict[str, dict] = {}
        self._start_calls: list[dict] = []

    # -- observation ---------------------------------------------------------
    def start_calls(self) -> list[dict]:
        return list(self._start_calls)

    def children(self) -> dict[str, dict]:
        return dict(self._children)

    # -- DelegationBackend ---------------------------------------------------
    def start(self, instance, prompt: dict, *,
              signal=None, timeout_seconds: float | None = None) -> DelegationRun:
        tool_name = getattr(instance, "tool_name", "")
        role = getattr(instance, "role", "")

        # Build the DSH invocation from the authorized prompt dict. The prompt
        # must be the authorized context the runtime produced (THREAT-020).
        description = (prompt or {}).get("description") or f"{role}: delegated subtask"
        task_prompt = (prompt or {}).get("prompt") or (prompt or {}).get("task", "")
        # Only a dict output_schema is honoured: the organization path can put
        # a free-text STRING here (MissionTask.output_schema is str; handoff.py
        # copies it verbatim), and a string is not a JSON Schema. Anything that
        # is not a mapping falls back to the canonical DEFAULT_TASK_RESULT_SCHEMA.
        schema = (prompt or {}).get("output_schema")
        output_schema = schema if isinstance(schema, dict) else DEFAULT_TASK_RESULT_SCHEMA
        invocation = DSHInvocation(
            description=description,
            prompt=task_prompt,
            role=role,
            run_in_background=False,
            output_schema=output_schema,
        )

        if signal is not None and getattr(signal, "is_set", lambda: False)():
            raise BridgeNotAvailable("aborted before start (signal set)")

        # The D4/D7 mount gate: a REAL start() requires the composition marker
        # unless the caller is an explicit contract test (require_marker=False).
        if self._require_marker and not check_instance_mounted(tool_name):
            raise BridgeNotAvailable(
                f"REAL DSH bridge not mounted: {tool_name!r} requires the "
                f"D4/D7 composition exception to be approved and mounted "
                f"({BRIDGE_MARKER_ENV}=1); no live tool call is performed "
                f"(fail-closed).")

        # The ONLY live tool call boundary. Refuse unless a bridge is injected.
        outcome = self._dispatch(invocation, instance)

        # The run_id comes from the dispatch response (the DSH session's run
        # identity). A missing run_id is a fallback only.
        run_id = outcome.run_id or f"real-{uuid.uuid4().hex[:12]}"

        # Normalize an unknown stop reason (fail-closed: never a partial
        # result reported as success).
        if outcome.stop_reason not in STOP_REASONS:
            outcome = DSHBridgeResponse(
                run_id=run_id, output=outcome.output,
                structured=outcome.structured,
                stop_reason="error",
                diagnostic=(outcome.diagnostic
                            or f"unknown stop reason {outcome.stop_reason!r}"))

        self._start_calls.append({
            "tool_name": tool_name, "role": role, "run_id": run_id,
            "invocation": invocation.to_dict(),
            "stop_reason": outcome.stop_reason,
        })
        self._children[run_id] = {
            "tool_name": tool_name, "role": role, "status": "completed",
            "stop_reason": outcome.stop_reason,
        }
        return _RealDSHRun(self, run_id, outcome)

    def interrupt(self, run_id: str, signal) -> None:
        child = self._children.get(run_id)
        if child is not None:
            child["status"] = "interrupt-requested"
        if signal is not None:
            signal.set()

    def list_children(self, parent_session_id: str) -> list[dict]:
        return [dict(c, parent=parent_session_id) for c in self._children.values()]


__all__ = [
    "RealDSHBackend", "BridgeNotAvailable", "DSHBridgeResponse",
    "DSHBridgeDispatch", "DSHInvocation", "DEFAULT_TASK_RESULT_SCHEMA",
    "BRIDGE_MARKER_ENV", "check_instance_mounted", "STOP_REASONS",
    "BackendKind", "probe_backend_kind",
]
