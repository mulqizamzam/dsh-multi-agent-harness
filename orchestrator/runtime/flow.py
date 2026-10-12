# orchestrator.runtime.flow — ExecutionFlow coordinator (Phase 3)
#
# The production orchestrator runtime: turns the existing foundation/control
# contracts into an executable, bounded Execution Flow:
#
#   INTAKE → UNDERSTAND → CLASSIFY → RISK_GATE → DECOMPOSE → SELECT → DELEGATE
#   → EXECUTE_SUBTASKS → COLLECT → EVIDENCE_GATE → SYNTHESIZE → CONFLICT_GATE
#   → ADVERSARIAL_REVIEW → AUTHORITY_GATE → EXECUTE → VERIFY
#   → CLOSE / RECOVER / ESCALATE
#
# INVARIANTS ENFORCED (re-using existing control modules, adding nothing new)
#   - every consequential transition passes structured authority (AUTH-INV-01/07)
#   - execution-time authority re-check is MANDATORY (AUTH-INV-05/06/11/18)
#   - state/version is checked before consequential actions (THREAT-021/022)
#   - a failed/unresolved gate STOPS the flow (fail-closed, AUTH-INV-20)
#   - BadSector PASS never grants authority (AUTH-INV-09)
#   - subdelegation remains DENY BY DEFAULT (DLG-003)
#   - no blind retry (AUTH-INV-16/REC-001); recovery re-checks authority
#     (AUTH-INV-12), detects obsolete versions (THREAT-022)
#   - all consequential writes go through the project execution gate (ADR 0002)
#   - agent reports are DATA, never authority (AUTH-INV-13)
#
# REUSE (no duplication)
#   - delegation & subtask execution: orchestrator.dsh.DelegationClient
#   - execute/verify/recovery per action: orchestrator.execution.ExecutionEngine
#   - gates: control.* production modules via runtime.gates.GateRunner
#   - state: foundation StateMachine/ProjectState via runtime.lifecycle
#   - audit: runtime.audit via the sanctioned audit channel

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dataclasses import dataclass, field

from orchestrator.foundation.contracts import (
    TaskIntake, Task, Delegation, TaskResult, ORCHESTRATOR,
)
from orchestrator.foundation.routing import select_agents, validate_no_fanout
from orchestrator.dsh import (
    DelegationClient,
    FakeSubagentBackend,
    RealDSHBackend,
    BridgeNotAvailable,
    BackendKind,
    check_instance_mounted,
    BRIDGE_MARKER_ENV,
)

from .exceptions import (
    FlowStopped, GateDenied, GateEscalated, StaleStateDetected,
    AuthorityDenied, RecoveryRefusedByRuntime, RuntimeFlowError,
    SubtaskFailed, ParallelUnsafe,
)
from .audit import RuntimeAudit
from .store import RuntimeStore
from .delegation import (
    DelegationProvider, FileDelegationProvider, DelegationLifecycle,
)
from .gates import GateRunner
from .lifecycle import TaskLifecycle
from .parallel import (
    ParallelExecutor, assert_parallel_safe, build_plans, plan_waves,
    DEFAULT_MAX_WORKERS,
)
from .collection import collect_all, classify_adapter_failure
from .result import (
    FlowResult, COMPLETE, BLOCKED, FAILED, ESCALATED, RECOVERING,
)

# The ordered phase chain of the production runtime.
RUNTIME_PHASE_CHAIN = (
    "intake", "understand", "classify", "risk_gate", "decompose", "select",
    "delegate", "execute_subtasks", "collect", "evidence_gate", "synthesize",
    "conflict_gate", "adversarial_review", "authority_gate", "execute",
    "verify", "close",
)

# Write-class actions that MUST pass the path-aware execution gate.
_WRITE_ACTIONS = {"write", "edit", "create", "delete", "rename", "overwrite",
                  "truncate", "code_write", "deploy", "publish",
                  "production_deploy", "server_write", "credential_change",
                  "financial_transaction", "sensitive_publication"}


class ExecutionFailure(RuntimeFlowError):
    """An execution/verification failure that routes to the RECOVERING
    disposition (failure propagation -> recovery handoff). Carries the
    classified failure_class and cause for the RecoveryRecord."""

    def __init__(self, failure_class: str = "unknown", cause: str = "",
                 phase: str = ""):
        self.failure_class = failure_class
        self.cause = cause
        # The runtime phase the flow was actually in when the failure occurred
        # (e.g. "execute_subtasks"). Recorded at raise time so recovery reporting
        # cannot misreport the stopping phase from prose (F7).
        self.phase = phase
        super().__init__(
            f"execution failure ({failure_class}): {cause}")


@dataclass(frozen=True)
class ExecutePlan:
    """The concrete consequential action the flow executes after all gates.

    action / target / environment are the EXACT strings re-validated by the
    execution-time authority re-check and the execution gate.
    """
    action: str = "write"
    target: str = ""
    environment: str = "dev"
    expected_outcome: dict = field(default_factory=dict)
    action_category: str = ""
    description: str = ""


class ExecutionFlow:
    """The production orchestrator runtime coordinator.

    Parameters
    ----------
    project:
        Project id (default "multi-agent-harness").
    base:
        Workspace base for the execution gate / state / audit (defaults to the
        project root).
    provider:
        DelegationProvider (re-read at execution time). Defaults to the file
        registry provider.
    store / audit / gates / lifecycle / delegation_lifecycle:
        Injectables for tests; defaults are created on first use.
    subtask_runner:
        Callable ``(task, delegation) -> TaskResult`` that executes a
        specialist subtask. When omitted, the flow uses the dsh
        DelegationClient with an explicitly selected backend: the live
        ``RealDSHBackend`` when a ``live_dispatch`` is injected AND the D4/D7
        bridge marker (``DSH_LIVE_BRIDGE_ACTIVE``) is present; otherwise the
        deterministic in-process ``FakeSubagentBackend`` (unit-test default).
        If a live dispatch is injected but the bridge is unavailable the flow
        fails closed (BridgeNotAvailable -> BLOCKED) — it never silently runs
        the fake backend in place of a requested REAL run (G1).
    live_dispatch:
        The injected DSH bridge dispatch (``DSHBridgeDispatch`` or a callable
        ``(invocation, instance) -> DSHBridgeResponse``). Injecting one is an
        explicit request for REAL DSH execution; the selection is observable
        via ``backend_kind`` / ``probe_backend()``. Default None (deterministic
        fake path).
    executor:
        Callable ``(plan) -> observed dict`` that performs the consequential
        EXECUTE action. Default: writes a synthesis artifact through the
        project execution gate.
    pre_execute:
        Optional test/operator hook invoked immediately before the EXECUTE
        phase's version/authority re-check (e.g. to simulate a parallel
        writer that bumps the state version).
    now:
        Optional clock override (tests).
    parallel_subtasks:
        Run independent subtasks concurrently through the approved DSH adapter
        (default True). A batch that cannot be proven independent runs
        sequentially; the flag never forces an unsafe parallel run.
    max_workers:
        Bound on concurrent children in a parallel batch.
    """

    def __init__(self, *, project: str = "multi-agent-harness", base=None,
                 provider: DelegationProvider | None = None,
                 store: RuntimeStore | None = None,
                 audit: RuntimeAudit | None = None,
                 gates: GateRunner | None = None,
                 lifecycle: TaskLifecycle | None = None,
                 delegation_lifecycle: DelegationLifecycle | None = None,
                 subtask_runner=None, executor=None, pre_execute=None,
                 now=None, flow_id: str = "",
                 parallel_subtasks: bool = True,
                 max_workers: int = DEFAULT_MAX_WORKERS,
                 live_dispatch=None):
        self.project = project
        self.base = base
        self.provider = provider or FileDelegationProvider(base=base,
                                                           project=project)
        self._store_impl = store
        self._audit_impl = audit
        self._gates_impl = gates
        self._lifecycle_impl = lifecycle
        self._delegation_lifecycle = delegation_lifecycle or DelegationLifecycle()
        self._subtask_runner = subtask_runner
        self._live_dispatch = live_dispatch
        self.executor = executor
        self.pre_execute = pre_execute
        self._now = now
        self.flow_id = flow_id or f"flow-{uuid.uuid4().hex[:8]}"
        self.parallel_subtasks = parallel_subtasks
        self.max_workers = max_workers
        self._seq = 0
        # per-run state
        self._result: FlowResult | None = None
        self._task: Task | None = None
        self._delegation: Delegation | None = None
        self._child: Delegation | None = None
        self._execute_plan: ExecutePlan | None = None
        self._risk = "LOW"
        self._results: list = []
        self._collected: list = []
        self._recovery_controller = None
        self._verification_result = None
        # Data-only trace of withheld verification evidence artifacts (the
        # independent kinds of an independence-requiring category). Never
        # verification evidence itself.
        self._pending_independent_verification: list = []
        self._approval_reference = ""
        self._client: DelegationClient | None = None

    # ------------------------------------------------------------------
    # Lazy dependencies
    # ------------------------------------------------------------------

    def _get_store(self) -> RuntimeStore:
        if self._store_impl is None:
            self._store_impl = RuntimeStore(base=self.base, project=self.project)
        return self._store_impl

    def _get_audit(self) -> RuntimeAudit:
        if self._audit_impl is None:
            self._audit_impl = RuntimeAudit(base=self.base, project=self.project,
                                            now=self._now)
        return self._audit_impl

    def _get_gates(self) -> GateRunner:
        if self._gates_impl is None:
            self._gates_impl = GateRunner()
        return self._gates_impl

    def _get_lifecycle(self) -> TaskLifecycle:
        if self._lifecycle_impl is None:
            self._lifecycle_impl = TaskLifecycle(self._get_store(),
                                                 self._get_audit(),
                                                 project=self.project)
        return self._lifecycle_impl

    # -- backend selection (G1: explicit REAL / FAKE / UNAVAILABLE) ----------

    @property
    def backend_kind(self) -> BackendKind:
        """The decided delegation-backend kind, observable without running.

        - REAL        — a ``live_dispatch`` is injected AND the D4/D7 bridge
                        marker (``DSH_LIVE_BRIDGE_ACTIVE``) is present.
        - UNAVAILABLE — a ``live_dispatch`` was requested but the bridge is
                        not active (marker absent) — the flow will fail closed.
        - FAKE        — no live dispatch requested: deterministic default.

        This is a probe: it never dispatches and never mutates state.
        """
        if self._live_dispatch is None:
            return BackendKind.FAKE
        if check_instance_mounted("subagent_probe"):
            return BackendKind.REAL
        return BackendKind.UNAVAILABLE

    def probe_backend(self) -> dict:
        """Explicit availability probe (never dispatches).

        Returns the observable three-state decision plus the inputs that
        drove it, so an operator can see WHY the backend was chosen.
        """
        return {
            "backend_kind": self.backend_kind.value,
            "live_dispatch_injected": self._live_dispatch is not None,
            "bridge_marker_active": check_instance_mounted("subagent_probe"),
            "marker_env": BRIDGE_MARKER_ENV,
        }

    def _select_backend(self):
        """Explicit, fail-closed backend selection.

        Returns a ``DelegationBackend`` for the decided kind.  Raises
        ``BridgeNotAvailable`` when a REAL dispatch was requested but the
        bridge is unavailable — it NEVER silently falls back to the fake
        backend (no silent fallback; requirement G1-3).
        """
        kind = self.backend_kind
        if kind is BackendKind.REAL:
            return RealDSHBackend(self._live_dispatch)
        if kind is BackendKind.UNAVAILABLE:
            raise BridgeNotAvailable(
                "REAL DSH dispatch requested but the live bridge is "
                f"unavailable ({BRIDGE_MARKER_ENV} not set); fail-closed — "
                "refusing to run the fake backend for a requested REAL run")
        return FakeSubagentBackend()

    def _assert_backend_available(self) -> None:
        """Fail-closed availability gate for the default (client) subtask path.

        Runs before any phase mutates state. When the flow will use its
        default DelegationClient (no injected subtask_runner) AND a REAL
        dispatch was requested but the bridge is unavailable, this raises
        ``BridgeNotAvailable`` so ``run()`` stops BLOCKED with no partial
        execution and never silently runs the fake backend (G1-5).
        """
        if self._subtask_runner is not None:
            # An explicit runner was injected — the default client is not used.
            return
        if self.backend_kind is BackendKind.UNAVAILABLE:
            raise BridgeNotAvailable(
                "REAL DSH dispatch requested but the live bridge is "
                f"unavailable ({BRIDGE_MARKER_ENV} not set); fail-closed — "
                "no silent fallback to the fake backend")

    def _get_client(self) -> DelegationClient:
        if self._client is None:
            self._client = DelegationClient(backend=self._select_backend())
        return self._client

    def _now_iso(self) -> str:
        return (self._now or datetime.now(timezone.utc)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def run(self, intake: TaskIntake, *, execute_plan: ExecutePlan | None = None,
            declared_risk: str = "LOW", review: dict | None = None,
            review_required: bool = False,
            approval_reference: str = "") -> FlowResult:
        """Run the full Execution Flow over a task intake.

        Returns a deterministic ``FlowResult``.  A failed / unresolved gate
        STOPS the flow (fail-closed); the result carries the terminal
        disposition (COMPLETE / BLOCKED / FAILED / ESCALATED / RECOVERING).
        """
        self._seq += 1
        task_id = f"task-{self._seq}"
        self._approval_reference = approval_reference
        audit = self._get_audit()
        started_id = audit.emit("flow_started", action="run",
                                target=getattr(intake, "objective", ""))
        result = FlowResult(
            flow_id=self.flow_id,
            objective=getattr(intake, "objective", ""),
            project=getattr(intake, "project", None) or self.project,
            task_id=task_id, phase="intake",
            started_at=self._now_iso(),
        )
        result.audit_ids = result.audit_ids + (started_id,)
        self._result = result
        try:
            self._run_chain(intake, execute_plan, declared_risk, review,
                            review_required, approval_reference)
        except ExecutionFailure as e:
            self._route_recovery(e)
        except SubtaskFailed as e:
            # Child failure PROPAGATES: the flow stops and hands off to the
            # recovery lifecycle with the classified failure (INT-12). An
            # unknown failure class is escalated, never guessed (Runbook 08).
            if e.failure_class == "unknown":
                self._stop(e, escalated=True)
            else:
                # Record the REAL stopping phase (result.phase was set at the
                # phase that raised) so recovery reporting preserves it (F7).
                self._route_recovery(
                    ExecutionFailure(e.failure_class, str(e),
                                     phase=result.phase))
        except GateEscalated as e:
            self._stop(e, escalated=True)
        except GateDenied as e:
            self._stop(e, blocked=True)
        except (StaleStateDetected, AuthorityDenied) as e:
            self._stop(e, blocked=True)
        except FlowStopped as e:
            self._stop(e, blocked=True)
        except RuntimeFlowError as e:
            self._stop(e, blocked=True)
        except Exception as e:  # noqa: BLE001 — fail-closed
            self._stop(e, blocked=True)
        # Finalize deterministically
        result.finished_at = self._now_iso()
        if result.outcome == COMPLETE and result.final_state != "COMPLETE":
            result.final_state = "COMPLETE"
        finished_id = audit.emit(
            "flow_finished", action="finish", target=result.task_id,
            task_id=result.task_id, result=result.outcome.lower(),
            new_state=result.final_state,
            extra={"outcome": result.outcome, "phase": result.phase})
        result.audit_ids = result.audit_ids + (finished_id,)
        return result

    # ------------------------------------------------------------------
    # The chain
    # ------------------------------------------------------------------

    def _run_chain(self, intake, execute_plan, declared_risk, review,
                   review_required, approval_reference):
        # Fail-closed backend gate FIRST — before any phase mutates state.
        # An unavailable REAL bridge stops the flow BLOCKED with no partial
        # execution and no silent fallback to the fake backend (G1).
        self._assert_backend_available()
        audit = self._get_audit()
        gates = self._get_gates()
        lc = self._get_lifecycle()
        r = self._result

        # --- INTAKE ---
        r.record_step("intake", "intake accepted")
        r.phase = "intake"
        audit.emit("intake_recorded", action="intake",
                   target=getattr(intake, "objective", ""), task_id=r.task_id)

        # --- UNDERSTAND ---
        r.record_step("understand", "normalize objective + require authority context")
        r.phase = "understand"
        if not intake.has_authority_context():
            raise GateEscalated(
                "understand", "authority_context", "ESCALATE",
                "intake has no required authority context (must name a "
                "delegation id or Human approval reference)")
        delegation, revocations = self.provider.current()
        if delegation is None:
            raise GateEscalated(
                "understand", "authority_context", "ESCALATE",
                f"no active delegation for authority context "
                f"{intake.required_authority_context!r}")
        if not delegation.is_active():
            raise GateDenied("understand", "authority_context", "DENY",
                             f"delegation {delegation.id} not ACTIVE")
        self._delegation = delegation
        audit.emit("authority_context", action="understand",
                   target=intake.required_authority_context,
                   authority_source=delegation.id, result="ok", task_id=r.task_id)

        # --- CLASSIFY + RISK_GATE (AUTH-INV-10) ---
        r.record_step("classify", "deterministic risk classification")
        r.phase = "classify"
        plan = self._resolve_plan(intake, execute_plan)
        self._execute_plan = plan
        risk_dec = gates.risk_gate(
            action=plan.action, target=plan.target, environment=plan.environment,
            declared=declared_risk)
        self._risk = risk_dec.detail.get("risk", declared_risk)
        r.risk = self._risk
        r.record_gate("classify", "risk_classify", risk_dec.decision,
                      risk_dec.reason, risk_dec.detail)

        r.phase = "risk_gate"
        r.record_step("risk_gate", "risk gate (non-downgradable HIGH)")
        r.record_gate("risk_gate", "risk", risk_dec.decision, risk_dec.reason,
                      risk_dec.detail)
        audit.emit("gate_risk", action="risk_gate", target=plan.target,
                   task_id=r.task_id,
                   result="denied" if risk_dec.decision != "ALLOW" else "allowed",
                   error=risk_dec.reason, extra={"risk": self._risk})
        if risk_dec.decision != "ALLOW":
            raise GateDenied("risk_gate", "risk", risk_dec.decision,
                             risk_dec.reason)

        # --- DECOMPOSE (DRAFT -> PLANNED, structured authority) ---
        r.phase = "decompose"
        r.record_step("decompose", "decompose objective into a scoped task")
        task = Task(
            task_id=r.task_id,
            objective=intake.normalized_objective() or intake.objective,
            assigned_role="cto",  # provisional; SELECT re-routes
            scope=tuple(intake.scope or ()),
            expected_output=intake.expected_outcome or "",
            risk_metadata=self._risk,
            project=self.project,
        )
        self._task = task
        lc.transition(task.task_id, "PLANNED", authority=delegation)
        r.final_state = lc.state(task.task_id)
        r.version = lc.version
        r.tasks = r.tasks + (task.to_dict(),)

        # --- SELECT (minimum specialist set, no blanket fan-out) ---
        r.phase = "select"
        r.record_step("select", "select minimum specialist set")
        selected = select_agents(task)
        validate_no_fanout(selected)
        r.selected = tuple(selected)
        audit.emit("routing_selected", action="select", target=task.task_id,
                   task_id=task.task_id, result="allowed",
                   extra={"selected": list(selected)})

        # --- DELEGATE (orchestrator-only child delegation, AUTH-INV-04) ---
        r.phase = "delegate"
        r.record_step("delegate", "issue scoped child delegation (orchestrator-only)")
        child = self._delegation_lifecycle.issue_child(
            delegation, task=task.task_id, action=plan.action, target=plan.target,
            environment=plan.environment)
        self._child = child
        lc.transition(task.task_id, "DELEGATED", authority=child)
        r.final_state = lc.state(task.task_id)
        r.version = lc.version
        r.delegations = r.delegations + (child.to_dict(),)
        audit.emit("delegation_issued", action="delegate", target=task.task_id,
                   task_id=task.task_id, authority_source=child.id,
                   result="allowed",
                   extra={"child_id": child.id,
                          "scope_ops": list(child.scope_operations)})

        # --- EXECUTE_SUBTASKS (DELEGATED -> EXECUTING) ---
        r.phase = "execute_subtasks"
        r.record_step("execute_subtasks",
                      "delegate subtasks to specialists (parallel when "
                      "independent)")
        lc.transition(task.task_id, "EXECUTING", authority=child)
        r.final_state = lc.state(task.task_id)
        r.version = lc.version
        runner = self._subtask_runner or self._default_subtask_runner()
        subtasks = tuple(self._subtask(task, role) for role in selected)
        payloads = self._run_subtasks(subtasks, child, runner)
        audit.emit("subtasks_executed", action="execute_subtasks",
                   target=task.task_id, task_id=task.task_id, result="allowed",
                   extra={"count": len(payloads),
                          "parallel": bool(r.parallel.get("safe"))})

        # --- COLLECT (EXECUTING -> COLLECTED) ---
        r.phase = "collect"
        r.record_step("collect", "collect structured results (data, not authority)")
        collected = self._collect(subtasks, payloads)
        results = [c.result for c in collected]
        self._results = results
        self._collected = collected
        lc.transition(task.task_id, "COLLECTED")
        r.final_state = lc.state(task.task_id)
        r.version = lc.version
        for c in collected:
            r.results = r.results + (c.to_dict(),)

        # --- EVIDENCE_GATE ---
        r.phase = "evidence_gate"
        r.record_step("evidence_gate", "evidence sufficiency ladder")
        claims, sources = self._evidence_inputs(results)
        ev_dec = gates.evidence_gate(risk=self._risk, claims=claims,
                                     sources=sources)
        r.record_gate("evidence_gate", "evidence", ev_dec.decision,
                      ev_dec.reason, ev_dec.detail)
        audit.emit("gate_evidence", action="evidence_gate", target=task.task_id,
                   task_id=task.task_id,
                   result="denied" if ev_dec.decision != "ALLOW" else "allowed",
                   error=ev_dec.reason)
        if ev_dec.decision != "ALLOW":
            raise (GateEscalated if ev_dec.decision == "ESCALATE" else GateDenied)(
                "evidence_gate", "evidence", ev_dec.decision, ev_dec.reason)

        # --- SYNTHESIZE (COLLECTED -> SYNTHESIZING) ---
        r.phase = "synthesize"
        r.record_step("synthesize", "consolidate results (preserve disagreement)")
        r.synthesis = self._synthesize(task, results, self._risk)
        lc.transition(task.task_id, "SYNTHESIZING")
        r.final_state = lc.state(task.task_id)
        r.version = lc.version

        # --- CONFLICT_GATE (no voting; material -> escalate) ---
        r.phase = "conflict_gate"
        r.record_step("conflict_gate", "detect + resolve conflicts (no voting)")
        outputs = [
            {"agent": tr.assigned_role, "decision": "recommendation",
             "position": (tr.recommendation or
                          (tr.findings[0] if tr.findings else "")),
             "evidence": list(tr.evidence)}
            for tr in results
        ]
        cf_dec = gates.conflict_gate(outputs=outputs, risk=self._risk)
        r.record_gate("conflict_gate", "conflict", cf_dec.decision,
                      cf_dec.reason, cf_dec.detail)
        audit.emit("gate_conflict", action="conflict_gate", target=task.task_id,
                   task_id=task.task_id,
                   result="escalated" if cf_dec.decision == "ESCALATE" else "allowed",
                   error=cf_dec.reason)
        if cf_dec.decision != "ALLOW":
            raise GateEscalated("conflict_gate", "conflict", cf_dec.decision,
                                cf_dec.reason)

        # --- ADVERSARIAL_REVIEW (THREAT-014/015; PASS != authority) ---
        r.phase = "adversarial_review"
        r.record_step("adversarial_review", "BadSector review (PASS != authority)")
        from control.badsector import _input_hash as _bs_hash
        expected_hash = _bs_hash(r.synthesis)
        if review:
            audit.emit("badsector_review", action="review", target=task.task_id,
                       task_id=task.task_id, authority_source=child.id,
                       result="recorded",
                       extra={"review_id": review.get("review_id"),
                              "input_hash": review.get("input_hash"),
                              "verdict": review.get("verdict")})
        review_log = audit.review_log()
        bd_dec = gates.badsector_review(
            risk=self._risk, action=plan.action, review=review,
            review_required=review_required,
            expected_input_hash=expected_hash, review_log=review_log)
        r.record_gate("adversarial_review", "badsector_review", bd_dec.decision,
                      bd_dec.reason, bd_dec.detail)
        audit.emit("gate_review", action="review", target=task.task_id,
                   task_id=task.task_id,
                   result="denied" if bd_dec.decision != "ALLOW" else "allowed",
                   error=bd_dec.reason)
        if bd_dec.decision != "ALLOW":
            raise GateDenied("adversarial_review", "badsector_review",
                             bd_dec.decision, bd_dec.reason)

        # --- AUTHORITY_GATE (planning) ---
        r.phase = "authority_gate"
        r.record_step("authority_gate", "planning-time authority check")
        delegation, revocations = self.provider.current()
        auth_dec = gates.authority_gate(
            delegation=child, action=plan.action, target=plan.target,
            environment=plan.environment, actor=ORCHESTRATOR,
            project=self.project, approval_reference=approval_reference,
            revocation_list=revocations, now=self._now)
        r.record_gate("authority_gate", "authority", auth_dec.decision,
                      auth_dec.reason, auth_dec.detail)
        audit.emit("gate_authority", action="authority_gate", target=plan.target,
                   task_id=task.task_id, authority_source=child.id,
                   result="denied" if auth_dec.decision == "DENY" else (
                       "escalated" if auth_dec.decision == "ESCALATE" else "allowed"),
                   error=auth_dec.reason)
        if auth_dec.decision == "DENY":
            raise AuthorityDenied(f"authority gate DENY: {auth_dec.reason}")
        if auth_dec.decision == "ESCALATE":
            raise GateEscalated("authority_gate", "authority", "ESCALATE",
                                auth_dec.reason)

        # --- EXECUTE (execution-time authority re-check is MANDATORY) ---
        r.phase = "execute"
        r.record_step("execute", "execution-time authority re-check + execute")
        self._execute(child, plan, approval_reference)

        # --- VERIFY ---
        r.phase = "verify"
        r.record_step("verify", "verification gate (reported != verified)")
        self._verify(plan)

        # --- CLOSE ---
        r.phase = "close"
        r.record_step("close", "COMPLETE after verified outcome")
        lc.transition(task.task_id, "COMPLETE")
        r.final_state = lc.state(task.task_id)
        r.version = lc.version
        r.outcome = COMPLETE
        audit.emit("state_complete", action="close", target=task.task_id,
                   task_id=task.task_id, result="completed",
                   new_state="COMPLETE")

    # ------------------------------------------------------------------
    # Phase helpers
    # ------------------------------------------------------------------

    def _resolve_plan(self, intake: TaskIntake,
                      execute_plan: ExecutePlan | None) -> ExecutePlan:
        if execute_plan is not None:
            return execute_plan
        target = ((intake.scope or ())[0] if intake.scope
                  else "multi-agent-harness")
        return ExecutePlan(action="read", target=target,
                           environment="dev", expected_outcome={},
                           action_category="internal_analysis",
                           description="derived read-only plan")

    def _subtask(self, task: Task, role: str) -> Task:
        return Task(
            task_id=f"{task.task_id}:{role}",
            objective=task.objective,
            assigned_role=role,
            parent_task=task.task_id,
            scope=tuple(task.scope or ()),
            expected_output=task.expected_output,
            risk_metadata=task.risk_metadata,
            project=task.project,
        )

    def _default_subtask_runner(self):
        client = self._get_client()

        def _run(task: Task, delegation: Delegation) -> TaskResult:
            return client.delegate(task, delegation)
        return _run

    # ------------------------------------------------------------------
    # EXECUTE_SUBTASKS — parallel when independent (contract §6)
    # ------------------------------------------------------------------

    def _run_subtasks(self, subtasks, delegation, runner) -> list:
        """Execute the decomposed subtasks and return their raw payloads in
        batch order, wave by wave.

        ``plan_waves`` partitions the subtask DAG into dependency-ordered
        waves (Kahn levels). Each wave is a maximal independent set and is
        dispatched through the *existing* ``ParallelExecutor`` (bounded
        concurrency, deterministic order, CAS revalidation) or the sequential
        fallback — no second scheduler, no new execution engine.

        Waves are sequential; subtasks *within* a wave may run concurrently.
        Every child failure propagates (SubtaskFailed) — no partial success.

        Inter-wave CAS semantics (point 1 / THREAT-021/022):
        Each wave establishes a NEW CAS epoch: ``held`` is re-read from
        ``lifecycle.version`` at the start of the wave and the existing
        ``ParallelExecutor`` / ``RuntimeStore.check_current`` validates that
        the on-disk version matches ``held`` before and after the wave. If an
        unrelated writer increments the version between wave N and wave N+1,
        the next wave's pre-check fails CLOSED (StaleStateDetected -> BLOCKED).
        This is tested in ``test_08_parallel`` inter-wave CAS cases.

        External dependencies (point 2):
        A ``depends_on`` not present in the current batch is an *external*
        dependency. It is considered satisfied IFF it is in the lifecycle's
        proven COMPLETE task set. Otherwise ``plan_waves`` fails CLOSED
        (ParallelUnsafe) — no silent assumption. Flow passes the proven
        completed set derived from ``lifecycle.project_state``.
        """
        r = self._result
        subtasks = tuple(subtasks)
        if not subtasks:
            r.parallel = {"safe": True, "mode": "sequential",
                          "task_ids": [], "owners": [],
                          "held_version": self._get_lifecycle().version,
                          "waves": [], "wave_count": 0}
            return []
        raw_plans = build_plans(subtasks)
        # Proven-completed set: every task in COMPLETE with a known state.
        # A dependency outside the batch is satisfied iff it is in this set;
        # otherwise its satisfaction is UNPROVEN and plan_waves fails closed.
        proven_completed = {
            tid for tid, sm in self._get_lifecycle().project_state.task_machines.items()
            if sm.current() == "COMPLETE"
        }
        # The parent task itself is PLANNED/DELEGATED/EXECUTING at this point,
        # not COMPLETE — it cannot satisfy a child dependency, and it is not
        # in the proven set, so a child depending on its parent id is correctly
        # treated as unsatisfied if the id is not inside the batch.
        try:
            waves = plan_waves(raw_plans, completed=proven_completed)
        except ParallelUnsafe as e:
            # Graph-level refusal (duplicate id / cycle / unsatisfied external)
            # — fail-closed before any child starts.
            self._get_audit().emit(
                "subtask_failed", action="execute_subtasks",
                target=r.task_id, task_id=r.task_id,
                result="error", error=str(e),
                extra={"failure_class": "logic", "role": ""})
            from .exceptions import ParallelUnsafe as _PU
            raise _PU(str(e)) from e

        # Wave observability (point 3): FlowResult.parallel exposes waves.
        # Required — observability (docs/phase-4/testing/0001) indexes
        # parallel_batches and metrics expect per-batch records; wave-level
        # provenance is the natural extension.  When no waves run, waves=[].
        wave_records: list[dict] = []
        # Payloads are produced in WAVE order (topological; each wave sorted by
        # task_id), which diverges from the ORIGINAL `subtasks` order whenever
        # there is >1 wave. _collect positional-zips payloads against `subtasks`
        # (collection.collect_all), so a wave-order payload list would pair the
        # wrong subtask to each result (role identity mismatch / wrong task).
        # Key each payload by its owning subtask id and re-sort back to the
        # original order before returning (F8).
        payloads_by_task_id: dict = {}
        for idx, wave_plans in enumerate(waves):
            wave_tasks = tuple(p.task for p in wave_plans)
            held = self._get_lifecycle().version
            # Inter-wave CAS epoch: re-validate held before dispatching
            # wave N+1.  If an unrelated writer bumped version between waves,
            # this check fails closed before the next wave starts.  The check
            # is free when no external writer intervened (current == held).
            try:
                self._get_store().check_current(held)
            except StaleStateDetected as e:
                self._get_audit().emit(
                    "version_conflict", action="execute_subtasks",
                    target=r.task_id, task_id=r.task_id,
                    result="denied", error=str(e))
                raise
            try:
                payloads = self._dispatch_subtasks(
                    wave_tasks, wave_plans, delegation, runner, held,
                    wave_index=idx, wave_count=len(waves),
                    wave_records=wave_records)
            except SubtaskFailed as e:
                # Record waves dispatched so far for forensic completeness
                self._finalize_wave_parallel(wave_records, len(waves))
                self._get_audit().emit(
                    "subtask_failed", action="execute_subtasks",
                    target=e.task_id or r.task_id, task_id=r.task_id,
                    result="error", error=str(e),
                    extra={"failure_class": e.failure_class, "role": e.role})
                raise
            except StaleStateDetected:
                self._finalize_wave_parallel(wave_records, len(waves))
                raise
            # _dispatch_subtasks returns exactly one payload per plan, in plans
            # order (the parallel executor returns batch order; the sequential
            # path iterates wave_tasks in order). Pair each with its plan's id.
            for plan, payload in zip(wave_plans, payloads):
                payloads_by_task_id[plan.task_id] = payload
        self._finalize_wave_parallel(wave_records, len(waves))
        # Re-sort to the ORIGINAL subtask order so _collect pairs payload[i]
        # with subtasks[i] correctly regardless of how many waves ran (F8).
        return [payloads_by_task_id[st.task_id] for st in subtasks]

    def _finalize_wave_parallel(self, wave_records: list[dict], wave_count: int) -> None:
        """Write the aggregated wave-aware parallel record to FlowResult.parallel.

        Single-wave runs preserve the legacy shape that existing tests assert on
        (safe/mode/owners/held_version), while adding waves/wave_count. Multi-wave
        runs aggregate similarly: top-level is the last wave's safety record
        (backward compatible) plus waves[] for full observability.
        """
        r = self._result
        # Legacy mirror: keep top-level safe/mode/owners from the last wave's
        # dispatch (the last _dispatch_subtasks call already wrote r.parallel).
        # If _dispatch recorded a parallel dict, reuse it as the aggregate base.
        base = dict(r.parallel) if isinstance(r.parallel, dict) else {}
        base["waves"] = list(wave_records)
        base["wave_count"] = wave_count
        # Ensure sequential fallback that overwrote r.parallel on the last wave
        # still carries waves on the aggregate.
        if not wave_records and wave_count == 0:
            base.setdefault("safe", True)
            base.setdefault("mode", "sequential")
        r.parallel = base

    def _dispatch_subtasks(self, subtasks, plans, delegation, runner,
                           held: int, *, wave_index: int | None = None,
                           wave_count: int | None = None,
                           wave_records: list[dict] | None = None):
        """Dispatch a subtask batch: parallel when provably independent,
        sequential otherwise. Returns raw payloads in batch order.

        When ``wave_records`` is supplied, this call appends one entry per
        wave to that list so the caller can aggregate wave observability.
        """
        r = self._result
        if self.parallel_subtasks and len(plans) > 1:
            try:
                safety = assert_parallel_safe(plans, held_version=held)
            except ParallelUnsafe as e:
                rec = {"safe": False, "reason": str(e),
                       "task_ids": [p.task_id for p in plans]}
                r.parallel = dict(rec)
                if wave_records is not None:
                    wave_records.append({
                        "wave_index": wave_index if wave_index is not None else 0,
                        "mode": "sequential",
                        "safe": False, "reason": str(e),
                        "task_ids": [p.task_id for p in plans],
                        "owners": [p.owner for p in plans],
                        "held_version": held,
                    })
                self._get_audit().emit(
                    "parallel_refused", action="execute_subtasks",
                    target=r.task_id, task_id=r.task_id, result="sequential",
                    error=str(e))
                return self._run_subtasks_sequential(subtasks, delegation,
                                                     runner)
            r.parallel = dict(safety.to_dict(), mode="parallel",
                              max_workers=self.max_workers)
            self._get_audit().emit(
                "parallel_batch", action="execute_subtasks", target=r.task_id,
                task_id=r.task_id, result="allowed",
                extra={"task_ids": list(safety.task_ids),
                       "owners": list(safety.owners),
                       "held_version": held,
                       "wave_index": wave_index,
                       "wave_count": wave_count})
            if wave_records is not None:
                wave_records.append({
                    "wave_index": wave_index if wave_index is not None else 0,
                    "mode": "parallel",
                    "safe": True, "reason": safety.reason,
                    "task_ids": list(safety.task_ids),
                    "owners": list(safety.owners),
                    "read_scopes": list(safety.read_scopes),
                    "held_version": held,
                    "max_workers": self.max_workers,
                })
            executor = ParallelExecutor(runner, store=self._get_store(),
                                        max_workers=self.max_workers)
            try:
                return executor.run(plans, delegation, held_version=held)
            except (StaleStateDetected, SubtaskFailed, RuntimeFlowError):
                raise
            except Exception as e:  # noqa: BLE001 — adapter failure -> typed
                cls, reason = classify_adapter_failure(e)
                raise SubtaskFailed(task_id=r.task_id, failure_class=cls,
                                    reason=reason) from e

        r.parallel = {"safe": True, "mode": "sequential",
                      "task_ids": [p.task_id for p in plans],
                      "owners": [p.owner for p in plans],
                      "held_version": held}
        if wave_records is not None:
            wave_records.append({
                "wave_index": wave_index if wave_index is not None else 0,
                "mode": "sequential",
                "safe": True, "reason": "sequential wave",
                "task_ids": [p.task_id for p in plans],
                "owners": [p.owner for p in plans],
                "held_version": held,
            })
        return self._run_subtasks_sequential(subtasks, delegation, runner)

    def _run_subtasks_sequential(self, subtasks, delegation, runner) -> list:
        payloads = []
        for st in subtasks:
            try:
                payloads.append(runner(st, delegation))
            except (SubtaskFailed, RuntimeFlowError):
                raise
            except Exception as e:  # noqa: BLE001 — adapter failure -> typed
                cls, reason = classify_adapter_failure(e)
                raise SubtaskFailed(role=st.assigned_role, task_id=st.task_id,
                                    failure_class=cls, reason=reason) from e
        return payloads

    # ------------------------------------------------------------------
    # COLLECT — structured results only, provenance preserved
    # ------------------------------------------------------------------

    def _collect(self, subtasks, payloads):
        """Collect structured TaskResults, preserving provenance and
        propagating a claimed FAILED / BLOCKED status."""
        audit = self._get_audit()
        r = self._result
        try:
            collected = collect_all(payloads, subtasks)
        except SubtaskFailed as e:
            audit.emit("subtask_failed", action="collect", target=e.task_id or r.task_id,
                       task_id=r.task_id, result="error", error=str(e),
                       extra={"failure_class": e.failure_class, "role": e.role})
            raise
        for c in collected:
            audit.emit("result_collected", action="collect", target=c.task_id,
                       task_id=r.task_id, result="recorded",
                       evidence=tuple(c.result.evidence),
                       extra={"role": c.role, "status": c.status,
                              "provenance": c.provenance})
        return collected

    def _evidence_inputs(self, results):
        claims, sources = [], []
        for tr in results:
            for i, f in enumerate(tr.findings or ()):
                claims.append({
                    "id": f"{tr.task_id}:f{i}", "text": f,
                    "source_ids": list(tr.evidence) or [],
                })
            for ev in (tr.evidence or ()):
                sources.append({
                    "id": ev, "timestamp": self._now_iso(),
                    "supports": True, "kind": "artifact", "independent": False,
                })
        return claims, sources

    def _synthesize(self, task, results, risk):
        return {
            "task_id": task.task_id,
            "objective": task.objective,
            "risk": risk,
            "findings": [f for tr in results for f in (tr.findings or ())],
            "recommendations": [tr.recommendation for tr in results
                                if tr.recommendation],
            "assumptions": [a for tr in results for a in (tr.assumptions or ())],
            "risks": [x for tr in results for x in (tr.risks or ())],
            "unresolved_items": [u for tr in results
                                 for u in (tr.unresolved_items or ())],
            "roles": [tr.assigned_role for tr in results],
        }

    # ------------------------------------------------------------------
    # EXECUTE — execution-time re-check + execute (reuses ExecutionEngine)
    # ------------------------------------------------------------------

    def _execute(self, delegation, plan: ExecutePlan, approval_reference: str):
        from orchestrator.execution import (
            ExecutionRequest, ExecutionEngine, ExecutionDenied, ExecutionRefused,
        )
        lc = self._get_lifecycle()
        audit = self._get_audit()
        r = self._result

        # Optional operator/test hook before the consequential re-check.
        if self.pre_execute is not None:
            self.pre_execute()

        # 1. re-read delegation + revocations NOW (AUTH-INV-05/06)
        delegation_now, revocations = self.provider.current()
        if delegation_now is None:
            raise AuthorityDenied(
                "execution-time re-check: delegation absent (AUTH-INV-05)")
        if not delegation_now.is_active() or delegation_now.id in revocations \
                or (delegation_now.expires_at
                    and delegation_now.is_expired()):
            audit.emit("execution_denial", action=plan.action, target=plan.target,
                       task_id=r.task_id, result="denied",
                       authority_source=delegation_now.id,
                       error="execution-time re-check: delegation revoked/expired "
                             "(AUTH-INV-06)")
            raise AuthorityDenied(
                "execution-time re-check: delegation revoked/expired "
                "(AUTH-INV-06)")

        # 1b. AUTH-INV-04 re-derived at EXECUTION against the CURRENT record:
        # a scope change that leaves the delegation ACTIVE (fewer operations/
        # resources/environments, an added prohibition or approval requirement,
        # a shortened expiry, a lower cost cap) must not be executed under the
        # superseded planning-time grant (AUTH-INV-06, DRIFT_AUTHORIZATION).
        from control.delegation import scope_contained
        if not scope_contained(delegation, delegation_now):
            audit.emit("execution_denial", action=plan.action,
                       target=plan.target, task_id=r.task_id, result="denied",
                       authority_source=delegation_now.id,
                       error="execution-time re-check: grant no longer "
                             "contained in current delegation scope "
                             "(AUTH-INV-04/06)")
            raise AuthorityDenied(
                "execution-time re-check: grant no longer contained in "
                "current delegation scope (AUTH-INV-04/06)")

        # 2. state/version must be current before the consequential action
        try:
            self._get_store().check_current(lc.version)
        except StaleStateDetected as e:
            audit.emit("version_conflict", action="execute", target=plan.target,
                       task_id=r.task_id, result="denied", error=str(e))
            raise StaleStateDetected(str(e)) from e

        # 3. execution-time authority re-check + execution gate (engine)
        request = ExecutionRequest(
            task_id=r.task_id, actor=ORCHESTRATOR,
            action=plan.action, target=plan.target, environment=plan.environment,
            delegation=delegation, expected_outcome=plan.expected_outcome or {},
            action_category=plan.action_category,
            revocation_list=revocations, approval_reference=approval_reference,
            project=self.project, state_version=lc.version,
        )
        engine = ExecutionEngine(request, base=self.base,
                                 audit=lambda ev: audit.emit_dict(ev),
                                 current_version=lc.version)
        try:
            engine.validate()
            engine.assert_plan_current(current_version=lc.version)
            engine.recheck_authority(revocation_list=revocations, now=self._now,
                                     approval_reference=approval_reference)
        except (ExecutionDenied, ExecutionRefused) as e:
            audit.emit("execution_denial", action=plan.action, target=plan.target,
                       task_id=r.task_id, result="denied",
                       authority_source=delegation.id, error=str(e))
            raise AuthorityDenied(
                f"execution-time authority re-check DENY: {e}") from e

        # 4. execute (consequential writes go through the execution gate)
        try:
            engine.execute(executor=self._make_executor(plan),
                           agent_claim=None)
        except Exception as e:  # noqa: BLE001 — classify -> recovery
            audit.emit("execution_attempt", action=plan.action, target=plan.target,
                       task_id=r.task_id, result="error",
                       authority_source=delegation.id, error=str(e))
            raise ExecutionFailure(engine.failure_class or "unknown",
                                   engine.failure_cause or str(e)) from e
        if engine.outcome.is_failed():
            audit.emit("execution_attempt", action=plan.action, target=plan.target,
                       task_id=r.task_id, result="error",
                       authority_source=delegation.id,
                       error=engine.outcome.error or "")
            raise ExecutionFailure(engine.failure_class or "unknown",
                                   engine.failure_cause
                                   or (engine.outcome.error or "execution failed"))

        # 5. verification (reported != verified; expected vs actual)
        self._attach_evidence(engine, plan)
        vresult = engine.verification_result()
        self._verification_result = vresult
        r.verification = {
            "verdict": vresult.verdict,
            "reason": vresult.reason,
            "detail": dict(vresult.detail),
        }
        audit.emit("execution_attempt", action=plan.action, target=plan.target,
                   task_id=r.task_id, result="executed",
                   authority_source=delegation.id,
                   extra={"verdict": vresult.verdict})
        if not vresult.is_verified():
            raise ExecutionFailure(
                "logic", f"verification not passed: {vresult.reason}")

    def _make_executor(self, plan: ExecutePlan):
        """Build the executor callable for the ExecutionEngine."""
        if self.executor is not None:
            return lambda request: self.executor(plan)
        from control.execution_gate import write_through

        def _exec(request):
            if (plan.action or "").lower() in _WRITE_ACTIONS:
                path = write_through(
                    "write", plan.target,
                    {"synthesis": self._result.synthesis,
                     "task_id": self._result.task_id},
                    base=self.base)
                self._result.note_file(plan.target)
                return {"target": plan.target, "file": path, "exit_code": 0}
            return {"target": plan.target, "exit_code": 0}
        return _exec

    def _attach_evidence(self, engine, plan: ExecutePlan):
        """Attach verification evidence artifacts for the action category
        (VERIFY-003: required kinds must be present).

        A category that requires INDEPENDENT verification gets NO fabricated
        evidence: the orchestrator is the executor, so a self-authored
        artifact of the required kind would satisfy the presence check while
        the independent verifier does not exist yet. The kinds are therefore
        left genuinely missing, so the verification gate answers INSUFFICIENT
        (fail-closed) until a separate verifier adds real artifacts. The
        withheld kinds are recorded as data only (never as evidence) in
        `_pending_independent_verification`.
        """
        try:
            reqs = engine.request.resolve_action_category()
            from control.verification import verification_requirements
            requirements = verification_requirements(reqs)
            required = requirements.required_evidence
            independence = requirements.independence
        except Exception:  # noqa: BLE001 — fail-closed to a generic artifact
            required = ("artifact",)
            independence = "self"
        target = plan.target or plan.description or "runtime"
        if independence != "independent":
            for kind in (required or ("artifact",)):
                try:
                    engine.add_evidence(
                        kind, f"{target}#{kind}",
                        verifier="self:orchestrator", independent=False)
                except Exception:  # noqa: BLE001 — evidence is best-effort data
                    pass
            return
        self._record_pending_independent(reqs, required, target)

    def _record_pending_independent(self, category: str, kinds, target: str):
        """Record — as DATA, never as verification evidence — that a category
        requiring independent verification has no independent artifacts yet.

        The pending kinds are exactly the artifacts withheld above; each entry
        names the artifact an independent verifier must supply. `verdict_until_
        supplied` states the gate's answer in the meantime (INSUFFICIENT)."""
        pending = getattr(self, "_pending_independent_verification", None)
        if pending is None:
            pending = self._pending_independent_verification = []
        record = {
            "action_category": category,
            "independence": "independent",
            "executor": "orchestrator",
            "verifier": "none",
            "reason": ("no independent verifier is attached: the orchestrator "
                       "is the executor of this action, so the required kinds "
                       "are not fabricated"),
            "pending_kinds": list(kinds or ("artifact",)),
            "target": target,
            "verdict_until_supplied": "INSUFFICIENT",
        }
        if record not in pending:
            pending.append(record)
        return record

    # ------------------------------------------------------------------
    # VERIFY
    # ------------------------------------------------------------------

    def _verify(self, plan: ExecutePlan):
        audit = self._get_audit()
        r = self._result
        vresult = self._verification_result
        if vresult is None:
            raise GateDenied("verify", "verification", "DENY",
                             "no verification result (reported != verified)")
        if vresult.is_verified():
            r.record_gate("verify", "verification", "ALLOW", vresult.reason,
                          dict(vresult.detail))
            audit.emit("gate_verification", action="verify", target=r.task_id,
                       task_id=r.task_id, result="allowed",
                       extra={"verdict": vresult.verdict})
            return
        r.record_gate("verify", "verification", "DENY", vresult.reason,
                      dict(vresult.detail))
        audit.emit("gate_verification", action="verify", target=r.task_id,
                   task_id=r.task_id, result="denied", error=vresult.reason)
        raise GateDenied("verify", "verification", "DENY", vresult.reason)

    # ------------------------------------------------------------------
    # Failure disposition
    # ------------------------------------------------------------------

    def _stop(self, error, *, blocked: bool = False,
              escalated: bool = False) -> None:
        """Record a terminal failure disposition on the result (fail-closed)."""
        r = self._result
        r.add_error(str(error))
        if isinstance(error, FlowStopped) and error.phase:
            r.phase = error.phase
        lc = self._get_lifecycle()
        task_id = r.task_id
        if escalated or isinstance(error, GateEscalated):
            r.outcome = ESCALATED
            if task_id:
                try:
                    lc.enter_escalated(task_id, reason=str(error))
                    r.final_state = lc.state(task_id)
                    r.version = lc.version
                except Exception:
                    pass
        else:
            r.outcome = BLOCKED
            if task_id:
                try:
                    lc.enter_blocked(task_id, reason=str(error))
                    r.final_state = lc.state(task_id)
                    r.version = lc.version
                except Exception:
                    pass
        self._get_audit().emit(
            "flow_stopped", action="stop", target=task_id, task_id=task_id,
            result=r.outcome.lower(), error=str(error),
            new_state=r.final_state)

    def _route_recovery(self, error: ExecutionFailure) -> None:
        """Execution/verification failure -> RECOVERING disposition with a
        RecoveryRecord (STOP -> PRESERVE), preserving the state version."""
        r = self._result
        r.add_error(str(error))
        # Preserve the REAL stopping phase recorded at raise time. The previous
        # code recomputed "execute"/"verify" from the cause prose and could
        # misreport (e.g. a subtask failure that stopped at "execute_subtasks"
        # was reported as "execute"); a cause string that merely contains
        # "verification" was misread as the "verify" phase.
        phase = getattr(error, "phase", "") or r.phase
        if phase:
            r.phase = phase
        try:
            ctrl = self.begin_recovery(
                task_id=r.task_id,
                preserved_version=self._get_lifecycle().version,
                failure_class=error.failure_class, reason=error.cause)
            r.recovery = ctrl.to_dict()
            lc = self._get_lifecycle()
            r.final_state = lc.state(r.task_id) if r.task_id in lc.project_state.task_machines else "RECOVERING"
            r.outcome = RECOVERING
        except Exception as e:  # noqa: BLE001
            r.outcome = FAILED
            r.final_state = "FAILED"
            r.add_error(f"recovery handoff failed: {e}")

    # ------------------------------------------------------------------
    # RECOVERY handoff (AUTH-INV-12/16, THREAT-017/022, REC-001..005)
    # ------------------------------------------------------------------

    def begin_recovery(self, *, task_id: str = "", preserved_version: int = 0,
                       failure_class: str = "unknown",
                       reason: str = ""):
        """Begin a recovery: STOP -> PRESERVE -> RECOVERING (state). Returns
        the control.recovery.RecoveryController.  No blind retry: the caller
        must then diagnose a cause (AUTH-INV-16)."""
        from control.recovery import RecoveryController
        task_id = task_id or self._result.task_id
        ctrl = RecoveryController(
            task_id, preserved_version or self._get_lifecycle().version,
            failure_class=failure_class, reason=reason)
        self._recovery_controller = ctrl
        lc = self._get_lifecycle()
        lc.enter_recovery(task_id, ctrl.record)
        self._result.outcome = RECOVERING
        self._result.recovery = ctrl.to_dict()
        self._get_audit().emit(
            "recovery", action="recover:begin", target=task_id,
            task_id=task_id, result="recovering", error=reason or "",
            extra={"recovery_state": ctrl.record.state})
        return ctrl

    def recover(self, *, task_id: str = "", cause: str,
                failure_class: str = "unknown", rollback: bool = False,
                restoration_evidence: str = "",
                restoration_verifier: str = "",
                re_execute: bool = True) -> FlowResult:
        """Recovery handoff (AUTH-INV-12/16, THREAT-017/022, REC-001..005).

        NO BLIND RETRY: a non-empty, NEW diagnosed cause is required; an
        identical-cause attempt or an exhausted budget is refused. Recovery
        re-checks authority through the SAME execution authority path and
        re-validates the current state version before any re-execution. It
        never acquires privilege.

        Returns a FlowResult (COMPLETE on successful recovery, else FAILED /
        ESCALATED).
        """
        audit = self._get_audit()
        lc = self._get_lifecycle()
        r = self._result
        task_id = task_id or r.task_id

        if not cause or not str(cause).strip():
            raise RecoveryRefusedByRuntime(
                "no blind retry: recovery requires a non-empty diagnosed cause "
                "(AUTH-INV-16/REC-001)")

        if self._recovery_controller is None:
            self.begin_recovery(task_id=task_id,
                                preserved_version=lc.version,
                                failure_class=failure_class, reason=cause)
        ctrl = self._recovery_controller

        # NO BLIND RETRY (AUTH-INV-16/REC-001): request_retry enforces a
        # non-empty, NEW diagnosed cause and the attempt cap.
        try:
            ctrl.request_retry(cause, max_attempts=ctrl.max_attempts)
        except Exception as e:  # noqa: BLE001 — wrapped, fail-closed
            raise RecoveryRefusedByRuntime(f"no blind retry: {e}") from e
        ctrl.diagnose(cause, failure_class=failure_class)
        if rollback:
            ctrl.rollback()
            ctrl.verify_restoration(evidence=restoration_evidence,
                                    verifier=restoration_verifier)
        else:
            ctrl.replan()

        # Recovery gate (belt-and-suspenders): cause diagnosed + attempts
        # within cap before re-execution (AUTH-INV-16, REC-001).
        gate = self._get_gates().recovery_gate(
            attempts=ctrl.record.attempts,
            cause_diagnosed=bool(ctrl.record.diagnosed_cause),
            max_attempts=ctrl.max_attempts)
        if gate.decision != "ALLOW":
            raise RecoveryRefusedByRuntime(gate.reason)

        # Authority re-check (AUTH-INV-12) + current version (THREAT-022)
        plan = self._execute_plan or ExecutePlan()
        delegation_now, revocations = self.provider.current()
        if delegation_now is None:
            raise RecoveryRefusedByRuntime(
                "recovery re-check: no current delegation (AUTH-INV-12)")

        def _gate_fn(action: str, target: str) -> bool:
            dec = self._get_gates().authority_gate(
                delegation=delegation_now, action=action, target=target,
                environment=plan.environment, actor=ORCHESTRATOR,
                project=self.project,
                approval_reference=self._approval_reference,
                revocation_list=revocations, now=self._now)
            return dec.decision == "ALLOW"

        current_version = self._get_store().current_version()
        # REC-004/THREAT-017 baseline: what the CURRENT DELEGATION authorizes
        # (the operative scope the authority gate itself checks —
        # control/authority.py:197), NOT the recovery attempt's own plan.
        # Building the baseline from `plan` made the comparison tautological:
        # the attempt could never exceed a baseline copied from itself.
        _orig_actions = list(delegation_now.scope_operations or ())
        if delegation_now.action and delegation_now.action not in _orig_actions:
            _orig_actions.append(delegation_now.action)
        _orig_targets = list(delegation_now.scope_resources or ())
        if delegation_now.target and delegation_now.target not in _orig_targets:
            _orig_targets.append(delegation_now.target)
        try:
            ctrl.recheck_authority(
                _gate_fn,
                attempt_action=plan.action, attempt_target=plan.target,
                attempt_grants=(), original_authority={
                    "actions": _orig_actions,
                    "targets": _orig_targets,
                    "grants": [],
                },
                current_version=current_version,
                expected_version=lc.version,
            )
        except Exception as e:  # noqa: BLE001 — fail-closed
            try:
                ctrl.fail(reason=str(e))
            except Exception:
                pass
            raise RecoveryRefusedByRuntime(
                f"recovery authority re-check: {e}") from e

        # RECOVERING -> DELEGATED (re-planned under the same delegation)
        lc.transition(task_id, "DELEGATED", authority=delegation_now)
        r.final_state = lc.state(task_id)
        r.version = lc.version

        if re_execute:
            # Bind the least-privilege grant: the scoped child issued at
            # planning when this flow instance still holds it (the normal-path
            # binding), otherwise the current record. Both are re-derived
            # against the fresh parent inside _execute (AUTH-INV-04/06).
            effective = self._child if self._child is not None else delegation_now
            try:
                self._execute(effective, plan, self._approval_reference)
                self._verify(plan)
                lc.transition(task_id, "EXECUTING", authority=delegation_now)
                lc.transition(task_id, "COLLECTED")
                lc.transition(task_id, "SYNTHESIZING")
                lc.transition(task_id, "COMPLETE")
                ctrl.complete()
                r.outcome = COMPLETE
                r.final_state = "COMPLETE"
                r.recovery = ctrl.to_dict()
                audit.emit("recovery", action="recover:complete",
                           target=task_id, task_id=task_id,
                           result="completed",
                           extra={"recovery_state": ctrl.record.state})
            except Exception as e:  # noqa: BLE001 — recovery re-execution failed
                try:
                    ctrl.fail(reason=str(e))
                    lc.enter_failed(task_id, reason=str(e))
                    r.outcome = FAILED
                    r.final_state = "FAILED"
                except Exception:
                    r.outcome = FAILED
                r.recovery = ctrl.to_dict()
                r.add_error(f"recovery re-execution failed: {e}")
                audit.emit("recovery", action="recover:failed", target=task_id,
                           task_id=task_id, result="failed", error=str(e))
        else:
            # A COMPLETE outcome must land in a TERMINAL state. Run the same
            # transition chain as the re-execute branch (DELEGATED ->
            # EXECUTING -> COLLECTED -> SYNTHESIZING -> COMPLETE) with the
            # authority-checked first hop, instead of leaving the state machine
            # parked at DELEGATED with a COMPLETE outcome.
            lc.transition(task_id, "EXECUTING", authority=delegation_now)
            lc.transition(task_id, "COLLECTED")
            lc.transition(task_id, "SYNTHESIZING")
            lc.transition(task_id, "COMPLETE")
            ctrl.complete()
            r.outcome = COMPLETE
            r.recovery = ctrl.to_dict()
            r.final_state = "COMPLETE"
            audit.emit("recovery", action="recover:complete", target=task_id,
                       task_id=task_id, result="completed",
                       extra={"recovery_state": ctrl.record.state})
        return r


__all__ = ["ExecutionFlow", "ExecutePlan", "ExecutionFailure",
           "RUNTIME_PHASE_CHAIN"]