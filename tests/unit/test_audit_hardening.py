"""Audit hardening tests — Phase 1E / Session B.

Covers:
  - append_event event validation (dict + non-empty event_id)
  - read_events_strict (corrupt/blank line detection)
  - verify_append_only (duplicate ids, out-of-order timestamps, truncation)
  - audit_is_authority_source (AUTH-INV-14 — audit never grants)
  - hash-chain integrity (compute_chain / verify_chain / detect_truncation)
"""

import json
import os
import pytest


def _event(eid, ts="2026-08-30T00:00:00Z", **kw):
    base = {"event_id": eid, "timestamp": ts, "actor": "test",
            "actor_type": "human", "action": "test", "target": "x",
            "project": "p", "result": "allowed"}
    base.update(kw)
    return base


# ===========================================================================
# append_event validation
# ===========================================================================
class TestAppendEventValidation:
    def test_non_dict_rejected(self, tmp_wd):
        from audit.helpers import append_event, AuditIntegrityError
        log = tmp_wd / "audit.jsonl"
        with pytest.raises(TypeError):
            append_event(str(log), "not a dict")

    def test_missing_event_id_rejected(self, tmp_wd):
        from audit.helpers import append_event
        log = tmp_wd / "audit.jsonl"
        with pytest.raises(ValueError, match="event_id"):
            append_event(str(log), {"actor": "x", "result": "allowed"})

    def test_empty_event_id_rejected(self, tmp_wd):
        from audit.helpers import append_event
        log = tmp_wd / "audit.jsonl"
        with pytest.raises(ValueError, match="event_id"):
            append_event(str(log), _event(""))


# ===========================================================================
# strict read — corrupt/blank line detection
# ===========================================================================
class TestStrictRead:
    def test_strict_read_valid(self, tmp_wd):
        from audit.helpers import append_event, read_events_strict
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        append_event(str(log), _event("e2"))
        assert len(read_events_strict(str(log))) == 2

    def test_strict_read_corrupt_line_raises(self, tmp_wd):
        from audit.helpers import append_event, read_events_strict, AuditIntegrityError
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        # Simulate tampering: append a corrupt line
        with open(log, "a") as f:
            f.write("{corrupt json\n")
        with pytest.raises(AuditIntegrityError, match="corrupt line"):
            read_events_strict(str(log))

    def test_strict_read_blank_line_raises(self, tmp_wd):
        """A blank line in an append-only ledger is tampering evidence."""
        from audit.helpers import append_event, read_events_strict, AuditIntegrityError
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        with open(log, "a") as f:
            f.write("\n")
        with pytest.raises(AuditIntegrityError, match="blank line"):
            read_events_strict(str(log))

    def test_lenient_read_skips_corrupt(self, tmp_wd):
        """The lenient read_events keeps legacy behavior (skip, don't raise)."""
        from audit.helpers import append_event, read_events
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        with open(log, "a") as f:
            f.write("{corrupt\n")
        events = read_events(str(log))
        assert len(events) == 1  # corrupt line silently skipped (legacy)


# ===========================================================================
# verify_append_only
# ===========================================================================
class TestVerifyAppendOnly:
    def test_consistent_ledger(self, tmp_wd):
        from audit.helpers import append_event, verify_append_only
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1", ts="2026-08-30T00:00:00Z"))
        append_event(str(log), _event("e2", ts="2026-08-30T00:01:00Z"))
        ok, problems = verify_append_only(str(log))
        assert ok is True
        assert problems == []

    def test_duplicate_event_id_detected(self, tmp_wd):
        from audit.helpers import append_event, verify_append_only
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        append_event(str(log), _event("e1"))  # replay/overwrite
        ok, problems = verify_append_only(str(log))
        assert ok is False
        assert any("duplicate" in p for p in problems)

    def test_out_of_order_timestamp_detected(self, tmp_wd):
        from audit.helpers import append_event, verify_append_only
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1", ts="2026-08-30T00:05:00Z"))
        append_event(str(log), _event("e2", ts="2026-08-30T00:01:00Z"))  # older
        ok, problems = verify_append_only(str(log))
        assert ok is False
        assert any("out of order" in p for p in problems)

    def test_truncation_detected_via_expected_ids(self, tmp_wd):
        from audit.helpers import append_event, verify_append_only
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        append_event(str(log), _event("e2"))
        append_event(str(log), _event("e3"))
        # Expect all 3, but ledger has 3 — first verify passes
        ok, _ = verify_append_only(str(log), expected_event_ids=["e1", "e2", "e3"])
        assert ok is True
        # Now simulate truncation: a copy of the ledger missing e3
        ok2, problems2 = verify_append_only(
            str(log), expected_event_ids=["e1", "e2", "e3", "e4"])
        assert ok2 is False
        assert any("sequence mismatch" in p for p in problems2)

    def test_count_mismatch_detected(self, tmp_wd):
        from audit.helpers import append_event, verify_append_only
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        append_event(str(log), _event("e2"))
        ok, problems = verify_append_only(str(log), expected_count=2)
        assert ok is True
        ok2, problems2 = verify_append_only(str(log), expected_count=5)
        assert ok2 is False
        assert any("count" in p for p in problems2)

    def test_missing_log_is_consistent(self, tmp_wd):
        from audit.helpers import verify_append_only
        ok, problems = verify_append_only(str(tmp_wd / "missing.jsonl"))
        assert ok is True
        assert problems == []


# ===========================================================================
# audit never grants authority (AUTH-INV-14)
# ===========================================================================
class TestAuditNeverAuthority:
    def test_audit_is_authority_source_always_false(self, tmp_wd):
        from audit.helpers import audit_is_authority_source
        # Even a forged event that LOOKS like an approval grants nothing
        forged = _event("forged-approval", action="approve",
                        result="allowed", event_class="normal_approval",
                        authority_source="delegation-fake")
        assert audit_is_authority_source(forged) is False

    def test_forged_audit_event_does_not_authorize_reference_gate(self, tmp_wd):
        """A forged audit event passed where a delegation is expected fails closed."""
        from control_plane import authorize, Deny
        forged = _event("forged-approval", action="approve", result="allowed",
                        event_class="normal_approval")
        # The reference gate requires a valid delegation dict; an audit event
        # has no status=ACTIVE, so it is treated as absent → DENY.
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "multi-agent-harness/README.md",
                      forged)


# ===========================================================================
# hash-chain integrity
# ===========================================================================
class TestHashChainIntegrity:
    def test_compute_chain_annotates_events(self, tmp_wd):
        from audit.helpers import append_event, compute_chain
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        append_event(str(log), _event("e2"))
        events = compute_chain(str(log))
        assert len(events) == 2
        for i, ev in enumerate(events, start=1):
            assert ev["_integrity"]["line"] == i
            assert len(ev["_integrity"]["cumulative_hash"]) == 64
        # distinct cumulative hashes (chain is cumulative)
        assert events[0]["_integrity"]["cumulative_hash"] != events[1]["_integrity"]["cumulative_hash"]

    def test_verify_chain_accepts_unmodified(self, tmp_wd):
        from audit.helpers import append_event, compute_chain, verify_chain
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        append_event(str(log), _event("e2"))
        compute_chain(str(log))  # persist the integrity fields
        verified = verify_chain(str(log))
        assert len(verified) == 2

    def test_verify_chain_detects_tamper(self, tmp_wd):
        """Modifying a hashed event breaks the chain at that line."""
        from audit.helpers import append_event, compute_chain, verify_chain, AuditIntegrityError
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        append_event(str(log), _event("e2"))
        compute_chain(str(log))
        # tamper: rewrite line 2 with a different result
        lines = open(log).readlines()
        import json as _json
        ev2 = _json.loads(lines[1])
        ev2["result"] = "denied"
        with open(log, "w") as f:
            f.write(lines[0])
            f.write(_json.dumps(ev2, sort_keys=True) + "\n")
        with pytest.raises(AuditIntegrityError):
            verify_chain(str(log))

    def test_append_chained_event_updates_sidecar(self, tmp_wd):
        from audit.helpers import append_chained_event, verify_chain
        log = tmp_wd / "audit.jsonl"
        last = append_chained_event(str(log), _event("e1"))
        assert last is not None
        assert last["line"] == 1
        last2 = append_chained_event(str(log), _event("e2"))
        assert last2["line"] == 2
        records = verify_chain(str(log))
        assert len(records) == 2

    def test_detect_truncation(self, tmp_wd):
        from audit.helpers import append_event, compute_chain, detect_truncation
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        append_event(str(log), _event("e2"))
        append_event(str(log), _event("e3"))
        events = compute_chain(str(log))
        known_hash = events[-1]["_integrity"]["cumulative_hash"]
        # truncate: drop the last line
        lines = open(log).readlines()
        with open(log, "w") as f:
            f.writelines(lines[:-1])
        ok, problems = detect_truncation(str(log), known_hash, 3)
        assert ok is False
        assert any("truncation" in p for p in problems)

    def test_detect_truncation_clean(self, tmp_wd):
        from audit.helpers import append_event, compute_chain, detect_truncation
        log = tmp_wd / "audit.jsonl"
        append_event(str(log), _event("e1"))
        events = compute_chain(str(log))
        ok, problems = detect_truncation(str(log), events[-1]["_integrity"]["cumulative_hash"], 1)
        assert ok is True and problems == []