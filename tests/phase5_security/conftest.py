"""Shared fixtures for the Phase-5 security hardening test suite."""

import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def tmp_workspace(tmp_path):
    """A throwaway workspace with protected-path-shaped directories.

    Mirrors the real `state/registry/` and `audit/` layout so negative tests
    document the residual WITHOUT touching the real project state.
    """
    registry = tmp_path / "state" / "registry"
    audit = tmp_path / "audit"
    state_projects = tmp_path / "state" / "projects"
    for d in (registry, audit, state_projects):
        d.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def role_filters():
    """The D4/D7 tool-surface allow/deny sets from config (read-only)."""
    import yaml
    root = PROJECT_ROOT
    with open(os.path.join(root, "config", "role-preset-mapping.yaml")) as f:
        mapping = yaml.safe_load(f)
    roles = {}
    for role in mapping["roles"]:
        roles[role["id"]] = {
            "allow": set(role["tool_surface"]["allow"]),
            "deny": set(role["tool_surface"]["deny"]),
        }
    return roles


@pytest.fixture
def bash_capable_roles(role_filters):
    """Roles whose allow set includes `bash` (raw-shell capability)."""
    return sorted(r for r, f in role_filters.items() if "bash" in f["allow"])


@pytest.fixture
def readonly_roles(role_filters):
    """Roles whose deny set excludes write/edit/bash."""
    return sorted(r for r, f in role_filters.items()
                  if "bash" in f["deny"] and "write" in f["deny"]
                  and "edit" in f["deny"])
