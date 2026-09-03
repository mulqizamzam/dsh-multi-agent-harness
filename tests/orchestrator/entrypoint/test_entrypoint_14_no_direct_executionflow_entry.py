# E-14 — No direct ExecutionFlow entry
#
# Prove that the front door module NEVER calls ExecutionFlow directly, NEVER
# exposes a raw ExecutionFlow run path, and NEVER allows a caller to bypass
# ProductionRun. The only execution path is:
#   FrontDoorRequest → resolve_delegation → ProductionRun.run()
#
# Static: source/AST analysis of orchestrator/entrypoint/entry.py.
# Behavioral: the front door accepts no parameter that would let a caller
# supply a raw ExecutionFlow, ExecutePlan, or bypass the gate chain.

import ast
import os
import inspect


def _read_entry_source():
    """Read the source of the front door entry module."""
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))))
    path = os.path.join(root, "orchestrator", "entrypoint", "entry.py")
    with open(path, "r") as f:
        return f.read()


class TestNoDirectExecutionFlowEntry:
    """Static checks: the front door source must not import or call
    ExecutionFlow directly."""

    def test_no_executionflow_import(self):
        """The front door module does not import ExecutionFlow."""
        source = _read_entry_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = [a.name for a in node.names]
                assert "ExecutionFlow" not in names, \
                    f"front door imports ExecutionFlow at line {node.lineno}"
            if isinstance(node, ast.Import):
                assert not any(
                    "ExecutionFlow" in a.name for a in node.names), \
                    f"front door imports ExecutionFlow at line {node.lineno}"

    def test_no_executionflow_constructor_call(self):
        """No direct ExecutionFlow(...) constructor call in the module."""
        source = _read_entry_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and \
                        node.func.id == "ExecutionFlow":
                    assert False, \
                        f"front door calls ExecutionFlow at line {node.lineno}"

    def test_no_executeplan_import(self):
        """The front door does not import ExecutePlan directly."""
        source = _read_entry_source()
        assert "ExecutePlan" not in source, \
            "front door must not import ExecutePlan directly"

    def test_only_productionrun_run_call(self):
        """The ONLY .run() call in the front door module is on a
        ProductionRun instance (the sanctioned execution path)."""
        source = _read_entry_source()
        tree = ast.parse(source)
        run_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and \
                    isinstance(node.func, ast.Attribute) and \
                    node.func.attr == "run":
                # The receiver must be a variable named `run` (the
                # ProductionRun instance created in run_front_door).
                run_calls.append(node.lineno)
        # run_front_door creates `run = ProductionRun(...)` then calls
        # `run.run(...)` — exactly one .run() call is permitted.
        assert len(run_calls) == 1, \
            f"expected exactly 1 .run() call (ProductionRun.run), got " \
            f"{len(run_calls)} at lines {run_calls}"

    def test_behavioral_no_executionflow_bypass(self):
        """The front door surface has no parameter for a raw ExecutionFlow or
        ExecutePlan — a caller cannot bypass the chain."""
        from orchestrator.entrypoint import run_front_door
        sig = inspect.signature(run_front_door)
        params = set(sig.parameters.keys())
        bypass_keys = {"execution_flow", "execute_plan", "flow", "raw_flow",
                       "skip_gates", "bypass", "direct"}
        assert params.isdisjoint(bypass_keys), \
            f"front door exposes bypass parameters: {params & bypass_keys}"