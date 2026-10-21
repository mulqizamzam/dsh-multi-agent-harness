# tests/live_dsh/contract.py — REAL DSH bridge contract (Phase 3 / Session E)
#
# TEST-SUPPORT ONLY. NOT production code.
#
# The observable contract of the DSH `tool-subagent` surface (verified against
# the DSH 0.1.1-rc.2 implementation in this environment):
#
#   packages/subagent/tool-subagent/src/index.ts        — the model-facing tool
#   packages/subagent/subagent/src/types.ts             — SubagentProvider /
#                                                          SubagentRun / SubagentResult
#   packages/subagent/subagent-in-process-driver/src/   — spawn provider driver
#                                                          + structured capture
#
# This module records the CONTRACT the REAL bridge must satisfy so the harness
# can prove, after a Human-approved composition is active, that the actual
# mounted `subagent_<id>` instances behave exactly like the deterministic
# backend the runtime already ships with. Nothing here assumes a live bridge
# exists.

from __future__ import annotations

import os
import sys
import time
import uuid
from dataclasses import dataclass, field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# DSH version pin this harness targets (docs/README.md + provenance module).
DSH_VERSION_PIN = "deepseek-harness-0.1.1-rc.2"

# ---------------------------------------------------------------------------
# Stop-reason vocabulary (mirrors DSH SubagentStopReasonMap in 0.1.1-rc.2)
# ---------------------------------------------------------------------------
STOP_COMPLETED = "completed"
STOP_ABORTED = "aborted"
STOP_ERROR = "error"
STOP_MAX_TOKENS = "max-tokens"
STOP_REFUSAL = "refusal"
STOP_REASONS = (STOP_COMPLETED, STOP_ABORTED, STOP_ERROR,
                STOP_MAX_TOKENS, STOP_REFUSAL)

# Model-facing tool parameters (tool-subagent/src/index.ts:222-265).
# The tool exposes description + prompt + agent_preset; NO provider/type/agent
# parameter is exposed to the model. `agent_preset` names the Agent Preset
# the child is composed from — it replaced the removed `run_in_background`
# argument and the per-instance persona/toolFilter config.
TOOL_PARAMETER_KEYS = ("description", "prompt", "agent_preset")

# Output `kind` vocabulary (tool-subagent/src/index.ts:336-364).
FOREGROUND_KIND = "foreground"
BACKGROUND_KIND = "background"
CONTINUABLE_KIND = "continuable"

# Child-scoped structured-output tool (subagent-in-process-driver/structured.ts).
STRUCTURED_OUTPUT_TOOL = "structured_output"


# ---------------------------------------------------------------------------
# Invocation contract — what the REAL bridge must send to `subagent_<id>`
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DSHInvocation:
    """The exact DSH tool-subagent call the real bridge issues.

    - `description`: short (3-5 word) display label (tool param).
    - `prompt`: the standalone task prompt handed to the child. It must be
      SELF-CONTAINED (the child does NOT see the parent conversation for a
      spawn provider; inheritsParentContext=false — VERIFIED).
    - `agent_preset`: the Agent Preset the child is composed from
      (`role-<id>`) — the model-facing role selector since 0.2.1-rc.2.
    - `output_schema`: the JSON Schema the child must satisfy through the
      `structured_output` tool so the bridge can capture a structured
      TaskResult from `SubagentResult.structured`.
    - `provider` / `max_depth`: composition the mounted delegation row already
      carries; the bridge does NOT re-declare them (they are row config, not
      per-call args).
    """
    description: str
    prompt: str
    agent_preset: str = ""
    output_schema: dict = field(default_factory=dict)

    def to_tool_args(self) -> dict:
        """The args dict as the model-facing tool would receive them."""
        args = {
            "description": self.description,
            "prompt": self.prompt,
        }
        if self.agent_preset:
            args["agent_preset"] = self.agent_preset
        return args

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "prompt": self.prompt,
            "agent_preset": self.agent_preset,
            "output_schema": self.output_schema,
        }


class BuildInvocation:
    """Build the DSH invocation from an authorized task context.

    The prompt is built from the SAME authorized context the existing
    DelegationClient would hand a child (orchestrator/dsh/context.py,
    THREAT-020: no authority in messages). The bridge must pass ONLY data —
    never delegation ids as authority, approval references, or state records.
    """

    @staticmethod
    def description_for(task) -> str:
        role = getattr(task, "assigned_role", "")
        return f"{role}: delegated subtask"

    @staticmethod
    def agent_preset_for(task) -> str:
        """The Agent Preset the child is composed from (`role-<id>`)."""
        role = getattr(task, "assigned_role", "")
        return f"role-{role}" if role else ""

    @staticmethod
    def prompt_for(task, delegation) -> str:
        from orchestrator.dsh.context import build_task_context
        ctx = build_task_context(task=task, delegation=delegation)
        # Deterministic, self-contained prompt from the authorized context.
        lines = [
            f"Task: {ctx.get('objective', '')}",
            f"Role: {ctx.get('assigned_role', '')}",
            f"Scope: {', '.join(ctx.get('scope') or ())}",
            f"Expected output: {ctx.get('expected_output', '') or 'n/a'}",
            "Return your final answer through the structured_output tool "
            "with arguments matching the provided schema exactly.",
        ]
        return "\n".join(lines)

    @classmethod
    def build(cls, task, delegation,
              output_schema: dict | None = None) -> DSHInvocation:
        """Build the invocation for one delegated subtask."""
        if output_schema is None:
            output_schema = cls.default_task_result_schema()
        return DSHInvocation(
            description=cls.description_for(task),
            prompt=cls.prompt_for(task, delegation),
            agent_preset=cls.agent_preset_for(task),
            output_schema=output_schema,
        )

    @staticmethod
    def default_task_result_schema() -> dict:
        """The TaskResult JSON Schema the child must satisfy to produce a
        structured TaskResult (schemas/task-result.schema.json shape)."""
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["task_id", "assigned_role", "status",
                         "confidence", "reported_at"],
            "properties": {
                "task_id": {"type": "string", "minLength": 1},
                "assigned_role": {"enum": [
                    "zeko", "cto", "cfo", "kai", "somad", "badsector", "nova"]},
                "status": {"enum": ["SUCCEEDED", "FAILED", "BLOCKED"]},
                "findings": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string"},
                "confidence": {"enum": ["LOW", "MEDIUM", "HIGH"]},
                "unresolved_items": {"type": "array", "items": {"type": "string"}},
                "actions_taken": {"type": "array", "items": {"type": "string"}},
                "reported_at": {"type": "string", "format": "date-time"},
            },
        }


# ---------------------------------------------------------------------------
# Stop-reason → outcome mapping (the bridge's failure contract)
# ---------------------------------------------------------------------------
# VERIFIED from tool-subagent/src/index.ts stopReasonError():
#   completed  → success (undefined error)
#   aborted    → 'subagent run was cancelled'
#   error      → 'subagent run failed'
#   max-tokens → 'subagent run hit its token limit before finishing'
#   refusal    → 'subagent declined the task'
#   unknown    → 'subagent run ended abnormally' (fail-closed: never partial
#                output reported as success)
STOP_REASON_MESSAGES = {
    STOP_ABORTED: "subagent run was cancelled",
    STOP_ERROR: "subagent run failed",
    STOP_MAX_TOKENS: "subagent run hit its token limit before finishing",
    STOP_REFUSAL: "subagent declined the task",
}


def map_stop_reason_to_outcome(stop_reason: str) -> dict:
    """Map a DSH stop reason to the adapter's delegation outcome.

    Returns a dict with `stop_reason`, `succeeded`, and `error` (None when the
    reason is `completed`). Unknown reasons fail closed (never success).
    """
    stop_reason = stop_reason or STOP_ERROR
    if stop_reason == STOP_COMPLETED:
        return {"stop_reason": STOP_COMPLETED, "succeeded": True, "error": None}
    if stop_reason in STOP_REASON_MESSAGES:
        return {"stop_reason": stop_reason, "succeeded": False,
                "error": STOP_REASON_MESSAGES[stop_reason]}
    return {"stop_reason": stop_reason, "succeeded": False,
            "error": f"subagent run ended abnormally ({stop_reason})"}


def map_stop_reason_to_failure(stop_reason: str) -> tuple[str, str]:
    """Map a DSH stop reason to (failure_class, reason) for the runtime's
    recovery handoff (orchestrator.runtime.collection.classify_adapter_failure
    semantics: environment / logic / authorization / unknown)."""
    stop_reason = stop_reason or STOP_ERROR
    if stop_reason == STOP_ABORTED:
        return ("environment", f"child aborted: {STOP_REASON_MESSAGES[STOP_ABORTED]}")
    if stop_reason == STOP_ERROR:
        return ("logic", f"child failure: {STOP_REASON_MESSAGES[STOP_ERROR]}")
    if stop_reason == STOP_MAX_TOKENS:
        return ("environment", f"child exceeded token budget: "
                               f"{STOP_REASON_MESSAGES[STOP_MAX_TOKENS]}")
    if stop_reason == STOP_REFUSAL:
        return ("logic", f"child refused: {STOP_REASON_MESSAGES[STOP_REFUSAL]}")
    return ("unknown", f"unknown stop reason {stop_reason!r} — escalate, never "
                       "guess (Runbook 08)")


__all__ = [
    "DSH_VERSION_PIN", "STOP_REASONS", "STOP_COMPLETED", "STOP_ABORTED",
    "STOP_ERROR", "STOP_MAX_TOKENS", "STOP_REFUSAL", "TOOL_PARAMETER_KEYS",
    "FOREGROUND_KIND", "BACKGROUND_KIND", "CONTINUABLE_KIND",
    "STRUCTURED_OUTPUT_TOOL", "DSHInvocation", "BuildInvocation",
    "STOP_REASON_MESSAGES", "map_stop_reason_to_outcome",
    "map_stop_reason_to_failure",
]
