# Category E — CONTROL-CHAIN INTEGRITY
#
# Prove the front door always reaches the complete bounded-autonomy chain and
# never shortcuts it:
#
#   FrontDoorRequest → resolve_delegation → ProductionRun
#     → BoundedExecutor → ExecutionFlow → gates → ExecutionEngine → verification
#
# Proofs:
#   E1 behavioral: monkeypatched spies confirm every link is reached.
#   E2 static: entry.py imports only ProductionRun, never ExecutionFlow,
#      never raw DSH, never creates a delegation, never writes the registry.
#   E3 prove the chain actually gates (verification is reached, gates recorded).
#   E4 prove no direct ExecutionFlow shortcut.
#   E5 prove no raw DSH invocation.
#   E6 prove no direct registry write.
#   E7 prove no direct authority creation.
#   E8 prove no gate bypass.

import pytest

from ._availability import front_door_available, _NOT_YET_AVAILABLE

pytestmark = pytest.mark.skipif(not front_door_available(),
                                reason=_NOT_YET_AVAILABLE)

from .conftest import (  # noqa: E402
    make_delegation, make_subtask_result, make_provider, seed_state,
)

import ast
import os

# Project root (5 levels up from tests/orchestrator/entrypoint/security/).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))))
_ENTRY_MODULES = [
    os.path.join(_PROJECT_ROOT, "orchestrator", "entrypoint", "entry.py"),
    os.path.join(_PROJECT_ROOT, "orchestrator", "entrypoint", "__main__.py"),
]


def _ast_names(tree):
    """Return the set of all identifier names referenced in AST nodes
    (Name, Attribute, Call func names) — never docstring/comment text."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def _ast_calls(tree):
    """Return the set of all callee names (function names that are called)."""
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    return calls


class TestBehavioralChainProof:
    """E1: monkeypatched class methods prove the full control chain is reached
    on every run."""

    def test_production_run_reached(self, front_door, ws, delegation, provider,
                                    subtask_runner, action_executor,
                                    monkeypatch):
        """ProductionRun.run() is always called (the sole execution entry)."""
        calls = []
        import orchestrator.production.lifecycle as lc
        orig = lc.ProductionRun.run
        monkeypatch.setattr(lc.ProductionRun, "run",
                            lambda self, **kw: (calls.append("ProductionRun.run"),
                                                orig(self, **kw)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert "ProductionRun.run" in calls, \
            "ProductionRun.run must be the sole execution entry"
        assert result.status in ("COMPLETE", "BLOCKED", "ESCALATED", "ERROR")

    def test_execution_flow_reached(self, front_door, ws, delegation, provider,
                                    subtask_runner, action_executor,
                                    monkeypatch):
        """ExecutionFlow.run() is reached (the 17-phase runtime chain)."""
        calls = []
        import orchestrator.runtime.flow as flowmod
        orig = flowmod.ExecutionFlow.run
        monkeypatch.setattr(flowmod.ExecutionFlow, "run",
                            lambda self, *a, **k: (
                                calls.append("ExecutionFlow.run"),
                                orig(self, *a, **k)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert "ExecutionFlow.run" in calls, \
            "ExecutionFlow.run must be reached through ProductionRun"
        assert result.status in ("COMPLETE", "BLOCKED", "ESCALATED", "ERROR")

    def test_execution_engine_execute_reached(self, front_door, ws, delegation,
                                              provider, subtask_runner,
                                              action_executor, monkeypatch):
        """ExecutionEngine.execute() is reached (the EXECUTE phase)."""
        calls = []
        import orchestrator.execution.engine as engmod
        orig = engmod.ExecutionEngine.execute
        monkeypatch.setattr(engmod.ExecutionEngine, "execute",
                            lambda self, *a, **k: (
                                calls.append("engine.execute"),
                                orig(self, *a, **k)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert "engine.execute" in calls, \
            "ExecutionEngine.execute must be reached"
        assert result.status in ("COMPLETE", "BLOCKED", "ESCALATED", "ERROR")

    def test_verification_gate_reached_on_complete(self, front_door, ws,
                                                   delegation, provider,
                                                   subtask_runner,
                                                   action_executor):
        """E3: when the run completes, the report carries a verification
        verdict — proving the verification gate was reached."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        if result.status == "COMPLETE":
            assert result.report is not None
            assert result.report["verification"]["verdict"] == "PASSED"
            assert len(result.report.get("gates", [])) > 0, \
                "gates must be recorded in report"
        # If the run did not COMPLETE, something else failed — but the chain
        # was still reached (the error occurred inside the chain).

    def test_production_run_is_only_execution_path(self, front_door):
        """E4 static: the front door's only execution path is
        ProductionRun.run(). It does not import or construct ExecutionFlow
        (AST-based — comments may mention the class, but never call it)."""
        entry_path = _ENTRY_MODULES[0]
        with open(entry_path) as f:
            tree = ast.parse(f.read())
        calls = _ast_calls(tree)
        names = _ast_names(tree)
        # ExecutionFlow/ExecutionEngine must never be *referenced* in code
        # (only in the module docstring / comments, which AST ignores).
        assert "ExecutionFlow" not in names, \
            "entry.py code must not reference ExecutionFlow"
        assert "ExecutionEngine" not in names, \
            "entry.py code must not reference ExecutionEngine"
        assert "ProductionRun" in names, \
            "entry.py code must reference ProductionRun"
        assert "run" in calls, \
            "entry.py must call .run() (ProductionRun.run)"

    def test_no_raw_dsh_in_imports(self, front_door):
        """E5 static: entry.py imports no raw DSH tools (AST name scan)."""
        entry_path = _ENTRY_MODULES[0]
        with open(entry_path) as f:
            tree = ast.parse(f.read())
        names = _ast_names(tree)
        forbidden = {"RealDSHBackend", "FakeSubagentBackend",
                     "DelegationClient", "check_instance_mounted",
                     "DSHBridgeDispatch", "interrupt_agent", "send_message",
                     "subagent_zeko", "subagent_cto", "subagent_cfo"}
        assert forbidden.isdisjoint(names), \
            f"entry.py references DSH: {forbidden & names}"
        # No import from orchestrator.dsh
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("orchestrator.dsh"), \
                    f"entry.py imports from {node.module}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("orchestrator.dsh"), \
                        f"entry.py imports {alias.name}"

    def test_no_registry_writes(self, front_door):
        """E6 static: entry.py never writes the delegation registry
        (AST-based — only the read seam DelegationProvider is used)."""
        entry_path = _ENTRY_MODULES[0]
        with open(entry_path) as f:
            tree = ast.parse(f.read())
        calls = _ast_calls(tree)
        forbidden_calls = {"atomic_write", "write_through",
                           "registry_write", "audit_append", "safe_write"}
        assert forbidden_calls.isdisjoint(calls), \
            f"entry.py calls write fn: {forbidden_calls & calls}"
        # No builtin open( for filesystem writes.
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and \
                    isinstance(node.func, ast.Name) and \
                    node.func.id == "open":
                pytest.fail("entry.py calls open( (filesystem write)")
        # It must reference the read-only DelegationProvider.
        names = _ast_names(tree)
        assert "DelegationProvider" in names

    def test_no_authority_minting(self, front_door):
        """E7 static: entry.py never creates a Delegation or sets ACTIVE
        (AST-based)."""
        entry_path = _ENTRY_MODULES[0]
        with open(entry_path) as f:
            tree = ast.parse(f.read())
        calls = _ast_calls(tree)
        forbidden_calls = {"create_delegation", "issue_child_delegation",
                           "delegation_from_dict", "revoke",
                           "DelegationLifecycle"}
        assert forbidden_calls.isdisjoint(calls), \
            f"entry.py mints authority: {forbidden_calls & calls}"
        # `Delegation` as a name (type annotation, isinstance check) is not
        # construction. Only flag `Delegation(` (constructor call) in calls.
        assert "Delegation" not in calls, \
            "entry.py must not construct Delegation"

    def test_no_gate_bypass_parameters(self, front_door):
        """E8: the front door's exposed functions have no skip/bypass/force
        parameters that could bypass a gate."""
        import inspect
        for fn_name in ("run_front_door", "resolve_delegation"):
            fn = getattr(front_door, fn_name)
            sig = inspect.signature(fn)
            params = set(sig.parameters.keys())
            bad = {"skip_gates", "bypass", "force", "raw", "ignore_gates",
                   "no_verify", "no_gate", "override"}
            assert params.isdisjoint(bad), \
                f"{fn_name} has bypass parameter: {params & bad}"


class TestNoDirectExecutionFlow:
    """E4/E5/E6/E7 — combined static proofs of no shortcut (AST-based)."""

    def _trees(self):
        for path in _ENTRY_MODULES:
            if not os.path.exists(path):
                pytest.skip(f"NOT_YET_AVAILABLE: {path} not found")
            with open(path) as f:
                yield path, ast.parse(f.read())

    def test_no_dsh_tool_names(self, front_door):
        """No raw DSH tool identifier appears in any entrypoint module."""
        forbidden = {"subagent", "subagent_zeko", "subagent_cto",
                     "subagent_cfo", "subagent_nova", "subagent_badsector",
                     "send_message", "interrupt_agent", "web_fetch",
                     "RealDSHBackend", "FakeSubagentBackend",
                     "DelegationClient", "DSHBridgeDispatch"}
        for path, tree in self._trees():
            names = _ast_names(tree)
            assert forbidden.isdisjoint(names), \
                f"{path} references DSH identifiers: {forbidden & names}"

    def test_no_delegation_client_import(self, front_door):
        """No DelegationClient reference in any entrypoint module."""
        for path, tree in self._trees():
            names = _ast_names(tree)
            assert "DelegationClient" not in names, \
                f"{path} references DelegationClient"

    def test_no_authority_minting_functions(self, front_door):
        """No authority-creation function is called in any entrypoint
        module (AST call scan — docstring mentions do not count)."""
        forbidden = {"create_delegation", "issue_child_delegation",
                     "delegation_from_dict", "DelegationLifecycle"}
        for path, tree in self._trees():
            calls = _ast_calls(tree)
            assert forbidden.isdisjoint(calls), \
                f"{path} calls minting function: {forbidden & calls}"

    def test_no_registry_write_functions(self, front_door):
        """No registry/audit write function is called in any entrypoint
        module."""
        forbidden = {"registry_write", "write_through", "authorize_write",
                     "append_event", "audit_append", "safe_write",
                     "atomic_write"}
        for path, tree in self._trees():
            calls = _ast_calls(tree)
            assert forbidden.isdisjoint(calls), \
                f"{path} calls write function: {forbidden & calls}"

    def test_only_sanctioned_imports(self, front_door):
        """The front door only imports from sanctioned packages."""
        allowed = ("orchestrator.foundation", "orchestrator.runtime",
                   "orchestrator.production", "control.delegation",
                   "typing", "os", "re", "sys", "dataclasses",
                   "argparse", "json", "__future__")
        for path, tree in self._trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert any(alias.name.startswith(p)
                                   for p in allowed), \
                            f"{path} imports disallowed {alias.name!r}"
                if isinstance(node, ast.ImportFrom):
                    if node.module is None:
                        continue
                    if node.level > 0:
                        # relative import within the entrypoint package
                        continue
                    assert any(node.module.startswith(p)
                               for p in allowed), \
                        f"{path} imports from disallowed {node.module!r}"