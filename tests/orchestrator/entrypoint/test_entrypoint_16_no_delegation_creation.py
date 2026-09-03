# E-16 — No Delegation creation / registry write
#
# Prove that the front door NEVER creates a Delegation, NEVER sets a record
# ACTIVE, NEVER writes the protected registry (state/registry/**), and NEVER
# fabricates authority. It only RESOLVES an existing structured delegation
# (read-only) and hands it to ProductionRun (ADR 0002, AUTH-INV-05).
#
# Static: source/AST analysis of orchestrator/entrypoint/entry.py.
# Behavioral: resolve_delegation never mutates; no registry write occurs.

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


class TestNoDelegationCreation:
    def test_no_delegation_constructor_call(self):
        """The front door never constructs a Delegation directly."""
        source = _read_entry_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "Delegation", \
                    f"front door creates Delegation at line {node.lineno}"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr != "create_delegation", \
                    f"front door creates delegation at line {node.lineno}"
                assert node.func.attr != "delegation_from_dict", \
                    f"front door builds delegation at line {node.lineno}"

    def test_no_registry_write_functions(self):
        """The front door never calls registry-write functions."""
        source = _read_entry_source()
        for fn in ("registry_write", "write_through", "authorize_write",
                   "append_event", "audit_append"):
            assert fn not in source, \
                f"front door references write function {fn!r}"

    def test_no_status_active_set(self):
        """The front door never sets a delegation status to ACTIVE."""
        source = _read_entry_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                # setattr / object.__setattr__ on status
                pass
        # Search for assigning "ACTIVE"
        assert 'status="ACTIVE"' not in source.replace(" ", "")
        assert "ACTIVE" in source  # it only checks status != "ACTIVE"

    def test_resolve_is_read_only(self, ws):
        """resolve_delegation consumes the provider read-only: the provider's
        current() is called but never a write; a memory provider with an
        ACTIVE delegation is returned unchanged and the registry is untouched."""
        from orchestrator.runtime import DelegationProvider
        from _helpers import make_delegation
        from orchestrator.entrypoint import (
            FrontDoorRequest, resolve_delegation,
        )
        delegation = make_delegation()
        seen = {"current": 0}

        class Provider(DelegationProvider):
            def current(self):
                seen["current"] += 1
                return delegation, ()

        result = resolve_delegation(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=Provider(),
        )
        assert result is delegation
        assert seen["current"] == 1
        assert result.status == "ACTIVE"  # unchanged, never re-minted

    def test_no_registry_file_written(self, ws):
        """A run that fails delegation resolution writes no registry file."""
        import os
        from _helpers import make_provider
        registry_dir = os.path.join(ws, "state", "registry")
        before = set(os.listdir(registry_dir)) if os.path.isdir(registry_dir) else set()
        from orchestrator.entrypoint import run_front_door, FrontDoorRequest
        run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=make_provider(None),
        )
        after = set(os.listdir(registry_dir)) if os.path.isdir(registry_dir) else set()
        assert after == before, "front door wrote to the registry"