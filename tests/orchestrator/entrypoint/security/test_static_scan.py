# STATIC TESTS — AST/import scan of the front-door source
#
# Static proofs (independent of a live run) that the front door cannot:
#   S1  call raw DSH tools
#   S2  construct a Delegation / mint authority
#   S3  write the protected registry
#   S4  invoke ExecutionFlow / ExecutionEngine directly
#   S5  accept an authority-shaped parameter (risk/approval/review/status)
#
# These scans run on the source files; when the front door is not present the
# whole module reports NOT_YET_AVAILABLE (via pytestmark) — nothing fabricated.

import ast
import os

import pytest

from ._availability import front_door_available, _NOT_YET_AVAILABLE

pytestmark = pytest.mark.skipif(not front_door_available(),
                                reason=_NOT_YET_AVAILABLE)

_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))))
_FRONT_DOOR_MODULES = [
    os.path.join(_ROOT, "orchestrator", "entrypoint", "entry.py"),
    os.path.join(_ROOT, "orchestrator", "entrypoint", "__main__.py"),
]

# Raw DSH tool names that must never appear in the front door.
_DSH_TOOLS = frozenset({
    "subagent", "subagent_zeko", "subagent_cto", "subagent_cfo",
    "subagent_kai", "subagent_somad", "subagent_badsector", "subagent_nova",
    "subagent_fork", "send_message", "interrupt_agent",
    "bash", "write", "edit", "web_fetch",
    "DSHBridgeDispatch", "RealDSHBackend", "FakeSubagentBackend",
    "DelegationClient", "check_instance_mounted", "BRIDGE_MARKER_ENV",
})

# Delegation / authority-minting functions.
_MINT_FUNCTIONS = frozenset({
    "create_delegation", "delegation_from_dict", "issue_child_delegation",
    "revoke", "DelegationLifecycle",
})

# Registry / audit write functions.
_WRITE_FUNCTIONS = frozenset({
    "registry_write", "write_through", "authorize_write",
    "append_event", "audit_append", "safe_write", "atomic_write",
})

# Direct execution / gate-bypass targets.
_BYPASS_TARGETS = frozenset({
    "ExecutionFlow", "ExecutionEngine", "ExecutionRequest",
    "RecoveryController", "recheck_authority", "authorize",
    "skip_gates", "bypass", "force", "no_verify", "no_gate",
})

# Authority-shaped parameter names that must never be accepted.
_AUTHORITY_FIELDS = frozenset({
    "declared_risk", "approval_reference", "review", "verdict",
    "permissions", "role", "status", "tool_filter", "tool_surface",
    "grant", "sudo",
})


def _sources():
    for path in _FRONT_DOOR_MODULES:
        if not os.path.exists(path):
            pytest.skip(f"NOT_YET_AVAILABLE: {path} not found")
        with open(path) as f:
            yield path, ast.parse(f.read())


def _source_text():
    parts = []
    for path in _FRONT_DOOR_MODULES:
        if not os.path.exists(path):
            pytest.skip(f"NOT_YET_AVAILABLE: {path} not found")
        with open(path) as f:
            parts.append(f.read())
    return "\n".join(parts)


class TestNoRawDshCall:
    def test_no_dsh_tool_names(self):
        """S1: no raw DSH tool identifier referenced in any front-door module
        (AST-based — comments are ignored)."""
        forbidden = {"subagent", "subagent_zeko", "subagent_cto",
                     "subagent_cfo", "subagent_kai", "subagent_somad",
                     "subagent_badsector", "subagent_nova", "subagent_fork",
                     "send_message", "interrupt_agent",
                     "RealDSHBackend", "FakeSubagentBackend",
                     "DelegationClient", "check_instance_mounted",
                     "DSHBridgeDispatch", "web_fetch"}
        for path, tree in _sources():
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    names.add(node.attr)
            assert forbidden.isdisjoint(names), \
                f"{path} references DSH identifiers: {forbidden & names}"

    def test_no_orchestrator_dsh_import(self):
        """S1: the front door never imports orchestrator.dsh."""
        for path, tree in _sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("orchestrator.dsh"), \
                        f"{path} imports from {node.module}"
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("orchestrator.dsh"), \
                            f"{path} imports {alias.name}"


class TestNoDelegationConstruction:
    def test_no_delegation_constructor_call(self):
        """S2: no Delegation(...) / create_delegation call in front door."""
        for path, tree in _sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = None
                    if isinstance(node.func, ast.Name):
                        name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        name = node.func.attr
                    if name in _MINT_FUNCTIONS or name == "Delegation":
                        pytest.fail(
                            f"{path}:{node.lineno} calls authority minting "
                            f"{name!r}")

    def test_no_mint_function_names(self):
        """S2: no mint-function is CALLED (AST call scan). The import of the
        read-only helpers is_expired/is_revoked is not a minting call."""
        for path, tree in _sources():
            calls = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        calls.add(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        calls.add(node.func.attr)
            mint_calls = calls & _MINT_FUNCTIONS
            assert not mint_calls, \
                f"{path} calls mint function(s): {mint_calls}"
            assert "Delegation" not in calls, \
                f"{path} constructs a Delegation"


class TestNoRegistryWrite:
    def test_no_write_function_names(self):
        """S3: no registry/audit write function is called (AST-based)."""
        for path, tree in _sources():
            calls = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        calls.add(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        calls.add(node.func.attr)
            write_calls = calls & _WRITE_FUNCTIONS
            assert not write_calls, \
                f"{path} calls write fn(s): {write_calls}"

    def test_no_filesystem_write_call(self):
        """S3: no open() call to protected files in entry.py."""
        entry = _FRONT_DOOR_MODULES[0]
        with open(entry) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and \
                    isinstance(node.func, ast.Name) and \
                    node.func.id == "open":
                pytest.fail("entry.py must not call open() for filesystem write")
        # Also check registry file names not present in source.
        with open(entry) as f:
            src = f.read()
        for forbidden in ("delegations.json", "revocations.json"):
            assert forbidden not in src, \
                f"entry.py must not contain registry file name ({forbidden})"


class TestNoDirectExecutionFlow:
    def test_no_executionflow_reference(self):
        """S4: entry.py code never references ExecutionFlow (AST — the module
        docstring may mention the class, but code never names it)."""
        entry = _FRONT_DOOR_MODULES[0]
        with open(entry) as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        assert "ExecutionFlow" not in names, \
            "entry.py code must not reference ExecutionFlow"
        assert "ProductionRun" in names, \
            "entry.py code must reference ProductionRun"

    def test_no_engine_reference(self):
        """S4: no ExecutionEngine reference (AST)."""
        entry = _FRONT_DOOR_MODULES[0]
        with open(entry) as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        assert "ExecutionEngine" not in names

    def test_only_production_run_call_into_runtime(self):
        """S4: the only call into the runtime is ProductionRun.run()."""
        entry = _FRONT_DOOR_MODULES[0]
        with open(entry) as f:
            src = f.read()
        assert "ProductionRun(project=request.project" in src
        assert "run.run(" in src
        for forbidden in ("flow.run(", "engine.execute(", ".run_flow("):
            assert forbidden not in src, f"entry.py must not call {forbidden}"


class TestNoAuthorityShapedParameter:
    def test_no_authority_fields_on_request(self):
        """S5: FrontDoorRequest dataclass exposes no authority-bearing field."""
        from orchestrator.entrypoint import FrontDoorRequest
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FrontDoorRequest)}
        assert _AUTHORITY_FIELDS.isdisjoint(fields), \
            f"request exposes authority fields: {fields & _AUTHORITY_FIELDS}"
        # The required data fields are present.
        assert {"objective", "scope", "delegation_id"} <= fields

    def test_no_bypass_parameter_on_functions(self):
        """S5: run_front_door / resolve_delegation have no bypass parameter."""
        import inspect
        from orchestrator.entrypoint import run_front_door, resolve_delegation
        for fn in (run_front_door, resolve_delegation):
            params = set(inspect.signature(fn).parameters.keys())
            assert params.isdisjoint(_BYPASS_TARGETS), \
                f"{fn.__name__} has bypass param: {params & _BYPASS_TARGETS}"


class TestSanctionedImportsOnly:
    def test_only_sanctioned_imports(self):
        """S6: the front door imports only sanctioned packages (AST check)."""
        allowed_prefixes = (
            "orchestrator.foundation", "orchestrator.runtime",
            "orchestrator.production", "control.delegation",
            "typing", "os", "re", "sys", "dataclasses",
            "argparse", "json", "__future__",  # __main__.py, entry.py
        )
        for path, tree in _sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert any(alias.name.startswith(p)
                                   for p in allowed_prefixes), \
                            f"{path}:{node.lineno} imports disallowed " \
                            f"{alias.name!r}"
                if isinstance(node, ast.ImportFrom):
                    if node.module is None:
                        continue
                    # Relative import (level > 0) is within the entrypoint
                    # package itself — allowed.
                    if node.level > 0:
                        continue
                    assert any(node.module.startswith(p)
                               for p in allowed_prefixes), \
                        f"{path}:{node.lineno} imports from disallowed " \
                        f"{node.module!r}"


class TestTerminalVocabulary:
    def test_terminal_statuses_are_exact(self):
        """S7: the front door emits only the four terminal statuses."""
        from orchestrator.entrypoint import (COMPLETE, BLOCKED, ESCALATED,
                                             ERROR, STATUSES)
        assert (COMPLETE, BLOCKED, ESCALATED, ERROR) == STATUSES
        assert set(STATUSES) == {"COMPLETE", "BLOCKED", "ESCALATED", "ERROR"}

    def test_schema_marker_present(self):
        """S7: the envelope carries a schema marker."""
        from orchestrator.entrypoint import FrontDoorResult
        env = FrontDoorResult(status="ERROR", errors=("x",)).to_dict()
        assert "schema" in env
        assert "status" in env
        assert "errors" in env