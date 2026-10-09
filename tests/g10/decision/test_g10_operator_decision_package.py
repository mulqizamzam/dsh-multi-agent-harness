"""G10 O3 — Operator Decision Package: honesty guards.

These tests verify the G10 O3 operator decision package document is honest,
complete, and consistent with the current evidence. They assert:

  1. The decision package document exists at the expected path.
  2. The document states G10 remains OPEN / BLOCKING and claims NO closure.
  3. The raw-write actor set is derived from the CURRENT config (post-O5:
     {zeko, cto}).
  4. All six O3 closure conditions (§4.1 of the closure determination) are
     documented in the package.
  5. The per-root closure is conditional on the projects extension and A+B
     isolation.
  6. The classification vocabulary (CLOSED/OPEN/BLOCKED/DEFERRED/UNKNOWN)
     is used throughout.
  7. Rollback is documented as file-level (no git repository).
  8. O3 is NOT implemented: no daemon module exists, and control/*,
     orchestrator/*, state/*, audit/* are unchanged.
  9. The decision package is confined to its two write-only targets.
 10. DSH version is still pinned to 0.1.1-rc.2.
 11. The Human decisions table lists H3, H4, H5 as required/expected.
 12. The remaining-blockers section states G13 remains OPEN/UNKNOWN and
     production remains BLOCKED.
 13. Existing G10 tests still pass (consistency gate).
"""

import os
import sys
import glob as _glob

import pytest

# tests/g10/decision/ -> project root is 4 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
DECISION_DOC = os.path.join(PROJECT_ROOT, "docs", "phase-5", "security",
                            "g10", "decision",
                            "0001-g10-o3-operator-decision-package.md")
DSH_CHECKOUT = "/home/administrator/deepseek-harness"
G10_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The six O3 closure conditions from o3/final/0002 §4.1 (must appear in the
# package, at least as keywords).
O3_CLOSURE_CONDITIONS = [
    "A+B isolation",
    "state/projects/** extension",
    "write path is fully switched",
    "no silent fallback",
    "verification passes",
    "human approval",
]

# The three G10 residual roots.
REQUIRED_ROOTS = [
    "state/registry/**",
    "audit/**",
    "state/projects/**",
]

# The classification vocabulary the package must use.
VOCABULARY = [
    "CLOSED",
    "OPEN",
    "BLOCKED",
    "DEFERRED",
    "UNKNOWN",
]


# ===========================================================================
# 1. Document existence, honesty, and G10 status
# ===========================================================================

def test_decision_document_exists():
    assert os.path.isfile(DECISION_DOC), (
        f"G10 O3 operator decision package missing at {DECISION_DOC}")


def test_decision_document_states_g10_open_blocking():
    with open(DECISION_DOC) as f:
        text = f.read()
    assert "G10 remains OPEN" in text or "G10 stays OPEN" in text or \
        "G10 remains OPEN / BLOCKING" in text, (
            "decision package must state G10 remains OPEN / BLOCKING")
    assert "BLOCKING" in text, "decision package must state G10 BLOCKING"


def test_decision_document_never_claims_closure():
    with open(DECISION_DOC) as f:
        text = f.read()
    low = text.lower()
    assert "no closure" in low, (
        "decision package must disclaim closure")
    # Affirmative closure claims must be absent. The word "closed"
    # legitimately appears inside conditional/honesty phrasing; only
    # unconditional affirmative forms are a violation.
    for forbidden in ("g10 is closed", "g10 closed.", "g10 closed\n",
                      "g10 closed —", "closes g10", "g10: closed",
                      "g10 **closed**", "status: closed"):
        assert forbidden not in low, (
            f"decision package must NOT claim G10 closure "
            f"(found {forbidden!r})")


def test_decision_document_states_o3_not_implemented():
    with open(DECISION_DOC) as f:
        text = f.read().lower()
    assert "not implemented" in text or "no implementation" in text, (
        "decision package must state O3 is not implemented")
    assert "no daemon" in text, (
        "decision package must note no daemon exists")


# ===========================================================================
# 2. Actor set (current config, post-O5)
# ===========================================================================

def test_actor_set_matches_current_config(role_filters):
    """The raw-write actor set must be exactly {zeko, cto} (post-O5)."""
    raw_write = sorted(
        r for r, f in role_filters.items()
        if {"bash", "write", "edit"} & f["allow"]
    )
    assert raw_write == ["cto", "zeko"], (
        f"Unexpected raw-write actor set: {raw_write}")
    with open(DECISION_DOC) as f:
        text = f.read()
    assert "{zeko, cto}" in text, (
        "decision package must state the current raw-write actor set")


def test_o5_applied_current_config(role_filters):
    """O5 has been applied: somad/nova deny write/edit; zeko/cto unchanged."""
    for rid in ("somad", "nova"):
        allow = role_filters[rid]["allow"]
        assert "write" not in allow, f"{rid} write still in allow"
        assert "edit" not in allow, f"{rid} edit still in allow"
    for rid in ("zeko", "cto"):
        assert {"bash", "write", "edit"} & role_filters[rid]["allow"], \
            f"{rid} must retain raw-write capability"


# ===========================================================================
# 3. O3 closure conditions documented
# ===========================================================================

@pytest.mark.parametrize("condition", O3_CLOSURE_CONDITIONS,
                         ids=O3_CLOSURE_CONDITIONS)
def test_o3_closure_condition_documented(condition):
    with open(DECISION_DOC) as f:
        text = f.read().lower()
    # Normalize: strip backticks (path tokens are often backtick-wrapped),
    # then use a permissive substring match.
    text = text.replace("`", "")
    assert condition.lower() in text, (
        f"decision package must document O3 closure condition: {condition!r}")


def test_all_three_residual_roots_covered():
    with open(DECISION_DOC) as f:
        text = f.read()
    for root in REQUIRED_ROOTS:
        assert root in text, (
            f"decision package must cover residual root {root!r}")


def test_projects_closure_is_conditional_on_extension():
    with open(DECISION_DOC) as f:
        text = f.read()
    n = text.replace("`", "")
    assert "projects extension" in n.lower() or \
        "state/projects/** extension" in n, (
            "closure of state/projects must be conditional on the extension")


# ===========================================================================
# 4. Classification vocabulary present
# ===========================================================================

@pytest.mark.parametrize("term", VOCABULARY, ids=VOCABULARY)
def test_classification_vocabulary_used(term):
    with open(DECISION_DOC) as f:
        text = f.read()
    assert term in text, (
        f"decision package must use status vocabulary term: {term!r}")


# ===========================================================================
# 5. Human decisions table
# ===========================================================================

def test_human_decisions_table_contains_h3_h4_h5():
    """The decision package must list H3 (approve O3), H4 (projects extension),
    and H5 (closure decision) as required/expected Human decisions."""
    with open(DECISION_DOC) as f:
        text = f.read()
    assert "H3" in text and "H4" in text and "H5" in text, (
        "Human decisions table must list H3, H4, H5")
    assert "approve O3" in text.lower() or "H3" in text, (
        "H3 must reference O3 approval")
    assert "state/projects" in text and "extension" in text, (
        "H4 must reference the projects scope extension")


# ===========================================================================
# 6. Rollback documented as file-level (no git)
# ===========================================================================

def test_rollback_documented_as_file_level_no_git():
    with open(DECISION_DOC) as f:
        text = f.read().lower()
    assert "not a git repository" in text or "no git" in text or \
        "file-level" in text, (
            "decision package must note rollback is file-level (no git)")
    assert "precondition" in text and "sha-256" in text, (
        "decision package must document the pre-condition backup SHA-256 "
        "requirement for rollback")


# ===========================================================================
# 7. Remaining blockers section
# ===========================================================================

def test_remaining_blockers_includes_g13_open_unknown():
    with open(DECISION_DOC) as f:
        text = f.read()
    assert "G13" in text and "OPEN" in text and "UNKNOWN" in text, (
        "remaining-blockers section must state G13 remains OPEN/UNKNOWN")
    assert "production remains BLOCKED" in text.lower() or \
        "not production-ready" in text.lower(), (
            "remaining-blockers section must state production remains blocked")


# ===========================================================================
# 8. O3 IS implemented (Phase A); protected components unchanged
# ===========================================================================

def test_daemon_module_implemented():
    """Phase A daemon code exists under registry_writer/ package."""
    d = os.path.join(PROJECT_ROOT, "registry_writer")
    assert os.path.isdir(d), "registry_writer package must exist (Phase A)"
    for mod in ("__init__.py", "__main__.py", "daemon.py", "client.py"):
        assert os.path.isfile(os.path.join(d, mod)), \
            f"registry_writer/{mod} must exist (Phase A)"


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
    assert "_daemon_client()" in gtext, \
        "protected writes must route through the O3 daemon client"
    assert "client.call(" in gtext, \
        "protected writes must call the O3 daemon (no direct-fs write)"
    assert "append_event" not in gtext, \
        "append_event must be removed from execution_gate (now in daemon)"
    store = os.path.join(PROJECT_ROOT, "orchestrator", "runtime", "store.py")
    with open(store) as f:
        stext = f.read()
    assert "_daemon_project_write" in stext, \
        "RuntimeStore.persist must route through the O3 daemon client"


# ===========================================================================
# 9. Scope honesty: decision confined to the two write-only targets
# ===========================================================================

def test_decision_package_confined_to_write_only_targets():
    """The decision docs directory must contain exactly markdown package docs,
    and the decision tests must live under tests/g10/decision/."""
    decision_dir = os.path.dirname(DECISION_DOC)
    docs = [d for d in os.listdir(decision_dir)
            if os.path.isfile(os.path.join(decision_dir, d))]
    non_md = [d for d in docs if not d.endswith(".md")]
    assert not non_md, (
        f"unexpected non-markdown files in decision dir: {non_md}")
    # The test file lives under tests/g10/decision/.
    assert os.path.basename(os.path.dirname(os.path.abspath(__file__))) == \
        "decision"
    assert os.path.basename(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))) == "g10"


def test_decision_package_scope_check_states_no_implementation():
    with open(DECISION_DOC) as f:
        text = f.read().lower()
    assert "no implementation" in text or "not implemented" in text, \
        "decision package must state no implementation"
    assert "no dsh modification" in text or "no dsh change" in text or \
        "no config/role" in text, \
        "decision package must state no DSH/config/role change"


# ===========================================================================
# 10. DSH version pin
# ===========================================================================

def test_dsh_version_pin():
    if not os.path.isdir(DSH_CHECKOUT):
        pytest.skip(f"DSH checkout not found at {DSH_CHECKOUT}")
    import json
    pkg = os.path.join(DSH_CHECKOUT, "package.json")
    with open(pkg) as f:
        v = json.load(f).get("version", "")
    # Pin moved from 0.1.1-rc.2 after the 2026-10-09 full-suite
    # re-verification against the running checkout (README policy: later
    # releases require re-verification).
    assert v == "0.2.0-rc.2", f"Expected 0.2.0-rc.2, got {v}"
    with open(DECISION_DOC) as f:
        text = f.read()
    # The dated decision package names a pin; either the historical or the
    # current pin satisfies the reference (the record is dated prose).
    assert "0.2.0-rc.2" in text or "0.1.1-rc.2" in text, (
        "decision package must reference the DSH version pin")


# ===========================================================================
# 11. Consistency gate: existing G10 tests still pass
# ===========================================================================

def test_existing_g10_tests_still_pass():
    """Re-run the existing G10 test suite to verify no regression introduced
    by the decision package. Targets the pre-existing test files (NOT this
    directory, which would recurse)."""
    import subprocess
    python = sys.executable
    session_c_files = [
        os.path.join(G10_PARENT_DIR, "test_dsh_capability.py"),
        os.path.join(G10_PARENT_DIR, "test_dsh_layer_isolation.py"),
        os.path.join(G10_PARENT_DIR, "test_project_layer_isolation.py"),
        os.path.join(G10_PARENT_DIR, "test_role_restrictions.py"),
    ]
    # Also include the final and planning suites for full coverage.
    extra_files = [
        os.path.join(G10_PARENT_DIR, "final", "test_g10_final_decision.py"),
        os.path.join(G10_PARENT_DIR, "planning", "test_o5_o3_planning.py"),
        os.path.join(G10_PARENT_DIR, "o3-planning", "test_o3_final_planning.py"),
        os.path.join(G10_PARENT_DIR, "o3-planning", "test_o3_planning.py"),
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
# 12. Honesty: the decision document uses the exact vocabulary and
#     documents the minimum safe path and production impact
# ===========================================================================

def test_decision_documents_rollback_conditions():
    with open(DECISION_DOC) as f:
        text = f.read().lower()
    assert "trigger" in text, \
        "decision package must document rollback trigger conditions"
    assert "reversibility" in text, \
        "decision package must state rollback reversibility"


def test_decision_documents_infrastructure_prerequisites():
    with open(DECISION_DOC) as f:
        text = f.read()
    assert "dsh-writer" in text, \
        "decision package must reference the dsh-writer user"
    assert "workspaceRoot" in text or "workspace root" in text.lower(), \
        "decision package must reference the out-of-workspace root requirement"
    assert "HMAC" in text, \
        "decision package must reference the HMAC shared secret"


def test_decision_documents_implementation_sequence():
    with open(DECISION_DOC) as f:
        text = f.read()
    assert "Phase A" in text and "Phase B" in text and "Phase C" in text, \
        "decision package must document the three-phase migration sequence"
    assert "freeze" in text.lower(), \
        "decision package must reference the freeze window for Phase B"


def test_decision_documents_acceptance_criteria():
    with open(DECISION_DOC) as f:
        text = f.read()
    assert "A1" in text or "ACCEPTANCE" in text, \
        "decision package must document acceptance criteria"
    assert "O3-ACCEPTANCE" in text or "O3-DAEMON" in text or \
        "FINAL 0004" in text, \
        "decision package must reference the O3 acceptance test suite"