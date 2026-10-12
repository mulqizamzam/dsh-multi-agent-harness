# tests/unit/test_f22_write_through.py — F22 proof: write_through arms the
# atomic_write containment guard.
#
# Before the fix, write_through called atomic_write(path, data) with no base, so
# atomic_write defaulted its guard base to the target's own parent (a no-op).
# That let an absolute target OUTSIDE the workspace through whenever
# authorize_write early-returned without a path check — e.g. a read-classified
# action, which is not a write action and so is allowed by the gate. The write
# then landed outside the workspace. The fix pins base=workspace_base in the
# atomic_write call so the helper guard is effective.
#
# Note: the MINIMAL-SAFE fix is the call-site pin, NOT changing atomic_write's
# base=None default — the core state/audit unit tests deliberately pass absolute
# tmp paths with base=None as an opt-out, so rejecting absolute-or-defaulting
# base inside atomic_write regresses ~15 tests.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from state.helpers.atomic_write import StatePathError


def test_f22_read_action_cannot_escape_workspace(tmp_path):
    from control.execution_gate import write_through, workspace_base
    outside = tmp_path / "escape.json"          # absolute path OUTSIDE the repo
    assert not str(os.path.realpath(outside)).startswith(
        os.path.realpath(workspace_base()))
    # A read-classified action early-returns in authorize_write (not a write
    # action), so the helper guard is the only containment left. It must refuse.
    with pytest.raises(StatePathError):
        write_through("read", str(outside), {"escaped": True})
    assert not outside.exists()                 # nothing written


def test_f22_happy_path_in_workspace_still_writes(tmp_path):
    """The base pin must not regress an ordinary in-scope write_through."""
    from control.execution_gate import write_through
    from state.helpers.atomic_write import safe_read
    ws = tmp_path / "ws"
    ws.mkdir()
    path = write_through("write", "sub/f22.json", {"ok": 1}, base=str(ws))
    assert os.path.exists(path)
    assert safe_read(path) == {"ok": 1}


def test_f22_write_outside_workspace_still_denied_by_gate(tmp_path):
    """A genuine WRITE action to an outside path is denied by the gate itself
    (belt AND suspenders)."""
    from control.execution_gate import write_through, Denied
    outside = tmp_path / "escape2.json"
    with pytest.raises(Denied):
        write_through("write", str(outside), {"x": 1})
    assert not outside.exists()
