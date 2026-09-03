# orchestrator.foundation.routing — Agent routing (Phase 1D)
#
# Task-dependent specialist selection. Rules (contract §6):
#   - select the MINIMUM relevant specialist set — no blanket fan-out
#   - preserve peer topology: no specialist becomes a manager of another
#   - routing returns only specialists (execution owners); the orchestrator
#     coordinates and never routes to itself as an execution owner
#   - subdelegation is DENY BY DEFAULT: a routed specialist never gains the
#     ability to delegate onward (enforced in messaging/gates)

from __future__ import annotations

from .contracts import (
    SPECIALIST_ROLES,
    DOMAIN_ROLE,
    DOMAIN_SECONDARY,
    Task,
    ContractError,
)

# A routing decision never returns ALL specialists (no blanket fan-out).
MAX_FAN_OUT = len(SPECIALIST_ROLES) - 1  # at most 6 of the 7


class RoutingError(ValueError):
    """Raised when a routing decision is invalid or would violate topology."""


def select_agents(task: Task) -> tuple[str, ...]:
    """Select the minimum specialist set for a task by domain fit.

    Returns a tuple of role ids (primary first, optional secondary). Raises
    RoutingError if the task's domain is unknown or the selection would fan out
    to all specialists.
    """
    objective = task.objective.lower().strip()
    # Exact keyword match first, then substring match against any domain token.
    matched_domain = objective if objective in DOMAIN_ROLE else None
    if matched_domain is None:
        matches = [k for k in DOMAIN_ROLE if k in objective]
        matched_domain = matches[0] if matches else None
    if matched_domain is None:
        raise RoutingError(f"cannot route task {task.task_id}: unknown domain")

    primary = DOMAIN_ROLE[matched_domain]
    selected = [primary]
    secondary = DOMAIN_SECONDARY.get(matched_domain)
    if secondary and secondary != primary:
        selected.append(secondary)

    if len(set(selected)) > MAX_FAN_OUT:
        raise RoutingError(f"routing {task.task_id} would fan out to all specialists")
    return tuple(dict.fromkeys(selected))  # dedupe, preserve order


def validate_no_fanout(selection: tuple[str, ...]) -> None:
    """Assert a selection is not a blanket fan-out and only uses specialists."""
    bad = [r for r in selection if r not in SPECIALIST_ROLES]
    if bad:
        raise RoutingError(f"selection contains non-specialist roles {bad}")
    if len(set(selection)) > MAX_FAN_OUT:
        raise RoutingError("selection fans out to all specialists")
    if len(set(selection)) == 0:
        raise RoutingError("selection is empty")


def route_tasks(tasks) -> dict[str, tuple[str, ...]]:
    """Route a batch of tasks; returns {task_id: (roles...)}. Each task gets
    its own minimum set (no shared blanket set)."""
    result = {}
    for task in tasks:
        result[task.task_id] = select_agents(task)
    return result
