# orchestrator.organization.rework — critic verdicts + bounded rework (MVP)
#
# BADSECTOR/SOMAD verdicts are DATA on their TaskResult.recommendation
# (validated against a verdict vocabulary — never parsed from prose).
# A non-accept verdict sends TYPED FINDINGS back to the owning specialist.
# Budget: MAX_REWORK_CYCLES rework cycles per worker task, then ESCALATE
# to ROOT.  No infinite retry.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dataclasses import dataclass, field

from control.badsector import VALID_VERDICTS as _BADSECTOR_VERDICTS  # noqa: E402

from .packet import MissionError, MissionTask  # noqa: E402

MAX_REWORK_CYCLES = 2

BADSECTOR_VERDICTS = frozenset(_BADSECTOR_VERDICTS)          # PASS/REWORK/REJECT
SOMAD_VERDICTS = frozenset({"VERIFIED", "REWORK", "REFUTED"})
REWORK_VERDICTS = frozenset({"REWORK", "REJECT", "REFUTED"})
ACCEPT_VERDICTS = frozenset({"PASS", "VERIFIED"})


class ReworkExhausted(MissionError):
    """Budget exhausted — must escalate to ROOT."""


def critic_verdicts_for(reviewer: str) -> frozenset[str]:
    if reviewer == "badsector":
        return BADSECTOR_VERDICTS
    if reviewer == "somad":
        return SOMAD_VERDICTS
    raise MissionError(f"{reviewer!r} is not a reviewer role")


def critic_verdict(result, reviewer: str) -> str:
    """Extract the typed critic verdict; fail-closed on unknown."""
    verdicts = critic_verdicts_for(reviewer)
    v = (getattr(result, "recommendation", "") or "").strip().upper()
    if v not in verdicts:
        raise MissionError(
            f"fail-closed: {reviewer} verdict {v!r} not in {sorted(verdicts)} "
            f"(recommendation must be a typed verdict)")
    return v


def verdict_action(verdict: str, cycles_used: int, max_cycles: int = MAX_REWORK_CYCLES) -> str:
    """Deterministic policy: accept | rework | escalate."""
    if verdict in ACCEPT_VERDICTS:
        return "accept"
    if cycles_used >= max_cycles:
        return "escalate"
    return "rework"


@dataclass(frozen=True)
class ReviewRecord:
    review_id: str
    mission_id: str
    reviewer: str
    reviewer_task_id: str
    target_task_id: str
    verdict: str
    input_hash: str
    action: str  # accept | rework | escalate
    findings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "mission_id": self.mission_id,
            "reviewer": self.reviewer,
            "reviewer_task_id": self.reviewer_task_id,
            "target_task_id": self.target_task_id,
            "verdict": self.verdict,
            "input_hash": self.input_hash,
            "action": self.action,
            "findings": list(self.findings),
        }


@dataclass
class ReworkLedger:
    """Tracks rework cycles per worker task."""

    max_cycles: int = MAX_REWORK_CYCLES
    _cycles: dict = field(default_factory=dict)
    _orders: list[dict] = field(default_factory=list)

    def cycles_used(self, task_id: str) -> int:
        return self._cycles.get(task_id, 0)

    def request(
        self,
        *,
        target_task_id: str,
        findings: tuple[str, ...] | list[str],
        reviewer: str,
        attempt: int,
    ) -> dict:
        """Record one rework order. Raises ReworkExhausted when the budget is spent."""
        used = self._cycles.get(target_task_id, 0)
        if used >= self.max_cycles:
            raise ReworkExhausted(
                f"task {target_task_id!r}: rework budget exhausted "
                f"({used}/{self.max_cycles} cycles) — escalating to ROOT")
        self._cycles[target_task_id] = used + 1
        order = {
            "cycle": used + 1,
            "target_task_id": target_task_id,
            "reviewer": reviewer,
            "findings": tuple(str(f) for f in (findings or ())),
            "attempt": attempt,
        }
        self._orders.append(order)
        return order

    def history(self, task_id: str | None = None) -> tuple[dict, ...]:
        if task_id is None:
            return tuple(self._orders)
        return tuple(o for o in self._orders if o["target_task_id"] == task_id)

    def rework_task(self, original: MissionTask, order: dict) -> MissionTask:
        """The re-run packet for the OWNING specialist (never the reviewer).

        Prerequisites are NOT silently discarded: the rework task re-establishes
        the original's depends_on and adds any proven completions (context_refs)
        so dependency/proof state is preserved.
        """
        n = int(order["cycle"])
        return MissionTask(
            task_id=f"{original.task_id}#rework-{n}",
            mission_id=original.mission_id,
            owner=original.owner,
            role=original.role,
            objective=original.objective,
            depends_on=tuple(original.depends_on),
            context_refs=tuple(original.context_refs),
            output_schema=original.output_schema,
            timeout=original.timeout,
            max_attempts=original.max_attempts,
            required_evidence=tuple(original.required_evidence),
            rework_of=original.task_id,
            rework_cycle=n,
        )

    def critic_rework_task(
        self,
        critic: MissionTask,
        rework_impl_id: str,
        cycle: int,
    ) -> MissionTask:
        """Re-review packet for the same critic role (same reviewer, new id)."""
        return MissionTask(
            task_id=f"{critic.task_id}#rework-{cycle}",
            mission_id=critic.mission_id,
            owner=critic.owner,
            role=critic.role,
            objective=critic.objective,
            depends_on=(rework_impl_id,),
            context_refs=(rework_impl_id,),
            output_schema=critic.output_schema,
            timeout=critic.timeout,
            max_attempts=critic.max_attempts,
            required_evidence=tuple(critic.required_evidence),
        )
