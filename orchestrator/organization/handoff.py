# orchestrator.organization.handoff — typed task/result handoff (MVP)
#
# Typed handoff uses the EXISTING Task/TaskResult data contracts and the
# EXISTING outputSchema/toolFilter machinery.  This module adds NO new
# wire format: TypedHandoff is a deterministic VIEW over a Task/TaskResult
# pair that carries the PRD vocabulary (done|blocked|uncertain) via the
# fail-closed mapping in packet.py.
#
# Evidence artifacts are carried as "kind:ref" strings in TaskResult.evidence
# (e.g. "test:pytest-log", "build:ci-123").  The evidence gate in
# evidence.py validates required_evidence against these typed strings.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from orchestrator.foundation.contracts import TaskResult, Task  # noqa: E402
from .packet import prd_status, runtime_status, MissionTask, MissionError  # noqa: E402

# Typed result statuses (PRD vocabulary).
HANDO_PRD_STATUSES = ("done", "blocked", "uncertain")


@dataclass(frozen=True)
class TypedHandoff:
    """Typed view over a Task + TaskResult.

    Encodes the full PRD result contract:
        status | summary | findings | evidence | artifacts |
        changed_files | risks | unknowns | next
    plus ownership and mission linkage.
    """

    mission_id: str
    task_id: str
    owner: str
    role: str
    status: str  # done | blocked | uncertain (PRD)
    summary: str
    findings: tuple[str, ...]
    evidence: tuple[str, ...]
    artifacts: tuple[str, ...]
    changed_files: tuple[str, ...]
    risks: tuple[str, ...]
    unknowns: tuple[str, ...]
    next: tuple[str, ...]
    attempt: int = 1
    produced_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if self.status not in HANDO_PRD_STATUSES:
            raise MissionError(
                f"TypedHandoff {self.task_id}: invalid PRD status {self.status!r} "
                f"(must be one of {HANDO_PRD_STATUSES})")

    def to_dict(self) -> dict:
        d = asdict(self)
        # keep JSON-serialisable: tuples -> lists
        for k in ("findings", "evidence", "artifacts", "changed_files",
                  "risks", "unknowns", "next"):
            d[k] = list(d[k])
        return d

    @classmethod
    def from_task_result(
        cls,
        task: MissionTask,
        result: TaskResult,
        *,
        attempt: int = 1,
    ) -> "TypedHandoff":
        """Deterministic projection Task + TaskResult -> TypedHandoff."""
        try:
            status = prd_status(result.status)
        except MissionError:
            status = "uncertain"
        # PRD summary = recommendation if present, else first finding.
        summary = (result.recommendation or "").strip()
        if not summary and result.findings:
            summary = str(result.findings[0])[:500]
        findings = tuple(str(f) for f in (result.findings or ()))
        evidence = tuple(str(e) for e in (result.evidence or ()))
        artifacts = tuple(str(a) for a in (result.actions_taken or ()))
        # Derive changed_files from evidence/artifact kinds.
        changed: set[str] = set()
        for e in evidence + artifacts:
            if ":" in e:
                k, ref = e.split(":", 1)
                if k in ("diff", "artifact", "file", "changed_file"):
                    changed.add(ref.strip())
        changed_files = tuple(sorted(c for c in changed if c))
        risks = tuple(str(r) for r in (result.risks or ()))
        unknowns = tuple(str(u) for u in (result.unresolved_items or ()))
        nxt: tuple[str, ...] = ()
        if result.recommendation and status != "uncertain":
            nxt = (str(result.recommendation).strip(),) if str(result.recommendation).strip() else ()
        return cls(
            mission_id=task.mission_id,
            task_id=task.task_id,
            owner=task.owner,
            role=task.role,
            status=status,
            summary=summary or status,
            findings=findings,
            evidence=evidence,
            artifacts=artifacts,
            changed_files=changed_files,
            risks=risks,
            unknowns=unknowns,
            next=nxt,
            attempt=attempt,
        )


def build_task_context(
    task: MissionTask,
    upstream: dict[str, TypedHandoff],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the role-scoped context for a task (context boundary).

    Only the task's own packet plus the declared context_refs/depends_on
    are passed.  No conversation history, no unrelated upstream data, and
    no authority-bearing keys.

    upstream: map task_id -> TypedHandoff of completed tasks.
    extra: optional typed rework findings (e.g. {"rework_cycle": n, ...})
           appended without introducing an auth-like key.
    """
    # Materialize only the declared refs plus direct dependencies.
    declared = set(task.context_refs) | set(task.depends_on)
    upstream_slice: dict[str, Any] = {}
    for ref in declared:
        ho = upstream.get(ref)
        if ho is not None:
            upstream_slice[ref] = {
                "status": ho.status,
                "summary": ho.summary,
                "findings": list(ho.findings),
                "evidence": list(ho.evidence),
            }
    ctx: dict[str, Any] = {
        "mission_id": task.mission_id,
        "task_id": task.task_id,
        "objective": task.objective,
        "output_schema": task.output_schema,
        "context_refs": list(task.context_refs),
        "depends_on": list(task.depends_on),
        "upstream": upstream_slice,
    }
    if extra:
        # Guard against smuggling auth-bearing keys into the slice.
        banned_substr = ("delegation", "approval", "grant", "authority",
                         "permission", "token", "secret", "credential")
        for k in extra:
            low = k.lower()
            if any(b in low for b in banned_substr):
                raise MissionError(
                    f"build_task_context: extra key {k!r} looks like an "
                    f"authority-bearing key (boundary violation)")
        for k, v in extra.items():
            ctx[f"extra_{k}"] = v
    return ctx
