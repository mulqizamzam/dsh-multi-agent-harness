"""Session C — G10 DSH hard filesystem isolation: shared fixtures.

The fixtures here mirror the protected-path layout in a THROWAWAY temp
workspace so the tests document the residual and the enforcement WITHOUT
touching real `state/registry/`, `audit/`, or `state/projects/` (same
convention as `tests/phase5_security/conftest.py`).

Two classes of tests consume these:

1. Project-layer (L1 gate) tests — always deterministic, run anywhere:
   the execution gate's path classification is pure code.
2. DSH-layer boundary tests — deterministic ONLY when the pytest process
   itself runs inside the DSH file sandbox (i.e. invoked via a sandboxed
   `bash`/exec tool under `workspace-write`). Those tests assert the
   sandbox's own boundary behavior (outside-write EROFS denial) and are
   skipped with an explicit reason when the process is NOT sandboxed, so
   the suite stays honest outside the harness.
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# DSH source checkout (read-only capability evidence). Resolved once.
DSH_CHECKOUT = "/home/administrator/deepseek-harness"


@pytest.fixture
def tmp_workspace(tmp_path):
    """A throwaway workspace mirroring the real protected-path layout.

    Mirrors `state/registry/`, `audit/`, `state/projects/`, plus a
    sibling-prefix decoy (`state/registry-evil/`) so prefix-confusion
    behavior is testable without touching the real project state.
    """
    registry = tmp_path / "state" / "registry"
    audit = tmp_path / "audit"
    state_projects = tmp_path / "state" / "projects"
    sibling = tmp_path / "state" / "registry-evil"
    for d in (registry, audit, state_projects, sibling):
        d.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def role_filters():
    """The D4/D7 per-role toolFilter allow/deny sets from config (read-only)."""
    import yaml
    with open(os.path.join(PROJECT_ROOT, "config",
                           "role-preset-mapping.yaml")) as f:
        mapping = yaml.safe_load(f)
    roles = {}
    for role in mapping["roles"]:
        roles[role["id"]] = {
            "allow": set(role["tool_filter"]["allow"]),
            "deny": set(role["tool_filter"]["deny"]),
        }
    return roles


@pytest.fixture
def raw_write_roles(role_filters):
    """Roles that can mutate the filesystem via raw DSH tools.

    A role is raw-write-capable when `bash` OR `write`/`edit` is in its
    toolFilter allow set (any one of those tools can carry a raw write that
    bypasses the project channel). See G10 residual proof §1.
    """
    return sorted(
        r for r, f in role_filters.items()
        if {"bash", "write", "edit"} & f["allow"]
    )


@pytest.fixture
def readonly_roles(role_filters):
    """Roles whose deny set excludes bash/write/edit entirely."""
    return sorted(r for r, f in role_filters.items()
                  if {"bash", "write", "edit"} <= f["deny"])


@pytest.fixture
def dsh_checkout():
    """The read-only DSH source checkout, or None when unavailable."""
    if os.path.isdir(DSH_CHECKOUT):
        return DSH_CHECKOUT
    return None


def _sandbox_active() -> bool:
    """Detect whether THIS pytest process runs inside the DSH file sandbox.

    Probe: a write outside the workspace root must fail with a read-only /
    permission error under `workspace-write`. We use a harmless throwaway
    path under the host temp area that is NOT a platform writable root
    (tmpdir() IS a writable root under workspace-write, so probe the
    workspace PARENT instead). We attempt a mkdir in the parent directory of
    the project root; if it fails with EROFS/EACCES the sandbox is active.
    """
    parent = os.path.dirname(PROJECT_ROOT)
    probe = os.path.join(parent, ".g10-sandbox-probe")
    try:
        os.mkdir(probe)
    except OSError:
        return True  # blocked -> sandbox active (or read-only parent)
    else:
        # Write landed: either no sandbox, or the parent is writable.
        os.rmdir(probe)
        return False


@pytest.fixture
def sandbox_active():
    """True when the test process is confined by the DSH file sandbox.

    DSH-layer boundary tests depend on this: the sandbox's outside-write
    denial is only observable from inside the sandbox. Outside the harness
    the probe returns False and the boundary tests skip with a reason.
    """
    return _sandbox_active()
