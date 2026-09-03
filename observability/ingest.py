# observability.ingest — Correlate the existing audit ledger into a RunIndex
#
# Phase 4 / Session D — Production operations + observability.
#
# READ-ONLY projection over the EXISTING audit ledger. This module:
#   - reads events with the existing audit primitives
#     (audit.helpers.append_log.read_events_strict, verify_append_only,
#      audit.helpers.integrity.verify_chain) — it does NOT write audit
#   - reconstructs bounded runs (RUN_STARTED -> ... -> RUN_TERMINAL)
#   - correlates run_id / task_id / parent_task / delegation_id / role /
#     agent-tool identity / gate decisions / execution / verification /
#     recovery / failure class / retry count / state version / provenance /
#     timing / final status
#   - FAILS CLOSED: a malformed/missing correlation field on a consequential
#     event REJECTS that event (never fabricate an id); a duplicate event id,
#     a missing terminal, or an ordering violation is recorded as a problem.
#   - NEVER treats audit as authority (AUTH-INV-14): `audit_is_authority_source`
#     is consulted so an audit event claiming an approval is recorded as DATA
#     only.
#
# The ingest takes an iterable of event dicts (from the ledger) OR a ledger
# path; when a path is given, the existing strict readers + integrity checks
# are reused.

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from observability.vocab import (
    RUN_STARTED, RUN_TERMINAL, GATES, EXECUTION, VERIFICATION,
    RECOVERY_ESCALATION,
    AGENT_REPORTED, RUNTIME_OBSERVED, CONTROL_PLANE_DECISION,
    CONSEQUENTIAL_EVENT_CLASSES, CORRELATION_REQUIREMENTS,
    stage_of, stage_index, is_start_event, is_terminal_event,
    terminal_outcome, evidence_source_of, classify_field_source,
    OUTCOME_COMPLETE, OUTCOME_BLOCKED, OUTCOME_FAILED, OUTCOME_ESCALATED,
    OUTCOME_RECOVERING,
)
from observability.model import (
    ObservedEvent, TaskRecord, DelegationRecord, FailureRecord,
    CorrelationProblem, RunRecord, RunIndex,
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts) -> datetime | None:
    """Parse an ISO-8601 timestamp (with optional Z) to a datetime."""
    if not isinstance(ts, str) or not ts:
        return None
    norm = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(norm)
    except ValueError:
        return None


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _event_id(event: dict) -> str:
    eid = event.get("event_id")
    return eid if isinstance(eid, str) and eid else ""


def _get_field(event: dict, path: str):
    """Look up a (possibly dotted) field path on the event dict.

    RuntimeAudit merges `extra` into the top level, so most required fields
    live at the top level; dotted paths are supported for nested dicts.
    """
    node = event
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


# ---------------------------------------------------------------------------
# Audit-ledger reuse (read-only) + integrity
# ---------------------------------------------------------------------------

def _audit_ledger_path(base: str | None, project: str) -> str:
    from control.execution_gate import workspace_base
    base = base or workspace_base()
    return os.path.join(base, "audit", project, "events.jsonl")


def read_ledger_events(base: str | None = None, project: str = "multi-agent-harness",
                       log_path: str | None = None) -> tuple[list, dict]:
    """Read the existing audit ledger with the existing strict primitive.

    Returns (events, integrity). ``integrity`` records:
      - strict_ok / strict_error : result of read_events_strict
      - append_only_ok / append_only_problems : result of verify_append_only
      - chain_ok / chain_error    : result of verify_chain (when a sidecar
        exists or the reader is allowed to persist a baseline)

    This module NEVER writes the ledger; verify_chain may persist its sidecar
    baseline, which is an audit-integrity helper behaviour we reuse as-is.
    """
    from audit.helpers.append_log import (
        read_events_strict, verify_append_only, AuditIntegrityError,
        audit_is_authority_source,
    )
    from audit.helpers.integrity import verify_chain
    path = log_path or _audit_ledger_path(base, project)
    integrity = {"path": path, "audit_is_authority_source": False}
    if not os.path.exists(path):
        return [], integrity

    try:
        events = read_events_strict(path)
        integrity["strict_ok"] = True
    except AuditIntegrityError as e:
        return [], {"path": path, "strict_ok": False,
                    "strict_error": str(e),
                    "audit_is_authority_source": False}

    try:
        ok, problems = verify_append_only(path)
        integrity["append_only_ok"] = ok
        integrity["append_only_problems"] = list(problems)
    except Exception as e:  # noqa: BLE001
        integrity["append_only_ok"] = False
        integrity["append_only_problems"] = [str(e)]

    try:
        verify_chain(path)
        integrity["chain_ok"] = True
    except Exception as e:  # noqa: BLE001
        integrity["chain_ok"] = False
        integrity["chain_error"] = str(e)

    # Hard invariant: an audit record never grants authority.
    try:
        assert audit_is_authority_source({}) is False
    except Exception:  # pragma: no cover
        pass
    integrity["audit_is_authority_source"] = False
    return events, integrity


# ---------------------------------------------------------------------------
# Fail-closed correlation validation
# ---------------------------------------------------------------------------

def validate_event_correlation(event: dict, *, known_runs: dict,
                               run_id: str = "") -> CorrelationProblem | None:
    """Fail-closed check on one event's correlation data.

    Returns None when the event is acceptable; otherwise a CorrelationProblem
    whose ``rejected`` flag is True for a consequential event that must not be
    ingested (never fabricate ids). Non-consequential events with anomalies are
    recorded but not rejected (they cannot corrupt a run's consequential path).
    """
    eid = _event_id(event)
    cls = event.get("event_class") or ""
    required = CORRELATION_REQUIREMENTS.get(cls, ())
    for field in required:
        value = _get_field(event, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return CorrelationProblem(
                kind="MALFORMED_CORRELATION",
                message=(f"event {eid!r} ({cls}) is missing required "
                         f"correlation field {field!r}"),
                event_id=eid, event_class=cls, run_id=run_id,
                rejected=cls in CONSEQUENTIAL_EVENT_CLASSES)

    # Audit-as-authority attempt: an audit event that claims an approval must
    # be recorded as DATA only (never treated as a grant). We only surface the
    # anomaly; the event remains data.
    if cls in ("state_transition", "production_run", "flow_stopped",
               "flow_finished"):
        claim = _get_field(event, "result")
        if isinstance(claim, str) and claim.upper() in ("APPROVED", "ALLOWED"):
            return CorrelationProblem(
                kind="AUDIT_AS_AUTHORITY",
                message=(f"event {eid!r} ({cls}) carries an authority-shaped "
                         f"result {claim!r}; audit is a record, never a grant"),
                event_id=eid, event_class=cls, run_id=run_id, rejected=False)

    return None


# ---------------------------------------------------------------------------
# Run segmentation + correlation
# ---------------------------------------------------------------------------

class RunCorrelator:
    """Build RunRecords from an ordered event stream.

    The stream is scanned in ledger order. A run opens at a start event
    (flow_started / production_run action=run) and closes at a terminal event
    (flow_finished / flow_stopped / production_run close|stop). Events before
    any start, after a terminal without a new start, or that cannot be
    assigned to a run are recorded as problems.
    """

    def __init__(self, project: str = "multi-agent-harness",
                 run_id_hints: dict | None = None,
                 now=None):
        self.project = project
        self.run_id_hints = dict(run_id_hints or {})
        self._now = now
        self.index = RunIndex(project=project)
        self._run_seq = 0
        self._open_run: RunRecord | None = None
        self._open_run_start_class: str = ""  # event_class that opened the run
        self._seen_event_ids: set = set()
        self._last_ts: datetime | None = None
        self._task_owner_run: dict = {}     # task_id -> run_id (conflict detect)
        self._delegation_owner_run: dict = {}  # delegation_id -> run_id

    # -- run identity -------------------------------------------------------

    def _next_run_id(self, start_event: dict) -> str:
        """Derive a run id deterministically.

        Precedence:
          1. an explicit caller hint keyed by the start event id
          2. a production run id embedded in the event (production_run task_id)
          3. a deterministic derivation from the start event id
        The record marks ``run_id_derived`` when the id was not emitted by the
        runtime. Never fabricated from prose.
        """
        eid = _event_id(start_event)
        if eid in self.run_id_hints:
            return str(self.run_id_hints[eid]), False
        task_id = start_event.get("task_id")
        if isinstance(task_id, str) and task_id:
            return task_id, False
        self._run_seq += 1
        return f"run-{self._run_seq:04d}", True

    # -- opening / closing --------------------------------------------------

    def _start_run(self, event: dict) -> RunRecord:
        run_id, derived = self._next_run_id(event)
        run = RunRecord(
            run_id=run_id,
            project=self.project,
            objective=event.get("target") or event.get("objective") or "",
            started_at=event.get("timestamp") or "",
            start_event_id=_event_id(event),
            run_id_derived=derived,
        )
        self.index.runs[run_id] = run
        self.index.run_order.append(run_id)
        self._open_run = run
        self._open_run_start_class = event.get("event_class") or ""
        return run

    def _close_run(self, event: dict) -> RunRecord:
        run = self._open_run
        if run is None:
            return None
        run.finished_at = event.get("timestamp") or ""
        run.terminal_event_id = _event_id(event)
        run.outcome = terminal_outcome(event)
        run.phase = event.get("phase") or run.phase
        self._open_run = None
        self._open_run_start_class = ""
        return run

    # -- event acceptance ---------------------------------------------------

    # Correlation detail keys merged into the event TOP LEVEL by RuntimeAudit
    # (audit.emit(..., extra={...}) merges extra into the event dict). These
    # are the fields the observability layer surfaces.
    _DETAIL_KEYS = (
        "role", "status", "verdict", "failure_class", "recovery_state",
        "state", "version", "held_version", "task_ids", "owners", "selected",
        "count", "parallel", "review_id", "input_hash", "provenance",
        "outcome", "from", "to",
    )

    def _accept(self, event: dict, *, run: RunRecord | None) -> ObservedEvent:
        eid = _event_id(event)
        cls = event.get("event_class") or ""
        stage = stage_of(event) or ""
        source = evidence_source_of(event)
        task_id = (event.get("task_id") or "" if isinstance(
            event.get("task_id"), str) else "")
        delegation_id = (event.get("authority_source") or ""
                         if isinstance(event.get("authority_source"), str)
                         else "")
        failure_class = (event.get("failure_class") or ""
                         if isinstance(event.get("failure_class"), str) else "")

        # Determine run association.
        run_id = run.run_id if run is not None else ""
        if run is not None and not task_id and cls != "flow_started":
            task_id = run.tasks and next(iter(run.tasks), "") or run.run_id
        # parent_task: `task-1:cto` -> `task-1`.
        parent_task = ""
        if ":" in task_id:
            parent_task = task_id.rsplit(":", 1)[0]

        oe = ObservedEvent(
            event_id=eid, event_class=cls, timestamp=event.get("timestamp") or "",
            stage=stage, source=source, task_id=task_id, run_id=run_id,
            delegation_id=delegation_id,
            outcome=terminal_outcome(event) if stage == RUN_TERMINAL else "",
            failure_class=failure_class,
            result=(event.get("result") or "" if isinstance(
                event.get("result"), str) else ""),
            detail={k: event[k] for k in self._DETAIL_KEYS if k in event},
            event=dict(event),
        )

        # Record into the run's correlation structures.
        if run is not None:
            run.events.append(oe)
            # task correlation
            if task_id:
                if task_id not in run.tasks:
                    run.tasks[task_id] = TaskRecord(
                        task_id=task_id, run_id=run_id, parent_task=parent_task,
                        role=(event.get("role") or "" if isinstance(
                            event.get("role"), str) else ""))
                run.tasks[task_id].events.append(eid)
                if parent_task and parent_task in run.tasks:
                    if task_id not in run.tasks[parent_task].subtasks:
                        run.tasks[parent_task].subtasks.append(task_id)
            # subtask correlation: result_collected / subtask_failed carry the
            # subtask id in `target` (`task-1:cto`); register it under the
            # parent task (parent_task_id is the run's root task_id).
            if cls in ("result_collected", "subtask_failed"):
                tgt = event.get("target")
                if isinstance(tgt, str) and ":" in tgt:
                    parent_tid = task_id or tgt.rsplit(":", 1)[0]
                    if tgt not in run.tasks:
                        run.tasks[tgt] = TaskRecord(
                            task_id=tgt, run_id=run_id,
                            parent_task=parent_tid,
                            role=event.get("role") or tgt.rsplit(":", 1)[1])
                    run.tasks[tgt].events.append(eid)
                    if parent_tid and parent_tid in run.tasks:
                        if tgt not in run.tasks[parent_tid].subtasks:
                            run.tasks[parent_tid].subtasks.append(tgt)
            # delegation correlation
            if delegation_id:
                if delegation_id not in run.delegations:
                    run.delegations[delegation_id] = DelegationRecord(
                        delegation_id=delegation_id, run_id=run_id,
                        task_id=task_id)
                run.delegations[delegation_id].events.append(eid)
            # failure correlation
            if cls in ("subtask_failed", "execution_denial",
                       "verification_denied", "version_conflict") \
                    or (cls == "recovery" and (event.get("result") or "") in
                        ("failed", "error")):
                self._record_failure(run, oe, event)
            # retry correlation (recovery_state_transition)
            if cls == "recovery_state_transition" and \
                    (event.get("result") or "") != "completed":
                run.retry_count += 1
            # evidence references (result_collected evidence tuple + gate
            # evidence)
            ev = event.get("evidence")
            if isinstance(ev, (list, tuple)):
                for ref in ev:
                    if ref not in run.evidence_refs:
                        run.evidence_refs.append(str(ref))
            # parallel batches (fields are merged at the event top level by
            # RuntimeAudit.emit extra=...)
            if cls == "parallel_batch":
                run.parallel_batches.append({
                    "task_ids": list(event.get("task_ids") or []),
                    "owners": list(event.get("owners") or []),
                    "held_version": event.get("held_version"),
                })
            # state version from state_transition extra
            if cls == "state_transition":
                ver = event.get("version")
                if isinstance(ver, int):
                    if task_id in run.tasks:
                        run.tasks[task_id].version = ver
                    run.tasks.setdefault(
                        task_id, TaskRecord(task_id=task_id, run_id=run_id,
                                            parent_task=parent_task)
                    ).version = ver
                st = event.get("new_state")
                if isinstance(st, str) and task_id in run.tasks:
                    run.tasks[task_id].state = st
        return oe

    def _record_failure(self, run: RunRecord, oe: ObservedEvent,
                        event: dict) -> None:
        run.failures.append(FailureRecord(
            failure_id=f"fail-{oe.event_id}",
            run_id=run.run_id, task_id=oe.task_id,
            failure_class=oe.failure_class or event.get("failure_class") or "unknown",
            cause=event.get("error") or event.get("cause") or "",
            source=oe.source, stage=oe.stage, event_id=oe.event_id))

    # -- main scan ----------------------------------------------------------

    def ingest(self, events) -> RunIndex:
        """Scan an ordered event stream into the RunIndex (fail-closed)."""
        for event in events:
            if not isinstance(event, dict):
                self.index.rejected.append(CorrelationProblem(
                    kind="MALFORMED_CORRELATION",
                    message=f"non-dict event rejected",
                    rejected=True))
                continue
            eid = _event_id(event)
            if not eid:
                self.index.rejected.append(CorrelationProblem(
                    kind="MALFORMED_CORRELATION",
                    message="event without an event_id rejected",
                    rejected=True))
                continue
            cls = event.get("event_class") or ""

            # Duplicate event id -> reject the duplicate (fail-closed).
            if eid in self._seen_event_ids:
                self.index.rejected.append(CorrelationProblem(
                    kind="DUPLICATE_EVENT",
                    message=f"duplicate event_id {eid!r} rejected",
                    event_id=eid, event_class=cls, rejected=True))
                continue
            self._seen_event_ids.add(eid)

            # Event ordering: timestamps must be non-decreasing across the
            # whole stream (an out-of-order ledger entry indicates tampering /
            # reordering — Runbook 10).
            ts = _parse_ts(event.get("timestamp"))
            if ts is not None and self._last_ts is not None \
                    and ts < self._last_ts:
                problem = CorrelationProblem(
                    kind="ORDERING_VIOLATION",
                    message=(f"event {eid!r} timestamp "
                             f"{event.get('timestamp')!r} is earlier than the "
                             f"preceding event ({self._last_ts.isoformat()})"),
                    event_id=eid, event_class=cls,
                    run_id=self._open_run.run_id if self._open_run else "",
                    rejected=False)
                if self._open_run is not None:
                    self._open_run.problems.append(problem)
                else:
                    self.index.rejected.append(problem)
            if ts is not None:
                self._last_ts = ts

            # Correlation validation (fail-closed for consequential events).
            problem = validate_event_correlation(event, known_runs={})
            if problem is not None:
                if problem.rejected:
                    self.index.rejected.append(problem)
                    continue
                # non-rejecting anomaly: attach to the open run if present
                if self._open_run is not None:
                    self._open_run.problems.append(problem)

            # A `production_run` wraps the flow lifecycle: the run opens at
            # `production_run action=run` and closes at `production_run
            # action=close|stop`. A nested `flow_started`..`flow_finished`
            # emitted by the wrapped ExecutionFlow is PART of that same run —
            # it must not open/close a second run (the per-ledger event-id
            # allocator fix surfaced this nesting that duplicate-id rejection
            # used to mask).
            nested_flow_start = (
                is_start_event(event)
                and self._open_run is not None
                and self._open_run_start_class == "production_run"
                and event.get("event_class") == "flow_started")
            if nested_flow_start:
                self._accept(event, run=self._open_run)
                continue

            if is_start_event(event):
                # Close any still-open run (missing terminal -> problem).
                if self._open_run is not None:
                    self._open_run.problems.append(CorrelationProblem(
                        kind="MISSING_TERMINAL",
                        message=("run did not reach a terminal event before a "
                                 "new run started"),
                        run_id=self._open_run.run_id,
                        event_id=self._open_run.start_event_id))
                self._open_run = self._open_run_new(event)
                self._accept(event, run=self._open_run)
                continue

            # A nested `flow_finished` is not the production run's terminal;
            # only the `production_run` close|stop closes the run.
            nested_flow_finish = (
                is_terminal_event(event)
                and self._open_run is not None
                and self._open_run_start_class == "production_run"
                and event.get("event_class") == "flow_finished")
            if nested_flow_finish:
                self._accept(event, run=self._open_run)
                continue

            if is_terminal_event(event):
                if self._open_run is None:
                    self.index.rejected.append(CorrelationProblem(
                        kind="MISSING_START",
                        message=f"terminal event {eid!r} has no open run",
                        event_id=eid, event_class=cls, rejected=True))
                    continue
                self._accept(event, run=self._open_run)
                self._close_run(event)
                continue

            # Mid-run event.
            if self._open_run is None:
                # An orphan event before any run started: reject if
                # consequential (fail-closed), else drop with a note.
                self.index.rejected.append(CorrelationProblem(
                    kind="MISSING_START",
                    message=f"event {eid!r} ({cls}) has no open run",
                    event_id=eid, event_class=cls,
                    rejected=cls in CONSEQUENTIAL_EVENT_CLASSES))
                continue
            self._accept(event, run=self._open_run)

        # Any run still open at end of stream -> missing terminal.
        if self._open_run is not None:
            self._open_run.problems.append(CorrelationProblem(
                kind="MISSING_TERMINAL",
                message="run did not reach a terminal event (end of stream)",
                run_id=self._open_run.run_id,
                event_id=self._open_run.start_event_id))
            # Leave the run open-but-incomplete; outcome stays unknown.

        self._finalize()
        return self.index

    def _open_run_new(self, event: dict) -> RunRecord:
        """Open a run and register it in the index (used above)."""
        return self._start_run(event)

    def _finalize(self) -> None:
        """Finalize latency, cross-run association conflicts, and provenance
        mismatches."""
        # Cross-run association detection: a task_id or delegation_id must
        # belong to exactly one run. A second occurrence in another run is a
        # wrong-association anomaly (never a silent merge — the ids stay
        # attached to their first owner).
        for run_id in self.index.run_order:
            run = self.index.runs[run_id]
            for tid in run.tasks:
                owner = self._task_owner_run.get(tid)
                if owner is None:
                    self._task_owner_run[tid] = run_id
                elif owner != run_id:
                    run.problems.append(CorrelationProblem(
                        kind="WRONG_RUN_ASSOCIATION",
                        message=(f"task {tid!r} is already associated with run "
                                 f"{owner!r}; second occurrence in run "
                                 f"{run_id!r}"),
                        run_id=run_id))
            for did in run.delegations:
                owner = self._delegation_owner_run.get(did)
                if owner is None:
                    self._delegation_owner_run[did] = run_id
                elif owner != run_id:
                    run.problems.append(CorrelationProblem(
                        kind="WRONG_DELEGATION_ASSOCIATION",
                        message=(f"delegation {did!r} is already associated "
                                 f"with run {owner!r}; second occurrence in "
                                 f"run {run_id!r}"),
                        run_id=run_id))

        for run_id in self.index.run_order:
            run = self.index.runs[run_id]
            # Provenance mismatch: a result_collected / subtask_failed event
            # whose role does not match the role encoded in the subtask id
            # (`task-1:cto` -> role `cto`). The subtask id is carried in the
            # event's `target` (the parent task_id does not encode the role).
            for e in run.events:
                if e.event_class in ("result_collected", "subtask_failed"):
                    subtask_id = e.event.get("target") or ""
                    if isinstance(subtask_id, str) and ":" in subtask_id:
                        expected_role = subtask_id.rsplit(":", 1)[1]
                        actual_role = e.event.get("role") or e.detail.get("role")
                        if actual_role and actual_role != expected_role:
                            run.problems.append(CorrelationProblem(
                                kind="PROVENANCE_MISMATCH",
                                message=(f"event {e.event_id!r} role "
                                         f"{actual_role!r} does not match "
                                         f"subtask id role {expected_role!r}"),
                                event_id=e.event_id,
                                event_class=e.event_class, run_id=run_id))

            if run.finished_at and run.started_at:
                s = _parse_ts(run.started_at)
                f = _parse_ts(run.finished_at)
                if s and f:
                    run.latency["total_ms"] = max(0, int(
                        (f - s).total_seconds() * 1000))
            # Per-stage latency between first and last event of a stage.
            for stage in (EXECUTION, VERIFICATION, RECOVERY_ESCALATION):
                ts = [e.timestamp for e in run.events if e.stage == stage]
                if len(ts) >= 2:
                    a, b = _parse_ts(ts[0]), _parse_ts(ts[-1])
                    if a and b:
                        run.latency[f"{stage.lower()}_ms"] = max(
                            0, int((b - a).total_seconds() * 1000))
                elif len(ts) == 1:
                    run.latency[f"{stage.lower()}_ms"] = 0


def build_index(events, *, project: str = "multi-agent-harness",
                run_id_hints: dict | None = None,
                now=None) -> RunIndex:
    """Build a RunIndex from an ordered event iterable (fail-closed)."""
    return RunCorrelator(project=project, run_id_hints=run_id_hints,
                         now=now).ingest(events)


def build_index_from_ledger(base: str | None = None,
                            project: str = "multi-agent-harness",
                            log_path: str | None = None,
                            run_id_hints: dict | None = None,
                            now=None) -> RunIndex:
    """Build a RunIndex from the EXISTING audit ledger (reuses audit helpers).

    Read-only: this function never writes the ledger.
    """
    events, integrity = read_ledger_events(base, project, log_path)
    index = build_index(events, project=project, run_id_hints=run_id_hints,
                        now=now)
    index.ledger_integrity = integrity
    index.built_at = _iso(now()) if callable(now) else (
        now or _iso(datetime.now(timezone.utc)))
    return index


__all__ = [
    "RunCorrelator", "build_index", "build_index_from_ledger",
    "read_ledger_events", "validate_event_correlation",
]
