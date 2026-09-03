# tests/l3_runner/__main__.py — CLI convenience entry for the L3 runner
#
# Usage:
#   python -m tests.l3_runner --help
#   python -m tests.l3_runner run --scenario L3-TEST-001 --mode replay
#   python -m tests.l3_runner validate --bundle-dir audit/l3/L3-TEST-001
#   python -m tests.l3_runner test                    # run infrastructure tests

from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="L3 Independent Verification Infrastructure")
    sub = parser.add_subparsers(dest="command", required=True)
    # `run` — execute a scenario
    run_parser = sub.add_parser("run", help="Run an L3 scenario")
    run_parser.add_argument("--scenario", required=True)
    run_parser.add_argument("--mode", default="replay", choices=("replay", "live"))
    run_parser.add_argument("--bundle-base", default=None)
    run_parser.add_argument("--fixtures-root", default=None)
    run_parser.add_argument("--seed", type=int, default=42)
    run_parser.add_argument("--orchestrator-pid", type=int, default=0)
    run_parser.add_argument("--orchestrator-uid", type=int, default=0)
    run_parser.add_argument("--orchestrator-session", default="")
    run_parser.add_argument("--parent-session", default="")

    # `validate` — validate a bundle
    val_parser = sub.add_parser("validate", help="Validate an L3 evidence bundle")
    val_parser.add_argument("--bundle-dir", required=True)
    val_parser.add_argument("--scenario-id", default="")
    val_parser.add_argument("--int-scenario", default="")
    val_parser.add_argument("--verbose", action="store_true")

    # `preflight` — read-only run-prerequisites check
    pf = sub.add_parser("preflight",
                        help="Read-only preflight check (never runs L3)")
    pf.add_argument("--scenario", default="", help="L3-<CTRL>-<NNN>")
    pf.add_argument("--fixtures-root", default="")
    pf.add_argument("--orchestrator-pid", type=int, default=0)
    pf.add_argument("--orchestrator-uid", type=int, default=0)
    pf.add_argument("--json", action="store_true", help="emit JSON report")

    # `rehearsal` — G8: end-to-end replay/inert rehearsal (never live L3)
    rh = sub.add_parser("rehearsal",
                        help="Run a full replay/inert rehearsal producing + "
                             "validating a bundle under scratch (l3_claim=false)")
    rh.add_argument("--scenario", default="L3-TEST-001")
    rh.add_argument("--fixtures-root", default="")
    rh.add_argument("--scratch-base", default="")
    rh.add_argument("--seed", type=int, default=42)
    rh.add_argument("--orchestrator-pid", type=int, default=0)
    rh.add_argument("--orchestrator-uid", type=int, default=0)
    rh.add_argument("--orchestrator-session", default="")
    rh.add_argument("--parent-session", default="")
    rh.add_argument("--verifier-mode", default="subprocess",
                    choices=("subprocess", "inline"))
    rh.add_argument("--json", action="store_true")

    # `test` — run the infrastructure test suite
    sub.add_parser("test", help="Run the L3 infrastructure + preflight test suite")

    args = parser.parse_args(argv)

    if args.command == "run":
        from .runner import main as run_main
        # Strip the subcommand token; the runner parses the remaining args.
        rest = list(sys.argv[1:] if argv is None else argv[1:])
        while rest and rest[0] in ("run",):
            rest = rest[1:]
        return run_main(rest)

    if args.command == "validate":
        from .validator import validate_bundle_dir
        result = validate_bundle_dir(
            args.bundle_dir, scenario_id=args.scenario_id,
            int_scenario=args.int_scenario)
        if args.verbose or result.passed:
            print(f"Validation: {result.summary}")
        if result.errors:
            print("Errors:")
            for e in result.errors:
                print(f"  [FAIL] {e}")
        if result.warnings:
            print("Warnings:")
            for w in result.warnings:
                print(f"  [WARN] {w}")
        return 0 if result.passed else 1

    if args.command == "preflight":
        from .preflight import main as preflight_main
        rest = list(sys.argv[1:] if argv is None else argv[1:])
        while rest and rest[0] in ("preflight",):
            rest = rest[1:]
        return preflight_main(rest)

    if args.command == "rehearsal":
        from .rehearsal import run_rehearsal
        import json
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
        print(json.dumps(summary, indent=1))
        return 0

    if args.command == "test":
        import subprocess
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        proc = subprocess.run(
            [sys.executable, "-m", "pytest",
             os.path.join(project_root, "tests", "l3_runner",
                         "test_l3_infrastructure.py"),
             os.path.join(project_root, "tests", "l3_runner",
                         "test_l3_preflight.py"),
             "-q", "--tb=short"],
            cwd=project_root)
        return proc.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())