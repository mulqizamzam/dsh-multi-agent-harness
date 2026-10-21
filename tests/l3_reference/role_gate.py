# tests/l3_reference/role_gate.py — INDEPENDENT role-isolation reference (O1)
#
# Phase 4 / Session B — L3 independent verification infrastructure.
#
# STATUS: REFERENCE/ORACLE ONLY. SELF-CONTAINED re-implementation of role
# isolation semantics: per-role capability boundaries from the documented
# capability matrix. Imports NOTHING from production control modules or DSH.
#
# Controls covered: L3-ISO-001..010, L3-AUTH-002. The oracle enumerates a
# role's tool/capability set from an INDEPENDENT capability matrix (the
# documented catalog), NOT from the runtime tool surface — so the runtime cannot
# influence the oracle.

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Independent capability matrix (documented catalog, docs/security/0001 §1)
# This is a REFERENCE copy of the capability matrix — a public document, not a
# secret — held independently so the verifier can cross-check the runtime
# tool surface without asking the runtime or the role.
# ---------------------------------------------------------------------------
# Capability set (tool names / capability ids).
CAP = frozenset({
    "write", "edit", "bash", "read", "grep", "glob", "web_search",
    "web_fetch", "subagent", "subagent_zeko", "subagent_cto", "subagent_cfo",
    "subagent_kai", "subagent_somad", "subagent_badsector", "subagent_nova",
    "job_list", "job_output", "job_kill", "interrupt_agent", "list_agents",
    "send_message", "financial_transaction", "routing", "control_plane",
})

# Read-only capabilities available to every role.
READ_CAPS = frozenset({"read", "grep", "glob", "web_search", "web_fetch"})

# Write/executing capabilities (the high-risk set).
WRITE_CAPS = frozenset({"write", "edit", "bash", "control_plane"})

# Per-role capability matrix (documented). Each role gets its own subset.
ROLE_CAPABILITIES: dict[str, frozenset] = {
    "orchestrator": CAP,   # orchestrator is the coordination role
    "zeko": frozenset(READ_CAPS | {"bash", "job_list", "job_output", "job_kill",
                                   "interrupt_agent", "subagent", "subagent_cto"}),
    "cto": frozenset(READ_CAPS | WRITE_CAPS | {"subagent", "subagent_nova",
                                               "subagent_somad", "subagent_badsector",
                                               "subagent_kai", "subagent_cfo"}),
    "cfo": frozenset(READ_CAPS | {"financial_transaction", "web_fetch"}),
    "kai": frozenset(READ_CAPS | {"web_fetch"}),
    "somad": frozenset(READ_CAPS),  # O5: write/edit removed (containment), content is channel-routed
    "badsector": frozenset(READ_CAPS | {"grep", "glob"}),
    "nova": frozenset(READ_CAPS),  # O5: write/edit removed (containment)
    "human": frozenset({"write", "edit", "bash", "read", "grep", "glob",
                        "web_search", "web_fetch", "control_plane"}),
}

# The subdelegation capability: only orchestrator has it (DLG-003 / V1).
DELEGATION_CAPS = frozenset({"subagent", "subagent_zeko", "subagent_cto",
                             "subagent_cfo", "subagent_kai", "subagent_somad",
                             "subagent_badsector", "subagent_nova"})

# Privileged tools that must be ABSENT from read-only role schemas.
PRIVILEGED_TOOLS = frozenset({"write", "edit", "bash", "control_plane",
                              "financial_transaction"})


@dataclass(frozen=True)
class RoleVerdict:
    decision: str
    reason: str = ""
    gate_under_test: str = "role_isolation"
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "gate_under_test": self.gate_under_test,
            "detail": dict(self.detail),
        }


def allowed_capabilities(role: str) -> frozenset:
    """Return the documented capability set for a role. Unknown role => empty
    (fail-closed)."""
    return ROLE_CAPABILITIES.get(role, frozenset())


def role_can_use(role: str, capability: str) -> bool:
    """True when the role's documented capability set contains the capability."""
    if not role or not capability:
        return False
    return capability in allowed_capabilities(role)


def verify_role_isolation(*, role, capability, actor_claimed_authority=None) -> RoleVerdict:
    """Independent role-isolation oracle.

    Checks that `capability` is within `role`'s documented capability matrix.
    DENY when:
      - role is unknown (fail-closed);
      - capability is empty/None;
      - the capability is a delegation capability and the role is not the
        orchestrator (subdelegation DENY BY DEFAULT, DLG-003);
      - the capability is a privileged tool and the role is a read-only role
        (the privileged tool must be ABSENT from the schema);
      - capability is not in the role's documented set.
    """
    if role not in ROLE_CAPABILITIES:
        return RoleVerdict("DENY", f"unknown role {role!r} (fail-closed)",
                           "role_isolation", {"role": role})

    if not capability or not str(capability).strip():
        return RoleVerdict("DENY", "empty capability (fail-closed)",
                           "role_isolation", {"role": role})

    caps = allowed_capabilities(role)

    # Subdelegation deny-by-default.
    if capability in DELEGATION_CAPS and role != "orchestrator":
        return RoleVerdict(
            "DENY",
            f"subdelegation by role {role!r} DENY BY DEFAULT (V1, DLG-003)",
            "role_isolation", {"role": role, "capability": capability})

    if capability not in caps:
        return RoleVerdict(
            "DENY",
            f"capability {capability!r} outside documented capability matrix "
            f"for role {role!r} (ISO-00x)",
            "role_isolation", {"role": role, "capability": capability,
                               "allowed": sorted(caps)})

    return RoleVerdict("ALLOW", f"capability {capability!r} within role {role!r} boundary",
                       "role_isolation", {"role": role, "capability": capability})


def enumerate_role_schema(role: str) -> list:
    """Independently enumerate a role's tool/capability set (from the matrix,
    not from the runtime). Returns a sorted list of capability names."""
    return sorted(allowed_capabilities(role))


def verify_privileged_tool_absent(role: str, observed_schema: list) -> RoleVerdict:
    """ISO-009: privileged tools must be absent from a read-only role's schema.

    `observed_schema` is the verifier's independent enumeration (e.g. from the
    instance config). Returns DENY if any privileged tool leaked in.
    """
    observed = set(observed_schema or ())
    leaked = sorted(PRIVILEGED_TOOLS & observed)
    if leaked:
        return RoleVerdict(
            "DENY",
            f"privileged tool(s) present in role {role!r} schema: {leaked}",
            "role_isolation", {"role": role, "leaked": leaked})
    return RoleVerdict("ALLOW", f"no privileged tools in role {role!r} schema",
                       "role_isolation", {"role": role})


def oracle_role(context: dict) -> dict:
    """Wrapper for the verifier."""
    mode = context.get("mode", "isolation")
    if mode == "schema":
        role = context.get("role", "")
        return RoleVerdict("ALLOW", "schema enumerated",
                           "role_isolation",
                           {"role": role, "schema": enumerate_role_schema(role)}).to_dict()
    v = verify_role_isolation(role=context.get("role", ""),
                              capability=context.get("capability", ""),
                              actor_claimed_authority=context.get("claimed_authority"))
    return v.to_dict()


__all__ = [
    "CAP",
    "ROLE_CAPABILITIES",
    "PRIVILEGED_TOOLS",
    "DELEGATION_CAPS",
    "RoleVerdict",
    "allowed_capabilities",
    "role_can_use",
    "verify_role_isolation",
    "enumerate_role_schema",
    "verify_privileged_tool_absent",
    "oracle_role",
]
