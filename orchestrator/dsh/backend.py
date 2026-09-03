# orchestrator.dsh.backend — DSH delegation backend abstraction
#
# Phase 3 / Session B. Scope: multi-agent-harness/ only.
#
# The adapter's seam to the DSH `tool-subagent` primitive family.  In
# production, the orchestrator root session holds the mounted `subagent_<id>`
# tool instances (D4/D7 controlled composition exception); this module models
# the observable contract of that tool surface — start a child with a prompt +
# optional outputSchema, receive a settled result with a DSH stop reason,
# cancel via signal, dispose when done — so the orchestrator runtime can drive
# it without depending on DSH internals.
#
# The stop-reason vocabulary mirrors DSH 0.1.1-rc.2 (`SubagentStopReasonMap`):
#   completed | aborted | error | max-tokens | refusal
#
# This module does NOT mount, register, or configure any DSH tool.  It only
# defines the interface the orchestrator consumes and a deterministic
# in-process fake backend for tests.

from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field
from typing import Any

from .exceptions import (
    ChildFailure,
    DelegationAborted,
    DelegationTimeout,
    DSHError,
)

# DSH stop reasons (mirrors SubagentStopReasonMap in dsh 0.1.1-rc.2)
STOP_COMPLETED = "completed"
STOP_ABORTED = "aborted"
STOP_ERROR = "error"
STOP_MAX_TOKENS = "max-tokens"
STOP_REFUSAL = "refusal"
KNOWN_STOP_REASONS = (STOP_COMPLETED, STOP_ABORTED, STOP_ERROR,
                      STOP_MAX_TOKENS, STOP_REFUSAL)


# ---------------------------------------------------------------------------
# Result / run contracts
# ---------------------------------------------------------------------------
@dataclass
class DelegationResult:
    """A settled delegation outcome at the backend seam.

    Mirrors DSH's SubagentResult: output (final assistant text), structured
    (validated against the requested outputSchema when the child satisfies
    it), stop_reason (DSH vocabulary), diagnostic (provider-authored failure
    detail for non-completed results).
    """
    output: str = ""
    structured: dict | None = None
    stop_reason: str = STOP_COMPLETED
    diagnostic: str = ""

    def __post_init__(self):
        if self.stop_reason not in KNOWN_STOP_REASONS:
            self.stop_reason = STOP_ERROR  # unknown reason → fail-closed error

    @property
    def succeeded(self) -> bool:
        return self.stop_reason == STOP_COMPLETED


class DelegationRun(ABC):
    """A handle to one delegated child run (mirrors DSH SubagentRun)."""

    run_id: str

    @abstractmethod
    def result(self) -> DelegationResult:
        """Settle the run. Does NOT raise on child-level failures — a
        model/transport failure is returned as stop_reason 'error'.  Raises
        only on infrastructure faults the backend cannot represent as a stop
        reason (e.g. timeout/abort at the harness boundary)."""

    @abstractmethod
    def dispose(self) -> None:
        """Cancel remaining work and release resources. Idempotent."""


class DelegationBackend(ABC):
    """The orchestrator-facing delegation surface.

    `start` spawns a child for the resolved instance with the given prompt;
    `timeout_seconds` bounds the tool call at the backend boundary
    (toolCallTimeoutMs equivalent).
    """

    name = "abstract-backend"

    @abstractmethod
    def start(self, instance, prompt: dict, *,
              signal=None, timeout_seconds: float | None = None) -> DelegationRun:
        ...

    @abstractmethod
    def interrupt(self, run_id: str, signal) -> None:
        """Request cancellation of a running child (fire-and-return)."""

    @abstractmethod
    def list_children(self, parent_session_id: str) -> list[dict]:
        """Enumerate the parent's direct children (durable discovery)."""


# ---------------------------------------------------------------------------
# In-process fake backend (test + dry-run support)
# ---------------------------------------------------------------------------
class FakeSubagentBackend(DelegationBackend):
    """Deterministic in-process backend that emulates the D4/D7-mounted
    `tool-subagent` surface for tests and DRY_RUN orchestrator flows.

    Each role instance is scripted with a handler that maps the prompt to a
    DelegationResult.  Handlers may:
      - raise DelegationTimeout   (child overruns its tool-call budget)
      - raise DelegationAborted   (child was cancelled mid-run)
      - raise ChildFailure        (child failed / refused)
      - return a DelegationResult with stop_reason != completed
      - return a valid structured result

    This backend NEVER mounts or configures DSH; it is an in-process model of
    the tool contract the orchestrator consumes.
    """

    name = "fake-subagent-backend"

    def __init__(self):
        self._handlers: dict[str, callable] = {}
        self._children: dict[str, dict] = {}
        self._start_calls: list[dict] = []
        self._lock = threading.Lock()

    # -- scripting -----------------------------------------------------------

    def register(self, tool_name: str, handler: callable) -> "FakeSubagentBackend":
        """Register a handler for a tool_name (e.g. 'subagent_cto').

        handler(instance, prompt) -> DelegationResult  (or raises).
        """
        with self._lock:
            self._handlers[tool_name] = handler
        return self

    def register_result(self, tool_name: str, structured: dict) -> "FakeSubagentBackend":
        """Script a completed result for a tool_name."""
        return self.register(
            tool_name,
            lambda instance, prompt: DelegationResult(
                output="done", structured=structured))

    def register_timeout(self, tool_name: str, delay: float = 0.05) -> "FakeSubagentBackend":
        """Script a child that overruns its budget (raises DelegationTimeout)."""
        def _handler(instance, prompt):
            time.sleep(delay)
            raise DelegationTimeout(
                f"subagent {instance.tool_name} exceeded its tool-call budget")
        return self.register(tool_name, _handler)

    def register_abort(self, tool_name: str, delay: float = 0.0) -> "FakeSubagentBackend":
        """Script a child that is cancelled mid-run (raises DelegationAborted)."""
        def _handler(instance, prompt):
            if delay:
                time.sleep(delay)
            raise DelegationAborted(
                f"subagent {instance.tool_name} cancelled (stopReason aborted)")
        return self.register(tool_name, _handler)

    def register_failure(self, tool_name: str, reason: str = "model failure",
                         stop_reason: str = STOP_ERROR,
                         diagnostic: str = "") -> "FakeSubagentBackend":
        """Script a child that fails (stop_reason error/refusal/max-tokens)."""
        def _handler(instance, prompt):
            return DelegationResult(
                output="partial", structured=None,
                stop_reason=stop_reason,
                diagnostic=diagnostic or f"{instance.tool_name}: {reason}")
        return self.register(tool_name, _handler)

    # -- observation ---------------------------------------------------------

    def start_calls(self) -> list[dict]:
        """Records of every start() call: {tool_name, prompt, started_at}."""
        with self._lock:
            return list(self._start_calls)

    def children(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._children)

    # -- DelegationBackend ---------------------------------------------------

    def start(self, instance, prompt: dict, *,
              signal=None, timeout_seconds: float | None = None) -> DelegationRun:
        tool_name = instance.tool_name
        run_id = f"fake-{uuid.uuid4().hex[:12]}"
        with self._lock:
            handler = self._handlers.get(tool_name)
            self._start_calls.append({
                "tool_name": tool_name,
                "role": instance.role,
                "prompt": prompt,
                "run_id": run_id,
            })
            self._children[run_id] = {
                "tool_name": tool_name,
                "role": instance.role,
                "status": "running",
            }
        if handler is None:
            # default: a completed result echoing the prompt task_id
            handler = _default_handler
        return _FakeRun(self, run_id, tool_name, handler, instance,
                        prompt, signal, timeout_seconds)

    def interrupt(self, run_id: str, signal) -> None:
        with self._lock:
            child = self._children.get(run_id)
            if child is not None:
                child["status"] = "interrupt-requested"
        if signal is not None:
            signal.set()

    def list_children(self, parent_session_id: str) -> list[dict]:
        with self._lock:
            return [dict(c, parent=parent_session_id) for c in self._children.values()]


def _default_handler(instance, prompt):
    """Default fake handler: echo a minimal completed result."""
    return DelegationResult(
        output="ok",
        structured={
            "task_id": prompt.get("task_id", ""),
            "assigned_role": instance.role,
            "status": "SUCCEEDED",
            "confidence": "MEDIUM",
            "findings": [f"{instance.role} completed the delegated task"],
            "reported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })


class _FakeRun(DelegationRun):
    """One scripted fake run. result() executes the registered handler."""

    def __init__(self, backend, run_id, tool_name, handler, instance,
                 prompt, signal, timeout_seconds):
        self._backend = backend
        self._run_id = run_id
        self._tool_name = tool_name
        self._handler = handler
        self._instance = instance
        self._prompt = prompt
        self._signal = signal
        self._timeout_seconds = timeout_seconds
        self._disposed = False

    @property
    def run_id(self) -> str:
        return self._run_id

    def result(self) -> DelegationResult:
        # Harness-boundary abort: signal fired before the run produced a result
        if self._signal is not None and self._signal.is_set():
            self._settle("aborted")
            raise DelegationAborted(
                f"subagent {self._tool_name} aborted before result (signal set)")

        started = time.monotonic()
        try:
            res = self._handler(self._instance, self._prompt)
        except DelegationTimeout as e:
            self._settle("timeout")
            raise e
        except DelegationAborted as e:
            self._settle("aborted")
            raise e
        except ChildFailure as e:
            self._settle("failed")
            raise e
        except Exception as e:  # handler bug → infrastructure fault
            self._settle("failed")
            raise ChildFailure(
                f"fake backend handler raised {type(e).__name__}",
                diagnostic=str(e)) from e

        # tool-call budget enforcement at the backend boundary
        if self._timeout_seconds is not None:
            elapsed = time.monotonic() - started
            if elapsed > self._timeout_seconds:
                self._settle("timeout")
                raise DelegationTimeout(
                    f"subagent {self._tool_name} exceeded "
                    f"{self._timeout_seconds}s tool-call budget")

        self._settle("completed")
        return res

    def dispose(self) -> None:
        self._disposed = True
        self._settle("disposed")

    def _settle(self, status: str) -> None:
        with self._backend._lock:
            child = self._backend._children.get(self._run_id)
            if child is not None:
                child["status"] = status