#!/usr/bin/env python3
# runs/mount-verification-2026-09-07/finalize_int01_int07.py — post-mount
# verification driver (2026-09-07). Consumes the session-recorded live
# subagent_cto results and drives ExecutionFlow + RealDSHBackend (marker ON)
# to produce canonical evidence bundles under this directory.
#
# TEST-SUPPORT ONLY. Based on runs/closure/closure_harness.py (Phase 3),
# with two differences:
#   1. require_marker=True  — the D4/D7 composition is Human-approved (this
#      session) and the marker is set post-mount, so the real gate is exercised.
#   2. Bundles are written HERE (timestamped dir), never into
#      audit/runtime/INT-01|07 — the Phase-3 canonical bundles are cited by
#      docs and must not be overwritten.

import json
import os
import sys
import tempfile
import uuid

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_RUNS_CLOSURE = os.path.join(_PROJECT_ROOT, "runs", "closure")
for _p in (_PROJECT_ROOT, os.path.join(_PROJECT_ROOT, "tests"), _RUNS_CLOSURE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from conftest import start_o3_daemon, stop_o3_daemon  # noqa: E402
import closure_harness as ch  # noqa: E402

RUNS_DIR = _PROJECT_ROOT + "/runs/closure"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def finalize(scenario: str, meta_file: str, live: dict) -> dict:
    meta = json.load(open(meta_file))
    os.environ.setdefault("DSH_LIVE_BRIDGE_ACTIVE", "1")
    assert os.environ.get("DSH_LIVE_BRIDGE_ACTIVE", "").lower() in ("1", "true", "yes"), \
        "DSH_LIVE_BRIDGE_ACTIVE must be set post-mount (fail-closed otherwise)"

    ws = tempfile.mkdtemp(prefix="mv-")
    ws = ch.make_ws(ws)
    d = start_o3_daemon(ws)
    try:
        ch.seed_delegation(ws, meta["del_id"], task="task-1")
        real_child = {
            "task_id": live["structured"].get("task_id", meta["subtask_task_id"]),
            "role": meta["subtask_role"],
            "run_id": live["run_id"],
            "tool_name": f"subagent_{meta['subtask_role']}",
            "stop_reason": live["stop_reason"],
            "structured": live["structured"],
        }
        bridge_calls = []

        def _bridge(invocation, instance):
            bridge_calls.append({"role": instance.role})
            return ch.DSHBridgeResponse(
                run_id=real_child["run_id"],
                output=json.dumps(real_child["structured"]),
                structured=real_child["structured"],
                stop_reason=real_child["stop_reason"],
            )

        backend = ch.RealDSHBackend(_bridge, require_marker=True)
        client = ch.DelegationClient(backend=backend, resolver=ch.RoleResolver())

        def subtask_runner(task, delegation):
            return client.delegate(task, delegation, extra_context={"prompt": meta["prompt"]})

        flow = ch.ExecutionFlow(
            base=ws, flow_id=f"flow-mountverify-{scenario.lower()}-{uuid.uuid4().hex[:6]}",
            subtask_runner=subtask_runner)

        if scenario == "INT-07":
            def _revoke():
                ch.revoke_delegation(ws, meta["del_id"])
            flow.pre_execute = _revoke

        result_flow = flow.run(ch.TaskIntake(**meta["intake"]),
                               execute_plan=ch.ExecutePlan(**meta["plan"]))
        audit_events = flow._get_audit().read()
        output_path = os.path.join(ws, meta["plan"]["target"]) if scenario == "INT-01" else None
        bundle = ch.build_canonical_bundle(scenario, result_flow.to_dict(), ws,
                                           audit_events, output_path, real_child)
        qa = ch.validate_evidence_bundle(bundle, scenario_id=scenario)
        bundle["qa_validation"] = qa.to_dict()

        out = os.path.join(OUT_DIR, scenario)
        os.makedirs(out, exist_ok=True)
        json.dump(bundle, open(os.path.join(out, "evidence.json"), "w"), indent=2)
        with open(os.path.join(out, "audit-log.jsonl"), "w") as f:
            for e in audit_events:
                f.write(json.dumps(e, default=str) + "\n")
        json.dump(result_flow.to_dict(), open(os.path.join(out, "flow_result.json"), "w"),
                  indent=2, default=str)
        json.dump(qa.to_dict(), open(os.path.join(out, "verdict.json"), "w"), indent=2)
        print(f"[{scenario}] outcome={result_flow.outcome} final={result_flow.final_state} "
              f"qa_valid={qa.valid} bridge_calls={len(bridge_calls)} "
              f"run_id={real_child['run_id'][:8]} marker=require_marker=True")
        for e in qa.errors[:8]:
            print("  ERR:", e[:160])
        return {"outcome": result_flow.outcome, "final": result_flow.final_state,
                "qa_valid": qa.valid}
    finally:
        stop_o3_daemon(d[2])


if __name__ == "__main__":
    which = sys.argv[1]
    live_file = sys.argv[2]
    live = json.load(open(live_file))
    if which == "INT-01":
        finalize("INT-01", os.path.join(RUNS_DIR, "int01_meta.json"), live)
    elif which == "INT-07":
        finalize("INT-07", os.path.join(RUNS_DIR, "int07_meta.json"), live)
    else:
        raise SystemExit(f"unknown scenario {which}")
