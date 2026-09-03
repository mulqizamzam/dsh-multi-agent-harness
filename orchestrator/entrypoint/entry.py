# orchestrator.entrypoint.entry — DSH chat → ProductionRun front door (V1)
#
# Phase 5 / Front Door V1. The thin, fail-closed entry point that bridges a
# user objective (chat/CLI) to the bounded ProductionRun:
#
#   user objective
#     → front-door shape validation
#     → resolve existing structured Delegation (read-only)
#     → ProductionRun.run()
#     → structured terminal result (COMPLETE | BLOCKED | ESCALATED | ERROR)
#
# Security posture (all invariants preserved):
#   - objective/scope/constraints/expected_outcome are DATA, never authority
#     (AUTH-INV-01/13)
#   - the front door NEVER creates a Delegation, NEVER sets ACTIVE, NEVER
#     fabricates an approval reference or a review verdict, and NEVER derives
#     authority from prose — it only RESOLVES an existing structured
#     Delegation from the protected registry and hands it to ProductionRun
#   - it NEVER calls ExecutionFlow directly and NEVER calls raw DSH tools;
#     ProductionRun.run() is the only execution path (all existing gates are
#     preserved: risk, evidence, conflict, BadSector review, authority,
#     execution, verification)
#   - intrinsic HIGH is never downgradable: the front door does not accept a
#     risk override from the caller (the deterministic RiskClassifier in
#     control.risk stays authoritative)
#   - scope remains authority-contained: the resolved delegation is matched by
#     id and project, and the runtime re-checks authority at execution time
#     (AUTH-INV-05/06/11)
#   - no new authority mechanism is introduced
#   - COMPLETE still requires PASSED verification (ProductionRun enforces this)

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from typing import Callable

from orchestrator.foundation.contracts import Delegation
from orchestrator.runtime import (
    DelegationProvider,
    FileDelegationProvider,
)
from control.delegation import is_expired, is_revoked

from orchestrator.production import (
    ProductionRun,
    ProductionDenied,
    ProductionEscalated,
    ProductionStopped,
    NoValidDelegation,
    ObjectiveNotActionable,
    PlanRejected,
    ReportGenerationFailed,
)

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------
SCHEMA = "run-result@1"

# ---------------------------------------------------------------------------
# Terminal statuses of the front-door envelope
# ---------------------------------------------------------------------------
COMPLETE = "COMPLETE"
BLOCKED = "BLOCKED"
ESCALATED = "ESCALATED"
ERROR = "ERROR"
STATUSES = (COMPLETE, BLOCKED, ESCALATED, ERROR)

# Structured delegation id pattern (kept in sync with
# schemas/delegation.schema.json).
_DELEGATION_ID_RE = re.compile(r"^delegation-[A-Za-z0-9-]+$")


# ---------------------------------------------------------------------------
# Front-door exceptions
# ---------------------------------------------------------------------------
class FrontDoorError(ValueError):
    """A front-door request failed shape validation (fail-closed)."""


# ---------------------------------------------------------------------------
# Request contract
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FrontDoorRequest:
    """Validated, normalized front-door request (DATA — never authority).

    Fields
    ------
    objective:         the user objective (required, non-empty).
    scope:             the bounded scope list (required, non-empty).
    delegation_id:     the id of an EXISTING structured Delegation in the
                       registry (required; matched exactly, never created).
    constraints:       optional constraints (strings).
    expected_outcome:  optional expected outcome (string).
    project:           project id (default "multi-agent-harness").
    base:              workspace base (default: project root).
    environment:       execution environment (default "dev").
    """

    objective: str
    scope: tuple[str, ...]
    delegation_id: str
    constraints: tuple[str, ...] = ()
    expected_outcome: str = ""
    project: str = "multi-agent-harness"
    base: str | None = None
    environment: str = "dev"

    def __post_init__(self):
        problems: list[str] = []

        if not self.objective or not str(self.objective).strip():
            problems.append("objective must be a non-empty string")

        scope = tuple(self.scope or ())
        if not scope:
            problems.append("scope must be a non-empty list of strings")
        else:
            for s in scope:
                if not isinstance(s, str) or not s.strip():
                    problems.append("every scope entry must be a non-empty string")
                    break

        if not self.delegation_id or not str(self.delegation_id).strip():
            problems.append("delegation_id must be a non-empty string")
        elif not _DELEGATION_ID_RE.match(str(self.delegation_id).strip()):
            problems.append(
                f"delegation_id {self.delegation_id!r} is not a structured "
                "delegation id (expected delegation-<id>; prose is never "
                "authority, AUTH-INV-01)")

        for c in (self.constraints or ()):
            if not isinstance(c, str):
                problems.append("every constraint must be a string")
                break

        if not isinstance(self.expected_outcome, str):
            problems.append("expected_outcome must be a string")

        if not self.project or not str(self.project).strip():
            problems.append("project must be a non-empty string")

        if problems:
            raise FrontDoorError("; ".join(problems))

        # Normalize (frozen dataclass — use object.__setattr__).
        object.__setattr__(self, "objective", str(self.objective).strip())
        object.__setattr__(self, "scope",
                           tuple(str(s).strip() for s in scope))
        object.__setattr__(self, "delegation_id",
                           str(self.delegation_id).strip())
        object.__setattr__(self, "constraints",
                           tuple(self.constraints or ()))
        object.__setattr__(self, "expected_outcome",
                           self.expected_outcome)
        object.__setattr__(self, "project", str(self.project).strip())


# ---------------------------------------------------------------------------
# Result envelope
# ---------------------------------------------------------------------------
class FrontDoorResult:
    """Structured terminal result of a front-door run (DATA — never authority).

    Attributes
    ----------
    status:     COMPLETE | BLOCKED | ESCALATED | ERROR.
    run_id:     the production run id ("" when no run was created).
    objective:  the original objective text.
    state:      ProductionState dict (None when no run was created).
    report:     FinalReport dict (None before report generation).
    errors:     error messages (tuple of str).
    audit_ids:  audit event ids from the run (tuple of str).
    """

    def __init__(self, *, status: str = ERROR, run_id: str | None = None,
                 objective: str = "", state: dict | None = None,
                 report: dict | None = None,
                 errors: tuple[str, ...] = (),
                 audit_ids: tuple[str, ...] = ()):
        self.status = status
        self.run_id = run_id
        self.objective = objective
        self.state = state
        self.report = report
        self.errors = tuple(errors)
        self.audit_ids = tuple(audit_ids)

    def to_dict(self) -> dict:
        """Serialize to a JSON-serializable dict with schema marker."""
        return {
            "schema": SCHEMA,
            "status": self.status,
            "run_id": self.run_id,
            "objective": self.objective,
            "state": self.state,
            "report": self.report,
            "errors": list(self.errors),
            "audit_ids": list(self.audit_ids),
        }


# ---------------------------------------------------------------------------
# Delegation resolution (read-only, fail-closed)
# ---------------------------------------------------------------------------
def resolve_delegation(
    request: FrontDoorRequest,
    provider: DelegationProvider | None = None,
) -> Delegation:
    """Resolve an EXISTING structured Delegation (read-only, fail-closed).

    Consumes only the DelegationProvider (default: the protected file
    registry). Returns the Delegation when it exists, matches the requested id
    and project, is ACTIVE, and is neither revoked nor expired.

    Raises NoValidDelegation on any failure (AUTH-INV-05/06). The front door
    never creates a delegation, never sets ACTIVE, and never derives authority
    from prose — it only reads and matches.
    """
    if not isinstance(request, FrontDoorRequest):
        raise FrontDoorError(
            "resolve_delegation requires a FrontDoorRequest, got "
            f"{type(request).__name__}")

    if provider is None:
        provider = FileDelegationProvider(base=request.base,
                                          project=request.project)
    if not isinstance(provider, DelegationProvider):
        raise NoValidDelegation(
            "intake",
            f"invalid delegation provider type {type(provider).__name__}",
            "DENY")

    delegation, revocations = provider.current()
    if delegation is None:
        raise NoValidDelegation(
            "intake",
            f"no delegation in registry for project {request.project!r} "
            "(AUTH-INV-05: a structured Delegation is required; model text, "
            "state records, and messages are never authority)",
            "DENY")

    if delegation.id != request.delegation_id:
        raise NoValidDelegation(
            "intake",
            f"delegation {delegation.id!r} does not match requested "
            f"{request.delegation_id!r} (AUTH-INV-05)",
            "DENY")

    if delegation.project != request.project:
        raise NoValidDelegation(
            "intake",
            f"delegation project {delegation.project!r} does not match "
            f"{request.project!r} (AUTH-INV-05)",
            "DENY")

    if delegation.status != "ACTIVE":
        # Never set ACTIVE — a non-ACTIVE record is not usable authority.
        raise NoValidDelegation(
            "intake",
            f"delegation {delegation.id} status {delegation.status} "
            "(not ACTIVE) — the front door never sets ACTIVE (AUTH-INV-05)",
            "DENY")

    if is_revoked(delegation, revocations):
        raise NoValidDelegation(
            "intake",
            f"delegation {delegation.id} is revoked (AUTH-INV-06)",
            "DENY")

    if is_expired(delegation):
        raise NoValidDelegation(
            "intake",
            f"delegation {delegation.id} is expired (AUTH-INV-06)",
            "DENY")

    return delegation


# ---------------------------------------------------------------------------
# Front-door run (the ONLY execution path)
# ---------------------------------------------------------------------------
def run_front_door(
    request: FrontDoorRequest,
    *,
    provider: DelegationProvider | None = None,
    subtask_runner: Callable | None = None,
    action_executor: Callable | None = None,
    live_dispatch=None,
    now=None,
) -> FrontDoorResult:
    """Run one front-door request through ProductionRun.

    Path
    ----
    shape validation → resolve existing structured Delegation →
    ProductionRun.run() → structured terminal result

    ``subtask_runner`` and ``action_executor`` are operator/test hooks
    forwarded unchanged to ProductionRun. They never grant authority; they
    only shape how subtasks are executed and verified.

    ``live_dispatch`` is an explicit request for REAL DSH execution (G1). It is
    threaded unchanged through ProductionRun → the bounded executor → the
    runtime flow, which selects the live DSH bridge backend only when the D4/D7
    bridge marker is present; if the bridge is unavailable the flow fails
    closed (``BridgeNotAvailable`` → BLOCKED) — never a silent fallback to the
    fake backend. ``None`` (default) keeps the deterministic in-process fake
    backend (local mode).

    Returns a FrontDoorResult with status COMPLETE | BLOCKED | ESCALATED |
    ERROR and run_id/state/report/errors/audit_ids where available.
    """
    # Accept a plain dict as a convenience (coerced through FrontDoorRequest
    # validation).
    if not isinstance(request, FrontDoorRequest):
        try:
            request = FrontDoorRequest(**request)
        except (TypeError, ValueError) as e:
            return FrontDoorResult(
                status=ERROR,
                errors=(f"invalid request shape: {e}",))

    # We use a single outer try/except so the error-handling path can read
    # ProductionRun.state after a caught exception.
    run: ProductionRun | None = None

    try:
        # 1. Resolve the ONLY authority record — read-only, fail-closed.
        #    Never creates a delegation, never sets ACTIVE, never derives
        #    authority from prose.
        delegation = resolve_delegation(request, provider=provider)

        # 2. ProductionRun is the ONLY execution path. No ExecutionFlow call,
        #    no raw DSH tool, no gate bypass.
        run = ProductionRun(project=request.project, base=request.base,
                            now=now, live_dispatch=live_dispatch)
        state = run.run(
            objective=request.objective,
            scope=request.scope,
            constraints=request.constraints,
            expected_outcome=request.expected_outcome,
            required_authority_context=request.delegation_id,
            delegation=delegation,
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
            live_dispatch=live_dispatch,
        )

        # 3. Map the successful outcome.
        if state.outcome == "complete" and state.report is not None:
            return FrontDoorResult(
                status=COMPLETE,
                run_id=state.run_id,
                objective=state.objective or request.objective,
                state=state.to_dict(),
                report=state.report,
                errors=state.errors,
                audit_ids=state.audit_ids,
            )
        # ProductionRun should only return when outcome is "complete". If it
        # returns in any other terminal state, treat as BLOCKED.
        return FrontDoorResult(
            status=BLOCKED,
            run_id=state.run_id,
            objective=state.objective or request.objective,
            state=state.to_dict(),
            report=state.report,
            errors=state.errors or ("production run did not complete",),
            audit_ids=state.audit_ids,
        )

    except FrontDoorError as e:
        # Shape validation failed before any run was created.
        return FrontDoorResult(
            status=ERROR,
            errors=(str(e),))

    except NoValidDelegation as e:
        # No valid delegation could be resolved (fail-closed denial).
        return _stopped(BLOCKED, run, e, request)

    except ProductionEscalated as e:
        # A gate escalated (needs Human approval / attention).
        return _stopped(ESCALATED, run, e, request)

    except (ProductionDenied, ProductionStopped, ObjectiveNotActionable,
            PlanRejected, ReportGenerationFailed) as e:
        # A gate denial or plan rejection (fail-closed).
        return _stopped(BLOCKED, run, e, request)

    except Exception as e:  # noqa: BLE001 — fail-closed
        return FrontDoorResult(
            status=ERROR,
            errors=(f"unexpected front-door error: {e}",))


# ---------------------------------------------------------------------------
# run_from_chat — public API alias
# ---------------------------------------------------------------------------
def run_from_chat(
    objective: str,
    scope: tuple[str, ...],
    delegation_id: str,
    *,
    constraints: tuple[str, ...] = (),
    expected_outcome: str = "",
    project: str = "multi-agent-harness",
    base: str | None = None,
    environment: str = "dev",
    provider: DelegationProvider | None = None,
    subtask_runner: Callable | None = None,
    action_executor: Callable | None = None,
    live_dispatch=None,
    now=None,
) -> FrontDoorResult:
    """Thin adapter: keyword arguments → FrontDoorRequest → run_front_door.

    This is the public API for integrating from chat/script/CLI. It builds a
    validated FrontDoorRequest and delegates to the internal run_front_door.

    ``live_dispatch`` is an explicit request for REAL DSH execution (G1). See
    ``run_front_door`` for the full live-mode semantics. Default ``None`` keeps
    the deterministic in-process fake backend (local mode).

    Example
    -------
    >>> result = run_from_chat(
    ...     objective="produce a design document",
    ...     scope=("docs/design/x.md",),
    ...     delegation_id="delegation-prod-001",
    ... )
    >>> result.status
    'COMPLETE'

    Raises
    ------
    None — every failure is returned as a fail-closed ERROR result
    (the adapter never raises on caller-supplied input).
    """
    try:
        request = FrontDoorRequest(
            objective=objective,
            scope=scope,
            delegation_id=delegation_id,
            constraints=constraints,
            expected_outcome=expected_outcome,
            project=project,
            base=base,
            environment=environment,
        )
    except FrontDoorError as e:
        # Fail-closed: a malformed request never starts a run.
        return FrontDoorResult(status=ERROR, errors=(str(e),))
    return run_front_door(
        request,
        provider=provider,
        subtask_runner=subtask_runner,
        action_executor=action_executor,
        live_dispatch=live_dispatch,
        now=now,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stopped(
    status: str,
    run: ProductionRun | None,
    exc: Exception,
    request: FrontDoorRequest,
) -> FrontDoorResult:
    """Build a FrontDoorResult from a stopped/incomplete run."""
    state = run.state if run is not None else None
    reason = getattr(exc, "reason", "") or str(exc)
    errors = (reason,)
    if state and state.errors:
        errors = errors + tuple(state.errors)
    return FrontDoorResult(
        status=status,
        run_id=state.run_id if state else None,
        objective=(state.objective if state and state.objective
                   else request.objective),
        state=state.to_dict() if state else None,
        report=state.report if state else None,
        errors=errors,
        audit_ids=state.audit_ids if state else (),
    )


__all__ = [
    # Schema
    "SCHEMA",
    # Statuses
    "COMPLETE", "BLOCKED", "ESCALATED", "ERROR", "STATUSES",
    # Exceptions
    "FrontDoorError",
    # Request
    "FrontDoorRequest",
    # Result
    "FrontDoorResult",
    # Core functions
    "resolve_delegation",
    "run_front_door",
    "run_from_chat",
]