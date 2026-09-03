# tests/orchestrator/execution/test_recovery_runtime.py — Session C (G11)
#
# Full-cycle recovery driver tests (orchestrator/execution/recovery_runtime/):
#   - full cycle: failure → PRESERVE → DIAGNOSE → REPLAN → AUTHORITY RECHECK
#     → EXECUTE → VERIFY → COMPLETE
#   - no blind retry (empty cause / identical cause / attempt cap)
#   - no authority expansion (recovery beyond original authority DENIED)
#   - stale-state refusal (version drift between failure and recovery)
#   - restoration verification (rollback path requires independent verifier)
#   - fail-closed (any denial → FAILED/ESCALATED, never partial COMPLETE)
#   - backend-agnostic (bridge-shaped stub variant)
#   - audit trail (recovery events recorded)

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import (
    Delegation, Task, ORCHESTRATOR,
)
from orchestrator.execution.recovery_runtime import (
    run_recovery_cycle, RecoveryRunResult,
)
from orchestrator.runtime.result import COMPLETE, FAILED, ESCALATED


def make_delegation(*, id="delegation-recovery", action="write",
                    target="agents/cto/out.txt", environment="dev",
                    scope_operations=("read", "write", "code_write"),
                    scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
                    scope_environments=("dev",),
                    status="ACTIVE", version=1):
    return Delegation(
        id=id, principal="human", delegate=ORCHESTRATOR,
        project="multi-agent-harness", task="recovery-task",
        action=action, target=target, environment=environment,
        scope_operations=tuple(scope_operations),
        scope_resources=tuple(scope_resources),
        scope_environments=tuple(scope_environments),
        expires_at="", status=status, version=version,
    )


ORIGINAL_AUTHORITY = {
    "actions": ["write"],
    "targets": ["agents/cto/out.txt"],
    "grants": [],
}


class TestFullRecoveryCycle:
    def test_cycle_to_complete(self, tmp_path):
        """Execution failure → recovery → COMPLETE (G11 closure)."""
        delegation = make_delegation()
        events = []

        def _executor(req):
            return {"exit_code": 0, "target": req.target}

        result = run_recovery_cycle(
            task_id="task-1", preserved_version=1,
            failure_class="logic", cause="observed mismatch",
            delegation=delegation,
            action="write", target="agents/cto/out.txt", environment="dev",
            action_category="code_change",
            expected_outcome={"exit_code": 0},
            original_authority=ORIGINAL_AUTHORITY,
            current_version=1, project="multi-agent-harness",
            base=str(tmp_path), audit_fn=lambda ev: events.append(ev) or "ev",
            executor_fn=_executor, revocation_list=(),
        )
        assert result.outcome == COMPLETE, result.errors
        assert result.final_state == "COMPLETE"
        assert result.recovery and result.recovery.get("state") == "COMPLETED"
        assert result.verification and result.verification.get("verdict")
        assert result.execution_observed is not None

    def test_audit_trail_recorded(self, tmp_path):
        """The cycle emits recovery / authority_recheck / execution_attempt /
        verification events through the audit channel."""
        delegation = make_delegation()
        events = []

        def _executor(req):
            return {"exit_code": 0, "target": req.target}

        run_recovery_cycle(
            task_id="task-audit", preserved_version=1,
            failure_class="logic", cause="provider hiccup",
            delegation=delegation,
            action="write", target="agents/cto/out.txt", environment="dev",
            action_category="code_change",
            expected_outcome={"exit_code": 0},
            original_authority=ORIGINAL_AUTHORITY,
            current_version=1, project="multi-agent-harness",
            base=str(tmp_path), audit_fn=lambda ev: events.append(ev) or "ev",
            executor_fn=_executor, revocation_list=(),
        )
        classes = {e.get("event_class") for e in events}
        assert "recovery_state_transition" in classes
        assert "authority_recheck" in classes
        assert "execution_attempt" in classes
        assert "recovery_runtime" in classes


class TestNoBlindRetry:
    def test_empty_cause_refused(self, tmp_path):
        """No blind retry: empty cause → refused (AUTH-INV-16)."""
        delegation = make_delegation()
        result = run_recovery_cycle(
            task_id="task-nb1", preserved_version=1,
            failure_class="logic", cause="",
            delegation=delegation,
            action="write", target="agents/cto/out.txt", environment="dev",
            action_category="code_change",
            expected_outcome={"exit_code": 0},
            original_authority=ORIGINAL_AUTHORITY,
            current_version=1, project="multi-agent-harness",
            base=str(tmp_path), revocation_list=(),
        )
        assert result.outcome == FAILED
        assert any("no blind retry" in e for e in result.errors)


class TestNoAuthorityExpansion:
    def test_privilege_escalation_refused(self, tmp_path):
        """Recovery attempting a target outside the original authority is
        DENIED (REC-004 / THREAT-017)."""
        delegation = make_delegation()
        events = []

        def _executor(req):
            return {"exit_code": 0, "target": req.target}

        # The recovery attempts a target NOT in the original authority.
        result = run_recovery_cycle(
            task_id="task-esc", preserved_version=1,
            failure_class="logic", cause="trying to escalate",
            delegation=delegation,
            action="write", target="state/registry/other.json",
            environment="dev", action_category="code_change",
            expected_outcome={"exit_code": 0},
            original_authority=ORIGINAL_AUTHORITY,
            current_version=1, project="multi-agent-harness",
            base=str(tmp_path), audit_fn=lambda ev: events.append(ev) or "ev",
            executor_fn=_executor, revocation_list=(),
        )
        assert result.outcome == FAILED
        assert any("escalat" in e.lower() or "privilege" in e.lower()
                   for e in result.errors)


class TestStaleStateRefusal:
    def test_version_drift_refused(self, tmp_path):
        """A stale state version between failure and recovery is refused
        (THREAT-022 / REC-005)."""
        delegation = make_delegation()
        # preserved_version=1 but current_version=5 → mismatch → refused.
        result = run_recovery_cycle(
            task_id="task-stale", preserved_version=1,
            failure_class="logic", cause="stale version",
            delegation=delegation,
            action="write", target="agents/cto/out.txt", environment="dev",
            action_category="code_change",
            expected_outcome={"exit_code": 0},
            original_authority=ORIGINAL_AUTHORITY,
            current_version=5, project="multi-agent-harness",
            base=str(tmp_path), revocation_list=(),
        )
        assert result.outcome == FAILED
        assert any("version" in e.lower() for e in result.errors)


class TestRestorationVerification:
    def test_rollback_requires_independent_verifier(self, tmp_path):
        """Rollback path: restoration must be independently verified (REC-003);
        a self verifier is refused."""
        delegation = make_delegation()
        result = run_recovery_cycle(
            task_id="task-restore", preserved_version=1,
            failure_class="logic", cause="rollback needed",
            delegation=delegation,
            action="write", target="agents/cto/out.txt", environment="dev",
            action_category="code_change",
            expected_outcome={"exit_code": 0},
            original_authority=ORIGINAL_AUTHORITY,
            current_version=1, project="multi-agent-harness",
            base=str(tmp_path), revocation_list=(),
            rollback=True, restoration_evidence="",
            restoration_verifier="",
        )
        assert result.outcome == FAILED
        assert any("restoration" in e.lower() for e in result.errors)


class TestBackendAgnostic:
    def test_bridge_shaped_executor(self, tmp_path):
        """The driver is backend-agnostic: a bridge-shaped executor (like the
        RealDSHBackend stub used in tests/live_dsh) is invoked through the
        same cycle."""
        delegation = make_delegation()
        bridge_calls = []

        def _bridge_executor(req):
            bridge_calls.append(req.target)
            return {"exit_code": 0, "target": req.target,
                    "run_id": "real-abc123"}

        result = run_recovery_cycle(
            task_id="task-bridge", preserved_version=1,
            failure_class="environment", cause="provider rate limit",
            delegation=delegation,
            action="write", target="agents/cto/out.txt", environment="dev",
            action_category="code_change",
            expected_outcome={"exit_code": 0},
            original_authority=ORIGINAL_AUTHORITY,
            current_version=1, project="multi-agent-harness",
            base=str(tmp_path), executor_fn=_bridge_executor,
            revocation_list=(),
        )
        assert result.outcome == COMPLETE, result.errors
        assert bridge_calls == ["agents/cto/out.txt"]
        assert result.execution_observed["observed"].get("run_id") == "real-abc123"


class TestRevocationRefusal:
    def test_revoked_delegation_denies(self, tmp_path):
        """Recovery with a revoked delegation is DENIED at authority re-check
        (AUTH-INV-06 / AUTH-INV-12)."""
        delegation = make_delegation(status="REVOKED")
        result = run_recovery_cycle(
            task_id="task-rev", preserved_version=1,
            failure_class="logic", cause="revoked",
            delegation=delegation,
            action="write", target="agents/cto/out.txt", environment="dev",
            action_category="code_change",
            expected_outcome={"exit_code": 0},
            original_authority=ORIGINAL_AUTHORITY,
            current_version=1, project="multi-agent-harness",
            base=str(tmp_path), revocation_list=(delegation.id,),
        )
        assert result.outcome == FAILED
        assert any("deny" in e.lower() or "revoked" in e.lower()
                   for e in result.errors)
