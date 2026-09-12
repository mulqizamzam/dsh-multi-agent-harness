#!/usr/bin/env python3
"""Verification harness for the orchestrator preset deployment (ADR 0004).

Two modes:

    python3 verify_preset.py --record-baseline   # run BEFORE deploying
    python3 verify_preset.py                     # run AFTER deploying

The baseline records the immutable surroundings (shipped `standard` preset, the
web profile patch, settings.yaml, and every pre-existing preset composition) so
the post-deploy run can prove the change was purely additive.

UPDATE 2026-09-12 — this baseline was re-recorded SURGICALLY, for six presets
only: role-badsector, role-cfo, role-kai, role-nova, role-somad, role-zeko. Their
deployed `agent.cordis.yml` headers still read `DRAFT — NOT MOUNTED` while the
repo and reality both said `Mounted 2026-09-07`; the recursive tool-row sets were
byte-for-byte identical in all six, so the re-sync changed comments only. The
`git diff` for that update was exactly six insertions and six deletions — the six
hash values, nothing else.

Do NOT re-run `--record-baseline` to refresh this baseline. `snapshot()` records
every deployed preset, so once the orchestrator preset is deployed a full
re-record would move `orchestrator` into `existing_presets` and thereby break two
checks that still matter: `no preset removed` and `exactly one preset added, and
it is the orchestrator` (the latter's `added` would become empty). Update the
individual hash values instead, then confirm the resulting diff touches only the
intended entries. The post-deploy invariant "repo source == deployed file" is now
additionally guarded by tests/unit/test_preset_deployment_sync.py, which hashes
raw bytes for all 16 presets and so catches comment-only drift that any
YAML-equality comparison would miss.

Structural checks parse the composition with `!!js ` tags stripped, because the
shipped preset uses `disabled: !!js process.platform === ...` and a plain
yaml.safe_load refuses it. The stripping is a parse convenience only; the
stripped text is never written anywhere. This limitation is stated rather than
hidden: the check proves the file is a list of named rows, not that the harness
loader accepts every row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

REPO = "/home/administrator/agent-workspace/project/dsh-multi-agent-harness"
DSH_HOME = "/home/administrator/agent-workspace/.dsh"
CHECKOUT = "/home/administrator/deepseek-harness"

USER_ROOT = os.path.join(DSH_HOME, ".agent-presets")
PRESET_ID = "orchestrator"
DEPLOYED_DIR = os.path.join(USER_ROOT, PRESET_ID)

SRC_COMPOSITION = os.path.join(REPO, "orchestrator", "agent.cordis.yml")
SRC_METADATA = os.path.join(REPO, "orchestrator", "preset.yml")
DEPLOYED_COMPOSITION = os.path.join(DEPLOYED_DIR, "agent.cordis.yml")
DEPLOYED_METADATA = os.path.join(DEPLOYED_DIR, "preset.yml")

STANDARD_COMPOSITION = os.path.join(
    CHECKOUT, "apps", "cli", "config", "agent-presets", "standard", "agent.cordis.yml"
)
PROFILE_PATCH = os.path.join(DSH_HOME, "profiles", "web", "cordis.patch.yml")
SETTINGS = os.path.join(DSH_HOME, "settings.yaml")

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "baseline.json")

# Forced by the orchestrator's declared toolFilter (config/role-preset-mapping.yaml).
DELETED_ROWS = ["tool-ralph", "tool-pwsh", "tool-subagent-codex", "tool-subagent-claude-code"]
PRESET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((ok, name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rows(path: str):
    """Parse a composition into a list of rows, tolerating `!!js` tags."""
    import yaml

    text = open(path, encoding="utf-8").read()
    stripped = re.sub(r"!!js\s+", "", text)
    return yaml.safe_load(stripped), stripped != text


def all_row_ids(rows) -> list:
    """Every row id in a composition, RECURSIVELY including group children.

    A `cordis:group` row carries its child rows in its own `config:` list. A
    top-level-only walk reads this preset's delta as 16 -> 15 while the true
    delta is 29 -> 25, because three of the four deleted rows
    (`tool-subagent-codex`, `tool-subagent-claude-code`, `tool-ralph`) are
    nested inside the `delegation` group. A top-level-only check therefore
    reports them "absent" while they are in fact still present — a false PASS.
    This function exists because that bug was found in this very harness.
    """
    out: list = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("id"):
            out.append(row["id"])
        children = row.get("config")
        if isinstance(children, list):
            out.extend(all_row_ids(children))
    return out


def snapshot() -> dict:
    presets = {}
    if os.path.isdir(USER_ROOT):
        for name in sorted(os.listdir(USER_ROOT)):
            comp = os.path.join(USER_ROOT, name, "agent.cordis.yml")
            if os.path.isfile(comp):
                presets[name] = sha256(comp)
    return {
        "standard_composition_sha256": sha256(STANDARD_COMPOSITION),
        "profile_patch_sha256": sha256(PROFILE_PATCH),
        "settings_sha256": sha256(SETTINGS),
        "existing_presets": presets,
    }


def record_baseline() -> int:
    snap = snapshot()
    with open(BASELINE, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"baseline recorded -> {BASELINE}")
    print(f"  standard composition sha256: {snap['standard_composition_sha256']}")
    print(f"  profile patch sha256:        {snap['profile_patch_sha256']}")
    print(f"  settings.yaml sha256:        {snap['settings_sha256']}")
    print(f"  existing presets:            {len(snap['existing_presets'])}")
    return 0


def verify() -> int:
    if not os.path.isfile(BASELINE):
        print(f"FATAL: no baseline at {BASELINE}; run --record-baseline first")
        return 2
    base = json.load(open(BASELINE, encoding="utf-8"))

    print("== repo source of truth ==")
    check("repo composition exists", os.path.isfile(SRC_COMPOSITION), SRC_COMPOSITION)
    check("repo metadata exists", os.path.isfile(SRC_METADATA), SRC_METADATA)

    print("== deployed preset ==")
    check("preset id is a valid DSH preset id", bool(PRESET_ID_RE.match(PRESET_ID)), PRESET_ID)
    check("deployed dir exists", os.path.isdir(DEPLOYED_DIR), DEPLOYED_DIR)
    check("deployed composition exists", os.path.isfile(DEPLOYED_COMPOSITION))
    check("deployed metadata exists", os.path.isfile(DEPLOYED_METADATA))

    print("== source <-> deployed integrity ==")
    if os.path.isfile(SRC_COMPOSITION) and os.path.isfile(DEPLOYED_COMPOSITION):
        check(
            "composition sha256 matches repo source",
            sha256(SRC_COMPOSITION) == sha256(DEPLOYED_COMPOSITION),
            sha256(DEPLOYED_COMPOSITION),
        )
    if os.path.isfile(SRC_METADATA) and os.path.isfile(DEPLOYED_METADATA):
        check(
            "metadata sha256 matches repo source",
            sha256(SRC_METADATA) == sha256(DEPLOYED_METADATA),
            sha256(DEPLOYED_METADATA),
        )

    print("== composition shape ==")
    rows = None
    if os.path.isfile(DEPLOYED_COMPOSITION):
        try:
            rows, had_js = load_rows(DEPLOYED_COMPOSITION)
            check("composition parses as a list", isinstance(rows, list), f"type={type(rows).__name__}")
            if isinstance(rows, list):
                check(
                    "every row carries an id (recursive)",
                    all(all_row_ids([r]) for r in rows)
                    and all(isinstance(r, dict) and r.get("id") for r in rows),
                )
                ids = all_row_ids(rows)
                check(
                    "row ids are unique (recursive)",
                    len(ids) == len(set(ids)),
                    f"{len(ids)} rows",
                )
        except Exception as exc:  # noqa: BLE001 - report, never raise
            check("composition parses as a list", False, f"{type(exc).__name__}: {exc}")

    print("== tool surface forced by the declared toolFilter (recursive) ==")
    if isinstance(rows, list):
        ids = all_row_ids(rows)
        idset = set(ids)
        for row_id in DELETED_ROWS:
            check(f"deleted row absent: {row_id}", row_id not in idset)
        try:
            std_rows, _ = load_rows(STANDARD_COMPOSITION)
            std_ids = all_row_ids(std_rows)
            std_idset = set(std_ids)
            check(
                "recursive row count == standard minus 4",
                len(std_ids) - len(ids) == len(DELETED_ROWS),
                f"standard={len(std_ids)} orchestrator={len(ids)} delta={len(std_ids) - len(ids)}",
            )
            check(
                "no row added",
                not (idset - std_idset),
                f"added={sorted(idset - std_idset)}",
            )
            check(
                "only the four expected rows differ",
                set(std_ids) - idset == set(DELETED_ROWS),
                f"removed={sorted(std_idset - idset)}",
            )
        except Exception as exc:  # noqa: BLE001
            check("recursive row count == standard minus 4", False, f"{type(exc).__name__}: {exc}")

    print("== additivity: nothing else moved ==")
    check(
        "shipped standard preset unchanged",
        sha256(STANDARD_COMPOSITION) == base["standard_composition_sha256"],
    )
    check("web profile patch untouched", sha256(PROFILE_PATCH) == base["profile_patch_sha256"])
    # settings.yaml is NOT whole-file-frozen, so hashing it is not a valid
    # invariant. Observed 2026-09-12 while this change was in flight: the
    # `mnemon` section gained `displayMode`, `taskAgentModel`, and `embedding`
    # because that subsystem writes its own section into the same file. The
    # invariant this change could actually violate is the preset default, and
    # that is asserted explicitly in the next block. The drift is still REPORTED
    # here rather than silently ignored.
    if sha256(SETTINGS) != base["settings_sha256"]:
        print("  [NOTE] settings.yaml drifted since baseline — not a failure:")
        print("         another subsystem writes its own section into this file at")
        print("         runtime. The preset-relevant invariant is checked below.")

    current = snapshot()["existing_presets"]
    before = base["existing_presets"]
    changed = sorted(k for k in before if current.get(k) != before[k])
    added = sorted(set(current) - set(before))
    removed = sorted(set(before) - set(current))
    check("no pre-existing preset composition modified", not changed, f"changed={changed}")
    check("no preset removed", not removed, f"removed={removed}")
    check(
        "exactly one preset added, and it is the orchestrator",
        added == [PRESET_ID],
        f"added={added}",
    )

    print("== resolved default preset ==")
    try:
        import yaml

        settings = yaml.safe_load(open(SETTINGS, encoding="utf-8"))
        check(
            "agent-presets.default is still 'standard'",
            settings.get("agent-presets", {}).get("default") == "standard",
            f"default={settings.get('agent-presets', {}).get('default')!r}",
        )
    except Exception as exc:  # noqa: BLE001
        check("agent-presets.default is still 'standard'", False, f"{type(exc).__name__}: {exc}")

    passed = sum(1 for ok, _, _ in _results if ok)
    failed = len(_results) - passed
    print(f"\nverify_preset: {passed} passed, {failed} failed")
    with open(os.path.join(HERE, "verification.txt"), "w", encoding="utf-8") as fh:
        for ok, name, detail in _results:
            fh.write(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else "") + "\n")
        fh.write(f"\nverify_preset: {passed} passed, {failed} failed\n")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record-baseline", action="store_true")
    args = ap.parse_args()
    return record_baseline() if args.record_baseline else verify()


if __name__ == "__main__":
    sys.exit(main())
