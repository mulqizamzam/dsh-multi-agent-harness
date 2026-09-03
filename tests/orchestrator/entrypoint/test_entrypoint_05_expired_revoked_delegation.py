# E-05 — Expired / revoked delegation → BLOCKED
#
# Prove that the front door rejects an expired or revoked delegation (either
# status-based or revocation-list based). The front door never re-activates
# a record and never treats a stale grant as usable authority
# (AUTH-INV-06 / AUTH-INV-05).

from datetime import datetime, timedelta, timezone

from _helpers import make_delegation, make_subtask_result, make_provider, seed_state

from orchestrator.entrypoint import (
    BLOCKED,
    run_front_door,
    FrontDoorRequest,
)


class TestExpiredRevokedDelegation:
    def test_revoked_status_rejected(self, ws, subtask_runner, action_executor):
        """A delegation with status REVOKED → BLOCKED (never re-activated)."""
        delegation = make_delegation(status="REVOKED")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED
        assert "revoked" in " ".join(result.errors).lower() or \
               "active" in " ".join(result.errors).lower()
        assert result.state is None

    def test_revocation_list_rejected(self, ws, subtask_runner,
                                      action_executor):
        """A delegation on the revocation list → BLOCKED (AUTH-INV-06)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=make_provider(delegation, revoked=("delegation-prod-001",)),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED
        assert "revoked" in " ".join(result.errors).lower()

    def test_expired_delegation_rejected(self, ws, subtask_runner,
                                         action_executor):
        """A past-dated expires_at → BLOCKED (AUTH-INV-06)."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        delegation = make_delegation(expires_at=past)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED
        assert "expired" in " ".join(result.errors).lower()

    def test_malformed_expiry_fails_closed(self, ws, subtask_runner,
                                           action_executor):
        """A malformed expires_at is treated as expired (fail-closed)."""
        delegation = make_delegation(expires_at="not-a-timestamp")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED