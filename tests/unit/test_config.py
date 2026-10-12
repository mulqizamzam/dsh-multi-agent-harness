"""Config/invariant validation tests (referenced by existing config files)."""

import os
import subprocess
import sys
import pytest

# Import the module form of validate-config.py. The check NAMES asserted below
# are not literals owned by this file: they are the names
# `validate_config.run_checks()` emits (the `check(...)` calls in
# tests/validate_config.py). Rename one there and update the lookups here.
from validate_config import all_failures, project_root, run_checks


class TestValidateConfig:
    """Tests that the config validation script referenced by config files passes."""

    def test_validate_config_no_failures(self, project_root):
        """validate_config.all_failures() must return empty — all checks pass."""
        fails = all_failures(project_root)
        assert not fails, f"validate_config failures:\n" + "\n".join(fails)

    def test_validate_config_standalone_runs(self, project_root):
        """The standalone validate-config.py script must exit 0."""
        script = os.path.join(project_root, "tests", "validate-config.py")
        assert os.path.exists(script)
        result = subprocess.run(
            [sys.executable, script, "--root", project_root],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    def test_registry_invariants_present(self, project_root):
        """Verify the specific invariants from the registry are set."""
        results = dict((n, o) for n, o, _ in run_checks(project_root))
        assert results.get("registry peer_relationship") is True
        assert results.get("registry badsector reviewer") is True
        assert results.get("registry orchestrator not 8th") is True

    def test_permission_invariants_present(self, project_root):
        """Verify the specific invariants from the permission matrix are set."""
        results = dict((n, o) for n, o, _ in run_checks(project_root))
        assert results.get("perm no self-grant") is True
        assert results.get("perm badsector never executes") is True
        assert results.get("perm cfo no transaction") is True
        assert results.get("perm destructive approval/denied") is True

    def test_all_role_mappings_consistent(self, project_root):
        """Every role in the mapping has allow∩deny=∅ and matching policy."""
        from validate_config import SPECIALIST_IDS
        results = dict((n, o) for n, o, _ in run_checks(project_root))
        for rid in SPECIALIST_IDS:
            assert results.get(f"{rid} allow∩deny=∅") is True, f"{rid} allow∩deny=∅ failed"
            assert results.get(f"{rid} mapping==policy allow") is True, f"{rid} mapping==policy allow failed"
            assert results.get(f"{rid} mapping==policy deny") is True, f"{rid} mapping==policy deny failed"
            assert results.get(f"{rid} tool names verified") is True, f"{rid} tool names verified failed"
            assert results.get(f"{rid} no delegation tools") is True, f"{rid} no delegation tools failed"
            assert results.get(f"{rid} max_depth 1") is True, f"{rid} max_depth 1 failed"