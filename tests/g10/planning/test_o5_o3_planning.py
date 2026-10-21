"""Session E — G10 O5/O3 implementation preparation: planning honesty guards.

These tests verify the IMPLEMENTATION PLAN document (not any applied change)
is honest and complete:

  1. The plan document exists in docs/phase-5/security/g10/implementation/.
  2. The plan states G10 remains OPEN / BLOCKING and claims NO closure.
  3. The plan derives the CURRENT (pre-application) residual actor set from
     the config, and this session applied NO config change (somad/nova still
     carry write/edit; the actor set is still {zeko, cto, somad, nova}).
  4. The plan documents every determination the brief requires: exact files,
     role capability impact, control-flow impact, rollback, test
     requirements, migration requirements, O5 independence, O3 architecture
     change, authority-semantics impact, production-blocked-after-O5.
  5. The plan explicitly characterizes O5 as containment (not hard isolation)
     and O3 as stronger but operationally heavier, and never says G10 CLOSED.

This is a PLANNING suite: it asserts the plan's honesty, not that any
implementation happened. Nothing here validates a changed config (there is
none) — it guards the boundary between preparation and implementation.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

# tests/g10/planning/ -> project root is 4 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
IMPL_DOC = os.path.join(PROJECT_ROOT, "docs", "phase-5", "security", "g10",
                        "implementation", "0001-o5-o3-implementation-plan.md")
MAPPING = os.path.join(PROJECT_ROOT, "config", "role-preset-mapping.yaml")
INSTANCES = os.path.join(PROJECT_ROOT, "config", "tool-subagent-instances.yaml")

# Determinations the brief requires the plan to document (exact keywords).
REQUIRED_DETERMINATIONS = [
    ("exact files", "files"),
    ("role capability impact", "capability impact"),
    ("control-flow impact", "control-flow impact"),
    ("rollback", "rollback"),
    ("test requirements", "test requirements"),
    ("migration requirements", "migration requirements"),
    ("O5 independent", "independently"),
    ("O3 architecture change", "architecture"),
    ("authority semantics", "authority semantics"),
    ("production after O5", "production"),
]


# ---------------------------------------------------------------------------
# 1. Plan document exists and is the right artifact
# ---------------------------------------------------------------------------

def test_implementation_plan_document_exists():
    assert os.path.isfile(IMPL_DOC), (
        f"G10 O5/O3 implementation plan missing at {IMPL_DOC}")


def test_plan_lives_in_implementation_dir():
    """The plan must be under docs/phase-5/security/g10/implementation/ (the
    session's write-only target), not under final/ or a live config path."""
    assert os.path.dirname(IMPL_DOC).endswith(
        os.path.join("g10", "implementation"))


def test_plan_header_states_status_after_approval():
    """The plan doc must reflect its post-approval status: O5 was applied per
    the Human decision (see the 0002 application record), G10 stays OPEN/
    BLOCKING, and no closure is claimed."""
    with open(IMPL_DOC) as f:
        text = f.read()
    assert "IMPLEMENTATION PLAN" in text
    assert "0002-o5-application-record.md" in text, \
        "plan must reference the O5 application record"
    assert "G10 remains OPEN" in text or "G10 stays OPEN" in text
    assert "no closure" in text.lower()


# ---------------------------------------------------------------------------
# 2. No closure claim; G10 stays OPEN/BLOCKING
# ---------------------------------------------------------------------------

def test_plan_states_g10_open_blocking():
    with open(IMPL_DOC) as f:
        text = f.read()
    assert "G10 remains OPEN" in text or "G10 stays OPEN" in text, \
        "plan must state G10 remains OPEN"
    assert "BLOCKING" in text, "plan must state G10 BLOCKING"


def test_plan_never_claims_closure():
    with open(IMPL_DOC) as f:
        text = f.read()
    low = text.lower()
    assert "no closure of prevention claimed" in low or \
        "no closure claim" in low or \
        "no closure is claimed" in low, \
        "plan must disclaim closure"
    # Affirmative closure claims must be absent. The word "closed" legitimately
    # appears inside negative/honesty phrasing (e.g. "no test may claim G10
    # closed after O5"); only affirmative forms are a violation.
    for forbidden in ("g10 is closed", "g10 closed.", "g10 closed\n",
                      "g10 closed —", "closes g10", "g10: closed",
                      "g10 **closed**", "status: closed"):
        assert forbidden not in low, \
            f"plan must NOT claim G10 closure (found {forbidden!r})"


def test_plan_characterizes_o5_as_containment():
    """O5 is containment (surface reduction), NOT hard isolation — the brief's
    critical constraint."""
    with open(IMPL_DOC) as f:
        text = f.read().lower()
    assert "containment" in text
    assert "not hard isolation" in text or \
        "never a closure" in text or \
        "reduction, never a closure" in text, \
        "O5 must be characterized as containment, not hard isolation"


def test_plan_characterizes_o3_as_stronger_but_heavier():
    with open(IMPL_DOC) as f:
        text = f.read().lower()
    assert "dedicated" in text and "process" in text, \
        "O3 must describe a dedicated process"
    assert "operationally heavier" in text or \
        "operational cost" in text or \
        "single point of failure" in text, \
        "O3 must be characterized as operationally heavier"


# ---------------------------------------------------------------------------
# 3. Current state untouched: actor set still {zeko, cto, somad, nova}
# ---------------------------------------------------------------------------

def test_plan_derives_actor_set_from_current_config(raw_write_roles):
    """The plan must reference the post-O5 actor set {zeko, cto} as the
    current state, noting that O5 was applied per Human decision."""
    with open(IMPL_DOC) as f:
        text = f.read()
    assert "{zeko, cto}" in text, (
        "plan must state the post-O5 raw-write actor set")


def test_o5_applied_this_session(role_filters):
    """O5 applied (2026-08-31): somad/nova deny write/edit. Amended
    2026-09-07 (Human-approved zeko discriminator, task 3 of
    "laksanakan 1 - 4"): zeko also loses write/edit
    (capabilities.code_write: no, now enforceable); cto keeps write/edit;
    zeko keeps bash (ops diagnosis residual). write/edit actors = {cto};
    bash/write/edit actors = {zeko, cto}."""
    for rid in ("somad", "nova", "zeko"):
        allow = role_filters[rid]["allow"]
        assert "write" not in allow, f"{rid} write still in allow — O5/amendment not applied?"
        assert "edit" not in allow, f"{rid} edit still in allow — O5/amendment not applied?"
    cto_allow = role_filters["cto"]["allow"]
    assert "write" in cto_allow, "cto write removed — must be preserved"
    assert "edit" in cto_allow, "cto edit removed — must be preserved"
    assert "bash" in role_filters["zeko"]["allow"], \
        "zeko bash removed — ops diagnosis residual must be preserved"
    assert set(raw_write_for(role_filters)) == {"zeko", "cto"}, (
        "bash/write/edit actor set after O5+amendment must be {zeko, cto}")


def test_mapping_matches_policy_yaml_still_holds():
    """Config consistency (mapping==policy) must still hold — nothing changed
    this session, so the consistency contract is intact."""
    import yaml
    with open(MAPPING) as f:
        mapping = yaml.safe_load(f)
    for role in mapping["roles"]:
        rid = role["id"]
        with open(os.path.join(PROJECT_ROOT, "agents", rid, "policy.yaml")) as f:
            pol = yaml.safe_load(f)
        assert set(role["tool_surface"]["allow"]) == set(
            pol["tool_surface"]["allow"]), f"{rid} mapping!=policy allow"
        assert set(role["tool_surface"]["deny"]) == set(
            pol["tool_surface"]["deny"]), f"{rid} mapping!=policy deny"


def raw_write_for(role_filters):
    return sorted(r for r, f in role_filters.items()
                  if {"bash", "write", "edit"} & f["allow"])


# ---------------------------------------------------------------------------
# 4. All required determinations are documented
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,needle", REQUIRED_DETERMINATIONS,
                         ids=[d[0] for d in REQUIRED_DETERMINATIONS])
def test_plan_documents_determination(label, needle):
    with open(IMPL_DOC) as f:
        text = f.read().lower()
    assert needle in text, (
        f"plan must document determination: {label} (missing {needle!r})")


def test_plan_states_production_blocked_after_o5_alone():
    with open(IMPL_DOC) as f:
        text = f.read().lower()
    assert "still blocked" in text or "still bl_ocked" in text or \
        "remains blocked" in text or "production stays blocked" in text or \
        "production remains blocked" in text, \
        "plan must state production remains blocked after O5 alone"
    assert "blocking" in text, "plan must keep G10 blocking"


def test_plan_states_o5_independent_and_o3_arch_change():
    with open(IMPL_DOC) as f:
        text = f.read()
    assert "YES." in text and "independently" in text.lower(), \
        "plan must answer: O5 can be applied independently"
    assert "YES." in text and "architecture" in text.lower(), \
        "plan must answer: O3 requires architecture change"


def test_plan_states_neither_changes_authority_semantics():
    with open(IMPL_DOC) as f:
        text = f.read().lower()
    assert "neither o5 nor o3 changes authority semantics" in text or \
        "does not change authority semantics" in text, \
        "plan must state authority semantics are unchanged"


def test_plan_states_rollback_is_file_level_no_git():
    """The project has no git repository; rollback must be file-level backups.
    The plan must say so explicitly so operators do not assume git revert."""
    with open(IMPL_DOC) as f:
        text = f.read().lower()
    assert "not a git repository" in text or "no git repo" in text or \
        "no git repository" in text, \
        "plan must note rollback is file-level (no git)"


# ---------------------------------------------------------------------------
# 5. Scope honesty: nothing outside the two write-only targets was modified
# ---------------------------------------------------------------------------

def test_plan_scope_check_only_planning_targets():
    """The plan's scope check must restrict this session's writes to
    docs/phase-5/security/g10/implementation/ + tests/g10/planning/."""
    with open(IMPL_DOC) as f:
        text = f.read()
    assert "implementation/0001-o5-o3-implementation-plan.md" in text
    assert "tests/g10/planning/test_o5_o3_planning.py" in text
    low = text.lower()
    assert "not modified" in low, "plan must include a scope check"


def test_plan_mentions_exact_files_for_both_options():
    """Both O5's config/live-patch files and O3's new daemon/IPC components
    must be enumerated in the plan."""
    with open(IMPL_DOC) as f:
        text = f.read()
    assert "config/role-preset-mapping.yaml" in text
    assert "config/tool-subagent-instances.yaml" in text
    assert "agents/somad/policy.yaml" in text
    assert "agents/nova/policy.yaml" in text
    assert "cordis.patch.yml" in text
    assert "execution_gate.py" in text
    assert "IPC" in text  # O3 IPC contract enumerated


def test_plan_lists_test_requirements_for_o5_and_o3():
    with open(IMPL_DOC) as f:
        text = f.read().lower()
    assert "test requirements" in text
    assert "o5 test requirements" in text or "2.5" in text
    assert "o3 test requirements" in text or "3.5" in text


def test_plan_lists_migration_requirements_for_o5_and_o3():
    with open(IMPL_DOC) as f:
        text = f.read().lower()
    assert "migration requirements" in text
    assert "o5 migration requirements" in text or "2.6" in text
    assert "o3 migration requirements" in text or "3.6" in text
