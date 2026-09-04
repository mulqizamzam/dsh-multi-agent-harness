# orchestrator.organization.root — ROOT final aggregation (MVP)
#
# Pure aggregation of recorded DATA (handoffs, review records, rework
# orders, evidence events).  The verdict NEVER grants authority and
# refuses COMPLETE unless every task is done with satisfied evidence and
# accepted reviews.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dataclasses import dataclass
from datetime import datetime, timezone

OUTCOMES = ("COMPLETE", "BLOCKED", "ESCALATED")


@dataclass(frozen=True)
class RootVerdict:
    mission_id: str
    outcome: str
    reason: str
    waves_executed: int = 0
    handoffs: tuple[dict, ...] = ()
    reviews: tuple[dict, ...] = ()
    rework_orders: tuple[dict, ...] = ()
    escalations: tuple[str, ...] = ()
    open_risks: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    evidence_events: int = 0
    produced_at: str = ""

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "outcome": self.outcome,
            "reason": self.reason,
            "waves_executed": self.waves_executed,
            "handoffs": [dict(h) for h in self.handoffs],
            "reviews": [dict(r) for r in self.reviews],
            "rework_orders": [dict(o) for o in self.rework_orders],
            "escalations": list(self.escalations),
            "open_risks": list(self.open_risks),
            "unknowns": list(self.unknowns),
            "evidence_events": self.evidence_events,
            "produced_at": self.produced_at,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _kinds_in(evidence) -> set[str]:
    kinds: set[str] = set()
    for e in evidence or ():
        if isinstance(e, str) and ":" in e:
            k, ref = e.split(":", 1)
            if k.strip() and ref.strip():
                kinds.add(k.strip())
    return kinds


def build_verdict(
    *,
    mission_id: str,
    handoffs: dict[str, object] | None,
    expected_tasks: tuple[str, ...] = (),
    reviews: list[dict] | None = None,
    rework_orders: tuple[dict, ...] | None = None,
    escalations: tuple[str, ...] | list[str] | None = None,
    blockers: tuple[str, ...] | list[str] | None = None,
    waves_executed: int = 0,
    evidence_events: int = 0,
    required_evidence: dict[str, tuple[str, ...]] | None = None,
    expected_reviewers: dict[str, tuple[str, ...]] | None = None,
) -> RootVerdict:
    statuses = {tid: getattr(h, "status", "") for tid, h in (handoffs or {}).items()}
    not_done = sorted(tid for tid in expected_tasks if statuses.get(tid) != "done")
    # Latest per (reviewer, target) — a later rework's review supersedes.
    latest: dict[tuple[str, str], str] = {}
    for r in reviews or ():
        key = (str(r.get("reviewer", "")), str(r.get("target_task_id", "")))
        latest[key] = str(r.get("action", ""))
    unaccepted = sorted(t for (_, t), a in latest.items() if a != "accept")
    # Direct evidence invariant: COMPLETE requires every expected task's
    # required_evidence kinds to be present as kind:ref in its handoff.
    # Do not rely solely on caller-side prevalidation (handoff status).
    missing_evidence: list[str] = []
    if required_evidence is not None:
        for tid in expected_tasks:
            req = tuple(required_evidence.get(tid, ()) or ())
            if not req:
                continue
            ho = (handoffs or {}).get(tid)
            ev = getattr(ho, "evidence", ()) if ho is not None else ()
            have = _kinds_in(ev)
            miss = [k for k in req if k not in have]
            if miss:
                missing_evidence.append(f"{tid}: missing {sorted(miss)}")
    # Direct reviewer invariant: when expected_reviewers is supplied,
    # every expected reviewer must have an accepted decision. Missing
    # review is not acceptance (fail-closed).
    missing_reviews: list[str] = []
    if expected_reviewers is not None:
        for tid, reviewers in expected_reviewers.items():
            if tid not in expected_tasks:
                continue
            for reviewer in reviewers or ():
                key = (str(reviewer), str(tid))
                action = latest.get(key, "")
                if action != "accept":
                    missing_reviews.append(f"{reviewer}->{tid}: {action or 'missing'}")
        # normalize
        missing_reviews = sorted(set(missing_reviews))
    open_risks: tuple[str, ...] = tuple(
        sorted({r for h in (handoffs or {}).values() for r in getattr(h, "risks", ())})
    )
    unknowns: tuple[str, ...] = tuple(
        sorted({u for h in (handoffs or {}).values() for u in getattr(h, "unknowns", ())})
    )
    handoff_dicts = tuple(getattr(h, "to_dict", lambda: dict(h))() for h in (handoffs or {}).values())
    escalations = tuple(escalations or ())
    blockers = tuple(blockers or ())
    if escalations:
        outcome, reason = "ESCALATED", "; ".join(str(e) for e in escalations)
    elif blockers:
        outcome, reason = "BLOCKED", "; ".join(str(b) for b in blockers)
    elif not_done:
        outcome, reason = "BLOCKED", f"tasks not done: {not_done}"
    elif missing_evidence:
        outcome, reason = "BLOCKED", f"required evidence not satisfied: {missing_evidence}"
    elif missing_reviews:
        outcome, reason = "BLOCKED", f"required reviewer decisions not accepted: {missing_reviews}"
    elif unaccepted:
        outcome, reason = "BLOCKED", f"reviews not accepted for: {unaccepted}"
    else:
        outcome, reason = "COMPLETE", "all tasks done with satisfied evidence and accepted reviews"
    return RootVerdict(
        mission_id=mission_id,
        outcome=outcome,
        reason=reason,
        waves_executed=waves_executed,
        handoffs=handoff_dicts,
        reviews=tuple(dict(r) for r in reviews or ()),
        rework_orders=tuple(dict(o) for o in rework_orders or ()),
        escalations=escalations,
        open_risks=open_risks,
        unknowns=unknowns,
        evidence_events=evidence_events,
        produced_at=_now_iso(),
    )
