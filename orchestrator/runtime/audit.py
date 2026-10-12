# orchestrator.runtime.audit — Runtime audit events (Phase 3)
#
# The runtime records ACTUAL events (gate decisions, state transitions,
# execution attempts, recovery transitions, escalations) into the append-only
# project audit ledger through the sanctioned audit channel
# (control.execution_gate.audit_append — the protected-path writer channel,
# ADR 0002). A runtime event is a RECORD, never a grant (AUTH-INV-14); agent
# prose is never written as a runtime fact.
#
# Event ids follow the audit-event schema pattern `event-<seq>`.
#
# DEFECT CLOSURE (Phase 4 / Targeted audit): ProductionRun and ExecutionFlow
# each create their OWN RuntimeAudit instance, and both append to the SAME
# ledger (audit/<project>/events.jsonl). A per-instance event counter produced
# duplicate event ids. The fix gives the ledger ONE authoritative event-id
# allocation sequence (module-level, keyed by the absolute ledger path, seeded
# from the ledger's existing max event id, advanced under a lock) so:
#   - any number of RuntimeAudit instances on the same ledger share one
#     monotonic sequence (no duplicate event_id);
#   - concurrent writers cannot observe the same id (lock);
#   - a reopened / restarted ledger continues after the ids already on disk;
#   - append-only semantics, the audit schema, the hash chain, and the
#     RuntimeAudit API are unchanged; audit remains DATA, never authority.

from __future__ import annotations

import os
import sys
import threading

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from datetime import datetime, timezone

# Sanctioned audit channel (protected-path writer, ADR 0002). The runtime
# NEVER writes the ledger through raw DSH tools.
from control.execution_gate import audit_append  # noqa: E402


def _now_iso(now=None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Authoritative per-ledger event-id allocation (defect closure)
# ---------------------------------------------------------------------------
# One sequence per ledger FILE, not per RuntimeAudit instance. The key is the
# absolute ledger path so every instance appending to the same ledger shares
# the counter. The sequence is seeded from the ledger's existing max `event-<n>`
# id on first use for a path (reopen/restart safe) and advanced under a
# per-path lock (concurrent writers never observe the same id, and appends
# keep allocation order — append-only monotonicity preserved).
_LEDGER_SEQS: dict[str, int] = {}          # abs ledger path -> last seq
_LEDGER_LOCKS: dict[str, threading.RLock] = {}
_LEDGER_LOCKS_GUARD = threading.Lock()


def _ledger_abs_path(base, project: str) -> str:
    """The absolute ledger path for (base, project) — the allocator key."""
    from control.execution_gate import workspace_base
    base = base or workspace_base()
    return os.path.abspath(os.path.join(
        base, "audit", project, "events.jsonl"))


def _ledger_lock_for(ledger_path: str) -> threading.RLock:
    """Per-ledger reentrant lock (created once per path)."""
    with _LEDGER_LOCKS_GUARD:
        lock = _LEDGER_LOCKS.get(ledger_path)
        if lock is None:
            lock = threading.RLock()
            _LEDGER_LOCKS[ledger_path] = lock
        return lock


def _max_existing_seq(ledger_path: str, *, base=None,
                      project: str | None = None) -> int:
    """Largest `event-<n>` sequence already present in the ledger (0 if none).

    O3 Phase B: the ledger is daemon-owned; the existing max seq is read
    through the O3 daemon (no in-workspace mirror read). `ledger_path` is the
    workspace-form absolute path used as the allocator key.

    When authoritative `base`/`project` are supplied (the RuntimeAudit
    instance's own values), they are used verbatim. Do NOT re-parse the ledger
    path when the base itself contains an "audit" directory (e.g.
    base=/srv/audit/mah): splitting on the FIRST "audit" segment then yields the
    wrong base/project, audit_read fails, this returns 0, and _allocate_seq
    restarts at 1 — duplicate event ids in a live ledger (F9)."""
    max_seq = 0
    try:
        from control.execution_gate import audit_read
        if base is not None and project is not None:
            rel = f"audit/{project}/events.jsonl"
        else:
            # Fallback: extract base and project from the ledger path:
            #   base/audit/<project>/events.jsonl
            parts = ledger_path.replace("\\", "/").split("/")
            try:
                audit_idx = parts.index("audit")
            except ValueError:
                return 0
            project = parts[audit_idx + 1] if audit_idx + 1 < len(parts) else "multi-agent-harness"
            base = "/".join(parts[:audit_idx])
            rel = f"audit/{project}/events.jsonl"
        result = audit_read(rel, base=base)
        events = result.get("events") or []
    except Exception:
        return 0  # daemon down / not readable → fail-closed: no fabricated seq
    for e in events:
        eid = e.get("event_id") or ""
        if eid.startswith("event-"):
            try:
                max_seq = max(max_seq, int(eid[len("event-"):]))
            except ValueError:
                continue
    return max_seq


def _allocate_seq(ledger_path: str, *, base=None,
                  project: str | None = None) -> int:
    """Advance the per-ledger sequence. Caller holds the path lock."""
    seq = _LEDGER_SEQS.get(ledger_path)
    if seq is None:
        seq = _max_existing_seq(ledger_path, base=base, project=project)
    seq += 1
    _LEDGER_SEQS[ledger_path] = seq
    return seq


def allocate_event_id(base, project: str) -> int:
    """Allocate the next event sequence for the ledger at (base, project).

    Thread-safe and shared across all RuntimeAudit instances writing to the
    same ledger: the sequence is keyed by the absolute ledger path, seeded
    from the ledger's existing max event id, and advanced under a per-path
    lock. It never re-allocates an id already present in the ledger.
    """
    ledger_path = _ledger_abs_path(base, project)
    with _ledger_lock_for(ledger_path):
        return _allocate_seq(ledger_path, base=base, project=project)


class RuntimeAudit:
    """Append-only runtime audit ledger.

    Wraps control.execution_gate.audit_append so every runtime event lands on
    disk through the sanctioned writer channel (no bypass). Events carry the
    schema-shaped fields (actor/action/target/project/result/authority_source)
    and a monotonic event id.

    Parameters
    ----------
    base:
        Workspace base (the audit ledger lives under ``audit/<project>/``).
    project:
        Project id (default "multi-agent-harness").
    now:
        Optional clock override (tests) — callable or datetime; defaults to
        UTC now.
    """

    def __init__(self, base=None, project: str = "multi-agent-harness",
                 now=None):
        from control.execution_gate import workspace_base
        self.base = base or workspace_base()
        self.project = project
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._seq = 0
        self._log_path_rel = f"audit/{project}/events.jsonl"

    # -- public -------------------------------------------------------------

    def emit(self, event_class: str, *, actor: str = "orchestrator",
             action: str = "", target: str = "", task_id: str = "",
             authority_source: str = "", evidence: tuple = (),
             previous_state: str = "", new_state: str = "",
             result: str = "recorded", error: str = "",
             extra: dict | None = None) -> str:
        """Append one runtime audit event. Returns its event_id.

        The event-id is allocated from the authoritative per-ledger sequence
        (module-level, lock-protected, seeded from the ledger's existing
        events). Any number of RuntimeAudit instances on the same ledger file
        share one counter — no duplicate event ids. The per-ledger lock is
        held across allocation AND append so concurrent writers keep the file
        in allocation order (append-only monotonicity preserved).
        """
        ledger_path = _ledger_abs_path(self.base, self.project)
        with _ledger_lock_for(ledger_path):
            seq = _allocate_seq(ledger_path, base=self.base,
                                project=self.project)
            self._seq = seq
            event_id = f"event-{seq:06d}"
            event = {
                "event_id": event_id,
                "timestamp": _now_iso(self._now()),
                "event_class": event_class,
                "actor": actor,
                "actor_type": "control_plane",
                "action": action or event_class,
                "target": target or self.project,
                "project": self.project,
                "task_id": task_id or None,
                "authority_source": authority_source or None,
                "evidence": list(evidence),
                "previous_state": previous_state or None,
                "new_state": new_state or None,
                "result": result,
                "error": error or None,
                "agent_reported": None,
            }
            if extra:
                event.update({k: v for k, v in extra.items()
                              if k not in event})
            audit_append(self.log_path(), event, base=self.base)
        return event_id

    def emit_dict(self, event: dict) -> str:
        """Emit an event supplied as a pre-shaped dict (adapter for the
        ExecutionEngine's ``audit(event_dict)`` contract).  The dict must
        carry an ``event_class``; other schema fields are honored."""
        if not isinstance(event, dict):
            return ""
        event_class = event.pop("event_class", "runtime")
        return self.emit(
            event_class,
            actor=event.pop("actor", "orchestrator"),
            action=event.pop("action", ""),
            target=event.pop("target", ""),
            task_id=event.pop("task_id", ""),
            authority_source=event.pop("authority_source", ""),
            evidence=tuple(event.pop("evidence", []) or []),
            previous_state=event.pop("previous_state", ""),
            new_state=event.pop("new_state", ""),
            result=event.pop("result", "recorded"),
            error=event.pop("error", ""),
            extra=event or None,
        )

    def log_path(self) -> str:
        return self._log_path_rel

    def read(self) -> list:
        """Read all events from the ledger (lenient).

        O3 Phase B: reads through the O3 daemon (no in-workspace mirror)."""
        from control.execution_gate import audit_read
        result = audit_read(self.log_path(), base=self.base)
        return list(result.get("events") or [])

    def events_of_class(self, event_class: str) -> list:
        return [e for e in self.read()
                if e.get("event_class") == event_class]

    def review_log(self) -> list:
        """BadSector review invocation records (for PASS provenance,
        THREAT-014/BAD-001)."""
        return [e for e in self.read()
                if e.get("event_class") == "badsector_review"
                and e.get("review_id")]


__all__ = ["RuntimeAudit", "_now_iso", "allocate_event_id",
           "_ledger_abs_path", "_max_existing_seq"]
