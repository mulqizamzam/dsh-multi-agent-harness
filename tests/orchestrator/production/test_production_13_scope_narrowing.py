# PROD-13 — Execution-time scope staleness (AUTH-INV-04/06)
#
# A scope change that leaves the delegation ACTIVE between planning and
# execution must DENY at the execution-time re-check: the runtime re-derives
# the grant against the CURRENT registry record (scope_contained) instead of
# executing under the superseded planning-time snapshot. Counterpart of
# PROD-02 (revocation), which covers the revoked/expired dimensions.
#
# Regression for the 2026-09-07 live-verification finding: flow.py re-read
# delegation_now but consulted it only for is_active/revocation/expiry, then
# built ExecutionRequest from the planning-time delegation — so a "quiet"
# narrowing of an ACTIVE delegation was invisible at execution.
#
# Tests: AUTH-1, AUTH-2 (AUTH-INV-04/06), fail-closed, no mutation

import dataclasses

import pytest

from conftest import make_delegation, make_subtask_result

from orchestrator.runtime import MemoryDelegationProvider
from orchestrator.production import (
    ProductionDenied, ObjectivePlanner, BoundedExecutor,
)


def _plan():
    return ObjectivePlanner().plan(
        objective="engineering",
        scope=("agents/cto/output.txt",),
        required_authority_context="delegation-prod-001")


class TestScopeNarrowingRecheck:
    def test_narrowed_active_delegation_denied(self, ws, subtask_runner,
                                               action_executor):
        """Scope narrowing with status still ACTIVE → DENY, no mutation."""
        delegation = make_delegation()  # agents/** + docs/**, ops incl. write
        provider = MemoryDelegationProvider(delegation)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        def narrow_before_execute():
            # Human narrows the grant but leaves it ACTIVE: fewer resources,
            # fewer operations. The in-flight grant no longer fits.
            provider.replace(dataclasses.replace(
                delegation,
                scope_resources=("agents/cto/**",),
                scope_operations=("read", "analysis"),
            ))

        plan = _plan()
        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        with pytest.raises(ProductionDenied) as excinfo:
            ex.execute(plan, delegation=delegation, provider=provider,
                       pre_execute=narrow_before_execute)
        assert "contained" in str(excinfo.value).lower()

        flow = ex.last_flow
        assert flow is not None
        result = flow._result
        assert result is not None and result.outcome == "BLOCKED"
        assert len(result.files_written) == 0
        events = [e for e in flow._get_audit().read()
                  if e.get("event_class") == "execution_denial"
                  and "AUTH-INV-04" in str(e.get("error", ""))]
        assert events, "expected an execution_denial audit event citing AUTH-INV-04"

    def test_added_prohibition_denied(self, ws, subtask_runner,
                                      action_executor):
        """Adding a prohibited action to an ACTIVE parent re-gates the child:
        the child may ADD prohibitions, never DROP one (AUTH-INV-04)."""
        delegation = make_delegation(prohibited_actions=())
        provider = MemoryDelegationProvider(delegation)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        def add_prohibition():
            provider.replace(dataclasses.replace(
                delegation, prohibited_actions=("write",)))

        plan = _plan()
        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        with pytest.raises(ProductionDenied) as excinfo:
            ex.execute(plan, delegation=delegation, provider=provider,
                       pre_execute=add_prohibition)
        assert "contained" in str(excinfo.value).lower()
        flow = ex.last_flow
        assert flow is not None
        assert flow._result is not None and flow._result.outcome == "BLOCKED"
        assert len(flow._result.files_written) == 0

    def test_widening_or_unchanged_still_allowed(self, ws, subtask_runner,
                                                 action_executor):
        """A parent change that keeps the grant contained (e.g. widened
        resources) must NOT trigger the new denial — no false positive."""
        delegation = make_delegation()
        provider = MemoryDelegationProvider(delegation)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        def widen_before_execute():
            # True superset: every original resource is kept, infra/** added.
            provider.replace(dataclasses.replace(
                delegation,
                scope_resources=("agents/**", "docs/**",
                                 "multi-agent-harness/**", "infra/**"),
            ))

        plan = _plan()
        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        ex.execute(plan, delegation=delegation, provider=provider,
                   pre_execute=widen_before_execute)

        flow = ex.last_flow
        assert flow is not None
        result = flow._result
        assert result is not None and result.outcome != "BLOCKED"
        events = [e for e in flow._get_audit().read()
                  if e.get("event_class") == "execution_denial"
                  and "AUTH-INV-04" in str(e.get("error", ""))]
        assert not events, "widening must not produce an AUTH-INV-04 denial"
