# orchestrator.dsh.provenance — delegation provenance record
#
# Phase 3 / Session B. Scope: multi-agent-harness/ only.
#
# Every delegation through the adapter carries a provenance record that
# preserves:
#   - ROLE IDENTITY   — the resolved role and its subagent instance/toolName
#   - RUNTIME PROVENANCE — the delegation id, task id, orchestrator session,
#     adapter version, timestamps, and the child run id
#
# Provenance is DATA (never authority).  It is used by the orchestrator to
# audit, correlate, and recover; it never grants a capability (AUTH-INV-13/14).

from __future__ import annotations

import os
import sys
import time
import uuid
from dataclasses import dataclass, field as dc_field, asdict

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from .backend import DelegationResult  # noqa: E402

# Version pin of the DSH engine the adapter targets (docs/README.md)
DSH_VERSION_PIN = "deepseek-harness-0.1.1-rc.2"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _session_id() -> str:
    """Runtime provenance: the orchestrator's root session identity."""
    return os.environ.get("DSH_SESSION_ID") or "orchestrator-root"


@dataclass(frozen=True)
class DelegationProvenance:
    """Immutable provenance stamp attached to every delegated result.

    Fields are read-only facts recorded by the adapter, never written by the
    child or by model text.
    """
    delegation_id: str
    task_id: str
    role: str
    tool_name: str          # subagent_<id>
    persona: str            # role-<id>
    instance_max_depth: int = 1
    background_mode: str = "continuable"
    provider: str = "spawn"
    actor: str = "orchestrator"
    session_id: str = "orchestrator-root"
    adapter_version: str = "dsh-integration-adapter-1.0"
    dsh_version_pin: str = DSH_VERSION_PIN
    run_id: str = ""
    started_at: str = ""
    settled_at: str = ""
    stop_reason: str = "completed"
    result_status: str = ""

    @classmethod
    def build(cls, *, delegation, task, instance, run=None,
              started_at: str = "", settled_at: str = "",
              result: DelegationResult | None = None,
              result_status: str = "") -> "DelegationProvenance":
        """Construct a provenance stamp from the delegation attempt's inputs
        and (optionally) its settled outcome."""
        return cls(
            delegation_id=getattr(delegation, "id", ""),
            task_id=getattr(task, "task_id", ""),
            role=getattr(task, "assigned_role", ""),
            tool_name=instance.tool_name,
            persona=instance.persona,
            instance_max_depth=instance.max_depth,
            background_mode=instance.background_mode,
            provider=instance.provider,
            session_id=_session_id(),
            run_id=getattr(run, "run_id", "") or "",
            started_at=started_at or _now_iso(),
            settled_at=settled_at or _now_iso(),
            stop_reason=result.stop_reason if result else "completed",
            result_status=result_status,
        )

    def to_dict(self) -> dict:
        return asdict(self)