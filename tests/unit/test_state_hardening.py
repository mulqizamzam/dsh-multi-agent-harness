"""State hardening tests — Phase 1E / Session B.

Covers:
  - atomic_write path traversal guard / JSON pre-check / size cap
  - compare_and_swap strict monotonic enforcement
  - safe_read oversized document handling
  - version_check validate_version_monotonic / is_stale / assert_current_version
  - StateMachine model-text authority rejection (AUTH-INV-01)
  - StateMachine version-aware transitions (THREAT-021/022)
  - ProjectState version CAS
"""

import json
import os
import pytest


# ===========================================================================
# Atomic write hardening
# ===========================================================================
class TestAtomicWriteHardening:
    """Phase 1E hardening: path guard, JSON pre-check, size cap, monotonic CAS."""

    def test_path_traversal_rejected(self, tmp_wd):
        """atomic_write must reject targets that escape the base directory."""
        from state.helpers import atomic_write, StatePathError
        escape = os.path.join(tmp_wd, "..", "outside.json")
        with pytest.raises(StatePathError):
            atomic_write(escape, {"v": 1}, base=str(tmp_wd))

    def test_absolute_path_outside_base_rejected(self, tmp_wd):
        """An absolute path that resolves outside the guard base is rejected."""
        from state.helpers import atomic_write, StatePathError
        # /etc/passwd is outside any reasonable workspace
        with pytest.raises(StatePathError):
            atomic_write("/etc/passwd", {"v": 1}, base=str(tmp_wd))

    def test_nul_byte_path_rejected(self, tmp_wd):
        from state.helpers import atomic_write, StatePathError
        with pytest.raises(StatePathError):
            atomic_write("valid\x00invalid", {"v": 1})

    def test_non_serializable_data_rejected(self, tmp_wd):
        """atomic_write must reject non-JSON-serializable data before writing."""
        from state.helpers import atomic_write
        path = tmp_wd / "state.json"

        class NotSerializable:
            pass

        with pytest.raises(TypeError):
            atomic_write(str(path), {"bad": NotSerializable()})
        # No partial file should exist
        assert not path.exists()

    def test_oversized_document_rejected(self, tmp_wd):
        """atomic_write must reject data whose serialized form exceeds MAX_DOC_BYTES."""
        from state.helpers import atomic_write, MAX_DOC_BYTES
        path = tmp_wd / "big.json"
        big = {"data": "x" * (MAX_DOC_BYTES * 2)}
        with pytest.raises(ValueError, match="exceeds MAX_DOC_BYTES"):
            atomic_write(str(path), big)

    def test_oversized_read_returns_none(self, tmp_wd):
        """safe_read must return None for an oversized document (fail-closed)."""
        from state.helpers import safe_read, MAX_DOC_BYTES
        path = tmp_wd / "big.json"
        # Write a file that exceeds MAX_DOC_BYTES directly (bypass atomic_write)
        with open(path, "w") as f:
            f.write(json.dumps({"data": "x" * (MAX_DOC_BYTES + 1)}))
        assert safe_read(str(path)) is None

    def test_compare_and_swap_rejects_non_monotonic(self, tmp_wd):
        """CAS must reject a new_data version that is not exactly expected+1."""
        from state.helpers.atomic_write import atomic_write, compare_and_swap
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 1, "data": "initial"})
        # Attempt to write version 10 (not 1+1=2) — should raise ValueError
        with pytest.raises(ValueError, match="monotonic"):
            compare_and_swap(str(path), 1, {"version": 10, "data": "skip"}, "version")
        # Verify file unchanged
        from state.helpers import safe_read
        assert safe_read(str(path))["version"] == 1

    def test_compare_and_swap_rejects_reused_version(self, tmp_wd):
        """CAS must reject writing the same version again (no reuse)."""
        from state.helpers.atomic_write import atomic_write, compare_and_swap
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 1, "data": "initial"})
        # Attempt to write version 1 again (reuse) — should raise ValueError
        with pytest.raises(ValueError, match="monotonic"):
            compare_and_swap(str(path), 1, {"version": 1, "data": "reuse"}, "version")

    def test_compare_and_swap_auto_bumps_when_key_missing(self, tmp_wd):
        """When new_data has no version_key, CAS auto-bumps to expected+1."""
        from state.helpers.atomic_write import atomic_write, compare_and_swap
        from state.helpers import safe_read
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 1, "data": "old"})
        ok, new_v = compare_and_swap(str(path), 1, {"data": "new"}, "version")
        assert ok is True
        assert new_v == 2
        assert safe_read(str(path))["version"] == 2


# ===========================================================================
# Version check hardening
# ===========================================================================
class TestVersionCheckHardening:
    """Phase 1E: validate_version_monotonic, is_stale, assert_current_version."""

    def test_validate_version_monotonic_ok(self):
        from state.helpers import validate_version_monotonic
        assert validate_version_monotonic(1, 2) is True
        assert validate_version_monotonic(5, 6) is True

    def test_validate_version_monotonic_skip(self):
        from state.helpers import validate_version_monotonic
        with pytest.raises(ValueError, match="non-monotonic"):
            validate_version_monotonic(1, 3)  # skip 2

    def test_validate_version_monotonic_reuse(self):
        from state.helpers import validate_version_monotonic
        with pytest.raises(ValueError, match="non-monotonic"):
            validate_version_monotonic(1, 1)  # reuse

    def test_validate_version_monotonic_negative(self):
        from state.helpers import validate_version_monotonic
        with pytest.raises(ValueError, match="non-monotonic"):
            validate_version_monotonic(5, 4)  # decrease

    def test_is_stale_match(self, tmp_wd):
        from state.helpers.atomic_write import atomic_write
        from state.helpers import is_stale
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 3})
        stale, cur, exp, reason = is_stale(str(path), 3)
        assert stale is False
        assert cur == 3

    def test_is_stale_newer(self, tmp_wd):
        from state.helpers.atomic_write import atomic_write
        from state.helpers import is_stale
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 5})
        stale, cur, exp, reason = is_stale(str(path), 3)
        assert stale is True
        assert cur == 5
        assert "NEWER" in reason

    def test_is_stale_older(self, tmp_wd):
        from state.helpers.atomic_write import atomic_write
        from state.helpers import is_stale
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 2})
        stale, cur, exp, reason = is_stale(str(path), 5)
        assert stale is True
        assert cur == 2
        assert "OLDER" in reason

    def test_is_stale_missing(self, tmp_wd):
        from state.helpers import is_stale
        stale, cur, exp, reason = is_stale(str(tmp_wd / "missing.json"), 1)
        assert stale is True
        assert cur == 0
        assert "missing" in reason.lower()

    def test_assert_current_version_ok(self, tmp_wd):
        from state.helpers.atomic_write import atomic_write
        from state.helpers import assert_current_version
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 3})
        assert assert_current_version(str(path), 3) == 3

    def test_assert_current_version_raises(self, tmp_wd):
        from state.helpers.atomic_write import atomic_write
        from state.helpers import assert_current_version, StaleStateError
        path = tmp_wd / "state.json"
        atomic_write(str(path), {"version": 3})
        with pytest.raises(StaleStateError):
            assert_current_version(str(path), 1)


# ===========================================================================
# StateMachine hardening — model-text authority
# ===========================================================================
class TestStateMachineAuthorityHardening:
    """Phase 1E: model text must never establish transitions (AUTH-INV-01).

    Note: bare-string rejection, Delegation acceptance, approval-reference
    acceptance and stale expected_version denial are canonically covered by
    tests/orchestrator/test_foundation.py (test_free_text_is_never_authority,
    test_draft_to_planned_with_delegation, test_approval_reference_pattern_accepted,
    test_stale_machine_version_refused). Only the unique assertions are kept
    here.
    """

    def test_delegation_reference_string_rejected(self):
        """A bare 'delegation-001' string is rejected — must pass the Delegation object."""
        from orchestrator.foundation.state import StateMachine, StateTransitionError
        sm = StateMachine("t-1")
        with pytest.raises(StateTransitionError, match="structured authority"):
            sm.transition("PLANNED", authority="delegation-001")

    def test_no_authority_for_non_consequential_transition(self):
        """Transitions to COLLECTED, SYNTHESIZING, COMPLETE need no authority."""
        from orchestrator.foundation.state import StateMachine
        from orchestrator.foundation.contracts import Delegation
        sm = StateMachine("t-1")
        d = Delegation(task="t-1")
        sm.transition("PLANNED", authority=d)
        sm.transition("DELEGATED", authority=d)
        sm.transition("EXECUTING", authority=d)
        # COLLECTED does not require authority
        assert sm.transition("COLLECTED") == "COLLECTED"
        assert sm.transition("SYNTHESIZING") == "SYNTHESIZING"
        assert sm.transition("COMPLETE") == "COMPLETE"

    def test_model_text_with_approval_keyword_rejected(self):
        """Even a string containing 'approval' is rejected if not a structured ref."""
        from orchestrator.foundation.state import StateMachine, StateTransitionError
        sm = StateMachine("t-1")
        with pytest.raises(StateTransitionError, match="structured authority"):
            sm.transition("PLANNED", authority="I have approval from Human")


# ===========================================================================
# StateMachine hardening — version-aware transitions
# ===========================================================================
class TestStateMachineVersioning:
    """Phase 1E: per-machine version CAS (THREAT-021/022)."""

    def test_version_increments_on_transition(self):
        from orchestrator.foundation.state import StateMachine
        from orchestrator.foundation.contracts import Delegation
        sm = StateMachine("t-1")
        d = Delegation(task="t-1")
        assert sm.current_version() == 1
        sm.transition("PLANNED", authority=d)
        assert sm.current_version() == 2
        sm.transition("DELEGATED", authority=d)
        assert sm.current_version() == 3

    def test_expected_version_cas_ok(self):
        from orchestrator.foundation.state import StateMachine
        from orchestrator.foundation.contracts import Delegation
        sm = StateMachine("t-1")
        d = Delegation(task="t-1")
        assert sm.transition("PLANNED", authority=d, expected_version=1) == "PLANNED"

    def test_transition_history_recorded(self):
        from orchestrator.foundation.state import StateMachine
        from orchestrator.foundation.contracts import Delegation
        sm = StateMachine("t-1")
        d = Delegation(task="t-1")
        sm.transition("PLANNED", authority=d, actor="human")
        sm.transition("DELEGATED", authority=d, actor="orchestrator")
        history = sm.transition_history()
        assert len(history) == 2
        assert history[0]["from"] == "DRAFT"
        assert history[0]["to"] == "PLANNED"
        assert history[0]["actor"] == "human"
        assert history[0]["version"] == 2
        assert history[1]["from"] == "PLANNED"
        assert history[1]["to"] == "DELEGATED"
        assert history[1]["actor"] == "orchestrator"
        assert history[1]["version"] == 3


# ===========================================================================
# ProjectState hardening — version CAS
# ===========================================================================
class TestProjectStateVersioning:
    """Phase 1E: ProjectState.transition with project-level CAS."""

    def test_project_version_bumps_on_transition(self):
        from orchestrator.foundation.state import ProjectState
        from orchestrator.foundation.contracts import Delegation
        ps = ProjectState()
        d = Delegation(task="t-1")
        assert ps.version == 1
        ps.transition("t-1", "PLANNED", authority=d)
        assert ps.version == 2
        ps.transition("t-1", "DELEGATED", authority=d)
        assert ps.version == 3

    def test_project_version_cas_ok(self):
        from orchestrator.foundation.state import ProjectState
        from orchestrator.foundation.contracts import Delegation
        ps = ProjectState()
        d = Delegation(task="t-1")
        assert ps.transition("t-1", "PLANNED", authority=d,
                             expected_project_version=1) == "PLANNED"

    def test_project_version_cas_stale(self):
        from orchestrator.foundation.state import ProjectState, StateTransitionError
        from orchestrator.foundation.contracts import Delegation
        ps = ProjectState()
        d = Delegation(task="t-1")
        ps.transition("t-1", "PLANNED", authority=d)  # version now 2
        # Second caller with stale expected_version
        with pytest.raises(StateTransitionError, match="stale project version"):
            ps.transition("t-1", "BLOCKED", expected_project_version=1)