# orchestrator/execution/engine.py — Runtime execution assurance engine
#
# Binds the existing control-plane modules into one fail-closed runtime flow:
#
#   validate → assert_plan_current → recheck_authority → execute
#     → record observed/claim → add evidence → verification_result
#     → complete (ONLY on PASSED)              [AUTH-INV-15 / THREAT-016]
#     → on failure: classify_failure → recovery lifecycle
#        (STOP→PRESERVE→DIAGNOSE→ROLLBACK→VERIFY RESTORATION→REPLAN→
#         AUTHORITY RE-CHECK)                  [AUTH-INV-12/16, REC-001..005]
#
# The engine NEVER grants authority and NEVER bypasses a gate. It re-passes
# the SAME authority path the original action used (AUTH-INV-12):
#   - control.authority.recheck_authority — the structured authority gate
#   - control.execution_gate.authorize_write — the path-aware execution gate
#     for every write-class action (no unrestricted execution)
#   - control.verification.VerificationSession / VerificationGate — the
#     verification lifecycle (expected declared BEFORE execution)
#   - control.recovery.RecoveryController — the recovery lifecycle
#
# A reported success is NOT a verified success (THREAT-016). The engine only
# reports COMPLETE when the verification session evaluates to PASSED.

from __future__ import annotations

from dataclasses import dataclass

# Control-plane modules this engine binds (read-only reuse).
from control.authority import (
    Denied as AuthorityDenied,
    NeedsApproval,
    recheck_authority as _recheck_authority,
)
from control.execution_gate import (
    authorize_write,
    Denied as ExecutionGateDenied,
)
from control.recovery import RecoveryController
from control.verification import (
    VerificationSession,
    VerificationGate,
    VerificationResult,
    VerificationDenied,
    VerificationError,
)

from .exceptions import (
    ExecutionError,
    ExecutionDenied,
    ExecutionRefused,
    VerificationRefused,
)
from .request import ExecutionRequest


# ---------------------------------------------------------------------------
# Actual outcome capture
# ---------------------------------------------------------------------------

@dataclass
class ExecutionOutcome:
    """The ACTUAL outcome of an execution attempt.

    observed:     the structured actual outcome captured AFTER execution
                  (VERIFY-001: compared against the expected outcome).
    agent_claim:  the status the agent REPORTED (e.g. "SUCCEEDED"). A claim is
                  NOT verification (THREAT-016 / AUTH-INV-15).
    error:        the error string when the execution attempt failed.
    """
    observed: dict | None = None
    agent_claim: str | None = None
    error: str = ""

    def is_failed(self) -> bool:
        return bool(self.error)

    def to_dict(self) -> dict:
        return {
            "observed": dict(self.observed or {}),
            "agent_claim": self.agent_claim,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------

def classify_failure(error) -> tuple[str, str]:
    """Classify a runtime failure into (failure_class, cause).

    Failure classes (state/helpers/recovery.py): environment | logic |
    authorization | unknown. Unknown is MANDATORY escalation — never guess
    (Runbook 08).

    Mapping (Runbook 07 §DIAGNOSE):
      - authority denial / approval-needs         → authorization
      - OS / IO / permission / path errors         → environment
      - schema / validation / contract / verification errors → logic
      - anything else                              → unknown
    """
    if isinstance(error, (AuthorityDenied, NeedsApproval)):
        return ("authorization", str(error))
    if isinstance(error, (OSError, IOError, PermissionError,
                          FileNotFoundError, ExecutionGateDenied)):
        return ("environment", str(error))
    if isinstance(error, (ValueError, TypeError, VerificationError,
                          VerificationDenied)):
        return ("logic", str(error))
    return ("unknown", str(error))


# ---------------------------------------------------------------------------
# The runtime execution engine
# ---------------------------------------------------------------------------

class ExecutionEngine:
    """Runtime execution assurance engine.

    Parameters
    ----------
    request:
        The structured ExecutionRequest (action/target/environment/authority/
        expected outcome/plan version).
    base:
        The workspace base for the path-aware execution gate. Optional (gate
        defaults to the multi-agent-harness root).
    state_machine:
        Optional orchestrator StateMachine to drive lifecycle transitions
        (EXECUTING → COLLECTED → SYNTHESIZING → COMPLETE; RECOVERING on
        failure).
    audit:
        Optional callable `fn(event: dict) -> None` invoked at each runtime
        event (execution_attempt / verification / recovery_state_transition /
        execution_denial). Records data only, never authority (AUTH-INV-14).
    """

    def __init__(self, request: ExecutionRequest, *, base=None,
                 state_machine=None, audit=None, current_version=None):
        if not isinstance(request, ExecutionRequest):
            raise ExecutionError("engine requires an ExecutionRequest")
        self.request = request
        self.base = base
        self.state_machine = state_machine
        self.audit = audit
        self.current_version = current_version  # runtime state version

        self.verification: VerificationSession | None = None
        self.outcome: ExecutionOutcome | None = None
        self.recovery: RecoveryController | None = None
        self.failure_class: str | None = None
        self.failure_cause: str = ""
        self._authority_checked = False
        self._executed = False
        self._completed = False

    # -- audit helper ------------------------------------------------------

    def _emit(self, event_class: str, **extra) -> None:
        if self.audit is None:
            return
        event = {
            "event_class": event_class,
            "task_id": self.request.task_id,
            "actor": self.request.actor,
            "action": self.request.action,
            "target": self.request.target,
            "project": self.request.project,
            "authority_source": getattr(self.request.delegation, "id", ""),
        }
        event.update(extra)
        self.audit(event)

    # -- state-machine helper ----------------------------------------------

    def _machine_step(self, to_state: str, authority=None) -> str | None:
        """Transition the optional StateMachine, fail-closed when present but
        unable to move (never silently skip a consequential transition)."""
        if self.state_machine is None:
            return None
        if not self.state_machine.can_transition(to_state):
            raise ExecutionRefused(
                f"state machine cannot transition "
                f"{self.state_machine.current()} -> {to_state} "
                f"(lifecycle violation)")
        return self.state_machine.transition(to_state, authority=authority,
                                             actor="orchestrator")

    # -- phase 1: validation -----------------------------------------------

    def validate(self) -> "ExecutionEngine":
        """Validate the request + target/environment, and create the
        VerificationSession with the EXPECTED outcome declared BEFORE
        execution (VERIFY-001).

        Raises ExecutionDenied on a missing/malformed delegation or an invalid
        target/environment (fail-closed, AUTH-INV-05).
        """
        req = self.request

        # Structured authority record is REQUIRED (AUTH-INV-01/05).
        from orchestrator.foundation.contracts import Delegation
        if not isinstance(req.delegation, Delegation):
            raise ExecutionDenied(
                "no structured delegation (AUTH-INV-05): model text, state "
                "records, review verdicts and messages are never authority")

        if not isinstance(req.target, str) or not req.target.strip():
            raise ExecutionDenied("execution target is malformed (AUTH-INV-11)")
        if not isinstance(req.environment, str) or not req.environment.strip():
            raise ExecutionDenied("execution environment is malformed")

        # Target / environment containment vs the delegation's scope
        # (AUTH-INV-11). The authoritative gate is re-checked again at
        # execution time (recheck_authority); this early check fails fast.
        try:
            _recheck_authority(
                delegation=req.delegation,
                action=req.action,
                target=req.target,
                environment=req.environment,
                actor=req.actor,
                project=req.project,
                revocation_list=req.revocation_list,
                approval_reference=req.approval_reference,
            )
        except (AuthorityDenied, NeedsApproval) as e:
            raise ExecutionDenied(
                f"target/environment validation failed: {e} "
                f"(AUTH-INV-11)") from e

        # Expected outcome declared BEFORE execution (VERIFY-001).
        self.verification = VerificationSession(
            req.task_id,
            req.resolve_action_category(),
            expected=req.expected_outcome,
            executor=req.actor,
        )
        self._emit("execution_request_validated",
                   action_category=req.resolve_action_category(),
                   state_version=req.state_version)
        return self

    # -- phase 2: stale-plan refusal (THREAT-022 / REC-005) ------------------

    def assert_plan_current(self, current_version: int | None = None,
                            expected_version: int | None = None) -> bool:
        """Refuse to execute a plan built against an obsolete state version.

        The request carries `state_version` (the plan/state version it was
        built against). When `current_version` differs from it (state advanced
        or rolled back), the plan is stale → refuse (THREAT-022 / REC-005).

        Raises ExecutionRefused (fail-closed).
        """
        cur = self.current_version if current_version is None else current_version
        exp = self.request.state_version if expected_version is None else expected_version
        if cur is None:
            raise ExecutionRefused(
                "cannot execute without the current state version — re-read "
                "current state and re-validate (THREAT-022)")
        if exp is None or exp <= 0:
            return True  # plan carries no version to compare (untracked)
        # Test the rollback case FIRST: `cur != exp` (below) subsumes it, so an
        # ordered `cur < exp` after `cur != exp` would be unreachable and the
        # distinct "rolled back" diagnostic lost (F5).
        if cur < exp:
            raise ExecutionRefused(
                f"state rolled back below the plan version {exp} (THREAT-022)")
        if cur != exp:
            raise ExecutionRefused(
                f"stale plan refused: request built against state version {exp}, "
                f"current is {cur} (THREAT-022 / REC-005)")
        return True

    # -- phase 3: execution-time authority re-check (AUTH-INV-05/06/11/18) ---

    def recheck_authority(self, *, action: str | None = None,
                          target: str | None = None,
                          environment: str | None = None,
                          revocation_list=None,
                          approval_reference: str | None = None,
                          now=None) -> bool:
        """Execution-time authority re-check + path-aware execution gate.

        Runs the SAME authority gate the original action used against the
        CURRENT delegation record (expiry/revocation re-checked at execution
        time — THREAT-008/009/024), and the SAME path-aware execution gate
        for every write-class action (no unrestricted execution).

        Raises ExecutionDenied on any denial (fail-closed, AUTH-INV-20).
        """
        req = self.request
        act = action or req.action
        tgt = target or req.target
        env = environment or req.environment
        rev_list = tuple(req.revocation_list) if revocation_list is None \
            else tuple(revocation_list)
        appr = req.approval_reference if approval_reference is None \
            else approval_reference

        # 1. Structured authority gate (AUTH-INV-01/05/06/11/18).
        try:
            _recheck_authority(
                delegation=req.delegation,
                action=act,
                target=tgt,
                environment=env,
                actor=req.actor,
                project=req.project,
                revocation_list=rev_list,
                approval_reference=appr,
                now=now,
            )
        except NeedsApproval as e:
            self._emit("execution_denial", result="escalated", error=str(e))
            raise ExecutionDenied(f"execution needs approval: {e}") from e
        except AuthorityDenied as e:
            self._emit("execution_denial", result="denied", error=str(e))
            raise ExecutionDenied(f"execution-time authority DENIED: {e}") from e

        # 2. Path-aware execution gate for write-class actions (no
        #    unrestricted execution). The gate governs the canonical write
        #    actions; a write-like action class (e.g. code_write, deploy,
        #    rollback) is normalized to the canonical "write" action so the
        #    protected-path / traversal / boundary checks always apply.
        if ExecutionRequest.is_write_class(req):
            try:
                authorize_write("write", tgt, base=self.base)
            except ExecutionGateDenied as e:
                self._emit("execution_denial", result="denied", error=str(e))
                raise ExecutionDenied(f"execution path gate DENIED: {e}") from e

        self._authority_checked = True
        self._emit("authority_recheck", result="ALLOW",
                   action=act, target=tgt, environment=env)
        return True

    # -- phase 4: execute + actual outcome capture --------------------------

    def execute(self, executor=None, *, observed: dict | None = None,
                agent_claim: str | None = None) -> "ExecutionEngine":
        """Execute the action and capture the ACTUAL outcome.

        Parameters
        ----------
        executor:
            Optional callable `fn(request) -> dict | None`. When provided, it
            performs the actual side-effect and returns the observed outcome
            dict. A raised exception is classified as a failure and routed to
            the recovery lifecycle.
        observed:
            The actual outcome dict, when the caller performs the action
            itself (outside the engine). The engine still re-checks authority
            at execution time and records the outcome for verification.
        agent_claim:
            The status the agent REPORTED (e.g. "SUCCEEDED"). A claim is NOT
            verification (THREAT-016).

        Returns
        -------
        self (for chaining). Inspect `outcome` / `failure_class` after the
        call to decide recovery.
        """
        # Fail-closed preconditions: authority must have been re-checked and
        # the plan must be current.
        if not self._authority_checked:
            self.recheck_authority()
        if self.current_version is not None:
            self.assert_plan_current(self.current_version)

        try:
            if executor is not None:
                observed = executor(self.request)
        except Exception as e:  # noqa: BLE001 — classify and route to recovery
            self.failure_class, self.failure_cause = classify_failure(e)
            self.outcome = ExecutionOutcome(error=self.failure_cause)
            self._emit("execution_attempt", result="error",
                       failure_class=self.failure_class, error=self.failure_cause)
            # EXECUTING → RECOVERING (authority token: the recovery record is
            # created in begin_recovery; transition lazily there).
            return self

        self.outcome = ExecutionOutcome(
            observed=dict(observed or {}) if observed is not None else None,
            agent_claim=agent_claim,
        )
        self._executed = True
        self._emit("execution_attempt", result="executed")

        # Record the ACTUAL outcome + claim into the verification session.
        if self.verification is not None:
            if agent_claim:
                self.verification.record_agent_claim(agent_claim)
            if observed is not None:
                self.verification.record_observed(dict(observed))

        # EXECUTING → COLLECTED (results gathered).
        if self.outcome.observed is not None or self.outcome.error:
            self._machine_step("COLLECTED")
        return self

    # -- phase 5: verification ----------------------------------------------

    def record_observed(self, observed: dict) -> None:
        if self.verification is None:
            raise ExecutionError("validation required before recording observed")
        self.verification.record_observed(dict(observed))

    def record_agent_claim(self, status: str) -> None:
        if self.verification is None:
            raise ExecutionError("validation required before recording a claim")
        self.verification.record_agent_claim(status)

    def add_evidence(self, kind: str, source: str, *, verifier=None,
                     independent: bool = False,
                     human_confirmation: bool = False):
        """Add a verification evidence artifact (VERIFY-003)."""
        if self.verification is None:
            raise ExecutionError("validation required before adding evidence")
        return self.verification.add_evidence(
            kind, source, verifier=verifier, independent=independent,
            human_confirmation=human_confirmation)

    def verification_result(self) -> VerificationResult:
        """Evaluate the verification session. Raises ExecutionError if no
        verification session exists."""
        if self.verification is None:
            raise ExecutionError("validation required before verifying")
        return self.verification.evaluate()

    def can_complete(self) -> bool:
        """AUTH-INV-15: COMPLETE may only be emitted when the verification
        session evaluates to PASSED."""
        if self.verification is None:
            return False
        return self.verification.can_emit_complete()

    # -- phase 6: COMPLETE only after verified outcome (AUTH-INV-15) --------

    def complete(self) -> VerificationResult:
        """Emit COMPLETE ONLY when the verification session has PASSED.

        Raises VerificationRefused when the outcome is not verified (a
        reported success is NOT a verified success — THREAT-016).
        """
        if self.verification is None:
            raise ExecutionRefused("cannot COMPLETE before validation")
        gate = VerificationGate()
        try:
            result = gate.evaluate(self.verification)
        except VerificationDenied as e:
            self._emit("verification_denied", result="denied", error=str(e))
            raise VerificationRefused(str(e)) from e

        # COLLECTED → SYNTHESIZING → COMPLETE (verified outcome only).
        self._machine_step("SYNTHESIZING")
        self._machine_step("COMPLETE")
        self._completed = True
        self._emit("verification_passed", result="allowed",
                   verdict=result.verdict)
        return result

    # -- phase 7: failure classification + recovery lifecycle ----------------

    def classify_failure(self, error) -> tuple[str, str]:
        """Classify a runtime failure (delegates to the module-level
        classifier)."""
        self.failure_class, self.failure_cause = classify_failure(error)
        return (self.failure_class, self.failure_cause)

    def begin_recovery(self, cause: str, *, failure_class: str | None = None,
                       preserved_version: int | None = None,
                       reason: str = "") -> RecoveryController:
        """Start the recovery lifecycle (STOP → PRESERVE → DIAGNOSED).

        Creates a control.recovery.RecoveryController, records the diagnosed
        cause (no blind retry, AUTH-INV-16), and transitions the task state
        machine to RECOVERING (authority token = the recovery record, per
        orchestrator/foundation/state.py).
        """
        if self.recovery is not None:
            raise ExecutionRefused("recovery already begun for this task")
        cls = failure_class or self.failure_class or "unknown"
        self.recovery = RecoveryController(
            self.request.task_id,
            preserved_version if preserved_version is not None
            else self.request.state_version,
            failure_class=cls,
            reason=reason,
            max_attempts=self.request.max_attempts,
            max_rework_cycles=self.request.max_rework_cycles,
        )
        # PRESERVED → DIAGNOSED (a retry only on a NEW cause — no blind retry).
        self.recovery.diagnose(cause, failure_class=cls, reason=reason)
        # EXECUTING → RECOVERING (or FAILED → RECOVERING); the token is the
        # RecoveryRecord (data, never authority).
        self._machine_step("RECOVERING", authority=self.recovery.record)
        self._emit("recovery_state_transition", state=self.recovery.state,
                   failure_class=cls, cause=cause)
        return self.recovery

    def _same_gate(self, action: str, target: str) -> bool:
        """The SAME authority + path gate the original action used
        (AUTH-INV-12). Any denial is a recovery DENY (fail-closed)."""
        return self.recheck_authority(action=action, target=target)

    def recover(self, *, cause: str, failure_class: str | None = None,
                preserved_version: int | None = None,
                rollback: bool = False,
                restoration_evidence: str = "",
                restoration_verifier: str = "",
                attempt_action: str | None = None,
                attempt_target: str | None = None,
                attempt_grants: tuple = (),
                current_version: int | None = None,
                reason: str = "") -> RecoveryController:
        """Drive the full recovery cycle to completion.

        STOP → PRESERVE → DIAGNOSE → (ROLLBACK → VERIFY RESTORATION) →
        REPLAN → AUTHORITY RE-CHECK → COMPLETE.

        Authority re-check (AUTH-INV-12) is bounded to the ORIGINAL authority
        baseline (REC-004 / THREAT-017): the recovery attempt may not use an
        action/target/grants the original action did not have.

        Raises RecoveryRefused on any denial (fail-closed, AUTH-INV-20).
        """
        ctrl = self.begin_recovery(cause, failure_class=failure_class,
                                   preserved_version=preserved_version,
                                   reason=reason)
        # begin_recovery already transitioned to DIAGNOSED with the cause.

        if rollback:
            ctrl.rollback(reason=reason)
            ctrl.verify_restoration(
                evidence=restoration_evidence,
                verifier=restoration_verifier,
                reason=reason,
            )  # REC-003: independent restoration verification
        else:
            ctrl.replan(reason=reason)  # skip-rollback path

        act = attempt_action or self.request.action
        tgt = attempt_target or self.request.target
        ctrl.recheck_authority(
            self._same_gate,
            attempt_action=act,
            attempt_target=tgt,
            attempt_grants=attempt_grants,
            original_authority=self.request.original_authority(),
            current_version=current_version
            if current_version is not None else self.current_version,
            reason=reason,
        )
        ctrl.complete(reason=reason)
        self._emit("recovery_state_transition", state=ctrl.state,
                   failure_class=ctrl.record.failure_class, cause=cause,
                   result="completed")
        # RECOVERING → DELEGATED (re-planned under the same delegation).
        self._machine_step("DELEGATED", authority=self.request.delegation)
        return ctrl

    # -- retry budget (AUTH-INV-16 / REC-001) --------------------------------

    def request_retry(self, new_cause: str,
                      max_attempts: int | None = None) -> int:
        """Request a re-execution with a NEW diagnosed cause.

        Refuses blind retries and enforces the per-cause attempt cap
        (delegates to control.recovery.RecoveryController.request_retry).

        Raises RecoveryRefused (no blind retry / budget exhausted).
        """
        if self.recovery is None:
            raise ExecutionRefused("retry requires an active recovery")
        return self.recovery.request_retry(new_cause,
                                           max_attempts=max_attempts)

    # -- convenience --------------------------------------------------------

    def summary(self) -> dict:
        return {
            "task_id": self.request.task_id,
            "action": self.request.action,
            "target": self.request.target,
            "authority_checked": self._authority_checked,
            "executed": self._executed,
            "outcome": self.outcome.to_dict() if self.outcome else None,
            "failure_class": self.failure_class,
            "failure_cause": self.failure_cause,
            "verification": (
                self.verification.evaluate().__dict__
                if self.verification else None
            ),
            "recovery_state": self.recovery.state if self.recovery else None,
            "completed": self._completed,
            "state_machine_state": (
                self.state_machine.current() if self.state_machine else None
            ),
        }