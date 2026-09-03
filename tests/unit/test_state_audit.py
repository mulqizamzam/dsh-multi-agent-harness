"""State/audit integrity helper tests — atomic_write, version_check, append_log.

Covers the Phase-1B surface (atomic write / CAS / version staleness / append)
plus the hardened assertions that are NOT duplicated in the Session B files.
Session B canonical homes:
  - tests/unit/test_state_hardening.py  — StatePathError guard, MAX_DOC_BYTES,
    strict-monotonic CAS, is_stale / assert_current_version, StateMachine
    version-aware transitions, ProjectState CAS
  - tests/unit/test_recovery.py         — recovery record machine (REC-*,
    AUTH-INV-12/16, THREAT-022)
  - tests/unit/test_audit_hardening.py  — audit integrity chain, strict read,
    verify_append_only, append-event validation, audit-is-not-authority
"""

import json
import os
import pytest


class TestAtomicWrite:
    """tests/state/helpers/atomic_write.py"""

    def test_atomic_write_and_read(self, tmp_wd):
        from state.helpers import atomic_write, safe_read
        path = tmp_wd / "state.json"
        data = {"key": "value", "version": 1}
        atomic_write(str(path), data)
        assert path.exists()
        read = safe_read(str(path))
        assert read == data

    def test_safe_read_missing(self, tmp_wd):
        from state.helpers import safe_read
        assert safe_read(str(tmp_wd / "nonexistent.json")) is None

    def test_safe_read_corrupt(self, tmp_wd):
        path = tmp_wd / "corrupt.json"
        with open(path, "w") as f:
            f.write("{bad json")
        from state.helpers import safe_read
        assert safe_read(str(path)) is None

    def test_atomic_write_creates_dir(self, tmp_wd):
        from state.helpers import atomic_write
        nested = tmp_wd / "a" / "b" / "state.json"
        atomic_write(str(nested), {"v": 1})
        assert nested.exists()

    def test_compare_and_swap_success(self, tmp_wd):
        from state.helpers import atomic_write
        from state.helpers.atomic_write import compare_and_swap
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 1, "data": "old"})
        ok, new_v = compare_and_swap(str(path), 1, {"version": 2, "data": "new"}, "version")
        assert ok is True
        assert new_v == 2

    def test_compare_and_swap_version_mismatch(self, tmp_wd):
        from state.helpers.atomic_write import compare_and_swap, atomic_write
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 5, "data": "current"})
        ok, cur_v = compare_and_swap(str(path), 3, {"version": 6, "data": "stale"}, "version")
        assert ok is False
        assert cur_v == 5

    def test_concurrent_write_detection(self, tmp_wd):
        """Simulate two concurrent writers; second should fail CAS."""
        from state.helpers.atomic_write import atomic_write, compare_and_swap
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 1, "data": "initial"})
        ok1, _ = compare_and_swap(str(path), 1, {"version": 2, "data": "writer1"}, "version")
        ok2, cur = compare_and_swap(str(path), 1, {"version": 2, "data": "writer2"}, "version")
        assert ok1 is True
        assert ok2 is False
        assert cur == 2

    # -- Phase 1E hardening: StatePathError guard ---------------------------
    # (nul-byte, non-serializable, size-cap, oversized-read and strict-monotonic
    #  CAS hardening are covered by tests/unit/test_state_hardening.py — Session B.)
    def test_atomic_write_denies_malformed_path(self, tmp_wd):
        from state.helpers.atomic_write import atomic_write, StatePathError
        for bad in (None, "", "   ", 42, ["x"]):
            with pytest.raises(StatePathError):
                atomic_write(bad, {"v": 1})

    def test_atomic_write_denies_symlink_escape(self, tmp_wd):
        """A symlink inside the workspace pointing outside must be refused."""
        from state.helpers.atomic_write import atomic_write, StatePathError
        outside = tmp_wd.parent / "outside-target.json"
        sub = tmp_wd / "sub"
        sub.mkdir()
        link = sub / "link.json"
        os.symlink(str(outside), str(link))
        with pytest.raises(StatePathError):
            atomic_write(str(link), {"v": 1})
        assert not outside.exists()

class TestVersionCheck:
    """tests/state/helpers/version_check.py"""

    def test_read_version(self, tmp_wd):
        from state.helpers.atomic_write import atomic_write
        from state.helpers import read_version
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 7})
        assert read_version(str(path)) == 7

    def test_read_version_missing(self, tmp_wd):
        from state.helpers import read_version
        assert read_version(str(tmp_wd / "missing.json")) == 0

    def test_bump_version(self):
        from state.helpers import bump_version
        d = {"version": 3}
        assert bump_version(d) == 4
        assert d["version"] == 4

    def test_validate_version_staleness(self, tmp_wd):
        from state.helpers.atomic_write import atomic_write
        from state.helpers import validate_version_staleness
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 1})
        assert validate_version_staleness(str(path), 1) is True
        assert validate_version_staleness(str(path), 0) is False

    def test_validate_version_staleness_missing(self, tmp_wd):
        from state.helpers import validate_version_staleness
        # missing file → version 0 → expected 0 → True (coincidence)
        assert validate_version_staleness(str(tmp_wd / "missing.json"), 0) is True

    # -- Phase 1E hardening: monotonicity / diagnosable staleness ------------
    # (validate_version_monotonic ok/skip, is_stale current/newer/older/missing,
    #  assert_current_version ok/stale-raises are covered by
    #  tests/unit/test_state_hardening.py — Session B.)
    def test_validate_version_monotonic_rejects_non_int(self):
        from state.helpers import validate_version_monotonic
        with pytest.raises(ValueError):
            validate_version_monotonic("1", 2)
        with pytest.raises(ValueError):
            validate_version_monotonic(1, "2")

    def test_assert_current_version_missing_raises(self, tmp_wd):
        from state.helpers import assert_current_version, StaleStateError
        with pytest.raises(StaleStateError):
            assert_current_version(str(tmp_wd / "missing.json"), 1)


class TestRecovery:
    """tests/state/helpers/recovery.py — unique assertions not covered by
    tests/unit/test_recovery.py (Session B, which is the canonical home for
    recovery tests)."""

    def test_recovery_invalid_transition_fails_closed(self):
        from state.helpers import begin_recovery, RecoveryError
        rec = begin_recovery("t-1", preserved_version=1)
        with pytest.raises(RecoveryError):
            rec.complete()  # cannot complete from PRESERVED

    def test_recovery_record_invalid_state_denied(self):
        from state.helpers import RecoveryRecord, RecoveryError
        with pytest.raises(RecoveryError):
            RecoveryRecord(task_id="t", state="HACKED")


class TestAppendLog:
    """tests/audit/helpers/append_log.py"""

    def test_append_and_read(self, tmp_wd):
        from audit.helpers import append_event, read_events
        log = tmp_wd / "audit.jsonl"
        e1 = {"event_id": "e1", "timestamp": "2026-08-29T00:00:00Z", "actor": "test",
              "actor_type": "human", "action": "test", "target": "x", "project": "p",
              "result": "allowed"}
        e2 = {**e1, "event_id": "e2", "result": "denied"}
        append_event(str(log), e1)
        append_event(str(log), e2)
        events = read_events(str(log))
        assert len(events) == 2
        assert events[0]["event_id"] == "e1"
        assert events[1]["event_id"] == "e2"

    def test_append_is_append_only(self, tmp_wd):
        from audit.helpers import append_event, read_events
        log = tmp_wd / "audit.jsonl"
        e1 = {"event_id": "e1", "timestamp": "2026-08-29T00:00:00Z", "actor": "test",
              "actor_type": "human", "action": "test", "target": "x", "project": "p",
              "result": "allowed"}
        append_event(str(log), e1)
        # Simulate a second write that should NOT overwrite
        e2 = {**e1, "event_id": "e2", "result": "denied"}
        append_event(str(log), e2)
        events = read_events(str(log))
        assert len(events) == 2  # append, not overwrite — both events present

    def test_read_events_missing(self, tmp_wd):
        from audit.helpers import read_events
        assert read_events(str(tmp_wd / "nonexistent.jsonl")) == []

    def test_read_events_by_class(self, tmp_wd):
        from audit.helpers import append_event, read_events_by_class
        log = tmp_wd / "audit.jsonl"
        base = {"event_id": "e1", "timestamp": "2026-08-29T00:00:00Z", "actor": "test",
                "actor_type": "human", "action": "test", "target": "x", "project": "p", "result": "allowed"}
        append_event(str(log), {**base, "event_class": "execution_success"})
        append_event(str(log), {**base, "event_class": "execution_denial"})
        assert len(read_events_by_class(str(log), "execution_success")) == 1
        assert len(read_events_by_class(str(log), "execution_denial")) == 1
        assert len(read_events_by_class(str(log), "human_override")) == 0

    # -- Phase 1E hardening: strict read / append-only / integrity ----------
    # (strict-read corrupt/blank, verify_append_only duplicate/truncation/
    #  out-of-order/clean, audit-is-not-authority, append-event validation and
    #  the full hash-chain TestAuditIntegrity class are covered canonically by
    #  tests/unit/test_audit_hardening.py — Session B.)