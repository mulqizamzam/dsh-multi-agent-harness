"""Correction-pass focused tests for the five contract gaps.

1. EvidenceLedger.record() persists typed evidence (kind:ref) into RuntimeAudit.
2. Root build_verdict() enforces its documented invariant directly.
3. Dependency semantics: external dep allowed only when proven completed.
4. Rework semantics: original prerequisites preserved, dead expression removed.
5. Dead/no-op expression in critic_rework_task removed.

No second audit store, no new scheduler, no L3/release changes.
"""
import os, sys, tempfile
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import Delegation, TaskResult


def _active_delegation(tmp_base=""):
    return Delegation(
        id="delegation-mission-001",
        principal="human", delegate="orchestrator", project="multi-agent-harness",
        task="org-test", action="write", target="repo/src/**",
        environment="dev",
        scope_operations=("read", "write", "test"),
        scope_resources=("repo/**", "mission/**"),
        status="ACTIVE", version=1,
    )


# ---------------------------------------------------------------------------
# 1. EvidenceLedger.record() persists typed evidence into existing audit
# ---------------------------------------------------------------------------
class TestEvidenceLedgerRecordPersists:
    def test_record_persists_evidence_in_audit_event(self):
        from orchestrator.organization.evidence import EvidenceLedger, EVENT_CLASS

        captured = {}

        class FakeAudit:
            def emit(self, event_class, **kw):
                captured["event_class"] = event_class
                captured["evidence_field"] = kw.get("evidence")
                captured["extra"] = kw.get("extra")
                captured["actor"] = kw.get("actor")
                captured["target"] = kw.get("target")
                captured["task_id"] = kw.get("task_id")
                return "event-000001"
            def events_of_class(self, c):
                return []
            def read(self):
                return []

        ledger = EvidenceLedger(FakeAudit())
        ledger.record(
            mission_id="m1", task_id="t1",
            evidence=("test:log.txt", "artifact:patch.diff", "build:ci-123"),
            producer="kai",
        )
        # Event class is org_evidence
        assert captured["event_class"] == EVENT_CLASS
        # Typed evidence must be in audit's evidence field
        assert captured["evidence_field"] == ("test:log.txt", "artifact:patch.diff", "build:ci-123")
        # Also in extra for round-trip
        assert "evidence" in captured["extra"]
        assert sorted(captured["extra"]["evidence"]) == sorted(["test:log.txt", "artifact:patch.diff", "build:ci-123"])
        assert "evidence_kinds" in captured["extra"]
        assert set(captured["extra"]["evidence_kinds"]) == {"test", "artifact", "build"}
        assert captured["extra"]["mission_id"] == "m1"
        assert captured["extra"]["producer"] == "kai"

    def test_record_allows_reconstruction_of_required_evidence(self):
        """The audit record must contain enough to reconstruct what satisfied requirement."""
        from orchestrator.organization import MissionTask
        from orchestrator.organization.evidence import EvidenceLedger

        captured = {}

        class FakeAudit:
            def emit(self, event_class, **kw):
                captured.update(kw)
                return "event-000002"
            def events_of_class(self, c): return []
            def read(self): return []

        ledger = EvidenceLedger(FakeAudit())
        task = MissionTask(task_id="t", mission_id="m", owner="kai", role="kai",
                          objective="x", required_evidence=("test", "artifact"))
        evidence = ("test:pytest-log", "artifact:diff.patch", "build:ci")
        ledger.record(mission_id="m", task_id="t", evidence=evidence, producer="kai")
        # Reconstruct satisfaction from persisted audit event
        persisted = captured.get("evidence") or captured.get("extra", {}).get("evidence")
        assert persisted is not None
        assert ledger.missing(task, persisted) == ()
        assert ledger.satisfied(task, persisted) is True

    def test_record_does_not_create_second_store(self):
        """Only the injected audit is used — no file creation or second ledger."""
        from orchestrator.organization.evidence import EvidenceLedger

        class CountingAudit:
            def __init__(self): self.emitted = 0
            def emit(self, *a, **kw): self.emitted += 1; return f"event-{self.emitted}"
            def events_of_class(self, c): return []
            def read(self): return []
        audit = CountingAudit()
        ledger = EvidenceLedger(audit)
        ledger.record(mission_id="m", task_id="t", evidence=("test:log",), producer="kai")
        assert audit.emitted == 1

    def test_events_readable_back_via_audit(self):
        from orchestrator.organization import MissionTask
        from orchestrator.organization.evidence import EvidenceLedger

        # Use a tiny in-memory audit that actually stores events
        class MemAudit:
            def __init__(self):
                self._events = []
            def emit(self, event_class, **kw):
                eid = f"event-{len(self._events)+1:06d}"
                ev = {"event_id": eid, "event_class": event_class, **kw}
                # mimic RuntimeAudit extra merging
                extra = kw.get("extra") or {}
                ev.update({k: v for k, v in extra.items() if k not in ev})
                # evidence merging
                if "evidence" in kw:
                    ev["evidence"] = list(kw["evidence"])
                self._events.append(ev)
                return eid
            def events_of_class(self, c):
                return [e for e in self._events if e.get("event_class") == c]
            def read(self):
                return list(self._events)

        audit = MemAudit()
        ledger = EvidenceLedger(audit)
        ledger.record(mission_id="m", task_id="t1", evidence=("test:log", "artifact:patch"), producer="kai")
        ledger.record(mission_id="m", task_id="t2", evidence=("build:ci",), producer="cto")
        evs = ledger.events(mission_id="m")
        assert len(evs) == 2
        # Each event carries its evidence
        assert any("test:log" in (e.get("evidence") or []) for e in evs)
        # Mission filtering works
        assert len(ledger.events(mission_id="other")) == 0


# ---------------------------------------------------------------------------
# 2. Root build_verdict() enforces documented invariant directly
# ---------------------------------------------------------------------------
class TestBuildVerdictInvariant:
    def test_blocks_when_required_evidence_missing_even_if_handoffs_done(self):
        from orchestrator.organization import TypedHandoff
        from orchestrator.organization.root import build_verdict

        # Handoff claims done, but evidence is missing required kinds
        ho = TypedHandoff(mission_id="m", task_id="kai", owner="kai", role="kai",
                         status="done", summary="s", findings=(), evidence=("build:ci",),
                         artifacts=(), changed_files=(), risks=(), unknowns=(), next=())
        # No required_evidence supplied -> legacy behavior would say COMPLETE
        v_legacy = build_verdict(mission_id="m", handoffs={"kai": ho},
                                expected_tasks=("kai",), reviews=[], escalations=(), blockers=(),
                                waves_executed=1, evidence_events=1)
        assert v_legacy.outcome == "COMPLETE"

        # With required_evidence directly enforce invariant -> BLOCKED
        v = build_verdict(mission_id="m", handoffs={"kai": ho},
                         expected_tasks=("kai",), reviews=[], escalations=(), blockers=(),
                         waves_executed=1, evidence_events=1,
                         required_evidence={"kai": ("test", "artifact")},
                         expected_reviewers={})
        assert v.outcome == "BLOCKED"
        assert "required evidence" in v.reason

    def test_blocks_when_reviewer_not_accepted_even_if_unaccepted_not_in_latest(self):
        from orchestrator.organization import TypedHandoff
        from orchestrator.organization.root import build_verdict

        ho = TypedHandoff(mission_id="m", task_id="kai", owner="kai", role="kai",
                         status="done", summary="s", findings=(), evidence=("test:log", "artifact:patch"),
                         artifacts=(), changed_files=(), risks=(), unknowns=(), next=())
        # A task that has a required reviewer but no review record at all
        # If we only checked latest unaccepted, it would say COMPLETE (no unaccepted entries)
        v = build_verdict(mission_id="m", handoffs={"kai": ho},
                         expected_tasks=("kai",), reviews=[], escalations=(), blockers=(),
                         waves_executed=1, evidence_events=1,
                         required_evidence={"kai": ("test", "artifact")},
                         expected_reviewers={"kai": ("badsector",)})
        assert v.outcome == "BLOCKED"
        assert "reviewer" in v.reason

    def test_completes_only_when_all_invariants_satisfied(self):
        from orchestrator.organization import TypedHandoff
        from orchestrator.organization.root import build_verdict

        ho = TypedHandoff(mission_id="m", task_id="kai", owner="kai", role="kai",
                         status="done", summary="s", findings=(), evidence=("test:log", "artifact:patch"),
                         artifacts=(), changed_files=(), risks=(), unknowns=(), next=())
        v = build_verdict(mission_id="m", handoffs={"kai": ho},
                         expected_tasks=("kai",),
                         reviews=[{"reviewer": "badsector", "target_task_id": "kai", "action": "accept"}],
                         escalations=(), blockers=(), waves_executed=1, evidence_events=1,
                         required_evidence={"kai": ("test", "artifact")},
                         expected_reviewers={"kai": ("badsector",)})
        assert v.outcome == "COMPLETE"

    def test_not_done_still_blocks(self):
        from orchestrator.organization import TypedHandoff
        from orchestrator.organization.root import build_verdict

        ho = TypedHandoff(mission_id="m", task_id="kai", owner="kai", role="kai",
                         status="blocked", summary="s", findings=(), evidence=(),
                         artifacts=(), changed_files=(), risks=(), unknowns=(), next=())
        v = build_verdict(mission_id="m", handoffs={"kai": ho},
                         expected_tasks=("kai",), reviews=[], escalations=(), blockers=(),
                         waves_executed=1, evidence_events=0,
                         required_evidence={"kai": ("test",)},
                         expected_reviewers={})
        assert v.outcome == "BLOCKED"

    def test_runner_finalize_enforces_invariant_end_to_end(self, tmp_path):
        """MissionRunner should not return COMPLETE when evidence is faked done.
        Requires a reviewer so _finalize expected_reviewers triggers.
        """
        from orchestrator.organization import MissionPacket, MissionTask
        from orchestrator.organization.runner import MissionRunner
        base = str(tmp_path)
        tasks = (
            MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai",
                       objective="impl", required_evidence=("test", "artifact")),
            MissionTask(task_id="bad", mission_id="m", owner="badsector", role="badsector",
                       objective="review", depends_on=("kai",)),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)

        def runner(task, delegation, ctx):
            if task.assigned_role == "badsector":
                return TaskResult(task_id=task.task_id, assigned_role="badsector",
                                 status="SUCCEEDED", recommendation="PASS")
            # Lie: claim SUCCEEDED without required evidence kinds
            return TaskResult(task_id=task.task_id, assigned_role="kai",
                             status="SUCCEEDED", findings=("done",), evidence=("build:ci",))

        r = MissionRunner(delegation=_active_delegation(base), base=base, runner=runner)
        v = r.run(m)
        # Should be BLOCKED (evidence missing -> uncertain -> rework -> still missing)
        # or ESCALATED, never COMPLETE, because invariant enforced in _finalize
        assert v.outcome != "COMPLETE"


# ---------------------------------------------------------------------------
# 3. Dependency semantics: external dep only when proven completed
# ---------------------------------------------------------------------------
class TestDependencySemantics:
    def test_plan_waves_external_proven_allowed(self):
        from orchestrator.organization.waves import plan_waves
        waves = plan_waves(("b",), {"b": ("a",)}, completed={"a"})
        assert waves == (("b",),)

    def test_plan_waves_external_unknown_fails_closed(self):
        from orchestrator.organization.waves import plan_waves
        with pytest.raises(ValueError, match="unproven external"):
            plan_waves(("b",), {"b": ("ghost",)}, completed=set())
        with pytest.raises(ValueError, match="unproven external"):
            plan_waves(("b",), {"b": ("ghost",)})

    def test_plan_waves_external_none_fails_closed(self):
        from orchestrator.organization.waves import plan_waves
        with pytest.raises(ValueError, match="unproven external"):
            plan_waves(("b",), {"b": ("ext",)}, completed=None)

    def test_plan_waves_internal_dag_preserved(self):
        from orchestrator.organization.waves import plan_waves
        # internal deps still validated
        with pytest.raises(ValueError, match="cycle"):
            plan_waves(("a", "b"), {"a": ("b",), "b": ("a",)})
        with pytest.raises(ValueError, match="itself"):
            plan_waves(("a",), {"a": ("a",)})

    def test_mission_packet_still_fails_unknown(self):
        from orchestrator.organization import MissionPacket, MissionTask, MissionError
        t = MissionTask(task_id="b", mission_id="m", owner="kai", role="kai",
                       objective="x", depends_on=("ghost",))
        with pytest.raises(MissionError, match="unknown/unproven"):
            MissionPacket(mission_id="m", objective="o", tasks=(t,))


# ---------------------------------------------------------------------------
# 4. Rework semantics: preserve prerequisites
# ---------------------------------------------------------------------------
class TestReworkPreservesPrereqs:
    def test_rework_task_preserves_depends_on(self):
        from orchestrator.organization import MissionTask
        from orchestrator.organization.rework import ReworkLedger
        orig = MissionTask(task_id="impl", mission_id="m", owner="kai", role="kai",
                          objective="impl", depends_on=("pre",), context_refs=("pre", "docs/a.md"),
                          required_evidence=("test",))
        rl = ReworkLedger()
        order = rl.request(target_task_id="impl", findings=("missing test",), reviewer="badsector", attempt=1)
        rew = rl.rework_task(orig, order)
        assert rew.depends_on == ("pre",)
        assert rew.context_refs == ("pre", "docs/a.md")
        assert rew.required_evidence == ("test",)
        assert rew.owner == "kai" and rew.rework_of == "impl"

    def test_rework_task_no_deps_stays_no_deps(self):
        from orchestrator.organization import MissionTask
        from orchestrator.organization.rework import ReworkLedger
        orig = MissionTask(task_id="a", mission_id="m", owner="kai", role="kai", objective="x")
        rl = ReworkLedger()
        order = rl.request(target_task_id="a", findings=("f",), reviewer="badsector", attempt=1)
        rew = rl.rework_task(orig, order)
        assert rew.depends_on == ()

    def test_rework_task_multi_deps_preserved(self):
        from orchestrator.organization import MissionTask
        from orchestrator.organization.rework import ReworkLedger
        # Use non-reviewer owners for multi-dep test
        orig = MissionTask(task_id="impl", mission_id="m", owner="kai", role="kai",
                          objective="impl", depends_on=("pre1", "pre2"), context_refs=("pre1",))
        # Need those deps to exist in a packet? Not needed for isolated test
        rl = ReworkLedger()
        order = rl.request(target_task_id="impl", findings=("f",), reviewer="badsector", attempt=1)
        rew = rl.rework_task(orig, order)
        assert set(rew.depends_on) == {"pre1", "pre2"}

    def test_critic_rework_context_refs_not_dead(self):
        from orchestrator.organization import MissionTask
        from orchestrator.organization.rework import ReworkLedger
        critic = MissionTask(task_id="bad", mission_id="m", owner="badsector", role="badsector",
                            objective="review", depends_on=("impl",))
        rl = ReworkLedger()
        ct = rl.critic_rework_task(critic, "impl#rework-1", 1)
        assert ct.depends_on == ("impl#rework-1",)
        assert ct.context_refs == ("impl#rework-1",)
        # No dead comprehension in source
        import inspect
        src = inspect.getsource(rl.critic_rework_task)
        assert "for c in () if False" not in src

    def test_dead_expression_removed_from_file(self):
        import pathlib
        p = pathlib.Path(_PROJECT_ROOT) / "orchestrator" / "organization" / "rework.py"
        text = p.read_text()
        assert "for c in () if False" not in text
        assert "keep empty" not in text


# ---------------------------------------------------------------------------
# 5. No dead expression anywhere in rework module
# ---------------------------------------------------------------------------
def test_no_dead_expression_in_rework():
    import pathlib
    p = pathlib.Path(_PROJECT_ROOT) / "orchestrator" / "organization" / "rework.py"
    text = p.read_text()
    assert "if False" not in text
