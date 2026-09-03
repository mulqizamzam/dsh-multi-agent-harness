"""Session C — G10: DSH-layer raw file access isolation tests.

These tests document the DSH layer's actual filesystem enforcement:

  1. RAW WRITE / EDIT / BASH mutation inside the workspace root to a
     protected-path mirror → LANDS (DSH layer has NO per-path interception
     within the workspace). This is the G10 residual (R) proven empirically.
  2. Writes OUTSIDE the workspace root → DENIED by the DSH sandbox
     (workspace-root boundary enforcement — hard isolation).
  3. Symlink escape → DENIED (realpath containment).
  4. Sibling-prefix → ALLOWED (the DSH layer does not distinguish it).

The inside-workspace probes (1, 4) are deterministic anywhere (Python file
ops). The outside-workspace probes (2, 3) are deterministic ONLY when the
pytest process itself runs inside the DSH file sandbox (bwrap/Seatbelt
under `workspace-write` mode). Those tests are guarded by the
`sandbox_active` fixture and skip with an explicit reason when the sandbox
is not detected, so the suite stays honest outside the harness.

All probes use a THROWAWAY mirror under `tmp_workspace`; real protected
state (`state/registry/`, `audit/`, `state/projects/`) is never touched.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


# ============================================================================
# 1. Residual: raw DSH filesystem access inside the workspace root is NOT
#    path-gated (the sandbox grants the entire workspace root).
# ============================================================================

def test_raw_write_reaches_protected_mirror(tmp_workspace):
    """RESIDUAL PROVEN OPEN: a raw file write to the protected-path layout
    inside the workspace IS NOT intercepted by the DSH sandbox.

    The DSH sandbox grants the entire workspace root under `workspace-write`;
    it has no per-path allow/deny. The project execution gate intercepts only
    CHANNELED writes (test_project_layer_isolation.py). This raw write
    bypasses the channel and lands.
    """
    target = tmp_workspace / "state" / "registry" / "x.json"
    with open(target, "w") as f:
        f.write('{"forged": true}')
    assert target.exists()
    assert target.read_text() == '{"forged": true}'


def test_raw_bash_mutation_reaches_protected_mirror(tmp_workspace):
    """RESIDUAL: a raw bash mutation (echo/cat/...) to a protected-path
    target inside the workspace lands — the DSH layer has no path-level
    interception for any tool under the same workspace sandbox."""
    target = tmp_workspace / "state" / "registry" / "bash-forged.json"
    subprocess.run(["bash", "-c", f"echo '{{\"bash\": true}}' > {target}"],
                   check=True, capture_output=True)
    assert target.exists()
    assert target.read_text() == '{"bash": true}\n'


def test_raw_edit_semantics_reach_protected_mirror(tmp_workspace):
    """RESIDUAL: the DSH `edit` tool (tool-fs/src/edit.ts) shares the same
    FsSandboxController and per-session sandbox resolution as `write` — it
    has no path-level interception within the workspace. This test emulates
    edit semantics (read-modify-write) on a protected-path mirror to
    document the equivalent residual."""
    target = tmp_workspace / "state" / "registry" / "editable.json"
    target.write_text('{"original": true}')
    # Emulate edit: read, modify, rewrite.
    data = target.read_text()
    data = data.replace('"original": true', '"original": false')
    with open(target, "w") as f:
        f.write(data)
    assert target.exists()
    assert target.read_text() == '{"original": false}'


def test_sibling_prefix_not_misclassified_at_dsh_layer(tmp_workspace):
    """The DSH layer does not treat `state/registry-evil` differently from
    any other workspace path — it's just a path under the workspace root,
    therefore writable. This is a statement about the DSH sandbox's
    root-based containment (no path-level awareness), not about the project
    gate which does classify sibling prefixes correctly (tested in
    test_project_layer_isolation.py)."""
    target = tmp_workspace / "state" / "registry-evil" / "x.json"
    target.write_text('{"sibling": true}')
    assert target.exists()


# ============================================================================
# 2. DSH sandbox boundary: outside-workspace writes are DENIED.
#    These tests are conditional on the DSH sandbox being active.
# ============================================================================

def _require_sandbox(sandbox_active):
    if not sandbox_active:
        pytest.skip("DSH file sandbox not active: outside-write denial "
                    "is not observable from this process")


def test_sandbox_denies_absolute_outside_write(tmp_workspace, sandbox_active):
    """The DSH sandbox (bwrap/Seatbelt under workspace-write) denies writes
    to paths outside the workspace root. Observed marker: 'Read-only file
    system' (EROFS)."""
    _require_sandbox(sandbox_active)
    with pytest.raises(OSError):
        open("/etc/g10-dsh-probe.txt", "w").write("x")


def test_sandbox_denies_traversal_escape(tmp_workspace, sandbox_active):
    """A `../` traversal that escapes the workspace root is denied by the
    sandbox (the workspace root is the bwrap bind mount boundary).

    NOTE: the probe target is the PARENT of the project root — NOT the
    parent of tmp_path, because tmp_path lives under /tmp, which is itself
    a writable root under workspace-write (roots.ts:52-55). Writing to the
    project root's parent is outside every writable root and must fail.
    """
    _require_sandbox(sandbox_active)
    parent = os.path.dirname(PROJECT_ROOT)
    probe = os.path.join(parent, ".g10-traversal-escape")
    try:
        with pytest.raises(OSError):
            open(probe, "w").write("x")
    finally:
        # Clean up if somehow landed (sandbox not active).
        if os.path.exists(probe):
            os.remove(probe)


def test_sandbox_denies_symlink_escape(tmp_workspace, sandbox_active):
    """A symlink inside the workspace pointing to a path outside the
    workspace root is denied on write — the sandbox resolves realpath and
    finds the target outside the writable root set."""
    _require_sandbox(sandbox_active)
    link = tmp_workspace / ".g10-esc-link"
    link.symlink_to("/etc/passwd")
    with pytest.raises(OSError):
        open(link, "w").write("x")


# ============================================================================
# 3. DSH sandbox ALLOWS writes inside the workspace root (boundary check).
# ============================================================================

def test_sandbox_allows_inside_workspace_write(tmp_workspace, sandbox_active):
    """The DSH sandbox allows writes INSIDE the workspace root under
    workspace-write mode (the root is the bwrap bind mount)."""
    _require_sandbox(sandbox_active)
    target = tmp_workspace / ".g10-inside-probe.txt"
    target.write_text("inside")
    assert target.read_text() == "inside"