# orchestrator.entrypoint.__main__ — CLI front door (DSH chat → ProductionRun)
#
# Phase 5 / Front Door V1. Usage:
#
#   python -m orchestrator.entrypoint \
#     --objective "produce a design doc" \
#     --scope "docs/design/x.md" \
#     --delegation-id "delegation-prod-001" \
#     [--constraint "no secrets"] \
#     [--expected-outcome "design doc written"] \
#     [--project multi-agent-harness] \
#     [--base /path/to/workspace]
#
# JSON stdin (fields merged; CLI flags override):
#
#   echo '{"objective":"...","scope":["..."]}' | \
#   python -m orchestrator.entrypoint --json-stdin \
#     --delegation-id "delegation-prod-001"
#
# Emits the structured JSON envelope on stdout. Exit codes:
#   0 COMPLETE    2 BLOCKED    3 ESCALATED    1 ERROR
#
# Security:
#   - objective is DATA, never authority
#   - delegation_id is resolved (read-only) from the protected registry
#   - the front door NEVER creates a Delegation and NEVER sets ACTIVE
#   - no raw DSH tool, no ExecutionFlow bypass, no gate downgrade

from __future__ import annotations

import argparse
import json
import sys

from .entry import (
    SCHEMA,
    COMPLETE,
    BLOCKED,
    ESCALATED,
    ERROR,
    FrontDoorRequest,
    FrontDoorResult,
    run_front_door,
)

# Exit code mapping per spec: COMPLETE→0, BLOCKED→2, ESCALATED→3, ERROR→1
_EXIT_CODE = {
    COMPLETE: 0,
    ERROR: 1,
    BLOCKED: 2,
    ESCALATED: 3,
}


def _parse_argv(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DSH chat → ProductionRun front door (V1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:  0 COMPLETE  2 BLOCKED  3 ESCALATED  1 ERROR\n\n"
            "The front door never creates a Delegation, never sets ACTIVE, "
            "never fabricates approval, and never derives authority from "
            "prose (AUTH-INV-01/05/07/09/13)."
        ),
    )
    parser.add_argument(
        "--objective", default=None,
        help="User objective (DATA — never authority). Required via CLI or "
             "--json-stdin.",
    )
    parser.add_argument(
        "--scope", action="append", dest="scope", default=None,
        help="Scope entry (repeatable, at least one required). "
             "Example: --scope agents/cto/output.txt",
    )
    parser.add_argument(
        "--delegation-id", default=None,
        help="Existing structured delegation id (delegation-<id>). "
             "The front door resolves this from the protected registry; "
             "it never creates a delegation from text.",
    )
    parser.add_argument(
        "--constraint", action="append", default=None,
        dest="constraint",
        help="Optional constraint (repeatable). Example: --constraint "
             "'no destructive actions'",
    )
    parser.add_argument(
        "--expected-outcome", default=None,
        help="Optional expected outcome description (string).",
    )
    parser.add_argument(
        "--project", default=None,
        help="Project id (default: multi-agent-harness).",
    )
    parser.add_argument(
        "--base", default=None,
        help="Workspace base directory (default: project root).",
    )
    parser.add_argument(
        "--json-stdin", action="store_true", default=False,
        help="Read a JSON request object from stdin. CLI flags override "
             "JSON fields when both are provided.",
    )
    parser.add_argument(
        "--indent", type=int, default=2,
        help="JSON indentation (default: 2). 0 for compact output.",
    )
    return parser.parse_args(argv)


def _merge_json_and_cli(args: argparse.Namespace) -> dict:
    """Merge JSON stdin data with CLI args (CLI overrides)."""
    data: dict = {}
    if args.json_stdin:
        raw = sys.stdin.read()
        if raw.strip():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"invalid JSON stdin: {e}")
            if not isinstance(data, dict):
                raise ValueError("JSON stdin must be a JSON object")
    # Merge: CLI overrides JSON
    for key, cli_val in [
        ("objective", args.objective),
        ("delegation_id", args.delegation_id),
        ("project", args.project),
        ("base", args.base),
        ("expected_outcome", args.expected_outcome),
        ("constraint", args.constraint),
    ]:
        if cli_val is not None:
            data[key] = cli_val

    # Scope: CLI append overrides JSON entirely
    if args.scope is not None:
        data["scope"] = args.scope

    # Normalize constraint → constraints
    if "constraint" in data:
        data["constraints"] = data.pop("constraint")

    return data


def main(argv: list[str] | None = None) -> int:
    args = _parse_argv(argv)
    indent = args.indent if args.indent else None

    # Merge JSON stdin and CLI args.
    try:
        data = _merge_json_and_cli(args)
    except ValueError as e:
        env = FrontDoorResult(status=ERROR, errors=(str(e),)).to_dict()
        print(json.dumps(env, indent=indent, default=str, sort_keys=False),
              flush=True)
        return _EXIT_CODE.get(ERROR, 1)

    # Build the request. Shape validation inside FrontDoorRequest will catch
    # missing required fields.
    try:
        request = FrontDoorRequest(
            objective=data.get("objective", ""),
            scope=tuple(data.get("scope", []) or []),
            delegation_id=data.get("delegation_id", ""),
            constraints=tuple(data.get("constraints", []) or []),
            expected_outcome=data.get("expected_outcome", ""),
            project=data.get("project", "multi-agent-harness"),
            base=data.get("base", None),
        )
    except Exception as e:  # noqa: BLE001 — shape validation is fail-closed
        env = FrontDoorResult(status=ERROR, errors=(str(e),)).to_dict()
        print(json.dumps(env, indent=indent, default=str, sort_keys=False),
              flush=True)
        return _EXIT_CODE.get(ERROR, 1)

    result = run_front_door(request)
    env = result.to_dict()
    print(json.dumps(env, indent=indent, default=str, sort_keys=False),
          flush=True)
    return _EXIT_CODE.get(result.status, 1)


if __name__ == "__main__":
    sys.exit(main())