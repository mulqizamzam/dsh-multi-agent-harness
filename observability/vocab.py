# observability.vocab — Event lifecycle vocabulary and fail-closed correlation spec
#
# Phase 4 / Session D — Production operations + observability.
#
# This module defines the OBSERVABILITY vocabulary only. It introduces NO
# authority, NO new audit implementation, and NO runtime change. It maps the
# EXISTING runtime audit event classes (emitted by orchestrator.runtime /
# orchestrator.execution / orchestrator.production) onto a lifecycle-stage
# model, classifies each event's evidence source (AGENT-REPORTED /
# RUNTIME-OBSERVED / CONTROL-PLANE-DECISION), and declares which correlation
# fields each event class REQUIRES so the ingest path can reject malformed or
# under-correlated events fail-closed (never fabricate IDs).
#
# Audit events are DATA (AUTH-INV-14): this module never treats an event, a
# `result`, an `authority_source` string, or a `verdict` as a grant.

from __future__ import annotations

# ---------------------------------------------------------------------------
# Lifecycle stages (the bounded-run event lifecycle)
# ---------------------------------------------------------------------------
RUN_STARTED = "RUN_STARTED"
TASK_CREATED = "TASK_CREATED"
ROUTING = "ROUTING"
DELEGATION = "DELEGATION"
SUBTASK_EXECUTION = "SUBTASK_EXECUTION"
COLLECTION = "COLLECTION"
GATES = "GATES"
EXECUTION = "EXECUTION"
VERIFICATION = "VERIFICATION"
RECOVERY_ESCALATION = "RECOVERY_ESCALATION"
RUN_TERMINAL = "RUN_TERMINAL"

LIFECYCLE_STAGES = (
    RUN_STARTED, TASK_CREATED, ROUTING, DELEGATION, SUBTASK_EXECUTION,
    COLLECTION, GATES, EXECUTION, VERIFICATION, RECOVERY_ESCALATION,
    RUN_TERMINAL,
)

# Canonical ordering used for missing/duplicate/ordering detection. GATES and
# RECOVERY_ESCALATION may repeat; RUN_TERMINAL must appear exactly once and
# LAST.
_STAGE_ORDER = {stage: i for i, stage in enumerate(LIFECYCLE_STAGES)}

# ---------------------------------------------------------------------------
# Evidence sources (aligned with tests/evidence/evidence_qa.py EVIDENCE_SOURCES)
# ---------------------------------------------------------------------------
AGENT_REPORTED = "AGENT-REPORTED"
RUNTIME_OBSERVED = "RUNTIME-OBSERVED"
CONTROL_PLANE_DECISION = "CONTROL-PLANE-DECISION"
INDEPENDENTLY_VERIFIED = "INDEPENDENTLY-VERIFIED"

EVIDENCE_SOURCES = (
    AGENT_REPORTED, RUNTIME_OBSERVED, CONTROL_PLANE_DECISION,
    INDEPENDENTLY_VERIFIED,
)

# ---------------------------------------------------------------------------
# Terminal outcomes (aligned with orchestrator.runtime.result OUTCOMES)
# ---------------------------------------------------------------------------
OUTCOME_COMPLETE = "COMPLETE"
OUTCOME_BLOCKED = "BLOCKED"
OUTCOME_FAILED = "FAILED"
OUTCOME_ESCALATED = "ESCALATED"
OUTCOME_RECOVERING = "RECOVERING"

# ---------------------------------------------------------------------------
# Start / terminal event classes
# ---------------------------------------------------------------------------
START_EVENT_CLASSES = ("flow_started", "production_run")
# production_run actions that open/close a production run.
PRODUCTION_START_ACTIONS = ("run",)
PRODUCTION_TERMINAL_ACTIONS = ("close", "stop")
# Runtime terminal event classes (only `flow_finished` is always the last
# event emitted by the runtime; `flow_stopped` and `state_complete` are
# mid-run events emitted before `flow_finished`).
TERMINAL_EVENT_CLASSES = ("flow_finished",)

# ---------------------------------------------------------------------------
# event_class -> lifecycle stage
# ---------------------------------------------------------------------------
EVENT_STAGE = {
    # start
    "flow_started": RUN_STARTED,
    # task
    "intake_recorded": TASK_CREATED,
    # routing / delegation
    "routing_selected": ROUTING,
    "delegation_issued": DELEGATION,
    # subtask execution + parallel control
    "subtasks_executed": SUBTASK_EXECUTION,
    "parallel_batch": SUBTASK_EXECUTION,
    "parallel_refused": SUBTASK_EXECUTION,
    "subtask_failed": SUBTASK_EXECUTION,
    # collection
    "result_collected": COLLECTION,
    # gates
    "gate_risk": GATES,
    "gate_evidence": GATES,
    "gate_conflict": GATES,
    "gate_review": GATES,
    "gate_authority": GATES,
    "gate_verification": GATES,
    "badsector_review": GATES,
    "authority_context": GATES,
    # execution
    "execution_request_validated": EXECUTION,
    "authority_recheck": EXECUTION,
    "execution_attempt": EXECUTION,
    "execution_denial": EXECUTION,
    "version_conflict": EXECUTION,
    # verification
    "verification_passed": VERIFICATION,
    "verification_denied": VERIFICATION,
    # recovery / escalation
    "recovery": RECOVERY_ESCALATION,
    "recovery_state_transition": RECOVERY_ESCALATION,
    # state / terminal
    "state_transition": GATES,          # control-plane decision, repeated
    "state_complete": RUN_TERMINAL,
    "flow_finished": RUN_TERMINAL,
    "flow_stopped": RUN_TERMINAL,
}

# Consequential event classes: those that require STRICT correlation. A
# malformed/missing required field on one of these REJECTS the event (fail-
# closed) — the ingest never guesses an id.
CONSEQUENTIAL_EVENT_CLASSES = frozenset({
    "gate_risk", "gate_evidence", "gate_conflict", "gate_review",
    "gate_authority", "gate_verification", "badsector_review",
    "delegation_issued", "subtasks_executed", "subtask_failed",
    "parallel_batch", "parallel_refused", "result_collected",
    "execution_request_validated", "authority_recheck", "execution_attempt",
    "execution_denial", "version_conflict",
    "verification_passed", "verification_denied",
    "recovery", "recovery_state_transition",
    "state_transition", "state_complete", "flow_stopped", "flow_finished",
    "production_run",
})

# Non-consequential classes: correlation is best-effort (they may open a run
# or carry context only).
NON_CONSEQUENTIAL_EVENT_CLASSES = frozenset({
    "flow_started", "intake_recorded", "authority_context",
})

# Required correlation fields per event class. Fields are looked up on the
# event dict itself (RuntimeAudit merges `extra` into the top-level event).
# Nested access is expressed with dotted paths (e.g. "extra.task_ids" is
# stored at top level as "task_ids" after merge; we support plain keys).
CORRELATION_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    # --- start / context (no task yet) ---
    "flow_started": (),
    "intake_recorded": ("timestamp",),
    "authority_context": ("authority_source",),
    # --- routing / delegation ---
    "routing_selected": ("task_id", "result"),
    "delegation_issued": ("task_id", "authority_source", "result"),
    # --- subtask execution ---
    "subtasks_executed": ("task_id", "result"),
    "parallel_batch": ("task_id", "task_ids", "owners", "held_version"),
    "parallel_refused": ("task_id", "result"),
    "subtask_failed": ("task_id", "failure_class"),
    # --- collection ---
    "result_collected": ("task_id", "target", "role", "status", "result"),
    # --- gates ---
    "gate_risk": ("task_id", "result"),
    "gate_evidence": ("task_id", "result"),
    "gate_conflict": ("task_id", "result"),
    "gate_review": ("task_id", "result"),
    "gate_authority": ("task_id", "authority_source", "result"),
    "gate_verification": ("task_id", "result"),
    "badsector_review": ("task_id", "verdict"),
    # --- execution ---
    "execution_request_validated": ("task_id", "authority_source"),
    "authority_recheck": ("task_id", "authority_source", "result"),
    "execution_attempt": ("task_id", "authority_source", "result"),
    "execution_denial": ("task_id", "authority_source", "result"),
    "version_conflict": ("task_id", "result"),
    # --- verification ---
    "verification_passed": ("task_id", "result"),
    "verification_denied": ("task_id", "result"),
    # --- recovery ---
    "recovery": ("task_id", "recovery_state", "result"),
    "recovery_state_transition": ("task_id", "state", "failure_class"),
    # --- state / terminal ---
    "state_transition": ("task_id", "result", "new_state"),
    "state_complete": ("task_id", "result"),
    "flow_finished": ("task_id", "result"),
    "flow_stopped": ("task_id", "result"),
    # --- production run (task_id IS the run_id) ---
    "production_run": ("task_id", "action", "result"),
}

# Default source classification per event class. Individual events may refine
# this (e.g. a child-claimed status inside result_collected is
# AGENT-REPORTED; the collection record itself is RUNTIME-OBSERVED).
DEFAULT_EVENT_SOURCE: dict[str, str] = {
    "flow_started": RUNTIME_OBSERVED,
    "production_run": RUNTIME_OBSERVED,
    "intake_recorded": RUNTIME_OBSERVED,
    "authority_context": CONTROL_PLANE_DECISION,
    "routing_selected": CONTROL_PLANE_DECISION,
    "delegation_issued": CONTROL_PLANE_DECISION,
    "subtasks_executed": CONTROL_PLANE_DECISION,
    "parallel_batch": RUNTIME_OBSERVED,
    "parallel_refused": CONTROL_PLANE_DECISION,
    "subtask_failed": RUNTIME_OBSERVED,
    "result_collected": RUNTIME_OBSERVED,
    "gate_risk": CONTROL_PLANE_DECISION,
    "gate_evidence": CONTROL_PLANE_DECISION,
    "gate_conflict": CONTROL_PLANE_DECISION,
    "gate_review": CONTROL_PLANE_DECISION,
    "gate_authority": CONTROL_PLANE_DECISION,
    "gate_verification": CONTROL_PLANE_DECISION,
    "badsector_review": CONTROL_PLANE_DECISION,
    "execution_request_validated": RUNTIME_OBSERVED,
    "authority_recheck": CONTROL_PLANE_DECISION,
    "execution_attempt": RUNTIME_OBSERVED,
    "execution_denial": CONTROL_PLANE_DECISION,
    "version_conflict": RUNTIME_OBSERVED,
    "verification_passed": CONTROL_PLANE_DECISION,
    "verification_denied": CONTROL_PLANE_DECISION,
    "recovery": CONTROL_PLANE_DECISION,
    "recovery_state_transition": CONTROL_PLANE_DECISION,
    "state_transition": CONTROL_PLANE_DECISION,
    "state_complete": CONTROL_PLANE_DECISION,
    "flow_finished": RUNTIME_OBSERVED,
    "flow_stopped": RUNTIME_OBSERVED,
}


def stage_of(event: dict) -> str | None:
    """Map one event dict to its lifecycle stage.

    ``production_run`` events map by action: run -> RUN_STARTED, close/stop ->
    RUN_TERMINAL, otherwise the stage of the phase it represents.
    """
    cls = event.get("event_class")
    if cls == "production_run":
        action = event.get("action")
        if action in PRODUCTION_START_ACTIONS:
            return RUN_STARTED
        if action in PRODUCTION_TERMINAL_ACTIONS:
            return RUN_TERMINAL
        return TASK_CREATED  # plan/execute/report phases
    return EVENT_STAGE.get(cls or "")


def is_start_event(event: dict) -> bool:
    cls = event.get("event_class")
    if cls == "production_run":
        return event.get("action") in PRODUCTION_START_ACTIONS
    return cls in ("flow_started",)


def is_terminal_event(event: dict) -> bool:
    cls = event.get("event_class")
    if cls == "production_run":
        return event.get("action") in PRODUCTION_TERMINAL_ACTIONS
    return cls in TERMINAL_EVENT_CLASSES


def terminal_outcome(event: dict) -> str:
    """Derive the run outcome from a terminal event (never from prose)."""
    cls = event.get("event_class")
    if cls == "production_run":
        return OUTCOME_COMPLETE if event.get("action") == "close" \
            else OUTCOME_BLOCKED
    # A non-string `result` (dict/list/int) must not crash the whole ingest:
    # it simply carries no outcome token -> fail-closed BLOCKED below.
    result = (r.upper() if isinstance(r := event.get("result"), str)
              else "")
    if cls == "flow_stopped":
        if result in ("ESCALATED", "ESCALATE"):
            return OUTCOME_ESCALATED
        if result in ("FAILED", "FAIL"):
            return OUTCOME_FAILED
        return OUTCOME_BLOCKED
    # flow_finished / state_complete
    if result in ("FAILED", "FAIL"):
        return OUTCOME_FAILED
    if result in ("BLOCKED", "BLOCK"):
        return OUTCOME_BLOCKED
    if result in ("ESCALATED", "ESCALATE"):
        return OUTCOME_ESCALATED
    if result in ("COMPLETE", "COMPLETED", "COMPLETION", "complete", "completed"):
        return OUTCOME_COMPLETE
    if result in ("RECOVERING", "RECOVER"):
        return OUTCOME_RECOVERING
    return OUTCOME_BLOCKED  # fail-closed: unknown terminal -> blocked


def evidence_source_of(event: dict) -> str:
    """Classify one event's evidence source (never authority)."""
    cls = event.get("event_class")
    src = DEFAULT_EVENT_SOURCE.get(cls or "", RUNTIME_OBSERVED)
    if cls == "result_collected":
        # The collection record is RUNTIME-OBSERVED; the child's claimed
        # status inside it is AGENT-REPORTED (see classify_field_source).
        return RUNTIME_OBSERVED
    if cls == "execution_attempt":
        # observed outcome/run identity is RUNTIME-OBSERVED; the verdict
        # field inside it is a CONTROL-PLANE-DECISION.
        return RUNTIME_OBSERVED
    return src


def classify_field_source(event: dict, field: str) -> str:
    """Classify ONE field of an event (AGENT-REPORTED subfields)."""
    cls = event.get("event_class")
    if cls == "result_collected" and field in ("status", "findings",
                                               "recommendation", "confidence"):
        return AGENT_REPORTED
    if cls == "subtask_failed" and field == "role":
        return RUNTIME_OBSERVED
    if cls in ("gate_risk", "gate_evidence", "gate_conflict", "gate_review",
               "gate_authority", "gate_verification") and field == "result":
        return CONTROL_PLANE_DECISION
    if cls in ("verification_passed", "verification_denied") \
            and field == "result":
        return CONTROL_PLANE_DECISION
    if cls == "execution_attempt" and field == "verdict":
        return CONTROL_PLANE_DECISION
    return evidence_source_of(event)


def stage_index(stage: str | None) -> int:
    return _STAGE_ORDER.get(stage, -1)


__all__ = [
    "RUN_STARTED", "TASK_CREATED", "ROUTING", "DELEGATION",
    "SUBTASK_EXECUTION", "COLLECTION", "GATES", "EXECUTION", "VERIFICATION",
    "RECOVERY_ESCALATION", "RUN_TERMINAL", "LIFECYCLE_STAGES",
    "AGENT_REPORTED", "RUNTIME_OBSERVED", "CONTROL_PLANE_DECISION",
    "INDEPENDENTLY_VERIFIED", "EVIDENCE_SOURCES",
    "OUTCOME_COMPLETE", "OUTCOME_BLOCKED", "OUTCOME_FAILED",
    "OUTCOME_ESCALATED", "OUTCOME_RECOVERING",
    "START_EVENT_CLASSES", "TERMINAL_EVENT_CLASSES",
    "CONSEQUENTIAL_EVENT_CLASSES", "NON_CONSEQUENTIAL_EVENT_CLASSES",
    "CORRELATION_REQUIREMENTS", "DEFAULT_EVENT_SOURCE",
    "stage_of", "is_start_event", "is_terminal_event", "terminal_outcome",
    "evidence_source_of", "classify_field_source", "stage_index",
]
