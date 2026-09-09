"""Scenario routing table for the expanded pool (PRD v0.2 §16 / §25.3).

For each PRD §16 scenario, routing must select the declared specialist set —
primary first, optional secondary — and never a blanket fan-out.
"""
import pytest

from orchestrator.foundation.contracts import SPECIALIST_ROLES, Task
from orchestrator.foundation.routing import select_agents, MAX_FAN_OUT


def _task(objective, tid="t-1"):
    return Task(task_id=tid, objective=objective, assigned_role="cto")


@pytest.mark.parametrize("objective,expected", [
    # PRD §16 table — new-role domains (primary [+ secondary])
    ("verify acceptance criteria for the evidence set", ("vera",)),
    # `security` routes argus with badsector secondary (adversarial challenge)
    ("review security scope of the delegated plan", ("argus", "badsector")),
    # `threat_model` is its own argus domain key (no secondary)
    ("threat_model analysis of the API surface", ("argus",)),
    ("architecture_review of the dependency graph", ("atlas",)),
    ("failure_analysis of the race_condition", ("tess", "talon")),
    ("draft policy invariants for the specification", ("quill",)),
    # `integration compatibility`: both keys match scout; longest-match picks
    # `compatibility` (no secondary) — architectural fit comes via atlas only
    # on a bare `integration` match
    ("integration compatibility of the plugin API", ("scout",)),
    ("integration surface of the plugin API", ("scout", "atlas")),
    # `version_drift` is its own scout domain key (no secondary)
    ("version_drift detection across dependencies", ("scout",)),
    ("reliability of the retry and rollback path", ("talon", "tess")),
    ("audit provenance lineage of the decision", ("ledger",)),
])
def test_scenario_routes_to_declared_specialists(objective, expected):
    assert select_agents(_task(objective)) == expected


@pytest.mark.parametrize("objective,expected", [
    # baseline domains unchanged (PRD v0.2 §8: no silent redefinition)
    ("deployment operations on servers", ("zeko",)),
    ("engineering task implementation", ("cto",)),
    ("pricing and unit economics", ("cfo",)),
    ("market research and trends", ("kai",)),
    ("social campaign distribution", ("somad",)),
    ("novel manuscript continuity", ("nova",)),  # no `review` substring
])
def test_baseline_scenarios_unchanged(objective, expected):
    assert select_agents(_task(objective)) == expected


def test_longest_match_beats_prefix_substring():
    """`architecture_review` (atlas) must not be swallowed by the `architecture`
    substring (cto); `security_review` (badsector) must not be swallowed by
    `security` (argus) (ADR 0003 D6 matcher-hardening). Baseline secondaries
    are preserved."""
    assert select_agents(_task("security_review of the plan")) == ("badsector", "cto")
    assert select_agents(_task("plain security scope check")) == ("argus", "badsector")


def test_unknown_domain_still_fails_closed():
    from orchestrator.foundation.routing import RoutingError
    with pytest.raises(RoutingError):
        select_agents(_task("completely unrelated xyzzy"))


def test_no_blanket_fan_out_on_15_pool():
    """MAX_FAN_OUT is len(SPECIALIST_ROLES)-1 = 14; a 2-specialist selection is
    far below it, and the guard is roster-derived, not hardcoded."""
    assert MAX_FAN_OUT == len(SPECIALIST_ROLES) - 1 == 14
    assert len(select_agents(_task("reliability of the retry path"))) <= MAX_FAN_OUT
