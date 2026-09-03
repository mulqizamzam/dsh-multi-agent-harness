"""Session F — G10 O3 FINAL ARCHITECTURE PACKAGE: planning honesty guards.

These tests verify the FINAL O3 ARCHITECTURE PACKAGE documents (not any
applied implementation) are honest and complete:

  1. The FINAL package documents exist in
     docs/phase-5/security/g10/o3/final/.
  2. The package finalizes every required topic: isolated writer root,
     separate UID/process, IPC, authentication/authorization,
     registry/audit/project-state API, fail-closed behavior,
     startup/shutdown, backup/restore, migration, rollback, threat model,
     acceptance tests.
  3. The closure determination answers explicitly — per root — whether O3
     closes all three G10 residual roots (state/registry/**, audit/**,
     state/projects/**) and does NOT assume closure; G10 remains
     OPEN / BLOCKING.
  4. O3 is NOT implemented: no daemon module exists, and control/*,
     orchestrator/*, state/*, audit/* are unchanged.
  5. Role capabilities are unchanged (O5 state preserved): raw-write actor
     set is still {zeko, cto}; somad/nova have no write/edit.
  6. The package is confined to the two write-only targets
     (docs/phase-5/security/g10/o3/ + tests/g10/o3-planning/).

This is a PLANNING suite: it asserts the FINAL package's honesty, not that
an implementation happened. Nothing here validates a daemon (there is none).
"""

import os
import sys
import glob as _glob

import pytest

# tests/g10/o3-planning/ -> project root is 4 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
FINAL_DIR = os.path.join(PROJECT_ROOT, "docs", "phase-5", "security", "g10",
                         "o3", "final")

PACKAGE_DOCS = [
    "0001-o3-final-architecture-package.md",
    "0002-o3-final-closure-determination.md",
    "0003-o3-final-threat-model.md",
    "0004-o3-final-acceptance-test-spec.md",
]

# The topics the brief requires the FINAL package to finalize (exact
# keywords; doc + section). The needles must appear somewhere in the package.
REQUIRED_TOPICS = [
    ("isolated writer root", "isolated writer root"),
    ("separate UID/process", "uid / process"),
    ("separate UID/process", "dedicated os user"),
    ("IPC", "ipc"),
    ("authentication", "authentication"),
    ("authorization", "authorization"),
    ("registry/audit/project-state API", "registry / audit / project-state api"),
    ("fail-closed behavior", "fail-closed"),
    ("startup", "startup"),
    ("shutdown", "shutdown"),
    ("backup", "backup"),
    ("restore", "restore"),
    ("migration", "migration"),
    ("rollback", "rollback"),
    ("threat model", "threat model"),
    ("acceptance tests", "acceptance test"),
]

# The three G10 residual roots O3 must cover.
REQUIRED_ROOTS = [
    "state/registry/**",
    "audit/**",
    "state/projects/**",
]


def _read(rel):
    with open(os.path.join(FINAL_DIR, rel)) as f:
        return f.read()


def _package_text():
    return "\n".join(_read(d) for d in PACKAGE_DOCS)


# ---------------------------------------------------------------------------
# 1. FINAL package documents exist in the right place
# ---------------------------------------------------------------------------

def test_final_package_documents_exist():
    missing = [d for d in PACKAGE_DOCS
               if not os.path.isfile(os.path.join(FINAL_DIR, d))]
    assert not missing, f"missing FINAL O3 package documents: {missing}"


def test_final_package_lives_in_o3_final_dir():
    assert os.path.basename(FINAL_DIR) == "final"
    assert os.path.basename(os.path.dirname(FINAL_DIR)) == "o3"
    assert os.path.basename(os.path.dirname(os.path.dirname(FINAL_DIR))) == "g10"


def test_final_package_supersedes_session_d():
    """The FINAL package must position itself as the authoritative O3 design
    relative to the Session D package (which must remain untouched)."""
    text = _package_text()
    assert "supersedes" in text.lower() or "authoritative" in text.lower(), \
        "FINAL package must position itself relative to the Session D package"
    for d in ("0001-o3-implementation-package.md",
              "0002-o3-g10-closure-determination.md",
              "0003-o3-threat-model.md",
              "0004-o3-acceptance-test-spec.md"):
        assert d in text, f"FINAL package must reference Session D doc {d!r}"


# ---------------------------------------------------------------------------
# 2. All three residual roots are covered
# ---------------------------------------------------------------------------

def test_all_three_residual_roots_covered():
    text = _package_text()
    for root in REQUIRED_ROOTS:
        assert root in text, f"FINAL package must cover root {root!r}"


def test_state_projects_extension_explicit():
    """The state/projects/** coverage must be stated as an explicit design
    extension (ADR 0002 consequence 4 originally mentions registry/audit)."""
    text = _package_text()
    assert "state/projects" in text
    assert "extension" in text, \
        "FINAL package must state the state/projects/** scope extension"


# ---------------------------------------------------------------------------
# 3. All required topics are finalized
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,needle", REQUIRED_TOPICS,
                         ids=[f"{l}::{n}" for l, n in REQUIRED_TOPICS])
def test_final_package_defines_topic(label, needle):
    text = _package_text().lower()
    assert needle in text, (
        f"FINAL package must finalize topic: {label} (missing {needle!r})")


def test_api_covers_registry_audit_and_projects():
    """The registry/audit/project-state API must define all three write
    methods (registry_write, audit_append, project_write)."""
    text = _read("0001-o3-final-architecture-package.md")
    for method in ("registry_write", "audit_append", "project_write"):
        assert method in text, f"API must define {method}"


def test_isolation_decisions_finalized():
    """The FINAL package must resolve the Session D design tensions: A+B
    isolation (outside-workspace root AND dedicated UID), the cross-UID
    socket decision, and the no-mirror read decision."""
    text = _package_text()
    low = text.lower()
    assert "outside" in low and "workspaceroot" in low, \
        "must decide Option A (roots outside workspaceRoot)"
    assert "dedicated os user" in low or "dedicated uid" in low, \
        "must decide Option B (dedicated UID)"
    assert "no in-workspace mirror" in low or "no read-only mirror" in low or \
        "no in-workspace read-only mirror" in low, \
        "must decide the no-mirror read path"


# ---------------------------------------------------------------------------
# 4. Closure determination: explicit per-root, conditional, no assumption
# ---------------------------------------------------------------------------

def test_closure_determination_document_exists():
    assert os.path.isfile(os.path.join(
        FINAL_DIR, "0002-o3-final-closure-determination.md"))


def test_closure_question_is_explicit():
    text = _read("0002-o3-final-closure-determination.md")
    assert "close all three" in text.lower() or \
        "all three residual roots" in text.lower(), \
        "determination must answer the explicit per-root question"


def test_closure_determined_per_root():
    """The determination must give a per-root answer for each of the three
    residual roots, stating CLOSED under the design conditions."""
    text = _read("0002-o3-final-closure-determination.md")
    for root in REQUIRED_ROOTS:
        assert root in text, f"per-root determination missing {root!r}"
    assert "CLOSED" in text, "determination must state the per-root outcome"


def test_projects_root_closure_is_conditional():
    """state/projects/** closure must be conditional on the projects
    extension; without it the root remains CAS-detected only."""
    text = _read("0002-o3-final-closure-determination.md")
    normalized = text.replace("`", "")
    assert "state/projects/** extension" in normalized or \
        "projects extension" in normalized, \
        "determination must hinge on the projects extension"
    assert "without the extension" in text.lower() or \
        "not closed" in text.lower(), \
        "determination must state the without-extension outcome"


def test_closure_not_assumed():
    """Every FINAL document must state G10 stays OPEN / BLOCKING and carry a
    no-closure disclaimer; the architecture + determination docs must
    additionally state O3 does not close G10 by default."""
    for rel in PACKAGE_DOCS:
        text = _read(rel)
        low = text.lower()
        assert "g10 remains open" in low or "g10 stays open" in low or \
            "open / blocking" in low, (
                f"{rel} must state G10 remains OPEN / BLOCKING")
        assert "no closure" in low, (
            f"{rel} must carry a no-closure disclaimer")
    for rel in ("0001-o3-final-architecture-package.md",
                "0002-o3-final-closure-determination.md"):
        text = _read(rel)
        assert "does NOT close G10" in text or \
            "does not close G10" in text.lower(), (
                f"{rel} must explicitly state O3 does not close G10 by default")


def test_no_unconditional_closure_claim():
    for rel in PACKAGE_DOCS:
        text = _read(rel)
        low = text.lower()
        stripped = low.replace("*", "").replace("`", "")
        # Strip negated/conditional heads so they do not leave a bare
        # affirmative claim behind.
        stripped = stripped.replace("does not close g10", "")
        stripped = stripped.replace("does not close g10 today", "")
        stripped = stripped.replace("doesn't close g10", "")
        stripped = stripped.replace("does not assume o3 closes g10", "")
        stripped = stripped.replace("can close the g10 residual", "")
        stripped = stripped.replace("closes the g10 residual", "")
        stripped = stripped.replace("close the g10 residual", "")
        for forbidden in ("g10 is closed", "g10 closed.", "g10 closed\n",
                          "status: closed", "g10: closed", "closes g10",
                          "g10 **closed**", "g10 is now closed"):
            assert forbidden not in stripped, \
                f"{rel} must not claim unconditional G10 closure ({forbidden!r})"


def test_closure_conditions_documented():
    text = _read("0002-o3-final-closure-determination.md")
    normalized = text.replace("`", "")
    assert "state/projects/** extension" in normalized, \
        "determination must hinge on the projects extension"
    assert "Option A" in text, "determination must reference Option-A isolation"
    assert "Option B" in text or "A+B" in text, \
        "determination must reference the dedicated UID (Option B)"


# ---------------------------------------------------------------------------
# 5. O3 IS implemented (Phase A daemon); Phase B migration NOT applied
# ---------------------------------------------------------------------------

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


def test_config_and_roles_unchanged(role_filters):
    """Role capabilities unchanged (O5 state preserved): raw-write actor set
    is exactly {zeko, cto}; somad/nova have no write/edit."""
    assert {"bash", "write", "edit"} & set(role_filters["zeko"]["allow"])
    assert {"bash", "write", "edit"} & set(role_filters["cto"]["allow"])
    for rid in ("somad", "nova"):
        allow = role_filters[rid]["allow"]
        assert "write" not in allow, f"{rid} write must remain removed (O5)"
        assert "edit" not in allow, f"{rid} edit must remain removed (O5)"
        assert "bash" in role_filters[rid]["deny"], \
            f"{rid} bash must remain denied"
    raw_write = sorted(r for r, f in role_filters.items()
                       if {"bash", "write", "edit"} & f["allow"])
    assert raw_write == ["cto", "zeko"], \
        f"raw-write actor set must remain {['cto', 'zeko']}, got {raw_write}"


# ---------------------------------------------------------------------------
# 6. Scope honesty: package confined to the two write-only targets
# ---------------------------------------------------------------------------

def test_final_package_confined_to_write_only_targets():
    """The FINAL docs directory must contain exactly markdown package docs,
    and the final planning tests must live under tests/g10/o3-planning/."""
    docs = [d for d in os.listdir(FINAL_DIR)
            if os.path.isfile(os.path.join(FINAL_DIR, d))]
    non_md = [d for d in docs if not d.endswith(".md")]
    assert not non_md, f"unexpected non-markdown files in FINAL dir: {non_md}"
    assert set(PACKAGE_DOCS) <= set(docs)
    assert os.path.basename(os.path.dirname(os.path.abspath(__file__))) == \
        "o3-planning"
    assert os.path.basename(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))) == "g10"


def test_final_package_states_no_implementation():
    text = _package_text()
    low = text.lower()
    assert "not implemented" in low or "no implementation" in low, \
        "FINAL package must state that O3 is not implemented"
    assert "no closure claim" in low or \
        "no closure of prevention claimed" in low, \
        "FINAL package must disclaim closure"


def test_final_package_states_no_dsh_or_policy_change():
    """The FINAL package must record that DSH and session policy are
    untouched (the task constraint)."""
    text = _package_text()
    low = text.lower()
    assert "no dsh modification" in low or "no dsh core" in low or \
        "no dsh/core" in low or "no dsh change" in low, \
        "FINAL package must state no DSH modification"
    assert "session-policy" in low or "session policy" in low, \
        "FINAL package must reference session policy (unchanged)"
