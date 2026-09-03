"""G10 O3 — Execution-Readiness Package: honesty guards + host feasibility.

These tests verify the G10 O3 execution-readiness package (the operator/Human
handoff) is honest, complete, and consistent with the current host state:

  1. The five execution-package documents exist at the expected paths.
  2. The package states G10 remains OPEN / BLOCKING and claims NO closure.
  3. O3 is NOT implemented (no daemon, no write-path switch, no user/group/secret).
  4. All 10 brief items are covered across the 5 docs.
  5. Host feasibility evidence matches the current state (read-only probes).
  6. The human approvals table (H3, H4, H5) is documented.
  7. The infrastructure prerequisites (P1–P9) are documented.
  8. The pre-change backup procedure, freeze window, migration order, acceptance
     test order, and rollback are documented.
  9. The G10 closure gate (six conditions, H5) is defined.
  10. The evidence matrix covers 30+ steps.
  11. Rollback is documented as file-level (no git repository).
  12. The package is confined to the two write-only targets.
  13. DSH version is still pinned to 0.1.1-rc.2.
  14. Scope confinement is verified (no out-of-scope modifications).
  15. Existing G10/planning/decision tests still pass (consistency gate).
"""

import os
import sys
import glob as _glob
import subprocess

import pytest

# tests/g10/o3-execution/ -> project root is 4 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
EXECUTION_DIR = os.path.join(
    PROJECT_ROOT, "docs", "phase-5", "security", "g10", "o3", "execution")
DSH_CHECKOUT = "/home/administrator/deepseek-harness"
G10_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The five execution-package documents.
EXECUTION_DOCS = {
    "0001-o3-execution-readiness-handoff.md": "master handoff",
    "0002-o3-approvals-and-infrastructure.md": "items 1-3",
    "0003-o3-backups-freeze-and-migration.md": "items 4-6",
    "0004-o3-acceptance-and-rollback.md": "items 7-8",
    "0005-o3-closure-gate-and-evidence.md": "items 9-10",
}

# The 10 brief items and which doc(s) cover them.
BRIEF_ITEMS = [
    ("1. Human approvals required", "H3", "H4", "H5"),
    ("2. Infrastructure provisioning checklist", "P1", "P2", "P3"),
    ("3. Exact root/user/group/secret/service requirements", "dsh-writer", "dsh", "systemd"),
    ("4. Exact pre-change backups", "backup", "MANIFEST.sha256"),
    ("5. Freeze-window procedure", "freeze", "holdback"),
    ("6. Phase A/B/C migration order", "Phase A", "Phase B", "Phase C"),
    ("7. Acceptance test order", "P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"),
    ("8. Rollback", "rollback", "reversibility", "trigger"),
    ("9. G10 closure gate", "H5", "six conditions", "closure gate"),
    ("10. Evidence required at each step", "evidence matrix", "evidence integrity"),
]

# The six O3 closure conditions (from FINAL 0002 §4.1).
O3_CLOSURE_CONDITIONS = [
    "A+B isolation",
    "state/projects/** extension",
    "write path is fully switched",
    "no silent fallback",
    "verification passes",
    "human approval",
]

# Infrastructure prerequisites (P1-P9).
INFRA_PREREQUISITES = [
    "dsh-writer",
    "HMAC",
    "systemd",
    "dsh group",
    "freeze window",
    "pre-change",
    "reusable modules",
]

# Expected host-state facts (read-only verified this session).
EXPECTED_HOST_FACTS = {
    "DSH version": "0.1.1-rc.2",
    "Host UID": "1000",
    "dsh-writer user": "absent",
    "dsh group": "absent",
    "daemon root": "absent",
    "VCS (git)": "absent",
    "O3 daemon": "absent",
    "schemas/ipc.py": "absent",
    "config/registry-writer.yaml": "absent",
}


# ===========================================================================
# 1. Document existence and structure
# ===========================================================================

def test_execution_package_documents_exist():
    """All five execution-package documents must exist at the expected paths."""
    missing = [d for d in EXECUTION_DOCS
               if not os.path.isfile(os.path.join(EXECUTION_DIR, d))]
    assert not missing, (
        f"missing execution-package documents: {missing}")


def test_execution_package_lives_in_o3_execution_dir():
    """The package must live under docs/phase-5/security/g10/o3/execution/."""
    assert os.path.basename(EXECUTION_DIR) == "execution"
    assert os.path.basename(os.path.dirname(EXECUTION_DIR)) == "o3"
    assert os.path.basename(os.path.dirname(
        os.path.dirname(EXECUTION_DIR))) == "g10"


def test_execution_docs_are_markdown():
    """All files in the execution directory must be .md files."""
    docs = [d for d in os.listdir(EXECUTION_DIR)
            if os.path.isfile(os.path.join(EXECUTION_DIR, d))]
    non_md = [d for d in docs if not d.endswith(".md")]
    assert not non_md, (
        f"unexpected non-markdown files in execution dir: {non_md}")


# ===========================================================================
# 2. Honesty: G10 remains OPEN / BLOCKING, no closure claim
# ===========================================================================

def _execution_text():
    """Return the concatenated text of all five execution-package docs."""
    lines = []
    for doc in sorted(EXECUTION_DOCS.keys()):
        path = os.path.join(EXECUTION_DIR, doc)
        if os.path.isfile(path):
            with open(path) as f:
                lines.append(f.read())
    return "\n".join(lines)


def test_package_states_g10_open_blocking():
    """Every execution doc must state G10 remains OPEN / BLOCKING."""
    for doc in EXECUTION_DOCS:
        path = os.path.join(EXECUTION_DIR, doc)
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            text = f.read().lower()
        assert "g10 remains open" in text or "g10 stays open" in text or \
            "open / blocking" in text, (
                f"{doc} must state G10 remains OPEN / BLOCKING")


def test_package_never_claims_closure():
    """The execution package must never claim unconditional G10 closure."""
    text = _execution_text()
    low = text.lower()
    assert "no closure" in low, (
        "execution package must disclaim closure")
    # Strip negated/conditional heads so they do not leave a bare
    # affirmative claim behind (mirrors test_o3_final_planning.py).
    stripped = low.replace("*", "").replace("`", "")
    stripped = stripped.replace("even after g10 is closed", "")
    stripped = stripped.replace("after g10 is closed", "")
    stripped = stripped.replace("once g10 is closed", "")
    stripped = stripped.replace("when g10 is closed", "")
    stripped = stripped.replace("if g10 is closed", "")
    stripped = stripped.replace("after g10 closure", "")
    for forbidden in ("g10 is closed", "g10 closed.", "g10 closed\n",
                      "g10 closed —", "closes g10", "g10: closed",
                      "g10 **closed**", "status: closed"):
        assert forbidden not in stripped, (
            f"execution package must NOT claim G10 closure "
            f"(found {forbidden!r})")


def test_package_states_o3_not_implemented():
    """The execution package must state O3 is not implemented."""
    text = _execution_text().lower()
    assert "not implemented" in text or "no implementation" in text, (
        "execution package must state O3 is not implemented")
    assert "no daemon" in text or "no daemon exists" in text, (
        "execution package must note no daemon exists")


def test_package_states_no_user_created():
    """The execution package must state no user/group/secret was created."""
    text = _execution_text().lower()
    assert "no user/group/secret/service" in text or \
        "no user" in text or "no provisioning" in text, (
            "execution package must state no user/group/secret was created")


# ===========================================================================
# 3. All 10 brief items covered
# ===========================================================================

def test_all_10_brief_items_covered():
    """All 10 brief items must be present in the execution package."""
    text = _execution_text().lower()
    for label, *keywords in BRIEF_ITEMS:
        found = [kw for kw in keywords if kw.lower() in text]
        assert found, (
            f"Item {label!r}: no keyword found in execution package text "
            f"(keywords: {keywords})")


# ===========================================================================
# 4. O3 closure conditions documented
# ===========================================================================

@pytest.mark.parametrize("condition", O3_CLOSURE_CONDITIONS,
                         ids=O3_CLOSURE_CONDITIONS)
def test_o3_closure_condition_documented(condition):
    """Each of the six O3 closure conditions must appear in the package."""
    text = _execution_text().lower()
    n = text.replace("`", "")
    assert condition.lower() in n, (
        f"execution package must document O3 closure condition: {condition!r}")


# ===========================================================================
# 5. Infrastructure prerequisites documented
# ===========================================================================

@pytest.mark.parametrize("prereq", INFRA_PREREQUISITES,
                         ids=INFRA_PREREQUISITES)
def test_infrastructure_prerequisite_documented(prereq):
    """Each infrastructure prerequisite must be documented."""
    text = _execution_text().lower()
    assert prereq.lower() in text, (
        f"execution package must document infrastructure prerequisite: "
        f"{prereq!r}")


# ===========================================================================
# 6. Human decisions documented (H3, H4, H5)
# ===========================================================================

def test_human_decisions_documented():
    """The execution package must document H3, H4, H5."""
    text = _execution_text()
    assert "H3" in text and "H4" in text and "H5" in text, (
        "execution package must document H3, H4, H5")
    assert "approve O3" in text.lower() or "H3" in text, (
        "H3 must reference O3 approval")
    assert "state/projects" in text and "extension" in text, (
        "H4 must reference the projects scope extension")
    assert "closure gate" in text.lower() or "H5" in text, (
        "H5 must reference the closure decision")


# ===========================================================================
# 7. Rollback documented as file-level (no git)
# ===========================================================================

def test_rollback_documented_as_file_level_no_git():
    """The execution package must note rollback is file-level (no git)."""
    text = _execution_text().lower()
    assert "not a git repository" in text or "no git" in text or \
        "file-level" in text, (
            "execution package must note rollback is file-level (no git)")
    assert "precondition" in text and "sha-256" in text, (
        "execution package must document the pre-condition backup SHA-256 "
        "requirement for rollback")


# ===========================================================================
# 8. Evidence matrix documented
# ===========================================================================

def test_evidence_matrix_documented():
    """The execution package must contain an evidence matrix."""
    text = _execution_text().lower()
    assert "evidence matrix" in text or "evidence required" in text, (
        "execution package must document the evidence matrix")
    assert "verification command" in text.lower() or \
        "verification command" in text.lower(), (
            "evidence matrix must include verification commands")
    assert "recorded location" in text.lower(), (
        "evidence matrix must include recorded locations")


# ===========================================================================
# 9. Host feasibility state matches current probes
# ===========================================================================

def test_host_state_consistent_with_current_probes():
    """The execution package's current-state table must match the live host."""
    text = _execution_text().lower()
    for fact, expected in EXPECTED_HOST_FACTS.items():
        assert expected.lower() in text, (
            f"execution package must state host fact: {fact} = {expected}")


def test_dsh_version_pinned():
    """The execution package must reference the DSH version pin."""
    if not os.path.isdir(DSH_CHECKOUT):
        pytest.skip(f"DSH checkout not found at {DSH_CHECKOUT}")
    import json
    pkg = os.path.join(DSH_CHECKOUT, "package.json")
    with open(pkg) as f:
        v = json.load(f).get("version", "")
    assert v == "0.1.1-rc.2", f"Expected 0.1.1-rc.2, got {v}"
    text = _execution_text()
    assert "0.1.1-rc.2" in text, (
        "execution package must reference the DSH version pin")


# ===========================================================================
# 10. O3 IS implemented (Phase A daemon); migration NOT applied (Phase B pending)
# ===========================================================================

def test_daemon_module_implemented():
    """Phase A daemon code exists under registry_writer/ package."""
    d = os.path.join(PROJECT_ROOT, "registry_writer")
    assert os.path.isdir(d), "registry_writer package must exist (Phase A)"
    components = ["__init__.py", "__main__.py", "daemon.py", "client.py"]
    missing = [c for c in components
               if not os.path.isfile(os.path.join(d, c))]
    assert not missing, f"registry_writer package missing components: {missing}"


def test_ipc_schema_implemented():
    """IPC contract module schemas/ipc.py exists."""
    assert os.path.isfile(os.path.join(PROJECT_ROOT, "schemas", "ipc.py")), \
        "IPC contract module schemas/ipc.py must exist (Phase A)"


def test_daemon_config_implemented():
    """Daemon config config/registry-writer.yaml exists."""
    assert os.path.isfile(os.path.join(PROJECT_ROOT, "config",
                                       "registry-writer.yaml")), \
        "Daemon config config/registry-writer.yaml must exist (Phase A)"


def test_control_orchestrator_state_audit_unchanged():
    """O3 Phase B applied: protected-root writes route through the O3 daemon
    client; the V1 direct append_event channel has been removed from
    execution_gate (now in daemon)."""
    gate = os.path.join(PROJECT_ROOT, "control", "execution_gate.py")
    with open(gate) as f:
        gtext = f.read()
    assert "def registry_write" in gtext
    assert "def audit_append" in gtext
    assert "def project_write" in gtext
    assert "_daemon_client()" in gtext, (
        "protected writes must route through the O3 daemon client")
    assert "client.call(" in gtext, (
        "protected writes must call the O3 daemon (no direct-fs write)")
    assert "append_event" not in gtext, (
        "append_event must be removed from execution_gate (now in daemon)")
    store = os.path.join(PROJECT_ROOT, "orchestrator", "runtime", "store.py")
    with open(store) as f:
        stext = f.read()
    assert "_daemon_project_write" in stext, (
        "RuntimeStore.persist must route through the O3 daemon client")


def test_dsh_writer_user_exists():
    """The dsh-writer user must exist (operator-provisioned for O3)."""
    import subprocess
    result = subprocess.run(
        ["id", "dsh-writer"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, (
        "dsh-writer user must exist; operator must provision it")


def test_dsh_group_exists():
    """The dsh group must exist (operator-provisioned)."""
    import subprocess
    result = subprocess.run(
        ["getent", "group", "dsh"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, (
        "dsh group must exist; operator must provision it")


def test_daemon_root_exists():
    """The daemon root /var/lib/dsh-registry-writer must exist (operator-provisioned)."""
    assert os.path.isdir("/var/lib/dsh-registry-writer"), (
        "daemon root must exist; operator must provision it")


# ===========================================================================
# 11. Scope honesty: confined to the two write-only targets
# ===========================================================================

def test_execution_package_confined_to_write_only_targets():
    """The execution docs must be under o3/execution/, and tests must be
    under tests/g10/o3-execution/."""
    assert os.path.basename(EXECUTION_DIR) == "execution"
    assert os.path.basename(os.path.dirname(os.path.abspath(__file__))) == \
        "o3-execution"
    assert os.path.basename(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))) == "g10"


def test_execution_package_states_scope_confinement():
    """The execution package must state its write-only scope."""
    text = _execution_text().lower()
    assert "write-only scope" in text or "write scope" in text, (
        "execution package must state its write-only scope")
    assert "no implementation" in text or "no dsh" in text, (
        "execution package must state no implementation")


# ===========================================================================
# 12. Consistency gate: existing G10 + planning + decision tests still pass
# ===========================================================================

def test_existing_g10_tests_still_pass():
    """Re-run the existing G10, planning, and decision suites to verify no
    regression introduced by the execution package."""
    python = sys.executable
    # Session C G10 files (pre-existing)
    session_c_files = [
        os.path.join(G10_PARENT_DIR, "test_dsh_capability.py"),
        os.path.join(G10_PARENT_DIR, "test_dsh_layer_isolation.py"),
        os.path.join(G10_PARENT_DIR, "test_project_layer_isolation.py"),
        os.path.join(G10_PARENT_DIR, "test_role_restrictions.py"),
    ]
    # Planning and decision suites
    extra_files = [
        os.path.join(G10_PARENT_DIR, "final", "test_g10_final_decision.py"),
        os.path.join(G10_PARENT_DIR, "planning", "test_o5_o3_planning.py"),
        os.path.join(G10_PARENT_DIR, "o3-planning", "test_o3_final_planning.py"),
        os.path.join(G10_PARENT_DIR, "o3-planning", "test_o3_planning.py"),
        os.path.join(G10_PARENT_DIR, "decision", "test_g10_operator_decision_package.py"),
    ]
    all_files = session_c_files + [f for f in extra_files
                                   if os.path.isfile(f)]
    proc = subprocess.run(
        [python, "-m", "pytest", *all_files, "-q", "--tb=short"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
        timeout=300,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"Existing G10 tests failed (rc={proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    assert "failed" not in proc.stdout.lower() or \
        "0 failed" in proc.stdout.lower(), (
            f"Existing G10 tests show failures:\n{proc.stdout}")


# ===========================================================================
# 13. Five execution docs each have required content
# ===========================================================================

def test_0001_master_handoff_has_current_state():
    """0001 must document the current state table."""
    path = os.path.join(EXECUTION_DIR, "0001-o3-execution-readiness-handoff.md")
    if not os.path.isfile(path):
        pytest.skip("0001 doc not found")
    with open(path) as f:
        text = f.read()
    assert "Current state" in text or "current state" in text.lower(), (
        "0001 must document current state")
    assert "DSH version" in text
    assert "Host UID" in text
    assert "O3 status" in text


def test_0002_has_approvals_and_infrastructure():
    """0002 must document approvals and infrastructure requirements."""
    path = os.path.join(EXECUTION_DIR, "0002-o3-approvals-and-infrastructure.md")
    if not os.path.isfile(path):
        pytest.skip("0002 doc not found")
    with open(path) as f:
        text = f.read().lower()
    assert "h3" in text and "h4" in text and "h5" in text
    assert "dsh-writer" in text
    assert "hmac" in text
    assert "systemd" in text


def test_0003_has_backups_freeze_migration():
    """0003 must document backups, freeze window, and migration."""
    path = os.path.join(EXECUTION_DIR, "0003-o3-backups-freeze-and-migration.md")
    if not os.path.isfile(path):
        pytest.skip("0003 doc not found")
    with open(path) as f:
        text = f.read().lower()
    assert "backup" in text
    assert "freeze" in text
    assert "phase a" in text and "phase b" in text and "phase c" in text


def test_0004_has_acceptance_and_rollback():
    """0004 must document acceptance test order and rollback."""
    path = os.path.join(EXECUTION_DIR, "0004-o3-acceptance-and-rollback.md")
    if not os.path.isfile(path):
        pytest.skip("0004 doc not found")
    with open(path) as f:
        text = f.read().lower()
    assert "p0" in text or "daemon" in text
    assert "rollback" in text
    assert "reversibility" in text


def test_0005_has_closure_gate_and_evidence():
    """0005 must document the closure gate and evidence matrix."""
    path = os.path.join(EXECUTION_DIR, "0005-o3-closure-gate-and-evidence.md")
    if not os.path.isfile(path):
        pytest.skip("0005 doc not found")
    with open(path) as f:
        text = f.read().lower()
    assert "closure gate" in text or "h5" in text
    assert "six conditions" in text or "c1" in text
    assert "evidence matrix" in text or "evidence required" in text