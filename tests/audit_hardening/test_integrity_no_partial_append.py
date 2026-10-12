# tests/audit_hardening/test_integrity_no_partial_append.py
#
# Regression proofs for the audit ledger's "never a partial append" contract
# (FINAL architecture §4.7):
#
#   F13 — append_chained_event must validate the existing ledger BEFORE it
#         appends. Appending first and computing the chain afterwards leaves a
#         durable but unchained event when compute_chain() fails, and every
#         later append for that project then fails CORRUPTION_DETECTED.
#   F16 — recompute_and_compare must surface a corrupt side-car through the
#         module's typed AuditIntegrityError, never a bare JSONDecodeError.
#   F26c — correlate_recovery must compare PARSED datetimes; lexicographic
#         string ordering reports false ordering anomalies across UTC offsets
#         and mixed naive/aware forms.

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from audit.helpers.append_log import AuditIntegrityError, append_event
from audit.helpers.integrity import append_chained_event, compute_chain
from audit.hardening.chain import recompute_and_compare
from audit.hardening.recovery_correlation import correlate_recovery

TS = "2026-08-31T00:00:0"


def _ev(eid, n):
    return {"event_id": eid, "event_class": "flow_started",
            "timestamp": f"{TS}{n}Z", "result": "recorded"}


def _write(path, events):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for e in events:
            f.write(json.dumps(e, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# F13 — no partial append
# ---------------------------------------------------------------------------

def test_append_chained_event_rejects_corrupt_ledger_without_writing(tmp_path):
    """A pre-existing corrupt line must abort the append AND leave the file
    byte-for-byte unchanged (no durable unchained event)."""
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [_ev("e1", 1), _ev("e2", 2)])
    # Corrupt line 2 in place (an append-only ledger is never edited, so this
    # is exactly the tampering shape that must make every append fail).
    lines = open(p).readlines()
    lines[1] = '{"event_id": "e2", "event_class": "flow_started"\n'  # truncated JSON
    with open(p, "w") as f:
        f.writelines(lines)
    before = open(p, "rb").read()

    with pytest.raises(AuditIntegrityError):
        append_chained_event(p, _ev("e3", 3))

    after = open(p, "rb").read()
    assert after == before, "append mutated a corrupt ledger (partial append!)"
    assert len(after.decode().splitlines()) == 2, (
        "appended event landed in the ledger without being chained")


def test_append_chained_event_happy_path_still_chains(tmp_path):
    """The ordering fix must not regress the documented return contract."""
    p = os.path.join(str(tmp_path), "events.jsonl")
    last = append_chained_event(p, _ev("e1", 1))
    assert last is not None and last["line"] == 1
    last2 = append_chained_event(p, _ev("e2", 2))
    assert last2 is not None and last2["line"] == 2
    # A third append over the now-chained ledger still succeeds.
    last3 = append_chained_event(p, _ev("e3", 3))
    assert last3["line"] == 3
    assert recompute_and_compare(p)["ok"] is True


def test_sidecar_not_written_when_ledger_is_corrupt(tmp_path):
    """A rejected append must not leave a stale side-car either."""
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [_ev("e1", 1)])
    with open(p, "a") as f:
        f.write("{{{not json\n")
    before_sidecar = open(p + ".chain", "rb").read() \
        if os.path.exists(p + ".chain") else b""
    with pytest.raises(AuditIntegrityError):
        append_chained_event(p, _ev("e2", 2))
    after_sidecar = open(p + ".chain", "rb").read() \
        if os.path.exists(p + ".chain") else b""
    assert after_sidecar == before_sidecar


# ---------------------------------------------------------------------------
# F16 — corrupt side-car raises the typed error
# ---------------------------------------------------------------------------

def test_recompute_and_compare_corrupt_sidecar_raises_typed_error(tmp_path):
    """A corrupt side-car is an AuditIntegrityError, not a bare JSONDecodeError."""
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [_ev("e1", 1), _ev("e2", 2)])
    compute_chain(p)   # establishes the side-car baseline
    with open(p + ".chain", "w") as f:
        f.write('{"line": 1, "event_id": "e1", "cumulativ\n')  # corrupt

    with pytest.raises(AuditIntegrityError):
        recompute_and_compare(p)


def test_recompute_and_compare_clean_sidecar_still_ok(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [_ev("e1", 1), _ev("e2", 2)])
    compute_chain(p)
    result = recompute_and_compare(p)
    assert result["ok"] is True
    assert result["problems"] == []


# ---------------------------------------------------------------------------
# F26c — parsed timestamps, not lexicographic strings
# ---------------------------------------------------------------------------

def test_correlate_recovery_ordering_handles_utc_offsets(tmp_path):
    """An execution event at 2026-08-31T00:00:00+02:00 is 22:00Z on Aug 30 —
    chronologically BEFORE the 23:00Z recovery event. String comparison
    ("2026-08-30T23:00:00Z" < "2026-08-31T00:00:00+02:00") wrongly reports a
    false ordering anomaly."""
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [
        {"event_id": "e1", "event_class": "execution_attempt",
         "timestamp": "2026-08-31T00:00:00+02:00", "task_id": "task-1",
         "result": "error"},
        {"event_id": "e2", "event_class": "recovery",
         "timestamp": "2026-08-30T23:00:00Z", "task_id": "task-1",
         "result": "recovering", "recovery_state": "PRESERVED"},
    ])
    result = correlate_recovery(p, task_id="task-1")
    assert result["ok"] is True, (
        f"false ordering anomaly from lexicographic comparison: "
        f"{result['problems']}")
    assert len(result["recovery_events"]) == 1
    assert len(result["execution_events"]) == 1


def test_correlate_recovery_ordering_anomaly_still_detected(tmp_path):
    """The fix must not blind the real anomaly: recovery genuinely first.

    Discriminating fixture: the execution event's CLOCK time is earlier
    ("20:00" < "23:00") but its INSTANT is later (20:00-05:00 == 01:00Z the
    next day). Lexicographic comparison reports no anomaly; instant
    comparison correctly reports one.
    """
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [
        {"event_id": "e1", "event_class": "recovery",
         "timestamp": "2026-08-30T23:00:00Z", "task_id": "task-1",
         "result": "recovering", "recovery_state": "PRESERVED"},
        {"event_id": "e2", "event_class": "execution_attempt",
         "timestamp": "2026-08-30T20:00:00-05:00", "task_id": "task-1",
         "result": "error"},
    ])
    result = correlate_recovery(p, task_id="task-1")
    assert result["ok"] is False
    assert any("ordering anomaly" in pr for pr in result["problems"])


def test_correlate_recovery_mixed_naive_and_aware_timestamps(tmp_path):
    """Mixing a naive and a Z-suffixed timestamp must not raise TypeError
    (the naive one is normalized to UTC)."""
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [
        {"event_id": "e1", "event_class": "execution_attempt",
         "timestamp": "2026-08-30T22:00:00", "task_id": "task-1",
         "result": "error"},
        {"event_id": "e2", "event_class": "recovery",
         "timestamp": "2026-08-30T23:00:00Z", "task_id": "task-1",
         "result": "recovering", "recovery_state": "PRESERVED"},
    ])
    result = correlate_recovery(p, task_id="task-1")
    assert result["ok"] is True, result["problems"]


def test_correlate_recovery_unparseable_timestamps_do_not_crash(tmp_path):
    """A ledger with no usable timestamps must degrade, not raise."""
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [
        {"event_id": "e1", "event_class": "execution_attempt",
         "timestamp": "not-a-date", "task_id": "task-1", "result": "error"},
        {"event_id": "e2", "event_class": "recovery",
         "task_id": "task-1", "result": "recovering",
         "recovery_state": "PRESERVED"},
    ])
    result = correlate_recovery(p, task_id="task-1")
    assert result["ok"] is True
    assert len(result["recovery_events"]) == 1
