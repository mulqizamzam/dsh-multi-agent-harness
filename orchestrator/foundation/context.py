# orchestrator.foundation.context — Context boundaries (Phase 1D)
#
# Explicit GLOBAL / PROJECT / TASK / AGENT context boundaries. Each boundary
# declares what may live there and the visibility/authority rule. Context is
# DATA: no boundary field is ever authority on its own (AUTH-INV-07/13).

from __future__ import annotations

from dataclasses import dataclass, field, asdict

# Boundary visibility: which scopes may READ which other scopes' data.
#   GLOBAL   harness/session facts (DSH version, workspace root, session id)
#   PROJECT  project-wide state (registry, decisions, risks, approvals)
#   TASK     per-task state (objective, decomposition, results)
#   AGENT    per-agent working context (assigned tasks, capabilities)
VISIBILITY = {
    "GLOBAL": ("GLOBAL", "PROJECT", "TASK", "AGENT"),
    "PROJECT": ("PROJECT", "TASK"),
    "TASK": ("TASK",),
    "AGENT": ("AGENT", "TASK"),
}


@dataclass
class Context:
    """Typed context boundary. `kind` is one of GLOBAL/PROJECT/TASK/AGENT.
    `owner` identifies the owning agent (AGENT) or task (TASK)."""

    kind: str
    owner: str = ""
    data: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in VISIBILITY:
            raise ValueError(f"invalid context kind {self.kind!r}")
        if self.kind in ("TASK", "AGENT") and not self.owner:
            raise ValueError(f"{self.kind} context requires an owner")

    def can_read(self, other: "Context") -> bool:
        return other.kind in VISIBILITY[self.kind]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def to_dict(self):
        return {"kind": self.kind, "owner": self.owner, "data": asdict(self.data) if isinstance(self.data, dict) else self.data}
