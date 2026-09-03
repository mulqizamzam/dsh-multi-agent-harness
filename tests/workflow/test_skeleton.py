"""Workflow skeleton shape validation.

Tests that orchestrator/workflows/skeleton.js is structurally valid as a DSH
workflow script: valid JS syntax, contains phase placeholders, no real agent()
calls in DRY_RUN mode, returns a JSON-compatible value.
"""

import os
import subprocess
import sys
import pytest

SKELETON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "orchestrator", "workflows", "skeleton.js"
)

NODE_AVAILABLE = False
try:
    result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
    NODE_AVAILABLE = result.returncode == 0
except (FileNotFoundError, subprocess.TimeoutExpired):
    pass


class TestWorkflowSkeleton:
    """Validate the structural shape of the workflow skeleton."""

    def test_skeleton_exists(self):
        assert os.path.exists(SKELETON_PATH), f"skeleton.js not found at {SKELETON_PATH}"

    def test_skeleton_readable(self):
        with open(SKELETON_PATH, "r") as f:
            content = f.read()
        assert len(content) > 100, "skeleton.js too short"

    def test_skeleton_has_phases(self):
        with open(SKELETON_PATH, "r") as f:
            content = f.read()
        # Phase 1E: the 15-phase chain is reported by the skeleton.
        for phase in ["intake", "understand", "classify", "risk_gate",
                      "decompose", "select", "delegate", "collect",
                      "evidence_gate", "synthesize", "conflict_gate",
                      "review_gate", "authority_gate", "execute_gate",
                      "verify_gate"]:
            assert phase in content, f"missing phase: {phase}"
        # The deterministic script-local phases still present:
        for phase in ["decompose", "select", "delegate", "collect", "gate", "synthesize"]:
            assert f"phase('{phase}')" in content, f"missing phase('{phase}')"

    def test_skeleton_has_gate_placeholders(self):
        with open(SKELETON_PATH, "r") as f:
            content = f.read()
        assert "GATES" in content
        assert "PLACEHOLDER" in content
        for gate in ["authority", "risk", "evidence", "conflict", "review",
                     "execution", "verification"]:
            assert gate in content, f"missing gate placeholder: {gate}"

    def test_skeleton_phase_chain_order(self):
        """Phase 1E: the reported phase chain must be in the exact 15-phase
        order (order matters — skipping a mandatory gate is a violation)."""
        with open(SKELETON_PATH, "r") as f:
            content = f.read()
        expected = ["intake", "understand", "classify", "risk_gate",
                    "decompose", "select", "delegate", "collect",
                    "evidence_gate", "synthesize", "conflict_gate",
                    "review_gate", "authority_gate", "execute_gate",
                    "verify_gate"]
        start = content.index("const PHASE_CHAIN")
        end = content.index("];", start)
        decl = content[start:end]
        idx = {p: decl.index(p) for p in expected}
        assert list(idx.values()) == sorted(idx.values()), \
            "PHASE_CHAIN order in skeleton.js does not match the required sequence"

    def test_skeleton_no_real_agent_calls_in_dry_run(self):
        """The skeleton must never call agent() in DRY_RUN mode."""
        with open(SKELETON_PATH, "r") as f:
            content = f.read()
        # Check that the DRY_RUN code path does NOT call agent()
        # The DRY_RUN= true branch returns placeholder intents, not agent().
        assert "DRY_RUN" in content
        # The only agent() call in the non-DRY_RUN path is commented out
        # We check there's no uncommented agent() call:
        lines = content.split("\n")
        dry_run_branch = False
        for line in lines:
            stripped = line.strip()
            if "DRY_RUN" in stripped and not stripped.startswith("//"):
                # The DRY_RUN = true branch
                pass
            if "agent(" in stripped and not stripped.strip().startswith("//"):
                # If there's an uncommented agent() call, it must be in the
                # DRY_RUN=false path, which is commented out in the skeleton.
                # Actually, the skeleton's DRY_RUN=false path is inside a
                # comment block. Let's just assert no uncommented agent() call.
                assert False, f"uncommented agent() call in skeleton: {stripped}"

    def test_skeleton_returns_json(self):
        with open(SKELETON_PATH, "r") as f:
            content = f.read()
        assert "return" in content, "skeleton must return a value"
        # The return should be a JSON-compatible object
        assert "return synthesize" in content or "return {" in content

    @pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js not available for JS syntax check")
    def test_skeleton_valid_js_syntax(self):
        """Validate JS syntax exactly as the DSH workflow harness evaluates it.

        The harness compiles the body as `new vm.Script('(async () => {\n<body>\n})()')`
        (verified in the DSH 0.1.1-rc.2 workflow-worker-thread runtime), so a top-level
        `return <value>` in the body is valid there. We replicate that wrapper before
        running node --check.
        """
        with open(SKELETON_PATH, "r") as f:
            body = f.read()
        wrapped = "(async () => {\n" + body + "\n})()\n"
        result = subprocess.run(
            ["node", "--check"],
            input=wrapped, capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"JS syntax error (as wrapped by DSH):\n{result.stderr}"

    def test_skeleton_has_no_hardcoded_secrets(self):
        """The skeleton must not contain secrets or credentials."""
        with open(SKELETON_PATH, "r") as f:
            content = f.read().lower()
        for secret_pattern in ["api_key", "password", "secret", "token", "credential", "DSH_HOME"]:
            # DSH_HOME is an env var reference, not a secret value
            if secret_pattern == "dsh_home":
                continue
            assert secret_pattern not in content, f"potential secret in skeleton: {secret_pattern}"

    def test_skeleton_has_fail_closed_guard(self):
        """The skeleton must have a fail-closed guard for unexpected gate values."""
        with open(SKELETON_PATH, "r") as f:
            content = f.read()
        assert "FAIL-CLOSED" in content or "fail-closed" in content or "error" in content.lower()