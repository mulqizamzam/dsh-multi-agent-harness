# tests/live_dsh/real_backend.py — REAL DSH bridge backend (Phase 3 / Session E)
#
# TEST-SUPPORT ONLY. NOT production code.
#
# A DelegationBackend that drives the ACTUAL mounted D4/D7 `subagent_<id>`
# tool instances — the replacement for FakeSubagentBackend after the
# Human-approved composition is active.
#
# The backend implements the SAME seam as orchestrator/dsh/backend.py
# (DelegationBackend / DelegationRun / DelegationResult) so the runtime can
# swap it in without any change to the orchestrator. It does NOT mount,
# register, or configure DSH; it consumes an injected dispatch bridge that the
# orchestrator session provides once the composition is live.
#
# SAFETY:
#   - The harness NEVER executes live scenarios. `start()` refuses with
#     BridgeNotAvailable unless a dispatch bridge is injected AND the D4/D7
#     mount marker is present (or the caller is an explicit contract test).
#   - It NEVER silently falls back to the fake backend.

from __future__ import annotations

import os
import sys
import time
import uuid
from dataclasses import dataclass, field as dc_field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.dsh.backend import (
    DelegationBackend, DelegationResult, DelegationRun,
    STOP_COMPLETED,
)

from .contract import (
    BuildInvocation, DSHInvocation, map_stop_reason_to_outcome,
    STOP_REASONS,
)
from .discovery import check_instance_mounted


class BridgeNotAvailable(RuntimeError):
    """The real DSH bridge is not available for this path.

    Raised when a REAL dispatch is requested without the D4/D7 mount marker
    (or without an injected contract-test dispatch). Fail-closed: the harness
    never silently runs the fake backend in place of a requested REAL run.
    """


@dataclass(frozen=True)
class DSHBridgeResponse:
    """The settled outcome of one REAL `subagent_<id>` call.

    This mirrors DSH SubagentResult (types.ts:219-245):
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


class DSHBridgeDispatch:
    """The injected bridge that performs the ACTUAL `subagent_<id>` tool call.

    The orchestrator session supplies an implementation when the D4/D7
    composition is mounted. The contract:
        dispatch(invocation, instance) -> DSHBridgeResponse

    The dispatch is the ONLY place a live tool call happens. This harness never
    provides a live dispatch; tests inject a recording/dispatch stub to
    exercise the mapping logic only.
    """

    def __init__(self, fn):
        self._fn = fn

    def __call__(self, invocation: DSHInvocation, instance):
        if self._fn is None:
            raise BridgeNotAvailable(
                "no live dispatch injected — the D4/D7 composition is not "
                "mounted (HUMAN_PENDING); no live tool call is performed here")
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
        output_schema = (prompt or {}).get("output_schema") \
            or BuildInvocation.default_task_result_schema()
        invocation = DSHInvocation(
            description=description,
            prompt=task_prompt,
            agent_preset=getattr(instance, "agent_preset", ""),
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
                f"({os.environ.get('DISCOVERY_MARKER_ENV', 'DSH_LIVE_BRIDGE_ACTIVE')}=1); "
                f"no live tool call is performed (Session E rule).")

        # The ONLY live tool call boundary. Refuse unless a bridge is injected.
        outcome = self._dispatch(invocation, instance)

        # The run_id comes from the dispatch response (the DSH session's run
        # identity). A missing run_id is a fallback only.
        run_id = outcome.run_id or f"real-{uuid.uuid4().hex[:12]}"

        # Normalize an unknown stop reason (fail-closed).
        if outcome.stop_reason not in STOP_REASONS:
            outcome = DSHBridgeResponse(
                run_id=run_id, output=outcome.output,
                structured=outcome.structured,
                stop_reason="error",
                diagnostic=(outcome.diagnostic
                            or f"unknown stop reason {outcome.stop_reason!r}"))

        # Normalize an unknown stop reason (fail-closed).
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
    "DSHBridgeDispatch",
]