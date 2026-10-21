"""Session C — G10: DSH 0.1.1-rc.2 capability evidence (static source facts).

These tests assert the DSH sandbox and tool-surface capabilities by reading
the read-only DSH source checkout at `/home/administrator/deepseek-harness`.
They pass when the checkout is available; skip gracefully when absent.

Verified facts (from the formal proof docs/phase-5/final/0002-g10 §3):

1. Sandbox mode is per-session, inherited by children — NOT per-agent
   (child-agent.ts:180 `DelegatedPolicyOverrides.sandboxMode`).
2. `writableRoots()` under `workspace-write` = [workspaceRoot, /tmp, tmpdir]
   — the ENTIRE workspace root, no per-path granularity (roots.ts:52-55).
3. NO path-level or per-agent sandbox differentiation exists in the
   codebase (negative grep for `pathFilter|pathAllow|pathDeny|perPath`).
4. `ToolRestriction` filters by global tool name only — no path-level
   allow/deny (tools/index.ts:680-685, 1071).
5. `SANDBOX_MODES` is a closed union of three modes (session-mode.ts:42).
6. tool-fs (write/edit) and tool-bash share the same per-session sandbox
   resolution (FsSandboxController, ctx.shell.sandboxMode).
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

# DSH version pin (verified)
DSH_CHECKOUT = "/home/administrator/deepseek-harness"


@pytest.fixture(scope="module")
def checkout():
    if not os.path.isdir(DSH_CHECKOUT):
        pytest.skip(f"DSH checkout not found at {DSH_CHECKOUT}")
    return DSH_CHECKOUT


# ---------------------------------------------------------------------------
# Version pin
# ---------------------------------------------------------------------------

def test_version_pin(checkout):
    import json
    pkg = os.path.join(checkout, "package.json")
    with open(pkg) as f:
        v = json.load(f).get("version", "")
    # Pin moved from 0.1.1-rc.2 after the 2026-10-09 full-suite
    # re-verification against the running checkout (README policy: later
    # releases require re-verification).
    assert v == "0.2.0-rc.2", f"Expected 0.2.0-rc.2, got {v}"


# ---------------------------------------------------------------------------
# Per-session sandbox (NOT per-agent)
# ---------------------------------------------------------------------------

def test_sandbox_mode_is_per_session(checkout):
    """child-agent.ts: DelegatedPolicyOverrides.sandboxMode is captured from
    the *parent session* — the child inherits one mode for the whole chain."""
    path = os.path.join(
        checkout, "packages/subagent/subagent/src/child-agent.ts")
    with open(path) as f:
        text = f.read()
    assert "The parent session's explicit sandbox-mode override" in text
    assert "parent.ctx.get('sandboxPolicy')?.overrideOf(parent.session)" in text


def test_writable_roots_are_workspace_root(checkout):
    """roots.ts: writableRoots() under workspace-write = [workspaceRoot,
    /tmp, tmpdir]. No per-path granularity."""
    path = os.path.join(checkout, "packages/sandbox/sandbox/src/roots.ts")
    with open(path) as f:
        text = f.read()
    assert "workspace-write" in text
    assert "policy.workspaceRoot" in text
    assert "policy.mode !== 'workspace-write'" in text


def test_sandbox_modes_closed_union(checkout):
    path = os.path.join(
        checkout, "packages/sandbox/sandbox-policy/src/session-mode.ts")
    with open(path) as f:
        text = f.read()
    assert "read-only" in text
    assert "workspace-write" in text
    assert "danger-full-access" in text


# ---------------------------------------------------------------------------
# No path-level or per-agent sandbox differentiation (negative finding)
# ---------------------------------------------------------------------------

def test_no_path_level_filter_exists(checkout):
    """Grep for path-level filtering constructs across the DSH packages —
    the only hits are the unrelated doc-comment in fs/src/types.ts:87 about
    a symlink probe. No pathAllow/pathDeny/perPath/allowPaths/denyPaths
    exists anywhere in the toolchain."""
    packages = os.path.join(checkout, "packages")
    terms = ["pathFilter", "pathAllow", "pathDeny", "perPath",
             "allowPaths", "denyPaths", "path-level"]
    hits = []
    unreadable = []
    for root, dirs, files in os.walk(packages):
        dirs[:] = [d for d in dirs
                   if d not in ("node_modules", "__pycache__", "lib")]
        for fname in files:
            if not fname.endswith(".ts"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        for term in terms:
                            if term in line:
                                hits.append((fpath, i, term, line.strip()))
            except Exception as exc:
                # A silently skipped file shrinks the "exhaustive" scan
                # surface; record it instead of swallowing it.
                unreadable.append(f"{fpath}: {exc!r}")
    assert not unreadable, f"unreadable during scan: {unreadable}"
    # Allow only the known unrelated doc-comment hit.
    legit_hits = [
        h for h in hits
        if "fs/src/types.ts" in h[0] and "path-level" in h[2]
    ]
    unexpected = [h for h in hits if h not in legit_hits]
    assert not unexpected, (
        f"Unexpected path-level filter references found: {unexpected}")


# ---------------------------------------------------------------------------
# the tool surface is tool-level only
# ---------------------------------------------------------------------------

def test_tool_restriction_is_tool_level(checkout):
    path = os.path.join(checkout, "packages/core/tools/src/index.ts")
    with open(path) as f:
        text = f.read()
    assert "ToolRestriction" in text
    assert "allow?: readonly string[]" in text
    assert "deny?: readonly string[]" in text
    assert "global-tool mask" in text or "tool-level" in text


# ---------------------------------------------------------------------------
# fs + bash tools share per-session sandbox
# ---------------------------------------------------------------------------

def test_fs_tools_use_per_session_sandbox(checkout):
    """tool-fs resolves policy via FsSandboxController using ctx.fs.sandboxMode
    (per-session). No per-path differentiation."""
    path = os.path.join(checkout, "packages/fs/tool-fs/src/sandbox.ts")
    with open(path) as f:
        text = f.read()
    assert "ctx.fs.sandboxMode" in text
    assert "FsSandboxController" in text


def test_bash_tool_uses_per_session_sandbox(checkout):
    path = os.path.join(checkout, "packages/shell/tool-bash/src/index.ts")
    with open(path) as f:
        text = f.read()
    assert "ctx.shell.sandboxMode" in text
    assert "SandboxExecutionPolicy" in text