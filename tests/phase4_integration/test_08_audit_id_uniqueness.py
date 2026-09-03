# P4I-08 — Audit event-id uniqueness (defect closure)
#
# Proves the per-ledger event-id allocator closes the dual-audit duplicate-id
# defect. Test scenarios (per the defect-closure requirement):
#
#   1. ProductionRun + ExecutionFlow on the same ledger → all-unique ids,
#      append-only integrity, hash-chain integrity, observability single run.
#   2. Two RuntimeAudit instances on one ledger → sequential, continuing.
#   3. Concurrent writers (threaded) → no id collisions.
#   4. Duplicate attempt → verify_append_only + observability still detect a
#      deliberately injected duplicate (fail-closed NOT weakened).
#   5. Restart/reopen → new RuntimeAudit continues after existing max id.
#   6. Append-only integrity → verify_append_only passes on a real ledger.
#   7. Hash-chain integrity → compute_chain + verify_chain on a real ledger.
#   8. Observability reconstruction → single run, healthy, no rejects.
#
# Deterministic runtime only. No live DSH. No L3 claim.
#
# Invariants: AUD-1, AUD-2, AUTH-INV-14, append-only + hash-chain integrity,
# fail-closed duplicate detection preserved.

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.phase4_integration.helpers import (
    make_delegation, make_subtask_result, StubSubtaskRunner,
)


# ---------------------------------------------------------------------------
# Scenario 1: ProductionRun + ExecutionFlow on the same ledger
# ---------------------------------------------------------------------------

class TestProductionFlowUniqueIds:
    """P4I-08a: a real ProductionRun produces 31 unique event ids."""

    def test_all_event_ids_unique(self, ws):
        from orchestrator.production import ProductionRun
        from audit.helpers.append_log import read_events_strict, verify_append_only
        from audit.helpers.integrity import verify_chain

        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=make_delegation(), subtask_runner=sr,
            parallel_subtasks=False)
        assert state.outcome == "complete"

        ledger = os.path.join(ws, "audit", "multi-agent-harness",
                              "events.jsonl")
        events = read_events_strict(ledger)
        ids = [e["event_id"] for e in events]
        assert len(ids) == len(set(ids)), f"duplicate ids: {[i for i in ids if ids.count(i) > 1]}"
        assert len(ids) >= 25, f"only {len(ids)} events"

    def test_append_only_integrity(self, ws):
        from orchestrator.production import ProductionRun
        from audit.helpers.append_log import verify_append_only

        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=make_delegation(), subtask_runner=sr,
            parallel_subtasks=False)

        ledger = os.path.join(ws, "audit", "multi-agent-harness",
                              "events.jsonl")
        ok, problems = verify_append_only(ledger)
        assert ok, f"append_only problems: {problems}"

    def test_hash_chain_integrity(self, ws):
        from orchestrator.production import ProductionRun
        from audit.helpers.integrity import compute_chain, verify_chain

        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=make_delegation(), subtask_runner=sr,
            parallel_subtasks=False)

        ledger = os.path.join(ws, "audit", "multi-agent-harness",
                              "events.jsonl")
        # compute + persist sidecar, then verify
        compute_chain(ledger)
        verify_chain(ledger)  # raises on mismatch

    def test_observability_reconstruction(self, ws):
        from orchestrator.production import ProductionRun
        import observability as obs

        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=make_delegation(), subtask_runner=sr,
            parallel_subtasks=False)

        idx = obs.build_index_from_ledger(
            base=ws, project="multi-agent-harness")
        assert len(idx.run_order) == 1
        run = idx.runs[idx.run_order[0]]
        assert run.outcome == obs.OUTCOME_COMPLETE
        assert run.run_id == state.run_id, \
            f"run_id={run.run_id} state.run_id={state.run_id}"
        assert run.run_id_derived is False
        assert idx.rejected == [], f"rejected={[(p.kind, p.message) for p in idx.rejected]}"
        assert run.problems == [], f"problems={run.problems}"
        hr = obs.health_report(idx)
        assert hr["healthy"] is True, f"health={hr}"


# ---------------------------------------------------------------------------
# Scenario 2: Two RuntimeAudit instances on the same ledger (sequential)
# ---------------------------------------------------------------------------

class TestMultiInstanceSharedLedger:
    """P4I-08b: two RuntimeAudit writing to the same ledger share a counter."""

    def test_instances_share_sequence(self, ws):
        from orchestrator.runtime.audit import RuntimeAudit

        a = RuntimeAudit(base=ws, project="multi-agent-harness")
        b = RuntimeAudit(base=ws, project="multi-agent-harness")

        e1 = a.emit("flow_started", action="run", target="test")
        e2 = b.emit("intake_recorded", action="intake", target="test",
                    task_id="task-1")
        e3 = a.emit("gate_risk", action="risk_gate", target="test",
                    task_id="task-1", result="allowed")

        ids = [e1, e2, e3]
        assert len(set(ids)) == 3, f"non-unique ids: {ids}"
        # Monotonic: e1 < e2 < e3
        seqs = [int(e.split("-")[1]) for e in ids]
        assert seqs == sorted(seqs), f"non-monotonic seqs: {seqs}"
        assert seqs[0] >= 1  # started correctly
        assert seqs[-1] == seqs[0] + 2

    def test_new_instance_continues_from_max(self, ws):
        """A new RuntimeAudit created after prior emits continues the
        sequence (no reset to 1)."""
        from orchestrator.runtime.audit import RuntimeAudit

        a = RuntimeAudit(base=ws, project="multi-agent-harness")
        e1 = a.emit("flow_started", action="run", target="test")
        e2 = a.emit("result_collected", action="collect", target="test",
                    task_id="task-1", result="recorded",
                    extra={"role": "cto", "status": "SUCCEEDED"})

        b = RuntimeAudit(base=ws, project="multi-agent-harness")
        e3 = b.emit("gate_authority", action="authority_gate", target="test",
                    task_id="task-1", authority_source="deleg-1",
                    result="allowed")

        seqs = [int(e.split("-")[1]) for e in (e1, e2, e3)]
        assert seqs == sorted(seqs), f"non-monotonic: {seqs}"
        assert seqs == [1, 2, 3]


# ---------------------------------------------------------------------------
# Scenario 3: Concurrent writers (threaded)
# ---------------------------------------------------------------------------

class TestConcurrentWriters:
    """P4I-08c: concurrent RuntimeAudit emit calls produce unique ids."""

    def test_threaded_concurrent_emits_unique(self, ws):
        from orchestrator.runtime.audit import RuntimeAudit

        audit = RuntimeAudit(base=ws, project="multi-agent-harness")
        n_events = 48
        n_threads = 8
        per_thread = n_events // n_threads  # 6

        def do_emits(count):
            return [audit.emit(
                "flow_started", action="run", target="concurrent",
                result="recorded",
            ) for _ in range(count)]

        ids = []
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(do_emits, per_thread)
                       for _ in range(n_threads)]
            for f in futures:
                ids.extend(f.result())

        assert len(ids) == n_events
        assert len(set(ids)) == n_events, \
            f"{n_events - len(set(ids))} duplicate(s) among {n_events} concurrent emits"

    def test_two_instances_concurrent_unique(self, ws):
        """Two separate RuntimeAudit instances on the same ledger,
        emitting concurrently from threads, produce unique ids."""
        from orchestrator.runtime.audit import RuntimeAudit

        a = RuntimeAudit(base=ws, project="multi-agent-harness")
        b = RuntimeAudit(base=ws, project="multi-agent-harness")
        n = 25

        def emit_n(inst, count):
            return [inst.emit(
                "flow_started", action="run", target="concurrent2",
                result="recorded",
            ) for _ in range(count)]

        ids = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            fa = pool.submit(emit_n, a, n)
            fb = pool.submit(emit_n, b, n)
            ids.extend(fa.result())
            ids.extend(fb.result())

        assert len(ids) == 2 * n
        assert len(set(ids)) == 2 * n, \
            f"{2*n - len(set(ids))} duplicate(s) among {2*n} concurrent emits"


# ---------------------------------------------------------------------------
# Scenario 4: Duplicate attempt detection (fail-closed NOT weakened)
# ---------------------------------------------------------------------------

class TestDuplicateDetectionPreserved:
    """P4I-08d: a deliberately injected duplicate is still caught fail-closed."""

    def test_verify_append_only_detects_duplicate(self, ws):
        """Direct-filesystem duplicate injection (bypassing the daemon) is
        still detected by verify_append_only. After O3 Phase B, the daemon
        enforces idempotency at write-time, so we inject a raw duplicate
        at the filesystem level to simulate a tamper that bypasses the
        daemon."""
        from orchestrator.runtime.audit import RuntimeAudit
        from audit.helpers.append_log import verify_append_only
        import json

        # Emit one event normally (through the daemon)
        a = RuntimeAudit(base=ws, project="multi-agent-harness")
        eid = a.emit("flow_started", action="run", target="test")

        # Inject a duplicate at the filesystem level (bypassing the daemon
        # idempotency gate) to verify read-time detection still works.
        ledger = os.path.join(ws, "audit", "multi-agent-harness",
                              "events.jsonl")
        with open(ledger, "a") as f:
            f.write(json.dumps({"event_id": eid, "event_class": "fake",
                                "actor": "test", "action": "replay",
                                "target": "test", "project": "test",
                                "result": "recorded",
                                "timestamp": "2026-09-01T00:00:00Z"}) + "\n")

        ok, problems = verify_append_only(ledger)
        assert not ok, "expected duplicate detection to flag the replay"
        assert any("duplicate" in p.lower() for p in problems), \
            f"no duplicate message in problems: {problems}"

    def test_observability_rejects_genuine_duplicate(self, ws):
        """A ledger with a genuine duplicate event_id (injected at the
        filesystem level, bypassing the daemon idempotency) still triggers
        DUPLICATE_EVENT rejection in observability (fail-closed)."""
        from orchestrator.runtime.audit import RuntimeAudit
        import observability as obs
        import json

        a = RuntimeAudit(base=ws, project="multi-agent-harness")
        eid = a.emit("flow_started", action="run", target="test")

        # Inject duplicate at filesystem level (bypassing daemon)
        ledger = os.path.join(ws, "audit", "multi-agent-harness",
                              "events.jsonl")
        with open(ledger, "a") as f:
            f.write(json.dumps({"event_id": eid, "event_class": "fake",
                                "actor": "test", "action": "replay",
                                "target": "test", "project": "multi-agent-harness",
                                "result": "recorded",
                                "timestamp": "2026-09-01T00:00:01Z"}) + "\n")

        idx = obs.build_index_from_ledger(
            base=ws, project="multi-agent-harness")
        rejected_kinds = [p.kind for p in idx.rejected]
        assert "DUPLICATE_EVENT" in rejected_kinds, \
            f"expected DUPLICATE_EVENT rejection, got: {rejected_kinds}"


# ---------------------------------------------------------------------------
# Scenario 5: Restart/reopen ledger
# ---------------------------------------------------------------------------

class TestRestartReopenLedger:
    """P4I-08e: a new RuntimeAudit on an existing ledger continues the
    sequence after the max event id already on disk (simulating a process
    restart that reads the ledger to seed the counter)."""

    def test_seeds_from_existing_ledger(self, ws):
        from audit.helpers.append_log import read_events
        from control.execution_gate import audit_append
        from orchestrator.runtime.audit import RuntimeAudit

        # Write events DIRECTLY to the ledger (bypassing RuntimeAudit
        # so the in-memory registry has no entry for this path — simulates
        # a FRESH process reopening an existing ledger).
        path = "audit/multi-agent-harness/events.jsonl"
        for i in range(3):
            audit_append(
                path,
                {"event_id": f"event-{i + 5:06d}",
                 "timestamp": "2026-09-01T00:00:00Z",
                 "event_class": "flow_started", "actor": "test",
                 "action": "run", "target": "pre-existing",
                 "project": "multi-agent-harness",
                 "result": "recorded", "evidence": [],
                 "agent_reported": None},
                base=ws)

        # Now create a NEW RuntimeAudit — this should seed from the ledger's
        # max event id (5+3-1 = 7) and start at event-000008.
        audit = RuntimeAudit(base=ws, project="multi-agent-harness")
        eid = audit.emit("flow_started", action="run", target="reopen")
        assert eid == "event-000008", \
            f"expected event-000008 after 3 pre-existing events, got {eid}"

        # Verify the ledger has all events (3 pre-existing + 1 new = 4)
        ledger_path = os.path.join(ws, path)
        events = read_events(ledger_path)
        assert len(events) == 4


# ---------------------------------------------------------------------------
# Scenarios 6-8 are covered by test_08a (append-only, chain, observability)
# The remaining tests below provide additional cross-checks.
# ---------------------------------------------------------------------------

class TestAllocatorDirect:
    """Direct assertions on the allocate_event_id function."""

    def test_allocate_event_id_returns_sequential(self, ws):
        from orchestrator.runtime.audit import allocate_event_id

        s1 = allocate_event_id(ws, "multi-agent-harness")
        s2 = allocate_event_id(ws, "multi-agent-harness")
        assert s2 == s1 + 1, f"got {s2} after {s1}"

    def test_different_projects_independent(self, ws):
        from orchestrator.runtime.audit import allocate_event_id

        s1 = allocate_event_id(ws, "project-a")
        s2 = allocate_event_id(ws, "project-b")
        # Both start at 1 since they're different ledgers
        assert s1 == 1, s1
        assert s2 == 1, s2