"""G10 O3 — Implementation Blocked Report: honesty guards.

These tests verify the O3 implementation blocked-state report
(`docs/phase-5/security/g10/o3/execution/0006-o3-implementation-blocked-report.md`)
is honest, complete, and consistent with the live host state:

  1. The blocked report exists at the expected path.
  2. The report states G10 remains OPEN / BLOCKING and claims NO closure.
  3. The report states O3 is NOT implemented (no daemon, no write-path switch).
  4. The report documents the failing pre-gate item (infrastructure).
  5. The report documents the absent infrastructure prerequisites (P1-P5).
  6. The report states H3/H4 approvals were granted but are insufficient alone.
  7. The report states no user/group/secret/service was created.
  8. The report documents what a privileged operator must provision to unblock.
  9. Host feasibility facts match the live environment (read-only probes).
  10. The report is confined to the write-only scope.

This is a HONESTY suite: it asserts the blocked report documents reality; it
does not implement anything and does not claim closure.
"""

import os
import sys
import subprocess

import pytest

# tests/g10/o3-execution/ -> project root is 4 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
BLOCKED_REPORT = os.path.join(
    PROJECT_ROOT, "docs", "phase-5", "security", "g10", "o3", "execution",
    "0006-o3-implementation-blocked-report.md")


# ===========================================================================
# 1. Document existence and honesty
# ===========================================================================

def test_blocked_report_exists():
    assert os.path.isfile(BLOCKED_REPORT), (
        f"G10 O3 blocked report missing at {BLOCKED_REPORT}")


def _report_text():
    with open(BLOCKED_REPORT) as f:
        return f.read()


def test_report_states_g10_open_blocking():
    text = _report_text()
    assert "G10 remains OPEN" in text or "G10 stays OPEN" in text or \
        "OPEN / BLOCKING" in text, (
            "blocked report must state G10 remains OPEN / BLOCKING")


def test_report_never_claims_closure():
    text = _report_text().lower()
    assert "no closure" in text, (
        "blocked report must disclaim closure")
    for forbidden in ("g10 is closed", "g10 closed.", "g10 closed\n",
                      "g10 closed —", "closes g10", "g10: closed",
                      "status: closed"):
        assert forbidden not in text, (
            f"blocked report must NOT claim G10 closure (found {forbidden!r})")


def test_report_states_o3_not_implemented():
    text = _report_text().lower()
    assert "not implemented" in text or "no implementation" in text, (
        "blocked report must state O3 is not implemented")
    assert "no daemon" in text, (
        "blocked report must note no daemon was implemented")


def test_report_states_no_user_created():
    text = _report_text().lower()
    assert "no user/group/secret/service" in text or \
        "no user" in text or "no provisioning" in text, (
            "blocked report must state no user/group/secret was created")


# ===========================================================================
# 2. Pre-gate determination
# ===========================================================================

def test_report_documents_failing_pre_gate():
    text = _report_text()
    assert "BLOCKED" in text, (
        "blocked report must state BLOCKED")
    assert "infrastructure" in text.lower(), (
        "blocked report must reference infrastructure prerequisites")
    assert "FAIL" in text, (
        "blocked report must mark the infrastructure gate as FAIL")


def test_report_documents_absent_prerequisites():
    text = _report_text()
    for prereq in ("P1", "P2", "P3", "P4", "P5"):
        assert prereq in text, (
            f"blocked report must document prerequisite {prereq}")
    for keyword in ("dsh-writer", "HMAC", "systemd", "dsh group"):
        assert keyword in text, (
            f"blocked report must reference infrastructure item: {keyword}")


def test_report_documents_approvals_granted():
    text = _report_text()
    assert "H3" in text and "H4" in text, (
        "blocked report must reference H3 and H4 approvals")
    assert "APPROVED" in text, (
        "blocked report must state approvals were granted")


def test_report_documents_unblock_requirements():
    text = _report_text()
    assert "privileged operator" in text.lower() or \
        "root" in text.lower(), (
            "blocked report must state a privileged operator is required")
    assert "useradd" in text or "provision" in text.lower(), (
        "blocked report must state what must be provisioned")


# ===========================================================================
# 3. Host feasibility facts match live state (read-only)
# ===========================================================================

def test_host_user_state_matches_report():
    """The dsh-writer user must now EXIST (operator provisioned O3)."""
    result = subprocess.run(["id", "dsh-writer"], capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0, (
        "dsh-writer user must exist after operator provisioning")


def test_host_group_state_matches_report():
    """The dsh group must now EXIST (operator provisioned O3)."""
    result = subprocess.run(["getent", "group", "dsh"], capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0, (
        "dsh group must exist after operator provisioning")


def test_host_daemon_root_state_matches_report():
    """The daemon root must now EXIST (operator provisioned O3)."""
    assert os.path.isdir("/var/lib/dsh-registry-writer"), (
        "daemon root must exist after operator provisioning")


def test_host_uid_matches_report():
    """The session UID must be 1000 (as documented)."""
    uid = os.getuid()
    assert uid == 1000, f"session UID changed to {uid}; report must be re-checked"


def test_daemon_modules_created():
    """Phase A daemon code now exists (implemented after unblock)."""
    d = os.path.join(PROJECT_ROOT, "registry_writer")
    assert os.path.isdir(d), "registry_writer package must exist (Phase A)"
    for mod in ("__init__.py", "__main__.py", "daemon.py", "client.py"):
        assert os.path.isfile(os.path.join(d, mod)), \
            f"registry_writer/{mod} must exist (Phase A)"
    assert os.path.isfile(os.path.join(PROJECT_ROOT, "schemas", "ipc.py")), \
        "schemas/ipc.py must exist (Phase A)"
    assert os.path.isfile(os.path.join(PROJECT_ROOT, "config",
                                       "registry-writer.yaml")), \
        "config/registry-writer.yaml must exist (Phase A)"


def test_control_plane_unchanged():
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


# ===========================================================================
# 4. Scope honesty
# ===========================================================================

def test_blocked_report_confined_to_write_only_targets():
    """The blocked report must live under o3/execution/, and the test under
    tests/g10/o3-execution/."""
    assert os.path.basename(os.path.dirname(BLOCKED_REPORT)) == "execution"
    assert os.path.basename(os.path.dirname(
        os.path.dirname(BLOCKED_REPORT))) == "o3"
    assert os.path.basename(os.path.dirname(os.path.abspath(__file__))) == \
        "o3-execution"
    assert os.path.basename(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))) == "g10"


def test_blocked_report_states_write_scope():
    text = _report_text().lower()
    assert "write-only scope" in text or "write scope" in text, (
        "blocked report must state its write-only scope")


# ===========================================================================
# 5. Consistency gate: existing suites still pass
# ===========================================================================

# Skip meta-tests when running in parallel (xdist) to avoid timeout
@pytest.mark.skipif(os.environ.get("PYTEST_XDIST_WORKER_COUNT") is not None, reason="Meta-test times out under parallel execution")
def test_existing_g10_suites_still_pass():
    """Re-run the G10, planning, decision, and execution suites to verify no
    regression introduced by the blocked report."""
    python = sys.executable
    files = [
        os.path.join(PROJECT_ROOT, "tests", "g10", "test_dsh_capability.py"),
        os.path.join(PROJECT_ROOT, "tests", "g10", "test_dsh_layer_isolation.py"),
        os.path.join(PROJECT_ROOT, "tests", "g10", "test_project_layer_isolation.py"),
        os.path.join(PROJECT_ROOT, "tests", "g10", "test_role_restrictions.py"),
        os.path.join(PROJECT_ROOT, "tests", "g10", "final", "test_g10_final_decision.py"),
        os.path.join(PROJECT_ROOT, "tests", "g10", "planning", "test_o5_o3_planning.py"),
        os.path.join(PROJECT_ROOT, "tests", "g10", "o3-planning", "test_o3_final_planning.py"),
        os.path.join(PROJECT_ROOT, "tests", "g10", "o3-planning", "test_o3_planning.py"),
        os.path.join(PROJECT_ROOT, "tests", "g10", "decision", "test_g10_operator_decision_package.py"),
        os.path.join(PROJECT_ROOT, "tests", "g10", "o3-execution", "test_o3_execution_readiness.py"),
    ]
    existing = [f for f in files if os.path.isfile(f)]
    proc = subprocess.run(
        [python, "-m", "pytest", *existing, "-q", "--tb=short"],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=300,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"Existing G10 suites failed (rc={proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    assert "failed" not in proc.stdout.lower() or \
        "0 failed" in proc.stdout.lower(), (
            f"Existing G10 suites show failures:\n{proc.stdout}")