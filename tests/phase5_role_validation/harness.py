# tests/phase5_role_validation — Session E (G12) role runtime validation
#
# TEST-SUPPORT ONLY. NOT production code.
#
# Live validation harness for the roles NOT independently exercised in
# Phase-3 closure (only `cto` was proven live):
#   zeko, cfo, kai, somad, badsector, nova
#
# Per role the harness validates:
#   - role resolution (role -> subagent_<id> instance from the D4/D7 config)
#   - tool surface (allow/deny as declared; allow ∩ deny = ∅; no delegation tools)
#   - prohibited tools (per config/permissions.yaml capability matrix: tools a
#     role must NOT have)
#   - provenance (a dispatched child, when live, records role identity + real
#     run id + tool_name + stop_reason)
#   - subdelegation denial (DLG-003: a specialist cannot delegate)
#
# HONESTY RULE: the harness is gated on the D4/D7 mount marker
# (DSH_LIVE_BRIDGE_ACTIVE). When the mount is absent the live checks report
# BLOCKED / UNAVAILABLE — NEVER a fake live result. Deterministic checks
# (resolution, tool-surface config, prohibited-tools config, subdelegation
# denial) always run and must pass.

from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.dsh import RoleResolver
from orchestrator.foundation.contracts import SPECIALIST_ROLES

# The D4/D7 mount marker (tests/live_dsh/discovery.py).
BRIDGE_MARKER_ENV = "DSH_LIVE_BRIDGE_ACTIVE"

# Roles already independently exercised live in Phase-3 closure (INT-01/07).
LIVE_PROVEN_ROLES = ("cto",)

# Roles this session validates (G12: not yet independently exercised).
TARGET_ROLES = ("zeko", "cfo", "kai", "somad", "badsector", "nova")

# Delegation tools that MUST be denied for every specialist (V1 subdelegation
# DENY BY DEFAULT, DLG-003).
DELEGATION_TOOLS = (
    "subagent", "subagent_fork", "subagent_zeko", "subagent_cto",
    "subagent_cfo", "subagent_kai", "subagent_somad", "subagent_badsector",
    "subagent_nova", "send_message", "workflow", "ralph",
)

# Tools that the capability matrix (config/permissions.yaml) marks as NOT
# available to a role: filesystem mutation tools must be absent from the allow
# list of read-only/review roles. (job_kill is a process-management tool in the
# harness base toolset — it is allowed for every role and is NOT a mutation
# tool in the capability-matrix sense.)
MUTATION_TOOLS = ("bash", "edit", "write")

# Roles that are read-only / review-only per config/permissions.yaml
# (server_write/code_write/social_publishing = no, and BadSector is review-only).
READ_ONLY_ROLES = ("cfo", "kai", "badsector")

# Roles whose allow list legitimately carries mutation tools.
# Post-O5: somad/nova had write/edit removed (containment step).
# 2026-09-07 (Human-approved discriminator): zeko lost write/edit too
# (capabilities.code_write: no now enforced by the role preset composition);
# only cto holds code-mutation tools.
WRITE_CAPABLE_ROLES = ("cto",)


def bridge_active() -> bool:
    """Whether the D4/D7 mount marker is set (REAL live dispatch available)."""
    return os.environ.get(BRIDGE_MARKER_ENV, "").strip().lower() in (
        "1", "true", "yes")


@dataclass
class RoleCheck:
    """One validation check result for a role."""
    role: str
    check: str
    passed: bool = False
    detail: str = ""
    live: bool = False          # True => requires a live dispatch
    blocked: bool = False       # True => could not run (mount absent)

    def to_dict(self) -> dict:
        return {
            "role": self.role, "check": self.check,
            "pass": bool(self.passed), "live": bool(self.live),
            "blocked": bool(self.blocked), "detail": self.detail,
        }


@dataclass
class RoleValidationResult:
    """Aggregated validation result for the six target roles."""
    checks: list = field(default_factory=list)
    recorded_at: str = ""

    def add(self, check: RoleCheck) -> None:
        self.checks.append(check)

    @property
    def deterministic_failures(self) -> list:
        return [c for c in self.checks
                if not c.live and not c.passed and not c.blocked]

    @property
    def live_blocked(self) -> list:
        return [c for c in self.checks if c.live and c.blocked]

    @property
    def live_passed(self) -> list:
        return [c for c in self.checks if c.live and c.passed]

    def to_dict(self) -> dict:
        return {
            "recorded_at": self.recorded_at,
            "bridge_active": bridge_active(),
            "deterministic_failures": [c.to_dict()
                                       for c in self.deterministic_failures],
            "live_blocked": [c.to_dict() for c in self.live_blocked],
            "live_passed": [c.to_dict() for c in self.live_passed],
            "checks": [c.to_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Deterministic checks (always run; must pass)
# ---------------------------------------------------------------------------

def check_role_resolution(role: str) -> RoleCheck:
    """Role -> subagent_<id> instance resolves with the approved shape."""
    try:
        inst = RoleResolver().resolve(role)
    except Exception as e:  # noqa: BLE001
        return RoleCheck(role, "resolution", False, f"resolve failed: {e}")
    expected_tool = "subagent"
    expected_preset = f"role-{role}"
    ok = (inst.tool_name == expected_tool
          and inst.agent_preset == expected_preset
          and inst.provider == "spawn"
          and inst.max_depth == 1)
    return RoleCheck(
        role, "resolution", ok,
        f"tool_name={inst.tool_name} agent_preset={inst.agent_preset} "
        f"provider={inst.provider} max_depth={inst.max_depth}")


def check_toolfilter_consistency(role: str) -> RoleCheck:
    """The tool surface is internally consistent (allow ∩ deny = ∅, no delegation
    tools in allow, max_depth=1)."""
    try:
        inst = RoleResolver().resolve(role)
    except Exception as e:  # noqa: BLE001
        return RoleCheck(role, "toolfilter", False, f"resolve failed: {e}")
    overlap = set(inst.allow) & set(inst.deny)
    delegation_in_allow = [t for t in DELEGATION_TOOLS if t in inst.allow]
    ok = (not overlap and not delegation_in_allow and inst.max_depth == 1)
    return RoleCheck(
        role, "toolfilter", ok,
        f"allow∩deny={sorted(overlap) or '∅'} "
        f"delegation_in_allow={delegation_in_allow or 'none'} "
        f"max_depth={inst.max_depth}")


def check_prohibited_tools(role: str) -> RoleCheck:
    """Tools the capability matrix prohibits for this role are NOT in allow."""
    try:
        inst = RoleResolver().resolve(role)
    except Exception as e:  # noqa: BLE001
        return RoleCheck(role, "prohibited_tools", False,
                         f"resolve failed: {e}")
    if role in READ_ONLY_ROLES:
        # Read-only / review-only roles must not carry mutation tools.
        forbidden = [t for t in MUTATION_TOOLS if t in inst.allow]
        ok = not forbidden
        return RoleCheck(
            role, "prohibited_tools", ok,
            f"read_only_role forbidden_mutation_tools={forbidden or 'none'}")
    if role == "zeko":
        # 2026-09-07 discriminator: code_write 'no' is enforced — zeko must
        # not carry edit/write in allow (bash residual is documented).
        forbidden = [t for t in ("edit", "write") if t in inst.allow]
        ok = not forbidden
        return RoleCheck(
            role, "prohibited_tools", ok,
            f"code_write_no_role forbidden_edit_write={forbidden or 'none'}")
    # Write-capable roles: nothing extra to forbid by matrix (their allow is
    # the declared boundary). Still assert no delegation tools in allow.
    delegation_in_allow = [t for t in DELEGATION_TOOLS if t in inst.allow]
    ok = not delegation_in_allow
    return RoleCheck(
        role, "prohibited_tools", ok,
        f"write_capable_role delegation_in_allow={delegation_in_allow or 'none'}")


def check_subdelegation_denial(role: str) -> RoleCheck:
    """A specialist attempting to delegate is denied (DLG-003)."""
    from orchestrator.dsh.client import _assert_actor_may_delegate
    from orchestrator.dsh.exceptions import ProhibitedDelegation
    try:
        _assert_actor_may_delegate(role)
        return RoleCheck(role, "subdelegation_denial", False,
                         "specialist delegation was NOT denied (DLG-003)")
    except ProhibitedDelegation:
        return RoleCheck(role, "subdelegation_denial", True,
                         "specialist delegation denied (DLG-003)")
    except Exception as e:  # noqa: BLE001
        return RoleCheck(role, "subdelegation_denial", False,
                         f"unexpected: {e}")


# ---------------------------------------------------------------------------
# Live checks (gated on the mount; report BLOCKED when absent)
# ---------------------------------------------------------------------------

def check_live_provenance(role: str, bridge_dispatch=None) -> RoleCheck:
    """When the mount is active, a dispatched child records role identity +
    real run id + tool_name + stop_reason.

    `bridge_dispatch` is an optional injected dispatch for a future live run
    (mirrors tests/live_dsh/conftest.py::recording_bridge). Without a live
    bridge this check reports BLOCKED — never a fake result.
    """
    if not bridge_active():
        return RoleCheck(role, "live_provenance", False,
                         "BLOCKED: D4/D7 mount not active "
                         f"({BRIDGE_MARKER_ENV} unset); no live dispatch "
                         "performed (no fake evidence)",
                         live=True, blocked=True)
    if bridge_dispatch is None:
        return RoleCheck(role, "live_provenance", False,
                         "BLOCKED: no live bridge dispatch injected",
                         live=True, blocked=True)
    try:
        inst = RoleResolver().resolve(role)
        outcome = bridge_dispatch(inst)
        ok = bool(getattr(outcome, "run_id", "")) and \
            getattr(outcome, "stop_reason", "") == "completed"
        return RoleCheck(
            role, "live_provenance", ok,
            f"run_id={getattr(outcome, 'run_id', '')} "
            f"stop_reason={getattr(outcome, 'stop_reason', '')} "
            f"tool_name={inst.tool_name}",
            live=True)
    except Exception as e:  # noqa: BLE001 — live failure is a real observation
        return RoleCheck(role, "live_provenance", False,
                         f"live dispatch failed: {e}", live=True)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_role_validation(bridge_dispatch=None) -> RoleValidationResult:
    """Validate all six target roles. Deterministic checks always run; live
    checks report BLOCKED when the mount is absent."""
    result = RoleValidationResult(
        recorded_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    for role in TARGET_ROLES:
        result.add(check_role_resolution(role))
        result.add(check_toolfilter_consistency(role))
        result.add(check_prohibited_tools(role))
        result.add(check_subdelegation_denial(role))
        result.add(check_live_provenance(role, bridge_dispatch))
    return result


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="G12 role runtime validation (live-gated, no fake evidence)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", default="", help="write JSON report path")
    args = parser.parse_args(argv)

    result = run_role_validation()
    if args.json:
        print(json.dumps(result.to_dict(), indent=1))
    else:
        for c in result.checks:
            mark = ("BLOCKED" if c.blocked else
                    ("PASS" if c.passed else "FAIL"))
            tag = " [live]" if c.live else ""
            print(f"[{mark}]{tag} {c.role}:{c.check} — {c.detail}")
    if args.report:
        with open(args.report, "w") as f:
            json.dump(result.to_dict(), f, indent=1)

    # Exit 2 when a deterministic check fails (a live check blocked is honest,
    # not a failure). Exit 0 otherwise.
    return 2 if result.deterministic_failures else 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "BRIDGE_MARKER_ENV", "TARGET_ROLES", "READ_ONLY_ROLES",
    "WRITE_CAPABLE_ROLES", "DELEGATION_TOOLS", "MUTATION_TOOLS",
    "bridge_active", "RoleCheck", "RoleValidationResult",
    "check_role_resolution", "check_toolfilter_consistency",
    "check_prohibited_tools", "check_subdelegation_denial",
    "check_live_provenance", "run_role_validation", "main",
]
