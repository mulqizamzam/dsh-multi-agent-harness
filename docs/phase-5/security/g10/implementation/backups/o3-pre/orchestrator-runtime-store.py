# orchestrator.runtime.store — Project state persistence + version guard (Phase 3)
#
# The runtime persists the authoritative project state document
# (`state/projects/<project>.json`) through the project execution gate
# (control.execution_gate.write_through — ADR 0002 writer discipline; a
# raw-DSH-tool write never lands here).
#
# Version semantics (THREAT-021/022):
#   - every persist is a compare-and-swap against the caller's expected
#     version; a stale writer is refused before any mutation
#   - `check_current` re-reads the on-disk version before a consequential
#     action, so a parallel writer that bumped the version stops the flow
#     (StaleStateDetected -> fail-closed)
#
# The project state is DATA, never authority (AUTH-INV-07/08); `approved`-like
# fields are records only.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.state import ProjectState, StateMachine  # noqa: E402
from state.helpers.atomic_write import safe_read  # noqa: E402
from state.helpers.version_check import read_version  # noqa: E402

from .exceptions import StaleStateDetected  # noqa: E402


# ---------------------------------------------------------------------------
# Project state codec
# ---------------------------------------------------------------------------

def encode_project_state(ps: ProjectState) -> dict:
    """Serialize a ProjectState to a JSON-able document (versioned)."""
    return {
        "project": ps.project,
        "version": ps.version,
        "current_state": ps.current_state,
        "task_machines": {
            tid: m.to_dict() for tid, m in ps.task_machines.items()
        },
        "active_delegations": list(ps.active_delegations),
        "approvals": list(ps.approvals),
    }


def decode_project_state(data: dict) -> ProjectState:
    """Rehydrate a ProjectState from a versioned document (fail-closed on a
    malformed document: treated as a fresh state, version 1)."""
    ps = ProjectState(project=data.get("project", "multi-agent-harness"))
    ps.version = data.get("version", 1)
    ps.current_state = data.get("current_state", "DRAFT")
    ps.active_delegations = list(data.get("active_delegations", []))
    ps.approvals = list(data.get("approvals", []))
    machines = data.get("task_machines", {}) or {}
    for tid, md in machines.items():
        sm = StateMachine(tid, initial=md.get("state", "DRAFT"))
        sm.version = md.get("version", 1)
        sm.history = list(md.get("history", []))
        ps.task_machines[tid] = sm
    return ps


# ---------------------------------------------------------------------------
# RuntimeStore
# ---------------------------------------------------------------------------

class RuntimeStore:
    """Persist the project state through the project execution gate.

    Parameters
    ----------
    base:
        Workspace base (state document lives under ``state/projects/``).
    project:
        Project id (default "multi-agent-harness").
    """

    def __init__(self, base=None, project: str = "multi-agent-harness"):
        from control.execution_gate import workspace_base
        self.base = base or workspace_base()
        self.project = project
        self.state_rel = f"state/projects/{project}.json"

    # -- paths --------------------------------------------------------------

    def state_path(self) -> str:
        return os.path.join(self.base, *self.state_rel.split("/"))

    def ensure_dirs(self) -> None:
        os.makedirs(os.path.dirname(self.state_path()), exist_ok=True)
        os.makedirs(os.path.join(self.base, "state", "registry"), exist_ok=True)
        os.makedirs(os.path.join(self.base, "audit"), exist_ok=True)

    # -- read ---------------------------------------------------------------

    def ensure_state(self) -> ProjectState:
        """Bootstrap the project state document if absent: writes a fresh
        ProjectState at version 1 through the execution gate. Returns the
        current ProjectState (loaded or freshly bootstrapped)."""
        if not os.path.exists(self.state_path()):
            from control.execution_gate import write_through
            ps = ProjectState(project=self.project)
            write_through("write", self.state_rel,
                          encode_project_state(ps), base=self.base)
            return ps
        return self.load_project_state()

    def load_project_state(self) -> ProjectState:
        """Read the persisted project state; a missing/corrupt document is a
        FRESH state at version 1 (fail-closed: never partial data)."""
        data = safe_read(self.state_path())
        if not isinstance(data, dict):
            return ProjectState(project=self.project)
        ps = decode_project_state(data)
        ps.project = self.project
        return ps

    def current_version(self) -> int:
        return read_version(self.state_path())

    # -- write (CAS through the execution gate) -----------------------------

    def persist(self, ps: ProjectState, expected_version: int) -> int:
        """Persist `ps` iff the on-disk version == `expected_version`.

        Raises StaleStateDetected on mismatch (THREAT-021 lost update). The
        write goes through the project execution gate (ADR 0002 writer
        discipline), never a raw DSH tool.
        """
        from control.execution_gate import write_through
        current = read_version(self.state_path())
        if current != expected_version:
            raise StaleStateDetected(
                f"state {self.state_rel}: on-disk version {current} != "
                f"expected {expected_version} (THREAT-021 lost update)")
        doc = encode_project_state(ps)
        write_through("write", self.state_rel, doc, base=self.base)
        return doc["version"]

    def check_current(self, expected_version: int) -> int:
        """Re-read the on-disk version before a consequential action.

        Raises StaleStateDetected when the on-disk version no longer matches
        the caller's held version (THREAT-022 stale state)."""
        current = read_version(self.state_path())
        if current != expected_version:
            raise StaleStateDetected(
                f"state {self.state_rel}: held version {expected_version} != "
                f"on-disk {current} — re-read current state and re-validate "
                f"authority (THREAT-022)")
        return current


__all__ = ["RuntimeStore", "encode_project_state", "decode_project_state"]
