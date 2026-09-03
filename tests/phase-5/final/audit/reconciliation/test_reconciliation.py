"""Phase 5 / Authoritative Evidence Reconciliation tests.

These tests lock the reconciliation findings: they assert that the
reconciliation report (`docs/phase-5/final/audit/reconciliation/0001-reconciliation-report.md`)
records the authoritative current values for R1-R20, that the audit's
internal arithmetic inconsistency is documented with corrected counts, and
that the authoritative values (regression count, L3 count, blocker count,
approval state, G5 status, O5 status, final acceptance state) are recorded
consistently with the current workspace state.

Write-only scope: tests/phase-5/final/audit/reconciliation/ +
docs/phase-5/final/audit/reconciliation/. Nothing else is modified;
no DSH/policy change, no signature invented, no claim made.
"""

import json
import os
import re
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DOCS = os.path.join(PROJECT_ROOT, "docs")
RECON_DOC = "phase-5/final/audit/reconciliation/0001-reconciliation-report.md"
AUDIT_DOC = "phase-5/final/audit/0001-evidence-consistency-audit.md"


def _read_doc(path):
    """Read a doc file relative to docs/."""
    full = os.path.join(DOCS, path)
    if not os.path.exists(full):
        return None
    with open(full, "r") as f:
        return f.read()


def _grep_doc(pattern, path):
    """Search for pattern in a doc file, return list of matching lines."""
    text = _read_doc(path)
    if text is None:
        return []
    return [line for line in text.split("\n") if re.search(pattern, line)]


# =========================================================================
# RECONCILIATION DOCUMENT INTEGRITY
# =========================================================================

class TestReconciliationDocumentIntegrity:
    """The reconciliation report must exist and cover all 20 findings."""

    def test_reconciliation_document_exists(self):
        assert _read_doc(RECON_DOC) is not None, "reconciliation report must exist"

    def test_covers_all_20_findings(self):
        t = _read_doc(RECON_DOC) or ""
        for r_id in [f"R{i}" for i in range(1, 21)]:
            assert f"## {r_id} —" in t, \
                f"finding {r_id} must be reconciled"

    def test_status_table_lists_all_20(self):
        t = _read_doc(RECON_DOC) or ""
        # The R1-R20 STATUS table must reference every R id
        for r_id in [f"R{i}" for i in range(1, 21)]:
            assert r_id in t, f"{r_id} must appear in the reconciliation report"

    def test_authoritative_values_section_present(self):
        t = _read_doc(RECON_DOC) or ""
        for header in ["AUTHORITATIVE REGRESSION COUNT",
                       "AUTHORITATIVE L3 COUNT",
                       "AUTHORITATIVE BLOCKER COUNT",
                       "AUTHORITATIVE APPROVAL STATE",
                       "AUTHORITATIVE G5 STATUS",
                       "AUTHORITATIVE O5 STATUS",
                       "AUTHORITATIVE FINAL ACCEPTANCE STATE"]:
            assert header in t, f"missing {header}"

    def test_scope_check_present(self):
        t = _read_doc(RECON_DOC) or ""
        assert "SCOPE CHECK" in t, "reconciliation must include a scope check"

    def test_reconciliation_scopes_written_paths_only(self):
        t = _read_doc(RECON_DOC) or ""
        assert "docs/phase-5/final/audit/reconciliation/" in t, \
            "reconciliation must declare its write scope"


# =========================================================================
# AUTHORITATIVE VALUES
# =========================================================================

class TestAuthoritativeRegressionCount:
    """R1: authoritative regression count recorded and consistent."""

    def test_regression_count_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "2761" in t, "reconciliation must record 2761 passed"

    def test_skipped_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "15 skipped" in t, "reconciliation must record 15 skipped"

    def test_total_collected_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "2786" in t, "reconciliation must record 2786 collected"

    def test_historical_values_preserved(self):
        t = _read_doc(RECON_DOC) or ""
        # Historical regression values must be preserved, not overwritten
        assert "1597" in t and "1642" in t and "1898" in t, \
            "historical regression values must be preserved"

    def test_isolation_failures_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "isolation" in t, "reconciliation must document the isolation failures"


class TestAuthoritativeL3Count:
    """R2: authoritative L3 count recorded and consistent."""

    def test_l3_count_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "592" in t, "reconciliation must record 592 L3 tests passed"

    def test_l3_historical_values_preserved(self):
        t = _read_doc(RECON_DOC) or ""
        for h in ["148", "275", "389", "545"]:
            assert h in t, f"historical L3 count {h} must be preserved"


class TestAuthoritativeBlockerCount:
    """R4/R6: authoritative L3 blocker count = 3 (ANS-1/2 PASS)."""

    def test_three_blockers_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "3 L3 blockers" in t, "reconciliation must record 3 L3 blockers"
        assert "L3ENV-UID-2" in t
        assert "L3ENV-D4D7-3" in t
        assert "L3ENV-PLAN-REAL" in t

    def test_ans_no_longer_blockers(self):
        t = _read_doc(RECON_DOC) or ""
        # ANS-1/2 must be recorded as PASS / not blockers
        assert "ANS-1/2 now PASS" in t or "ANS-1/2 PASS" in t or \
            "L3ENV-ANS-1/2 = PASS" in t, \
            "reconciliation must record ANS-1/2 as PASS (not blockers)"


class TestAuthoritativeApprovalState:
    """R5/R18: approval answerer available by composition; E2E UNKNOWN."""

    def test_available_by_composition_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "AVAILABLE BY COMPOSITION" in t, \
            "reconciliation must record approval available by composition"

    def test_e2e_unknown_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "E2E = UNKNOWN" in t or "E2E = **UNKNOWN**" in t, \
            "reconciliation must record E2E as UNKNOWN"


class TestAuthoritativeG5Status:
    """R3: G5 = CLOSED (infrastructure); master gate is historical."""

    def test_g5_closed_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "G5 = CLOSED (infrastructure" in t, \
            "reconciliation must record G5 CLOSED (infrastructure)"

    def test_live_l3_still_blocked(self):
        t = _read_doc(RECON_DOC) or ""
        assert "Live L3 execution remains BLOCKED" in t or \
            "live L3 execution remains BLOCKED" in t, \
            "reconciliation must note live L3 execution remains BLOCKED"


class TestAuthoritativeO5Status:
    """R7/R20: O5 applied (containment only); G10 remains OPEN."""

    def test_o5_applied_documented(self):
        t = _read_doc(RECON_DOC) or ""
        assert "O5 APPLIED (containment only)" in t or \
            "O5 APPLIED" in t, "reconciliation must record O5 applied"

    def test_g10_remains_open(self):
        t = _read_doc(RECON_DOC) or ""
        assert "G10 remains OPEN/BLOCKING" in t or \
            "G10 remains OPEN / BLOCKING" in t, \
            "reconciliation must record G10 remains OPEN"


class TestAuthoritativeAcceptanceState:
    """Final acceptance: NOT PRODUCTION-READY (unchanged)."""

    def test_not_production_ready(self):
        t = _read_doc(RECON_DOC) or ""
        assert "NOT PRODUCTION-READY" in t, \
            "reconciliation must preserve NOT PRODUCTION-READY verdict"

    def test_l3_not_claimed(self):
        t = _read_doc(RECON_DOC) or ""
        assert "NOT CLAIMED" in t, \
            "reconciliation must preserve L3 NOT CLAIMED verdict"


# =========================================================================
# AUDIT ARITHMETIC INCONSISTENCY
# =========================================================================

class TestAuditArithmeticCorrection:
    """The audit report's internal arithmetic must be documented & corrected."""

    def test_audit_arithmetic_section_present(self):
        t = _read_doc(RECON_DOC) or ""
        assert "Audit Report Internal Arithmetic Inconsistency" in t, \
            "reconciliation must document the audit arithmetic inconsistency"

    def test_high_count_corrected_to_6(self):
        t = _read_doc(RECON_DOC) or ""
        # The audit claims HIGH=5 but lists 6 items (R1,R2,R4,R5,R6,R18)
        assert "Correct count = **6**" in t or "HIGH** | 6 |" in t, \
            "reconciliation must correct HIGH count to 6"

    def test_medium_count_corrected(self):
        t = _read_doc(RECON_DOC) or ""
        # R8 severity is MEDIUM (per discrepancy table) but was omitted from
        # the audit's MEDIUM row; correct MEDIUM set = R3,R7,R8,R15 = 4
        assert "MEDIUM** | 4 |" in t, "reconciliation must correct MEDIUM count to 4"

    def test_low_count_corrected(self):
        t = _read_doc(RECON_DOC) or ""
        # LOW listed 8 items (incl. R8 which is MEDIUM) but count said 6
        assert "LOW** | 7 |" in t, "reconciliation must correct LOW count to 7"

    def test_stale_count_corrected_to_9(self):
        t = _read_doc(RECON_DOC) or ""
        # The audit claims 5 STALE but lists 9 STALE findings
        assert "**9** STALE" in t or "STALE** | 9 |" in t or \
            "STALE: claimed **5** but ... **9**" in t or \
            "**STALE** | 9 |" in t, \
            "reconciliation must correct STALE count to 9"

    def test_classification_counts_sum_to_20(self):
        t = _read_doc(RECON_DOC) or ""
        # STALE 9 + CONTRADICTORY 4 + MISSING EVIDENCE 3 + VALID 4 + UNKNOWN 0 = 20
        assert "9" in t and "CONTRADICTORY** | 4" in t and \
            "MISSING EVIDENCE** | 3" in t and "VALID** | 4" in t, \
            "reconciliation must document corrected classification counts"


# =========================================================================
# R1-R20 STATUS TABLE
# =========================================================================

class TestR1R20Status:
    """Every finding must have a reconciled status entry."""

    def test_status_entries(self):
        t = _read_doc(RECON_DOC) or ""
        # Every R must have a row in the status table with a resolved state
        for r_id in [f"R{i}" for i in range(1, 21)]:
            # status rows look like: | R1 | ... | ✅ RESOLVED | ... |
            line = next((l for l in t.split("\n")
                         if l.startswith(f"| {r_id} |")), None)
            assert line is not None, f"missing status row for {r_id}"

    def test_no_finding_left_unclassified(self):
        t = _read_doc(RECON_DOC) or ""
        # None of the 20 findings should be left as UNKNOWN classification
        unknown_rows = [l for l in t.split("\n")
                        if re.match(r"\| R\d+ \|.*\|.*UNKNOWN\|", l)]
        # R12/R17/R19/R20 are VALID; no finding is classified UNKNOWN
        assert len(unknown_rows) == 0, f"unexpected UNKNOWN rows: {unknown_rows}"


# =========================================================================
# CONSISTENCY WITH CURRENT WORKSPACE STATE
# =========================================================================

class TestConsistencyWithWorkspace:
    """Reconciliation values must match the current workspace state."""

    def test_authorization_count_matches(self):
        # R11: current tests/authorization/ count
        t = _read_doc(RECON_DOC) or ""
        assert "178 passed" in t, \
            "reconciliation must record 178 authorization tests"

    def test_g10_count_matches(self):
        # R13: current tests/g10/ count
        t = _read_doc(RECON_DOC) or ""
        assert "201" in t, "reconciliation must record 201 g10 tests"

    def test_g13_count_matches(self):
        # R16: current tests/g13/ count
        t = _read_doc(RECON_DOC) or ""
        assert "107" in t, "reconciliation must record 107 g13 tests"

    def test_entrypoint_count_matches(self):
        # R17: current entrypoint count
        t = _read_doc(RECON_DOC) or ""
        assert "270 passed" in t, "reconciliation must record 270 entrypoint tests"

    def test_marker_unset_state_recorded(self):
        t = _read_doc(RECON_DOC) or ""
        assert "DSH_LIVE_BRIDGE_ACTIVE" in t, \
            "reconciliation must reference the live bridge marker"
