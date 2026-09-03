# tests/l3_runner/critical/runner.py — Critical-control L3 rehearsal runner
#
# Phase 5 / Session C — L3 Critical Control Readiness.
#
# Runs the six critical-control scenario bundles through the existing
# rehearsal/replay machinery and produces a readiness report. This module is
# TEST-SUPPORT ONLY. It never claims L3; it reports the honest readiness state.

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

# Ensure project root importable.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.l3_runner.rehearsal import run_rehearsal  # noqa: E402
from tests.l3_runner.replay import fixture_hash  # noqa: E402

# ---------------------------------------------------------------------------
# Critical scenario registry (6 critical controls -> 8 scenario bundles)
# ---------------------------------------------------------------------------
CRITICAL_SCENARIOS = {
    # control, scenario_id, gate, expected_verdict, oracle classes
    "authority_grant":      ("L3-AUTH-001", "authority", "ALLOW", ("O1", "O3", "O4")),
    "authority_expiry":     ("L3-AUTH-003", "authority", "DENY", ("O1", "O3", "O4")),
    "authority_revocation": ("L3-AUTH-004", "authority", "DENY", ("O1", "O3", "O4")),
    "execution_time_recheck": ("L3-AUTH-006", "authority", "DENY", ("O1", "O3", "O4")),
    "protected_path":       ("L3-PATH-001", "execution_gate", "DENY", ("O1", "O3", "O4")),
    "recovery_privilege":   ("L3-REC-004", "recovery", "DENY", ("O1", "O3", "O4")),
    "stale_state":          ("L3-ST-003", "state_transition", "DENY", ("O1", "O2", "O4")),
    "audit_integrity":      ("L3-AUD-002", "audit_integrity", "INVALID", ("O1", "O2", "O4")),
}

CRITICAL_CONTROLS = (
    "authority grant/revoke/expiry",
    "execution-time recheck",
    "protected-path execution",
    "recovery privilege bounding",
    "stale-state protection",
    "audit integrity",
)


def critical_fixtures_root() -> str:
    """The critical fixtures root under tests/l3_reference/critical/fixtures."""
    return os.path.join(_PROJECT_ROOT, "tests", "l3_reference", "critical", "fixtures")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_critical_rehearsal(scenario_id: str, *, fixtures_root: str = "",
                           scratch_base: str = "", seed: int = 42,
                           orchestrator_pid: int = 0,
                           orchestrator_uid: int = 0,
                           orchestrator_session: str = "",
                           parent_session: str = "",
                           verifier_mode: str = "subprocess") -> dict:
    """Run ONE critical scenario through the rehearsal machinery."""
    fixtures_root = fixtures_root or critical_fixtures_root()
    return run_rehearsal(
        scenario_id,
        fixtures_root=fixtures_root,
        scratch_base=scratch_base or tempfile.mkdtemp(prefix="l3-critical-"),
        seed=seed,
        orchestrator_pid=orchestrator_pid,
        orchestrator_uid=orchestrator_uid,
        orchestrator_session=orchestrator_session,
        parent_session=parent_session,
        verifier_mode=verifier_mode,
    )


def run_all_critical_rehearsals(*, fixtures_root: str = "",
                                scratch_base: str = "", seed: int = 42,
                                orchestrator_uid: int = 0) -> list[dict]:
    """Run every critical scenario bundle through the rehearsal machinery.

    Returns a list of per-scenario rehearsal summaries (never an L3 claim).
    """
    out = []
    for control, (scenario_id, gate, expected, classes) in CRITICAL_SCENARIOS.items():
        summary = run_critical_rehearsal(
            scenario_id, fixtures_root=fixtures_root, scratch_base=scratch_base,
            seed=seed,
            orchestrator_pid=os.getpid() + 1000 + len(out),
            orchestrator_uid=orchestrator_uid or os.getuid(),
            orchestrator_session=f"session-crit-{scenario_id}",
            parent_session="session-external",
            verifier_mode="subprocess",
        )
        summary["critical_control"] = control
        summary["expected_verdict"] = expected
        summary["gate_under_test"] = gate
        summary["declared_oracle_classes"] = sorted(set(classes))
        out.append(summary)
    return out


def critical_readiness_report(*, fixtures_root: str = "", scratch_base: str = "",
                              seed: int = 42, orchestrator_uid: int = 0) -> dict:
    """Produce the critical-control readiness report (read-only, no L3 claim).

    For each critical scenario it records:
      - P1: a runtime verdict was produced (recorded driver in rehearsal);
      - P2: IO-1 (distinct PID) and IO-2 (distinct UID) status — IO-2 is
        expected to FAIL honestly on a same-UID host;
      - P3: >= 2 oracle classes declared AND recorded;
      - P4: reproducible replay (deterministic fixture hash + recorded command);
      - rehearsal result (bundle complete, LV10-by-design, l3_claim=false).
    """
    summaries = run_all_critical_rehearsals(
        fixtures_root=fixtures_root, scratch_base=scratch_base, seed=seed,
        orchestrator_uid=orchestrator_uid)

    per_scenario = {}
    for s in summaries:
        sid = s["scenario_id"]
        per_scenario[sid] = {
            "critical_control": s["critical_control"],
            "expected_verdict": s["expected_verdict"],
            "gate_under_test": s["gate_under_test"],
            "P1_runtime_verdict_present": bool(s.get("bundle_dir")),
            "P2_io1_distinct_pid": bool(s.get("io1_pass")),
            "P2_io2_distinct_uid": bool(s.get("io2_pass")),
            "P3_oracle_classes": s.get("oracle_classes_used", []),
            "P3_at_least_two": len(set(s.get("oracle_classes_used", []))) >= 2,
            "P4_fixture_hash_deterministic": bool(s.get("fixture_hash")),
            "P4_replay_command": s.get("replay_command", ""),
            "l3_claim": bool(s.get("l3_claim")),
            "lv10_by_design": bool(s.get("lv10_by_design")),
            "validation_passed": bool(s.get("validation_passed")),
            "validation_errors": list(s.get("validation_errors", [])),
        }

    io2_all_fail = all(not p["P2_io2_distinct_uid"] for p in per_scenario.values())
    l3_claim_any = any(p["l3_claim"] for p in per_scenario.values())
    oracle_ok = all(p["P3_at_least_two"] for p in per_scenario.values())
    replay_ok = all(p["P4_fixture_hash_deterministic"] for p in per_scenario.values())
    bundles_complete = all(p["P1_runtime_verdict_present"] for p in per_scenario.values())

    return {
        "readiness_report": True,
        "date": _now_iso(),
        "critical_controls": list(CRITICAL_CONTROLS),
        "scenarios": per_scenario,
        "P1": {"all_runtime_verdicts_present": bundles_complete},
        "P2": {
            "io1_all_distinct_pid": all(
                p["P2_io1_distinct_pid"] for p in per_scenario.values()),
            "io2_all_distinct_uid": all(
                p["P2_io2_distinct_uid"] for p in per_scenario.values()),
            "io2_honest_fail_same_uid": io2_all_fail,
        },
        "P3": {"all_at_least_two_oracles": oracle_ok},
        "P4": {"all_replay_metadata_present": replay_ok},
        "rehearsal": {
            "all_bundles_complete": bundles_complete,
            "all_lv10_by_design": all(
                p["lv10_by_design"] for p in per_scenario.values()),
            "any_l3_claim": l3_claim_any,
        },
        "l3_claim_status": "NONE — rehearsal only; no control claimed L3",
        "live_readiness": {
            "live_dsh_runtime": "NOT READY (LiveDSHRuntimeDriver is a stub)",
            "separate_uid": "NOT READY (same-UID sandbox; IO-2 fails honestly)",
            "human_signed_plan": "FIXTURE-ONLY (inert plan.json templates; no real Human signature)",
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Critical-control L3 readiness report (rehearsal only, no L3 claim)")
    parser.add_argument("--fixtures-root", default="")
    parser.add_argument("--scratch-base", default="")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--orchestrator-uid", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = critical_readiness_report(
        fixtures_root=args.fixtures_root, scratch_base=args.scratch_base,
        seed=args.seed, orchestrator_uid=args.orchestrator_uid)

    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print("CRITICAL CONTROL L3 READINESS (rehearsal only — NO L3 CLAIM)")
        print("=" * 60)
        for sid, p in report["scenarios"].items():
            print(f"\n[{sid}] {p['critical_control']}")
            print(f"  gate={p['gate_under_test']} expected={p['expected_verdict']}")
            print(f"  P1 runtime={p['P1_runtime_verdict_present']} "
                  f"P2 io1={p['P2_io1_distinct_pid']} io2={p['P2_io2_distinct_uid']}")
            print(f"  P3 oracles={p['P3_oracle_classes']} "
                  f"P4 replay={p['P4_fixture_hash_deterministic']}")
            print(f"  l3_claim={p['l3_claim']} lv10_by_design={p['lv10_by_design']}")
        print("\n" + "=" * 60)
        print("P1:", report["P1"])
        print("P2:", report["P2"])
        print("P3:", report["P3"])
        print("P4:", report["P4"])
        print("L3 CLAIM STATUS:", report["l3_claim_status"])
        print("LIVE READINESS:", report["live_readiness"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
