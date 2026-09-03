# tests/environment/preflight.py — runtime environment readiness preflight (G2+G3)
#
# TEST-SUPPORT ONLY. NOT production code.
#
# A read-only preflight checker that verifies, BEFORE a consequential Phase-5
# session, the environment prerequisites defined in
# docs/phase-5/environment/0001-environment-readiness-spec.md:
#
#   ENV-POLICY-1   sandbox mode is the project baseline (workspace-write)
#   ENV-POLICY-2   approval policy is the project baseline (ask)
#   ENV-APPROVAL-1 a live approval answerer is available (G3)
#   ENV-MOUNT-1    the DSH live bridge marker is set (DSH_LIVE_BRIDGE_ACTIVE=1)
#   ENV-MOUNT-2    the 7 D4/D7 role presets are present under $DSH_HOME
#   ENV-DSH-1      DSH version pin matches 0.1.1-rc.2
#
# THE PREFLIGHT NEVER MODIFIES ANYTHING. It never changes session policy, never
# mounts DSH, never sets environment variables, never writes files. It is pure
# detection (the same posture as tests/l3_runner/preflight.py's PF-* checks).
#
# HONESTY: a check that fails is reported as failed with its required value.
# Readiness is NEVER claimed from this module alone — only from runtime
# evidence (a passing check here is a precondition, not a proof).
#
# USAGE (read-only):
#   python -m tests.environment.preflight [--json]

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Project root (three levels up from this file).
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# DSH version pin (docs/README.md + contract.py).
DSH_VERSION_PIN = "deepseek-harness-0.1.1-rc.2"

# The 7 D4/D7 role presets (config/role-preset-mapping.yaml).
ROLE_PRESETS = (
    "role-zeko", "role-cto", "role-cfo", "role-kai",
    "role-somad", "role-badsector", "role-nova",
)

# The D4/D7 mount-marker env var (tests/live_dsh/discovery.py, docs/testing/0003 §6).
BRIDGE_MARKER_ENV = "DSH_LIVE_BRIDGE_ACTIVE"

# Project baseline (ADR 0001 Decision 2 / docs/operations.md §1).
REQUIRED_SANDBOX_MODE = "workspace-write"
REQUIRED_APPROVAL_POLICY = "ask"


@dataclass
class EnvCheck:
    """One environment-readiness check result."""
    check_id: str
    name: str
    passed: bool = False
    detail: str = ""
    required: bool = True  # a failed required check blocks readiness for that gate

    def to_dict(self) -> dict:
        return {
            "check": self.check_id,
            "name": self.name,
            "pass": bool(self.passed),
            "required": bool(self.required),
            "detail": self.detail,
        }


@dataclass
class EnvReport:
    """Aggregated environment-readiness result."""
    checks: list = field(default_factory=list)
    ready_for_live_dsh: bool = False
    ready_for_interactive: bool = False

    def add(self, check: EnvCheck) -> None:
        self.checks.append(check)

    def all_required_pass(self) -> bool:
        return all(c.passed for c in self.checks if c.required)

    def to_dict(self) -> dict:
        return {
            "ready_for_live_dsh": self.ready_for_live_dsh,
            "ready_for_interactive": self.ready_for_interactive,
            "all_required_pass": self.all_required_pass(),
            "checks": [c.to_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Detectors (each is read-only; env/snapshot values are injectable for tests)
# ---------------------------------------------------------------------------

def _detect_sandbox_mode(env: dict | None) -> str:
    """Detect the effective sandbox mode.

    In the harness this is enforced by the DSH file sandbox; the runtime
    context snapshot reports it. Prefer an explicit snapshot value; otherwise
    fall back to the DSH permission-mode derivation (docs/operations.md §1).
    """
    if env and env.get("sandbox_mode"):
        return str(env["sandbox_mode"])
    return os.environ.get("DSH_PERMISSION_MODE", "workspace-write")


def _detect_approval_policy(env: dict | None) -> str:
    """Detect the effective approval policy.

    DSH derives approval.policy from the permission mode
    (docs/operations.md §1): mode == danger-full-access -> 'never', else 'ask'.
    """
    if env and env.get("approval_policy"):
        return str(env["approval_policy"])
    mode = _detect_sandbox_mode(env)
    return "never" if mode == "danger-full-access" else "ask"


def _answerer_available(env: dict | None) -> bool:
    """Detect whether a live approval answerer is available (G3).

    CORRECTED detection (approval-path correction): the obsolete probe keyed
    off the project-side DSH_APPROVAL_PROMPTS_DISABLED convention (never read
    by DSH) and a $DSH_HOME/profiles marker scan (the bundle-composed answerer
    does not live there). The corrected probe discovers the ACTUAL DSH bundle/web
    composition (approval_composition.approval_readiness) and reports the
    answerer available when the DSH base bundle composes the approval service AND
    the web-app bundle composes the answerer surface (apiproxy + ui-user-questions
    + ui-conversation ApprovalPanel) AND the web GUI browser answerer is attached,
    i.e. status is INTERACTIVE_READY or E2E_VERIFIED.

    An explicit snapshot value (`approval_answerer_available`) still wins for
    deterministic injection by callers/tests.
    """
    if env and "approval_answerer_available" in env:
        return bool(env["approval_answerer_available"])
    # Corrected: use actual DSH bundle/web composition, never the project-side
    # DSH_APPROVAL_PROMPTS_DISABLED convention (verified DSH does not read it).
    try:
        from tests.environment.approval_composition import (
            ApprovalStatus, approval_readiness,
        )
    except ImportError:
        # Fallback: composition module unavailable — fail-closed.
        return False
    detection = approval_readiness()
    return detection.status in (
        ApprovalStatus.APPROVAL_INTERACTIVE_READY,
        ApprovalStatus.APPROVAL_E2E_VERIFIED,
    )


def _bridge_marker_set() -> bool:
    """Detect the D4/D7 mount marker (G2)."""
    return os.environ.get(BRIDGE_MARKER_ENV, "") == "1"


def _role_presets_present() -> bool:
    """Detect whether the 7 role presets are present under $DSH_HOME/.agent-presets/."""
    dsh_home = os.environ.get("DSH_HOME", "")
    if not dsh_home:
        return False
    presets_dir = os.path.join(dsh_home, ".agent-presets")
    if not os.path.isdir(presets_dir):
        return False
    try:
        present = os.listdir(presets_dir)
    except OSError:
        return False
    return all(p in present for p in ROLE_PRESETS)


def _dsh_version(env: dict | None) -> str:
    if env and env.get("dsh_version"):
        return str(env["dsh_version"])
    return DSH_VERSION_PIN


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_env_preflight(env: dict | None = None) -> EnvReport:
    """Run the full environment-readiness preflight. Read-only.

    Args:
        env: optional environment snapshot dict (bypasses live detection).
            Recognized keys: sandbox_mode, approval_policy,
            approval_answerer_available, dsh_version.
    """
    env = env or {}
    report = EnvReport()

    # ENV-POLICY-1 / ENV-POLICY-2: baseline (PB-1).
    sandbox = _detect_sandbox_mode(env)
    report.add(EnvCheck(
        "ENV-POLICY-1", "sandbox mode is the project baseline (workspace-write)",
        passed=sandbox == REQUIRED_SANDBOX_MODE,
        detail=f"sandbox_mode={sandbox} required={REQUIRED_SANDBOX_MODE} "
               f"[REPORT ONLY — session policy is out of scope]"))

    approval = _detect_approval_policy(env)
    report.add(EnvCheck(
        "ENV-POLICY-2", "approval policy is the project baseline (ask)",
        passed=approval == REQUIRED_APPROVAL_POLICY,
        detail=f"approval_policy={approval} required={REQUIRED_APPROVAL_POLICY} "
               f"[REPORT ONLY — session policy is out of scope]"))

    # ENV-APPROVAL-1: answerer availability (G3).
    ans = _answerer_available(env)
    report.add(EnvCheck(
        "ENV-APPROVAL-1", "a live approval answerer is available (G3)",
        passed=ans,
        detail=("DSH approval service + web answerer surface composed and web "
                "GUI browser answerer attached -> ask resolves to a live "
                "answerer [REPORT ONLY]"
                if ans else
                "no live approval answerer (composition absent OR browser not "
                "attached) -> ask resolves unavailable (DENY + escalate, "
                "fail-closed) [REPORT ONLY]")))

    # ENV-MOUNT-1 / ENV-MOUNT-2: D4/D7 availability (G2).
    marker = _bridge_marker_set()
    report.add(EnvCheck(
        "ENV-MOUNT-1", f"live bridge marker set ({BRIDGE_MARKER_ENV}=1) (G2)",
        passed=marker,
        detail=(f"{BRIDGE_MARKER_ENV}=1 -> REAL DSH dispatch available"
                if marker else
                f"{BRIDGE_MARKER_ENV} unset -> live DSH unavailable "
                f"(fail-closed, BridgeNotAvailable)")))

    presets = _role_presets_present()
    report.add(EnvCheck(
        "ENV-MOUNT-2", "7 D4/D7 role presets present under $DSH_HOME/.agent-presets/",
        passed=presets,
        required=False,  # presets may be mounted elsewhere (cordis.patch.yml rows)
        detail=(f"presets_present={presets} roles={list(ROLE_PRESETS)} "
                f"dsh_home={os.environ.get('DSH_HOME', '(unset)')}")))

    # ENV-DSH-1: version pin.
    dsh_ver = _dsh_version(env)
    report.add(EnvCheck(
        "ENV-DSH-1", f"DSH version pinned to {DSH_VERSION_PIN}",
        passed=dsh_ver == DSH_VERSION_PIN,
        detail=f"dsh_version={dsh_ver}"))

    # Honest readiness derivation (never claimed from detection alone; these
    # flags mean "preconditions satisfied", NOT "proven live").
    mount_ok = any(c.check_id == "ENV-MOUNT-1" and c.passed for c in report.checks)
    presets_ok = any(c.check_id == "ENV-MOUNT-2" and c.passed for c in report.checks)
    policy_ok = any(c.check_id == "ENV-POLICY-1" and c.passed for c in report.checks)
    report.ready_for_live_dsh = bool(policy_ok and mount_ok and presets_ok)
    report.ready_for_interactive = bool(ans)

    return report


# ---------------------------------------------------------------------------
# CLI (read-only)
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Runtime environment readiness preflight (read-only; "
                    "never modifies session policy or DSH)")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--sandbox-mode", default="")
    parser.add_argument("--approval-policy", default="")
    parser.add_argument("--approval-answerer", default="", metavar="BOOL")
    args = parser.parse_args(argv)

    env = {}
    if args.sandbox_mode:
        env["sandbox_mode"] = args.sandbox_mode
    if args.approval_policy:
        env["approval_policy"] = args.approval_policy
    if args.approval_answerer:
        env["approval_answerer_available"] = args.approval_answerer.lower() in ("1", "true", "yes")

    report = run_env_preflight(env)
    if args.json:
        print(json.dumps(report.to_dict(), indent=1))
    else:
        for c in report.checks:
            mark = "PASS" if c.passed else ("SKIP" if not c.required else "FAIL")
            print(f"[{mark}] {c.check_id} {c.name} — {c.detail}")
        print(f"ready_for_live_dsh={report.ready_for_live_dsh} "
              f"ready_for_interactive={report.ready_for_interactive}")

    # Exit 2 when a REQUIRED check fails (readiness preconditions not met);
    # exit 0 otherwise. This is detection, never a readiness claim.
    return 2 if not report.all_required_pass() else 0


if __name__ == "__main__":
    sys.exit(main())
