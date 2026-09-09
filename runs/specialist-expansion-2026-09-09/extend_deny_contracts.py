#!/usr/bin/env python3
"""Task 7a — extend the sibling deny contract 6 -> 14 (ADR 0003 D4).

The ONE change that touches the baseline seven roles: every specialist deny
list (agents/<id>/policy.yaml, config/role-preset-mapping.yaml,
config/tool-subagent-instances.yaml) gains the 8 new sibling instance names
appended in PRD v0.2 order. Also: mapping_version 1->2 + orchestrator allow
+= 8 instance names; instances draft_version 1->2 + header wording. Verifies
parsed deny sets afterwards.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

NEW = ["subagent_vera", "subagent_argus", "subagent_atlas", "subagent_tess",
       "subagent_quill", "subagent_scout", "subagent_talon", "subagent_ledger"]
BASELINE = ["zeko", "cto", "cfo", "kai", "somad", "badsector", "nova"]

ENDINGS = {  # unique closing text of each baseline deny list
    "zeko": "subagent_somad, subagent_badsector, subagent_nova]",
    "cto": "subagent_badsector, subagent_nova, subagent_zeko]",
    "cfo": "subagent_badsector, subagent_nova, subagent_zeko]",
    "kai": "subagent_badsector, subagent_nova, subagent_zeko]",
    "somad": "subagent_badsector, subagent_nova, subagent_zeko]",
    "badsector": "subagent_somad, subagent_nova, subagent_zeko]",
    "nova": "subagent_somad, subagent_badsector, subagent_zeko]",
}


def extend_in_segments(text, rid_marker_fmt, endings, indent):
    """Extend deny lists file-section-wise: each role's block runs from its
    `id:` marker line to the next marker; the ending must be unique WITHIN
    the block (identical deny lists across roles share file-level endings)."""
    lines = text.split("\n")
    # collect marker line indexes
    markers = [(i, ln) for i, ln in enumerate(lines) if ln.startswith(rid_marker_fmt)]
    for idx, (start, ln) in enumerate(markers):
        rid = ln[len(rid_marker_fmt):].strip().rstrip(":")
        if rid not in endings:
            continue
        end = markers[idx + 1][0] if idx + 1 < len(markers) else len(lines)
        seg = "\n".join(lines[start:end])
        ending = endings[rid]
        if seg.count(ending) == 0:
            print(f"skip {rid} (already extended)")
            continue
        assert seg.count(ending) == 1, f"{rid}: x{seg.count(ending)}"
        seg = seg.replace(ending, ending[:-1] + ",\n" + indent + (",\n" + indent).join(NEW) + "]", 1)
        lines[start:end] = seg.split("\n")
    return "\n".join(lines)


def extend_file(path, rid_to_indent):
    text = open(path).read()
    for rid, (ending, indent) in rid_to_indent.items():
        text = append_names(text, ending, indent)
    open(path, "w").write(text)


def main():
    import yaml

    # 1. baseline policy.yaml files (continuation indent: 9 spaces)
    for rid in BASELINE:
        p = os.path.join(ROOT, "agents", rid, "policy.yaml")
        text = open(p).read()
        if "subagent_vera" in text:
            print(f"already extended agents/{rid}/policy.yaml")
            continue
        ending = ENDINGS[rid]
        assert text.count(ending) == 1, f"{p}: {text.count(ending)}"
        add = ",\n         " + ", ".join(NEW) + "]"
        text = text.replace(ending, ending[:-1] + add, 1)
        open(p, "w").write(text)
        d = yaml.safe_load(open(p))
        deny = d["tool_filter"]["deny"]
        assert set(NEW) <= set(deny), rid
        print(f"extended agents/{rid}/policy.yaml deny -> {len(deny)} entries")

    # 2. role-preset-mapping.yaml (continuation indent: 13 spaces)
    p = os.path.join(ROOT, "config", "role-preset-mapping.yaml")
    text = open(p).read()
    for rid in BASELINE:
        if text.count(ENDINGS[rid]) == 0:
            print(f"skip mapping deny {rid} (already extended)")
            continue
        text = extend_in_segments(text, "  - id: ", ENDINGS, "             ")
    # orchestrator allow += 8 instance names
    anchor = "            workflow, skill, ask_user_question, exit_plan_mode,"
    if "            subagent_vera, subagent_argus" not in text:
        assert text.count(anchor) == 1
        text = text.replace(
            anchor,
            "            subagent_vera, subagent_argus, subagent_atlas, subagent_tess,\n"
            "            subagent_quill, subagent_scout, subagent_talon, subagent_ledger,\n" + anchor, 1)
    if "mapping_version: 1" in text:
        text = text.replace("mapping_version: 1", "mapping_version: 2", 1)
    if "six sibling subagent_<id> instances" in text:
        text = text.replace(
            "every deny list names exactly the six sibling subagent_<id> instances",
            "every deny list names exactly the fourteen sibling subagent_<id> instances", 1)
    if "Registration is not activation." not in text:
        text = text.replace(
            "#  - Mounted 2026-09-07: per-role presets/instances ARE mounted in the live",
            "#  - PRD v0.2 expansion (2026-09-09, ADR 0003): eight new roles (vera,\n"
            "#    argus, atlas, tess, quill, scout, talon, ledger) are REGISTERED here\n"
            "#    (mapping_version 2). Their tool-subagent instances are NOT yet mounted\n"
            "#    in the live profile: mount is the separate Human per-case exception\n"
            "#    (ADR 0003 D8). Registration is not activation.\n"
            "#  - Mounted 2026-09-07: per-role presets/instances ARE mounted in the live", 1)
    open(p, "w").write(text)
    m = yaml.safe_load(open(p))
    assert len(m["roles"]) >= 7, len(m["roles"])   # 15 after the Task 7 append step
    assert m["mapping_version"] == 2
    print(f"extended {p} -> {len(m['roles'])} roles so far, orchestrator allow +8")

    # 3. tool-subagent-instances.yaml (continuation indent: 15 spaces)
    p = os.path.join(ROOT, "config", "tool-subagent-instances.yaml")
    text = open(p).read()
    for rid in BASELINE:
        if text.count(ENDINGS[rid]) == 0:
            print(f"skip instance deny {rid} (already extended)")
            continue
        text = extend_in_segments(text, "  - id: tool-subagent-", ENDINGS, "               ")
    if "draft_version: 1" in text:
        text = text.replace("draft_version: 1", "draft_version: 2", 1)
    if "six sibling subagent_<id> instances" in text:
        text = text.replace(
            "its six sibling subagent_<id> instances",
            "its fourteen sibling subagent_<id> instances", 1)
    if "REGISTERED-pending-mount" not in text:
        text = text.replace(
            "draft_version: 2\nstatus: mounted           # was: draft — mounted 2026-09-07 (Human-approved D4/D7)",
            "draft_version: 2\n"
            "status: mounted           # 7 baseline rows mounted 2026-09-07 (Human-approved\n"
            "                          # D4/D7). The 8 PRD v0.2 expansion rows (vera..ledger)\n"
            "                          # are REGISTERED-pending-mount: inserting them into the\n"
            "                          # live profile is the separate Human per-case exception\n"
            "                          # (ADR 0003 D8) and is NOT executed by this change.", 1)
    open(p, "w").write(text)
    ins = yaml.safe_load(open(p))
    assert len(ins["insert_draft"]) == 7, len(ins["insert_draft"])
    print(f"extended {p} deny lists -> {len(ins['insert_draft'])} rows (8 new rows added separately)")

    print("deny contract 6 -> 14: OK")


if __name__ == "__main__":
    main()
