# tests/unit/test_audit_append_log.py
#
# Regression proofs for the audit ledger append helpers:
#
#   F17 — append_event on a bare relative filename ("events.jsonl") must not
#         raise FileNotFoundError: os.path.dirname() returns "" and
#         os.makedirs("") fails.
#   F18 — verify_append_only must normalize naive vs aware datetimes before
#         the monotonicity comparison; a "Z"-suffixed event followed by a naive
#         one otherwise aborts the check with TypeError.

import contextlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from audit.helpers.append_log import append_event, verify_append_only


@contextlib.contextmanager
def _cwd(path):
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(prev)


# ---------------------------------------------------------------------------
# F17 — bare relative filename
# ---------------------------------------------------------------------------

def test_append_event_accepts_bare_relative_filename(tmp_path):
    """A bare relative log path has no directory component; the append must
    land in the current directory, not raise FileNotFoundError."""
    target = tmp_path / "events.jsonl"
    with _cwd(str(tmp_path)):
        assert not target.exists()
        assert append_event("events.jsonl", {
            "event_id": "e1", "event_class": "flow_started",
            "timestamp": "2026-08-31T00:00:00Z", "result": "recorded"}) is True
        assert target.exists(), "ledger must land in the current directory"
        # a second append (same path, ledger now exists) must also work
        append_event("events.jsonl", {
            "event_id": "e2", "event_class": "flow_finished",
            "timestamp": "2026-08-31T00:00:01Z", "result": "complete"})
        assert len(target.read_text().splitlines()) == 2
        # the bare name landed directly in cwd — no directory was created
        # for it (the os.makedirs("") FileNotFoundError regression)
        assert target.is_file()
        assert not (tmp_path / "events.jsonl").is_dir()
    # nothing leaked into the repo tree
    assert not os.path.exists(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "events.jsonl"))


def test_append_event_still_creates_nested_directories(tmp_path):
    p = os.path.join(str(tmp_path), "a", "b", "events.jsonl")
    append_event(p, {"event_id": "e1", "event_class": "flow_started",
                     "timestamp": "2026-08-31T00:00:00Z"})
    assert os.path.exists(p)


# ---------------------------------------------------------------------------
# F18 — naive / aware timestamp normalization
# ---------------------------------------------------------------------------

def _ledger(tmp_path, events):
    p = os.path.join(str(tmp_path), "events.jsonl")
    with open(p, "w") as f:
        for e in events:
            f.write(json.dumps(e, sort_keys=True) + "\n")
    return p


def test_verify_append_only_handles_mixed_naive_and_aware_timestamps(tmp_path):
    """A Z-suffixed event followed by a naive one must not raise TypeError."""
    p = _ledger(tmp_path, [
        {"event_id": "e1", "event_class": "flow_started",
         "timestamp": "2026-08-31T00:00:00Z", "result": "recorded"},
        {"event_id": "e2", "event_class": "intake_recorded",
         "timestamp": "2026-08-31T00:00:01", "result": "recorded"},
        {"event_id": "e3", "event_class": "flow_finished",
         "timestamp": "2026-08-31T00:00:02+00:00", "result": "complete"},
    ])
    ok, problems = verify_append_only(p)
    assert ok is True, problems
    assert problems == []


def test_verify_append_only_still_detects_out_of_order_mixed_timestamps(tmp_path):
    """The fix must not blind the real reordering signal: the naive event is
    treated as UTC, so it is still *earlier* than the preceding Z-suffixed."""
    p = _ledger(tmp_path, [
        {"event_id": "e1", "event_class": "flow_started",
         "timestamp": "2026-08-31T00:00:00Z", "result": "recorded"},
        {"event_id": "e2", "event_class": "intake_recorded",
         "timestamp": "2026-08-30T23:59:59", "result": "recorded"},
    ])
    ok, problems = verify_append_only(p)
    assert ok is False
    assert any("out of order" in pr for pr in problems)


def test_verify_append_only_offset_aware_ordering(tmp_path):
    """An event stamped 01:00+02:00 is 23:00Z on the PREVIOUS day, so it is
    earlier than a following 00:00Z event. Only parsed comparison sees that."""
    p = _ledger(tmp_path, [
        {"event_id": "e1", "event_class": "flow_started",
         "timestamp": "2026-08-31T00:00:00Z", "result": "recorded"},
        {"event_id": "e2", "event_class": "intake_recorded",
         "timestamp": "2026-08-31T01:00:00+02:00", "result": "recorded"},
    ])
    ok, problems = verify_append_only(p)
    assert ok is False, "2026-08-31T01:00:00+02:00 == 2026-08-30T23:00:00Z"
    assert any("out of order" in pr for pr in problems)
