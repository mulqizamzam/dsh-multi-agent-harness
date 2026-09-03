# INT-08 — State / version conflict
#
# Proves that two parallel workers using the same state version cause the
# second to be DENIED (CAS/stale-version detection).
#
# Modules integrated: StateMachine (expected_version) + ProjectState
# (expected_project_version) + compare_and_swap
# Invariants: THREAT-021, ST-002, PST-001/002

import pytest

from orchestrator.foundation import StateTransitionError
from state.helpers import compare_and_swap


class TestINT08StateVersionConflict:
    def test_second_writer_stale_project_version_denied(self, harness):
        """Two parallel workers; the second using a stale version is DENIED."""
        h = harness
        d = h.build_delegation()
        # Worker A: version 1 -> transitions -> version 2
        h.transition("int-08", "PLANNED", authority=d)           # v2
        h.transition("int-08", "DELEGATED", authority=d)         # v3
        v_after_a = h.project_version()
        assert v_after_a == 3

        # Worker B read version 1 before A wrote; tries to write with
        # expected_project_version=1 -> stale -> StateTransitionError
        with pytest.raises(StateTransitionError, match="stale"):
            h.transition("int-08", "EXECUTING", authority=d,
                         expected_project_version=1)
        # B's change did not happen
        assert h.machine("int-08").current() == "DELEGATED"
        assert h.project_version() == v_after_a

    def test_stale_machine_version_denied(self, harness):
        """A stale expected_version on a single StateMachine is refused."""
        h = harness
        d = h.build_delegation()
        m = h.machine("int-08b")
        m.transition("PLANNED", authority=d)  # version 2
        with pytest.raises(StateTransitionError, match="stale"):
            m.transition("DELEGATED", authority=d, expected_version=1)
        assert m.current_version() == 2

    def test_compare_and_swap_denies_stale_version(self, harness, tmp_path):
        """The CAS primitive refuses a write based on a stale version."""
        import os
        path = str(tmp_path / "state.json")
        from state.helpers import atomic_write
        atomic_write(path, {"version": 1, "data": "a"})
        ok, cur = compare_and_swap(path, 1, {"version": 2, "data": "b"})
        assert ok is True and cur == 2
        # Second writer with stale expectation
        ok2, cur2 = compare_and_swap(path, 1, {"version": 2, "data": "c"})
        assert ok2 is False and cur2 == 2

    def test_version_conflict_audited(self, harness):
        """A version conflict produces an audit event."""
        h = harness
        h.append_audit({
            "event_id": "ev-version-001", "timestamp": "2026-08-30T00:00:00Z",
            "event_class": "version_conflict", "actor": "worker-b",
            "action": "transition", "target": "int-08",
            "project": "multi-agent-harness", "result": "denied",
            "error": "stale project version (THREAT-021)",
        })
        conflicts = [e for e in h.audit_events()
                     if e.get("event_class") == "version_conflict"]
        assert len(conflicts) == 1