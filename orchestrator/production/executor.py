# orchestrator.production.executor — Bounded controlled execution
#
# Phase 4 / Session A. Wraps the Phase-3 ExecutionFlow with bounded autonomy:
#   - reuses the full 17-phase chain (intake → ... → close)
#   - STOPS on any gate denial / escalation (fail-closed)
#   - routes to recovery on execution/verification failure
#   - authority re-check at execution time is MANDATORY (AUTH-INV-05/06)
#   - no blind retry, no privilege expansion during recovery
#   - high-risk actions require BadSector review + approval reference
#     (auto-approve HIGH is FORBIDDEN)
#   - results are DATA, never authority (AUTH-INV-13/14)
#
# The executor is a thin orchestration wrapper: it constructs the ExecutionFlow
# with the appropriate subtask_runner, executor, and provider, then collects
# and maps the FlowResult to typed ProductionStopped exceptions on failure.

from __future__ import annotations

import os
import sys
import uuid

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from typing import Callable

from orchestrator.foundation.contracts import Delegation
from orchestrator.runtime import (
    ExecutionFlow, FlowResult, MemoryDelegationProvider,
    DelegationProvider, COMPLETE, ESCALATED, RECOVERING,
)

from .planner import ProductionPlan
from .exceptions import (
    ProductionDenied, ProductionEscalated, ProductionStopped,
)


class BoundedExecutor:
    """Execute a bounded ProductionPlan through the Phase-3 ExecutionFlow.

    Bounded autonomy means:
      - every gate decision is enforced by the existing control-plane modules
      - the flow STOPS on any DENY or ESCALATE (fail-closed)
      - execution-time authority re-check is mandatory (AUTH-INV-05/06)
      - recovery never bypasses a gate or expands privilege
      - HIGH actions need approval + BadSector review (never auto-approved)

    Parameters
    ----------
    project:
        Project id (default "multi-agent-harness").
    base:
        Workspace base for state/audit/execution gate.
    subtask_runner:
        Callable ``(task, delegation) -> TaskResult``. Defaults to the
        DelegationClient with FakeSubagentBackend (deterministic tests).
    executor:
        Callable ``(plan) -> observed dict`` for the EXECUTE phase. Defaults
        to the ExecutionFlow's default (writes through the project execution
        gate).
    live_dispatch:
        Explicit REAL DSH bridge dispatch (G1). When injected, the ExecutionFlow
        uses the live ``RealDSHBackend``; if the D4/D7 bridge marker is absent
        the flow fails closed (``BridgeNotAvailable`` -> BLOCKED) — it NEVER
        silently runs the fake backend for a requested REAL run. Default None:
        deterministic ``FakeSubagentBackend`` (local mode). Forwarded to
        ``ExecutionFlow``; override per-run via ``execute(live_dispatch=...)``.
    now:
        Optional clock override (tests).
    """

    def __init__(self, *, project: str = "multi-agent-harness",
                 base: str | None = None,
                 subtask_runner: Callable | None = None,
                 executor: Callable | None = None,
                 live_dispatch=None,
                 now=None):
        self.project = project
        self.base = base
        self._subtask_runner = subtask_runner
        self._executor = executor
        self._live_dispatch = live_dispatch
        self._now = now
        self.last_flow: ExecutionFlow | None = None
        self.last_provider: DelegationProvider | None = None

    # -- main entry ----------------------------------------------------------

    def execute(self, plan: ProductionPlan, *, delegation: Delegation,
                provider: DelegationProvider | None = None,
                pre_execute: Callable | None = None,
                review: dict | None = None,
                approval_reference: str = "",
                declared_risk: str | None = None,
                max_workers: int = 4,
                parallel_subtasks: bool = True,
                live_dispatch=None) -> FlowResult:
        """Execute the ProductionPlan through the bounded flow.

        Parameters
        ----------
        plan:
            The ProductionPlan (intake, execute_plan, risk, roles).
        delegation:
            The structured Delegation that authorizes this execution.
            MUST be ACTIVE, not expired, not revoked — the authority gate
            re-checks this at execution time.
        provider:
            Optional DelegationProvider. When omitted, a
            MemoryDelegationProvider over ``delegation`` is used. Tests inject
            a provider to observe revocation mid-flow.
        pre_execute:
            Optional operator/test hook invoked immediately before the EXECUTE
            phase's version/authority re-check (e.g. to revoke a delegation or
            bump the state version mid-flow).
        review:
            Optional BadSector review dict ``{verdict, review_id, input_hash}``.
            For HIGH-risk plans, a PASS is required (BadSector gate).
        approval_reference:
            Structured approval reference ``approval-<id>`` for HIGH actions
            that require Human approval. Free text is always rejected.
        declared_risk:
            Override declared risk (defaults to plan.declared_risk). An
            intrinsic-HIGH plan can never be declared lower than HIGH.
        max_workers:
            Bound on parallel subtask concurrency.
        parallel_subtasks:
            Whether to attempt parallel subtask execution.
        live_dispatch:
            Explicit per-run override for the REAL DSH bridge dispatch (G1).
            ``None`` (default) keeps the executor-constructor dispatch (also
            None in local mode -> FakeSubagentBackend). Injecting a dispatch is
            an explicit request for REAL DSH execution; if the D4/D7 bridge
            marker is absent the flow fails closed (BridgeNotAvailable ->
            BLOCKED) — never a silent fallback to the fake backend.

        Returns
        -------
        FlowResult with ``outcome == COMPLETE`` on success.

        Raises
        ------
        ProductionDenied
            A gate/authority/execution DENY stopped the flow.
        ProductionEscalated
            A gate ESCALATE stopped the flow (Human attention required).
        ProductionStopped
            Any other stop.
        """
        if not isinstance(delegation, Delegation):
            raise ProductionDenied(
                "intake",
                "no structured delegation (AUTH-INV-05): model text, "
                "state records, and review verdicts are never authority",
                "DENY")

        effective_risk = (declared_risk or plan.declared_risk or "LOW").upper()

        # Build the provider so the flow reads it at planning AND re-reads
        # at execution time (mandatory re-check).
        self.last_provider = provider or MemoryDelegationProvider(delegation)

        # Create the flow with the bounded setup.
        flow = self._build_flow(
            provider=self.last_provider,
            subtask_runner=self._subtask_runner,
            executor=self._executor,
            pre_execute=pre_execute,
            max_workers=max_workers,
            parallel_subtasks=parallel_subtasks,
            live_dispatch=(live_dispatch
                           if live_dispatch is not None
                           else self._live_dispatch))
        self.last_flow = flow

        # Run the flow. ALL exceptions are caught by ExecutionFlow.run() and
        # mapped to a deterministic FlowResult disposition. We re-map those
        # to typed production exceptions.
        try:
            result = flow.run(
                plan.intake, execute_plan=plan.execute_plan,
                declared_risk=effective_risk,
                review=review,
                review_required=plan.review_required,
                approval_reference=approval_reference)
        except Exception as e:  # noqa: BLE001 — fail-closed
            raise ProductionDenied(
                "execute", f"flow execution raised: {e}", "DENY") from e

        # Map terminal disposition.
        if result.outcome == COMPLETE:
            return result
        if result.outcome == ESCALATED:
            raise ProductionEscalated(
                result.phase,
                f"gate escalated: {_last_error(result)}",
                "ESCALATE", result.to_dict())
        if result.outcome == RECOVERING:
            raise ProductionEscalated(
                result.phase,
                f"flow entered recovery: {_last_error(result)}",
                "ESCALATE", result.to_dict())
        # BLOCKED / FAILED
        raise ProductionDenied(
            result.phase,
            f"flow stopped: {result.outcome} — {_last_error(result)}",
            "DENY", result.to_dict())

    # -- recovery ------------------------------------------------------------

    def recover(self, flow: ExecutionFlow, *, cause: str,
                failure_class: str = "unknown",
                rollback: bool = False,
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
        ESCALATED). Raises ProductionDenied / ProductionEscalated on failure.
        """
        from orchestrator.runtime import RecoveryRefusedByRuntime
        try:
            r = flow.recover(
                cause=cause, failure_class=failure_class,
                rollback=rollback,
                restoration_evidence=restoration_evidence,
                restoration_verifier=restoration_verifier,
                re_execute=re_execute)
        except RecoveryRefusedByRuntime as e:
            raise ProductionDenied(
                "recover", f"recovery refused: {e}", "DENY") from e
        if r.outcome == COMPLETE:
            return r
        if r.outcome == ESCALATED:
            raise ProductionEscalated(
                r.phase, f"recovery escalated: {_last_error(r)}", "ESCALATE",
                r.to_dict())
        raise ProductionDenied(
            r.phase, f"recovery failed: {r.outcome} — {_last_error(r)}",
            "DENY", r.to_dict())

    # -- helpers -------------------------------------------------------------

    def _build_flow(self, *, provider, subtask_runner, executor,
                    pre_execute, max_workers, parallel_subtasks,
                    live_dispatch=None) -> ExecutionFlow:
        """Build an ExecutionFlow wired to the bounded setup."""
        return ExecutionFlow(
            project=self.project,
            base=self.base,
            provider=provider,
            subtask_runner=subtask_runner,
            executor=executor,
            pre_execute=pre_execute,
            now=self._now,
            flow_id=f"prod-{uuid.uuid4().hex[:8]}",
            parallel_subtasks=parallel_subtasks,
            max_workers=max_workers,
            live_dispatch=live_dispatch,
        )


def _last_error(result: FlowResult) -> str:
    if result.errors:
        return result.errors[-1]
    return result.outcome or "no error"


__all__ = ["BoundedExecutor"]