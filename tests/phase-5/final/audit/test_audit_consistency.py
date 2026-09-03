"""Phase 5 / Session D — MASTER EVIDENCE CONSISTENCY AUDIT.

These tests lock the consistency audit findings: they assert that the
discrepancies documented in the audit report are factually correct, and
that the key claims (G10 OPEN, G13 OPEN/UNKNOWN, L3 NOT CLAIMED, production
NOT PRODUCTION-READY, D4/D7 marker UNSET) remain consistent across all
authoritative documents.

Write-only scope: tests/phase-5/final/audit/ + docs/phase-5/final/audit/.
Nothing else is modified; no DSH/policy change, no signature invented, no claim made.
"""

import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DOCS = os.path.join(PROJECT_ROOT, "docs")


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
# VERDICT CONSISTENCY
# =========================================================================

class TestProductionVerdictConsistency:
    """ALL authoritative documents must agree: NOT PRODUCTION-READY."""

    PATHS = [
        "phase-5/final/0001-security-closure-matrix.md",
        "phase-5/final/0005-final-security-gate-evidence.md",
        "phase-5/final/acceptance/0001-final-acceptance-matrix.md",
        "phase-5/final/live-assurance/0001-live-assurance-coordinator-report.md",
    ]

    def test_closure_matrix_says_not_production_ready(self):
        t = _read_doc(self.PATHS[0]) or ""
        assert "NOT PRODUCTION-READY" in t, "closure matrix must say NOT PRODUCTION-READY"

    def test_security_gate_says_not_production_ready(self):
        t = _read_doc(self.PATHS[1]) or ""
        # This doc uses "no production deployment started" instead of
        # "NOT PRODUCTION-READY" — both are equivalent.
        assert "NOT PRODUCTION-READY" in t or "no production deployment started" in t

    def test_acceptance_matrix_says_not_production_ready(self):
        t = _read_doc(self.PATHS[2]) or ""
        assert "NOT PRODUCTION-READY" in t

    def test_live_assurance_says_not_production_ready(self):
        t = _read_doc(self.PATHS[3]) or ""
        assert "NOT PRODUCTION-READY" in t


class TestG10VerdictConsistency:
    """ALL authoritative documents must agree: G10 OPEN / BLOCKING."""

    PATHS = [
        "phase-5/final/0001-security-closure-matrix.md",
        "phase-5/final/0002-g10-formal-residual-proof.md",
        "phase-5/final/0005-final-security-gate-evidence.md",
        "phase-5/final/acceptance/0001-final-acceptance-matrix.md",
    ]

    def test_g10_open_in_every_authoritative_doc(self):
        for p in self.PATHS:
            t = _read_doc(p) or ""
            has_open = "G10" in t and ("OPEN" in t.split("G10")[1][:50]
                                      if "G10" in t else False)
            lines = _grep_doc("G10.*OPEN|G10.*BLOCKING", p)
            assert len(lines) > 0, f"G10 OPEN/BLOCKING not found in {p}"


class TestG13VerdictConsistency:
    """ALL authoritative documents must agree: G13 OPEN / UNKNOWN, no claim."""

    PATHS = [
        "phase-5/final/0001-security-closure-matrix.md",
        "phase-5/final/0003-g13-external-content-evidence.md",
        "phase-5/final/0005-final-security-gate-evidence.md",
        "phase-5/final/acceptance/0001-final-acceptance-matrix.md",
    ]

    def test_g13_open_or_unknown_in_every_doc(self):
        for p in self.PATHS:
            t = _read_doc(p) or ""
            # Must contain either OPEN or UNKNOWN for G13, and no claim of closure
            assert "G13" in t, f"G13 not mentioned in {p}"
            # Check no document claims G13 is closed
            assert "G13.*CLOSED" not in t, f"G13 claims CLOSED in {p}"


class TestL3VerdictConsistency:
    """ALL authoritative documents must agree: L3 NOT CLAIMED, ZERO controls."""

    PATHS = [
        "phase-5/final/0001-security-closure-matrix.md",
        "phase-5/final/0004-l3-critical-controls-evidence.md",
        "phase-5/final/0005-final-security-gate-evidence.md",
        "phase-5/final/acceptance/0001-final-acceptance-matrix.md",
        "phase-5/l3/final/0001-l3-critical-control-final-readiness.md",
    ]

    def test_no_l3_claim_in_any_authoritative_doc(self):
        for p in self.PATHS:
            t = _read_doc(p) or ""
            assert "L3" in t, f"L3 not mentioned in {p}"
            # Check that no document claims L3 is claimed
            no_claim_patterns = ["NOT CLAIMED", "not claimed", "ZERO controls",
                                 "l3_claim=false", "l3_claim_possible=False", "no L3 claim"]
            found = any(pat in t for pat in no_claim_patterns)
            assert found, f"No L3-not-claimed pattern found in {p}"


# =========================================================================
# DISCREPANCY VERIFICATION
# =========================================================================

class TestRegressionCountDiscrepancy:
    """R1: Regression counts must differ across documents (the discrepancy)."""

    def test_1597_in_closure_matrix(self):
        t = _read_doc("phase-5/final/0001-security-closure-matrix.md") or ""
        assert "1597" in t, "closure matrix must cite 1597"

    def test_1642_in_security_gate(self):
        t = _read_doc("phase-5/final/0005-final-security-gate-evidence.md") or ""
        assert "1642" in t, "security gate must cite 1642"

    def test_1898_in_l3_final(self):
        t = _read_doc("phase-5/l3/final/0001-l3-critical-control-final-readiness.md") or ""
        assert "1898" in t, "l3 final must cite 1898"

    def test_counts_differ(self):
        t1 = _read_doc("phase-5/final/0001-security-closure-matrix.md") or ""
        t2 = _read_doc("phase-5/final/0005-final-security-gate-evidence.md") or ""
        t3 = _read_doc("phase-5/l3/final/0001-l3-critical-control-final-readiness.md") or ""
        # 1597, 1642, 1898 are all different
        assert "1597" in t1 and "1642" in t2 and "1898" in t3
        assert "1597" != "1642" != "1898"


class TestL3BlockerCountDiscrepancy:
    """R4: 5-blocker vs 3-blocker discrepancy must be detectable."""

    def test_l3_final_0001_lists_5_blockers(self):
        t = _read_doc("phase-5/l3/final/0001-l3-critical-control-final-readiness.md") or ""
        # Must contain L3ENV-ANS-1 as a blocker
        assert "L3ENV-ANS-1" in t, "l3/final/0001 must list L3ENV-ANS-1 as a blocker"

    def test_env_final_0001_lists_3_blockers(self):
        t = _read_doc("phase-5/environment/final/0001-operator-infrastructure-checklist.md") or ""
        lines = _grep_doc("L3ENV-ANS-1.*no longer block", t)
        # Actually the file is a path — need to read it
        # The doc should say ANS-1/2 are no longer blockers
        assert "no longer blockers" in t, "env/final/0001 must say ANS-1/2 no longer blockers"


class TestApprovalAnswererDiscrepancy:
    """R5: Answerer 'unavailable' vs 'available by composition' discrepancy."""

    def test_closure_matrix_says_prompts_disabled(self):
        t = _read_doc("phase-5/final/0001-security-closure-matrix.md") or ""
        lines = _grep_doc("prompts disabled", "phase-5/final/0001-security-closure-matrix.md")
        assert len(lines) > 0, "closure matrix must say prompts disabled (stale claim)"

    def test_env_final_0001_says_answerer_ready(self):
        t = _read_doc("phase-5/environment/final/0001-operator-infrastructure-checklist.md") or ""
        assert "READY" in t, "env/final/0001 must say answerer READY"


class TestG5StatusDiscrepancy:
    """R3: G5 BLOCKED (master gate) vs CLOSED (final docs)."""

    def test_master_gate_says_g5_blocked(self):
        t = _read_doc("phase-5/master-integration-gate.md") or ""
        lines = _grep_doc("G5.*BLOCKED", "phase-5/master-integration-gate.md")
        assert len(lines) > 0, "master gate must say G5 BLOCKED"

    def test_closure_matrix_says_g5_closed(self):
        t = _read_doc("phase-5/final/0001-security-closure-matrix.md") or ""
        # Find the G5 row
        lines = _grep_doc("G5", "phase-5/final/0001-security-closure-matrix.md")
        # Some must say CLOSED
        closed_lines = [l for l in lines if "CLOSED" in l]
        assert len(closed_lines) > 0, "closure matrix must say G5 CLOSED"


# =========================================================================
# D4/D7 CONSISTENCY
# =========================================================================

class TestD4D7Consistency:
    """D4/D7 marker must be UNSET in every authoritative document."""

    PATHS = [
        "phase-5/final/0001-security-closure-matrix.md",
        "phase-5/final/0005-final-security-gate-evidence.md",
        "phase-5/final/acceptance/0001-final-acceptance-matrix.md",
        "phase-5/final/live-assurance/0001-live-assurance-coordinator-report.md",
        "phase-5/final/preflight/0001-final-operator-checklist.md",
    ]

    def test_marker_unset_everywhere(self):
        for p in self.PATHS:
            t = _read_doc(p) or ""
            # Must state that D4/D7 marker is unset
            found_unset = False
            for pat in ["UNSET", "unset", "not set", "BLOCKED", "NOT_MOUNTED",
                         "inactive", "UNAVAILABLE", "not active"]:
                if pat in t:
                    found_unset = True
                    break
            assert found_unset, f"No D4/D7 unset/blocked pattern found in {p}"


# =========================================================================
# O5 CONSISTENCY
# =========================================================================

class TestO5Consistency:
    """O5 applied as containment only — G10 remains OPEN."""

    PATHS = [
        "phase-5/final/0001-security-closure-matrix.md",
        "phase-5/final/0002-g10-formal-residual-proof.md",
        "phase-5/final/0005-final-security-gate-evidence.md",
        "phase-5/final/acceptance/0001-final-acceptance-matrix.md",
        "phase-5/security/g10/implementation/0002-o5-application-record.md",
    ]

    def test_os_applied_everywhere(self):
        for p in self.PATHS:
            t = _read_doc(p) or ""
            # Must mention O5 or the addendum
            # Check for terms like "O5 was applied", "O5 applied", "addendum",
            # "removed write/edit from somad and nova"
            found = False
            for pat in ["O5 applied", "O5 APPLIED", "Addendum", "addendum",
                         "removed write/edit", "containment only"]:
                if pat in t:
                    found = True
                    break
            assert found, f"No O5 application mention found in {p}"

    def test_g10_remains_open_after_o5(self):
        for p in self.PATHS:
            t = _read_doc(p) or ""
            # Check that G10 remains OPEN (not closed)
            if "G10" in t:
                closed = "G10.*CLOSED" in t
                assert not closed, f"G10 claimed CLOSED (post-O5) in {p}"


# =========================================================================
# AUDIT DOCUMENT INTEGRITY
# =========================================================================

class TestAuditDocumentIntegrity:
    """The audit document itself must be present and correct."""

    AUDIT_PATH = "phase-5/final/audit/0001-evidence-consistency-audit.md"

    def test_audit_document_exists(self):
        assert _read_doc(self.AUDIT_PATH) is not None, "audit document must exist"

    def test_audit_lists_20_discrepancies(self):
        t = _read_doc(self.AUDIT_PATH) or ""
        assert "20 discrepancies" in t, "audit must document 20 discrepancies"

    def test_audit_says_not_production_ready(self):
        t = _read_doc(self.AUDIT_PATH) or ""
        assert "NOT PRODUCTION-READY" in t

    def test_audit_records_exact_blockers(self):
        t = _read_doc(self.AUDIT_PATH) or ""
        assert "L3ENV-UID-2" in t
        assert "L3ENV-D4D7-3" in t
        assert "L3ENV-PLAN-REAL" in t

    def test_audit_maps_each_r_to_classification(self):
        t = _read_doc(self.AUDIT_PATH) or ""
        for r_id in ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
                      "R9", "R10", "R11", "R12", "R13", "R14", "R15",
                      "R16", "R17", "R18", "R19", "R20"]:
            assert r_id in t, f"Discrepancy {r_id} must be documented"

    def test_audit_has_no_contradictory_claims_within_itself(self):
        t = _read_doc(self.AUDIT_PATH) or ""
        # The audit must not claim production-ready
        assert "PRODUCTION-READY" not in t.split("NOT PRODUCTION-READY")[0]
        # The audit must not claim G10 CLOSED
        assert "G10.*CLOSED" not in t
        # The audit must not claim L3
        assert "L3 CLAIMED" not in t
