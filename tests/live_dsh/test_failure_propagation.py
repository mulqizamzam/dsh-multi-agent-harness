# tests/live_dsh/test_failure_propagation.py — failure propagation through the REAL bridge
#
# Every typed DSH failure (error, refusal, timeout, abort, malformed) must
# produce a deterministic failure_class that the runtime's recovery path
# branches on — never a silent skip or partial success.

import pytest

from orchestrator.dsh import (
    DelegationTimeout, DelegationAborted, ChildFailure, MalformedResult,
    RoleResolutionError,
)
from orchestrator.runtime.collection import classify_adapter_failure
from .contract import (
    STOP_ABORTED, STOP_ERROR, STOP_MAX_TOKENS, STOP_REFUSAL,
    map_stop_reason_to_failure,
)


class TestFailureClassification:
    def test_timeout_classification(self):
        cls, _ = classify_adapter_failure(DelegationTimeout("timeout"))
        assert cls == "environment"

    def test_aborted_classification(self):
        cls, _ = classify_adapter_failure(DelegationAborted("aborted"))
        assert cls == "environment"

    def test_child_failure_classification(self):
        cls, _ = classify_adapter_failure(ChildFailure("child failed"))
        assert cls == "logic"

    def test_malformed_result_classification(self):
        cls, _ = classify_adapter_failure(MalformedResult("bad result"))
        assert cls == "logic"

    def test_role_resolution_classification(self):
        cls, _ = classify_adapter_failure(RoleResolutionError("unknown role"))
        assert cls == "environment"

    def test_unknown_error_classification(self):
        cls, _ = classify_adapter_failure(ValueError("unknown"))
        assert cls == "unknown"

    def test_stop_reason_error_is_logic(self):
        cls, _ = map_stop_reason_to_failure(STOP_ERROR)
        assert cls == "logic"

    def test_stop_reason_refusal_is_logic(self):
        cls, _ = map_stop_reason_to_failure(STOP_REFUSAL)
        assert cls == "logic"

    def test_unknown_stop_reason_is_unknown(self):
        cls, _ = map_stop_reason_to_failure("frobnicated")
        assert cls == "unknown"