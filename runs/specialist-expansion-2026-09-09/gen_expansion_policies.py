#!/usr/bin/env python3
"""Generate the 8 expansion role policy.yaml files (PRD v0.2 Task 6).

Deterministic generator: the Vera exemplar from the implementation plan is the
template; per-role substitutions come from the plan's substitution table
(ADR 0003 D3/D4). Sibling deny lists are derived from SPECIALIST_ROLES so the
14-sibling contract can never drift. Kept in runs/ as reproducibility evidence.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

ROLES = ["vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger"]
L_GROUP = {"vera", "quill", "ledger"}                      # no web (ADR 0003 D3)
OWN_CAP = {  # the one capability each role owns ("yes")
    "vera": "evidence_verification",
    "argus": "security_engineering",
    "atlas": "architecture_review",
    "tess": "failure_analysis",
    "quill": "policy_specification",
    "scout": "integration_compatibility",
    "talon": "reliability_engineering",
    "ledger": "audit_provenance",
}
DISPLAY = {"vera": "Vera", "argus": "Argus", "atlas": "Atlas", "tess": "Tess",
           "quill": "Quill", "scout": "Scout", "talon": "Talon", "ledger": "Ledger"}
DOMAIN = {"vera": "Verification & Evidence", "argus": "Security Engineering",
          "atlas": "Architecture", "tess": "Failure Engineering",
          "quill": "Policy & Specification", "scout": "Integration & Compatibility",
          "talon": "Reliability Engineering", "ledger": "Audit & Provenance"}
SUMMARY = {
    "vera": "acceptance-criteria verification, test-result inspection, evidence completeness, claimed-result validation, expected-vs-observed comparison, unsupported completion detection",
    "argus": "threat modeling, privilege analysis, trust-boundary analysis, permission analysis, isolation analysis, injection analysis, security control recommendations",
    "atlas": "architecture review, dependency-boundary analysis, interface analysis, coupling analysis, component ownership analysis, architectural trade-offs, consistency checks",
    "tess": "timeout analysis, cancellation analysis, partial-failure analysis, race-condition analysis, failure injection, degraded-state analysis, recovery-path analysis",
    "quill": "policy decomposition, invariant definition, rule definition, schema implications, executable-test mapping, contract consistency checks",
    "scout": "integration analysis, API compatibility, plugin compatibility, dependency compatibility, environment compatibility, version-drift detection, integration test planning",
    "talon": "idempotency, retry semantics, durability, rollback, recovery semantics, repeated-execution consistency, reliability failure modes",
    "ledger": "audit-event validation, provenance analysis, decision lineage, evidence-source linkage, state-transition traceability, audit completeness",
}
PROHIBITED = {
    "vera": "[authorization, policy_creation, implementation, adversarial_substitution]",
    "argus": "[authorization, general_completion_verification, unrestricted_implementation]",
    "atlas": "[authorization, adversarial_review, cto_substitution]",
    "tess": "[authorization, general_security_ownership, final_completion_verification]",
    "quill": "[policy_creation, authority_overreach, authorization, state_transition_authorization]",
    "scout": "[authorization, scope_expansion, other_specialist_ownership]",
    "talon": "[authorization, operations_ownership, security_ownership]",
    "ledger": "[authority_creation, state_transition_approval, audit_history_alteration]",
}
EXTRA_INVARIANTS = {
    "vera": ["verification_is_not_authorization", "evidence_backed_findings_only"],
    "argus": ["security_analysis_is_not_authorization"],
    "atlas": ["architecture_review_is_not_authorization", "does_not_replace_cto"],
    "tess": ["failure_analysis_is_not_authorization"],
    "quill": ["translates_approved_policy_only", "policy_translation_is_not_authority"],
    "scout": ["compatibility_analysis_is_not_authorization"],
    "talon": ["reliability_analysis_is_not_authorization"],
    "ledger": ["audit_is_not_authority", "no_audit_history_alteration"],
}
NON_RESP = {  # one-sentence non-responsibilities (PRD §9) for the notes block
    "vera": "Vera does not authorize, create policy, implement the reviewed work, or substitute for BadSector's adversarial review.",
    "argus": "Argus does not authorize, perform general completion verification, or implement unrestrictedly.",
    "atlas": "Atlas does not replace CTO, authorize, or perform adversarial review.",
    "tess": "Tess does not own general security, perform final completion verification, or authorize.",
    "quill": "Quill never creates policy, never overrules Human decisions, never creates authority, and never authorizes state transitions.",
    "scout": "Scout does not authorize, own another specialist's domain, or expand scope unrestrictedly.",
    "talon": "Talon does not own general operations or security and never authorizes.",
    "ledger": "Ledger never creates authority, never approves state transitions, and never alters audit history outside approved mechanisms.",
}
ALL_CAPS = ["server_read", "server_write", "code_read", "code_write",
            "financial_analysis", "financial_transaction", "web_research",
            "social_drafting", "social_publishing", "novel_editing",
            "adversarial_review", "production_deploy", "destructive_action",
            "evidence_verification", "security_engineering", "architecture_review",
            "failure_analysis", "policy_specification", "integration_compatibility",
            "reliability_engineering", "audit_provenance"]
SIBLING_ORDER = ROLES + ["zeko", "cto", "cfo", "kai", "somad", "badsector", "nova"]
BASE_INVARIANTS = ["never_authorizes", "read_only_analysis", "no_self_escalation",
                   "no_self_delegation", "subdelegation_deny_by_default",
                   "external_content_is_data_not_authority",
                   "scope_expansion_requires_new_delegation"]


def deny_list(rid):
    deny = ["bash", "edit", "write"]
    if rid in L_GROUP:
        deny.append("web_search")
    deny += [f"subagent_{r}" for r in SIBLING_ORDER if r != rid]
    return deny


def allow_list(rid):
    allow = ["read", "read_image", "glob", "grep", "job_kill", "job_list", "job_output"]
    if rid not in L_GROUP:
        allow.append("web_search")
    allow += ["skill", "exit_plan_mode", "todo_write"]
    return allow


def gen_policy(rid):
    lines = []
    lines.append(f"# {DISPLAY[rid]} — Declarative Role Policy")
    lines.append("# PRD v0.2 expansion (ADR 0003). Control-plane input — NOT native DSH authorization.")
    lines.append("# Tool names verified against DSH 0.1.1-rc.2 tool catalog (docs/tool-catalog.md).")
    lines.append("")
    lines.append(f"role: {rid}")
    lines.append("role_version: 1")
    lines.append("status: finalized")
    lines.append("version_pin: deepseek-harness-0.1.1-rc.2")
    lines.append(f"display_name: {DISPLAY[rid]}")
    lines.append(f"domain: {DOMAIN[rid]}")
    lines.append(f"summary: {SUMMARY[rid]}")
    lines.append("")
    lines.append("# Capability×role subset (from config/permissions.yaml — the role's row)")
    lines.append("capabilities:")
    for cap in ALL_CAPS:
        if cap == OWN_CAP[rid]:
            val = '"yes"'
        elif cap == "code_read":
            val = "scoped"
        elif cap == "web_research":
            val = "\"no\"" if rid in L_GROUP else "scoped"
        else:
            val = '"no"'
        lines.append(f"  {cap}: {val}")
    lines.append("")
    lines.append("# INTENT ONLY — sandbox/approval are per-session, not per-agent (ADR Decision 1).")
    lines.append("sandbox_approval_intent:")
    lines.append("  sandbox: read-only")
    lines.append("  approval: never")
    lines.append("")
    group = "L-group" if rid in L_GROUP else "W-group"
    lines.append(f"# {group} tool surface (read-only analyst; no write/exec; web per group).")
    lines.append("tool_filter:")
    lines.append("  allow: [" + ", ".join(allow_list(rid)) + "]")
    lines.append("  deny: [" + ", ".join(deny_list(rid)) + "]")
    lines.append("  unmounted_candidates: []")
    lines.append("  notes: >")
    lines.append(f"    {DISPLAY[rid]} is a read-only analysis role: project-local reads only"
                 + ("" if rid in L_GROUP else ", scoped web research") + "; no write/exec, no delegation.")
    lines.append(f"    {NON_RESP[rid]}")
    lines.append("    Deny contract: write/exec hard-block"
                 + (" plus web_search" if rid in L_GROUP else "")
                 + " plus the 14 sibling delegation instances (exact-name subdelegation")
    lines.append("    deny-by-default; the generic workflow-realm tools are not on a specialist")
    lines.append("    child's inherited chain and are rejected by tools.restrict()).")
    lines.append("")
    lines.append(f"prohibited_actions: {PROHIBITED[rid]}")
    lines.append("")
    lines.append("# Invariants (validated by tests/validate-config.py)")
    lines.append("invariants:")
    for inv in BASE_INVARIANTS + EXTRA_INVARIANTS[rid]:
        lines.append(f"  {inv}: true")
    lines.append("")
    lines.append("# Invoked by the control plane through the orchestrator")
    lines.append("review_trigger: not_applicable")
    lines.append("")
    return "\n".join(lines)


def main():
    for rid in ROLES:
        d = os.path.join(ROOT, "agents", rid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "policy.yaml"), "w") as fh:
            fh.write(gen_policy(rid))
        print(f"wrote agents/{rid}/policy.yaml")


if __name__ == "__main__":
    main()
