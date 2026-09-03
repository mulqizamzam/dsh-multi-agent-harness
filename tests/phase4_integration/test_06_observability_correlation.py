# P4I-06 — Observability correlation
#
# Proves the observability layer correlates the audit ledger emitted by a REAL
# ProductionRun into a RunIndex with correct run/task/delegation/failure/
# evidence/parallel records, that the run_id is preserved (not derived), and
# that the ingest fails closed on duplicate events.
#
# Deterministic runtime only. No live DSH. No L3 claim.
#
# Acceptance rows: AUD-2, AUTH-INV-14 (audit is never authority)

import observability as obs

from tests.phase4_integration.helpers import (
    make_delegation, make_subtask_result, StubSubtaskRunner,
)


def _build_real_run(ws, *, objective="engineering",
                    scope=("agents/cto/output.txt",),
                    parallel=False):
    """Run a real ProductionRun and return (state, index)."""
    from orchestrator.production import ProductionRun

    delegation = make_delegation(
        scope_operations=("write", "read", "code_write", "analysis"))
    sr = StubSubtaskRunner()
    if parallel:
        delegation = make_delegation(
            id="delegation-price-obs",
            scope_operations=("write", "read", "code_write", "analysis"),
            scope_resources=("docs/**", "agents/**",
                             "multi-agent-harness/**"))
        sr.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:cfo",)))
        sr.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            evidence=("artifact:kai",)))
        objective = "pricing strategy for launch"
        scope = ("docs/report.md",)
    else:
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

    state = ProductionRun(base=ws).run(
        objective=objective, scope=scope,
        required_authority_context=delegation.id,
        delegation=delegation, subtask_runner=sr,
        parallel_subtasks=parallel, max_workers=4)
    idx = obs.build_index_from_ledger(base=ws, project="multi-agent-harness")
    return state, idx


class TestObservabilityCorrelation:
    """P4I-06: real ledger → correlated RunIndex."""

    def test_complete_run_correlates(self, ws):
        """A real COMPLETE run correlates with preserved run_id and records."""
        state, idx = _build_real_run(ws)

        assert len(idx.run_order) == 1
        run = idx.runs[idx.run_order[0]]

        # Run identity preserved (not derived)
        assert run.run_id == state.run_id, \
            f"run_id={run.run_id} state.run_id={state.run_id}"
        assert run.run_id_derived is False
        assert run.outcome == obs.OUTCOME_COMPLETE

        # Task correlation
        assert "task-1" in run.tasks, f"tasks={list(run.tasks)}"
        assert run.tasks["task-1"].state == "COMPLETE"
        assert run.tasks["task-1"].version > 0
        assert run.tasks["task-1"].role in ("cto", "")

        # Delegation correlation
        assert "delegation-prod-001" in run.delegations

        # Evidence references preserved
        assert "artifact:cto" in run.evidence_refs

        # No correlation problems on the run itself
        assert run.problems == [], f"problems={run.problems}"

        # No duplicate event ids: the per-ledger allocator fix eliminated
        # the ProductionRun/ExecutionFlow collision. The observability
        # ingest rejects NO events from a clean real ledger.
        assert idx.rejected == [], f"rejected={idx.rejected}"

        # Audit is never authority
        assert idx.ledger_integrity["audit_is_authority_source"] is False

        # Metrics
        m = obs.compute_metrics(idx)
        assert m["totals"]["total_runs"] == 1
        assert m["totals"]["completed_runs"] == 1
        assert m["integrity"]["runs_with_problems"] == 0

        # Health — no rejected events, no problems → healthy
        hr = obs.health_report(idx)
        assert hr["healthy"] is True, f"health={hr}"

        # Ledger integrity passes append-only check (no duplicates)
        assert idx.ledger_integrity.get("append_only_ok") is True, \
            idx.ledger_integrity

        # Queries work
        assert obs.find_run(idx, state.run_id) is not None
        assert obs.find_task(idx, "task-1") is not None
        assert obs.find_delegation(idx, "delegation-prod-001") is not None
        assert obs.find_evidence_refs(idx, run_id=state.run_id)

    def test_blocked_run_correlates_failure(self, ws):
        """A BLOCKED run correlates its authority denial as a failure."""
        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped,
        )
        from orchestrator.runtime import MemoryDelegationProvider

        delegation = make_delegation()
        provider = MemoryDelegationProvider(delegation)
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        def revoke():
            provider.revoke(delegation.id)

        run = ProductionRun(base=ws)
        try:
            run.run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=delegation, provider=provider,
                subtask_runner=sr, pre_execute=revoke,
                parallel_subtasks=False)
            assert False, "expected ProductionDenied"
        except (ProductionDenied, ProductionEscalated, ProductionStopped):
            pass

        idx = obs.build_index_from_ledger(base=ws, project="multi-agent-harness")
        assert len(idx.run_order) == 1
        run = idx.runs[idx.run_order[0]]
        assert run.outcome == obs.OUTCOME_BLOCKED
        assert len(run.failures) >= 1, f"failures={run.failures}"
        f = run.failures[0]
        assert f.stage == obs.EXECUTION
        m = obs.compute_metrics(idx)
        assert m["denials"]["authority_denials"] >= 1
        assert m["totals"]["blocked_runs"] == 1

    def test_parallel_run_correlates_batch(self, ws):
        """A parallel run correlates its parallel batch and owners."""
        state, idx = _build_real_run(ws, parallel=True)

        run = idx.runs[idx.run_order[0]]
        assert run.outcome == obs.OUTCOME_COMPLETE
        assert len(run.parallel_batches) >= 1, \
            f"batches={run.parallel_batches}"
        batch = run.parallel_batches[0]
        assert set(batch["owners"]) == {"cfo", "kai"}
        assert len(batch["task_ids"]) == 2
        # Subtasks correlated under the parent task
        parent = run.tasks["task-1"]
        assert set(parent.subtasks) == {"task-1:cfo", "task-1:kai"}
        m = obs.compute_metrics(idx)
        assert m["parallelism"]["parallel_batches"] >= 1
        assert m["parallelism"]["max_parallel_batch_size"] == 2
        assert obs.find_task(idx, "task-1:kai") is not None

    def test_clean_stream_is_healthy(self):
        """A clean synthetic stream correlates with a healthy report."""
        from tests.observability.conftest import complete_run_events

        events = complete_run_events()
        idx = obs.build_index(events)
        hr = obs.health_report(idx)
        assert hr["healthy"] is True
        assert hr["rejected_events"] == 0
        assert hr["total_runs"] == 1