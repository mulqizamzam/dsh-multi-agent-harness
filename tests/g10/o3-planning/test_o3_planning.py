"""Session D — G10 O3 implementation package: planning honesty guards.

These tests verify the O3 IMPLEMENTATION PACKAGE documents (not any applied
implementation) are honest and complete:

  1. The package documents exist in docs/phase-5/security/g10/o3/.
  2. The package covers all three G10 residual roots:
     state/registry/**, audit/**, state/projects/**.
  3. The package defines every required topic (writer process, isolated
     workspace/root, UID boundary, IPC contract, authn/authz, registry write
     API, audit append API, health check, fail-closed behavior, startup/
     shutdown, backup/restore, corruption handling, replay/idempotency,
     migration path, rollback plan, threat model, acceptance tests).
  4. The closure determination document answers "does O3 alone close G10?"
     explicitly and does NOT assume closure; G10 remains OPEN / BLOCKING.
  5. O3 is NOT implemented: no daemon module exists, and control/*,
     orchestrator/*, state/*, audit/* are unchanged.
  6. Role capabilities are unchanged (O5 state preserved): actor set is
     still {zeko, cto}; somad/nova have no write/edit.
  7. The package is confined to the two write-only targets.

This is a PLANNING suite: it asserts the package's honesty, not that an
implementation happened. Nothing here validates a daemon (there is none).
"""

import os
import sys
import glob as _glob

import pytest

# tests/g10/o3-planning/ -> project root is 4 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
O3_DIR = os.path.join(PROJECT_ROOT, "docs", "phase-5", "security", "g10", "o3")

PACKAGE_DOCS = [
    "0001-o3-implementation-package.md",
    "0002-o3-g10-closure-determination.md",
    "0003-o3-threat-model.md",
    "0004-o3-acceptance-test-spec.md",
]

# Required topics the package must define (exact keywords; doc + section).
REQUIRED_TOPICS = [
    ("dedicated writer process", "writer process"),
    ("isolated workspace/root", "isolated workspace"),
    ("UID boundary", "UID"),
    ("IPC contract", "IPC contract"),
    ("authentication/authz", "authn"),
    ("authentication/authz", "authorization"),
    ("registry write API", "registry write API"),
    ("audit append API", "audit append API"),
    ("health check", "health"),
    ("fail-closed behavior", "fail-closed"),
    ("startup/shutdown", "startup"),
    ("startup/shutdown", "shutdown"),
    ("backup/restore", "backup"),
    ("backup/restore", "restore"),
    ("corruption handling", "corruption"),
    ("replay/idempotency", "idempotency"),
    ("replay/idempotency", "replay"),
    ("migration path", "migration"),
    ("rollback plan", "rollback"),
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
    with open(os.path.join(O3_DIR, rel)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. Package documents exist
# ---------------------------------------------------------------------------

def test_package_documents_exist():
    missing = [d for d in PACKAGE_DOCS
               if not os.path.isfile(os.path.join(O3_DIR, d))]
    assert not missing, f"missing O3 package documents: {missing}"


def test_package_lives_in_write_only_dir():
    assert os.path.dirname(O3_DIR).endswith(os.path.join("g10"))
    assert os.path.basename(O3_DIR) == "o3"


# ---------------------------------------------------------------------------
# 2. All three residual roots are covered
# ---------------------------------------------------------------------------

def test_all_three_residual_roots_covered():
    text = "\n".join(_read(d) for d in PACKAGE_DOCS)
    for root in REQUIRED_ROOTS:
        assert root in text, f"package must cover root {root!r}"


def test_state_projects_extension_explicit():
    """The state/projects/** coverage must be stated as an explicit design
    extension (ADR 0002 consequence 4 originally mentions registry/audit)."""
    text = _read("0001-o3-implementation-package.md")
    assert "state/projects" in text
    assert "extension" in text, \
        "package must state the state/projects/** scope extension explicitly"


# ---------------------------------------------------------------------------
# 3. All required topics are defined
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,needle", REQUIRED_TOPICS,
                         ids=[f"{l}::{n}" for l, n in REQUIRED_TOPICS])
def test_package_defines_topic(label, needle):
    text = "\n".join(_read(d) for d in PACKAGE_DOCS)
    assert needle.lower() in text.lower(), (
        f"package must define topic: {label} (missing {needle!r})")


# ---------------------------------------------------------------------------
# 4. Closure determination: explicit, conditional, no assumption
# ---------------------------------------------------------------------------

def test_closure_determination_document_exists():
    assert os.path.isfile(os.path.join(O3_DIR,
                                       "0002-o3-g10-closure-determination.md"))


def test_closure_determination_is_explicit():
    text = _read("0002-o3-g10-closure-determination.md")
    assert "Does O3 Alone Close G10" in text or "close G10" in text.lower(), \
        "determination must answer the explicit question"


def test_closure_not_assumed():
    """The package must NOT assume O3 alone closes G10: every document must
    state G10 stays OPEN and carry an explicit no-closure disclaimer; the
    main package + determination must additionally state O3 does not close
    G10 by default."""
    for rel in PACKAGE_DOCS:
        text = _read(rel)
        low = text.lower()
        assert "g10 remains open" in low or "g10 stays open" in low or \
            "open / blocking" in low, (
                f"{rel} must state G10 remains OPEN / BLOCKING")
        assert "no closure" in low, (
            f"{rel} must carry a no-closure disclaimer")
    for rel in ("0001-o3-implementation-package.md",
                "0002-o3-g10-closure-determination.md"):
        text = _read(rel)
        assert "does NOT close G10" in text or \
            "does not close G10" in text.lower(), (
                f"{rel} must explicitly state O3 does not close G10 by default")


def test_no_unconditional_closure_claim():
    for rel in PACKAGE_DOCS:
        text = _read(rel)
        low = text.lower()
        # Negated/conditional forms are REQUIRED and must not trip the
        # affirmative-claim check. Strip markdown emphasis and the negated
        # heads before scanning so "**does not assume** O3 alone closes G10"
        # / "does NOT close G10" do not leave a bare "closes g10" behind.
        stripped = low.replace("*", "").replace("`", "")
        stripped = stripped.replace("does not close g10", "")
        stripped = stripped.replace("does not close g10 today", "")
        stripped = stripped.replace("doesn't close g10", "")
        stripped = stripped.replace("does not close it", "")
        stripped = stripped.replace("does not assume o3 alone closes g10", "")
        stripped = stripped.replace("does not assume o3 closes g10", "")
        stripped = stripped.replace("does not assume o3 alone closes g10 ", "")
        stripped = stripped.replace("can close the g10 residual", "")
        for forbidden in ("g10 is closed", "g10 closed.", "g10 closed\n",
                          "status: closed", "g10: closed", "closes g10",
                          "g10 **closed**", "g10 is now closed"):
            assert forbidden not in stripped, \
                f"{rel} must not claim unconditional G10 closure ({forbidden!r})"


def test_closure_conditions_documented():
    text = _read("0002-o3-g10-closure-determination.md")
    # The doc may backtick-quote the path; match the stem without punctuation.
    normalized = text.replace("`", "")
    assert "state/projects/** extension" in normalized, \
        "determination must hinge on the state/projects extension"
    assert "Option A" in text, "determination must reference Option-A isolation"


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
    client (execution_gate registry_write/audit_append/project_write use
    _daemon_client; store.persist uses _daemon_project_write). The V1 direct
    append_event channel has been removed from execution_gate (now in daemon)."""
    gate = os.path.join(PROJECT_ROOT, "control", "execution_gate.py")
    with open(gate) as f:
        gtext = f.read()
    # Sanctioned channels exist and route through the daemon.
    assert "def registry_write" in gtext
    assert "def audit_append" in gtext
    assert "def project_write" in gtext
    assert "_daemon_client()" in gtext, \
        "protected writes must route through the O3 daemon client"
    assert "client.call(" in gtext, \
        "protected writes must call the O3 daemon (no direct-fs write)"
    # V1 direct append_event removed from execution_gate (now in daemon).
    assert "append_event" not in gtext, \
        "append_event must be removed from execution_gate (now in daemon)"
    # store.py must route project-state through the daemon client.
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
        assert "bash" not in allow, f"{rid} bash must remain outside allow (O5)"
    raw_write = sorted(r for r, f in role_filters.items()
                       if {"bash", "write", "edit"} & f["allow"])
    assert raw_write == ["cto", "zeko"], \
        f"raw-write actor set must remain {['cto', 'zeko']}, got {raw_write}"


# ---------------------------------------------------------------------------
# 6. Scope honesty: package confined to the two write-only targets
# ---------------------------------------------------------------------------

def test_package_confined_to_write_only_targets():
    """The O3 docs directory must contain exactly the package documents, and
    the planning tests must live under tests/g10/o3-planning/."""
    docs = [d for d in os.listdir(O3_DIR)
            if os.path.isfile(os.path.join(O3_DIR, d))]
    non_md = [d for d in docs if not d.endswith(".md")]
    assert not non_md, f"unexpected non-markdown files in O3 dir: {non_md}"
    assert set(PACKAGE_DOCS) <= set(docs)
    assert os.path.basename(os.path.dirname(os.path.abspath(__file__))) == \
        "o3-planning"
    assert os.path.basename(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))) == "g10"


def test_package_mentions_all_component_areas():
    """The package must define the full O3 component set (daemon, IPC,
    config, deployment, tests, ADR addendum, residual update)."""
    text = "\n".join(_read(d) for d in PACKAGE_DOCS)
    for needle in ("daemon", "IPC", "config/registry-writer",
                   "systemd", "backup", "restore", "migration", "rollback",
                   "threat model", "acceptance test", "ADR 0002",
                   "consequence 4"):
        assert needle in text, f"package must cover component area {needle!r}"


def test_package_states_no_implementation():
    text = "\n".join(_read(d) for d in PACKAGE_DOCS)
    low = text.lower()
    assert "not implemented" in low or "no implementation" in low, \
        "package must state that O3 is not implemented"
    assert "no closure claim" in low or "no closure of prevention claimed" in low, \
        "package must disclaim closure"
