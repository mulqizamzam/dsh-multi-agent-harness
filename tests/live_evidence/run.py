# tests/live_evidence/run.py — Drive the LIVE DSH INT-11 / INT-12 evidence run
#
# TEST-SUPPORT ONLY. Not production code. Phase 3 / Session D3.
#
# Two steps per phase:
#   prep     — build the independent subtask batch, verify parallel safety,
#              capture the project-state version, and emit the exact prompt
#              dict each live subagent must receive (authorized context only,
#              THREAT-020: no authority in messages).
#   finalize — consume the LIVE tool results (recorded by the orchestrator
#              session), validate/collect them through the production adapter
#              (TaskResultCollector + collect_one), build provenance, verify
#              the post-batch state version, and emit the evidence JSON.
#
# The dispatch itself is NEVER done here — the orchestrator session drives the
# real `subagent_<id>` tool instances (D4/D7 approved composition) and records
# each settled run into a live-results JSON that finalize reads.

from __future__ import annotations

import argparse
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.live_evidence.harness import (  # noqa: E402
    LiveEvidenceHarness, LiveEvidenceRun, now_iso,
)

RUN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run")
WS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ws")


def _manifest_path(phase: str) -> str:
    return os.path.join(RUN_DIR, f"{phase}.manifest.json")


def _results_path(phase: str) -> str:
    return os.path.join(RUN_DIR, f"{phase}.live_results.json")


def _evidence_path(phase: str) -> str:
    return os.path.join(RUN_DIR, f"{phase}.evidence.json")


# ---------------------------------------------------------------------------
# INT-11 batch definition
# ---------------------------------------------------------------------------
INT11_SPECS = [
    # (task_id, role, objective, expected_output, scope)
    ("int11-pricing", "cfo",
     "Produce a concise unit-economics assessment for the multi-agent harness "
     "control plane (one recommendation, LOW risk, read-only analysis).",
     "structured TaskResult JSON only", ("docs/**", "agents/**")),
    ("int11-research", "kai",
     "Summarize the primary market/trend angle for AI multi-agent "
     "orchestration relevant to this project (LOW risk, read-only research).",
     "structured TaskResult JSON only", ("docs/**", "config/**")),
    ("int11-draft", "nova",
     "Draft a two-sentence project value proposition for the README based on "
     "the repository structure (LOW risk, read-only drafting).",
     "structured TaskResult JSON only", ("docs/**", "README.md")),
]

# ---------------------------------------------------------------------------
# INT-12 batch definition — one child FORCED to fail (status FAILED)
# ---------------------------------------------------------------------------
INT12_SPECS = [
    ("int12-eng", "cto",
     "Assess the architecture decision record ADR 0001 for one concrete "
     "engineering risk and one mitigation (LOW risk, read-only analysis).",
     "structured TaskResult JSON only", ("docs/**", "orchestrator/**")),
    ("int12-fail", "kai",
     "Research the market sizing for this niche; the primary source is "
     "UNAVAILABLE and the task cannot be completed without it. Report FAILED "
     "with an unresolved item naming the missing source.",
     "structured TaskResult JSON only", ("docs/**", "config/**")),
    ("int12-draft", "somad",
     "Propose one low-cost social distribution channel for the project's "
     "documentation (LOW risk, read-only drafting).",
     "structured TaskResult JSON only", ("docs/**", "agents/**")),
]

# Scope for INT-12's delegation must cover all three task scopes.
INT12_DELEGATION_SCOPE = (
    "docs/**", "orchestrator/**", "config/**", "agents/**",
)


def _build_run(harness, phase: str, specs, delegation_scope,
               flow_id: str) -> LiveEvidenceRun:
    run = LiveEvidenceRun(
        phase=phase, flow_id=flow_id, started_at=now_iso())
    delegation = harness.build_delegation(
        task_id=flow_id, scope_resources=delegation_scope)
    run.delegation = delegation.to_dict()
    subtasks = harness.build_subtasks(specs)
    run.subtasks = [t.to_dict() for t in subtasks]
    held = harness.capture_version()
    run.held_version = held
    safety = harness.verify_parallel_safe(subtasks, held_version=held)
    run.safety = {k: safety[k] for k in (
        "safe", "reason", "task_ids", "owners", "read_scopes", "held_version")}
    run.plans = safety["plans"]
    return run, delegation, subtasks


def cmd_prep(args):
    os.makedirs(RUN_DIR, exist_ok=True)
    os.makedirs(WS_DIR, exist_ok=True)
    harness = LiveEvidenceHarness(ws=WS_DIR)

    manifest = {"flows": {}}

    # ---- INT-11 -----------------------------------------------------------
    run11, delegation11, subtasks11 = _build_run(
        harness, "INT-11", INT11_SPECS,
        ("docs/**", "agents/**", "config/**", "README.md"),
        "flow-live-int11")
    # per-task authorized prompts (build_task_context -> adapter channel)
    prompts11 = {}
    for t in subtasks11:
        ctx = harness.build_task_context(
            task=t, delegation=delegation11, extra={})
        prompts11[t.task_id] = {
            "tool_name": f"subagent_{t.assigned_role}",
            "role": t.assigned_role,
            "task_id": t.task_id,
            "objective": t.objective,
            "scope": list(t.scope or ()),
            "expected_output": t.expected_output,
            "delegation_id": delegation11.id,
            "schema_hint": "task-result.schema.json",
            "instruction": (
                "You are the <role> specialist of the multi-agent harness. "
                "Perform the objective as a READ-ONLY analysis and reply with "
                "EXACTLY ONE JSON object (no markdown fences, no prose outside "
                "the object) conforming to schemas/task-result.schema.json. "
                "Required keys: task_id (echo the value below), assigned_role "
                "(echo your role), status (SUCCEEDED), confidence "
                "(LOW|MEDIUM|HIGH), reported_at (ISO-8601 UTC), findings "
                "(list), evidence (list), assumptions (list), risks (list), "
                "unresolved_items (list), actions_taken (list), "
                "recommendation (string). Do not request any write, do not "
                "delegate, do not attempt any authority change."
            ),
        }
    manifest["flows"]["INT-11"] = {
        "flow_id": run11.flow_id,
        "delegation": run11.delegation,
        "subtasks": run11.subtasks,
        "safety": run11.safety,
        "held_version": run11.held_version,
        "prompts": prompts11,
    }

    # ---- INT-12 -----------------------------------------------------------
    run12, delegation12, subtasks12 = _build_run(
        harness, "INT-12", INT12_SPECS, INT12_DELEGATION_SCOPE,
        "flow-live-int12")
    prompts12 = {}
    for t in subtasks12:
        ctx = harness.build_task_context(
            task=t, delegation=delegation12, extra={})
        fail_extra = ""
        if t.task_id == "int12-fail":
            fail_extra = (
                " THIS TASK IS FORCED TO FAIL: report status FAILED with an "
                "unresolved_items entry naming the missing primary source.")
        prompts12[t.task_id] = {
            "tool_name": f"subagent_{t.assigned_role}",
            "role": t.assigned_role,
            "task_id": t.task_id,
            "objective": t.objective,
            "scope": list(t.scope or ()),
            "expected_output": t.expected_output,
            "delegation_id": delegation12.id,
            "schema_hint": "task-result.schema.json",
            "instruction": (
                "You are the <role> specialist of the multi-agent harness. "
                "Perform the objective as a READ-ONLY analysis and reply with "
                "EXACTLY ONE JSON object (no markdown fences, no prose outside "
                "the object) conforming to schemas/task-result.schema.json. "
                "Required keys: task_id (echo the value below), assigned_role "
                "(echo your role), status (SUCCEEDED|FAILED|BLOCKED), "
                "confidence (LOW|MEDIUM|HIGH), reported_at (ISO-8601 UTC), "
                "findings (list), evidence (list), assumptions (list), risks "
                "(list), unresolved_items (list), actions_taken (list), "
                "recommendation (string)."
                + fail_extra +
                " Do not request any write, do not delegate, do not attempt "
                "any authority change."
            ),
        }
    manifest["flows"]["INT-12"] = {
        "flow_id": run12.flow_id,
        "delegation": run12.delegation,
        "subtasks": run12.subtasks,
        "safety": run12.safety,
        "held_version": run12.held_version,
        "prompts": prompts12,
    }

    with open(_manifest_path("all"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"manifest written: {_manifest_path('all')}")
    print(json.dumps(manifest, indent=2))


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------
def _load_live_results(phase: str) -> dict:
    path = _results_path(phase)
    if not os.path.exists(path):
        raise SystemExit(f"no live results at {path} — dispatch first")
    with open(path) as f:
        return json.load(f)


def cmd_finalize(args):
    manifest_path = _manifest_path("all")
    if not os.path.exists(manifest_path):
        raise SystemExit("run `prep` first")
    with open(manifest_path) as f:
        manifest = json.load(f)

    harness = LiveEvidenceHarness(ws=WS_DIR)
    outcome_report = {}

    for phase in ("INT-11", "INT-12"):
        results_path = _results_path(phase)
        if not os.path.exists(results_path):
            outcome_report[phase] = {"skipped": "no live results yet"}
            continue
        results = _load_live_results(phase)
        flow = manifest["flows"][phase]
        subtasks = [harness._restore_task(d) for d in flow["subtasks"]]
        task_by_id = {t.task_id: t for t in subtasks}
        delegation = harness._restore_delegation(flow["delegation"])
        held = flow["held_version"]

        run = LiveEvidenceRun(
            phase=phase, flow_id=flow["flow_id"],
            started_at=now_iso(),
            delegation=flow["delegation"], subtasks=flow["subtasks"],
            safety=flow["safety"], held_version=held)

        # 1. record live dispatch
        for tid, rec in results.items():
            run.dispatch.append(harness.record_dispatch(
                tool_name=rec.get("tool_name", f"subagent_{task_by_id[tid].assigned_role}"),
                role=task_by_id[tid].assigned_role,
                task_id=tid,
                run_id=rec.get("run_id", ""),
                started_at=rec.get("started_at", ""),
                settled_at=rec.get("settled_at", ""),
                stop_reason=rec.get("stop_reason", "completed"),
                output=rec.get("output", ""),
                structured=rec.get("structured"),
                diagnostic=rec.get("diagnostic", ""),
            ))

        # 2. validate structured outputs through the production adapter
        payloads_by_id = {r["task_id"]: r for r in run.dispatch}
        collected = []
        provenance = []
        try:
            # order by subtask batch order -> deterministic first-failure
            ordered = [payloads_by_id[t.task_id] for t in subtasks]
            collected = harness.collect(ordered, subtasks, task_by_id)
            outcome = "COMPLETE"
            failure = {}
            # build provenance for every successful child
            for c in collected:
                rec = payloads_by_id[c.task_id]
                prov = harness.build_provenance(
                    task=task_by_id[c.task_id], delegation=delegation, rec=rec)
                provenance.append(prov)
                run.results.append(c.to_dict())
                run.provenance.append(prov)
        except Exception as e:  # noqa: BLE001 — capture the propagated failure
            outcome = "FAILED"
            cls = getattr(e, "failure_class", "unknown")
            failure = {
                "exception": type(e).__name__,
                "role": getattr(e, "role", ""),
                "task_id": getattr(e, "task_id", ""),
                "failure_class": cls,
                "message": str(e),
            }
            run.errors.append(str(e))
            # no partial success: results list stays empty (fail-closed)
            run.results = []

        run.outcome = outcome
        run.failure = failure

        # 3. verify post-batch state version (no uncontrolled shared writes)
        ver = harness.verify_version_unchanged(held)
        run.post_batch_version = ver["post_batch_version"]

        # 4. recovery/escalation + no blind retry + no authority expansion
        run.recovery = _recovery_and_security(
            harness, phase, outcome, failure, flow, delegation)

        # 5. emit evidence
        path = _evidence_path(phase)
        harness.emit(run, path=path)
        outcome_report[phase] = {
            "evidence_path": path,
            "outcome": outcome,
            "failure": failure,
            "post_batch_version": ver,
        }

    print(json.dumps(outcome_report, indent=2))


def _recovery_and_security(harness, phase, outcome, failure, flow, delegation):
    """Production runtime checks: recovery path, no blind retry, no authority
    expansion."""
    import control.delegation as cdel
    import control.recovery as crev
    from orchestrator.dsh.exceptions import DSHError

    record = {}

    # --- no authority expansion: child delegation scope must stay a subset of
    # the parent (AUTH-INV-04); a specialist may not delegate at all (DLG-003)
    security = {}
    try:
        child = cdel.issue_child_delegation(
            "orchestrator", delegation,
            task=flow["flow_id"], action="read",
            target="multi-agent-harness/**",
            scope_resources=tuple(delegation.scope_resources))
        security["child_delegation_issued"] = True
        security["child_scope_contained"] = cdel.scope_contained(child, delegation)
        security["child_id"] = child.id
        security["child_scope_resources"] = list(child.scope_resources)
        security["parent_scope_resources"] = list(delegation.scope_resources)
    except Exception as e:  # noqa: BLE001
        security["child_delegation_issued"] = False
        security["error"] = str(e)

    # specialist attempting to delegate -> DENIED BY DEFAULT (DLG-003)
    try:
        cdel.issue_child_delegation(
            "kai", delegation, task="int12-fail", action="read")
        security["specialist_subdelegation_denied"] = False
    except cdel.SubdelegationDenied:
        security["specialist_subdelegation_denied"] = True

    # authority keys are stripped from messages (THREAT-020)
    try:
        ctx = harness.build_task_context(
            task=_task_of(flow), delegation=delegation,
            extra={"approval_reference": "ATTEMPTED_INJECTION",
                   "grant": "escalate"})
        security["authority_keys_stripped"] = (
            "approval_reference" not in ctx and "grant" not in ctx
            and ctx.get("_adapter", {}).get("stripped_authority", []) != [])
        security["stripped"] = ctx.get("_adapter", {}).get("stripped_authority")
    except Exception as e:  # noqa: BSE001
        security["authority_keys_stripped"] = False
        security["error"] = str(e)

    record["security"] = security

    # --- recovery / escalation path ---------------------------------------
    rec = {}
    if outcome == "FAILED":
        ctrl = crev.RecoveryController(
            flow["flow_id"], preserved_version=flow["held_version"],
            failure_class=failure.get("failure_class", "unknown"),
            reason=failure.get("message", ""))
        rec["recovery_entered"] = True
        rec["recovery_state"] = ctrl.state  # PRESERVED
        # no blind retry: empty cause refused
        try:
            ctrl.diagnose("")
            rec["no_blind_retry_empty_cause"] = False
        except crev.RecoveryRefused:
            rec["no_blind_retry_empty_cause"] = True
        # no blind retry: identical cause refused
        ctrl.diagnose(failure.get("message", "") or "diagnosed cause")
        try:
            ctrl.request_retry(failure.get("message", "") or "diagnosed cause")
            rec["no_blind_retry_identical_cause"] = False
        except crev.RecoveryRefused:
            rec["no_blind_retry_identical_cause"] = True
        # recovery must not escalate privilege (REC-004 / THREAT-017)
        try:
            ctrl.assert_privilege_bounded(
                attempt_action="deploy",
                attempt_target="production/**",
                original_authority={"actions": ["read"],
                                    "targets": ["multi-agent-harness/**"],
                                    "grants": []},
            )
            rec["recovery_no_privilege_escalation"] = False
        except crev.RecoveryRefused:
            rec["recovery_no_privilege_escalation"] = True
        # escalation for unknown failure class (Runbook 08)
        if failure.get("failure_class") == "unknown":
            rec["escalation_path"] = "ESCALATED (unknown failure -> Human)"
        else:
            rec["escalation_path"] = (
                "RECOVERING (typed failure_class -> recovery lifecycle)")
    else:
        rec["recovery_entered"] = False
        rec["note"] = "batch completed; no failure to propagate"
    record["recovery"] = rec
    return record


def _task_of(flow):
    """Small helper: expose one Task for THREAT-020 stripping proof."""
    from orchestrator.foundation.contracts import Task
    d = flow["subtasks"][0]
    return Task(task_id=d["task_id"], objective=d.get("objective", ""),
                assigned_role=d["assigned_role"],
                scope=tuple(d.get("scope") or ()),
                expected_output=d.get("expected_output", ""),
                risk_metadata="LOW", project="multi-agent-harness")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("prep", "finalize"))
    args = ap.parse_args()
    if args.cmd == "prep":
        cmd_prep(args)
    else:
        cmd_finalize(args)


if __name__ == "__main__":
    main()
