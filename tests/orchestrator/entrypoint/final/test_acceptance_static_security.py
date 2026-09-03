# tests/orchestrator/entrypoint/final/test_acceptance_static_security.py —
# FINAL SECURITY STATIC CHECK (AST/source inspection)
#
# Phase 5 / FINAL ACCEPTANCE HARDENING.
#
# Confirms by AST/source inspection of the CURRENT production implementation
# (orchestrator/entrypoint/entry.py + __main__.py) that the front door:
#   1. makes no raw DSH call / has no DSH bridge import
#   2. never constructs a Delegation (no Delegation(...), no create_delegation,
#      no delegation_from_dict, no issue_child_delegation)
#   3. never writes the registry (no registry write function, no atomic
#      write through the entrypoint)
#   4. never shortcuts ExecutionFlow / ExecutionEngine directly
#   5. never creates authority/approval (no approval minting, no status
#      assignment, no review fabrication)
#
# The check is static (AST) so it holds regardless of runtime state.

import ast
import os

# tests/orchestrator/entrypoint/final/ -> project root = 5 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

FRONT_DOOR_FILES = [
    os.path.join(PROJECT_ROOT, "orchestrator", "entrypoint", "entry.py"),
    os.path.join(PROJECT_ROOT, "orchestrator", "entrypoint", "__main__.py"),
]

# --- banned raw-tool / bridge identifiers (runtime references only) -------
RAW_DSH_TOKENS = frozenset({
    "subagent_", "send_message", "interrupt_agent", "job_kill", "job_output",
    "DSHBridgeDispatch", "RealDSHBackend", "FakeSubagentBackend",
    "DelegationClient", "check_instance_mounted", "BRIDGE_MARKER_ENV",
    "web_fetch", "todo_write", "workflow",
})

# --- banned authority-minting / registry-write call names ------------------
MINT_CALLS = frozenset({
    "Delegation", "create_delegation", "delegation_from_dict",
    "issue_child_delegation", "revoke", "approval", "grant_authority",
    "NeedsApproval", "authorize", "authority_approve",
})

REGISTRY_WRITE_CALLS = frozenset({
    "registry_write", "write_through", "authorize_write", "append_event",
    "audit_append", "atomic_write", "safe_write", "persist",
})

# --- banned gate-bypass / execution shortcut identifiers -------------------
BYPASS_TOKENS = frozenset({
    "ExecutionFlow", "ExecutionEngine", "ExecutionRequest",
    "RecoveryController", "recheck_authority", "skip_gates", "bypass",
    "no_verify", "no_gate",
})


def _parse(path):
    with open(path) as f:
        return ast.parse(f.read())


def _call_names(tree):
    """All callable names referenced in the AST (Name / Attribute)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _imported_modules(tree):
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    return mods


class TestStaticSecurity:
    def test_files_exist(self):
        """Both front-door production files exist (the check targets the
        CURRENT implementation, not a copy)."""
        for f in FRONT_DOOR_FILES:
            assert os.path.isfile(f), f"missing {f}"

    def test_no_raw_dsh_call(self):
        """Check 1: no raw DSH tool / bridge token in runtime code of either
        front-door module."""
        for path in FRONT_DOOR_FILES:
            tree = _parse(path)
            names = _call_names(tree)
            for banned in RAW_DSH_TOKENS:
                assert banned not in names, \
                    f"{os.path.basename(path)} calls raw DSH {banned!r}"
            # No orchestrator.dsh module import (AST-level, not prose).
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("orchestrator.dsh"):
                            raise AssertionError(
                                f"{path} imports orchestrator.dsh at "
                                f"line {node.lineno}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and \
                            node.module.startswith("orchestrator.dsh"):
                        raise AssertionError(
                            f"{path} imports orchestrator.dsh at "
                            f"line {node.lineno}")

    def test_no_delegation_construction(self):
        """Check 2: the front door never constructs/creates a Delegation —
        it only RESOLVES an existing one read-only."""
        for path in FRONT_DOOR_FILES:
            tree = _parse(path)
            names = _call_names(tree)
            for banned in MINT_CALLS:
                assert banned not in names, \
                    f"{os.path.basename(path)} calls authority-mint {banned!r}"

    def test_no_registry_write(self):
        """Check 3: the front door never writes the registry/state/audit —
        only the read-only DelegationProvider seam is consumed."""
        for path in FRONT_DOOR_FILES:
            tree = _parse(path)
            names = _call_names(tree)
            for banned in REGISTRY_WRITE_CALLS:
                assert banned not in names, \
                    f"{os.path.basename(path)} calls registry write {banned!r}"

    def test_no_executionflow_engine_shortcut(self):
        """Check 4: no direct ExecutionFlow/ExecutionEngine/ExecutionRequest
        reference — ProductionRun.run() is the ONLY execution path."""
        for path in FRONT_DOOR_FILES:
            tree = _parse(path)
            # Collect runtime (non-comment) identifiers, not docstring prose.
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in BYPASS_TOKENS:
                    raise AssertionError(
                        f"{os.path.basename(path)}: runtime reference to "
                        f"{node.id!r} at line {node.lineno}")
                if isinstance(node, ast.Attribute) and \
                        node.attr in BYPASS_TOKENS:
                    raise AssertionError(
                        f"{os.path.basename(path)}: runtime reference to "
                        f"{node.attr!r} at line {node.lineno}")

    def test_productionrun_is_the_only_execution_entry(self):
        """The front door imports and calls ProductionRun (the sanctioned
        entry) — and nothing else that executes the flow."""
        path = os.path.join(PROJECT_ROOT, "orchestrator", "entrypoint",
                            "entry.py")
        tree = _parse(path)
        names = _call_names(tree)
        assert "ProductionRun" in names, \
            "entry.py must call ProductionRun.run()"
        assert "ProductionRun" in _module_imports(path), \
            "entry.py must import ProductionRun"
        for banned in ("ExecutionFlow", "ExecutionEngine", "ExecutionRequest"):
            assert banned not in names, \
                f"entry.py shortcuts {banned}"

    def test_no_authority_or_approval_creation(self):
        """Check 5: no authority/approval creation — no approval_reference
        accepted, no ACTIVE assignment, no review verdict fabrication.
        
        Note: `self.status = status` in FrontDoorResult is the result-envelope
        status field (COMPLETE/BLOCKED/ESCALATED/ERROR), NOT a delegation
        status. The check below allows that legitimate pattern while catching
        delegation-shaped status assignments (status as a dict key or on a
        delegation-named variable).
        """
        path = os.path.join(PROJECT_ROOT, "orchestrator", "entrypoint",
                            "entry.py")
        tree = _parse(path)
        # Check for status assignment on delegation-like targets, not on self.
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Attribute) and \
                            t.attr in ("status", "approval_reference"):
                        # Allow self.status in FrontDoorResult.__init__
                        if isinstance(t.value, ast.Name) and \
                                t.value.id == "self":
                            continue
                        raise AssertionError(
                            f"entry.py assigns {t.attr} on non-self at "
                            f"line {node.lineno}")
                # Also check dict assignments like x["status"] = ...
                if isinstance(t, ast.Subscript) and \
                        isinstance(t.slice, (ast.Str, ast.Constant)):
                    val = getattr(t.slice, "value",
                                  getattr(t.slice, "s", None))
                    if val in ("status", "approval_reference"):
                        raise AssertionError(
                            f"entry.py assigns dict key {val!r} at "
                            f"line {node.lineno}")
        # FrontDoorRequest has no approval/authority-shaped fields.
        import dataclasses
        import sys
        sys.path.insert(0, PROJECT_ROOT)
        try:
            from orchestrator.entrypoint import FrontDoorRequest
            fields = {f.name for f in dataclasses.fields(FrontDoorRequest)}
            for banned in ("approval_reference", "declared_risk", "review",
                           "status", "permissions", "tool_filter"):
                assert banned not in fields, \
                    f"FrontDoorRequest accepts authority field {banned!r}"
        finally:
            if PROJECT_ROOT in sys.path:
                sys.path.remove(PROJECT_ROOT)

    def test_only_resolve_readonly_delegation(self):
        """The only delegation-touching surface is the read-only provider
        resolution + expiry/revocation checks (imported from control)."""
        path = os.path.join(PROJECT_ROOT, "orchestrator", "entrypoint",
                            "entry.py")
        tree = _parse(path)
        names = _call_names(tree)
        # Read-only checks are sanctioned.
        assert "is_revoked" in names or "is_expired" in names
        # The provider's current() is the read seam.
        assert "current" in names


def _module_imports(path):
    with open(path) as f:
        source = f.read()
    return source
