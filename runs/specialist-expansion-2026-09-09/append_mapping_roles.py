#!/usr/bin/env python3
"""Task 7b — append the 8 expansion role entries to role-preset-mapping.yaml.

Policy-reflected allow/deny (equal to the generated policy.yaml files), notes
per plan; sibling deny lists carry 14 names each (not self).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

ROLES = ["vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger"]
L_GROUP = {"vera", "quill", "ledger"}
SIBLING_ORDER = ROLES + ["zeko", "cto", "cfo", "kai", "somad", "badsector", "nova"]
NOTES = {
    "vera": "assurance verification role; project-local evidence reads only; verification result is never authorization; registered 2026-09-09, live mount pending Human per-case exception (ADR 0003 D8)",
    "argus": "security engineering analysis role; scoped web research; findings inform decisions, never authority; registered 2026-09-09, live mount pending Human per-case exception (ADR 0003 D8)",
    "atlas": "architecture review role; scoped web research; does not replace CTO; registered 2026-09-09, live mount pending Human per-case exception (ADR 0003 D8)",
    "tess": "failure engineering analysis role; scoped web research; never owns final completion verification; registered 2026-09-09, live mount pending Human per-case exception (ADR 0003 D8)",
    "quill": "policy/specification translation role; project-local reads only; translates approved policy, never creates authority; registered 2026-09-09, live mount pending Human per-case exception (ADR 0003 D8)",
    "scout": "integration/compatibility analysis role; scoped web research; never owns another specialist's domain; registered 2026-09-09, live mount pending Human per-case exception (ADR 24/ADR 0003 D8)",
    "scout": "integration/compatibility analysis role; scoped web research; never owns another specialist's domain; registered 2026-09-09, live mount pending Human per-case exception (ADR 0003 D8)",
    "talon": "reliability analysis role; scoped web research; never owns operations; registered 2026-09-09, live mount pending Human per-case exception (ADR 0003 D8)",
    "ledger": "audit/provenance validation role; project-local reads only; audit is not authority; registered 2026-09-09, live mount pending Human per-case exception (ADR 0003 D8)",
}


def allow_for(rid):
    a = ["read", "read_image", "glob", "grep", "job_kill", "job_list", "job_output"]
    if rid not in L_GROUP:
        a.append("web_search")
    a += ["skill", "exit_plan_mode", "todo_write"]
    return a


def deny_for(rid):
    d = ["bash", "edit", "write"]
    if rid in L_GROUP:
        d.append("web_search")
    d += [f"subagent_{r}" for r in SIBLING_ORDER if r != rid]
    return d


def main():
    p = os.path.join(ROOT, "config", "role-preset-mapping.yaml")
    text = open(p).read()
    if "  - id: vera\n" in text:
        print("mapping already has expansion entries")
        return
    # anchor: insert before the orchestrator block comment
    anchor = "\n# The orchestrator is the root session (ADR Decision 3 hybrid), not a"
    assert text.count(anchor) == 1
    blocks = []
    for rid in ROLES:
        allow = ",\n              ".join(" ".join(allow_for(rid)[i:i+4]) for i in range(0, len(allow_for(rid)), 4))
        deny = ",\n             ".join(" ".join(deny_for(rid)[i:i+4]) for i in range(0, len(deny_for(rid)), 4))
        b = []
        b.append("  - id: " + rid)
        b.append(f"    preset: role-{rid}")
        b.append(f"    policy_ref: agents/{rid}/policy.yaml")
        b.append("    tool_instance:")
        b.append(f"      tool_name: subagent_{rid}")
        b.append("      provider: spawn")
        b.append("      background_mode: continuable")
        b.append("      max_depth: 1")
        b.append(f"      persona: role-{rid}")
        b.append("    tool_filter:")
        b.append("      allow: [" + allow_for(rid)[0] + ", " + ", ".join(allow_for(rid)[1:]) + "]")
        b.append("      deny: [" + deny_for(rid)[0] + ", " + ", ".join(deny_for(rid)[1:]) + "]")
        b.append(f"    notes: {NOTES[rid]}")
        blocks.append("\n".join(b))
    text = text.replace(anchor, "\n" + "\n\n".join(blocks) + anchor, 1)
    open(p, "w").write(text)
    import yaml
    m = yaml.safe_load(open(p))
    ids = [r["id"] for r in m["roles"]]
    assert len(ids) == 15 and len(set(ids)) == 15, ids
    for r in m["roles"]:
        d = [t for t in r["tool_filter"]["deny"] if t.startswith("subagent_")]
        assert len(d) == 14 and f"subagent_{r['id']}" not in d, r["id"]
    print(f"mapping roles now {len(ids)}; all deny lists carry 14 siblings")


if __name__ == "__main__":
    main()
