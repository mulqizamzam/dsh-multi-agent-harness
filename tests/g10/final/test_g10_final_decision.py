"""Session A — G10 final mitigation analysis: honesty guards.

These tests assert the G10 final decision document and the surrounding
evidence are honest, consistent, and make no closure claim. They
complement the existing Session C G10 test suite (tests/g10/).

Invariants under test:
  1. The final decision document exists and states G10 OPEN.
  2. The final decision document does NOT claim closure.
  3. The upstream DSH requirement (O4) is documented — per-agent sandbox
     root or per-path allow/deny on filesystem tools.
  4. The residual actor set is derived from the CURRENT config (not stale).
  5. DSH version is still pinned to 0.1.1-rc.2.
  6. The existing Session C G10 tests still pass (consistency gate).
  7. The recommended mitigation order is documented (O5 → O3 → O4).
  8. Production impact states G10 blocks production.
"""

import os
import sys

import pytest

_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(_FILE_DIR))))

# Paths: test at tests/g10/final/ -> project root is 3 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(_FILE_DIR)))
FINAL_DOC = os.path.join(PROJECT_ROOT, "docs", "phase-5", "security",
                          "g10", "final", "0001-g10-final-mitigation-analysis.md")
DSH_CHECKOUT = "/home/administrator/deepseek-harness"
G10_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ===========================================================================
# 1. Document existence and honesty
# ===========================================================================

def test_final_document_exists():
    assert os.path.isfile(FINAL_DOC), (
        f"G10 final decision document missing at {FINAL_DOC}")


def test_final_document_states_g10_open():
    with open(FINAL_DOC) as f:
        text = f.read()
    assert "G10 remains OPEN" in text, "document must state G10 OPEN"
    assert "BLOCKING" in text, "document must state G10 BLOCKING"
    assert "no closure claim" in text.lower() or \
        "no closure of prevention claimed" in text.lower() or \
        "not a closure claim" in text.lower(), (
            "document must not claim closure")


def test_upstream_requirement_documented():
    with open(FINAL_DOC) as f:
        text = f.read()
    # The upstream requirement must mention per-agent sandbox root or
    # per-path allow/deny.
    assert "per-agent sandbox root" in text or \
        "per-agent/per-delegation sandbox root" in text, (
            "upstream requirement must mention per-agent sandbox root")
    assert "per-path allow/deny" in text or \
        "path-level restriction" in text, (
            "upstream requirement must mention per-path allow/deny")


def test_recommended_mitigation_order_documented():
    with open(FINAL_DOC) as f:
        text = f.read()
    # The recommended stages must mention O5, O3, O4 in that order.
    o5_idx = text.find("O5")
    o3_idx = text.find("O3")
    o4_idx = text.find("O4")
    # All three should be present and in the right order.
    assert o5_idx >= 0 and o3_idx >= 0 and o4_idx >= 0, (
        "O5, O3, O4 must all be mentioned"
    )
    # O5 should come before O3, O3 before O4 in the document.
    assert o5_idx < o3_idx, "O5 must precede O3 (recommended order)"
    assert o3_idx < o4_idx, "O3 must precede O4 (recommended order)"


def test_production_impact_blocks_production():
    with open(FINAL_DOC) as f:
        text = f.read()
    assert "BLOCKED" in text or "blocks production" in text.lower(), (
        "production impact must state that G10 blocks production")


# ===========================================================================
# 2. DSH version pin (re-verified)
# ===========================================================================

def test_dsh_version_pin():
    if not os.path.isdir(DSH_CHECKOUT):
        pytest.skip(f"DSH checkout not found at {DSH_CHECKOUT}")
    import json
    pkg = os.path.join(DSH_CHECKOUT, "package.json")
    with open(pkg) as f:
        v = json.load(f).get("version", "")
    # Pin moved from 0.1.1-rc.2 after the 2026-10-09 full-suite
    # re-verification against the running checkout (README policy: later
    # releases require re-verification). Moved from 0.2.0-rc.2 to 0.2.1-rc.2
    # on the 0.2.1-rc.2 port.
    assert v == "0.2.1-rc.2", f"Expected 0.2.1-rc.2, got {v}"


# ===========================================================================
# 3. Actor set (current config, unchanged)
# ===========================================================================

def test_actor_set_derived_from_current_config():
    """The raw-write actor set must match the current config."""
    import yaml
    mapping_path = os.path.join(PROJECT_ROOT, "config",
                                "role-preset-mapping.yaml")
    with open(mapping_path) as f:
        mapping = yaml.safe_load(f)
    raw_write = set()
    for role in mapping["roles"]:
        allow = set(role["tool_surface"]["allow"])
        if {"bash", "write", "edit"} & allow:
            raw_write.add(role["id"])
    assert raw_write == {"zeko", "cto"}, (
        f"Unexpected raw-write actor set: {raw_write}"
    )


def test_readonly_roles_unchanged():
    import yaml
    mapping_path = os.path.join(PROJECT_ROOT, "config",
                                "role-preset-mapping.yaml")
    with open(mapping_path) as f:
        mapping = yaml.safe_load(f)
    for role in mapping["roles"]:
        deny = set(role["tool_surface"]["deny"])
        if role["id"] in ("badsector", "cfo", "kai"):
            assert "bash" in deny and "write" in deny and "edit" in deny, (
                f"Read-only role {role['id']} missing raw-write denial")


# ===========================================================================
# 4. Consistency gate: existing Session C G10 tests still pass
# ===========================================================================

def test_existing_g10_tests_still_pass():
    """Re-run the existing Session C G10 test suite to verify no regression
    introduced by the final analysis.

    Only the pre-existing Session C test files are targeted (NOT this
    directory, which would recurse). The suite is expected to pass
    (39 tests as of Session C).
    """
    import subprocess
    python = sys.executable
    session_c_files = [
        os.path.join(G10_PARENT_DIR, "test_dsh_capability.py"),
        os.path.join(G10_PARENT_DIR, "test_dsh_layer_isolation.py"),
        os.path.join(G10_PARENT_DIR, "test_project_layer_isolation.py"),
        os.path.join(G10_PARENT_DIR, "test_role_restrictions.py"),
    ]
    proc = subprocess.run(
        [python, "-m", "pytest", *session_c_files, "-q", "--tb=short"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
        timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"Existing G10 tests failed (rc={proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    # Also check there are no failures in the output.
    assert "failed" not in proc.stdout.lower(), (
        f"Existing G10 tests show failures:\n{proc.stdout}"
    )


# ===========================================================================
# 5. Honesty: no role-boundary change was applied
# ===========================================================================

def test_role_boundaries_not_changed():
    """The final decision document must NOT claim any role boundary was
    changed. O5 is a recommendation, not an applied change."""
    with open(FINAL_DOC) as f:
        text = f.read().lower()
    # The document should say "recommended" or "decision" rather than
    # "applied" or "changed" for O5.
    assert "human decision" in text or "recommended" in text, (
        "document must frame O5 as a Human decision/recommendation, "
        "not an applied change"
    )