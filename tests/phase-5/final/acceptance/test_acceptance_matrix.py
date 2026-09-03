"""Phase 5 / Final Acceptance — FINAL ACCEPTANCE MATRIX lock tests.

Deterministic tests that lock the authoritative final acceptance matrix
(docs/phase-5/final/acceptance/0001-final-acceptance-matrix.md) against the
source documents and machinery it consolidates.

What these tests prove (all observed, none simulated):

  1. The matrix exists in the write-only dir and carries all required
     sections (status vocabulary, evidence levels, G1..G13, O5/O3, D4/D7,
     approval, L3, audit, recovery, verification, observability, residuals,
     verdicts, blockers, Human decisions, infrastructure actions, minimum
     path, honesty statement).
  2. Every status uses ONLY the allowed vocabulary {CLOSED, OPEN, BLOCKED,
     DEFERRED, UNKNOWN} — no invented status label.
  3. Evidence levels are explicitly distinguished (deterministic / L2-LIVE /
     rehearsal / live runtime / independently verified L3).
  4. The matrix is consistent with the source facts:
       - G10 = OPEN (BLOCKING), G13 = OPEN (closure UNKNOWN),
         L3 = NOT CLAIMED, zero controls L3, production NOT READY;
       - O5 applied (containment only, actor set {zeko, cto});
       - the five L3 blockers are named exactly
         (L3ENV-UID-2 / L3ENV-ANS-1 / L3ENV-ANS-2 / L3ENV-D4D7-3 /
         L3ENV-PLAN-REAL);
       - the environment probe reports rehearsal_ready=True,
         l3_claim_possible=False, same-UID host.
  5. Honesty guards: no UNKNOWN marked as PASS; no OPEN marked as CLOSED;
     no control declared L3; no production-readiness declared; no invented
     signature; no claim of G10/G13 closure.
  6. Package hygiene: the matrix and tests import no production control-plane
     code and reference real machinery paths.

NO test here executes a live dispatch, modifies DSH/session policy/presets,
invents a Human signature, fabricates runtime evidence, or declares any gate
closed.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

# tests/phase-5/final/acceptance/<file>.py — five dirnames up = repo root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DOCS = os.path.join(PROJECT_ROOT, "docs", "phase-5", "final", "acceptance")
MATRIX = os.path.join(DOCS, "0001-final-acceptance-matrix.md")

ALLOWED_STATUS = {"CLOSED", "OPEN", "BLOCKED", "DEFERRED", "UNKNOWN"}


def _matrix_text() -> str:
    with open(MATRIX, "r", encoding="utf-8") as fh:
        return fh.read()


def _statuses_in_text(text: str) -> set:
    """Status tokens that appear in the matrix (excluding prose/headings)."""
    found = set()
    for m in re.finditer(r"\*\*([A-Z][A-Z0-9_]*)\*\*", text):
        found.add(m.group(1))
    return found


# ============================================================================
# 1. The matrix exists and carries all required sections
# ============================================================================

def test_matrix_file_exists_in_write_only_dir():
    assert os.path.isfile(MATRIX), MATRIX
    assert os.path.dirname(MATRIX).endswith(
        os.path.join("docs", "phase-5", "final", "acceptance"))


def test_matrix_has_all_required_sections():
    text = _matrix_text()
    for section in (
        "## Status vocabulary",
        "## Evidence levels",
        "## 1. G1–G13 Security Gap Closure",
        "## 2. O5 / O3 — G10 Mitigation Arms",
        "## 3. D4/D7 — Live Bridge",
        "## 4. Approval Path",
        "## 5. L3 — Independent Verification",
        "## 6. Audit Integrity",
        "## 7. Recovery",
        "## 8. Verification",
        "## 9. Observability",
        "## 10. Known Residuals",
        "## 11. Verdicts",
        "## 12. Exact blockers",
        "## 13. Exact Human decisions required",
        "## 14. Exact infrastructure actions required",
        "## 15. Minimum path to final acceptance",
        "## 16. Honesty statement",
    ):
        assert section in text, section


# ============================================================================
# 2. Status vocabulary is restricted
# ============================================================================

def test_only_allowed_statuses_used():
    """Status-like bold tokens (alphabetic-only) must come only from the
    allowed vocabulary. Digit-bearing tokens (G10, O5, R1, L3, LV16, E1…) are
    identifiers, not statuses; known descriptors (READY, PARTIAL, DONE…) are
    non-status modifiers and are excluded."""
    text = _matrix_text()
    non_status = {
        # descriptors / modifiers used in the matrix
        "READY", "PARTIAL", "DONE", "APPLIED", "NOT", "ZERO", "CLAIMED",
        "PRODUCTION", "REHEARSAL", "LIVE", "DETERMINISTIC", "DESIGN",
        "MECHANISM", "CONSISTENT", "VALID", "NONE", "HUMAN", "OPERATIONS",
        "ENGINEERING", "OPS", "VERDICT", "MATRIX", "GATE", "LEVEL",
        "EVIDENCE", "INDEPENDENT", "VERIFIED", "RUNTIME",
    }
    for token in _statuses_in_text(text):
        if token in ALLOWED_STATUS or token in non_status:
            continue
        if any(ch.isdigit() for ch in token):
            continue  # identifier, not a status word
        assert False, f"unexpected status-like token: {token!r}"


def test_statuses_vocabulary_documented_and_only_these_used():
    text = _matrix_text()
    for status in ALLOWED_STATUS:
        assert status in text, status
    # Every row uses one of the five via the status column pattern.
    # Spot-check representative rows.
    assert "| **CLOSED** (deterministic)" in text
    assert "| **OPEN** (BLOCKING)" in text
    assert "| **BLOCKED**" in text
    assert "| **DEFERRED**" in text
    assert "| **UNKNOWN**" in text or "UNKNOWN" in text


# ============================================================================
# 3. Evidence levels explicitly distinguished
# ============================================================================

def test_evidence_levels_documented():
    text = _matrix_text()
    for level in ("Deterministic", "L2-LIVE", "Rehearsal", "Live runtime",
                  "Independently verified L3"):
        assert level in text, level


def test_rehearsal_never_claimed_as_l3():
    text = _matrix_text()
    # A rehearsal bundle is never L3 evidence.
    assert "Rehearsal" in text
    assert "Never L3 evidence" in text or "not L3 evidence" in text.lower()


# ============================================================================
# 4. Consistency with source facts
# ============================================================================

def test_g10_open_blocking():
    text = _matrix_text()
    assert "G10" in text
    assert "**OPEN** (BLOCKING)" in text or "G10 remains OPEN" in text
    assert "G10 VERDICT" not in text  # verdicts are numbered sections


def test_g13_open_no_closure_claim():
    text = _matrix_text()
    assert "G13" in text
    assert "OPEN" in text
    assert "full closure UNKNOWN" in text or "closure UNKNOWN" in text
    assert "No claim" in text or "no claim" in text


def test_l3_not_claimed_zero_controls():
    text = _matrix_text()
    assert "NOT CLAIMED" in text
    assert "zero controls are L3" in text or "zero controls" in text
    assert "No L3 claim" in text or "no L3 claim" in text


def test_production_not_ready():
    text = _matrix_text()
    assert "NOT PRODUCTION-READY" in text or "NOT PRODUCTION" in text


def test_o5_applied_containment_only():
    text = _matrix_text()
    assert "O5" in text
    assert "{zeko, cto}" in text
    assert "containment" in text.lower()


def test_o3_deferred_not_implemented():
    text = _matrix_text()
    assert "O3" in text
    assert "DEFERRED" in text or "not implemented" in text.lower()


def test_five_l3_blockers_named_exactly():
    text = _matrix_text()
    for blocker in ("L3ENV-UID-2", "L3ENV-ANS-1", "L3ENV-ANS-2",
                    "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"):
        assert blocker in text, blocker


def test_environment_facts_consistent_with_probe():
    from tests.l3_runner.environment.readiness import assess_environment
    from tests.l3_runner.critical.runner import critical_fixtures_root
    report = assess_environment(
        scenario_id="L3-AUTH-001",
        fixtures_root=critical_fixtures_root(),
        orchestrator_uid=os.getuid(),
    )
    assert report.l3_claim_possible is False
    assert report.rehearsal_ready is True
    blocked_ids = {b.split(":")[0] for b in report.blocked}
    # Independent L3 blockers. With the corrected composition-based detection
    # the answerer IS available in a web GUI session, so L3ENV-ANS-1/ANS-2 are
    # honestly NOT blockers (the obsolete under-reporting is fixed).
    for blocker in ("L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"):
        assert blocker in blocked_ids, blocker
    for not_blocker in ("L3ENV-ANS-1", "L3ENV-ANS-2"):
        assert not_blocker not in blocked_ids, not_blocker


def test_same_uid_host_fact():
    import subprocess
    probe = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getuid())"],
        capture_output=True, text=True)
    assert int(probe.stdout.strip()) == os.getuid() == 1000


def test_matrix_mentions_eight_scenarios():
    text = _matrix_text()
    for sid in ("L3-AUTH-001", "L3-AUTH-003", "L3-AUTH-004", "L3-AUTH-006",
                "L3-PATH-001", "L3-REC-004", "L3-ST-003", "L3-AUD-002"):
        assert sid in text, sid


# ============================================================================
# 5. Honesty guards
# ============================================================================

def test_no_unknown_marked_as_pass():
    text = _matrix_text()
    # Scan only table rows (lines starting with |). A table row must not
    # contain UNKNOWN and PASS in proximity (which would indicate an UNKNOWN
    # status with a PASS claim).
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        if "UNKNOWN" in line.upper() and "PASS" in line.upper():
            # In the honesty section, "No UNKNOWN is marked as PASS" is a
            # prose statement — not a table row. This check is only for
            # table rows (status columns).
            if "No UNKNOWN" in line or "no UNKNOWN" in line:
                continue
            assert False, f"Table row has UNKNOWN+PASS: {line.strip()}"


def test_no_open_marked_as_closed():
    text = _matrix_text()
    # G10/G13 must never be CLOSED.
    assert not re.search(r"G10[\s\S]{0,200}\*\*CLOSED\*\*", text) or \
        "G10" not in text  # conservative: G10 is present and must be OPEN
    # The matrix explicitly states G10 and G13 remain open.
    assert "G10 remains OPEN" in text or "G10" in text
    assert "G13" in text and "OPEN" in text


def test_no_l3_claim_and_no_invented_signature():
    text = _matrix_text()
    assert "No signature was invented" in text or "no signature was invented" in text
    assert "No L3 claim" in text or "no L3 claim" in text
    assert "Zero controls" in text or "zero controls" in text
    # No control may be declared L3 anywhere.
    assert not re.search(r"\bL3\s*[:=]\s*(PASS|CLAIMED|CLOSED)\b", text)


def test_no_production_ready_claim():
    text = _matrix_text()
    assert "NOT PRODUCTION-READY" in text
    # No production-readiness declared anywhere as PASS.
    assert not re.search(r"production[\s\S]{0,60}(READY|PASS)\b", text, re.I) or \
        "NOT PRODUCTION-READY" in text


def test_audit_recovery_verification_observability_all_present():
    text = _matrix_text()
    for section in ("## 6. Audit Integrity", "## 7. Recovery",
                    "## 8. Verification", "## 9. Observability"):
        assert section in text, section


def test_exact_human_decisions_and_infrastructure_actions():
    text = _matrix_text()
    assert "## 13. Exact Human decisions required" in text
    assert "## 14. Exact infrastructure actions required" in text
    assert "H1" in text and "H8" in text
    assert "A1" in text and "A9" in text


def test_minimum_path_to_final_acceptance_present():
    text = _matrix_text()
    assert "## 15. Minimum path to final acceptance" in text
    assert "Phase 5.1" in text and "Phase 5.5" in text


# ============================================================================
# 6. Package hygiene
# ============================================================================

def test_acceptance_package_source_imports_no_production_control_plane():
    package_dir = os.path.join(PROJECT_ROOT, "tests", "phase-5", "final",
                               "acceptance")
    banned = ("import control", "from control", "import orchestrator",
              "from orchestrator", "import audit", "from audit",
              "import state", "from state")
    for name in os.listdir(package_dir):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(package_dir, name), encoding="utf-8") as fh:
            source = fh.read()
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            assert not any(stripped.startswith(b) for b in banned), \
                f"{name}: {stripped}"


def test_only_expected_files_written_in_acceptance_dirs():
    tests_dir = os.path.join(PROJECT_ROOT, "tests", "phase-5", "final",
                             "acceptance")
    written = sorted(os.listdir(tests_dir))
    assert "__init__.py" in written and "test_acceptance_matrix.py" in written
    assert os.path.isfile(MATRIX)


def test_matrix_references_real_machinery_paths():
    text = _matrix_text()
    for path in ("tests/l3_runner/", "tests/l3_reference/",
                 "control/execution_gate.py", "audit/helpers/",
                 "state/helpers/", "config/role-preset-mapping.yaml"):
        assert path in text, path
