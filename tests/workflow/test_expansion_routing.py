"""Capability routing for the 15-specialist pool (PRD v0.2 §15/§16).

Baseline domains must keep their primary specialists (PRD v0.2 §22); the
`verification` domain moves badsector → vera as documented in ADR 0003 D6.
"""

import pytest

from orchestrator.foundation.contracts import (
    DOMAIN_ROLE,
    SPECIALIST_ROLES,
    Task,
)
from orchestrator.foundation.routing import (
    RoutingError,
    select_agents,
    validate_no_fanout,
)

NEW_ROLES = ("vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger")


def test_roster_is_15_with_new_roles():
    assert len(SPECIALIST_ROLES) == 15
    assert set(NEW_ROLES) <= set(SPECIALIST_ROLES)
    # Baseline order preserved first, new roles appended in PRD v0.2 §9 order.
    assert SPECIALIST_ROLES[:7] == (
        "zeko", "cto", "cfo", "kai", "somad", "badsector", "nova")
    assert SPECIALIST_ROLES[7:] == NEW_ROLES


@pytest.mark.parametrize("objective,primary", [
    ("verification of acceptance criteria", "vera"),
    ("evidence completeness check", "vera"),
    ("acceptance criteria verification", "vera"),
    ("threat_model for the API", "argus"),
    ("privilege_analysis of the service", "argus"),
    ("architecture_review of module boundaries", "atlas"),
    ("dependency_boundary analysis", "atlas"),
    ("failure_analysis of the timeout path", "tess"),
    ("race_condition review", "tess"),
    ("policy translation into invariants", "quill"),
    ("specification decomposition", "quill"),
    ("integration compatibility of the plugin", "scout"),
    ("version_drift detection", "scout"),
    ("retry and idempotency semantics", "talon"),
    ("rollback durability", "talon"),
    ("audit provenance of the decision lineage", "ledger"),
])
def test_new_domains_route_to_new_specialists(objective, primary):
    t = Task(task_id="t1", objective=objective, assigned_role=primary)
    sel = select_agents(t)
    assert sel[0] == primary
    assert all(r in SPECIALIST_ROLES for r in sel)
    assert len(sel) <= 2  # minimum sufficient set: primary + at most one secondary


def test_baseline_domains_unchanged():
    assert DOMAIN_ROLE["architecture"] == "cto"        # baseline preserved (ADR 0003 D6)
    assert DOMAIN_ROLE["security_review"] == "badsector"
    assert DOMAIN_ROLE["red_team"] == "badsector"
    assert DOMAIN_ROLE["adversarial_review"] == "badsector"
    assert DOMAIN_ROLE["operations"] == "zeko"
    assert DOMAIN_ROLE["finance"] == "cfo"
    assert DOMAIN_ROLE["research"] == "kai"
    assert DOMAIN_ROLE["social"] == "somad"
    assert DOMAIN_ROLE["writing"] == "nova"


def test_verification_moved_to_vera():
    assert DOMAIN_ROLE["verification"] == "vera"       # documented move (ADR 0003 D6)


def test_longest_match_wins_over_substring_baseline():
    """`architecture_review` (atlas) must beat its substring `architecture`
    (cto) when the specific tag is present; free-text `architecture` stays cto.
    """
    specific = Task(task_id="t2", objective="architecture_review of boundaries",
                    assigned_role="atlas")
    assert select_agents(specific)[0] == "atlas"
    plain = Task(task_id="t3", objective="architecture of the game client",
                 assigned_role="cto")
    assert select_agents(plain)[0] == "cto"
    # security_review (baseline, badsector) must beat its substring security.
    sec = Task(task_id="t4", objective="security_review of the release",
               assigned_role="badsector")
    assert select_agents(sec)[0] == "badsector"


def test_minimum_set_with_declared_secondary():
    t = Task(task_id="t5", objective="reliability of the retry loop",
             assigned_role="talon")
    assert select_agents(t) == ("talon", "tess")       # ADR 0003 D6 secondary


def test_no_blanket_fanout_over_15_pool():
    # Selecting ALL 15 is a blanket fan-out and must raise (MAX_FAN_OUT = 14).
    with pytest.raises(RoutingError):
        validate_no_fanout(SPECIALIST_ROLES)


def test_routing_rejects_non_specialists():
    with pytest.raises(RoutingError):
        validate_no_fanout(("orchestrator",))
