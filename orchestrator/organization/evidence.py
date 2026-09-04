# orchestrator.organization.evidence — evidence ledger (MVP)
#
# Records typed evidence for every task result INTO THE EXISTING runtime
# audit ledger (RuntimeAudit — the same append-only ledger the flow uses).
# No second audit system.  Acceptance: a task's required_evidence kinds
# must each appear in its result evidence as "kind:ref".
#
# Worker claims are never accepted as evidence by themselves — evidence
# must be a typed "kind:ref" entry with a non-empty ref.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from .packet import EVIDENCE_KINDS, MissionTask  # noqa: E402

EVENT_CLASS = "org_evidence"


class EvidenceLedger:
    """Thin ledger over the existing RuntimeAudit.

    ledger_id = audit event id; satisfied/missing are pure predicates over
    the evidence strings the workers cited.
    """

    def __init__(self, audit):
        self._audit = audit

    # -- evidence normalization ---------------------------------------------
    @staticmethod
    def _kinds_in(evidence: tuple[str, ...] | list[str] | None) -> set[str]:
        kinds: set[str] = set()
        for e in evidence or ():
            if isinstance(e, str) and ":" in e:
                k, ref = e.split(":", 1)
                if k in EVIDENCE_KINDS and ref.strip():
                    kinds.add(k)
        return kinds

    def missing(self, task: MissionTask, evidence) -> tuple[str, ...]:
        have = self._kinds_in(evidence)
        return tuple(k for k in task.required_evidence if k not in have)

    def satisfied(self, task: MissionTask, evidence) -> bool:
        return not self.missing(task, evidence)

    # -- persistence (same audit ledger, event class scoped) ----------------
    def record(
        self,
        *,
        mission_id: str,
        task_id: str,
        evidence,
        producer: str,
    ) -> str:
        ev = tuple(evidence or ())
        # Persist typed evidence entries (kind:ref) into the existing RuntimeAudit
        # event so reconstruction is possible without a second store. Evidence is
        # stored both in the audit's typed `evidence` field and in `extra` for
        # explicit round-trip (audit extra keys are merged top-level).
        kinds = sorted(self._kinds_in(ev))
        event_id = self._audit.emit(
            EVENT_CLASS,
            actor=producer or "orchestrator",
            action="evidence_record",
            target=task_id,
            task_id=task_id,
            evidence=ev,
            extra={
                "mission_id": mission_id,
                "producer": producer,
                "evidence": list(ev),
                "evidence_kinds": kinds,
            },
        )
        return event_id

    def events(self, mission_id: str | None = None) -> list[dict]:
        # Prefer the ledger helper when available; fall back to full read.
        try:
            evs = self._audit.events_of_class(EVENT_CLASS)  # type: ignore[attr-defined]
        except Exception:
            try:
                evs = [e for e in self._audit.read() if e.get("event_class") == EVENT_CLASS]  # type: ignore[attr-defined, call-arg]
            except Exception:
                return []
        if mission_id is None:
            return list(evs)
        filtered: list[dict] = []
        for e in evs:
            # audit extra keys are merged top-level unless colliding
            if e.get("mission_id") == mission_id or e.get("extra", {}).get("mission_id") == mission_id:
                filtered.append(e)
        return filtered
