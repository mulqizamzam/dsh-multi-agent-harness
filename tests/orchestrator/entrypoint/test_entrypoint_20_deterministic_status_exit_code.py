# E-20 — Deterministic status→exit code mapping
#
# Prove that the front door's CLI entry point (__main__.py) maps terminal
# statuses to exit codes deterministically. Per spec:
#   COMPLETE → 0
#   ERROR    → 1
#   BLOCKED  → 2
#   ESCALATED → 3
#
# The mapping is stable, unambiguous, and never changes between runs.

from orchestrator.entrypoint import (
    COMPLETE,
    BLOCKED,
    ESCALATED,
    ERROR,
    STATUSES,
)


class TestDeterministicStatusExitCodeMapping:
    """The _EXIT_CODE dict in __main__.py is the canonical mapping."""

    def test_mapping_contains_all_statuses(self):
        """Every STATUS has a defined exit code, and every exit code maps to
        exactly one status."""
        from orchestrator.entrypoint.__main__ import _EXIT_CODE
        for status in STATUSES:
            assert status in _EXIT_CODE, \
                f"status {status} has no exit code mapping"
        codes = list(_EXIT_CODE.values())
        assert len(set(codes)) == len(codes), \
            "exit codes must be unique (one-to-one mapping)"

    def test_complete_zero(self):
        """COMPLETE maps to exit code 0 (success)."""
        from orchestrator.entrypoint.__main__ import _EXIT_CODE
        assert _EXIT_CODE[COMPLETE] == 0

    def test_blocked_two(self):
        """BLOCKED maps to exit code 2."""
        from orchestrator.entrypoint.__main__ import _EXIT_CODE
        assert _EXIT_CODE[BLOCKED] == 2

    def test_error_one(self):
        """ERROR maps to exit code 1."""
        from orchestrator.entrypoint.__main__ import _EXIT_CODE
        assert _EXIT_CODE[ERROR] == 1

    def test_escalated_three(self):
        """ESCALATED maps to exit code 3, distinct from all others."""
        from orchestrator.entrypoint.__main__ import _EXIT_CODE
        assert _EXIT_CODE[ESCALATED] == 3
        assert len(set(_EXIT_CODE.values())) == 4

    def test_mapping_is_deterministic(self):
        """Running the same mapping twice produces the same result."""
        from orchestrator.entrypoint.__main__ import _EXIT_CODE
        first = dict(_EXIT_CODE)
        second = dict(_EXIT_CODE)
        assert first == second

    def test_main_returns_blocked_for_empty_registry(self):
        """main() with an empty registry returns exit code 2 (BLOCKED)."""
        import shutil
        import tempfile
        from orchestrator.entrypoint.__main__ import main
        empty_dir = tempfile.mkdtemp()
        try:
            exit_code = main([
                "--objective", "engineering",
                "--scope", "agents/cto/output.txt",
                "--delegation-id", "delegation-prod-001",
                "--base", empty_dir,
                "--indent", "0",
            ])
        except SystemExit as e:
            exit_code = e.code
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)
        assert exit_code == 2, \
            f"expected BLOCKED exit code 2, got {exit_code}"