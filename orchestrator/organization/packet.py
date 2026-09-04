# orchestrator.organization.packet — mission/task packet contract (MVP)
#
# Organization packet extends the EXISTING Task/TaskResult data contracts
# with PRD-required organization fields: mission_id, owner/role,
# depends_on, context_refs, output_schema, timeout, max_attempts,
# required_evidence.  No existing schema or gate is modified; results
# remain validated TaskResult (schemas/task-result.schema.json).
#
# Status vocabulary (PRD): done | blocked | uncertain.
# Mapping to runtime TaskResult status is FAIL-CLOSED:
#   PRD done      -> SUCCEEDED
#   PRD blocked   -> BLOCKED
#   PRD uncertain -> FAILED
# and inversely
#   SUCCEEDED -> done
#   BLOCKED   -> blocked
#   FAILED    -> uncertain  (fail-closed: never promotes to done)
# Invariant: uncertain/FAILED never becomes done/SUCCEEDED.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dataclasses import dataclass, field, asdict

from orchestrator.foundation.contracts import SPECIALIST_ROLES, Task  # noqa: E402

PRD_STATUSES = ("done", "blocked", "uncertain")
EVIDENCE_KINDS = (
    "test",
    "build",
    "artifact",
    "diff",
    "runtime_observation",
    "security_finding",
    "verification_result",
)
REVIEWER_ROLES = ("badsector", "somad")

PRD_TO_RUNTIME = {"done": "SUCCEEDED", "blocked": "BLOCKED", "uncertain": "FAILED"}
RUNTIME_TO_PRD = {"SUCCEEDED": "done", "BLOCKED": "blocked", "FAILED": "uncertain"}


class MissionError(ValueError):
    """Invalid mission/task packet (fail-closed)."""


def runtime_status(prd_status: str) -> str:
    """PRD status -> runtime TaskResult status."""
    try:
        return PRD_TO_RUNTIME[prd_status]
    except KeyError:
        raise MissionError(f"unknown PRD status {prd_status!r}")


def prd_status(runtime: str) -> str:
    """Runtime TaskResult status -> PRD status."""
    try:
        return RUNTIME_TO_PRD[runtime]
    except KeyError:
        raise MissionError(f"unknown runtime status {runtime!r}")


@dataclass(frozen=True)
class MissionTask:
    """One task packet (PRD data contract) mapped onto the existing Task.

    owner/role: single specialist owning the task (peer topology;
                owner == role is enforced).
    depends_on: task ids that must be ACCEPTED before this task runs.
    context_refs: resource patterns / upstream task ids this task may see
                  (role context boundary — nothing else is passed).
    output_schema: expected structured-output shape (Task.expected_output).
    timeout: per-delegation deadline (seconds) — DelegationClient.
    max_attempts: execution attempts budget (1 + rework cycles).
    required_evidence: evidence kinds that MUST be present to accept 'done'.
    rework_of: internal — original task id when this is a rework packet.
    rework_cycle: internal — cycle number for rework packets.
    """

    task_id: str
    mission_id: str
    owner: str
    role: str
    objective: str
    depends_on: tuple[str, ...] = ()
    context_refs: tuple[str, ...] = ()
    output_schema: str = ""
    timeout: float | None = None
    max_attempts: int = 1
    required_evidence: tuple[str, ...] = ()
    rework_of: str = ""
    rework_cycle: int = 0

    def __post_init__(self):
        if not self.task_id or not self.task_id.strip():
            raise MissionError("MissionTask: task_id required")
        if not self.mission_id or not self.mission_id.strip():
            raise MissionError(f"MissionTask {self.task_id}: mission_id required")
        if not self.objective or not self.objective.strip():
            raise MissionError(f"MissionTask {self.task_id}: objective required")
        if self.owner != self.role:
            raise MissionError(
                f"MissionTask {self.task_id}: owner {self.owner!r} != role "
                f"{self.role!r} (single-owner rule)")
        if self.owner not in SPECIALIST_ROLES:
            raise MissionError(
                f"MissionTask {self.task_id}: owner {self.owner!r} is not a "
                f"specialist role {SPECIALIST_ROLES}")
        if self.task_id in self.depends_on:
            raise MissionError(f"MissionTask {self.task_id}: self-dependency")
        if self.timeout is not None and self.timeout <= 0:
            raise MissionError(f"MissionTask {self.task_id}: timeout must be > 0")
        if self.max_attempts < 1:
            raise MissionError(f"MissionTask {self.task_id}: max_attempts >= 1")
        bad = [k for k in self.required_evidence if k not in EVIDENCE_KINDS]
        if bad:
            raise MissionError(
                f"MissionTask {self.task_id}: unknown evidence kinds {bad} "
                f"(must be from {EVIDENCE_KINDS})")
        if bool(self.rework_of) != (self.rework_cycle > 0):
            raise MissionError(
                f"MissionTask {self.task_id}: rework_of/rework_cycle inconsistent")
        if self.rework_cycle < 0:
            raise MissionError(f"MissionTask {self.task_id}: rework_cycle < 0")
        if self.owner in REVIEWER_ROLES and len(self.depends_on) > 1:
            raise MissionError(
                f"MissionTask {self.task_id}: reviewer {self.owner!r} task must "
                f"review exactly one target or be a precheck (0 deps), got "
                f"{len(self.depends_on)} deps")

    def to_task(self) -> Task:
        """Project the packet onto the EXISTING Task contract."""
        return Task(
            task_id=self.task_id,
            objective=self.objective,
            assigned_role=self.owner,
            parent_task=self.mission_id,
            dependencies=tuple(self.depends_on),
            expected_output=self.output_schema,
            scope=tuple(self.context_refs),
        )

    def is_critic(self) -> bool:
        """True for critic gate tasks (review exactly one target)."""
        return self.owner in REVIEWER_ROLES and len(self.depends_on) == 1

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "mission_id": self.mission_id,
            "owner": self.owner,
            "role": self.role,
            "objective": self.objective,
            "depends_on": list(self.depends_on),
            "context_refs": list(self.context_refs),
            "output_schema": self.output_schema,
            "timeout": self.timeout,
            "max_attempts": self.max_attempts,
            "required_evidence": list(self.required_evidence),
            "rework_of": self.rework_of,
            "rework_cycle": self.rework_cycle,
        }


@dataclass(frozen=True)
class MissionPacket:
    """The mission: objective + task decomposition (validated)."""

    mission_id: str
    objective: str
    tasks: tuple[MissionTask, ...]
    context_refs: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    proven_completed: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.mission_id or not self.mission_id.strip():
            raise MissionError("MissionPacket: mission_id required")
        if not self.objective or not self.objective.strip():
            raise MissionError("MissionPacket: objective required")
        if not self.tasks:
            raise MissionError("MissionPacket: at least one task required")
        ids = [t.task_id for t in self.tasks]
        if len(ids) != len(set(ids)):
            raise MissionError("MissionPacket: duplicate task ids")
        for t in self.tasks:
            if t.mission_id != self.mission_id:
                raise MissionError(
                    f"MissionPacket: task {t.task_id} belongs to mission "
                    f"{t.mission_id!r}, not {self.mission_id!r}")
        known = set(ids)
        proven = set(self.proven_completed or ())
        # External dependencies are allowed ONLY when explicitly proven completed.
        # Unknown/unproven external deps must fail closed here as well (reconciled
        # with plan_waves semantics). Internal DAG validation is preserved.
        for t in self.tasks:
            unknown = set(t.depends_on) - known - proven
            if unknown:
                raise MissionError(
                    f"MissionPacket: task {t.task_id} depends on unknown/unproven "
                    f"tasks {sorted(unknown)} (external deps require proven completion)")
        # CFO gate: only when explicitly useful — include_cfo not needed;
        # enforce per-task: cfo tasks must be justified by mission objective
        # containing finance signals or explicit context_refs; for MVP: allow
        # cfo tasks always but note discipline in docs.
        # Acyclicity via the wave planner (fail-closed).
        from .waves import plan_waves as _plan_waves  # noqa: WPS433

        try:
            _plan_waves(tuple(t.task_id for t in self.tasks),
                        {t.task_id: tuple(t.depends_on) for t in self.tasks},
                        completed=proven)
        except ValueError as e:
            raise MissionError(str(e)) from e

    def by_id(self, task_id: str) -> MissionTask:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        raise MissionError(f"unknown task {task_id!r}")

    def reviewers_of(self, task_id: str) -> tuple[MissionTask, ...]:
        """Critic tasks whose depends_on includes task_id."""
        return tuple(t for t in self.tasks
                     if task_id in t.depends_on and t.owner in REVIEWER_ROLES)

    def to_dict(self) -> dict:
        d = {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "context_refs": list(self.context_refs),
            "constraints": list(self.constraints),
            "tasks": [t.to_dict() for t in self.tasks],
        }
        if self.proven_completed:
            d["proven_completed"] = list(self.proven_completed)
        return d
