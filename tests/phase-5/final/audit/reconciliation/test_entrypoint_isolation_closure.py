"""Phase 5 / Entrypoint import-isolation closure tests.

Lock the closure of the 10 entrypoint import-isolation failures:

  1. The entrypoint suite collects and passes standalone (337).
  2. The entrypoint helpers live in the uniquely-named module `_helpers`
     (no bare `from conftest import X` in entrypoint test modules).
  3. No test was removed/deselected: every entrypoint test module that existed
     is still collectable; collection count is not reduced.
  4. The closure report records the exact before/after and the remaining
     out-of-scope master-audit failures.

Write-only scope: tests/phase-5/final/audit/reconciliation/ +
docs/phase-5/final/audit/reconciliation/. Nothing else is modified;
no production/DSH/control-plane change; no security claim.
"""

import os
import re
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DOCS = os.path.join(PROJECT_ROOT, "docs")
ENTRYPOINT = os.path.join(PROJECT_ROOT, "tests", "orchestrator", "entrypoint")
CLOSURE_DOC = "phase-5/final/audit/reconciliation/0002-entrypoint-isolation-closure.md"
RECON_DOC = "phase-5/final/audit/reconciliation/0001-reconciliation-report.md"

PYTHON = os.path.join(PROJECT_ROOT, ".venv-tests", "bin", "python")


def _read_doc(path):
    full = os.path.join(DOCS, path)
    if not os.path.exists(full):
        return None
    with open(full, "r") as f:
        return f.read()


def _entrypoint_test_modules():
    """All test_*.py modules directly under tests/orchestrator/entrypoint/."""
    return sorted(
        f for f in os.listdir(ENTRYPOINT)
        if f.startswith("test_") and f.endswith(".py")
    )


def _grep_entrypoint(pattern):
    """Search entrypoint test modules for a pattern; return matching lines."""
    hits = []
    for mod in _entrypoint_test_modules():
        with open(os.path.join(ENTRYPOINT, mod)) as f:
            for i, line in enumerate(f, 1):
                if re.search(pattern, line):
                    hits.append(f"{mod}:{i}: {line.strip()}")
    return hits


class TestEntrypointIsolationFix:
    """The import-isolation fix is in place."""

    def test_helpers_module_exists(self):
        assert os.path.isfile(os.path.join(ENTRYPOINT, "_helpers.py")), (
            "unique helper module _helpers.py must exist")

    def test_no_bare_conftest_import_in_entrypoint_tests(self):
        """No entrypoint test module uses the ambiguous bare `from conftest`
        import (the root cause of the 10 failures)."""
        hits = _grep_entrypoint(r"^from conftest import |^import conftest$")
        assert hits == [], (
            f"entrypoint test modules still use bare conftest import: {hits}")

    def test_helpers_module_uniquely_named(self):
        """There is exactly one _helpers.py in the whole tree."""
        matches = []
        for root, _, files in os.walk(os.path.join(PROJECT_ROOT, "tests")):
            if "_helpers.py" in files:
                matches.append(os.path.join(root, "_helpers.py"))
        assert matches == [os.path.join(ENTRYPOINT, "_helpers.py")], (
            f"_helpers must be unique; found: {matches}")

    def test_helpers_exports_required_symbols(self):
        import ast
        path = os.path.join(ENTRYPOINT, "_helpers.py")
        tree = ast.parse(open(path).read())
        defs = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef,
                                                                 ast.ClassDef))}
        for sym in ("make_delegation", "make_subtask_result", "make_provider",
                    "seed_state", "StubSubtaskRunner", "StubActionExecutor"):
            assert sym in defs, f"_helpers missing {sym}"


class TestEntrypointSuiteGreen:
    """The Front Door suite passes standalone (collection + execution)."""

    def test_entrypoint_collects(self):
        r = subprocess.run(
            [PYTHON, "-m", "pytest", "tests/orchestrator/entrypoint/", "--co", "-q"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=120,
        )
        assert r.returncode == 0, r.stderr
        assert re.search(r"tests collected", r.stdout), r.stdout
        m = re.search(r"(\d+) tests collected", r.stdout)
        assert m is not None
        assert int(m.group(1)) >= 301, (
            "entrypoint collection must not shrink below its historical count")

    def test_entrypoint_suite_passes(self):
        r = subprocess.run(
            [PYTHON, "-m", "pytest", "tests/orchestrator/entrypoint/", "-q"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=600,
        )
        assert r.returncode == 0, (
            f"entrypoint suite not green:\n{r.stdout}\n{r.stderr}")


class TestNoCoverageLoss:
    """No test was removed, deselected, or renamed to dodge collection."""

    def test_all_entrypoint_test_modules_present(self):
        expected = {
            "test_cli.py", "test_entry.py",
            "test_entrypoint_01_valid_objective.py",
            "test_entrypoint_02_empty_objective.py",
            "test_entrypoint_03_missing_delegation.py",
            "test_entrypoint_04_unknown_delegation.py",
            "test_entrypoint_05_expired_revoked_delegation.py",
            "test_entrypoint_06_scope_outside_delegation.py",
            "test_entrypoint_07_free_text_authority_injection.py",
            "test_entrypoint_08_fake_approval_reference.py",
            "test_entrypoint_09_declared_low_intrinsic_high.py",
            "test_entrypoint_10_blocked_propagation.py",
            "test_entrypoint_11_escalated_propagation.py",
            "test_entrypoint_12_unexpected_exception.py",
            "test_entrypoint_13_json_serialization.py",
            "test_entrypoint_14_no_direct_executionflow_entry.py",
            "test_entrypoint_15_no_raw_dsh_invocation.py",
            "test_entrypoint_16_no_delegation_creation.py",
            "test_entrypoint_17_no_authority_from_chat_text.py",
            "test_entrypoint_18_complete_requires_verification.py",
            "test_entrypoint_19_audit_ids_preserved.py",
            "test_entrypoint_20_deterministic_status_exit_code.py",
            "test_entrypoint_static_source_checks.py",
            "test_static_security.py",
        }
        present = set(_entrypoint_test_modules())
        missing = expected - present
        assert not missing, f"entrypoint test modules removed: {missing}"

    def test_the_10_failing_test_names_present(self):
        """The 10 tests that failed are still present (not renamed/deleted)."""
        # Verify the specific test functions exist in their modules.
        import ast
        checks = {
            "test_cli.py": ["test_exit_code_complete", "test_exit_code_blocked",
                            "test_json_stdin_happy_path",
                            "test_json_stdin_cli_overrides",
                            "test_json_stdin_invalid", "test_module_runs",
                            "test_module_rejects_free_text_delegation",
                            "test_module_missing_required"],
            "test_entrypoint_16_no_delegation_creation.py":
                ["test_resolve_is_read_only", "test_no_registry_file_written"],
        }
        for mod, fns in checks.items():
            path = os.path.join(ENTRYPOINT, mod)
            tree = ast.parse(open(path).read())
            defined = {n.name for n in ast.walk(tree)
                       if isinstance(n, ast.FunctionDef)}
            for fn in fns:
                assert fn in defined, f"{mod} lost test {fn}"


class TestClosureDocumentation:
    """The closure report records the exact before/after and remaining items."""

    def test_closure_document_exists(self):
        assert _read_doc(CLOSURE_DOC) is not None, "closure report must exist"

    def test_closure_records_10_before(self):
        t = _read_doc(CLOSURE_DOC) or ""
        assert "10" in t and "import-isolation" in t

    def test_closure_records_root_cause(self):
        t = _read_doc(CLOSURE_DOC) or ""
        assert "conftest" in t and "shadow" in t

    def test_closure_records_failures_after(self):
        t = _read_doc(CLOSURE_DOC) or ""
        assert "2977 passed" in t, "closure must record post-fix pass count"
        assert "337 passed" in t, "closure must record entrypoint pass count"

    def test_closure_reports_out_of_scope_master_audit(self):
        t = _read_doc(CLOSURE_DOC) or ""
        assert "master-audit" in t, "closure must report remaining master-audit"
        assert "ENVIRONMENT" in t, "closure must classify remaining failures"

    def test_closure_records_collection_not_reduced(self):
        t = _read_doc(CLOSURE_DOC) or ""
        assert "2998" in t, "closure must record full-suite collection count"
        assert "not reduced" in t or "not a reduction" in t, (
            "closure must state collection was not reduced")

    def test_closure_scope_check_present(self):
        t = _read_doc(CLOSURE_DOC) or ""
        assert "SCOPE CHECK" in t

    def test_reconciliation_r1_preserved_as_historical(self):
        t = _read_doc(RECON_DOC) or ""
        assert "2761 passed, 15 skipped, 10 failed" in t or \
            "2761 passed, 15 skipped, 10 isolation-failures" in t, (
            "historical R1 count must be preserved as a historical record")