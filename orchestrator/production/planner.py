# orchestrator.production.planner — Objective → bounded production plan
#
# Phase 4 / Session A. Turns a Human objective into an ACTIONABLE, BOUNDED
# ProductionPlan WITHOUT adding new authority:
#   - objective + scope + authority context  →  TaskIntake (Phase-3 contract)
#   - domain routing                          →  minimum specialist set
#     (orchestrator.foundation.routing.select_agents — no blanket fan-out)
#   - deterministic action/target/environment →  ExecutePlan (Phase-3 contract)
#   - deterministic risk classification       →  control.risk.RiskClassifier
#     (AUTH-INV-10: intrinsic HIGH is never downgradable)
#   - HIGH ⇒ mandatory BadSector review + approval required (THREAT-015;
#     auto-approve HIGH is FORBIDDEN — the plan only RECORDS the requirement,
#     it never fabricates an approval reference)
#
# The planner produces DATA. It never grants authority: no delegation is
# created here, no approval is invented, no gate is bypassed. Everything the
# plan claims is re-validated by the existing Phase-3 runtime gates.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dataclasses import dataclass, field

from orchestrator.foundation.contracts import (
    TaskIntake, Task, SPECIALIST_ROLES,
)
from orchestrator.foundation.routing import select_agents, validate_no_fanout
from orchestrator.runtime.flow import ExecutePlan

from .exceptions import ObjectiveNotActionable

# Write-capable domains map to a concrete write action class so the execution
# gate + verification table apply (no unrestricted action). Everything else
# maps to the safe internal-analysis action.
_WRITE_DOMAINS = frozenset({
    "engineering", "architecture", "coding", "testing", "operations",
})
_ANALYSIS_ACTION = "analysis"
_WRITE_ACTION = "write"

# Actions that are intrinsically HIGH by control.risk (kept in sync with
# INTRINSIC_HIGH_ACTIONS — the authoritative classifier is control.risk).
_INTRINSIC_HIGH_ACTIONS = frozenset({
    "production_deploy", "deploy_to_prod", "production_change",
    "destructive", "destroy", "drop_database", "delete_production",
    "purge", "wipe", "unlink", "truncate_data",
    "credential_change", "permission_change", "role_grant", "access_grant",
    "financial_transaction", "financial_commitment", "payment", "wire_transfer",
    "sensitive_publication", "publish", "material_publication",
    "delete", "drop", "truncate", "overwrite", "rm",
})


@dataclass(frozen=True)
class ProductionPlan:
    """The bounded, actionable plan for one objective (DATA — never authority).

    Fields
    ------
    intake:             the Phase-3 TaskIntake (with the required authority
                        context).
    execute_plan:       the concrete ExecutePlan (action/target/environment/
                        expected outcome) re-validated at execution time.
    declared_risk:      LOW / MEDIUM / HIGH (effective; intrinsic HIGH is
                        never downgraded).
    review_required:    True when BadSector review is MANDATORY (HIGH /
                        intrinsic-HIGH action — THREAT-015).
    approval_required:  True when the plan carries a requires_approval
                        category (approval is NEVER auto-issued).
    selected_roles:     the minimum specialist set (routing, no fan-out).
    authority_context:  the delegation id / Human approval reference the
                        objective requires.
    objective:          normalized objective text.
    """
    intake: TaskIntake
    execute_plan: ExecutePlan
    declared_risk: str = "LOW"
    review_required: bool = False
    approval_required: bool = False
    selected_roles: tuple[str, ...] = ()
    authority_context: str = ""
    objective: str = ""

    def to_dict(self) -> dict:
        return {
            "objective": self.objective,
            "authority_context": self.authority_context,
            "declared_risk": self.declared_risk,
            "review_required": self.review_required,
            "approval_required": self.approval_required,
            "selected_roles": list(self.selected_roles),
            "intake": self.intake.to_dict(),
            "execute_plan": {
                "action": self.execute_plan.action,
                "target": self.execute_plan.target,
                "environment": self.execute_plan.environment,
                "expected_outcome": dict(self.execute_plan.expected_outcome),
                "action_category": self.execute_plan.action_category,
                "description": self.execute_plan.description,
            },
        }


class ObjectivePlanner:
    """Deterministic, fail-closed planner: objective → bounded ProductionPlan.

    Parameters
    ----------
    project:      project id (default "multi-agent-harness").
    environment:  default execution environment (default "dev").
    now:          optional clock (tests) — unused by default.
    """

    def __init__(self, *, project: str = "multi-agent-harness",
                 environment: str = "dev", now=None):
        self.project = project
        self.environment = environment
        self._now = now

    # -- main ----------------------------------------------------------------

    def plan(self, *, objective: str = "", scope=(),
             constraints=(), expected_outcome: str = "",
             required_authority_context: str = "",
             declared_risk: str = "LOW",
             approval_reference: str = "",
             action: str = "",
             action_category: str = "") -> ProductionPlan:
        """Build a bounded plan from a Human objective.

        ``action`` / ``action_category`` are optional explicit action-class
        overrides (DATA — never authority): when omitted they are derived
        deterministically from the objective. An explicit action still passes
        the same risk classifier, authority gate, execution gate, and
        verification table — it cannot bypass any gate.

        Raises ObjectiveNotActionable when the objective/scope are missing or
        malformed, the domain cannot be routed, or the plan would violate a
        boundary (e.g. an intrinsic-HIGH action declared LOW).
        """
        objective = (objective or "").strip()
        scope = tuple(scope or ())
        if not objective:
            raise ObjectiveNotActionable(
                "intake", "objective is empty — cannot plan", "DENY")
        if not scope:
            raise ObjectiveNotActionable(
                "intake", "scope is empty — cannot plan", "DENY")
        if not required_authority_context.strip():
            raise ObjectiveNotActionable(
                "intake",
                "no authority context: every actionable objective must name a "
                "delegation id or Human approval reference (AUTH-INV-05)",
                "ESCALATE")

        intake = TaskIntake(
            objective=objective, scope=scope,
            constraints=tuple(constraints or ()),
            expected_outcome=expected_outcome or "",
            required_authority_context=required_authority_context.strip(),
            project=self.project,
        )

        # Deterministic action selection from the objective text (or an
        # explicit operator override — still fully gated).
        if action:
            action = action.strip()
        else:
            action, action_category, _ = self._select_action(objective, scope)
        if not action_category:
            action_category = _action_category_of(action)

        target = scope[0]
        plan = ExecutePlan(
            action=action, target=target, environment=self.environment,
            expected_outcome={
                "target": target,
                "exit_code": 0,
            } if action != _ANALYSIS_ACTION else {
                "target": target,
            },
            action_category=action_category,
            description=f"objective {objective!r} → action {action!r}",
        )

        # Minimum specialist set (routing — never all 7).
        probe = Task(
            task_id="plan-probe",
            objective=objective,
            assigned_role="cto",  # provisional; routing re-derives
            scope=scope,
            risk_metadata="LOW",
            project=self.project,
        )
        try:
            selected = select_agents(probe)
            validate_no_fanout(selected)
        except Exception as e:  # noqa: BLE001 — fail-closed
            raise ObjectiveNotActionable(
                "select", f"cannot route objective: {e}", "DENY") from e

        # Deterministic risk classification (AUTH-INV-10). The classifier is
        # authoritative; an intrinsic HIGH can never be downgraded.
        from control.risk import RiskClassifier
        rc = RiskClassifier().classify(
            action, target, self.environment,
            requires_approval=(),
            operation_flags=(), tool=None, command=None,
            declared=declared_risk)

        effective = rc.level
        intrinsic = rc.intrinsic
        if intrinsic and (declared_risk or "LOW").upper() != "HIGH":
            raise ObjectiveNotActionable(
                "classify",
                f"intrinsic HIGH action {action!r} cannot be declared "
                f"{declared_risk or 'LOW'} (AUTH-INV-10)",
                "DENY", {"risk": "HIGH", "intrinsic": True})

        # HIGH ⇒ mandatory BadSector review (THREAT-015).
        review_required = effective == "HIGH" or intrinsic or action in \
            _INTRINSIC_HIGH_ACTIONS

        # Approval requirement: HIGH/requires-approval categories are NEVER
        # auto-approved. The plan records the requirement; the caller must
        # supply a matching structured approval reference (approval-<id>).
        approval_required = effective == "HIGH" or intrinsic or action in \
            _INTRINSIC_HIGH_ACTIONS

        if approval_required and approval_reference and \
                not approval_reference.strip().startswith("approval-"):
            raise ObjectiveNotActionable(
                "classify",
                f"approval claim {approval_reference!r} is not a structured "
                "approval reference (AUTH-INV-01: text is never approval)",
                "DENY")

        return ProductionPlan(
            intake=intake,
            execute_plan=plan,
            declared_risk=effective,
            review_required=review_required,
            approval_required=approval_required,
            selected_roles=tuple(selected),
            authority_context=required_authority_context.strip(),
            objective=intake.normalized_objective(),
        )

    # -- helpers -------------------------------------------------------------

    def _select_action(self, objective: str, scope):
        """Deterministic action selection.

        Write-capable domains map to a concrete write action (the execution
        gate + verification table then govern it). Everything else maps to
        internal analysis (read-only, self-verifiable). Returns
        (action, action_category, description).
        """
        obj_l = objective.lower()
        for dom in sorted(_WRITE_DOMAINS, key=len, reverse=True):
            if dom in obj_l:
                return (_WRITE_ACTION, "code_change",
                        f"produce an artifact for objective {objective!r}")
        return (_ANALYSIS_ACTION, "internal_analysis",
                f"internal analysis for objective {objective!r}")


def _action_category_of(action: str) -> str:
    """Return the default verification category for an action class.

    This mirrors control.verification._ACTION_TO_CATEGORY but is kept
    minimal: unknown actions default to 'internal_analysis' (the most
    permissive category). The verification table is authoritative — if the
    category is unknown, the flow's execution request will raise
    VerificationError at resolve_action_category().
    """
    from control.verification import action_category
    return action_category(action)


__all__ = ["ObjectivePlanner", "ProductionPlan", "_WRITE_ACTION",
           "_ANALYSIS_ACTION", "_INTRINSIC_HIGH_ACTIONS"]