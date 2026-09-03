# tests/l3_runner/test_l3_rehearsal.py — G8: end-to-end evidence-bundle rehearsal tests
#
# Phase 5 / Session F — L3 execution readiness (G8 gap closure).
#
# Exercises tests/l3_runner/rehearsal.py — the FULL replay/inert execution path:
#   runner (R1..R8) -> verifier subprocess (P2/P3) -> collector (E1..E13)
#   -> validator (LV1..LV22) -> replay metadata (E11)
#
# The rehearsal uses ONLY the RecordedRuntimeDriver (no live DSH, no
# destructive action), forces l3_claim=false, and therefore FAILS LV10 by
# design. It also proves:
#   - oracle execution: O1 reference gates are exercised (>= 2 oracle classes),
#     reference-verdict.json is computed by the verifier process;
#   - replay: fixture hash determinism + replay command recorded;
#   - verifier independence: IO-1..IO-10 computed by the verifier process and
#     recorded in the bundle; same-PID and orchestrator-written
#     verifier-independence.json are rejected (LV21/LV22 + overwrite guard).
#
# SAFETY: bundles are produced under pytest tmp_path / tempfile scratch — the
# repo audit/l3/ is NEVER written, live L3 is never attempted.

from __future__ import annotations

import json
import os
import sys

import pytest

TESTS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(TESTS_ROOT)
FIXTURES_ROOT = os.path.join(TESTS_ROOT, "l3_reference", "fixtures")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.l3_runner.rehearsal import run_rehearsal  # noqa: E402
from tests.l3_runner.replay import fixture_hash  # noqa: E402


ALLOW_SCENARIO = "L3-TEST-001"   # expected ALLOW; O1=authority, O4
DENY_SCENARIO = "L3-TEST-002"    # expected DENY;  O1=execution_gate, O3, O4


def _rehearse(scenario, tmp_path, seed=42, orch_uid=None, orch_pid=99999):
    return run_rehearsal(
        scenario,
        fixtures_root=FIXTURES_ROOT,
        scratch_base=str(tmp_path / "auditroot"),
        seed=seed,
        orchestrator_pid=orch_pid,
        orchestrator_uid=orch_uid if orch_uid is not None else os.getuid(),
        orchestrator_session="session-orch",
        parent_session="session-ext",
        verifier_mode="subprocess",
    )


# ---------------------------------------------------------------------------
# End-to-end rehearsal: full path produces a complete bundle
# ---------------------------------------------------------------------------
def test_end_to_end_rehearsal_produces_complete_bundle(tmp_path):
    """The FULL path (runner -> verifier subprocess -> collector -> replay)
    produces a complete 13-file evidence bundle under the scratch location."""
    summary = _rehearse(ALLOW_SCENARIO, tmp_path)
    bundle_dir = summary["bundle_dir"]

    # The bundle must live under the scratch base, never the repo audit/l3/.
    assert str(tmp_path) in bundle_dir
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "audit", "l3",
                                           ALLOW_SCENARIO))

    for fname in ("manifest.json", "env.json", "plan.json", "before.sha256",
                  "after.sha256", "runtime-verdict.json", "audit-log.jsonl",
                  "reference-verdict.json", "oracle-classes.json",
                  "provenance.json", "replay.json",
                  "verifier-independence.json", "verdict-match.json"):
        assert os.path.isfile(os.path.join(bundle_dir, fname)), f"missing {fname}"

    assert summary["rehearsal"] is True
    assert summary["mode"] == "replay"


def test_rehearsal_l3_claim_false_and_lv10_by_design(tmp_path):
    """A rehearsal bundle is NOT an L3 bundle: l3_claim=false and validation
    fails LV10 by design (docs/testing/0003 LV10 requires l3_claim=true)."""
    summary = _rehearse(ALLOW_SCENARIO, tmp_path)
    assert summary["l3_claim"] is False
    assert summary["lv10_by_design"] is True
    assert any(e.startswith("LV10") for e in summary["validation_errors"])


def test_rehearsal_same_uid_io2_fails_honestly(tmp_path):
    """On this same-UID sandbox IO-2 fails honestly (never faked), so the
    independence checklist is not all-pass and no claim is possible."""
    summary = _rehearse(ALLOW_SCENARIO, tmp_path, orch_uid=os.getuid())
    assert summary["io1_pass"] is True      # separate process (subprocess)
    assert summary["io2_pass"] is False     # same UID => honest failure
    assert summary["io2_honest_fail_on_same_uid"] is True
    assert summary["independence_all_pass"] is False
    assert summary["l3_claim"] is False


# ---------------------------------------------------------------------------
# Oracle execution (O1 reference gates exercised in the rehearsal)
# ---------------------------------------------------------------------------
def test_rehearsal_oracle_classes_at_least_two(tmp_path):
    """R6 / IO-6: the rehearsal bundle records >= 2 oracle classes."""
    summary = _rehearse(ALLOW_SCENARIO, tmp_path)
    assert len(summary["oracle_classes_used"]) >= 2
    assert "O1" in summary["oracle_classes_used"]
    assert "O4" in summary["oracle_classes_used"]


def test_rehearsal_reference_verdict_computed_by_verifier(tmp_path):
    """The O1 oracle was executed: reference-verdict.json carries the decision
    and the verifier-binary identity of the process that computed it."""
    bundle_dir = _rehearse(ALLOW_SCENARIO, tmp_path)["bundle_dir"]
    with open(os.path.join(bundle_dir, "reference-verdict.json")) as f:
        ref = json.load(f)
    assert ref["decision"] == "ALLOW"
    assert ref["gate_under_test"] == "authority"
    assert ref["checklist_item_results"]
    assert len(ref.get("verifier_binary_sha256", "")) == 64


def test_rehearsal_deny_scenario_oracle_matches(tmp_path):
    """A DENY scenario rehearses end-to-end too: the execution-gate O1 oracle
    denies and the recorded runtime denies (match=true, still no claim)."""
    summary = _rehearse(DENY_SCENARIO, tmp_path)
    bundle_dir = summary["bundle_dir"]
    with open(os.path.join(bundle_dir, "reference-verdict.json")) as f:
        ref = json.load(f)
    assert ref["decision"] == "DENY"
    with open(os.path.join(bundle_dir, "verdict-match.json")) as f:
        match = json.load(f)
    assert match["match"] is True
    assert match["runtime_decision"] == "DENY"
    assert match["l3_claim"] is False
    assert summary["lv10_by_design"] is True


# ---------------------------------------------------------------------------
# Replay / reproducibility exercised in the rehearsal
# ---------------------------------------------------------------------------
def test_rehearsal_fixture_hash_deterministic(tmp_path):
    """Replay metadata: the fixture hash is deterministic across rehearsals of
    the same fixture, and the replay command is recorded."""
    s1 = _rehearse(ALLOW_SCENARIO, tmp_path, seed=42)
    s2 = _rehearse(ALLOW_SCENARIO, tmp_path, seed=7)
    expected = fixture_hash(os.path.join(FIXTURES_ROOT, ALLOW_SCENARIO))
    assert s1["fixture_hash"] == expected == s2["fixture_hash"]
    assert s1["fixture_hash"].startswith("sha256:")


def test_rehearsal_replay_command_recorded(tmp_path):
    """E11 + verdict-match: the documented re-run command is recorded."""
    summary = _rehearse(ALLOW_SCENARIO, tmp_path)
    assert "runner" in summary["replay_command"]
    assert summary["verdict_match_replay_command"]  # non-empty
    assert ALLOW_SCENARIO in summary["verdict_match_replay_command"]


# ---------------------------------------------------------------------------
# Verifier independence: IO-1..IO-10 recorded, forged records rejected
# ---------------------------------------------------------------------------
def test_rehearsal_io_checks_recorded_by_verifier(tmp_path):
    """IO-1..IO-10 are computed by the verifier process and recorded in
    verifier-independence.json with the verifier's own pid/session."""
    bundle_dir = _rehearse(ALLOW_SCENARIO, tmp_path)["bundle_dir"]
    with open(os.path.join(bundle_dir, "verifier-independence.json")) as f:
        ind = json.load(f)
    assert set(ind["io_checks"]) == {f"IO-{i}" for i in range(1, 11)}
    assert ind["verifier_pid"] > 0 and ind["orchestrator_pid"] > 0
    assert ind["verifier_pid"] != ind["orchestrator_pid"]  # IO-1 at record level
    assert ind["verifier_session_id"].startswith("verifier-")  # LV22 marker


def test_same_pid_verifier_independence_rejected(tmp_path):
    """LV21: a verifier-independence.json whose verifier_pid equals the
    orchestrator_pid (same-process verifier) is rejected by the validator."""
    from tests.l3_runner.validator import validate_bundle_dir
    bundle_dir = _rehearse(ALLOW_SCENARIO, tmp_path)["bundle_dir"]
    ind_path = os.path.join(bundle_dir, "verifier-independence.json")
    with open(ind_path) as f:
        forged = json.load(f)
    forged["verifier_pid"] = forged["orchestrator_pid"]  # same-process forgery
    forged["all_pass"] = True  # even a forged all-pass must be rejected
    with open(ind_path, "w") as f:
        json.dump(forged, f)
    res = validate_bundle_dir(bundle_dir, scenario_id=ALLOW_SCENARIO)
    assert any(e.startswith("LV21") for e in res.errors), res.errors


def test_orchestrator_written_verifier_independence_rejected(tmp_path):
    """LV22: a verifier-independence.json without the verifier-process session
    marker is rejected (orchestrator-written independence is not accepted)."""
    from tests.l3_runner.validator import validate_bundle_dir
    bundle_dir = _rehearse(ALLOW_SCENARIO, tmp_path)["bundle_dir"]
    ind_path = os.path.join(bundle_dir, "verifier-independence.json")
    with open(ind_path) as f:
        forged = json.load(f)
    forged["verifier_session_id"] = "orchestrator-session-abc"
    forged["all_pass"] = True
    with open(ind_path, "w") as f:
        json.dump(forged, f)
    res = validate_bundle_dir(bundle_dir, scenario_id=ALLOW_SCENARIO)
    assert any(e.startswith("LV22") for e in res.errors), res.errors


def test_verifier_overwrites_orchestrator_written_independence(tmp_path):
    """The verifier never trusts a pre-existing verifier-independence.json: an
    orchestrator-written forgery in the bundle is removed and replaced with the
    verifier's own computation (honest IO values preserved)."""
    from tests.l3_runner.collector import ensure_bundle_dir, write_bundle_item
    from tests.l3_runner.runner import _load_scenario_def
    from tests.l3_runner.verifier import Verifier

    bundle_dir = ensure_bundle_dir(ALLOW_SCENARIO, base=str(tmp_path))
    fixture = _load_scenario_def(ALLOW_SCENARIO, FIXTURES_ROOT)
    with open(os.path.join(FIXTURES_ROOT, ALLOW_SCENARIO, "plan.json")) as f:
        plan_pure = json.load(f)
    write_bundle_item(bundle_dir, "plan.json", plan_pure)
    write_bundle_item(bundle_dir, "runtime-verdict.json", {
        "scenario_id": ALLOW_SCENARIO, "decision": "ALLOW", "denial_path": None,
        "tool_call_id": "tc-1", "audit_event_ids": ["event-1"],
        "stopReason": "completed", "captured_at": "2026-08-31T10:00:10Z",
    })
    write_bundle_item(bundle_dir, "before.sha256",
                      {"algorithm": "sha256", "scope": [], "root_hash": "a" * 64})
    write_bundle_item(bundle_dir, "after.sha256",
                      {"algorithm": "sha256", "scope": [], "root_hash": "b" * 64})
    write_bundle_item(bundle_dir, "audit-log.jsonl",
                      [{"event_id": "event-1",
                        "timestamp": "2026-08-31T10:00:01Z",
                        "actor": "orchestrator", "actor_type": "orchestrator",
                        "action": "write", "target": "agents/cto/x.txt",
                        "project": "multi-agent-harness", "result": "allowed"}])

    # Orchestrator-written forgery: claims full independence + a fake pid.
    ind_path = os.path.join(bundle_dir, "verifier-independence.json")
    with open(ind_path, "w") as f:
        json.dump({
            "scenario_id": ALLOW_SCENARIO,
            "verifier_pid": 424242, "verifier_uid": 9999,
            "verifier_session_id": "orchestrator-session",
            "parent_session_id": None, "trust_root": "verifier-process",
            "orchestrator_pid": 99999,
            "io_checks": {f"IO-{i}": {"pass": True, "detail": "forged"}
                          for i in range(1, 11)},
            "all_pass": True,
        }, f)

    v = Verifier(bundle_dir, fixture,
                 orchestrator_pid=99999, orchestrator_uid=os.getuid(),
                 orchestrator_session="session-orch",
                 parent_session="session-ext", rehearsal=True)
    v.run()

    # The forgery must be gone: the file now reflects the verifier's own
    # process state and the honest same-UID IO-2 failure.
    assert v._independence_overwrite is True
    with open(ind_path) as f:
        ind = json.load(f)
    assert ind["verifier_session_id"].startswith("verifier-")
    assert ind["io_checks"]["IO-2"]["pass"] is False  # honest same-UID failure
    assert ind["all_pass"] is False
    assert ind["verifier_pid"] == os.getpid()  # this (verifier) process


# ---------------------------------------------------------------------------
# CLI / scratch hygiene
# ---------------------------------------------------------------------------
def test_rehearsal_cli_emits_json(tmp_path):
    from tests.l3_runner.rehearsal import main
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--scenario", ALLOW_SCENARIO, "--fixtures-root",
                   FIXTURES_ROOT, "--scratch-base", str(tmp_path / "cliroot"),
                   "--orchestrator-pid", "99999",
                   "--orchestrator-uid", str(os.getuid()), "--json"])
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data["rehearsal"] is True
    assert data["l3_claim"] is False
    assert data["lv10_by_design"] is True
    assert str(tmp_path) in data["bundle_dir"]


def test_rehearsal_never_touches_repo_audit_l3(tmp_path):
    """Rehearsals produce bundles under scratch only; the repo audit/l3/ is
    never written by the rehearsal path."""
    _rehearse(ALLOW_SCENARIO, tmp_path)
    _rehearse(DENY_SCENARIO, tmp_path)
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "audit", "l3",
                                           ALLOW_SCENARIO))
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "audit", "l3",
                                           DENY_SCENARIO))
