# tests/l3_reference/fixtures.py — fixture helpers for L3 infrastructure tests
#
# Inert specification support: creates synthetic scenario fixtures used ONLY by
# the infrastructure tests (tests/l3_runner/test_l3_infrastructure.py). These
# carry no authority (AUTH-INV-14) and are NOT Human-signed evidence.

from __future__ import annotations

import json
import os

FIXTURES_ROOT = os.path.dirname(os.path.abspath(__file__))


def _write_single_oracle_scenario(fixtures_root: str = FIXTURES_ROOT) -> str:
    """Write a synthetic scenario whose plan declares only ONE oracle class,
    so the runner's R6 guard can be exercised (must refuse). Returns the
    scenario id."""
    scenario_id = "L3-TEST-SINGLE"
    dirpath = os.path.join(fixtures_root, scenario_id)
    os.makedirs(dirpath, exist_ok=True)
    plan = {
        "scenario_id": scenario_id,
        "actor": "orchestrator",
        "action": "write",
        "target": "agents/x.txt",
        "preconditions": ["synthetic single-oracle scenario"],
        "expected_verdict": "ALLOW",
        "expected_verdict_reason": "must be refused by R6 (single oracle)",
        "human_signoff_id": "human-2026-08-31-003",
        "human_signoff_ts": "2026-08-31T00:00:00Z",
        "human_signoff_method": "interactive",
        "gate_under_test": "authority",
        "oracle_classes_used": ["O1"],   # < 2 => R6 violation
        "oracle_rationale": "single oracle only",
        "replayable": True,
        "target_is_protected": False,
        "environment": "dev",
        "project": "multi-agent-harness",
        "oracle_context": {},
    }
    with open(os.path.join(dirpath, "plan.json"), "w") as f:
        json.dump(plan, f, indent=1)
    return scenario_id
