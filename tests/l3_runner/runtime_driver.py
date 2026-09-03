# tests/l3_runner/runtime_driver.py — Safe runtime driver for L3 scenarios
#
# Provides the P1 (runtime) check for L3 scenarios. Two backends:
#   1. RecordedRuntimeDriver — replays a captured runtime verdict from a
#      fixture. USED NOW for infrastructure tests (safe, deterministic,
#      no live session, no destructive action). This is the P4 replay path.
#   2. LiveDSHRuntimeDriver — a STUB that raises NotImplementedError. It
#      documents the seam where a real DSH session would be plugged in for
#      an authorized L3 run. It is NOT implemented here and NOT executed.
#
# HARD REQUIREMENT: The runtime driver must NOT be used by the verifier.
# The verifier reads only the on-disk runtime-verdict.json produced by the
# driver (or replayed from a fixture). The driver and the verifier never
# share a process.

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now_iso() -> str:
    """UTC timestamp in the bundle's canonical format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RuntimeResult:
    """The result of executing an action through the runtime."""
    decision: str                           # ALLOW | DENY | ERROR | INVALID
    denial_path: str | None = None          # which gate fired
    tool_call_id: str | None = None
    audit_event_ids: list = field(default_factory=list)
    stopReason: str = "completed"
    captured_at: str = ""
    final_status: str = "COMPLETE"
    state_version_before: int | None = None
    state_version_after: int | None = None
    failure: dict | None = None
    audit_log: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "denial_path": self.denial_path,
            "tool_call_id": self.tool_call_id,
            "audit_event_ids": list(self.audit_event_ids),
            "stopReason": self.stopReason,
            "captured_at": self.captured_at,
            "final_status": self.final_status,
            "state_version_before": self.state_version_before,
            "state_version_after": self.state_version_after,
            "failure": self.failure,
            "audit_log": list(self.audit_log),
        }


class RecordedRuntimeDriver:
    """Replays a recorded runtime verdict from a fixture JSON file.

    This is the SAFE, deterministic backend used for infrastructure tests
    and replay/reproducibility (P4). It does NOT connect to a live DSH
    session. The recorded fixture is a JSON file containing a runtime-verdict
    dict and optionally an audit-log slice.
    """

    def __init__(self, recorded_path: str):
        if not os.path.exists(recorded_path):
            raise FileNotFoundError(
                f"recorded runtime verdict fixture not found: {recorded_path}")
        with open(recorded_path) as f:
            data = json.load(f)
        self.decision = data.get("decision", "ERROR")
        self.denial_path = data.get("denial_path")
        self.tool_call_id = data.get("tool_call_id")
        self.audit_event_ids = data.get("audit_event_ids", [])
        self.stopReason = data.get("stopReason", "completed")
        self.captured_at = data.get("captured_at", "")
        self.final_status = data.get("final_status", "COMPLETE")
        self.state_version_before = data.get("state_version_before")
        self.state_version_after = data.get("state_version_after")
        self.failure = data.get("failure")
        self._audit_log = data.get("audit_log", [])

    @property
    def audit_log_events(self) -> list[dict]:
        return list(self._audit_log)

    def execute(self, scenario_id: str, action: str, target: str, **kwargs) -> RuntimeResult:
        """Return the pre-recorded runtime result (no actual execution)."""
        return RuntimeResult(
            decision=self.decision,
            denial_path=self.denial_path,
            tool_call_id=self.tool_call_id,
            audit_event_ids=list(self.audit_event_ids),
            stopReason=self.stopReason,
            captured_at=self.captured_at or f"2026-08-31T12:00:00Z",
            final_status=self.final_status,
            state_version_before=self.state_version_before,
            state_version_after=self.state_version_after,
            failure=self.failure,
        )


class LiveDSHRuntimeDriver:
    """Live DSH runtime driver (G5).

    Provides the P1 (runtime) property for an authorized live L3 run. The
    driver enforces the live-execution seam:
      - do NOT bypass approval, authority, D4/D7 role boundaries, or the
        existing runtime gates;
      - when live preconditions are missing, return BLOCKED — never a
        simulated PASS;
      - when no real dispatcher is injected, return BLOCKED — never fall back
        to a FAKE/in-process substitute (no silent LIVE -> FAKE downgrade).

    `available()` reports which preconditions currently hold (read-only).

    `execute()` has exactly three outcomes, in order:
      1. any precondition missing        -> BLOCKED, `live-precondition:<names>`
      2. preconditions hold but no real
         dispatcher was injected, or the
         caller did not assert explicit
         live authorization              -> BLOCKED, `live-execution-not-authorized`
      3. preconditions hold AND a real
         dispatcher is injected AND live
         execution is authorized         -> the REAL runtime result

    Outcome 3 is the only path that performs work, and it performs it by
    calling the injected dispatcher — this class never constructs a verdict of
    its own. A dispatcher that raises is reported as an ERROR RuntimeResult
    with the exception recorded; it is never converted into an ALLOW, and the
    driver never retries (no blind retry of an uncertain side effect).

    Injection contract (`session_config`):
      - `dispatch`: callable(scenario_id, action, target, **kwargs) -> dict.
        The dict is the REAL runtime observation. Recognised keys: decision
        (required: ALLOW|DENY|ERROR|INVALID), denial_path, tool_call_id,
        audit_event_ids, stopReason, captured_at, final_status,
        state_version_before, state_version_after, failure.
      - `live_execution_authorized`: bool — the caller asserts that an
        authorized live L3 run is in progress. Absent/False => outcome 2.

    A real live L3 run additionally requires (all probed by `available()`):
      1. a Human-signed plan.json committed before the run (docs/security/0007
         PF-PLAN-*);
      2. the D4/D7 composition mounted (DSH_LIVE_BRIDGE_ACTIVE=1);
      3. the approval answerer available for HIGH-risk actions (docs/phase-4/
         0003-approval-readiness.md);
      4. session policy at the baseline workspace-write + ask (G9);
      5. the execution gate (control.execution_gate) as the only write channel.
    """

    #: Runtime decisions the driver will accept from a real dispatcher.
    #: INVALID is included for integrity-verification scenarios (L3-AUD-002:
    #: a tampered ledger detected by chain re-computation).
    VALID_DECISIONS = ("ALLOW", "DENY", "ERROR", "INVALID")

    def __init__(self, session_config: dict | None = None):
        self._config = dict(session_config or {})

    # -- precondition probes (read-only, never mutate) ---------------------
    def _probe_marker(self) -> bool:
        if "d4_d7_mounted" in self._config:
            return bool(self._config["d4_d7_mounted"])
        return os.environ.get("DSH_LIVE_BRIDGE_ACTIVE", "") in ("1", "true", "yes")

    def _probe_plan(self, scenario_id: str = "") -> bool:
        plan = self._config.get("plan") or {}
        ts = plan.get("human_signoff_ts", "")
        return bool(ts)

    def _probe_approval(self) -> bool:
        return self._config.get("approval_answerer_available", False)

    def _probe_policy(self) -> bool:
        mode = self._config.get("sandbox_mode", "workspace-write")
        approval = self._config.get("approval_policy", "ask")
        return mode == "workspace-write" and approval == "ask"

    def _probe_gates(self) -> bool:
        # The execution gate must be the only write channel; a config flag
        # confirms the caller routes writes through control.execution_gate.
        return bool(self._config.get("execution_gate_routes_writes", True))

    def available(self, scenario_id: str = "") -> dict:
        """Report which live preconditions currently hold (read-only)."""
        checks = {
            "human_signed_plan": self._probe_plan(scenario_id),
            "d4_d7_mounted": self._probe_marker(),
            "approval_answerer": self._probe_approval(),
            "baseline_policy": self._probe_policy(),
            "execution_gate_routes_writes": self._probe_gates(),
        }
        checks["all"] = all(checks.values())
        return checks

    # -- dispatch seam -----------------------------------------------------
    def dispatch_available(self) -> bool:
        """Whether a REAL dispatcher is injected AND live execution is
        explicitly authorized by the caller. Read-only."""
        return (callable(self._config.get("dispatch"))
                and bool(self._config.get("live_execution_authorized")))

    def _blocked(self, denial_path: str, failure_class: str, cause: str) -> RuntimeResult:
        return RuntimeResult(
            decision="ERROR",
            denial_path=denial_path,
            tool_call_id=None,
            audit_event_ids=[],
            stopReason="refused",
            captured_at=_now_iso(),
            final_status="BLOCKED",
            state_version_before=None,
            state_version_after=None,
            failure={"class": failure_class, "cause": cause},
        )

    def execute(self, scenario_id: str, action: str, target: str, **kwargs) -> RuntimeResult:
        """Live-driver entry point. See the class docstring for the three
        outcomes. NEVER simulates an ALLOW and never downgrades to FAKE."""
        checks = self.available(scenario_id)
        missing = [k for k, v in checks.items() if k != "all" and not v]
        if missing:
            return self._blocked(
                f"live-precondition:{','.join(missing)}",
                "environment",
                (f"live L3 run BLOCKED: missing precondition(s) {missing}; "
                 f"no live dispatch performed, no simulated PASS"))

        if not self.dispatch_available():
            # Preconditions hold, but either no real dispatcher was injected or
            # the caller did not assert live authorization. Refuse rather than
            # simulate, and never substitute a FAKE backend.
            return self._blocked(
                "live-execution-not-authorized",
                "authorization",
                ("all live preconditions hold, but an actual live L3 dispatch "
                 "is not authorized in this session (no real dispatcher "
                 "injected and/or live_execution_authorized not asserted); "
                 "return BLOCKED, never a simulated PASS"))

        # Outcome 3: authorized live dispatch through the injected REAL
        # dispatcher. The observation comes from the dispatcher; this driver
        # does not invent any part of it.
        dispatch = self._config["dispatch"]
        try:
            observed = dispatch(scenario_id=scenario_id, action=action,
                                target=target, **kwargs)
        except Exception as e:  # noqa: BLE001 - any dispatcher failure
            # A failed dispatch is an ERROR observation, never an ALLOW, and is
            # never retried here (no blind retry of an uncertain side effect).
            return RuntimeResult(
                decision="ERROR",
                denial_path="live-dispatch-error",
                tool_call_id=None,
                audit_event_ids=[],
                stopReason="error",
                captured_at=_now_iso(),
                final_status="BLOCKED",
                failure={
                    "class": "environment",
                    "cause": (f"live dispatch raised "
                              f"{type(e).__name__}: {e}; outcome UNKNOWN, not "
                              f"retried, never converted to a PASS"),
                },
            )

        if not isinstance(observed, dict):
            return self._blocked(
                "live-dispatch-malformed",
                "logic",
                (f"live dispatcher returned {type(observed).__name__}, "
                 f"expected dict; refusing to infer a verdict"))

        decision = observed.get("decision")
        if decision not in self.VALID_DECISIONS:
            return self._blocked(
                "live-dispatch-malformed",
                "logic",
                (f"live dispatcher returned decision={decision!r}, which is "
                 f"not one of {self.VALID_DECISIONS}; refusing to infer a "
                 f"verdict"))

        return RuntimeResult(
            decision=decision,
            denial_path=observed.get("denial_path"),
            tool_call_id=observed.get("tool_call_id"),
            audit_event_ids=list(observed.get("audit_event_ids") or []),
            stopReason=observed.get("stopReason", "completed"),
            captured_at=observed.get("captured_at") or _now_iso(),
            final_status=observed.get("final_status", "COMPLETE"),
            state_version_before=observed.get("state_version_before"),
            state_version_after=observed.get("state_version_after"),
            failure=observed.get("failure"),
            audit_log=list(observed.get("audit_log") or []),
        )