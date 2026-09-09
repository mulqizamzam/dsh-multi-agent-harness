#!/usr/bin/env python3
"""Task 7c — append the 8 expansion instance rows to tool-subagent-instances.yaml.

cordis-patch style, identical toolFilter content to the mapping entries.
Rows stay REGISTERED-pending-mount (ADR 0003 D8) — this file is the
composition source-of-record, not the live profile.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

ROLES = ["vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger"]
L_GROUP = {"vera", "quill", "ledger"}
SIBLING_ORDER = ROLES + ["zeko", "cto", "cfo", "kai", "somad", "badsector", "nova"]


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
    p = os.path.join(ROOT, "config", "tool-subagent-instances.yaml")
    text = open(p).read()
    if "  - id: tool-subagent-vera\n" in text:
        print("instances already have expansion rows")
        return
    anchor = "\n# Consistency guardrails (validated by tests/validate-config.py):"
    assert text.count(anchor) == 1
    blocks = []
    for rid in ROLES:
        b = []
        b.append(f"  - id: tool-subagent-{rid}")
        b.append("    name: '@deepseek-ai/dsh-tool-subagent'")
        b.append("    config:")
        b.append("      provider: spawn")
        b.append(f"      toolName: subagent_{rid}")
        b.append(f"      persona: role-{rid}")
        b.append("      backgroundMode: continuable")
        b.append("      maxDepth: 1")
        b.append("      toolFilter:")
        allow = allow_for(rid)
        deny = deny_for(rid)
        b.append("        allow: [" + ", ".join(allow) + "]")
        b.append("        deny: [" + ", ".join(deny) + "]")
        blocks.append("\n".join(b))
    text = text.replace(anchor, "\n" + "\n\n".join(blocks) + anchor, 1)
    open(p, "w").write(text)
    import yaml
    ins = yaml.safe_load(open(p))
    rows = ins["insert_draft"]
    assert len(rows) == 15, len(rows)
    names = {r["config"]["toolName"] for r in rows}
    assert names == {f"subagent_{x}" for x in SIBLING_ORDER}, names
    for r in rows:
        d = [t for t in r["config"]["toolFilter"]["deny"] if t.startswith("subagent_")]
        assert len(d) == 14 and r["config"]["toolName"] not in d, r["id"]
    print(f"instance rows now {len(rows)}; all 14-sibling deny; source-of-record updated (not mounted)")


if __name__ == "__main__":
    main()
