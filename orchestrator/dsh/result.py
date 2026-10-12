# orchestrator.dsh.result — structured TaskResult collection + validation
#
# Phase 3 / Session B. Scope: multi-agent-harness/ only.
#
# Collects a child's structured output into a validated
# `orchestrator.foundation.contracts.TaskResult`.  The child's output is DATA:
#   - the status/recommendation fields are CLAIMS the orchestrator later
#     verifies; collecting them never grants authority (AUTH-INV-13)
#   - a malformed result (missing fields, bad enum, wrong role, unknown keys)
#     is REJECTED (MalformedResult), never coerced — fail-closed
#   - ROLE IDENTITY is preserved: the collected result's assigned_role MUST
#     equal the role that was delegated to
#
# The collector validates against schemas/task-result.schema.json (draft
# 2020-12) when jsonschema is available, and against the TaskResult contract in
# all cases.

from __future__ import annotations

import json
import os
import sys
import time

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import TaskResult  # noqa: E402
from .exceptions import MalformedResult  # noqa: E402

_SCHEMA_REL = ("schemas", "task-result.schema.json")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class TaskResultCollector:
    """Validates a child's structured output into a TaskResult."""

    def __init__(self, *, require_schema: bool = True):
        self._require_schema = require_schema
        self._schema = None
        if require_schema:
            self._schema = self._load_schema()

    def _load_schema(self):
        path = os.path.join(_PROJECT_ROOT, *_SCHEMA_REL)
        if not os.path.isfile(path):
            if self._require_schema:
                raise MalformedResult(f"schema file not found: {path}")
            return None
        with open(path, "r") as f:
            return json.load(f)

    def collect(self, structured, *, task) -> TaskResult:
        """Convert `structured` (dict or JSON string) into a validated
        TaskResult for `task`.

        Raises MalformedResult on any invalid / unexpected shape, on a
        role-identity or task-id mismatch, or on schema non-conformance.
        """
        data = self._normalize(structured)
        if data is None:
            raise MalformedResult("child produced no structured result")

        if not isinstance(data, dict):
            raise MalformedResult(
                f"structured result must be an object, got {type(data).__name__}")

        # Field-level contract validation (always)
        task_id = data.get("task_id")
        assigned_role = data.get("assigned_role")
        status = data.get("status")
        confidence = data.get("confidence", "MEDIUM")
        reported_at = data.get("reported_at")

        if not isinstance(task_id, str) or not task_id:
            raise MalformedResult("structured result: missing/invalid task_id")
        if not isinstance(assigned_role, str) or not assigned_role:
            raise MalformedResult("structured result: missing/invalid assigned_role")
        # PRD v0.2 §13 vocabulary: SUCCEEDED plus every failing status. The
        # accepted set is DERIVED from the canonical collection.FAILING_STATUSES
        # (which equals the schema enum minus SUCCEEDED) so this whitelist cannot
        # drift from schemas/task-result.schema.json or the TaskResult contract,
        # both of which accept all six. Imported LAZILY: a top-level
        # `orchestrator.runtime.collection` import here is a circular import
        # (orchestrator.dsh -> orchestrator.runtime.__init__ -> flow ->
        # `from orchestrator.dsh import RealDSHBackend`, which is still bound
        # AFTER this module in dsh/__init__.py).
        from orchestrator.runtime.collection import FAILING_STATUSES
        _accepted_statuses = ("SUCCEEDED",) + tuple(FAILING_STATUSES)
        if status != "SUCCEEDED" and status not in FAILING_STATUSES:
            raise MalformedResult(
                f"structured result: invalid status {status!r} "
                f"({'/'.join(_accepted_statuses)})")
        if confidence not in ("LOW", "MEDIUM", "HIGH"):
            raise MalformedResult(
                f"structured result: invalid confidence {confidence!r}")

        # ROLE IDENTITY: the collected result must match the delegated role
        expected_role = getattr(task, "assigned_role", "")
        if assigned_role != expected_role:
            raise MalformedResult(
                f"role identity mismatch: child reported role {assigned_role!r} "
                f"but was delegated role {expected_role!r}")
        if task_id != getattr(task, "task_id", ""):
            raise MalformedResult(
                f"task id mismatch: child reported {task_id!r} but task is "
                f"{getattr(task, 'task_id', '')!r}")

        # JSON-Schema validation (when schema is available)
        if self._schema is not None:
            self._validate_schema(data)

        # Contract construction (also validates types)
        kwargs = {
            "task_id": task_id,
            "assigned_role": assigned_role,
            "status": status,
            "confidence": confidence,
            "reported_at": reported_at or _now_iso(),
        }
        for seq in ("findings", "evidence", "assumptions", "risks",
                    "unresolved_items", "actions_taken"):
            v = data.get(seq, ())
            if v is None:
                v = ()
            if isinstance(v, list):
                kwargs[seq] = tuple(str(x) for x in v)
            elif isinstance(v, tuple):
                kwargs[seq] = v
            else:
                raise MalformedResult(f"structured result: {seq} must be a list")
        for scalar in ("recommendation",):
            kwargs[scalar] = data.get(scalar, "") or ""

        try:
            return TaskResult(**kwargs)
        except Exception as e:
            raise MalformedResult(f"structured result failed contract: {e}") from e

    def _normalize(self, structured):
        if structured is None:
            return None
        if isinstance(structured, dict):
            return structured
        if isinstance(structured, str):
            try:
                return json.loads(structured)
            except json.JSONDecodeError:
                raise MalformedResult("structured result is not valid JSON") from None
        if hasattr(structured, "to_dict"):
            return structured.to_dict()
        raise MalformedResult(
            f"structured result has unsupported type {type(structured).__name__}")

    def _validate_schema(self, data: dict) -> None:
        try:
            import jsonschema
        except ImportError:
            return  # schema validation best-effort
        try:
            jsonschema.Draft202012Validator(self._schema).validate(data)
        except jsonschema.ValidationError as e:
            raise MalformedResult(f"structured result fails schema: {e.message}") from e


__all__ = ["TaskResultCollector"]