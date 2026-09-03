# E-SRC — Static import/source checks for the front door
#
# These four checks prove that the entrypoint module (orchestrator/entrypoint/)
# cannot bypass the existing control chain:
#
#   1. No DSH raw tool call    — no direct invocation of subagent_*, bash, etc.
#   2. No registry write        — no write to state/registry/** or audit/**
#   3. No authority minting     — no Delegation creation, no ACTIVE set, no
#                                 approval reference fabrication
#   4. No gate bypass           — the front door does not skip any gate (no
#                                 direct execution engine call, no direct
#                                 write_through, no skip_gates parameter)
#
# All checks are AST-based on the production source modules.

import ast
import os


def _module_path(name):
    """Resolve a dotted module name to a file path under the project root."""
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))))
    parts = name.split(".")
    return os.path.join(root, *parts) + ".py"


def _read_source(module_name):
    path = _module_path(module_name)
    with open(path, "r") as f:
        return f.read()


def _parse_tree(source):
    return ast.parse(source)


# Modules that are part of the "front door" (entrypoint package).
_FRONT_DOOR_MODULES = [
    "orchestrator.entrypoint.entry",
    "orchestrator.entrypoint.__main__",
]

# DSH tool names that must never appear in the front door.
_DSH_TOOLS = frozenset({
    "subagent", "subagent_zeko", "subagent_cto", "subagent_cfo",
    "subagent_kai", "subagent_somad", "subagent_badsector", "subagent_nova",
    "subagent_fork", "send_message",
    "bash", "write", "edit", "web_fetch",
    "DSHBridgeDispatch", "RealDSHBackend", "FakeSubagentBackend",
    "DelegationClient", "check_instance_mounted", "interrupt_agent",
    "BRIDGE_MARKER_ENV",
})

# Registry/audit write functions that must never be called from the front door.
_WRITE_FUNCTIONS = frozenset({
    "registry_write", "write_through", "authorize_write",
    "append_event", "audit_append",
    "safe_write", "atomic_write",
})

# Authority minting functions that must never be called.
_MINT_FUNCTIONS = frozenset({
    "create_delegation", "delegation_from_dict",
    "issue_child_delegation", "revoke",
})

# Gate bypass functions/classes that must never be called directly.
_BYPASS_TARGETS = frozenset({
    "ExecutionEngine", "ExecutionRequest",
    "RecoveryController",
    "write_through",  # must not call directly; only through ProductionRun
    "recheck_authority",  # must not call to force ALLOW
    "authorize",  # must not call to bypass
})


class TestStaticSourceChecks:
    """Combined static import/source checks for all front-door modules."""

    def test_no_dsh_raw_tool_call(self):
        """Check 1: No DSH raw tool name appears in any front-door module."""
        for mod in _FRONT_DOOR_MODULES:
            source = _read_source(mod)
            for tool in _DSH_TOOLS:
                assert tool not in source, \
                    f"{mod} references DSH tool {tool!r}"

    def test_no_delegationclient_import(self):
        """Check 1b: No DelegationClient import in entrypoint."""
        for mod in _FRONT_DOOR_MODULES:
            source = _read_source(mod)
            assert "DelegationClient" not in source, \
                f"{mod} imports DelegationClient"

    def test_no_registry_write(self):
        """Check 2: No registry/audit write function in any front-door module."""
        for mod in _FRONT_DOOR_MODULES:
            source = _read_source(mod)
            for fn in _WRITE_FUNCTIONS:
                assert fn not in source, \
                    f"{mod} references write function {fn!r}"

    def test_no_authority_minting(self):
        """Check 3: No authority minting function in any front-door module.
        Uses AST call detection to avoid false positives from substrings
        (e.g., 'is_revoked' contains 'revoke')."""
        for mod in _FRONT_DOOR_MODULES:
            source = _read_source(mod)
            tree = _parse_tree(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    if func_name in _MINT_FUNCTIONS:
                        assert False, \
                            f"{mod} calls mint function {func_name} at line {node.lineno}"

    def test_no_delegation_constructor(self):
        """Check 3b: No Delegation(...) constructor call in front-door code."""
        for mod in _FRONT_DOOR_MODULES:
            source = _read_source(mod)
            tree = _parse_tree(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    if func_name in ("Delegation", "create_delegation",
                                     "delegation_from_dict"):
                        assert False, \
                            f"{mod} calls {func_name} at line {node.lineno}"

    def test_no_gate_bypass(self):
        """Check 4: No gate bypass function/class in any front-door module."""
        for mod in _FRONT_DOOR_MODULES:
            source = _read_source(mod)
            for target in _BYPASS_TARGETS:
                assert target not in source, \
                    f"{mod} references bypass target {target!r}"

    def test_no_executionflow_in_entry(self):
        """Check 4b: entry.py must not CALL or IMPORT ExecutionFlow (only
        reference ProductionRun). Comments/docstrings may name it as a
        prohibition; the AST must show no runtime reference."""
        source = _read_source("orchestrator.entrypoint.entry")
        tree = _parse_tree(source)
        # Collect runtime (non-comment) references to ExecutionFlow
        refs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "ExecutionFlow":
                refs.append(node.lineno)
            if isinstance(node, ast.Attribute) and node.attr == "ExecutionFlow":
                refs.append(node.lineno)
            if isinstance(node, ast.ImportFrom):
                if any(a.name == "ExecutionFlow" for a in node.names):
                    refs.append(node.lineno)
        assert not refs, \
            f"entry.py references ExecutionFlow at runtime lines {refs}"
        assert "ProductionRun" in source, \
            "entry.py must reference ProductionRun"

    def test_no_skip_or_bypass_parameters(self):
        """Check 4c: The front door functions have no skip_gates/bypass
        parameter."""
        import inspect
        from orchestrator.entrypoint import run_front_door, resolve_delegation
        for fn in (run_front_door, resolve_delegation):
            sig = inspect.signature(fn)
            params = set(sig.parameters.keys())
            bad = {"skip_gates", "bypass", "force", "raw", "ignore_gates",
                   "no_verify", "no_gate"}
            assert params.isdisjoint(bad), \
                f"{fn.__name__} has bypass parameter: {params & bad}"

    def test_only_sanctioned_imports(self):
        """Check: The front door only imports from sanctioned packages
        (or relative imports within the entrypoint package)."""
        allowed_prefixes = (
            "orchestrator.foundation",
            "orchestrator.runtime",
            "orchestrator.production",
            "control.delegation",
            "typing", "os", "re", "sys", "dataclasses",
            "argparse", "json",  # __main__.py
            ".entry", ".",  # relative imports within the package
            "__future__",  # annotations
        )
        for mod in _FRONT_DOOR_MODULES:
            source = _read_source(mod)
            tree = _parse_tree(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name
                        assert any(name.startswith(p) for p in allowed_prefixes), \
                            f"{mod} imports disallowed {name!r} at line {node.lineno}"
                if isinstance(node, ast.ImportFrom):
                    if node.module is None:
                        continue
                    if node.module.startswith(".") or node.level > 0:
                        # relative import within the package
                        continue
                    if node.module == "__future__":
                        # standard annotations import
                        continue
                    assert any(node.module.startswith(p) for p in allowed_prefixes), \
                        f"{mod} imports from disallowed {node.module!r} at line {node.lineno}"