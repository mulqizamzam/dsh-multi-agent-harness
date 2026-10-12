"""Registration coverage for the 15-specialist pool (PRD v0.2 §25.1)."""
import os

import yaml

import pytest

from validate_config import all_failures, run_checks, SPECIALIST_IDS

NEW = ("vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger")


def test_expansion_no_config_failures(project_root):
    fails = all_failures(project_root)
    assert not fails, "\n".join(fails)


def test_all_eight_registered_with_unique_ids(project_root):
    reg = yaml.safe_load(open(os.path.join(project_root, "config", "agents.yaml")))
    ids = [a["id"] for a in reg["agents"]]
    assert set(NEW) <= set(ids) and len(ids) == len(set(ids)) == 15
    assert reg["invariants"]["specialist_count"] == 15


def test_every_specialist_has_bounded_role_files(project_root):
    for rid in SPECIALIST_IDS:
        for f in ("AGENT.md", "policy.yaml", "agent.cordis.yml"):
            assert os.path.exists(os.path.join(project_root, "agents", rid, f)), f"{rid}/{f}"


def test_validator_covers_new_roles(project_root):
    # The check names asserted below are the canonical names emitted by
    # `validate_config.run_checks()` (see tests/validate_config.py); this file
    # only looks them up, it does not define them.
    names = {n: ok for n, ok, _ in run_checks(project_root)}
    for rid in NEW:
        assert names.get(f"perm {rid} defaults read-only") is True
        assert names.get(f"perm {rid} defaults approval never") is True
        assert names.get(f"perm adversarial_review reserved (not {rid})") is True
        assert names.get(f"{rid} never_authorizes invariant declared") is True
        assert names.get(f"{rid} deny covers sibling instances") is True


def test_baseline_registry_untouched_except_declared(project_root):
    """Baseline seven keep their registry roles/summaries (PRD v0.2 §8: the
    expansion must not silently redefine baseline roles)."""
    reg = yaml.safe_load(open(os.path.join(project_root, "config", "agents.yaml")))
    by_id = {a["id"]: a for a in reg["agents"]}
    assert by_id["badsector"]["role"] == "adversarial_review"
    assert by_id["badsector"]["pool_group"] == "adversarial"
    assert by_id["cto"]["role"] == "engineering"
    assert by_id["zeko"]["role"] == "operations"
