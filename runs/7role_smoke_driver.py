#!/usr/bin/env python3
"""Canonical 7-role smoke driver (one bounded mission, all 7 specialists).

Runs ONE bounded mission through the EXISTING organization layer:
  W0 nova+cfo -> W1 cto -> W2 kai -> W3 badsector+somad -> W4 zeko -> ROOT.

The handoff payloads are the verbatim structured outputs recorded from the
seven real specialist subagent runs (tests/organization/fixtures/7role_*.json).
The MissionRunner executes through ParallelExecutor + DelegationClient seam
with a recorder backend that returns the collected TaskResults.

Artifacts under runs/7role_smoke/:
  mission_metrics.json    — MissionMetrics.to_dict()
  root_verdict.json       — RootVerdict.to_dict()
  handoffs.json           — per-role TypedHandoff dicts
  smoke_log.txt           — wave-by-wave dispatch log

No repository mutation: mission artifacts live only under runs/7role_smoke/.
"""
from __future__ import annotations

import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import Delegation, TaskResult
from orchestrator.foundation.state import ProjectState  # noqa: F401 (contract reference)
from orchestrator.organization import (
    MissionTask,
    MissionPacket,
    collect_from_runner,
)
from orchestrator.organization.runner import MissionRunner

MISSION_ID = "mission-7role-smoke-0001"
FIXTURE_DIR = os.path.join(_PROJECT_ROOT, "tests", "organization", "fixtures")
OUT_DIR = os.path.join(_PROJECT_ROOT, "runs", "7role_smoke")

ROLE_ORDER = ("nova", "cfo", "cto", "kai", "badsector", "somad", "zeko")


def _load_fixtures() -> dict:
    """Load the recorded subagent structured outputs, keyed by role."""
    fx = {}
    for role in ROLE_ORDER:
        path = os.path.join(FIXTURE_DIR, f"7role_{role}.json")
        with open(path) as f:
            fx[role] = json.load(f)
    return fx


def build_mission() -> MissionPacket:
    tasks = (
        MissionTask(task_id="nova", mission_id=MISSION_ID, owner="nova", role="nova",
                    objective="facts/research: bounded smoke context for CTO decision",
                    context_refs=("docs/AGENTS.md",)),
        MissionTask(task_id="cfo", mission_id=MISSION_ID, owner="cfo", role="cfo",
                    objective="resource/cost recommendation for one bounded mission"),
        MissionTask(task_id="cto", mission_id=MISSION_ID, owner="cto", role="cto",
                    objective="technical decision: reuse organization layer as-is",
                    depends_on=("nova",), context_refs=("nova",)),
        MissionTask(task_id="kai", mission_id=MISSION_ID, owner="kai", role="kai",
                    objective="implementation: harmless smoke artifact under runs/",
                    depends_on=("cto",), context_refs=("cto",),
                    required_evidence=("test", "artifact")),
        MissionTask(task_id="bad", mission_id=MISSION_ID, owner="badsector",
                    role="badsector", objective="adversarial review of kai artifact",
                    depends_on=("kai",), context_refs=("kai",)),
        MissionTask(task_id="som", mission_id=MISSION_ID, owner="somad",
                    role="somad", objective="independent verification of kai artifact",
                    depends_on=("kai",), context_refs=("kai",)),
        MissionTask(task_id="zeko", mission_id=MISSION_ID, owner="zeko", role="zeko",
                    objective="integration/release readiness",
                    depends_on=("bad", "som")),
    )
    return MissionPacket(mission_id=MISSION_ID,
                         objective="7-role bounded smoke: metrics + verdict",
                         tasks=tasks)


def make_backend(fx, log):
    """Recorder backend: returns the recorded TaskResult per role.

    Also writes the harmless smoke artifact kai owns (runs/7role_smoke/), so
    the artifact evidence ref is real on disk.
    """
    def backend(task, delegation, ctx):
        role = task.assigned_role
        rec = fx[role]
        log.append(f"dispatch role={role} task={task.task_id} "
                   f"deps={getattr(task, 'depends_on', getattr(task, 'dependencies', ()))} "
                   f"wave_ctx_keys={sorted(ctx)[:4]}")
        if role == "kai":
            art = os.path.join(OUT_DIR, "smoke_artifact.md")
            if not os.path.exists(art):
                with open(art, "w") as f:
                    f.write(rec.get("artifact", "# smoke artifact\n"))
            log.append(f"kai wrote artifact {os.path.relpath(art, _PROJECT_ROOT)}")
        return TaskResult(
            task_id=task.task_id,
            assigned_role=role,
            status=rec["status"],
            findings=tuple(rec["findings"]),
            evidence=tuple(rec.get("evidence", ())),
            risks=tuple(rec.get("risks", ())),
            recommendation=rec.get("recommendation", ""),
            confidence=rec.get("confidence", "MEDIUM"),
            unresolved_items=tuple(rec.get("unresolved_items", ())),
            actions_taken=tuple(rec.get("actions_taken", ())),
        )
    return backend


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    fx = _load_fixtures()
    log: list[str] = []

    # The audit ledger routes through the O3 daemon (fail-closed, no
    # direct-fs fallback) — start the sanctioned per-run daemon rooted at
    # the smoke output dir, exactly as tests/conftest.start_o3_daemon does.
    sys.path.insert(0, os.path.join(_PROJECT_ROOT, "tests"))
    from conftest import start_o3_daemon, stop_o3_daemon
    _wsdir, _client, daemon = start_o3_daemon(OUT_DIR)
    log.append(f"o3 daemon started at {_wsdir}")

    mission = build_mission()
    delegation = Delegation(
        id=f"delegation-{MISSION_ID}", principal="human",
        delegate="orchestrator", project="multi-agent-harness",
        task="7role-smoke", action="write", target="runs/7role_smoke/**",
        environment="dev", scope_operations=("read", "write", "test"),
        scope_resources=("runs/7role_smoke/**",), status="ACTIVE", version=1,
    )
    backend = make_backend(fx, log)
    state = ProjectState(project="multi-agent-harness")
    runner = MissionRunner(delegation=delegation, base=str(OUT_DIR),
                           runner=backend, project="multi-agent-harness")
    verdict = runner.run(mission)
    metrics = collect_from_runner(runner, mission, verdict)

    # ---- write artifacts ------------------------------------------------
    with open(os.path.join(OUT_DIR, "mission_metrics.json"), "w") as f:
        json.dump(metrics.to_dict(), f, indent=2)
    with open(os.path.join(OUT_DIR, "root_verdict.json"), "w") as f:
        json.dump(verdict.to_dict(), f, indent=2)
    handoffs = {tid: ho.to_dict() if hasattr(ho, "to_dict") else vars(ho)
                for tid, ho in runner.handoffs.items()}
    with open(os.path.join(OUT_DIR, "handoffs.json"), "w") as f:
        json.dump(handoffs, f, indent=2, default=str)
    with open(os.path.join(OUT_DIR, "smoke_log.txt"), "w") as f:
        f.write("\n".join(log) + "\n")
    with open(os.path.join(OUT_DIR, "mission_packet.json"), "w") as f:
        json.dump(mission.to_dict(), f, indent=2)

    print(f"MISSION_ID: {MISSION_ID}")
    print(f"VERDICT: {verdict.outcome} — {verdict.reason}")
    print(f"waves_executed={runner.waves_executed} "
          f"parallel_peak={runner.parallel_peak_observed}")
    print(f"metrics: tasks={metrics.task_count} completed={metrics.completed_tasks} "
          f"blocked={metrics.blocked_tasks} failed={metrics.failed_tasks} "
          f"rework={metrics.rework_cycles} "
          f"roles_invoked={','.join(metrics.roles_invoked)} "
          f"roles_completed={','.join(metrics.roles_completed)} "
          f"verif_pass={metrics.verification_passed} "
          f"verif_fail={metrics.verification_failed} "
          f"duration_ms={metrics.duration_ms:.1f}")
    print(f"artifacts under runs/7role_smoke/: "
          f"{sorted(os.listdir(OUT_DIR))}")
    stop_o3_daemon(daemon)
    return 0 if verdict.outcome == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
