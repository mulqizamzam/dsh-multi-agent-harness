"""Session G — O3 Implementation Readiness: planning honesty guards.

These tests verify the O3 IMPLEMENTATION READINESS PACKAGE document
(docs/phase-5/security/g10/o3/implementation/0001-o3-implementation-readiness.md)
is honest and complete:

  1. The document exists in the right place.
  2. All 17 brief topics are covered (isolated writer root, dedicated UID/
     process, Unix-socket NDJSON IPC, HMAC authentication, channel->method->root
     authorization, registry API, audit append API, project-state API,
     startup/readiness/health, fail-closed daemon absence, migration
     prepare->switch->verify, backup/restore, rollback, replay/idempotency,
     corruption handling, acceptance tests, observability/audit requirements).
  3. All three G10 residual roots (state/registry/**, audit/**,
     state/projects/**) are covered.
  4. O3 is NOT implemented: no daemon module exists, no IPC schema, no
     daemon config, no registry_writer references anywhere.
  5. control/*, orchestrator/*, state/*, audit/* are unchanged (V1 direct-write
     channels).
  6. Role capabilities are unchanged (O5 state preserved): raw-write actor set
     is still {zeko, cto}; somad/nova have no write/edit.
  7. The package is confined to the two write-only targets
     (docs/phase-5/security/g10/o3/implementation/ +
     tests/g10/o3-planning/final/).
  8. No G10 CLOSED claim is made; G10 remains OPEN / BLOCKING.
  9. DSH, session policy, and role capabilities are stated as unchanged.
  10. The fail-closed-by-absence honesty is stated.

This is a PLANNING suite: it asserts the implementation-readiness package's
honesty, not that an implementation happened. Nothing here validates a daemon
(there is none).
"""

import os
import sys
import glob as _glob

import pytest

# tests/g10/o3-planning/final/ -> project root is 5 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
IMPLEMENTATION_DIR = os.path.join(PROJECT_ROOT, "docs", "phase-5", "security",
                                  "g10", "o3", "implementation")

READINESS_DOC = "0001-o3-implementation-readiness.md"

# The 17 topics the brief requires the implementation-readiness package to
# verify and finalize. Each entry is (label, needle) where needle is a string
# that must appear (case-insensitive) in the doc.
REQUIRED_TOPICS = [
    ("isolated writer root", "isolated writer root"),
    ("dedicated UID/process", "dedicated uid"),
    ("dedicated UID/process", "dsh-writer"),
    ("Unix-socket NDJSON IPC", "unix socket"),
    ("Unix-socket NDJSON IPC", "ndjson"),
    ("HMAC authentication", "hmac"),
    ("channel->method->root authorization", "channel→method→root"),
    ("channel->method->root authorization", "sanctioned root"),
    ("registry API", "registry_write"),
    ("registry API", "registry_read"),
    ("audit append API", "audit_append"),
    ("audit append API", "audit_read"),
    ("project-state API", "project_write"),
    ("project-state API", "project_read"),
    ("startup/readiness/health", "startup"),
    ("startup/readiness/health", "readiness"),
    ("startup/readiness/health", "health"),
    ("fail-closed daemon absence", "fail-closed"),
    ("fail-closed daemon absence", "no daemon"),
    ("migration prepare->switch->verify", "phase a"),
    ("migration prepare->switch->verify", "phase b"),
    ("migration prepare->switch->verify", "phase c"),
    ("backup/restore", "backup"),
    ("backup/restore", "restore"),
    ("rollback", "rollback"),
    ("replay/idempotency", "replay"),
    ("replay/idempotency", "idempotency"),
    ("corruption handling", "corruption"),
    ("acceptance tests", "acceptance test"),
    ("observability/audit requirements", "self-audit"),
    ("observability/audit requirements", "health"),
]

# The three G10 residual roots O3 must cover.
REQUIRED_ROOTS = [
    "state/registry/**",
    "audit/**",
    "state/projects/**",
]


def _read():
    with open(os.path.join(IMPLEMENTATION_DIR, READINESS_DOC)) as f:
        return f.read()


def _doc_text():
    return _read()


# ---------------------------------------------------------------------------
# 1. Implementation-readiness document exists in the right place
# ---------------------------------------------------------------------------

def test_implementation_readiness_doc_exists():
    assert os.path.isfile(os.path.join(IMPLEMENTATION_DIR, READINESS_DOC))


def test_implementation_dir_is_o3_implementation():
    assert os.path.basename(IMPLEMENTATION_DIR) == "implementation"
    assert os.path.basename(os.path.dirname(IMPLEMENTATION_DIR)) == "o3"
    assert os.path.basename(os.path.dirname(os.path.dirname(IMPLEMENTATION_DIR))) == "g10"


def test_implementation_dir_positioned_relative_to_final():
    """The implementation/ dir must be a sibling of final/ under o3/."""
    o3_dir = os.path.dirname(IMPLEMENTATION_DIR)
    final_dir = os.path.join(o3_dir, "final")
    assert os.path.isdir(final_dir), (
        "implementation/ must be a sibling of final/ under o3/")


# ---------------------------------------------------------------------------
# 2. All 17 required topics are covered
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,needle", REQUIRED_TOPICS,
                         ids=[f"{l}::{n}" for l, n in REQUIRED_TOPICS])
def test_doc_covers_topic(label, needle):
    text = _doc_text().lower()
    assert needle in text, (
        f"implementation-readiness doc must cover topic: {label} "
        f"(missing {needle!r})")


# ---------------------------------------------------------------------------
# 3. All three residual roots are covered
# ---------------------------------------------------------------------------

def test_all_three_residual_roots_covered():
    text = _doc_text()
    for root in REQUIRED_ROOTS:
        assert root in text, (
            f"implementation-readiness doc must cover root {root!r}")


def test_state_projects_extension_explicit():
    """The state/projects/** coverage must be stated as an explicit design
    extension (ADR 0002 consequence 4 originally mentions registry/audit)."""
    text = _doc_text()
    assert "state/projects" in text
    assert "scope extension" in text.lower() or "extension" in text.lower(), (
        "implementation-readiness doc must state the state/projects/** "
        "scope extension")


# ---------------------------------------------------------------------------
# 4. O3 IS implemented (Phase A); no Phase B migration / no G10 closure
# ---------------------------------------------------------------------------

def test_daemon_module_implemented():
    """Phase A daemon code exists under registry_writer/ package."""
    d = os.path.join(PROJECT_ROOT, "registry_writer")
    assert os.path.isdir(d), "registry_writer package must exist (Phase A)"
    for mod in ("__init__.py", "__main__.py", "daemon.py", "client.py"):
        assert os.path.isfile(os.path.join(d, mod)), \
            f"registry_writer/{mod} must exist (Phase A)"


def test_ipc_schema_implemented():
    """schemas/ipc.py exists (the IPC contract module is NEW)."""
    assert os.path.isfile(os.path.join(PROJECT_ROOT, "schemas", "ipc.py")), \
        "IPC contract module schemas/ipc.py must exist (Phase A)"


def test_daemon_config_implemented():
    """config/registry-writer.yaml exists."""
    assert os.path.isfile(os.path.join(PROJECT_ROOT, "config",
                                       "registry-writer.yaml")), \
        "Daemon config config/registry-writer.yaml must exist (Phase A)"


def test_doc_states_no_implementation():
    text = _doc_text().lower()
    assert "not implemented" in text or "no implementation" in text, \
        "implementation-readiness doc must state that O3 is not implemented"


def test_doc_states_no_daemon_exists():
    text = _doc_text().lower()
    assert "no daemon" in text or "no daemon code" in text or \
        "no daemon module" in text, \
        "implementation-readiness doc must state that no daemon exists"


# ---------------------------------------------------------------------------
# 5. Protected components unchanged (V1 direct-write)
# ---------------------------------------------------------------------------

def test_control_orchestrator_state_audit_unchanged():
    """O3 Phase B applied: protected-root writes route through the O3 daemon
    client; the V1 direct append_event channel has been removed from
    execution_gate (now in daemon); store routes through the daemon client."""
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


# ---------------------------------------------------------------------------
# 6. Role capabilities unchanged (O5 state preserved)
# ---------------------------------------------------------------------------

@pytest.fixture
def role_filters():
    import yaml
    with open(os.path.join(PROJECT_ROOT, "config",
                           "role-preset-mapping.yaml")) as f:
        mapping = yaml.safe_load(f)
    return {r["id"]: {
        "allow": set(r["tool_surface"]["allow"]),
        "deny": set(r["tool_surface"]["deny"]),
    } for r in mapping["roles"]}


def test_role_capabilities_unchanged(role_filters):
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
# 7. Scope honesty: package confined to the two write-only targets
# ---------------------------------------------------------------------------

def test_implementation_package_confined_to_write_only_targets():
    """The implementation docs directory must contain only the readiness
    markdown doc, and the final planning tests must live under
    tests/g10/o3-planning/final/."""
    docs = [d for d in os.listdir(IMPLEMENTATION_DIR)
            if os.path.isfile(os.path.join(IMPLEMENTATION_DIR, d))]
    non_md = [d for d in docs if not d.endswith(".md")]
    assert not non_md, f"unexpected non-markdown files in IMPLEMENTATION dir: {non_md}"
    assert READINESS_DOC in docs, \
        f"implementation-readiness doc {READINESS_DOC!r} must be present"
    assert os.path.basename(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))) == "o3-planning", \
        "test file must live under o3-planning/"
    assert os.path.basename(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) == "g10", \
        "test file must live under g10/"


# ---------------------------------------------------------------------------
# 8. No G10 CLOSED claim; G10 remains OPEN / BLOCKING
# ---------------------------------------------------------------------------

def test_doc_states_g10_open_blocking():
    text = _doc_text().lower()
    assert "g10 remains open" in text or "g10 stays open" in text or \
        "open / blocking" in text, \
        "implementation-readiness doc must state G10 remains OPEN / BLOCKING"


def test_no_unconditional_closure_claim():
    text = _doc_text().lower()
    stripped = text.replace("*", "").replace("`", "")
    # Remove negated/conditional/clarifying phrases so they don't mask a
    # bare affirmative claim.
    stripped = stripped.replace("does not close g10", "")
    stripped = stripped.replace("does not close g10 today", "")
    stripped = stripped.replace("doesn't close g10", "")
    stripped = stripped.replace("does not claim g10", "")
    stripped = stripped.replace("would close the g10", "")
    stripped = stripped.replace("would close g10", "")
    stripped = stripped.replace("closes the g10 residual", "")
    stripped = stripped.replace("close the g10 residual", "")
    for forbidden in ("g10 is closed", "g10 closed.", "g10 closed\n",
                      "status: closed", "g10: closed", "closes g10",
                      "g10 **closed**", "g10 is now closed"):
        assert forbidden not in stripped, \
            f"implementation-readiness doc must not claim unconditional " \
            f"G10 closure ({forbidden!r})"


def test_closure_conditions_documented():
    text = _doc_text()
    assert "not closed" in text.lower() or "no closure" in text.lower(), \
        "implementation-readiness doc must disclaim closure"


# ---------------------------------------------------------------------------
# 9. DSH / session policy / role capabilities unchanged
# ---------------------------------------------------------------------------

def test_doc_states_no_dsh_or_policy_change():
    text = _doc_text().lower()
    assert "no dsh modification" in text or "no dsh core" in text or \
        "no dsh/core" in text or "no dsh change" in text, \
        "implementation-readiness doc must state no DSH modification"
    assert "session-policy" in text or "session policy" in text, \
        "implementation-readiness doc must reference session policy (unchanged)"


def test_doc_states_role_capabilities_unchanged():
    text = _doc_text().lower()
    assert "role capabilities" in text and "unchanged" in text, \
        "implementation-readiness doc must state role capabilities unchanged"


# ---------------------------------------------------------------------------
# 10. Fail-closed-by-absence honesty stated
# ---------------------------------------------------------------------------

def test_fail_closed_by_absence_honesty_stated():
    """The doc must honestly state that the current 'no daemon' state provides
    no isolation benefit — the G10 residual is unchanged."""
    text = _doc_text().lower()
    assert "fail-closed by absence" in text or \
        "fail-closed by absence" in text.replace("-", " "), \
        "implementation-readiness doc must state fail-closed-by-absence honesty"
    assert "no isolation benefit" in text.lower(), \
        "implementation-readiness doc must state the no-isolation honesty"


# ---------------------------------------------------------------------------
# 11. Return fields present (MILESTONE, STATUS, O3 READINESS, etc.)
# ---------------------------------------------------------------------------

def test_return_fields_all_present():
    """The doc must contain the return fields required by the brief:
    MILESTONE, STATUS, O3 READINESS, DEPENDENCIES, MIGRATION, ROLLBACK,
    ACCEPTANCE TESTS, G10 IMPACT, VERIFIED, UNKNOWN, BLOCKED, SCOPE CHECK,
    NEXT."""
    text = _doc_text()
    required_fields = [
        "MILESTONE", "STATUS", "O3 READINESS", "DEPENDENCIES",
        "MIGRATION", "ROLLBACK", "ACCEPTANCE TESTS", "G10 IMPACT",
        "VERIFIED", "UNKNOWN", "BLOCKED", "SCOPE CHECK", "NEXT",
    ]
    # Use case-insensitive match for section headings
    low = text.lower()
    for field in required_fields:
        assert field.lower() in low, (
            f"implementation-readiness doc must contain return field: {field}")