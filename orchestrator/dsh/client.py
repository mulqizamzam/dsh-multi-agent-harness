# orchestrator.dsh.client — Orchestrator → DSH subagent delegation client
#
# Phase 3 / Session B. Scope: multi-agent-harness/ only.
#
# The adapter's core: the orchestrator runtime delegates a scoped task to a
# specialist subagent through this client.  The client:
#   - resolves role → subagent instance (D4/D7 approved composition)
#   - builds only the authorized task context (no authority leaks)
#   - enforces delegation scope containment (AUTH-INV-04)
#   - prevents specialist-to-specialist delegation (DLG-003)
#   - prevents authority-through-messages (THREAT-020)
#   - collects structured results into validated TaskResult
#   - propagates timeout/abort/child-failure as typed exceptions
#   - preserves role identity + runtime provenance
#
# The client is backend-agnostic; tests use FakeSubagentBackend.

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field as dc_field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import (
    Delegation,
    ORCHESTRATOR,
    Task,
    TaskResult,
)

from .backend import (
    DelegationBackend,
    DelegationResult,
    DelegationRun,
    FakeSubagentBackend,
    STOP_ABORTED,
    STOP_COMPLETED,
)
from .context import build_task_context, assert_no_authority_in_payload
from .exceptions import (
    ChildFailure,
    DelegationAborted,
    DelegationDenied,
    DelegationTimeout,
    DSHError,
    ProhibitedDelegation,
    RoleResolutionError,
    MalformedResult,
)
from .provenance import DelegationProvenance
from .resolver import RoleResolver, SubagentInstance
from .result import TaskResultCollector
from .bridge import BackendKind


# ---------------------------------------------------------------------------
# Re-export control.delegation helpers for scope containment, expiry, etc.
# We import them inside the module to avoid runtime circulars.
# ---------------------------------------------------------------------------
def _assert_actor_may_delegate(actor: str) -> None:
    """V1: only the orchestrator delegates (DLG-003).  Raises
    ProhibitedDelegation on any other actor."""
    if actor != ORCHESTRATOR:
        raise ProhibitedDelegation(
            f"subdelegation by actor {actor!r} DENIED BY DEFAULT (V1, DLG-003): "
            "only the orchestrator may issue delegations to specialists")


def _is_expired(delegation) -> bool:
    try:
        from control.delegation import is_expired
        return is_expired(delegation)
    except ImportError:
        # Fallback: check the delegation's own method
        return delegation.is_expired() if hasattr(delegation, "is_expired") else False


def _is_revoked(delegation) -> bool:
    # A delegation is revoked if its status is REVOKED
    return getattr(delegation, "status", "") == "REVOKED"


def _check_scope_containment(task, delegation) -> None:
    """AUTH-INV-04: validate task scope ⊆ delegation scope_resources."""
    task_scope = tuple(getattr(task, "scope", ()) or ())
    if not task_scope:
        return  # empty scope → no containment check (relies on delegation-level auth)
    try:
        from control.delegation import target_in_scope
    except ImportError:
        return  # best-effort; test with control.delegation available
    for s in task_scope:
        if not target_in_scope(s, delegation.scope_resources):
            raise DelegationDenied(
                f"task scope {s!r} is outside delegation resources "
                f"{delegation.scope_resources} (AUTH-INV-04)")


# ---------------------------------------------------------------------------
# DelegationResult (adapter-level)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DelegationOutcome:
    """The adapter's final result on a successful delegation.

    `result` is the validated TaskResult collected from the child.
    `provenance` is the runtime provenance stamp.
    `outcome` is the raw backend DelegationResult (for diagnostics).
    """
    result: TaskResult
    provenance: DelegationProvenance
    outcome: DelegationResult


# ---------------------------------------------------------------------------
# DelegationClient
# ---------------------------------------------------------------------------
class DelegationClient:
    """The orchestrator's delegation surface to DSH subagent instances.

    Usage::

        client = DelegationClient(backend=FakeSubagentBackend())
        outcome = client.delegate(task, delegation)
        print(outcome.result.status, outcome.provenance.role)
    """

    def __init__(self, *, resolver=None, backend=None,
                 collector=None, now=None):
        self._resolver = resolver or RoleResolver()
        self._backend = backend or FakeSubagentBackend()
        self._collector = collector or TaskResultCollector()
        self._now = now or time.monotonic

    # -- observable backend kind (G1) ---------------------------------------

    @property
    def backend_kind(self) -> BackendKind:
        """The backend kind this client is wired to (REAL / FAKE).

        Read-only observability — the value is derived from the actual backend
        instance.  ``BackendKind.UNAVAILABLE`` does not occur here (a client
        always has a usable backend).
        """
        name = getattr(self._backend, "name", "")
        return BackendKind.REAL if name == "real-dsh-bridge" else BackendKind.FAKE

    @property
    def backend(self):
        """The underlying DelegationBackend (read-only access)."""
        return self._backend

    # -- public API ----------------------------------------------------------

    def delegate(self, task, delegation, *, actor=ORCHESTRATOR,
                 signal=None, timeout_seconds=None, extra_context=None) -> DelegationOutcome:
        """Delegate a scoped *task* to a specialist under *delegation*.

        Parameters
        ----------
        task : Task
            The decomposed unit of work.  ``task.assigned_role`` must be a
            valid specialist role resolvable by the RoleResolver.
        delegation : Delegation
            The scoped authority record authorizing this delegation.  Must be
            ACTIVE, not expired, not revoked; the task scope must be contained
            within the delegation's scope_resources (AUTH-INV-04).
        actor : str
            The delegating agent.  MUST be ``orchestrator`` (V1, DLG-003).
        signal : AbortSignal-like or None
            Cancellation signal.  ``signal.is_set()`` → DelegationAborted.
        timeout_seconds : float or None
            Tool-call deadline.  Exceeded → DelegationTimeout.
        extra_context : dict or None
            Additional data to pass to the child (sanitized — authority
            assertion keys are stripped).

        Returns
        -------
        DelegationOutcome
            The validated TaskResult + provenance on success.

        Raises
        ------
        ProhibitedDelegation
            Actor is not the orchestrator (specialist→specialist).
        DelegationDenied
            Delegation inactive/expired/revoked/out of scope.
        RoleResolutionError
            The task's assigned_role is not a known specialist.
        DelegationTimeout
            The child did not settle within *timeout_seconds*.
        DelegationAborted
            The delegation was cancelled (signal or DSH stopReason aborted).
        ChildFailure
            The child failed or refused (stopReason error/max-tokens/refusal).
        MalformedResult
            The child's structured output is not a valid TaskResult.
        """
        started = self._now_iso()

        # 1. PREVENT SPECIALIST-TO-SPECIALIST DELEGATION (DLG-003)
        _assert_actor_may_delegate(actor)

        # 2. DELEGATION VALIDITY (fail-closed) — AUTH-INV-05/06
        if not isinstance(delegation, Delegation):
            raise DelegationDenied(
                "delegation must be a structured Delegation object "
                "(AUTH-INV-01/05)")
        if not delegation.is_active():
            raise DelegationDenied(
                f"delegation {delegation.id} is not ACTIVE (status={delegation.status})")
        if _is_expired(delegation):
            raise DelegationDenied(f"delegation {delegation.id} is expired")
        if _is_revoked(delegation):
            raise DelegationDenied(f"delegation {delegation.id} is revoked")

        # 3. RESOLVE ROLE → SUBAGENT INSTANCE (D4/D7 approved composition)
        role = getattr(task, "assigned_role", "")
        instance = self._resolver.resolve(role)

        # 4. DELEGATION SCOPE CONTAINMENT — AUTH-INV-04
        _check_scope_containment(task, delegation)

        # 5. BUILD AUTHORIZED CONTEXT (no authority in messages — THREAT-020)
        context = build_task_context(task=task, delegation=delegation,
                                     extra=extra_context)

        # 6. START DELEGATION
        run = self._backend.start(instance, context, signal=signal,
                                  timeout_seconds=timeout_seconds)

        # 7. SETTLE WITH TIMEOUT/ABORT/FALLURE PROPAGATION
        if signal is not None and signal.is_set():
            run.dispose()
            raise DelegationAborted(
                f"delegation {delegation.id} aborted before result (signal set)")

        outcome = self._settle(run, timeout_seconds, signal)

        # 8. MAP NON-COMPLETED STOP REASONS TO TYPED EXCEPTIONS
        if outcome.stop_reason == STOP_ABORTED or (signal is not None and signal.is_set()):
            raise DelegationAborted(
                f"delegation aborted (stopReason {outcome.stop_reason})")
        if outcome.stop_reason != STOP_COMPLETED:
            # error / max-tokens / refusal / unknown → child failure
            raise ChildFailure(
                f"child stopped with {outcome.stop_reason}: {outcome.diagnostic}",
                diagnostic=outcome.diagnostic, outcome=outcome)

        # 9. COLLECT STRUCTURED TASK RESULT (role identity checked here)
        if outcome.structured is None:
            raise MalformedResult(
                "child completed without producing a structured result")
        result = self._collector.collect(outcome.structured, task=task)

        # 9. PROVENANCE (role identity + runtime context)
        settled = self._now_iso()
        provenance = DelegationProvenance.build(
            delegation=delegation, task=task, instance=instance,
            run=run, started_at=started, settled_at=settled,
            result=outcome, result_status=result.status)

        return DelegationOutcome(result=result, provenance=provenance,
                                 outcome=outcome)

    # -- internal helpers ---------------------------------------------------

    def _settle(self, run: DelegationRun, timeout_seconds: float | None,
                signal) -> DelegationResult:
        """Await *run*'s result with a watchdog thread that enforces
        *timeout_seconds* and respects *signal*.

        The backend's own run.result() may raise DelegationTimeout / Aborted
        / ChildFailure when the DSH tool-call budgets are exhausted.  The
        watchdog adds an additional orchestrator-layer timeout for cases where
        the backend itself hangs (unresponsive transport).
        """
        if timeout_seconds is not None and timeout_seconds <= 0:
            timeout_seconds = None

        # No timeout → still check signal, then trust the backend's result()
        if timeout_seconds is None:
            if signal is not None and signal.is_set():
                run.dispose()
                raise DelegationAborted("aborted before settle")
            return run.result()

        box: dict = {}
        done = threading.Event()

        def _work():
            try:
                box["result"] = run.result()
            except BaseException as e:
                box["error"] = e
            finally:
                done.set()

        t = threading.Thread(target=_work, daemon=True,
                             name="dsh-settle-watchdog")
        t.start()

        deadline = time.monotonic() + timeout_seconds
        while not done.is_set():
            remain = deadline - time.monotonic()
            if remain <= 0:
                run.dispose()
                raise DelegationTimeout(
                    f"delegation did not settle within {timeout_seconds}s "
                    f"(orchestrator watchdog)")
            if signal is not None and signal.is_set():
                run.dispose()
                raise DelegationAborted(
                    f"delegation aborted by signal (watchdog)")
            done.wait(max(0.02, min(remain, 0.2)))

        if "error" in box:
            # Re-raise backend exceptions through the adapter
            exc = box["error"]
            if isinstance(exc, (DelegationTimeout, DelegationAborted,
                                ChildFailure, RoleResolutionError,
                                DelegationDenied, MalformedResult)):
                raise exc
            raise ChildFailure(
                f"unexpected backend error: {exc}",
                diagnostic=str(exc)) from exc

        return box["result"]

    def _now_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())