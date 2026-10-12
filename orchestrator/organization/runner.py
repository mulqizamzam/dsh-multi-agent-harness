# orchestrator.organization.runner — mission runner (MVP)
#
# Orchestrates ONE mission through bounded waves:
#   plan_waves (pure ordering) -> per wave: ParallelExecutor (the EXISTING
#   bounded-concurrency executor; store CAS revalidated around the batch)
#   -> typed handoff per result -> critic gate (control/badsector.py
#   provenance — EvidenceGate + BadSectorGate; fallback if
#   verification_requirements unknown) -> bounded rework (max 2 cycles)
#   -> ROOT verdict.
#
# NO second execution engine: children run through the delegation seam
# (DelegationClient / stub runner) exactly as ExecutionFlow/signoff does.

from __future__ import annotations

import os
import sys
import threading
import queue
import time
from collections import defaultdict
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dataclasses import dataclass, field

from orchestrator.foundation.contracts import TaskResult, ORCHESTRATOR  # noqa: E402
from orchestrator.runtime.parallel import (  # noqa: E402
    ParallelExecutor,
    SubtaskPlan,
    DEFAULT_MAX_WORKERS,
)
from orchestrator.runtime.audit import RuntimeAudit  # noqa: E402
from orchestrator.runtime.store import RuntimeStore  # noqa: E402
from orchestrator.dsh.client import DelegationClient  # noqa: E402

from control.badsector import BadSectorGate, _input_hash  # noqa: E402

from .packet import MissionPacket, MissionTask, MissionError  # noqa: E402
from .waves import plan_waves  # noqa: E402
from .handoff import TypedHandoff, build_task_context  # noqa: E402
from .evidence import EvidenceLedger  # noqa: E402
from .rework import ReworkLedger, ReworkExhausted, critic_verdict, verdict_action, ACCEPT_VERDICTS  # noqa: E402
from .root import build_verdict, RootVerdict  # noqa: E402


@dataclass
class MissionOutcome:
    """Runner result for one mission."""

    mission_id: str
    verdict: RootVerdict
    handoffs: dict[str, TypedHandoff]
    reviews: list[dict]
    rework_orders: tuple[dict, ...]
    escalations: tuple[str, ...]
    blockers: tuple[str, ...]
    waves_executed: int


def _result_of(outcome):
    result = getattr(outcome, "result", outcome)
    if not isinstance(result, TaskResult):
        raise MissionError("child returned no structured TaskResult")
    return result


def _root_id(task_id: str) -> str:
    """Lineage root of a (possibly rework) task id."""
    tid = str(task_id)
    while "#rework-" in tid:
        tid = tid.split("#rework-")[0]
    return tid


class MissionRunner:
    """Execute a mission via existing DSH + bounded parallel execution.

    Delegation + store + audit mirror the execution signatures used by the
    production flow (front door path).  A custom ``runner`` (callable taking
    (task, delegation, context) -> TaskResult | DelegationOutcome) may be
    supplied for tests; the default dispatches through DelegationClient.
    """

    def __init__(
        self,
        *,
        delegation,
        base=None,
        project: str = "multi-agent-harness",
        runner=None,
        now=None,
        max_workers: int = DEFAULT_MAX_WORKERS,
        provider=None,
    ):
        if delegation is None or not hasattr(delegation, "is_active"):
            raise MissionError("MissionRunner requires a structured Delegation")
        try:
            active = delegation.is_active()
        except Exception:
            active = False
        if not active:
            raise MissionError(
                f"delegation {getattr(delegation, 'id', '?')} is not ACTIVE")
        self.delegation = delegation
        # Optional live delegation provider (AUTH-INV-05/06): when wired, the
        # revocation registry is re-read at every dispatch — a mid-mission
        # revocation must not be invisible to a snapshot taken in __init__.
        self.provider = provider
        self.project = project
        self.base = base
        self.now = now
        self.max_workers = max(1, int(max_workers or 1))
        self._runner = runner  # (task, delegation, context) -> TaskResult
        self.store = RuntimeStore(base, project)
        try:
            self.store.ensure_state()
        except Exception:
            pass
        self.audit = RuntimeAudit(base, project, now=now)
        self.evidence = EvidenceLedger(self.audit)
        self.rework = ReworkLedger()
        self._badsector = BadSectorGate()
        # populated by run()
        self.handoffs: dict[str, TypedHandoff] = {}
        self.reviews: list[dict] = []
        self.escalations: list[str] = []
        self.blockers: list[str] = []
        self.blocked: set[str] = set()
        self._evidence_reworked: set[str] = set()
        self._reviewed_targets: set[str] = set()
        self.waves_executed = 0
        self._held_version_cached: int | None = None
        self._attempts: dict[str, int] = {}
        # OBSERVED execution metrics (no estimates — see organization/metrics.py)
        self.started_at: str = ""            # mission run start (ISO)
        self.completed_at: str = ""          # mission finalize (ISO)
        self.parallel_peak_observed: int = 0  # max tasks dispatched in one wave
        self._task_wave: dict[str, int] = {}  # task_id -> wave index dispatched
        self._task_durations: dict[str, float] = {}  # task_id -> dispatch ms

    # -- helpers ------------------------------------------------------------
    def _get_held_version(self) -> int:
        if self._held_version_cached is not None:
            return self._held_version_cached
        try:
            ps = self.store.load_project_state()
            self._held_version_cached = ps.version
        except Exception:
            self._held_version_cached = 1
        return self._held_version_cached

    def _provenance_ok(self, review_id: str) -> bool:
        try:
            for entry in (self.audit.review_log() or ()):
                if isinstance(entry, dict) and entry.get("review_id") == review_id:
                    return True
        except Exception:
            pass
        return False

    def _accepted(self, task_id: str) -> bool:
        ho = self.handoffs.get(task_id)
        if ho is None or ho.status != "done":
            return False
        # Any failing latest review for this target disqualifies it.
        latest: dict[str, str] = {}
        for r in self.reviews:
            if r.get("target_task_id") == task_id:
                latest[str(r.get("reviewer", ""))] = str(r.get("action", ""))
        return all(a == "accept" for a in latest.values())

    def _block(self, task: MissionTask, reason: str):
        self.blocked.add(task.task_id)
        if task.task_id not in self.handoffs:
            self.handoffs[task.task_id] = TypedHandoff(
                mission_id=task.mission_id,
                task_id=task.task_id,
                owner=task.owner,
                role=task.role,
                status="blocked",
                summary=reason[:500],
                findings=(),
                evidence=(),
                artifacts=(),
                changed_files=(),
                risks=(),
                unknowns=(reason,),
                next=(),
                attempt=self._attempts.get(task.task_id, 1),
            )
        self.audit.emit(
            "task_blocked", actor=task.owner, action="block",
            target=task.task_id, task_id=task.task_id,
            result="blocked", error=reason,
            extra={"mission_id": task.mission_id},
        )

    def _dispatch_one(
        self,
        task_obj,
        mission_task: MissionTask,
        upstream: dict,
        extra: dict | None = None,
    ):
        _t0 = time.perf_counter()
        try:
            return self._dispatch_one_inner(
                task_obj, mission_task, upstream, extra=extra)
        finally:
            # OBSERVED: dispatch duration, recorded even on failure/timeout.
            self._task_durations[mission_task.task_id] = round(
                self._task_durations.get(mission_task.task_id, 0.0)
                + (time.perf_counter() - _t0) * 1000.0, 3)

    def _dispatch_one_inner(
        self,
        task_obj,
        mission_task: MissionTask,
        upstream: dict,
        extra: dict | None = None,
    ):
        # AUTH-INV-05/06 execution-time re-check: re-read the revocation
        # registry per dispatch when a provider is wired. control.delegation
        # .revoke() returns a NEW REVOKED copy, so a revocation that lands
        # mid-mission leaves the __init__ snapshot ACTIVE — without this
        # re-read this path never observed it (F13).
        if self.provider is not None:
            try:
                current, revocations = self.provider.current()
            except Exception:
                raise MissionError(
                    "delegation provider unreadable at dispatch "
                    "(AUTH-INV-05/06): fail-closed")
            revoked = self.delegation.id in tuple(revocations or ())
            if current is None or revoked or not current.is_active():
                raise MissionError(
                    f"delegation {getattr(self.delegation, 'id', '?')} is no "
                    f"longer ACTIVE at dispatch (revoked={revoked}, "
                    f"current={'none' if current is None else current.status})"
                    " — AUTH-INV-05/06")
        context = build_task_context(mission_task, upstream, extra=extra)
        # timeout honoured at the mission seam (fail-closed -> blocked)
        timeout = mission_task.timeout
        if timeout is not None and timeout > 0:
            q: queue.Queue = queue.Queue()

            def _work():
                try:
                    if self._runner is not None:
                        res = self._runner(task_obj, self.delegation, context)
                    else:
                        client = DelegationClient(now=self.now)
                        res = client.delegate(
                            task_obj, self.delegation,
                            extra_context=context,
                            timeout_seconds=timeout,
                        )
                    q.put(("ok", res))
                except BaseException as exc:
                    q.put(("err", exc))

            t = threading.Thread(target=_work, daemon=True)
            t.start()
            try:
                kind, val = q.get(timeout=timeout)
            except queue.Empty:
                raise awaitable_blocked(mission_task, f"timeout after {timeout}s")
            if kind == "err":
                raise val  # type: ignore[arg-type]
            return val
        if self._runner is not None:
            return self._runner(task_obj, self.delegation, context)
        client = DelegationClient(now=self.now)
        return client.delegate(
            task_obj, self.delegation,
            extra_context=context,
            timeout_seconds=timeout,
        )

    def _run_wave(self, tasks: list[MissionTask], wave_index: int = 0):
        if not tasks:
            return
        # OBSERVED wave metrics: peak concurrency and per-task wave index.
        self.parallel_peak_observed = max(self.parallel_peak_observed, len(tasks))
        for t in tasks:
            if t.task_id not in self._task_wave:
                self._task_wave[t.task_id] = wave_index
        for t in tasks:
            self._attempts.setdefault(t.task_id, 1)
        plans = [
            SubtaskPlan(
                task=t.to_task(), owner=t.owner,
                reads=tuple(t.context_refs), writes=(),
                depends_on=tuple(t.depends_on),
            )
            for t in tasks
        ]
        executor = ParallelExecutor(
            lambda task, delegation: self._dispatch_one(
                task, self._mission_task_of(task.task_id), self.handoffs),
            store=self.store, max_workers=self.max_workers,
        )
        outcomes = executor.run(plans, self.delegation, held_version=self._get_held_version())
        self.waves_executed += 1
        for mt, outcome in zip(tasks, outcomes):
            try:
                result = _result_of(outcome)
            except MissionError as exc:
                self.blockers.append(f"task {mt.task_id}: {exc}")
                self._block(mt, str(exc))
                continue
            attempt = self._attempts.get(mt.task_id, 1)
            self.evidence.record(
                mission_id=mt.mission_id, task_id=mt.task_id,
                evidence=tuple(result.evidence or ()), producer=mt.owner)
            ho = TypedHandoff.from_task_result(mt, result, attempt=attempt)
            # Evidence gate: missing required evidence -> uncertain (not accepted)
            missing = self.evidence.missing(mt, ho.evidence)
            if missing and ho.status == "done":
                from dataclasses import replace  # noqa: WPS433

                ho = replace(ho, status="uncertain",
                             unknowns=ho.unknowns + (f"missing required evidence: {', '.join(missing)}",))
            self.handoffs[mt.task_id] = ho
            # Rework lineage promotion: when a rework dispatch of a base task
            # lands done (evidence satisfied), the BASE handoff adopts the
            # rework outcome so ROOT / downstream review gates observe the
            # final state (the base 'uncertain' snapshot is superseded, never
            # promoted silently — the rework result carries its own evidence).
            if mt.rework_of and mt.rework_cycle > 0 and ho.status == "done":
                base = self.handoffs.get(mt.rework_of)
                if base is not None and base.status != "done":
                    from dataclasses import replace as _replace  # noqa: WPS433

                    self.handoffs[mt.rework_of] = _replace(ho, task_id=mt.rework_of)
                self._attempts[mt.rework_of] = max(
                    self._attempts.get(mt.rework_of, 1),
                    self._attempts.get(mt.task_id, 1))
            trait = ho.status
            r_field = "done" if trait == "done" else ("uncertain" if trait == "uncertain" else "blocked")
            self.audit.emit(
                "task_collected", actor=mt.owner, action="collect",
                target=mt.task_id, task_id=mt.task_id, result=r_field,
                extra={"mission_id": mt.mission_id, "status": trait},
            )
            # Review gate for critic tasks that review exactly one target
            if mt.is_critic():
                self._record_review(mt, result)

    def _mission_task_of(self, task_id: str) -> MissionTask:
        return self._mtasks[task_id]

    def _record_review(self, critic: MissionTask, result: TaskResult):
        # Normalize: the review's target is the rework lineage root (strip all "#rework-N" suffixes).
        # The budget lives on the root; per-rework-id budgets caused a forked bypass.
        def _root(tid: str) -> str:
            while "#rework-" in tid:
                tid = tid.split("#rework-")[0]
            return tid

        raw_target = critic.depends_on[0]
        target = _root(raw_target)
        reviewer = critic.owner
        try:
            verdict = critic_verdict(result, reviewer)
        except MissionError as exc:
            # fail-closed: malformed verdict -> escalate
            self.escalations.append(f"review {critic.task_id} malformed: {exc}")
            record = {
                "review_id": f"review-{critic.task_id}",
                "mission_id": critic.mission_id,
                "reviewer": reviewer,
                "reviewer_task_id": critic.task_id,
                "target_task_id": target,
                "verdict": str(getattr(result, "recommendation", "") or "").strip(),
                "input_hash": "",
                "action": "escalate",
                "findings": tuple(result.findings or ()),
            }
            self.reviews.append(record)
            self.audit.emit(
                "review_recorded", actor=reviewer, action="review",
                target=target, task_id=critic.task_id,
                result="escalate", error=str(exc),
                extra={"verdict": record["verdict"], "review_id": record["review_id"]},
            )
            return
        # Typed input binding for provenance (hash of reviewed payload)
        payload_target = self.handoffs.get(raw_target) or self.handoffs.get(target)
        payload_dict = {
            "task_id": target,
            "status": getattr(payload_target, "status", "missing"),
            "findings": list(getattr(payload_target, "findings", ()) or ()),
            "evidence": list(getattr(payload_target, "evidence", ()) or ()),
        }
        input_hash = _input_hash(payload_dict)
        review_id = f"review-{critic.task_id}"
        # Record REAL invocation for provenance (THREAT-014)
        try:
            self.audit.emit(
                "badsector_review", actor=reviewer, action="review",
                target=target, task_id=critic.task_id,
                extra={"review_id": review_id, "input_hash": input_hash, "verdict": verdict},
            )
        except Exception:
            pass
        # Gate evaluation: BADSECTOR uses BadSectorGate provenance; SOMAD is deterministic verified/rework
        if reviewer == "badsector":
            # BadSector gate: PASS only with provenance
            try:
                decision = self._badsector.evaluate(
                    risk="MEDIUM", action="adversarial_review",
                    review={"verdict": verdict, "review_id": review_id, "input_hash": input_hash},
                    review_required=True, expected_input_hash=input_hash,
                    review_log=self.audit.review_log(),
                )
                if verdict == "PASS" and decision.decision == "ALLOW":
                    action = "accept"
                elif verdict in ("REWORK", "REJECT"):
                    action = verdict_action(verdict, self.rework.cycles_used(target))
                else:
                    # PASS but gate denied (provenance or risk) → treated as rework/escalate
                    action = verdict_action("REWORK", self.rework.cycles_used(target))
            except Exception as exc:  # noqa: BLE001
                action = "escalate"
                self.escalations.append(f"badsector gate error on {target}: {exc}")
        else:
            # SOMAD — ACCEPT_VERDICTS contains VERIFIED only (rework handled via evidence+verdict)
            if verdict == "VERIFIED":
                # Worker claims alone are not evidence — somad's evidence must
                # be present. The badsector branch above consults self.evidence;
                # this branch previously accepted a VERIFIED verdict with an
                # EMPTY evidence tuple, exactly what this comment claimed was
                # impossible (F6).
                if self.evidence.missing(critic, tuple(result.evidence or ())):
                    action = verdict_action(
                        "REWORK", self.rework.cycles_used(target))
                else:
                    action = "accept"
            else:
                action = verdict_action(verdict, self.rework.cycles_used(target))
        if action == "escalate" and verdict not in ("EXHAUSTED",):
            msg = f"review {critic.task_id} escalated target {target} (verdict {verdict}) — rework budget exhausted"
            if msg not in self.escalations:
                self.escalations.append(msg)
        record = {
            "review_id": review_id,
            "mission_id": critic.mission_id,
            "reviewer": reviewer,
            "reviewer_task_id": critic.task_id,
            "target_task_id": target,
            "verdict": verdict,
            "input_hash": input_hash,
            "action": action,
            "findings": tuple(result.findings or ()),
        }
        self.reviews.append(record)
        self.audit.emit(
            "review_recorded", actor=reviewer, action="review",
            target=target, task_id=critic.task_id, result=action,
            extra={"verdict": verdict, "review_id": review_id, "action": action},
        )

    # -- wave planning + rework insertion --------------------------------
    def _attempt_of_target(self, target: str) -> int:
        # attempts for worker target = 1 + rework cycles so far
        return 1 + self.rework.cycles_used(target)

    def _review_gate_unmet(self, task: MissionTask) -> tuple[tuple[str, bool], ...]:
        """Downstream review gates for a NON-critic task (additive, fail-closed).

        For every dependency:
          - a dep with mission-declared reviewers passes only when ALL of its
            reviewers' LATEST decisions are 'accept' (missing review is not
            acceptance) — so a consumer cannot run ahead of, or override, a
            rejected / rework-pending / escalated review (ZEKO role rule);
          - a dep that is itself a critic task passes only when its reviewed
            target is accepted.
        Returns (gate_description, escalated) pairs; empty when nothing unmet.
        """
        gates: list[tuple[str, bool]] = []
        for dep in task.depends_on:
            ok, escalated, desc = self._dep_gate(dep)
            if not ok:
                gates.append((desc, escalated))
        return tuple(gates)

    def _dep_gate(self, dep: str) -> tuple[bool, bool, str]:
        """(accepted, escalated, description) for one dependency of a
        non-critic task.  Fail-closed: missing reviews are never acceptance."""
        if dep not in self.handoffs:
            return False, False, f"{dep}: not collected"
        root = _root_id(dep)
        reviewers = self._reviewers_of.get(root, ())
        if reviewers:
            latest: dict[str, str] = {}
            for r in self.reviews:
                if str(r.get("target_task_id", "")) == root:
                    latest[str(r.get("reviewer", ""))] = str(r.get("action", ""))
            missing = [rv for rv in reviewers if latest.get(rv) != "accept"]
            if not missing:
                return True, False, ""
            escalated = any(latest.get(rv) == "escalate" for rv in reviewers)
            return False, escalated, f"{root}: reviewers not accepted {missing}"
        dep_task = self._mtasks.get(dep)
        if dep_task is not None and dep_task.is_critic():
            target = _root_id(dep_task.depends_on[0])
            if self._accepted(target):
                return True, False, ""
            escalated = any(
                str(r.get("target_task_id", "")) == target
                and r.get("action") == "escalate"
                for r in self.reviews
            )
            return False, escalated, f"{dep}->reviewed:{target}"
        return self._accepted(dep), False, f"{dep}: not accepted"

    def run(self, mission: MissionPacket) -> RootVerdict:  # type: ignore[override]
        from .waves import plan_waves as _plan_waves  # noqa: WPS433

        self._mission = mission
        self._mtasks: dict[str, MissionTask] = {t.task_id: t for t in mission.tasks}
        # mission-declared reviewers per task id (the review admission gate)
        self._reviewers_of: dict[str, tuple[str, ...]] = {
            t.task_id: tuple(r.owner for r in mission.tasks
                             if r.owner in ("badsector", "somad")
                             and t.task_id in r.depends_on)
            for t in mission.tasks
        }
        self._attempts = {t.task_id: 1 for t in mission.tasks}
        self.handoffs = {}
        self.reviews = []
        self.escalations = []
        self.blockers = []
        self.blocked = set()
        self._evidence_reworked = set()
        self._task_wave = {}
        self._task_durations = {}
        self.parallel_peak_observed = 0
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.completed_at = ""
        self.waves_executed = 0
        self.audit.emit(
            "mission_started", actor=ORCHESTRATOR, action="mission",
            target=mission.mission_id,
            extra={"tasks": [t.task_id for t in mission.tasks]},
        )
        try:
            waves = [list(w) for w in _plan_waves(
                tuple(t.task_id for t in mission.tasks),
                {t.task_id: tuple(t.depends_on) for t in mission.tasks},
                completed=set(mission.proven_completed) if mission.proven_completed else None,
            )]
        except ValueError as exc:
            self.blockers = [str(exc)]
            return self._finalize(mission, stopped=str(exc))

        i = 0
        processed_review_idx = 0
        while i < len(waves):
            wave_ids = list(waves[i])
            runnable: list[MissionTask] = []
            for tid in wave_ids:
                if tid in self.blocked or tid in self.handoffs:
                    continue
                mt = self._mtasks[tid]
                # Dependency admission: every depends_on must be accepted.
                # For critic tasks the dep need only be collected (done or
                # uncertain is enough to review — but accepted=False blocks
                # downstream non-critic tasks, not the review itself).
                if mt.is_critic():
                    # critics are admitted as soon as their target is collected
                    unmet = [d for d in mt.depends_on if d not in self.handoffs]
                else:
                    unmet = [d for d in mt.depends_on if not self._accepted(d)]
                    if not unmet:
                        # Downstream review gate: a dep that is itself a critic
                        # task passes only when its reviewed target is accepted
                        # by all reviewers (ZEKO cannot override a rejected or
                        # rework-pending review).
                        gates = self._review_gate_unmet(mt)
                        if gates:
                            if any(g_escalated for _, g_escalated in gates):
                                self._block(
                                    mt,
                                    "review gate not accepted (escalated): "
                                    + ", ".join(g for g, _ in gates))
                                continue
                            # rework still in flight — hold for the re-review waves
                            continue
                if unmet:
                    # Block if any dependency is explicitly blocked
                    blocked_deps = [d for d in unmet if self.handoffs.get(d, None) is not None
                                    and self.handoffs[d].status == "blocked"]
                    if blocked_deps:
                        self._block(mt, f"dependencies blocked: {blocked_deps}")
                        continue
                    # Otherwise hold for rework: do not run this wave yet for this task.
                    # Keep the task pending in this wave; retry after rework waves.
                    continue
                runnable.append(mt)

            if runnable:
                try:
                    self._run_wave(runnable, wave_index=i)
                except Exception as exc:  # noqa: BLE001
                    msg = f"wave {i}: {type(exc).__name__}: {exc}"
                    self.blockers.append(msg)
                    self.audit.emit(
                        "mission_stopped", actor=ORCHESTRATOR, action="stop",
                        target=mission.mission_id, error=msg)
                    # remaining wave tasks become blocked.
                    for tid in wave_ids:
                        if tid not in self.handoffs and tid not in self.blocked:
                            mt = self._mtasks[tid]
                            self._block(mt, f"wave failure: {msg[:200]}")
                    break

            # After the wave: evidence-based rework + review-based rework
            fresh_reviews = self.reviews[processed_review_idx:]
            processed_review_idx = len(self.reviews)

            # Evidence-uncertain tasks (done without required evidence)
            # Only the original task lineage triggers evidence rework; rework
            # tasks themselves are tracked via cycles_used, not re-adding evidence_gate indefinitely.
            pending_rework: dict[str, dict] = {}

            def _root(tid: str) -> str:
                while "#rework-" in tid:
                    tid = tid.split("#rework-")[0]
                return tid

            # Evidence rework only for roots not yet exhausted; rework tasks are handled via review flow
            for tid, ho in list(self.handoffs.items()):
                if ho.status != "uncertain":
                    continue
                root = _root(tid)
                if root in self._evidence_reworked:
                    continue
                # Only trigger evidence rework once per root per distinct uncertain result
                # Check if root already has pending or exhausted budget
                if self.rework.cycles_used(root) >= self.rework.max_cycles:
                    self._evidence_reworked.add(root)
                    continue
                mt = self._mtasks.get(root) or self._mtasks.get(tid)
                if mt is None or mt.owner in ("badsector", "somad"):
                    continue
                missing = self.evidence.missing(mt, ho.evidence)
                if not missing:
                    continue
                self._evidence_reworked.add(root)
                self._evidence_reworked.add(tid)
                bucket = pending_rework.setdefault(root, {
                    "findings": [], "reviewers": [],
                })
                bucket["findings"].append(f"missing required evidence: {', '.join(missing)}")
                bucket["reviewers"].append("evidence_gate")

            # Review-driven rework — escalated reviews already have their
            # escalation in self.escalations via _record_review/target resolution.
            for r in fresh_reviews:
                if r.get("action") not in ("rework",):
                    continue
                target = _root(r["target_task_id"])
                bucket = pending_rework.setdefault(target, {
                    "findings": [], "reviewers": [],
                })
                # Dedup findings
                for f in (r.get("findings") or ()):
                    if f not in bucket["findings"]:
                        bucket["findings"].append(f)
                if r.get("reviewer") not in bucket["reviewers"]:
                    bucket["reviewers"].append(r["reviewer"])

            if pending_rework:
                rework_impl_ids: list[str] = []
                rework_critic_ids: list[str] = []
                for target, info in list(pending_rework.items()):
                    try:
                        order = self.rework.request(
                            target_task_id=target,
                            findings=tuple(info["findings"] or ("review requested rework",)),
                            reviewer="+".join(info["reviewers"]) or "review",
                            attempt=self._attempts.get(target, 1),
                        )
                    except ReworkExhausted as exc:
                        msg = str(exc)
                        if msg not in self.escalations:
                            self.escalations.append(msg)
                        self.reviews.append({
                            "review_id": f"rework-exhausted-{target}-{self.rework.cycles_used(target)}",
                            "mission_id": mission.mission_id,
                            "reviewer": "+".join(info["reviewers"]),
                            "reviewer_task_id": "rework_limiter",
                            "target_task_id": target,
                            "verdict": "EXHAUSTED",
                            "input_hash": "",
                            "action": "escalate",
                            "findings": info["findings"],
                        })
                        continue
                    original = self._mtasks[target]
                    attempt = 1 + self.rework.cycles_used(target)
                    self._attempts.setdefault(target, 1)
                    rework_mt = self.rework.rework_task(original, order)
                    self._attempts[rework_mt.task_id] = attempt
                    self._mtasks[rework_mt.task_id] = rework_mt
                    self.audit.emit(
                        "rework_requested", actor=ORCHESTRATOR, action="rework",
                        target=target, task_id=target,
                        extra={"cycle": order["cycle"], "rework_task_id": rework_mt.task_id,
                               "reviewers": info["reviewers"],
                               "findings": list(info["findings"])},
                    )
                    rework_impl_ids.append(rework_mt.task_id)
                    for critic in mission.tasks:
                        if critic.owner in ("badsector", "somad") and target in critic.depends_on:
                            # Also include any critic that was created for rework? For MVP, only original mission critics re-review.
                            ct = self.rework.critic_rework_task(critic, rework_mt.task_id, order["cycle"])
                            self._mtasks[ct.task_id] = ct
                            self._attempts[ct.task_id] = 1
                            rework_critic_ids.append(ct.task_id)
                if rework_impl_ids:
                    waves.insert(i + 1, rework_impl_ids)
                if rework_critic_ids:
                    waves.insert(i + 2, rework_critic_ids)
                # Do not count the insertion step as a separate wave advancement above;
                # still increment i to move past the just-executed wave.
            i += 1

        # Mark any remaining expected tasks that were never dispatched as blocked.
        for mt in mission.tasks:
            if mt.task_id not in self.handoffs and mt.task_id not in self.blocked:
                self._block(mt, "never dispatched (dependencies or mission stopped)")
        return self._finalize(mission, stopped="")

    def _finalize(self, mission: MissionPacket, stopped: str) -> RootVerdict:
        self.completed_at = datetime.now(timezone.utc).isoformat()
        expected = tuple(t.task_id for t in mission.tasks)
        evidence_events = len(self.evidence.events(mission.mission_id))
        blockers = tuple(self.blockers)
        required_evidence = {t.task_id: tuple(t.required_evidence) for t in mission.tasks}
        expected_reviewers: dict[str, tuple[str, ...]] = {}
        for t in mission.tasks:
            revs = self._reviewers_of.get(t.task_id) or tuple(
                r.owner for r in mission.tasks
                if r.owner in ("badsector", "somad") and t.task_id in r.depends_on)
            if revs:
                expected_reviewers[t.task_id] = revs
        verdict = build_verdict(
            mission_id=mission.mission_id,
            handoffs=self.handoffs,
            expected_tasks=expected,
            reviews=self.reviews,
            rework_orders=self.rework.history(),
            escalations=tuple(self.escalations),
            blockers=blockers,
            waves_executed=self.waves_executed,
            evidence_events=evidence_events,
            required_evidence=required_evidence,
            expected_reviewers=expected_reviewers,
        )
        self.audit.emit(
            "mission_verdict", actor=ORCHESTRATOR, action="verdict",
            target=mission.mission_id, result=verdict.outcome.lower(),
            extra={"outcome": verdict.outcome, "reason": verdict.reason,
                   "waves_executed": self.waves_executed,
                   "stopped": stopped} if stopped else {
                       "outcome": verdict.outcome, "reason": verdict.reason,
                       "waves_executed": self.waves_executed},
        )
        return verdict


def awaitable_blocked(task: MissionTask, reason: str) -> Exception:
    """Produce a blocked-form TaskResult exception placeholder."""

    class _TimeoutAsBlocked(MissionError):
        pass

    exc = _TimeoutAsBlocked(reason)
    # Convert timeout to a blocked-form exception that the dispatch wrapper understands.
    raise exc
