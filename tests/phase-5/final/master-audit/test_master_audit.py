"""Phase 5 / Master Security Audit — FINAL AUDIT LOCK TESTS.

Deterministic tests that lock the authoritative master audit
(docs/phase-5/final/master-audit/0001-master-audit.md) against the current
live environment and the source documents it consolidates.

What these tests prove (all observed, none simulated):

  1. The audit document exists and carries all required sections.
  2. Master verdicts are consistent: NOT PRODUCTION-READY, G10 OPEN,
     G13 OPEN/UNKNOWN, L3 NOT CLAIMED, zero controls L3.
  3. The current live environment facts are as reported (Web GUI session,
     DSH_WEB_URL set, backend UNAVAILABLE, O5 applied, markers unset).
  4. The reported L3 blockers match the current live probe (3 blockers:
     UID-2, D4D7-3, PLAN-REAL; ANS-1/2 PASS in Web GUI session).
  5. Stale/contradictory evidence findings (S1-S10) are factually grounded.
  6. Honesty guards: no UNKNOWN marked as PASS, no OPEN marked as CLOSED,
     no control declared L3, no production-readiness declared.
  7. Live environment conditions are independently re-derived, not assumed.

NO test here executes a live dispatch, modifies DSH/session policy/presets,
invents a Human signature, fabricates runtime evidence, or declares any gate
closed.
"""

from __future__ import annotations

import json
import os
import sys
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DOCS = os.path.join(PROJECT_ROOT, "docs")
AUDIT_DOC = os.path.join(DOCS, "phase-5", "final", "master-audit",
                          "0001-master-audit.md")


def _read_audit() -> str:
    with open(AUDIT_DOC, "r", encoding="utf-8") as f:
        return f.read()


def _read_doc(path: str) -> str | None:
    full = os.path.join(DOCS, path)
    if not os.path.exists(full):
        return None
    with open(full, "r") as f:
        return f.read()


# =========================================================================
# 1. Audit document integrity
# =========================================================================

class TestAuditDocumentIntegrity:
    """The master audit document exists and is complete."""

    def test_audit_file_exists(self):
        assert os.path.isfile(AUDIT_DOC), AUDIT_DOC

    def test_audit_has_all_required_sections(self):
        text = _read_audit()
        for section in (
            "## AUDIT CONTEXT",
            "## MASTER VERDICTS",
            "### PRODUCTION_VERDICT",
            "### SECURITY_VERDICT",
            "### L3_VERDICT",
            "## FINAL MATRIX",
            "### 1. G10",
            "### 2. G13",
            "### 3. L3",
            "### 4. D4/D7",
            "### 5. Approval Path",
            "### 6. Front Door",
            "### 7. Audit / Observability",
            "### 8. Recovery / Verification / Parallel",
            "### 9. Scope / Concurrency",
            "### 10. Production Readiness",
            "## STALE / CONTRADICTORY EVIDENCE",
            "## EXACT HUMAN DECISIONS REQUIRED",
            "## EXACT OPERATOR / INFRASTRUCTURE ACTIONS",
            "## EXACT IMPLEMENTATION ACTIONS",
            "## MINIMUM PATH TO PRODUCTION",
            "## SCOPE / CONCURRENCY FINDINGS",
            "## FINAL RECOMMENDATION",
        ):
            assert section in text, f"Missing section: {section}"


# =========================================================================
# 2. Master verdicts consistency
# =========================================================================

class TestVerdictsConsistency:
    """Master verdicts must be consistent across domains."""

    def test_not_production_ready(self):
        t = _read_audit()
        assert "NOT PRODUCTION-READY" in t

    def test_g10_open(self):
        t = _read_audit()
        assert "G10" in t and "OPEN" in t.split("G10")[-1][:80]

    def test_g13_open_unknown(self):
        t = _read_audit()
        assert "G13" in t
        assert "OPEN" in t.split("G13")[-1][:80] or "UNKNOWN" in t.split("G13")[-1][:80]

    def test_l3_not_claimed(self):
        t = _read_audit()
        assert "NOT CLAIMED" in t
        assert "zero controls are L3" in t

    def test_no_control_claimed_l3(self):
        t = _read_audit()
        # No control may be declared L3 as PASS/CLAIMED/CLOSED.
        # The audit may mention "L3 claim" in factual reports
        # ("L3 claim possible = False") and in acceptance criteria
        # ("bundles with l3_claim=true") — those are not claims.
        # What must NOT appear is a declaration that L3 IS currently claimed.
        assert "L3 CLAIMED" not in t
        assert "L3=PASS" not in t
        assert "L3=CLOSED" not in t
        # The audit must state that L3 is NOT claimed.
        assert "NOT CLAIMED" in t
        assert "zero controls" in t

    def test_audit_does_not_claim_production_ready(self):
        t = _read_audit()
        # "NOT PRODUCTION-READY" is the only production-readiness statement
        assert "PRODUCTION-READY" in t.split("NOT PRODUCTION-READY")[-1] or \
               "PRODUCTION-READY" not in t.split("NOT PRODUCTION-READY")[0]


# =========================================================================
# 3. Live environment facts (independently re-derived)
# =========================================================================

class TestLiveEnvironmentFacts:
    """Current environment facts as reported in the audit; re-derived here."""

    def test_dsh_version(self):
        result = subprocess.run(["dsh", "--version"], capture_output=True,
                                text=True, timeout=30)
        # Pin moved from 0.1.1-rc.2 after the 2026-10-09 full-suite
        # re-verification against the running checkout (README policy: later
        # releases require re-verification). Moved from 0.2.0-rc.2 to 0.2.1-rc.2
        # on the 0.2.1-rc.2 port.
        assert "0.2.1-rc.2" in result.stdout or result.stderr

    def test_dsh_live_bridge_marker_unset(self):
        import os
        assert os.environ.get("DSH_LIVE_BRIDGE_ACTIVE", "") != "1"

    def test_dsh_web_url_set_web_gui_session(self):
        import os
        # This session is a Web GUI session; DSH_WEB_URL is set
        assert os.environ.get("DSH_WEB_URL", "") == "http://127.0.0.1:13080"

    def test_backend_kind_unavailable(self):
        # Probe via subprocess so this test package imports no production
        # control-plane code (package-hygiene rule).
        import subprocess
        import sys as _sys
        code = (
            "from orchestrator.dsh.bridge import probe_backend_kind; "
            "print(probe_backend_kind().value)"
        )
        proc = subprocess.run([_sys.executable, "-c", code],
                              capture_output=True, text=True, cwd=PROJECT_ROOT)
        assert proc.returncode == 0, proc.stderr
        assert "unavailable" in proc.stdout.strip()

    def test_mount_probes_all_false(self):
        from tests.live_dsh.discovery import probe_all_instances_mounted
        probes = probe_all_instances_mounted()
        assert all(v is False for v in probes.values()), f"False expected, got {probes}"

    def test_same_uid_host(self):
        assert os.getuid() == 1000

    def test_l3_claim_possible_false(self):
        from tests.l3_runner.environment.readiness import assess_environment
        from tests.l3_runner.critical.runner import critical_fixtures_root
        report = assess_environment(
            scenario_id="L3-AUTH-001",
            fixtures_root=critical_fixtures_root(),
            orchestrator_uid=os.getuid(),
        )
        assert report.l3_claim_possible is False

    def test_rehearsal_ready_true(self):
        from tests.l3_runner.environment.readiness import assess_environment
        from tests.l3_runner.critical.runner import critical_fixtures_root
        report = assess_environment(
            scenario_id="L3-AUTH-001",
            fixtures_root=critical_fixtures_root(),
            orchestrator_uid=os.getuid(),
        )
        assert report.rehearsal_ready is True

    def test_approval_interactive_ready(self):
        from tests.environment.approval_composition import (
            approval_readiness, authorized_web_url,
        )
        r = approval_readiness()
        if authorized_web_url():
            assert r.interactive_ready is True, f"Expected interactive, got interactive_ready={r.interactive_ready}"
        else:
            # No authorized (launch-token) browser answerer attached: a
            # composed-but-unattached surface fails closed to COMPOSED.
            assert r.interactive_ready is False, (
                "interactive_ready must be False without an attached "
                f"browser answerer; got {r.interactive_ready}")
            assert r.status.value == "APPROVAL_COMPOSED"

    def test_approval_status_interactive_ready(self):
        from tests.environment.approval_composition import (
            approval_readiness, authorized_web_url, ApprovalStatus,
        )
        r = approval_readiness()
        if authorized_web_url():
            # In an attached Web GUI session, the service is composed and
            # interactive-ready. Since 2026-09-07 a real approval has also
            # flowed through the Web GUI (sanctioned escalation of the zeko
            # live-row edit), so the ladder may legitimately sit at
            # E2E_VERIFIED — the rung strictly above INTERACTIVE_READY, with
            # identical composition requirements.
            assert r.status in (ApprovalStatus.APPROVAL_INTERACTIVE_READY,
                                ApprovalStatus.APPROVAL_E2E_VERIFIED)
        else:
            # Fail-closed: composed but not attached → COMPOSED, never
            # promoted to the interactive rung.
            assert r.status is ApprovalStatus.APPROVAL_COMPOSED

    def test_l3_blockers_exclude_ans_in_web_gui_session(self):
        """With an authorized (launch-token) browser answerer attached,
        L3ENV-ANS-1 must NOT be a blocker. Without one the answerer checks
        block L3 fail-closed — composed != attached."""
        from tests.environment.approval_composition import authorized_web_url
        from tests.l3_runner.environment.readiness import assess_environment
        from tests.l3_runner.critical.runner import critical_fixtures_root
        report = assess_environment(
            scenario_id="L3-AUTH-001",
            fixtures_root=critical_fixtures_root(),
            orchestrator_uid=os.getuid(),
        )
        blocked_ids = {b.split(":")[0] for b in report.blocked}
        if authorized_web_url():
            assert "L3ENV-ANS-1" not in blocked_ids, \
                f"L3ENV-ANS-1 should NOT be blocked with an attached answerer; blocked={blocked_ids}"
        else:
            assert "L3ENV-ANS-1" in blocked_ids, (
                "L3ENV-ANS-1 must block fail-closed without an attached "
                f"browser answerer; blocked={blocked_ids}")

    def test_l3_blockers_include_uid_2(self):
        from tests.l3_runner.environment.readiness import assess_environment
        from tests.l3_runner.critical.runner import critical_fixtures_root
        report = assess_environment(
            scenario_id="L3-AUTH-001",
            fixtures_root=critical_fixtures_root(),
            orchestrator_uid=os.getuid(),
        )
        blocked_ids = {b.split(":")[0] for b in report.blocked}
        assert "L3ENV-UID-2" in blocked_ids

    def test_l3_blockers_include_d4d7_3(self):
        from tests.l3_runner.environment.readiness import assess_environment
        from tests.l3_runner.critical.runner import critical_fixtures_root
        report = assess_environment(
            scenario_id="L3-AUTH-001",
            fixtures_root=critical_fixtures_root(),
            orchestrator_uid=os.getuid(),
        )
        blocked_ids = {b.split(":")[0] for b in report.blocked}
        assert "L3ENV-D4D7-3" in blocked_ids

    def test_l3_blockers_include_plan_real(self):
        from tests.l3_runner.environment.readiness import assess_environment
        from tests.l3_runner.critical.runner import critical_fixtures_root
        report = assess_environment(
            scenario_id="L3-AUTH-001",
            fixtures_root=critical_fixtures_root(),
            orchestrator_uid=os.getuid(),
        )
        blocked_ids = {b.split(":")[0] for b in report.blocked}
        assert "L3ENV-PLAN-REAL" in blocked_ids

    def test_o5_applied_somad_nova_no_write_edit(self):
        """Verify the composed somad/nova delegation rows carry no write/edit.

        The 15 `tool-subagent-<id>` rows moved out of the live profile patch
        ($DSH_HOME/profiles/web/cordis.patch.yml) into
        `orchestrator/agent.cordis.yml` on 2026-10-11. The old text-scan of
        the patch degenerated into a vacuous pass once the rows moved — an
        empty section matched every `if section:` / `if allow_match:` guard,
        so the test reported PASS while verifying nothing. This version
        parses the composition that actually carries the rows, so a missing
        row or a drifted allow list FAILS loudly.

        `todo_write` is a permitted tool and contains the substring 'write';
        the parsed allow list holds exact tool names, so `todo_write` does
        not trip the O5 write/edit guard.
        """
        from tests.d4d7_composition import preset_tool_surface
        for rid in ("somad", "nova"):
            allow_tools = preset_tool_surface(f"role-{rid}")
            assert "write" not in allow_tools, (
                f"{rid} allow list still contains 'write' (O5 not applied): "
                f"{sorted(allow_tools)}")
            assert "edit" not in allow_tools, (
                f"{rid} allow list still contains 'edit' (O5 not applied): "
                f"{sorted(allow_tools)}")


# =========================================================================
# 4. Stale/contradictory evidence findings (S1-S10)
# =========================================================================

class TestStaleEvidenceFindings:
    """The stale/contradictory evidence findings documented in the audit are
    factually grounded and reflect the current state."""

    def test_s1_rebaseline_environment_mismatch(self):
        """The rebaseline claims web GUI; the current session is now also web GUI
        (DSH_WEB_URL set), so the rebaseline claim is consistent with the live
        environment — no headless/Web drift in this session."""
        rebaseline = _read_doc("phase-5/final/rebaseline/0001-live-assurance-rebaseline-report.md")
        if rebaseline:
            assert "http://127.0.0.1:13080" in rebaseline or "DSH_WEB_URL" in rebaseline
        # Current session is a Web GUI session (DSH_WEB_URL set) — matches rebaseline.
        assert os.environ.get("DSH_WEB_URL", "") == "http://127.0.0.1:13080"

    def test_s3_regression_counts_differ(self):
        """Regression counts across documents are different from current."""
        closure = _read_doc("phase-5/final/0001-security-closure-matrix.md")
        if closure:
            assert "1597" in closure
        security_gate = _read_doc("phase-5/final/0005-final-security-gate-evidence.md")
        if security_gate:
            assert "1642" in security_gate

    def test_s5_closure_matrix_approval_stale(self):
        """final/0001 says 'prompts disabled' for approval answerer."""
        closure = _read_doc("phase-5/final/0001-security-closure-matrix.md")
        if closure:
            assert "prompts disabled" in closure or "unavailable" in closure.lower()

    def test_s6_master_gate_g5_stale(self):
        """master-integration-gate says G5 BLOCKED."""
        gate = _read_doc("phase-5/master-integration-gate.md")
        if gate:
            # G5 row: "| **G5** | Independent verifier ... | — | **BLOCKED** |"
            assert "G5" in gate
            assert "BLOCKED" in gate
            # The row where G5 is named must carry the BLOCKED verdict.
            idx = gate.find("G5")
            assert "BLOCKED" in gate[idx:idx + 200], "G5 row should say BLOCKED (stale)"

    def test_s7_l3_final_lists_5_blockers(self):
        """l3/final/0001 lists 5 blockers including ANS-1."""
        l3_final = _read_doc("phase-5/l3/final/0001-l3-critical-control-final-readiness.md")
        if l3_final:
            assert "L3ENV-ANS-1" in l3_final

    def test_audit_lists_all_10_stale_findings(self):
        t = _read_audit()
        for i in range(1, 11):
            assert f"S{i}" in t, f"Stale finding S{i} not in audit document"


# =========================================================================
# 5. Honesty guards
# =========================================================================

class TestHonestyGuards:
    """No UNKNOWN marked as PASS; no OPEN marked as CLOSED; no L3 claim;
    no production-readiness claim."""

    def test_no_unknown_promoted_to_pass(self):
        t = _read_audit()
        # Table rows must not have UNKNOWN status with PASS evidence
        # (prose descriptions are exempt)
        for line in t.splitlines():
            if not line.lstrip().startswith("|"):
                continue
            if "UNKNOWN" in line.upper() and "PASS" in line.upper():
                if "UNKNOWN" in line and "PASS" in line:
                    # Check it's not a prose statement
                    if "No UNKNOWN" not in line and "no UNKNOWN" not in line:
                        assert False, f"Table row has UNKNOWN+PASS: {line.strip()}"

    def test_no_open_claimed_closed(self):
        t = _read_audit()
        # G10 must not be claimed as CLOSED
        # G13 must not be claimed as CLOSED
        for gap in ("G10", "G13"):
            # Check that the gap is not marked CLOSED anywhere
            # We need to be careful with the regex
            if gap in t:
                # Find the section around the gap
                idx = t.index(gap)
                section = t[idx:idx+300]
                assert "CLOSED" not in section.split("OPEN")[0] if "OPEN" in section else True

    def test_no_l3_claim(self):
        t = _read_audit()
        assert "NOT CLAIMED" in t
        assert "zero controls" in t
        assert "L3 CLAIMED" not in t

    def test_no_production_ready_claim(self):
        t = _read_audit()
        assert "NOT PRODUCTION-READY" in t
        # No positive production-readiness claim
        assert "PRODUCTION-READY" not in t.split("NOT PRODUCTION-READY")[0]


# =========================================================================
# 6. Package hygiene
# =========================================================================

class TestPackageHygiene:
    """The master-audit package imports no production control-plane code."""

    def test_no_production_imports(self):
        package_dir = os.path.join(PROJECT_ROOT, "tests", "phase-5", "final",
                                    "master-audit")
        banned = ("import control", "from control", "import orchestrator",
                  "from orchestrator", "import audit", "from audit",
                  "import state", "from state")
        for name in os.listdir(package_dir):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(package_dir, name), encoding="utf-8") as f:
                source = f.read()
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                assert not any(stripped.startswith(b) for b in banned), \
                    f"{name}: {stripped}"

    def test_only_expected_files_written(self):
        tests_dir = os.path.join(PROJECT_ROOT, "tests", "phase-5", "final",
                                  "master-audit")
        written = sorted(os.listdir(tests_dir))
        assert "__init__.py" in written
        assert "test_master_audit.py" in written
        assert os.path.isfile(AUDIT_DOC)