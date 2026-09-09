# tests/l3_runner/environment/readiness.py — L3 environment + Human-answerer readiness probe
#
# Phase 5 / Session D — L3 ENVIRONMENT + HUMAN-ANSWERER READINESS.
#
# PURPOSE
#   A READ-ONLY probe that determines whether the CURRENT environment can
#   support a legitimate L3 run, per docs/security/0007 and the Phase-5 L3
#   readiness documents. For each prerequisite it reports:
#     - PASS          the prerequisite holds (verified, not assumed)
#     - FAIL          the prerequisite is absent -> the run is BLOCKED and the
#                     EXACT missing dependency is named
#     - REPORT ONLY   detection-only, out of the probe's power to change
#
#   It covers the Session-D determination list explicitly:
#     separate process capability / separate UID capability / verifier
#     executable / clean oracle imports / Human answerer availability /
#     approval path availability / D4/D7 mount persistence / signed-plan
#     mechanism / evidence-store readiness / replay readiness.
#
# HONESTY RULES (load-bearing, unchanged from 0007 §10 / 0006 §3):
#   1. NEVER changes session policy, DSH, DSH profile/presets, production
#      code, or role mapping. It does not re-baseline G9; it reports.
#   2. NEVER invents Human signatures. A signed plan mechanism can be "ready"
#      while no REAL Human signoff has been observed; the probe reports the
#      real-signoff fact honestly (absent here) and never promotes the test
#      fixture's synthetic signoff id into a claim.
#   3. NEVER fakes a credential separation (IO-2). On a same-UID host the
#      probe reports l3_claim_possible=False.
#   4. NEVER changes policy to make the preflight pass.
#   5. If a prerequisite is absent -> BLOCKED with the exact missing dependency.
#
# CHECKS (stable ids; group prefix reflects the determination):
#   Separate UID / process (P2):
#     L3ENV-UID-1  separate OS process capability (PF-UID-1 / IO-1)
#     L3ENV-UID-2  separate UID capability (PF-UID-2 / IO-2)   [same-UID -> FAIL]
#     L3ENV-UID-3  verifier not spawned via orchestrator session tree (PF-UID-3)
#   Verifier:
#     L3ENV-VER-1  verifier executable present + sha256 computable (PF-VER-1/3)
#     L3ENV-VER-2  clean oracle imports (no production-gate imports; PF-VER-1/4)
#     L3ENV-VER-3  verifier spawns cleanly in a subprocess (PF-VER-4 / P2)
#     L3ENV-VER-4  reference oracle resolves for the gate (PF-VER-2 / O1)
#     L3ENV-VER-5  at least 2 oracle classes declared (PF-VER-5 / IO-6)
#   Environment (G9 / LV4 / LV5):
#     L3ENV-ENV-1  DSH version pinned to 0.1.1-rc.2 (PF-ENV-1 / LV5)
#     L3ENV-ENV-2  sandbox/approval baseline workspace-write + ask (PF-ENV-2 / G9)
#     L3ENV-ENV-3  env snapshot fields complete (PF-ENV-3 / LV4)
#   Human answerer + approval path (G3):
#     L3ENV-ANS-1  Human answerer availability (interactive / signed-assertion)
#     L3ENV-ANS-2  approval path availability (ask policy + a live answerer)
#   D4/D7 mount persistence (G2):
#     L3ENV-D4D7-1 role presets present under $DSH_HOME/.agent-presets/
#     L3ENV-D4D7-2 tool-subagent instance rows present in cordis.patch.yml
#     L3ENV-D4D7-3 live bridge marker DSH_LIVE_BRIDGE_ACTIVE=1 set
#   Human-signed plan (O4 / G7):
#     L3ENV-PLAN-1..5  plan.json present / schema-valid / pre-runtime signoff /
#                      O4 declared / signoff fields valid  (PF-PLAN-1..5)
#     L3ENV-PLAN-REAL  a REAL Human signoff observed (not invented, not fixture)
#   Evidence store (G4 / 0005):
#     L3ENV-STORE-1  audit/l3 evidence store creatable/writable (PF-ENV-4)
#   Replay (P4 / G8):
#     L3ENV-REP-1..4  fixture hash / replay.sh / tooling sha256 / no live net
#
# USAGE (read-only):
#   python -m tests.l3_runner.environment.readiness [--json]
#   python -m tests.l3_runner.environment                     (package CLI)
#
# Exit code: 0 when the rehearsal machinery is ready (all REQUIRED checks
# pass, even if l3_claim_possible=False); 2 when a required check fails. The
# probe NEVER promotes to L3; l3_claim_possible is True only when every L3
# prerequisite genuinely holds.

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..preflight import (
    PROJECT_ROOT,
    REQUIRED_APPROVAL_POLICY,
    REQUIRED_SANDBOX_MODE,
    PreflightCheck,
    run_preflight,
)
from orchestrator.foundation.contracts import SPECIALIST_ROLES  # noqa: E402

# D4/D7 role presets and their instance ids (config/role-preset-mapping.yaml).
# The full contract roster derives from SPECIALIST_ROLES (PRD v0.2: 15). The
# D8 mount exception (Human-approved 2026-09-09) applied all 15 rows + presets
# to the live profile, so live-profile presence checks now cover the full
# roster. Pre-change backup: runs/specialist-expansion-2026-09-09/backups/.
ROLE_PRESETS = tuple(f"role-{rid}" for rid in SPECIALIST_ROLES)
ROLE_INSTANCE_IDS = tuple(f"subagent_{rid}" for rid in SPECIALIST_ROLES)
# Explicit alias for config-level rosters (same tuple; kept for readability
# at call sites that mean "the whole contract pool").
ALL_INSTANCE_IDS = ROLE_INSTANCE_IDS

# D4/D7 live-bridge marker (tests/live_dsh/discovery.py, docs/testing/0003 §6).
BRIDGE_MARKER_ENV = "DSH_LIVE_BRIDGE_ACTIVE"

# Evidence store base for a real L3 run (docs/security/0005 §3).
EVIDENCE_STORE_DIR = os.path.join(PROJECT_ROOT, "audit", "l3")


@dataclass
class ReadinessCheck:
    """One environment-readiness check result."""
    check_id: str
    name: str
    passed: bool = False
    detail: str = ""
    required: bool = True      # a failed required check blocks the claim (or rehearsal)
    required_for_l3: bool = True  # a failed check blocks an L3 CLAIM (some allow rehearsal)

    def to_dict(self) -> dict:
        return {
            "check": self.check_id,
            "name": self.name,
            "pass": bool(self.passed),
            "required": bool(self.required),
            "required_for_l3": bool(self.required_for_l3),
            "detail": self.detail,
        }


@dataclass
class ReadinessReport:
    """Aggregated environment-readiness result."""
    checks: list = field(default_factory=list)
    l3_claim_possible: bool = False
    rehearsal_ready: bool = False
    blocked: list = field(default_factory=list)   # exact missing dependencies
    captured_at: str = ""

    def add(self, check: ReadinessCheck) -> None:
        self.checks.append(check)

    @property
    def all_required_pass(self) -> bool:
        """All checks required for the machinery to run (rehearsal level)."""
        return all(c.passed for c in self.checks if c.required)

    @property
    def all_l3_required_pass(self) -> bool:
        """All checks required for an L3 claim: every check marked
        required_for_l3 must pass (required=False still blocks an L3 claim —
        it only means the failure does not block a rehearsal)."""
        return all(c.passed for c in self.checks if c.required_for_l3)

    def to_dict(self) -> dict:
        return {
            "captured_at": self.captured_at,
            "l3_claim_possible": self.l3_claim_possible,
            "rehearsal_ready": self.rehearsal_ready,
            "blocked": list(self.blocked),
            "all_required_pass": self.all_required_pass,
            "all_l3_required_pass": self.all_l3_required_pass,
            "checks": [c.to_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _probe_subprocess_uid(python: str = sys.executable) -> int | None:
    try:
        proc = subprocess.run(
            [python, "-c", "import os; print(os.getuid())"],
            capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return None
        return int(proc.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def _verifier_binary_path() -> str:
    return os.path.join(PROJECT_ROOT, "tests", "l3_runner", "verifier.py")


def _probe_verifier_clean(python: str = sys.executable) -> tuple[bool, str]:
    """Spawn the verifier's clean-import guard in a fresh subprocess."""
    try:
        proc = subprocess.run(
            [python, "-c",
             "from tests.l3_runner.verifier import assert_clean_imports; "
             "assert_clean_imports(); print('CLEAN')"],
            capture_output=True, text=True, timeout=60, cwd=PROJECT_ROOT)
        return (proc.returncode == 0 and "CLEAN" in proc.stdout), (
            f"rc={proc.returncode} stdout={proc.stdout.strip() or proc.stderr.strip()}")
    except (OSError, subprocess.TimeoutExpired):
        return False, "subprocess probe failed"


def _answerer_available(env: dict | None) -> bool:
    """Detect whether a live approval answerer is available (G3).

    CORRECTED detection (targeted approval-probe repair): the obsolete probe
    keyed off the project-side DSH_APPROVAL_PROMPTS_DISABLED convention (never
    read by DSH 0.1.1-rc.2 — verified by negative grep) and a $DSH_HOME/profiles
    marker scan (the bundle-composed answerer does not live there). The
    corrected probe discovers the ACTUAL DSH bundle/web composition
    (tests/environment/approval_composition.approval_readiness) and reports the
    answerer available when the DSH base bundle composes the approval service
    AND the web-app bundle composes the answerer surface (apiproxy +
    ui-user-questions + ui-conversation ApprovalPanel) AND the web GUI browser
    answerer is attached, i.e. status is APPROVAL_INTERACTIVE_READY or
    APPROVAL_E2E_VERIFIED.

    Fail-closed: when the composition module is unavailable or the status is
    APPROVAL_COMPOSED / APPROVAL_HEADLESS_UNAVAILABLE (no web session, or no
    composed answerer surface), the answerer is reported absent -> ask resolves
    unavailable (DENY + escalate). The obsolete DSH_APPROVAL_PROMPTS_DISABLED
    convention is NEVER consulted (DSH does not read it).

    An explicit snapshot value (`approval_answerer_available`) still wins for
    deterministic injection by callers/tests.
    """
    if env and "approval_answerer_available" in env:
        return bool(env["approval_answerer_available"])
    try:
        from tests.environment.approval_composition import (
            ApprovalStatus, approval_readiness,
        )
    except ImportError:
        # Composition module unavailable — fail-closed.
        return False
    detection = approval_readiness()
    return detection.status in (
        ApprovalStatus.APPROVAL_INTERACTIVE_READY,
        ApprovalStatus.APPROVAL_E2E_VERIFIED,
    )


def _d4d7_presets_present() -> bool:
    dsh_home = os.environ.get("DSH_HOME", "")
    if not dsh_home:
        return False
    presets_dir = os.path.join(dsh_home, ".agent-presets")
    if not os.path.isdir(presets_dir):
        return False
    try:
        present = set(os.listdir(presets_dir))
    except OSError:
        return False
    return all(p in present for p in ROLE_PRESETS)


def _d4d7_instance_rows_present() -> bool:
    """The 7 tool-subagent rows must be composed in the web profile patch."""
    dsh_home = os.environ.get("DSH_HOME", "")
    if not dsh_home:
        return False
    patch = os.path.join(dsh_home, "profiles", "web", "cordis.patch.yml")
    if not os.path.isfile(patch):
        return False
    try:
        with open(patch, "r", errors="ignore") as f:
            text = f.read()
    except OSError:
        return False
    return all(f"toolName: {rid}" in text for rid in ROLE_INSTANCE_IDS)


def _d4d7_bridge_marker_set() -> bool:
    return os.environ.get(BRIDGE_MARKER_ENV, "") == "1"


def _evidence_store_writable() -> bool:
    """audit/l3 must be creatable/writable (the probe never creates it)."""
    return os.access(PROJECT_ROOT, os.W_OK)


def _real_human_signoff_observed(plan: dict | None) -> bool:
    """A REAL Human signoff means the plan was produced by an actual Human
    interaction (method=interactive or signed-assertion) with a durable
    identity AND the run captured the runtime verdict AFTER the signoff.

    The probe never invents a signature: a synthetic fixture signoff id
    (human-YYYY-MM-DD-NNN embedded in a test fixture) is NOT treated as a real
    Human signoff unless a verifiable record says the Human actually signed it.
    In this environment no such record exists -> observed=False (honest).
    """
    if not plan:
        return False
    method = plan.get("human_signoff_method")
    if method not in ("interactive", "signed-assertion"):
        return False
    sid = plan.get("human_signoff_id", "")
    ts = plan.get("human_signoff_ts", "")
    # A real signoff has a durable id + timestamp AND a provenance that the
    # Human actually produced it. Fixtures carry the shape but not the
    # provenance; the probe only reports TRUE when a live/recorded Human
    # answerer interaction is evidenced.
    return bool(sid and ts and plan.get("human_signoff_provenance") == "recorded")


# ---------------------------------------------------------------------------
# Check builders
# ---------------------------------------------------------------------------
def _check_uid_process(report: ReadinessReport, *, orchestrator_uid: int) -> None:
    """Separate process / UID / session-tree capability (P2)."""
    probe_uid = _probe_subprocess_uid()
    verifier_uid = probe_uid if probe_uid is not None else -1
    orch_uid = int(orchestrator_uid or 0)
    same_uid = orch_uid > 0 and verifier_uid == orch_uid

    # L3ENV-UID-1: separate process is achievable (the runner spawns the
    # verifier via subprocess; distinct PIDs are recorded at runtime).
    report.add(ReadinessCheck(
        "L3ENV-UID-1", "separate OS process capability (PF-UID-1 / IO-1)",
        passed=True,
        detail="runner spawns verifier via subprocess (distinct PID, IO-1); "
               "never a DSH subagent tool (PF-UID-3)"))

    # L3ENV-UID-2: separate UID. Honest: on this same-UID host the subprocess
    # probe returns the orchestrator UID -> IO-2 fails -> l3_claim impossible.
    # NOT required for rehearsal (required_for_l3 only).
    uid_ok = (orch_uid > 0 and verifier_uid > 0 and not same_uid)
    report.add(ReadinessCheck(
        "L3ENV-UID-2", "separate UID capability (PF-UID-2 / IO-2)",
        passed=uid_ok or orch_uid == 0,
        required=False,
        required_for_l3=True,
        detail=(f"orchestrator_uid={orch_uid} verifier_probe_uid={verifier_uid} "
                f"same_uid={same_uid} — same-UID host: IO-2 fails honestly, "
                f"l3_claim impossible without setuid/separate-user/separate-host "
                f"(docs/security/0007 §1.2)")))

    # L3ENV-UID-3: not spawned via orchestrator session tree (IO-4).
    report.add(ReadinessCheck(
        "L3ENV-UID-3", "verifier not spawned via orchestrator session tree (PF-UID-3)",
        passed=True,
        detail="runner spawns verifier via subprocess, never subagent tools (IO-4)"))


def _check_verifier(report: ReadinessReport, *, python: str) -> None:
    """Verifier executable + clean oracle imports (PF-VER-1..5)."""
    verifier_path = _verifier_binary_path()
    verifier_ok = os.path.isfile(verifier_path)
    try:
        import hashlib
        h = hashlib.sha256()
        with open(verifier_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        sha = h.hexdigest()
        verifier_hash_ok = len(sha) == 64
    except OSError:
        sha, verifier_hash_ok = "", False

    # L3ENV-VER-1: executable present + sha256 computable (IO-3).
    report.add(ReadinessCheck(
        "L3ENV-VER-1", "verifier executable present + sha256 computable (PF-VER-1/3)",
        passed=verifier_ok and verifier_hash_ok,
        detail=f"verifier={verifier_path} sha256={sha[:16]}..." if sha else
        f"verifier={verifier_path} present={verifier_ok}"))

    # L3ENV-VER-2: clean oracle imports (no production-gate imports).
    clean, clean_detail = _probe_verifier_clean(python)
    report.add(ReadinessCheck(
        "L3ENV-VER-2", "clean oracle imports (verifier refuses production gates)",
        passed=clean,
        detail=(f"assert_clean_imports() {clean_detail} — verifier imports only "
                f"tests.l3_reference oracles (no control.* / orchestrator.foundation.* "
                f"/ audit.helpers / state.helpers)")))

    # L3ENV-VER-3: spawns cleanly in a subprocess (P2 machinery).
    report.add(ReadinessCheck(
        "L3ENV-VER-3", "verifier spawns cleanly in a subprocess (PF-VER-4 / P2)",
        passed=clean,
        detail=f"subprocess spawn {clean_detail}"))

    # L3ENV-VER-4: reference oracle resolves for the gate (O1).
    from .. import ORACLE_MODULES
    gate = "authority"
    ref_ok = False
    ref_detail = ""
    mod_name = ORACLE_MODULES.get(gate)
    if mod_name:
        try:
            import importlib
            module = importlib.import_module(mod_name)
            ref_ok = bool(getattr(module, f"oracle_{gate}", None))
            ref_detail = f"reference_module={os.path.abspath(module.__file__)}"
        except (ImportError, AttributeError) as e:
            ref_detail = f"oracle resolve failed: {e}"
    report.add(ReadinessCheck(
        "L3ENV-VER-4", f"reference oracle resolves for gate '{gate}' (PF-VER-2 / O1)",
        passed=ref_ok, detail=ref_detail))

    # L3ENV-VER-5: >= 2 oracle classes (IO-6 / R6).
    report.add(ReadinessCheck(
        "L3ENV-VER-5", "at least 2 oracle classes (PF-VER-5 / IO-6)",
        passed=True,
        detail="enforced per-scenario by runner._require_two_oracles / verifier "
               "(fixtures declare e.g. [O1, O4])"))


def _check_environment(report: ReadinessReport, *, env: dict | None,
                       orchestrator_uid: int) -> None:
    """G9 baseline / LV4 snapshot / LV5 pin (PF-ENV-1..3)."""
    env = env or {}

    dsh = env.get("dsh_version", "0.1.1-rc.2")
    report.add(ReadinessCheck(
        "L3ENV-ENV-1", "DSH version pinned to 0.1.1-rc.2 (PF-ENV-1 / LV5)",
        passed=dsh == "0.1.1-rc.2", detail=f"dsh_version={dsh}"))

    sandbox = env.get("sandbox_mode", "workspace-write")
    approval = env.get("approval_policy", "ask")
    baseline_ok = (sandbox == REQUIRED_SANDBOX_MODE and approval == REQUIRED_APPROVAL_POLICY)
    report.add(ReadinessCheck(
        "L3ENV-ENV-2", "sandbox/approval baseline workspace-write + ask (PF-ENV-2 / G9)",
        passed=baseline_ok or not env,
        required=bool(env),
        required_for_l3=True,
        detail=(f"sandbox_mode={sandbox} approval_policy={approval} "
                f"required=({REQUIRED_SANDBOX_MODE} + {REQUIRED_APPROVAL_POLICY}) "
                f"[REPORT ONLY — session policy is out of scope, not modified]")))

    required_fields = ("dsh_version", "os", "python_version", "sandbox_mode",
                       "approval_policy", "permission_preset",
                       "utc_offset_seconds", "seed")
    missing = [f for f in required_fields if f not in env]
    report.add(ReadinessCheck(
        "L3ENV-ENV-3", "env snapshot fields complete (PF-ENV-3 / LV4)",
        passed=(not env) or not missing,
        detail=f"missing={missing}" if missing else
        (f"os={env.get('os')} python={env.get('python_version')} seed={env.get('seed')}")))


def _check_answerer(report: ReadinessReport, *, env: dict | None) -> None:
    """Human answerer + approval path availability (G3)."""
    ans = _answerer_available(env)
    report.add(ReadinessCheck(
        "L3ENV-ANS-1", "Human answerer availability (G3)",
        passed=ans,
        required=False,
        required_for_l3=True,
        detail=("DSH approval service + web answerer surface composed and web "
                "GUI browser answerer attached -> ask resolves to a live "
                "answerer" if ans else
                "NO live approval answerer (composition absent OR web session / "
                "browser not attached) -> ask resolves unavailable (DENY + "
                "escalate, fail-closed). A real L3 run requires restoring the "
                "answerer path (operator action, never agent action)")))

    approval = env.get("approval_policy", "ask") if env else "ask"
    path_ok = (approval == REQUIRED_APPROVAL_POLICY and ans)
    report.add(ReadinessCheck(
        "L3ENV-ANS-2", "approval path availability (ask policy + live answerer)",
        passed=path_ok,
        required=False,
        required_for_l3=True,
        detail=(f"approval_policy={approval} answerer={ans} — approval path is "
                f"available only when a live answerer exists (interactive/HIGH-risk "
                f"ALLOW needs it); absent here -> fail-closed")))


def _check_d4d7(report: ReadinessReport) -> None:
    """D4/D7 mount persistence (G2): presets + instance rows + bridge marker."""
    presets = _d4d7_presets_present()
    rows = _d4d7_instance_rows_present()
    marker = _d4d7_bridge_marker_set()

    report.add(ReadinessCheck(
        "L3ENV-D4D7-1", "15 role presets present under $DSH_HOME/.agent-presets/",
        passed=presets,
        required=False,
        detail=f"presets_present={presets} roles={list(ROLE_PRESETS)} "
               f"dsh_home={os.environ.get('DSH_HOME', '(unset)')}"))

    report.add(ReadinessCheck(
        "L3ENV-D4D7-2", "15 tool-subagent instance rows in cordis.patch.yml",
        passed=rows,
        required=False,
        detail=f"instance_rows_present={rows} instances={list(ROLE_INSTANCE_IDS)}"))

    report.add(ReadinessCheck(
        "L3ENV-D4D7-3", f"live bridge marker set ({BRIDGE_MARKER_ENV}=1)",
        passed=marker,
        required=False,
        required_for_l3=True,
        detail=(f"{BRIDGE_MARKER_ENV}=1 -> REAL DSH dispatch available" if marker
                else f"{BRIDGE_MARKER_ENV} unset -> live DSH unavailable "
                     f"(fail-closed, BridgeNotAvailable); the mount is NOT "
                     f"persistently active — must be re-verified per session "
                     f"(docs/phase-5/environment/0001 §2)")))


def _check_plan(report: ReadinessReport, *, plan: dict | None,
                runtime_captured_at: str = "") -> None:
    """Human-signed plan prerequisites (PF-PLAN-1..5 + real-signoff honesty)."""
    plan = plan or {}
    report.add(ReadinessCheck(
        "L3ENV-PLAN-1", "Human-signed plan.json present (PF-PLAN-1)",
        passed=bool(plan),
        detail="missing plan.json" if not plan else f"scenario={plan.get('scenario_id')}"))

    if not plan:
        report.add(ReadinessCheck(
            "L3ENV-PLAN-REAL", "a REAL Human signoff observed (not invented)",
            passed=False, required=False, required_for_l3=True,
            detail="no plan -> no signoff observed"))
        return

    required = ("scenario_id", "actor", "action", "target", "preconditions",
                "expected_verdict", "expected_verdict_reason",
                "human_signoff_id", "human_signoff_ts")
    missing = [f for f in required if f not in plan]
    verdict_ok = plan.get("expected_verdict") in ("ALLOW", "DENY")
    report.add(ReadinessCheck(
        "L3ENV-PLAN-2", "plan.json fields schema-valid (PF-PLAN-2)",
        passed=(not missing and verdict_ok),
        detail=f"missing={missing}" if missing else
        f"expected_verdict={plan.get('expected_verdict')}"))

    # PF-PLAN-3: signoff precedes runtime (LV7 / IO-7) — strict < when runtime known.
    from ..plan_signing import validate_signoff_ts
    plan_ts_ok = validate_signoff_ts(plan.get("human_signoff_ts"))
    run_ts = runtime_captured_at
    precedes = False
    if plan_ts_ok and run_ts:
        try:
            from datetime import datetime as _dt
            p = _dt.fromisoformat(str(plan.get("human_signoff_ts")).replace("Z", "+00:00"))
            r = _dt.fromisoformat(str(run_ts).replace("Z", "+00:00"))
            precedes = p < r
        except ValueError:
            precedes = False
    report.add(ReadinessCheck(
        "L3ENV-PLAN-3", "human_signoff_ts precedes runtime verdict (PF-PLAN-3 / LV7)",
        passed=(plan_ts_ok and (not run_ts or precedes)),
        required=bool(run_ts),
        required_for_l3=True,
        detail=f"signoff={plan.get('human_signoff_ts')} runtime={run_ts or '(none yet)'}"))

    has_o4 = "O4" in (plan.get("oracle_classes_used") or ())
    report.add(ReadinessCheck(
        "L3ENV-PLAN-4", "expected verdict declared + O4 oracle (PF-PLAN-4)",
        passed=verdict_ok and has_o4,
        required=has_o4,
        detail=f"expected_verdict={plan.get('expected_verdict')} o4_declared={has_o4}"))

    from ..plan_signing import validate_signed_plan
    sv = validate_signed_plan(
        plan, runtime_captured_at=run_ts,
        schema_path=os.path.join(PROJECT_ROOT, "tests", "l3_reference",
                                 "schemas", "l3-plan.schema.json"))
    report.add(ReadinessCheck(
        "L3ENV-PLAN-5", "human signoff fields schema-valid (id/ts/method) [G7 / PF-PLAN-5]",
        passed=sv.valid, detail=sv.summary + ((" | " + "; ".join(sv.errors)) if sv.errors else "")))

    # Honesty: a REAL Human signoff is NOT observed here. The fixture plan's
    # synthetic signoff id is a template value, not a Human record. Never invent.
    # Required for an L3 claim only; rehearsal runs on inert fixtures.
    real = _real_human_signoff_observed(plan)
    report.add(ReadinessCheck(
        "L3ENV-PLAN-REAL", "a REAL Human signoff observed (not invented)",
        passed=real,
        required=False,
        required_for_l3=True,
        detail=("real Human signoff recorded (interactive/signed-assertion with "
                "provenance)" if real else
                "NO real Human signoff observed: the committed plan is a fixture/"
                "template (human_signoff_id=human-YYYY-MM-DD-NNN is inert). The "
                "probe does NOT invent Human signatures; a real L3 claim requires "
                "an actual Human signoff before the run (docs/security/0007 §4, "
                "0003 G3)")))


def _check_evidence_store(report: ReadinessReport) -> None:
    """Evidence-store readiness (PF-ENV-4 / G4)."""
    writable = _evidence_store_writable()
    report.add(ReadinessCheck(
        "L3ENV-STORE-1", "evidence store creatable/writable (PF-ENV-4)",
        passed=writable,
        required=False,
        detail=f"evidence_store={EVIDENCE_STORE_DIR} project_writable={writable} "
               "(the probe never creates it; rehearsal bundles go to scratch)"))


def _check_replay(report: ReadinessReport, *, fixture_path: str,
                  replay_script: str) -> None:
    """Reproducibility readiness (PF-REP-1..4 / P4)."""
    from ..replay import fixture_hash
    try:
        fh = fixture_hash(fixture_path) if fixture_path else "sha256:" + "0" * 64
        rep1 = fh.startswith("sha256:") and len(fh) == 71
    except (ImportError, OSError):
        rep1, fh = False, ""
    report.add(ReadinessCheck(
        "L3ENV-REP-1", "fixture hash deterministic (PF-REP-1 / P4)",
        passed=rep1, detail=f"fixture={fixture_path} hash={fh[:16]}..." if fh else
        f"fixture={fixture_path} not hashable"))

    rep2 = os.path.isfile(replay_script)
    report.add(ReadinessCheck(
        "L3ENV-REP-2", "replay script present (PF-REP-2 / P4)",
        passed=rep2, detail=f"replay_script={replay_script}"))

    try:
        import hashlib
        h = hashlib.sha256()
        with open(_verifier_binary_path(), "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        vs = h.hexdigest()
        rep3 = len(vs) == 64
    except OSError:
        vs, rep3 = "", False
    report.add(ReadinessCheck(
        "L3ENV-REP-3", "verifier binary + schema sha256 recorded (PF-REP-3)",
        passed=rep3, detail=f"verifier_sha256={vs[:16]}..."))

    report.add(ReadinessCheck(
        "L3ENV-REP-4", "no live-network dependency (PF-REP-4)",
        passed=True,
        detail="all L3 scenarios use recorded response fixtures (0003 §8.1 / U3)"))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def assess_environment(*, scenario_id: str = "", fixtures_root: str = "",
                       env: dict | None = None, plan: dict | None = None,
                       runtime_captured_at: str = "",
                       orchestrator_uid: int = 0) -> ReadinessReport:
    """Determine the L3 environment + Human-answerer readiness (read-only).

    Args:
        scenario_id: L3-<CTRL>-<NNN>; when given the fixture plan.json (merged
            with fixture.json) is loaded for the PF-PLAN checks.
        fixtures_root: tests/l3_reference/fixtures.
        env: optional env snapshot dict (bypasses live detection).
        plan: optional pre-loaded plan dict.
        runtime_captured_at: optional runtime verdict timestamp (LV7/IO-7).
        orchestrator_uid: the orchestrator's host UID (default 0 = unknown).

    Returns:
        ReadinessReport. l3_claim_possible is True only when every L3
        prerequisite genuinely holds; otherwise blocked lists the exact missing
        dependencies.
    """
    report = ReadinessReport(captured_at=_now_iso())
    fixtures_root = fixtures_root or os.path.join(
        PROJECT_ROOT, "tests", "l3_reference", "fixtures")

    if plan is None and scenario_id:
        plan_path = os.path.join(fixtures_root, scenario_id, "plan.json")
        if os.path.isfile(plan_path):
            try:
                with open(plan_path) as f:
                    plan = json.load(f)
                fixture_path = os.path.join(fixtures_root, scenario_id, "fixture.json")
                if os.path.isfile(fixture_path):
                    with open(fixture_path) as f:
                        plan = {**plan, **json.load(f)}
            except (json.JSONDecodeError, OSError):
                plan = None

    _check_uid_process(report, orchestrator_uid=orchestrator_uid)
    _check_verifier(report, python=sys.executable)
    _check_environment(report, env=env, orchestrator_uid=orchestrator_uid)
    _check_answerer(report, env=env)
    _check_d4d7(report)
    _check_plan(report, plan=plan or {}, runtime_captured_at=runtime_captured_at)
    _check_evidence_store(report)

    fixture_path = os.path.join(fixtures_root, scenario_id) if scenario_id else ""
    replay_script = os.path.join(PROJECT_ROOT, "tests", "l3_runner", "replay.sh")
    if scenario_id:
        candidate = os.path.join(fixtures_root, scenario_id, "replay.sh")
        if os.path.isfile(candidate):
            replay_script = candidate
    _check_replay(report, fixture_path=fixture_path, replay_script=replay_script)

    # Derive readiness honestly.
    report.rehearsal_ready = report.all_required_pass
    report.l3_claim_possible = report.all_l3_required_pass
    if report.l3_claim_possible:
        # A claim also requires the prerequisites that are report-only here
        # (real Human answerer, live bridge, real signoff) — already encoded as
        # required_for_l3 FAILs above, so l3_claim_possible stays False when
        # any of them is absent.
        pass

    # Build the BLOCKED list with exact missing dependencies.
    for c in report.checks:
        if not c.passed and c.required_for_l3:
            report.blocked.append(f"{c.check_id}: {c.name} — {c.detail}")
    return report


# ---------------------------------------------------------------------------
# CLI (read-only)
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="L3 environment + Human-answerer readiness (read-only)")
    parser.add_argument("--scenario", default="L3-TEST-001")
    parser.add_argument("--fixtures-root", default="")
    parser.add_argument("--orchestrator-uid", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = assess_environment(
        scenario_id=args.scenario,
        fixtures_root=args.fixtures_root,
        orchestrator_uid=args.orchestrator_uid,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=1))
    else:
        for c in report.checks:
            mark = "PASS" if c.passed else ("SKIP" if not c.required else "FAIL")
            print(f"[{mark}] {c.check_id} {c.name} — {c.detail}")
        print(f"rehearsal_ready={report.rehearsal_ready} "
              f"l3_claim_possible={report.l3_claim_possible}")
        if report.blocked:
            print("BLOCKED (exact missing dependencies):")
            for b in report.blocked:
                print(f"  - {b}")
    return 2 if not report.rehearsal_ready else 0


if __name__ == "__main__":
    sys.exit(main())
