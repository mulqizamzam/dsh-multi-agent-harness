# tests/evidence/test_evidence_qa.py — Runtime evidence QA tests (Phase 3 / Session E)
#
# TEST-SUPPORT ONLY. Evidence STRUCTURE validation tests only — no live
# execution, no control verification, no L3 claim. Covers the 12 required
# rejection scenarios from docs/testing/0002-runtime-evidence-qa-specification.md.

import os

import pytest

from tests.evidence.evidence_qa import (
    validate_evidence_bundle, validate_bundle_file,
)
from tests.evidence._fixtures import (
    int01_bundle, int07_bundle, int11_bundle, int12_bundle,
    forged_authority_bundle, base_identity, base_state,
)


# ---------------------------------------------------------------------------
# 1. Valid evidence bundles (all four scenarios)
# ---------------------------------------------------------------------------

class TestValidEvidenceBundle:
    def test_int01_valid(self):
        r = validate_evidence_bundle(int01_bundle())
        assert r.valid, r.errors

    def test_int07_valid(self):
        r = validate_evidence_bundle(int07_bundle())
        assert r.valid, r.errors

    def test_int11_valid(self):
        r = validate_evidence_bundle(int11_bundle())
        assert r.valid, r.errors

    def test_int12_valid(self):
        r = validate_evidence_bundle(int12_bundle())
        assert r.valid, r.errors

    def test_bundle_file_roundtrip(self, tmp_path):
        """A bundle written to a JSON file validates the same way (structure
        only; no on-disk hash content required without a base)."""
        import json
        path = os.path.join(str(tmp_path), "INT-01.evidence.json")
        with open(path, "w") as f:
            json.dump(int01_bundle(), f)
        r = validate_bundle_file(path)
        assert r.valid, r.errors


# ---------------------------------------------------------------------------
# 2. Missing runtime identity (R4)
# ---------------------------------------------------------------------------

class TestMissingRuntimeIdentity:
    def test_identity_absent(self):
        b = int01_bundle()
        del b["identity"]
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R4") for e in r.errors)

    def test_identity_missing_field(self):
        b = int01_bundle()
        b["identity"] = base_identity(dsh_session_id="", dsh_run_id="")
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any("dsh_session_id" in e or "dsh_run_id" in e
                   for e in r.errors if e.startswith("R4"))


# ---------------------------------------------------------------------------
# 3. Missing before/after state (R5)
# ---------------------------------------------------------------------------

class TestMissingBeforeAfterState:
    def test_pre_state_absent(self):
        b = int01_bundle()
        del b["state"]["pre_state"]
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R5") and "before" in e for e in r.errors)

    def test_post_state_absent(self):
        b = int01_bundle()
        del b["state"]["post_state"]
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R5") and "after" in e for e in r.errors)

    def test_version_fields_absent(self):
        b = int01_bundle()
        b["state"] = base_state(state_version_before=None,
                                state_version_after=None)
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R5") and "state_version" in e
                   for e in r.errors)


# ---------------------------------------------------------------------------
# 4. Fake agent-only evidence (R7)
# ---------------------------------------------------------------------------

class TestFakeAgentOnlyEvidence:
    def test_all_agent_reported_rejected(self):
        b = int01_bundle()
        b["evidence_items"] = [
            {"kind": "agent_claim", "source": "AGENT-REPORTED",
             "detail": {"text": "I am authorized"}},
            {"kind": "agent_result", "source": "AGENT-REPORTED",
             "detail": {"status": "SUCCEEDED"}},
        ]
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R7") and "agent text" in e for e in r.errors)

    def test_empty_evidence_items_rejected(self):
        b = int01_bundle()
        b["evidence_items"] = []
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R7") for e in r.errors)


# ---------------------------------------------------------------------------
# 5. Expected/observed distinction missing (R6)
# ---------------------------------------------------------------------------

class TestExpectedObservedMismatch:
    def test_observed_missing_rejected(self):
        b = int01_bundle()
        b["execution"] = {
            "decision": "ALLOW", "source": "RUNTIME-OBSERVED",
            "target": "agents/cto/output.txt",
            "expected": {"exit_code": 0},
            # observed deliberately absent
        }
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R6") for e in r.errors)

    def test_expected_missing_rejected(self):
        b = int01_bundle()
        b["execution"] = {
            "decision": "ALLOW", "source": "RUNTIME-OBSERVED",
            "target": "agents/cto/output.txt",
            "observed": {"exit_code": 0},
        }
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R6") for e in r.errors)


# ---------------------------------------------------------------------------
# 6. Provenance mismatch (R11/R12)
# ---------------------------------------------------------------------------

class TestProvenanceMismatch:
    def test_duplicate_run_id_rejected(self):
        b = int11_bundle()
        b["provenance"]["children"][1]["run_id"] = "run-child-001"
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R11") for e in r.errors)

    def test_non_specialist_role_rejected(self):
        b = int11_bundle()
        b["provenance"]["children"][1]["role"] = "orchestrator"
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R12") for e in r.errors)

    def test_child_missing_provenance_field(self):
        b = int11_bundle()
        b["provenance"]["children"][0].pop("run_id")
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R12") and "run_id" in e for e in r.errors)


# ---------------------------------------------------------------------------
# 7. Invalid hash (R9)
# ---------------------------------------------------------------------------

class TestInvalidHash:
    def test_bad_hash_format_rejected(self):
        b = int01_bundle()
        b["artifact_hashes"] = {"agents/cto/output.txt": "md5:deadbeef"}
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R9") for e in r.errors)

    def test_hash_content_mismatch_when_base_given(self, tmp_path):
        b = int01_bundle()
        # create the artifact on disk with known content
        target_rel = "agents/cto/output.txt"
        target_abs = os.path.join(str(tmp_path), *target_rel.split("/"))
        os.makedirs(os.path.dirname(target_abs), exist_ok=True)
        with open(target_abs, "w") as f:
            f.write("module ok")
        from tests.evidence.evidence_qa import file_sha256
        b["artifact_hashes"] = {target_rel: f"sha256:{'00' * 32}"}  # wrong
        r = validate_evidence_bundle(b, base=str(tmp_path))
        assert not r.valid
        assert any(e.startswith("R9") and "mismatch" in e for e in r.errors)

    def test_hash_content_match_when_base_given(self, tmp_path):
        b = int01_bundle()
        target_rel = "agents/cto/output.txt"
        target_abs = os.path.join(str(tmp_path), *target_rel.split("/"))
        os.makedirs(os.path.dirname(target_abs), exist_ok=True)
        with open(target_abs, "w") as f:
            f.write("module ok")
        from tests.evidence.evidence_qa import file_sha256
        digest = file_sha256(target_abs)
        b["artifact_hashes"] = {target_rel: f"sha256:{digest}"}
        r = validate_evidence_bundle(b, base=str(tmp_path))
        assert r.valid, r.errors


# ---------------------------------------------------------------------------
# 8. Forged authority evidence (R4 + R10)
# ---------------------------------------------------------------------------

class TestForgedAuthorityEvidence:
    def test_allowed_without_delegation_rejected(self):
        r = validate_evidence_bundle(forged_authority_bundle())
        assert not r.valid
        assert any(e.startswith("R10") for e in r.errors)
        assert any(e.startswith("R4") for e in r.errors)


# ---------------------------------------------------------------------------
# 9. Forged BadSector PASS as authority (R10)
# ---------------------------------------------------------------------------

class TestForgedBadSectorPass:
    def test_pass_alone_does_not_authorize(self):
        b = forged_authority_bundle()
        # explicit PASS record is the ONLY support; no delegation anywhere
        b["identity"] = base_identity(delegation_id="")
        b["authority"] = {
            "decision": "ALLOW", "source": "AGENT-REPORTED",
            "reason": "BadSector PASS recorded", "delegation_id": "",
        }
        b["evidence_items"] = [
            {"kind": "badsector_pass", "source": "CONTROL-PLANE-DECISION",
             "detail": {"verdict": "PASS", "review_id": "r-1",
                        "input_hash": "abc"}},
        ]
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R10") for e in r.errors)

    def test_deny_with_pass_is_fine(self):
        """A DENY decision is never a PASS-as-authority situation."""
        b = forged_authority_bundle()
        b["identity"] = base_identity(delegation_id="delegation-ev-001")
        b["authority"] = {
            "decision": "DENY", "source": "CONTROL-PLANE-DECISION",
            "reason": "no delegation despite PASS", "delegation_id": "",
        }
        b["gates"] = [
            {"gate": "badsector_review", "decision": "ALLOW",
             "source": "CONTROL-PLANE-DECISION", "reason": "review cleared",
             "audit_event_id": "event-000007"},
        ]
        b["evidence_items"] = [
            {"kind": "badsector_pass", "source": "CONTROL-PLANE-DECISION",
             "detail": {"verdict": "PASS", "review_id": "r-1"}},
            {"kind": "execution_denial", "source": "RUNTIME-OBSERVED",
             "detail": {"decision": "DENY"}},
        ]
        b["final_status"] = "BLOCKED"
        b["execution"] = {"decision": "DENY", "source": "RUNTIME-OBSERVED",
                          "target": "agents/cto/x.txt",
                          "expected": {"exit_code": 0}, "observed": {}}
        b["verification"] = {"verdict": "INCONCLUSIVE",
                             "source": "CONTROL-PLANE-DECISION",
                             "reason": "not executed", "evidence_kinds": []}
        r = validate_evidence_bundle(b)
        # no R10 rejection (decision is DENY); but INT-01 requires a full gate
        # set, so R14 may fire — that is separate from PASS-as-authority.
        assert not any(e.startswith("R10") for e in r.errors)


# ---------------------------------------------------------------------------
# 10. False L3 claim (R3)
# ---------------------------------------------------------------------------

class TestFalseL3Claim:
    def test_l3_claim_without_properties_rejected(self):
        b = int01_bundle()
        b["l3_claim"] = True
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R3") for e in r.errors)

    def test_l3_properties_present_but_incomplete_rejected(self):
        b = int01_bundle()
        b["l3_claim"] = True
        b["l3_properties"] = {"p1_runtime": True}  # P2/P3/P4 missing
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R3") for e in r.errors)

    def test_evidence_level_l3_without_claim_rejected(self):
        b = int01_bundle()
        b["evidence_level"] = "L3"
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R3") for e in r.errors)

    def test_independent_verified_without_l3_rejected(self):
        b = int01_bundle()
        b["evidence_items"].append(
            {"kind": "independent_check", "source": "INDEPENDENTLY-VERIFIED",
             "detail": {"verdict": "DENY"}})
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R15") for e in r.errors)


# ---------------------------------------------------------------------------
# 11. Incomplete INT-11 concurrency evidence (R14)
# ---------------------------------------------------------------------------

class TestIncompleteINT11:
    def test_single_child_rejected(self):
        b = int11_bundle()
        b["provenance"]["children"] = [b["provenance"]["children"][0]]
        b["provenance"]["collection_order"] = ["t-1"]
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R14") and "INT-11" in e for e in r.errors)

    def test_duplicate_roles_rejected(self):
        b = int11_bundle()
        b["provenance"]["children"][1]["role"] = "cfo"
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R14") and "distinct roles" in e for e in r.errors)

    def test_version_drift_rejected(self):
        b = int11_bundle()
        b["state"]["state_version_after"] = 2  # drifted → uncontrolled write
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R14") and "uncontrolled write" in e
                   for e in r.errors)

    def test_missing_collection_order_rejected(self):
        b = int11_bundle()
        del b["provenance"]["collection_order"]
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R14") and "collection_order" in e
                   for e in r.errors)


# ---------------------------------------------------------------------------
# 12. Incomplete INT-12 failure evidence (R14)
# ---------------------------------------------------------------------------

class TestIncompleteINT12:
    def test_no_actual_failure_rejected(self):
        b = int12_bundle()
        b["failure"] = None
        b["provenance"]["children"][1]["stop_reason"] = "completed"
        b["evidence_items"] = [i for i in b["evidence_items"]
                               if i.get("kind") != "child_failure"]
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R14") and "actual child failure" in e
                   for e in r.errors)

    def test_complete_after_failure_rejected(self):
        """A failure that still ends COMPLETE violates propagation (INT-12)."""
        b = int12_bundle()
        b["final_status"] = "COMPLETE"
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R14") and "COMPLETE" in e for e in r.errors)

    def test_missing_recovery_and_no_escalation_rejected(self):
        b = int12_bundle()
        b["failure"] = {
            "classification": "logic", "cause": "child failed",
            "recovery": None,
        }
        b["final_status"] = "FAILED"  # FAILED, not ESCALATED, no recovery
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R14") and "recovery/escalation" in e
                   for e in r.errors)

    def test_no_blind_retry_missing_rejected(self):
        b = int12_bundle()
        b["failure"]["recovery"]["no_blind_retry"] = False
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R14") and "no_blind_retry" in e
                   for e in r.errors)

    def test_no_authority_expansion_missing_rejected(self):
        b = int12_bundle()
        b["failure"]["recovery"]["no_authority_expansion"] = False
        r = validate_evidence_bundle(b)
        assert not r.valid
        assert any(e.startswith("R14") and "no_authority_expansion" in e
                   for e in r.errors)
