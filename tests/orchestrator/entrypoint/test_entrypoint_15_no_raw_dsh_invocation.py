# E-15 — No raw DSH invocation
#
# Prove that the front door module NEVER calls raw DSH tools (subagent_*,
# bash, write, edit, web_fetch, send_message, DSHBridgeDispatch, etc.). The
# front door only reads from the DelegationProvider (read-only registry
# access) and delegates to ProductionRun which uses the sanctioned DSH
# surface through the DelegationClient.
#
# Static: source/AST analysis of orchestrator/entrypoint/entry.py.
# Behavioral: the front door surface has no DSH tool parameters.

import ast
import os
import inspect


def _read_entry_source():
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))))
    path = os.path.join(root, "orchestrator", "entrypoint", "entry.py")
    with open(path, "r") as f:
        return f.read()


# DSH tool names that MUST NOT appear in the front door module.
_FORBIDDEN_TOOL_NAMES = frozenset({
    "subagent", "subagent_zeko", "subagent_cto", "subagent_cfo",
    "subagent_kai", "subagent_somad", "subagent_badsector", "subagent_nova",
    "subagent_fork", "send_message",
    "bash", "write", "edit", "web_fetch",
    "DSHBridgeDispatch", "RealDSHBackend",
    "FakeSubagentBackend",
    "DelegationClient",
    "check_instance_mounted",
    "interrupt_agent",
})

# Modules that are allowed imports (the front door's permitted surface).
_ALLOWED_IMPORTS = frozenset({
    "Delegation", "DelegationProvider", "FileDelegationProvider",
    "is_expired", "is_revoked",
    "ProductionRun", "ProductionDenied", "ProductionEscalated",
    "ProductionStopped", "NoValidDelegation", "ObjectiveNotActionable",
    "PlanRejected", "ReportGenerationFailed",
    "Callable", "re", "dataclass", "field",
    "FrontDoorRequest", "FrontDoorResult", "FrontDoorError",
    "COMPLETE", "BLOCKED", "ESCALATED", "ERROR", "STATUSES",
    "resolve_delegation", "run_front_door", "_stopped",
})


class TestNoRawDshInvocation:
    """Static: the front door source must not reference DSH tool names."""

    def test_no_dsh_tool_name_in_source(self):
        """No forbidden DSH tool name appears in the source code."""
        source = _read_entry_source()
        for name in _FORBIDDEN_TOOL_NAMES:
            assert name not in source, \
                f"front door module references DSH tool name {name!r}"

    def test_no_dsh_import_in_ast(self):
        """No import of DSH modules in the AST. Checks the imported MODULE
        names (not aliases, which may be `dataclass`/`field`/`Callable`)."""
        source = _read_entry_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    name = a.name
                    if name == "__future__":
                        continue
                    allowed_prefixes = {
                        "orchestrator.foundation",
                        "orchestrator.runtime",
                        "orchestrator.production",
                        "control.delegation",
                        "typing", "os", "re", "sys", "dataclasses",
                    }
                    assert any(name.startswith(p) for p in allowed_prefixes), \
                        f"front door imports disallowed module {name!r} at line {node.lineno}"
            if isinstance(node, ast.ImportFrom):
                mod = str(node.module or "")
                if mod == "__future__":
                    continue
                # The front door may ONLY import from these packages.
                allowed_prefixes = {
                    "orchestrator.foundation",
                    "orchestrator.runtime",
                    "orchestrator.production",
                    "control.delegation",
                    "dataclasses", "typing",
                }
                assert any(mod.startswith(p) for p in allowed_prefixes), \
                    f"front door imports from disallowed module {mod!r} at line {node.lineno}"

    def test_behavioral_no_dsh_parameter(self):
        """The front door surface has no DSH tool parameter."""
        from orchestrator.entrypoint import run_front_door
        sig = inspect.signature(run_front_door)
        params = set(sig.parameters.keys())
        dsh_params = {"subtask_runner", "action_executor", "provider", "now"}
        # subtask_runner/action_executor are test hooks, not DSH tools.
        # DSH tool names must not appear.
        for name in _FORBIDDEN_TOOL_NAMES:
            assert name not in params, \
                f"front door exposes DSH tool parameter {name!r}"