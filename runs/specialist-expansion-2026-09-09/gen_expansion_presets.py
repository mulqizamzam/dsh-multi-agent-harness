#!/usr/bin/env python3
"""Generate the 8 expansion agent.cordis.yml preset drafts (PRD v0.2 Task 7).

L-group (vera, quill, ledger) = badsector's 10-row structure (no web).
W-group (argus, atlas, tess, scout, talon) = cfo's 11-row structure (tool-web,
fetch: false). Header marks every file REGISTERED-NOT-MOUNTED (ADR 0003 D8).
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

L_GROUP = {"vera", "quill", "ledger"}
PERSONA = {
    "vera": """You are Vera, the Verification & Evidence specialist. You verify acceptance criteria, inspect test results, check evidence completeness, and detect unsupported completion claims. You are read-only: you never mutate, never execute, and never authorize. A verification result from you is evidence for the control plane, never authorization. You escalate through the orchestrator.""",
    "argus": """You are Argus, the Security Engineering specialist. Your domain is threat modeling, privilege and trust-boundary analysis, permission and isolation analysis, injection analysis, and security control recommendations. You are read-only analysis: you never mutate, never execute, and never authorize. Your findings inform decisions; they do not grant authority. You escalate through the orchestrator.""",
    "atlas": """You are Atlas, the Architecture specialist. Your domain is architecture review, dependency boundaries, interfaces, coupling, component ownership, and architectural trade-offs. You do not replace CTO and do not implement. You are read-only: you never mutate, never execute, and never authorize. You escalate through the orchestrator.""",
    "tess": """You are Tess, the Failure Engineering specialist. Your domain is timeout, cancellation, partial-failure, race-condition, degraded-state, and recovery-path analysis. You are read-only: you never mutate, never execute, and never authorize. You escalate through the orchestrator.""",
    "quill": """You are Quill, the Policy & Specification Engineering specialist. You translate already-authorized policy and project contracts into explicit, machine-checkable constraints: invariants, rules, schema implications, and executable-test mappings. You never create policy and never authorize state transitions. You escalate through the orchestrator.""",
    "scout": """You are Scout, the Integration & Compatibility specialist. Your domain is integration analysis, API, plugin, dependency, and environment compatibility, and version-drift detection. You are read-only: you never mutate, never execute, and never authorize. You escalate through the orchestrator.""",
    "talon": """You are Talon, the Reliability Engineering specialist. Your domain is idempotency, retry semantics, durability, rollback, recovery semantics, and repeated-execution consistency. You are read-only: you never mutate, never execute, and never authorize. You escalate through the orchestrator.""",
    "ledger": """You are Ledger, the Audit & Provenance specialist. You validate audit integrity, provenance, decision lineage, and traceability. You never create authority, never approve state transitions, and never alter audit history. You escalate through the orchestrator.""",
}
DISPLAY = {"vera": "Vera", "argus": "Argus", "atlas": "Atlas", "tess": "Tess",
           "quill": "Quill", "scout": "Scout", "talon": "Talon", "ledger": "Ledger"}
TITLE = {"vera": "Verification & Evidence", "argus": "Security Engineering",
         "atlas": "Architecture", "tess": "Failure Engineering",
         "quill": "Policy & Specification", "scout": "Integration & Compatibility",
         "talon": "Reliability Engineering", "ledger": "Audit & Provenance"}


def gen_preset(rid):
    L = []
    L.append(f"# Role preset: {DISPLAY[rid]} ({TITLE[rid]})")
    L.append("# PRD v0.2 expansion (ADR 0003); NOT yet mounted — per-case Human exception")
    L.append("# required (ADR 0003 D8). Registration is not activation: this draft becomes")
    L.append("# part of the live web profile composition only if the operator approves the")
    L.append("# 8-row insert in $DSH_HOME/profiles/web/cordis.patch.yml.")
    L.append("# Version pin: DeepSeek Harness 0.1.1-rc.2")
    L.append(f"# Source: agents/{rid}/AGENT.md + config/role-preset-mapping.yaml")
    L.append("")
    L.append("# ── identity ────────────────────────────────────────────────────────────────")
    L.append("- id: persona")
    L.append("  name: '@deepseek-ai/dsh-persona'")
    L.append("  config:")
    L.append("    text: >-")
    # wrap persona text at ~72 chars with 6-space continuation indent
    words = PERSONA[rid].split()
    line, lines = "", []
    for w in words:
        if len(line) + len(w) + 1 > 72:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    lines.append(line)
    for i, ln in enumerate(lines):
        L.append("      " + ln)
    L.append("")
    L.append("- id: agent-instructions")
    L.append("  name: '@deepseek-ai/dsh-agent-instructions'")
    L.append("  config:")
    L.append("    maxBytes: 65536")
    L.append("")
    L.append("# ── filesystem ─────────────────────────────────────────────────────────────")
    L.append("# tool-fs registers read/read_image/edit/write as a suite (VERIFIED). The")
    L.append(f"# per-role instance toolFilter (subagent_{rid}) denies edit/write"
           + (" AND bash AND web" if rid in L_GROUP else " AND bash")
           + " to enforce")
    L.append("# read-only analysis. tool-fs cannot be removed because read is needed.")
    L.append("- id: tool-fs")
    L.append("  name: '@deepseek-ai/dsh-tool-fs'")
    L.append("")
    L.append("- id: tool-fs-search")
    L.append("  name: '@deepseek-ai/dsh-tool-fs-search'")
    L.append("  config:")
    L.append("    sampleOverCapGlobResults: false")
    L.append("")
    L.append("# ── background jobs ─────────────────────────────────────────────────────────")
    L.append("- id: tool-jobs")
    L.append("  name: '@deepseek-ai/dsh-tool-jobs'")
    L.append("")
    L.append("# ── skills ─────────────────────────────────────────────────────────────────")
    L.append("- id: skill-filesystem")
    L.append("  name: '@deepseek-ai/dsh-skill-filesystem'")
    L.append("")
    L.append("- id: tool-skill")
    L.append("  name: '@deepseek-ai/dsh-tool-skill'")
    L.append("")
    L.append("# ── plan mode ───────────────────────────────────────────────────────────────")
    L.append("- id: planning")
    L.append("  name: cordis:group")
    L.append("  group: true")
    L.append("  isolate:")
    L.append("    planMode: true")
    L.append("  config:")
    L.append("    - id: plan-mode")
    L.append("      name: '@deepseek-ai/dsh-plan-mode'")
    L.append("      config:")
    L.append("        section: |")
    L.append("              You are in plan mode. Stay in plan mode until exit_plan_mode succeeds. Use non-mutating reads, searches, and static analysis to ground the analysis. Do not edit or write files. When ready, call exit_plan_mode with the complete analysis.")
    L.append("")
    L.append("# ── compaction ──────────────────────────────────────────────────────────────")
    L.append("- id: compaction")
    L.append("  name: cordis:group")
    L.append("  group: true")
    L.append("  isolate:")
    L.append("    compaction: true")
    L.append("    toolResultPruner: true")
    L.append("  config:")
    L.append("    - id: compaction-basic")
    L.append("      name: '@deepseek-ai/dsh-compaction-basic'")
    L.append("    - id: command-compact")
    L.append("      name: '@deepseek-ai/dsh-command-compact'")
    L.append("    - id: tool-result-pruner")
    L.append("      name: '@deepseek-ai/dsh-compaction-tool-result-pruner'")
    L.append("      config:")
    L.append("        thresholdChars: 8192")
    L.append("        headChars: 4096")
    L.append("        tailChars: 1024")
    L.append("")
    if rid not in L_GROUP:
        L.append("# ── web search (scoped domain research) ────────────────────────────────────")
        L.append("- id: tool-web")
        L.append("  name: '@deepseek-ai/dsh-tool-web'")
        L.append("  config:")
        L.append("    fetch: false")
        L.append("    searchTimeoutMs: 60000")
        L.append("")
    L.append("# ── todo ────────────────────────────────────────────────────────────────────")
    L.append("- id: tool-todo")
    L.append("  name: '@deepseek-ai/dsh-tool-todo'")
    L.append("  config:")
    L.append("    allowParallelInProgress: true")
    L.append("")
    L.append(f"# NOTE: NO shell (bash), NO shell group — read-only analysis role."
             + ("" if rid in L_GROUP else " Scoped web search per W-group.")
             + "")
    L.append("# NO delegation/workflow realm — subdelegation DENY BY DEFAULT (V1).")
    L.append("# NO tool-goal, NO tool-ask-user — orchestrator-only.")
    L.append("# Outputs are evidence/data for the control plane, never authority.")
    return "\n".join(L) + "\n"


def main():
    for rid in PERSONA:
        d = os.path.join(ROOT, "agents", rid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "agent.cordis.yml"), "w") as fh:
            fh.write(gen_preset(rid))
        print(f"wrote agents/{rid}/agent.cordis.yml")


if __name__ == "__main__":
    main()
