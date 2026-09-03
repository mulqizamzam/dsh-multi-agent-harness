# tests/orchestrator/execution/test_execution_request.py — ExecutionRequest
# validation (Phase 3 / Session C).
#
# The request object carries DATA + the authority RECORD (never a grant). It
# must fail closed: missing delegation, malformed target/environment, unknown
# action category → rejected at construction or validation.

import pytest

from control.verification import VerificationError

from orchestrator.execution import (
    ExecutionRequest,
    ExecutionEngine,
    ExecutionDenied,
)

from .conftest import make_delegation, make_request


class TestExecutionRequestConstruction:
    def test_requires_task_id(self, delegation):
        with pytest.raises(ValueError, match="task_id"):
            ExecutionRequest(task_id="", delegation=delegation,
                             action="write", target="agents/cto/x.txt")

    def test_requires_target(self, delegation):
        with pytest.raises(ValueError, match="target"):
            ExecutionRequest(task_id="t", delegation=delegation,
                             action="write", target="")

    def test_requires_action(self, delegation):
        with pytest.raises(ValueError, match="action"):
            ExecutionRequest(task_id="t", delegation=delegation,
                             action="", target="agents/cto/x.txt")

    def test_expected_outcome_must_be_dict(self, delegation):
        with pytest.raises(ValueError, match="expected_outcome"):
            ExecutionRequest(task_id="t", delegation=delegation,
                             action="write", target="agents/cto/x.txt",
                             expected_outcome="not a dict")

    def test_delegation_must_be_structured(self):
        """A non-Delegation delegation (model text / dict) is refused at
        construction (AUTH-INV-01/05)."""
        with pytest.raises(ValueError, match="structured Delegation"):
            ExecutionRequest(task_id="t", delegation={"principal": "human"},
                             action="write", target="agents/cto/x.txt")

    def test_unknown_action_category_fails_closed(self, delegation):
        """An unknown action → cannot determine verification requirements →
        fail-closed at construction (control.verification contract)."""
        with pytest.raises(VerificationError):
            make_request(delegation=delegation, action="totally_unknown",
                         target="agents/cto/x.txt")

    def test_category_resolution_from_action(self, delegation):
        """`code_write` maps to the code_change verification category."""
        req = make_request(delegation=delegation, action="code_write",
                           target="agents/cto/x.py")
        assert req.resolve_action_category() == "code_change"
        assert req.is_write_class() is True

    def test_write_class_detection(self, delegation):
        req_write = make_request(delegation=delegation, action="write",
                                 target="agents/cto/x.txt")
        req_read = make_request(delegation=delegation, action="read",
                                target="agents/cto/x.txt")
        assert req_write.is_write_class() is True
        assert req_read.is_write_class() is False

    def test_original_authority_baseline(self, delegation):
        """The recovery privilege baseline reflects the delegation scope
        (actions/targets/grants) — data only, never a grant."""
        req = make_request(delegation=delegation, action="write",
                           target="agents/cto/x.txt")
        auth = req.original_authority()
        assert "write" in auth["actions"]
        assert "agents/**" in auth["targets"]
        assert auth["grants"] == ["write"]

    def test_original_authority_empty_without_delegation(self):
        req = ExecutionRequest(task_id="t", delegation=None,
                               action="write", target="agents/cto/x.txt")
        assert req.original_authority() == {}


class TestRequestValidation:
    def test_validate_denies_without_delegation(self, ws, engine_factory):
        """A request without a structured delegation is DENIED at validation
        (AUTH-INV-05) — no authority, no execution."""
        req = make_request(task_id="no-auth", delegation=None,
                           action="write", target="agents/cto/x.txt")
        eng = engine_factory(req)
        with pytest.raises(ExecutionDenied, match="AUTH-INV-05"):
            eng.validate()
        assert eng.verification is None  # never reached verification

    def test_validate_denies_bad_environment(self, ws, engine_factory):
        """An environment outside the delegation's scope is DENIED
        (AUTH-INV-11)."""
        d = make_delegation(task_id="env", id="delegation-exec-env",
                            scope_environments=("prod",))
        req = make_request(task_id="env", delegation=d, environment="dev",
                           action="write", target="agents/cto/x.txt")
        eng = engine_factory(req)
        with pytest.raises(ExecutionDenied, match="environment"):
            eng.validate()

    def test_validate_accepts_valid_request(self, ws, delegation,
                                            engine_factory):
        """A valid request validates and creates the VerificationSession with
        the expected outcome declared BEFORE execution (VERIFY-001)."""
        req = make_request(task_id="ok", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"exit_code": 0})
        eng = engine_factory(req)
        eng.validate()
        assert eng.verification is not None
        assert eng.verification.expected_outcome.expected == {"exit_code": 0}
