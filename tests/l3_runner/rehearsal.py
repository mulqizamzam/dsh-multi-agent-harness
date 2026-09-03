# tests/l3_runner/rehearsal.py — G8: evidence-bundle rehearsal execution path
#
# Phase 5 / Session F — L3 execution readiness (G8 gap closure).
#
# PURPOSE
#   Drives a FULL L3 scenario in REPLAY / INERT mode end-to-end, producing and
#   validating a complete evidence bundle under a SCRATCH location:
#
#       runner (R1..R8) -> verifier subprocess (P2/P3) -> collector (E1..E13)
#       -> validator (LV1..LV22) -> replay metadata (E11)
#
#   The rehearsal uses ONLY the RecordedRuntimeDriver (safe, deterministic) and
#   forces `l3_claim=false` (rehearsal). A rehearsal bundle therefore FAILS
#   LV10 by design — it is machinery proof, never an L3 claim.
#
# SAFETY (hard requirements):
#   - NEVER runs live L3: `run_rehearsal()` always uses mode="replay"; live
#     mode refusal in runner.py is untouched.
#   - NEVER writes into the repo's audit/l3/: bundles are produced under a
#     caller-supplied scratch base (pytest tmp_path or tempfile).
#   - NEVER fakes separation: with the real same-UID host, IO-2 fails honestly
#     and the rehearsal reports l3_claim=false.
#
# USAGE:
#   python -m tests.l3_runner.rehearsal --scenario L3-TEST-001 [--json]
#   from tests.l3_runner.rehearsal import run_rehearsal
#   summary = run_rehearsal("L3-TEST-001", fixtures_root=..., scratch_base=...)

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

from .runner import run_scenario
from .validator import validate_bundle_dir

# Project root (three levels up from this file).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_rehearsal(scenario_id: str, *, fixtures_root: str = "",
                  scratch_base: str = "", seed: int = 42,
                  orchestrator_pid: int = 0, orchestrator_uid: int = 0,
                  orchestrator_session: str = "", parent_session: str = "",
                  verifier_mode: str = "subprocess",
                  verifier_python: str = sys.executable) -> dict:
    """Run one L3 scenario end-to-end in replay/inert (rehearsal) mode.

    Args:
        scenario_id: L3-<CTRL>-<NNN>.
        fixtures_root: tests/l3_reference/fixtures (defaults to the repo path).
        scratch_base: directory under which `audit/l3/<scenario>/` is created.
            Defaults to a fresh tempfile.mkdtemp() so the repo audit/l3/ is
            NEVER written by a rehearsal.
        orchestrator_pid/uid/session/parent_session: orchestrator identity for
            the IO-1/IO-2/IO-4 checks. When omitted (0), the runner records the
            runner-side identity; the rehearsal still reports l3_claim=false.

    Returns:
        summary dict: bundle_dir, validation result, l3_claim, lv10_by_design,
        fixture_hash, replay_command, oracle classes, io2_honest flag, and the
        rehearsal mode marker.
    """
    fixtures_root = fixtures_root or os.path.join(
        PROJECT_ROOT, "tests", "l3_reference", "fixtures")
    scratch_base = scratch_base or tempfile.mkdtemp(prefix="l3-rehearsal-")

    # The rehearsal ALWAYS runs in replay mode with the recorded driver. Live
    # mode is never reachable here (runner.py refuses it).
    summary = run_scenario(
        scenario_id,
        fixtures_root=fixtures_root,
        bundle_base=scratch_base,
        mode="replay",
        seed=seed,
        orchestrator_pid=orchestrator_pid,
        orchestrator_uid=orchestrator_uid,
        orchestrator_session=orchestrator_session,
        parent_session=parent_session,
        verifier_mode=verifier_mode,
        verifier_python=verifier_python,
    )
    bundle_dir = summary["bundle_dir"]

    # Validate the produced bundle (structure-only; never executes anything).
    validation = validate_bundle_dir(bundle_dir, scenario_id=scenario_id)

    # Extract the key facts for the readiness report.
    with open(os.path.join(bundle_dir, "verdict-match.json")) as f:
        match = json.load(f)
    with open(os.path.join(bundle_dir, "replay.json")) as f:
        replay = json.load(f)
    with open(os.path.join(bundle_dir, "oracle-classes.json")) as f:
        oracles = json.load(f)
    with open(os.path.join(bundle_dir, "verifier-independence.json")) as f:
        ind = json.load(f)

    lv10_errors = [e for e in validation.errors if e.startswith("LV10")]
    lv21_22_errors = [e for e in validation.errors
                      if e.startswith("LV21") or e.startswith("LV22")]

    return {
        "rehearsal": True,
        "mode": "replay",
        "scenario_id": scenario_id,
        "bundle_dir": bundle_dir,
        "scratch_base": scratch_base,
        "l3_claim": bool(match.get("l3_claim")),
        "lv10_by_design": bool(lv10_errors),
        "validation_passed": validation.passed,
        "validation_errors": list(validation.errors),
        "validation_warnings": list(validation.warnings),
        "oracle_classes_used": sorted(set(oracles.get("oracle_classes_used", []))),
        "fixture_hash": replay.get("fixture_hash", ""),
        "replay_command": replay.get("command_line", ""),
        "verdict_match_replay_command": match.get("replay_command", ""),
        "io1_pass": bool(ind.get("io_checks", {}).get("IO-1", {}).get("pass")),
        "io2_pass": bool(ind.get("io_checks", {}).get("IO-2", {}).get("pass")),
        "io2_honest_fail_on_same_uid": (ind.get("io_checks", {}).get("IO-2", {}).get("pass") is False),
        "independence_all_pass": bool(ind.get("all_pass")),
        "verifier_pid": ind.get("verifier_pid"),
        "orchestrator_pid": ind.get("orchestrator_pid"),
        "completed_at": _now_iso(),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="L3 rehearsal (replay/inert) end-to-end execution — "
                    "never runs live L3, never writes repo audit/l3/")
    parser.add_argument("--scenario", default="L3-TEST-001")
    parser.add_argument("--fixtures-root", default="")
    parser.add_argument("--scratch-base", default="")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--orchestrator-pid", type=int, default=0)
    parser.add_argument("--orchestrator-uid", type=int, default=0)
    parser.add_argument("--orchestrator-session", default="")
    parser.add_argument("--parent-session", default="")
    parser.add_argument("--verifier-mode", default="subprocess",
                        choices=("subprocess", "inline"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    summary = run_rehearsal(
        args.scenario,
        fixtures_root=args.fixtures_root,
        scratch_base=args.scratch_base,
        seed=args.seed,
        orchestrator_pid=args.orchestrator_pid,
        orchestrator_uid=args.orchestrator_uid,
        orchestrator_session=args.orchestrator_session,
        parent_session=args.parent_session,
        verifier_mode=args.verifier_mode,
    )
    if args.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"rehearsal scenario={summary['scenario_id']} "
              f"mode={summary['mode']} l3_claim={summary['l3_claim']}")
        print(f"bundle_dir={summary['bundle_dir']}")
        print(f"oracle_classes={summary['oracle_classes_used']}")
        print(f"fixture_hash={summary['fixture_hash'][:24]}...")
        print(f"replay_command={summary['replay_command']}")
        print(f"io1_pass={summary['io1_pass']} io2_pass={summary['io2_pass']} "
              f"independence_all_pass={summary['independence_all_pass']}")
        print(f"validation_passed={summary['validation_passed']} "
              f"lv10_by_design={summary['lv10_by_design']}")
        if summary["validation_errors"]:
            print("validation errors:")
            for e in summary["validation_errors"]:
                print(f"  [FAIL] {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
