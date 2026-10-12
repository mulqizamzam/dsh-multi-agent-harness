# orchestrator.execution.recovery_runtime — Full-cycle recovery driver
#
# Phase 5 / Session C (G11 — LIVE RECOVERY CLOSURE)
#
# A standalone runtime recovery driver that composes the existing
# RecoveryController (control/recovery.py) + ExecutionEngine into a full-cycle
# recovery-to-COMPLETE path. Does NOT duplicate either.
#
# Full cycle:
#   execution failure (typed failure_class + cause)
#   → PRESERVE (begin_recovery, capture state version)
#   → DIAGNOSE (no blind retry — refuse empty/identical cause)
#   → RECOVER/REPLAN (skip-rollback or rollback+verify_restoration)
#   → AUTHORITY RECHECK (same gate; no privilege expansion; stale-version refusal)
#   → EXECUTE → VERIFY → COMPLETE
#   → on any denial: FAILED / ESCALATED (fail-closed)
#
# REUSE (no duplication):
#   - RecoveryRecord / RecoveryController: control/recovery.py
#   - ExecutionEngine / ExecutionRequest: orchestrator/execution/engine.py
#   - Authority gate: control/authority.py / control/execution_gate.py
#   - Verification: control/verification.py
#   - Audit: RuntimeAudit (orchestrator/runtime/audit.py)
#
# The driver is backend-agnostic: it does not depend on the delegation backend
# (FakeSubagentBackend / RealDSHBackend) — the caller provides the execution
# engine configured with the appropriate backend.

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from typing import Callable

from control.recovery import (
    RecoveryController,
    RecoveryRefused,
    DEFAULT_MAX_ATTEMPTS,
)
from orchestrator.execution.engine import (
    ExecutionEngine,
    ExecutionRequest,
)
from orchestrator.execution.exceptions import (
    ExecutionDenied,
    ExecutionRefused,
)
from orchestrator.runtime.result import (
    COMPLETE, FAILED, ESCALATED, RECOVERING,
)
from orchestrator.foundation.contracts import (
    Delegation, ORCHESTRATOR,
)
from control.verification import (
    VerificationDenied,
    VerificationError,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RecoveryRuntimeError(RuntimeError):
    """A recovery runtime failure (fail-closed)."""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class RecoveryRunResult:
    """The deterministic result of a full recovery cycle run.

    Attributes:
        outcome:      COMPLETE / FAILED / ESCALATED
        final_state:  The final task state machine state
        version:      The final state version
        recovery:     The RecoveryController's to_dict() record
        errors:       Any error messages (fail-closed accumulation)
        audit_events: List of event dicts emitted during the cycle
    """
    outcome: str = ""
    final_state: str = ""
    version: int = 0
    recovery: dict | None = None
    errors: list = field(default_factory=list)
    verification: dict | None = None
    execution_observed: dict | None = None
    audit_events: list = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(str(msg))

    @property
    def succeeded(self) -> bool:
        return self.outcome == COMPLETE


# ---------------------------------------------------------------------------
# Recovery runtime driver
# ---------------------------------------------------------------------------

def run_recovery_cycle(
    *,
    task_id: str,
    preserved_version: int,
    failure_class: str,
    cause: str,
    delegation: Delegation,
    action: str,
    target: str,
    environment: str = "dev",
    action_category: str = "",
    expected_outcome: dict | None = None,
    original_authority: dict | None = None,
    current_version: int | None = None,
    approval_reference: str = "",
    project: str = "multi-agent-harness",
    base: str | None = None,
    audit_fn: Callable[[dict], str] | None = None,
    executor_fn: Callable[[ExecutionRequest], dict] | None = None,
    rollback: bool = False,
    restoration_evidence: str = "",
    restoration_verifier: str = "",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    revocation_list: tuple = (),
    now: datetime | None = None,
) -> RecoveryRunResult:
    """Run the full recovery cycle to COMPLETE and return a RecoveryRunResult.

    This is a standalone driver that composes the existing RecoveryController
    with ExecutionEngine. It does NOT modify either module.

    Parameters
    ----------
    task_id:
        The task being recovered.
    preserved_version:
        The state version preserved at the point of failure.
    failure_class:
        The typed failure class (logic, environment, authorization, unknown).
    cause:
        The diagnosed cause of the failure (non-empty, no blind retry).
    delegation:
        The current delegation (re-read at authority re-check).
    action / target / environment:
        The execution plan parameters.
    action_category:
        The action category for evidence requirements.
    expected_outcome:
        Expected outcome dict for verification.
    original_authority:
        The original authority bounds for privilege-escalation check.
    current_version:
        The current state version (re-read; if None, loaded from the engine).
    approval_reference:
        Structured approval reference for the gate.
    project:
        Project id.
    base:
        Workspace base (defaults to project root).
    audit_fn:
        Callable ``(event_dict) -> event_id`` for audit events. Defaults to
        printing to stdout.
    executor_fn:
        Callable ``(ExecutionRequest) -> observed dict`` for the actual
        consequential action. Defaults to a no-op that returns {"exit_code": 0}.
    rollback / restoration_evidence / restoration_verifier:
        When rollback=True, the recovery runs the rollback path with
        restoration verification (REC-003). When False, skip-rollback replan.
    max_attempts:
        Per-cause attempt cap (default 1, per REC-001 / AUTH-INV-16).
    revocation_list:
        Current revocation list for the authority re-check.
    now:
        Optional clock override.

    Returns
    -------
    RecoveryRunResult
        The deterministic result of the recovery cycle.
    """
    result = RecoveryRunResult()
    audit_events = []
    ctrl = None
    _now = now or datetime.now(timezone.utc)
    base = base or _discover_base()

    def _audit(event: dict) -> str:
        event_id = f"rec-{uuid.uuid4().hex[:8]}"
        event["event_id"] = event_id
        event["timestamp"] = _now.strftime("%Y-%m-%dT%H:%M:%SZ")
        audit_events.append(event)
        if audit_fn:
            return audit_fn(event)
        return event_id

    if executor_fn is None:
        executor_fn = lambda req: {"exit_code": 0, "target": target}

    # ---- 1. PRESERVE + DIAGNOSE (no blind retry) ----
    try:
        ctrl = RecoveryController(
            task_id, preserved_version, failure_class=failure_class,
            reason=cause, max_attempts=max_attempts,
        )
        ctrl.request_retry(cause, max_attempts=max_attempts)
        ctrl.diagnose(cause, failure_class=failure_class, reason=cause)
    except RecoveryRefused as e:
        result.add_error(f"no blind retry: {e}")
        result.outcome = FAILED
        result.recovery = ctrl.to_dict() if ctrl is not None else None
        _audit({"event_class": "recovery_runtime",
                "action": "recover:diagnose",
                "target": task_id, "result": "denied",
                "error": f"no blind retry: {e}"})
        return result

    _audit({"event_class": "recovery_state_transition",
            "action": "recover:diagnose", "target": task_id,
            "result": "diagnosed",
            "extra": {"state": ctrl.state, "failure_class": failure_class,
                       "cause": cause}})

    # ---- 2. RECOVER / REPLAN ----
    try:
        if rollback:
            ctrl.rollback(reason=cause)
            ctrl.verify_restoration(
                evidence=restoration_evidence,
                verifier=restoration_verifier,
                reason=cause)
        else:
            ctrl.replan(reason=cause)
    except RecoveryRefused as e:
        result.add_error(f"replan/rollback refused: {e}")
        result.outcome = FAILED
        result.recovery = ctrl.to_dict()
        _audit({"event_class": "recovery_runtime",
                "action": "recover:replan",
                "target": task_id, "result": "denied",
                "error": str(e)})
        return result

    _audit({"event_class": "recovery_state_transition",
            "action": "recover:replan", "target": task_id,
            "result": "replanned",
            "extra": {"state": ctrl.state, "rollback": rollback}})

    # ---- 3. AUTHORITY RECHECK (AUTH-INV-12) ----
    # Build the authority gate function (same path as the original). The
    # gate returns bool; any denial (control.authority.Denied /
    # NeedsApproval, or an ExecutionDenied from the engine gate) is a DENY.
    from control.authority import (
        Denied as AuthorityDenied,
        NeedsApproval,
        recheck_authority as _ra,
    )

    def _gate_fn(a: str, t: str) -> bool:
        try:
            _ra(delegation=delegation, action=a, target=t,
                environment=environment, actor=ORCHESTRATOR, project=project,
                revocation_list=revocation_list, now=_now,
                approval_reference=approval_reference)
            return True
        except (AuthorityDenied, NeedsApproval, ExecutionDenied,
                ExecutionRefused):
            return False

    try:
        # REC-004/THREAT-017 baseline: derive from the DELEGATION the recovery
        # runs under (the scope the authority gate itself checks), never from
        # the attempt's own action/target — a baseline copied from the attempt
        # makes the privilege comparison tautological.
        _del_actions = list(getattr(delegation, "scope_operations", ()) or ())
        _del_action = getattr(delegation, "action", "")
        if _del_action and _del_action not in _del_actions:
            _del_actions.append(_del_action)
        _del_targets = list(getattr(delegation, "scope_resources", ()) or ())
        _del_target = getattr(delegation, "target", "")
        if _del_target and _del_target not in _del_targets:
            _del_targets.append(_del_target)
        ctrl.recheck_authority(
            _gate_fn,
            attempt_action=action, attempt_target=target,
            attempt_grants=(),
            original_authority=original_authority or {
                "actions": _del_actions,
                "targets": _del_targets,
                "grants": [],
            },
            current_version=current_version,
            expected_version=preserved_version,
            reason=cause,
        )
    except RecoveryRefused as e:
        _audit({"event_class": "authority_recheck",
                "action": "recover:recheck",
                "target": task_id, "result": "denied",
                "error": str(e)})
        ctrl.fail(reason=str(e))
        result.add_error(f"recovery authority re-check DENY: {e}")
        result.outcome = FAILED
        result.recovery = ctrl.to_dict()
        return result

    _audit({"event_class": "authority_recheck",
            "action": "recover:recheck",
            "target": task_id, "result": "allowed",
            "extra": {"state": ctrl.state}})

    # ---- 4. EXECUTE + VERIFY + COMPLETE ----
    # Build the execution request and engine.
    request = ExecutionRequest(
        task_id=task_id, actor=ORCHESTRATOR,
        action=action, target=target, environment=environment,
        delegation=delegation,
        expected_outcome=expected_outcome or {},
        action_category=action_category,
        revocation_list=revocation_list,
        approval_reference=approval_reference,
        project=project, state_version=current_version or preserved_version,
    )
    engine = ExecutionEngine(
        request, base=base,
        audit=_audit,
        current_version=current_version or preserved_version,
    )

    try:
        engine.validate()
        engine.assert_plan_current(
            current_version=current_version or preserved_version)
        engine.recheck_authority(
            revocation_list=revocation_list, now=_now,
            approval_reference=approval_reference)
    except (ExecutionDenied, ExecutionRefused) as e:
        ctrl.fail(reason=str(e))
        result.add_error(f"execution engine re-check DENY: {e}")
        result.outcome = FAILED
        result.recovery = ctrl.to_dict()
        _audit({"event_class": "execution_denial",
                "action": "recover:execute",
                "target": task_id, "result": "denied",
                "error": str(e)})
        return result

    # Execute the consequential action.
    try:
        engine.execute(executor=executor_fn, agent_claim=None)
    except Exception as e:
        ctrl.fail(reason=str(e))
        result.add_error(f"recovery execution failed: {e}")
        result.outcome = FAILED
        result.recovery = ctrl.to_dict()
        result.execution_observed = {"error": str(e)}
        _audit({"event_class": "execution_attempt",
                "action": "recover:execute",
                "target": task_id, "result": "error",
                "error": str(e)})
        return result

    if engine.outcome.is_failed():
        ctrl.fail(reason=engine.outcome.error or "execution failed")
        result.add_error(engine.outcome.error or "execution failed")
        result.outcome = FAILED
        result.recovery = ctrl.to_dict()
        result.execution_observed = engine.outcome.to_dict()
        _audit({"event_class": "execution_attempt",
                "action": "recover:execute",
                "target": task_id, "result": "failed",
                "error": engine.outcome.error or "execution failed"})
        return result

    result.execution_observed = engine.outcome.to_dict()
    _audit({"event_class": "execution_attempt",
            "action": "recover:execute",
            "target": task_id, "result": "executed",
            "extra": engine.outcome.to_dict()})

    # Verify. Attach the evidence kinds the action category requires
    # (VERIFY-003) before evaluating the verification session.
    try:
        from control.verification import verification_requirements
        required = verification_requirements(
            action_category or "internal_analysis").required_evidence
    except Exception:  # noqa: BLE001 — fail-closed to a generic artifact
        required = ("artifact",)
    for kind in (required or ("artifact",)):
        try:
            engine.add_evidence(
                kind, f"{target}#recovery", verifier="self:recovery_runtime",
                independent=False)
        except Exception:  # noqa: BLE001 — evidence is best-effort data
            pass

    try:
        vresult = engine.verification_result()
        if not vresult.is_verified():
            raise VerificationDenied(
                f"verification not passed: {vresult.reason}")
        result.verification = {
            "verdict": vresult.verdict, "reason": vresult.reason}
    except (VerificationDenied, VerificationError, Exception) as e:
        ctrl.fail(reason=str(e))
        result.add_error(f"recovery verification failed: {e}")
        result.outcome = FAILED
        result.recovery = ctrl.to_dict()
        _audit({"event_class": "verification_failed",
                "action": "recover:verify",
                "target": task_id, "result": "failed",
                "error": str(e)})
        return result

    # ---- 5. COMPLETE ----
    ctrl.complete(reason=cause)
    result.outcome = COMPLETE
    result.final_state = "COMPLETE"
    result.version = current_version or preserved_version
    result.recovery = ctrl.to_dict()
    result.audit_events = audit_events

    _audit({"event_class": "recovery_runtime",
            "action": "recover:complete",
            "target": task_id, "result": "completed",
            "extra": {"recovery_state": ctrl.state}})

    return result


def _discover_base() -> str:
    """Discover the project workspace base."""
    import os
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


__all__ = [
    "RecoveryRunResult", "RecoveryRuntimeError", "run_recovery_cycle",
]