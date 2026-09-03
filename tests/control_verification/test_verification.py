"""Verification control-plane tests — AUTH-INV-15 / VERIFY-001..003 / THREAT-016.

Required semantics under test:
  - AUTH-INV-15: COMPLETE only after verified outcome; false-success refused
  - VERIFY-001: false success report (agent claims done without evidence → no COMPLETE)
  - VERIFY-002: expected vs actual mismatch → FAIL → recovery path
  - VERIFY-003: incomplete verification evidence → no COMPLETE (HIGH)
  - Independence requirements per action category
  - VerificationSession lifecycle (expected declared BEFORE execution)
  - VerificationGate fail-closed
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from control.verification import (
    VerificationSession,
    VerificationGate,
    VerificationEvidence,
    VerificationResult,
    ExpectedOutcome,
    VerificationDenied,
    VerificationError,
    verification_requirements,
    action_category,
    evaluate_verification,
)


# ===========================================================================
# AUTH-INV-15 — COMPLETE only after verified outcome
# ===========================================================================

class TestAuthInv15:
    """AUTH-INV-15: COMPLETE requires a verified outcome."""

    def test_verified_outcome_allows_complete(self):
        """A properly verified outcome (code_change with test+build evidence)
        allows COMPLETE."""
        session = VerificationSession("t-1", "code_change",
                                      expected={"exit_code": 0})
        session.record_observed({"exit_code": 0, "output": "ok"})
        session.add_evidence("test", "tests/test_x.py::test_case",
                             verifier="self:cto")
        session.add_evidence("build", "build/output.log",
                             verifier="self:cto")
        assert session.can_emit_complete() is True

    def test_claim_without_evidence_denies_complete(self):
        """An agent claim of success WITHOUT evidence → no COMPLETE
        (AUTH-INV-15 / THREAT-016)."""
        session = VerificationSession("t-1", "code_change",
                                      expected={"exit_code": 0})
        # Agent reports success, observed outcome matches expected, but no
        # verification evidence was collected → cannot COMPLETE.
        session.record_agent_claim("SUCCEEDED")
        session.record_observed({"exit_code": 0, "output": "ok"})
        result = session.evaluate()
        assert result.verdict == "INSUFFICIENT"  # claim alone is not evidence
        assert session.can_emit_complete() is False

    def test_claim_without_evidence_denies(self):
        """Agent 'SUCCEEDED' claim with no observed outcome → UNVERIFIED."""
        result = evaluate_verification(
            action_category="code_change",
            expected_outcome={"exit_code": 0},
            observed_outcome=None,
            evidence=(),
            agent_claim="SUCCEEDED",
        )
        assert result.verdict == "UNVERIFIED"
        assert "claim is not verification" in result.reason

    def test_claim_without_evidence_observed_missing(self):
        """Agent claim 'SUCCEEDED' but observed outcome is empty → UNVERIFIED."""
        result = evaluate_verification(
            action_category="code_change",
            expected_outcome={"exit_code": 0},
            observed_outcome={},
            evidence=(),
            agent_claim="SUCCEEDED",
        )
        assert result.verdict == "UNVERIFIED"

    def test_verification_gate_raises_on_unverified(self):
        """VerificationGate raises VerificationDenied when COMPLETE is not
        allowed (fail-closed)."""
        session = VerificationSession("t-1", "code_change",
                                      expected={"exit_code": 0})
        session.record_observed({"exit_code": 0, "output": "ok"})
        # No evidence at all → cannot complete
        gate = VerificationGate()
        with pytest.raises(VerificationDenied, match="COMPLETE refused"):
            gate.evaluate(session)

    def test_verification_gate_passes_verified(self):
        """VerificationGate passes when the session is verified."""
        session = VerificationSession("t-1", "code_change",
                                      expected={"exit_code": 0})
        session.record_observed({"exit_code": 0})
        session.add_evidence("test", "tests/test_x.py",
                             verifier="self:cto")
        session.add_evidence("build", "build/output.log",
                             verifier="self:cto")
        gate = VerificationGate()
        result = gate.evaluate(session)
        assert result.verdict == "PASSED"

    def test_false_success_report_observed_mismatch(self):
        """Agent reports success but observed outcome differs from expected
        → FAILED (VERIFY-002 → recovery)."""
        session = VerificationSession("t-1", "code_change",
                                      expected={"exit_code": 0})
        session.record_agent_claim("SUCCEEDED")
        session.record_observed({"exit_code": 1, "output": "error"})
        result = session.evaluate()
        assert result.verdict == "FAILED"
        assert "recovery path" in result.reason
        assert session.can_emit_complete() is False


# ===========================================================================
# VERIFY-001 — false success report
# ===========================================================================

class TestVerify001:
    """VERIFY-001: false success report → no COMPLETE."""

    def test_agent_claim_without_observed_denies_complete(self):
        """Agent claims success but actual outcome is missing → no COMPLETE."""
        result = evaluate_verification(
            action_category="internal_analysis",
            expected_outcome={"result": "ok"},
            observed_outcome=None,
            evidence=(),
            agent_claim="SUCCEEDED",
        )
        assert result.verdict == "UNVERIFIED"

    def test_observed_outcome_missing_denies_complete(self):
        """No observed outcome at all → no COMPLETE (nothing to verify)."""
        session = VerificationSession("t-1", "internal_analysis",
                                      expected={"result": "ok"})
        result = session.evaluate()
        assert result.verdict == "UNVERIFIED"
        assert session.can_emit_complete() is False

    def test_observed_outcome_empty_denies_complete(self):
        """Empty observed outcome → no COMPLETE (nothing verified)."""
        session = VerificationSession("t-1", "internal_analysis",
                                      expected={"result": "ok"})
        session.record_observed({})
        result = session.evaluate()
        assert result.verdict == "UNVERIFIED"
        assert session.can_emit_complete() is False


# ===========================================================================
# VERIFY-002 — expected vs actual mismatch
# ===========================================================================

class TestVerify002:
    """VERIFY-002: expected vs actual mismatch → FAIL → recovery path."""

    def test_expected_vs_actual_mismatch(self):
        """Expected outcome differs from observed → FAILED."""
        result = evaluate_verification(
            action_category="code_change",
            expected_outcome={"exit_code": 0, "file_count": 5},
            observed_outcome={"exit_code": 1, "file_count": 3},
            evidence=(VerificationEvidence("test", "tests/test_x.py"),),
        )
        assert result.verdict == "FAILED"

    def test_expected_property_missing_from_observed(self):
        """Expected property not present in observed → FAILED."""
        result = evaluate_verification(
            action_category="code_change",
            expected_outcome={"exit_code": 0, "created": True},
            observed_outcome={"exit_code": 0},
            evidence=(VerificationEvidence("test", "tests/test_x.py"),),
        )
        assert result.verdict == "FAILED"
        assert "missing" in result.reason

    def test_expected_vs_actual_match(self):
        """Expected matches observed → comparison passes."""
        result = evaluate_verification(
            action_category="internal_analysis",
            expected_outcome={"found": True, "confidence": "high"},
            observed_outcome={"found": True, "confidence": "high"},
        )
        assert result.verdict == "PASSED"


# ===========================================================================
# VERIFY-003 — incomplete verification evidence (HIGH action)
# ===========================================================================

class TestVerify003:
    """VERIFY-003: incomplete verification evidence → no COMPLETE."""

    def test_missing_evidence_for_code_change(self):
        """Code change requires test+build evidence; missing both → INSUFFICIENT."""
        session = VerificationSession("t-1", "code_change",
                                      expected={"exit_code": 0})
        session.record_observed({"exit_code": 0})
        # No evidence at all
        result = session.evaluate()
        assert result.verdict == "INSUFFICIENT"
        assert "missing" in result.reason

    def test_missing_one_evidence_kind(self):
        """Code change requires test AND build; missing build → INSUFFICIENT."""
        session = VerificationSession("t-1", "code_change",
                                      expected={"exit_code": 0})
        session.record_observed({"exit_code": 0})
        session.add_evidence("test", "tests/test_x.py",
                             verifier="self:cto")
        # build missing
        result = session.evaluate()
        assert result.verdict == "INSUFFICIENT"
        assert "build" in result.reason

    def test_independent_verification_required_for_production(self):
        """Production deploy requires independent verification; self-verify
        is insufficient."""
        evs = (
            VerificationEvidence("deployment_status", "deploy/report.json",
                                 verifier="self:orchestrator",
                                 independent=False),
            VerificationEvidence("runtime_health", "health/probe.json",
                                 verifier="self:orchestrator",
                                 independent=False),
        )
        result = evaluate_verification(
            action_category="production_deploy",
            expected_outcome={"status": "live"},
            observed_outcome={"status": "live"},
            evidence=evs,
        )
        assert result.verdict == "INSUFFICIENT"
        assert "INDEPENDENT" in result.reason

    def test_human_confirmation_required_for_financial(self):
        """Financial action requires independent verification + Human
        confirmation."""
        ev = VerificationEvidence("financial_result", "ledger/entry.json",
                                  verifier="independent:auditor",
                                  independent=True)
        result = evaluate_verification(
            action_category="financial",
            expected_outcome={"amount": 1000, "currency": "USD"},
            observed_outcome={"amount": 1000, "currency": "USD"},
            evidence=(ev,),
            human_confirmation=False,
        )
        assert result.verdict == "INSUFFICIENT"
        assert "Human confirmation" in result.reason

    def test_financial_with_human_confirmation_passes(self):
        """Financial action with independent verification + Human
        confirmation → PASSED."""
        ev = VerificationEvidence("financial_result", "ledger/entry.json",
                                  verifier="independent:auditor",
                                  independent=True)
        result = evaluate_verification(
            action_category="financial",
            expected_outcome={"amount": 1000, "currency": "USD"},
            observed_outcome={"amount": 1000, "currency": "USD"},
            evidence=(ev,),
            human_confirmation=True,
        )
        assert result.verdict == "PASSED"


# ===========================================================================
# Independence requirements per action category
# ===========================================================================

class TestIndependence:
    """Independence requirements per action category (§10 / §16.1)."""

    def test_internal_analysis_self_ok(self):
        """Internal analysis accepts self-verification."""
        result = evaluate_verification(
            action_category="internal_analysis",
            expected_outcome={"result": "ok"},
            observed_outcome={"result": "ok"},
        )
        assert result.verdict == "PASSED"

    def test_code_change_self_plus_test_build(self):
        """Code change (non-prod) requires self + test+build evidence."""
        session = VerificationSession("t-1", "code_change",
                                      expected={"exit_code": 0})
        session.record_observed({"exit_code": 0})
        session.add_evidence("test", "tests/test_x.py",
                             verifier="self:cto", independent=False)
        session.add_evidence("build", "build/output.log",
                             verifier="self:cto", independent=False)
        assert session.can_emit_complete() is True

    def test_production_deploy_requires_independent(self):
        """Production deploy requires independent verification (self fails)."""
        session = VerificationSession("t-1", "production_deploy",
                                      expected={"status": "live"})
        session.record_observed({"status": "live", "url": "https://example.com"})
        # Self-verification
        session.add_evidence("deployment_status", "deploy/report.json",
                             verifier="self:orchestrator", independent=False)
        assert session.can_emit_complete() is False

    def test_production_deploy_independent_passes(self):
        """Production deploy with independent verifier passes."""
        session = VerificationSession("t-1", "production_deploy",
                                      expected={"status": "live"})
        session.record_observed({"status": "live", "url": "https://example.com"})
        session.add_evidence("deployment_status", "deploy/report.json",
                             verifier="independent:ops", independent=True)
        session.add_evidence("runtime_health", "health/probe.json",
                             verifier="independent:ops", independent=True)
        assert session.can_emit_complete() is True

    def test_credential_change_requires_independent_and_human(self):
        """Credential change requires independent + Human confirmation."""
        session = VerificationSession("t-1", "credential_change",
                                      expected={"key": "rotated"})
        session.record_observed({"key": "rotated", "timestamp": "..."})
        session.add_evidence("audit_record", "audit/events.jsonl",
                             verifier="independent:security", independent=True,
                             human_confirmation=True)
        assert session.can_emit_complete() is True

    def test_material_publication_requires_independent_and_human(self):
        """Material publication requires independent + Human."""
        ev = VerificationEvidence("published_content", "pub/url",
                                  verifier="independent:editor",
                                  independent=True)
        result = evaluate_verification(
            action_category="material_publication",
            expected_outcome={"url": "https://example.com/post"},
            observed_outcome={"url": "https://example.com/post"},
            evidence=(ev,),
            human_confirmation=True,
        )
        assert result.verdict == "PASSED"

    def test_recovery_rollback_requires_independent_restoration(self):
        """Recovery/rollback requires independent restoration verification
        (REC-003)."""
        ev = VerificationEvidence("restoration_proof", "checksum/backup.txt",
                                  verifier="independent:ops", independent=True)
        result = evaluate_verification(
            action_category="recovery_rollback",
            expected_outcome={"restored": True, "checksum": "abc123"},
            observed_outcome={"restored": True, "checksum": "abc123"},
            evidence=(ev,),
        )
        assert result.verdict == "PASSED"

    def test_novel_writing_self_ok(self):
        """Novel writing accepts self-verification with continuity check."""
        session = VerificationSession("t-1", "novel_writing",
                                      expected={"chapter": 5, "word_count": 3000})
        session.record_observed({"chapter": 5, "word_count": 3000})
        session.add_evidence("continuity_check", "novel/continuity/v5.md",
                             verifier="self:nova", independent=False)
        assert session.can_emit_complete() is True


# ===========================================================================
# VerificationSession lifecycle
# ===========================================================================

class TestVerificationSessionLifecycle:
    """VerificationSession lifecycle: expected declared BEFORE execution."""

    def test_expected_declared_before_execution(self):
        """Expected outcome is set at construction (before execution)."""
        session = VerificationSession("t-1", "internal_analysis",
                                      expected={"result": "ok"})
        assert session.expected_outcome.task_id == "t-1"
        assert session.expected_outcome.expected == {"result": "ok"}
        # observed is None until record_observed is called
        result = session.evaluate()
        assert result.verdict == "UNVERIFIED"

    def test_observed_recorded_once(self):
        """record_observed can be called only once."""
        session = VerificationSession("t-1", "internal_analysis",
                                      expected={"result": "ok"})
        session.record_observed({"result": "ok"})
        with pytest.raises(VerificationError, match="already recorded"):
            session.record_observed({"result": "ok"})

    def test_expected_outcome_requires_non_empty_task_id(self):
        """ExpectedOutcome requires a non-empty task_id."""
        with pytest.raises(VerificationError, match="task_id"):
            ExpectedOutcome("", "internal_analysis")

    def test_unknown_category_fails_closed(self):
        """Unknown action category raises VerificationError at construction."""
        with pytest.raises(VerificationError, match="unknown"):
            VerificationSession("t-1", "unknown_category")

    def test_action_category_mapping(self):
        """Action class strings map to verification categories."""
        assert action_category("code_write") == "code_change"
        assert action_category("financial_transaction") == "financial"
        assert action_category("read") == "internal_analysis"
        assert action_category("rollback") == "recovery_rollback"
        assert action_category("unknown_action") == "unknown_action"

    def test_unknown_action_category_in_evaluate_fails_closed(self):
        """evaluate_verification with unknown action category raises
        VerificationError (fail-closed)."""
        with pytest.raises(VerificationError, match="unknown"):
            evaluate_verification(
                action_category="nonexistent",
                expected_outcome={"x": 1},
                observed_outcome={"x": 1},
            )


# ===========================================================================
# VerificationRequirement lookup
# ===========================================================================

class TestVerificationRequirements:
    """verification_requirements() returns the correct requirements."""

    def test_internal_analysis(self):
        reqs = verification_requirements("internal_analysis")
        assert reqs.independence == "self"
        assert reqs.required_evidence == ()
        assert reqs.human_confirmation is False

    def test_code_change(self):
        reqs = verification_requirements("code_change")
        assert reqs.independence == "self"
        assert "test" in reqs.required_evidence
        assert "build" in reqs.required_evidence

    def test_financial(self):
        reqs = verification_requirements("financial")
        assert reqs.independence == "independent"
        assert reqs.human_confirmation is True

    def test_recovery_rollback(self):
        reqs = verification_requirements("recovery_rollback")
        assert reqs.independence == "independent"
        assert "restoration_proof" in reqs.required_evidence

    def test_unknown_raises(self):
        with pytest.raises(VerificationError, match="unknown"):
            verification_requirements("nonexistent")


# ===========================================================================
# Evidence structure
# ===========================================================================

class TestEvidenceStructure:
    """VerificationEvidence is a data-only artifact, not a claim."""

    def test_evidence_has_kind_and_source(self):
        ev = VerificationEvidence("test", "tests/test_x.py",
                                  verifier="self:cto", independent=False)
        assert ev.kind == "test"
        assert ev.source == "tests/test_x.py"
        assert ev.verifier == "self:cto"
        assert ev.independent is False

    def test_evidence_can_be_independent(self):
        ev = VerificationEvidence("deployment_status", "deploy/report.json",
                                  verifier="independent:ops", independent=True)
        assert ev.independent is True

    def test_evidence_with_human_confirmation(self):
        ev = VerificationEvidence("financial_result", "ledger/entry.json",
                                  verifier="independent:auditor",
                                  independent=True,
                                  human_confirmation=True)
        assert ev.human_confirmation is True

    def test_session_builds_evidence(self):
        session = VerificationSession("t-1", "code_change",
                                      expected={"exit_code": 0})
        ev = session.add_evidence("test", "tests/test_x.py",
                                  verifier="self:cto")
        assert isinstance(ev, VerificationEvidence)
        assert ev.kind == "test"
        assert ev.verifier == "self:cto"