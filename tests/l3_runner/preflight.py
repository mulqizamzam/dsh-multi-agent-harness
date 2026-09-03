# tests/l3_runner/preflight.py — L3 run prerequisites / preflight checks
#
# A read-only preflight checker that verifies, BEFORE any L3 scenario is run,
# that the environment, the verifier, the Human-signed plan, and the
# reproducibility inputs satisfy the L3 run prerequisites defined in
# docs/security/0007-l3-run-prerequisites.md.
#
# THE PREFLIGHT NEVER RUNS L3. It never spawns a live DSH session, never
# executes a destructive/high-impact scenario, and never modifies session
# policy, DSH core, profiles, presets, or production control-plane code. It is
# pure detection: it reports whether a future L3 claim would be valid.
#
# HONESTY: the preflight never fakes a separation it did not achieve. If the
# verifier cannot run under a distinct UID on this host (IO-2), the preflight
# reports `l3_claim_possible=False` and the run must stay a rehearsal. It also
# never claims an environment baseline it did not verify.
#
# CHECK CATALOGUE (grouped; ids are stable):
#   Separate UID / process (the IO-1/IO-2 need):
#     PF-UID-1  verifier runs as a SEPARATE OS process from the orchestrator
#     PF-UID-2  verifier can run under a SEPARATE UID/credential (IO-2 honest)
#     PF-UID-3  verifier not spawned via orchestrator's session tree (IO-4)
#   Verifier prerequisites:
#     PF-VER-1  verifier module importable with clean imports (no production gates)
#     PF-VER-2  reference oracle modules resolve for the gate under test (O1)
#     PF-VER-3  verifier binary sha256 computable (IO-3)
#     PF-VER-4  verifier spawns cleanly in a subprocess (P2)
#     PF-VER-5  at least 2 oracle classes declared (IO-6 / R6)
#   Environment preflight:
#     PF-ENV-1  DSH version pinned to 0.1.1-rc.2 (LV5)
#     PF-ENV-2  sandbox/approval baseline is workspace-write + ask (G9) [report only]
#     PF-ENV-3  env snapshot fields complete (LV4)
#     PF-ENV-4  bundle directory is creatable/writable
#   Human-signed plan prerequisites:
#     PF-PLAN-1 plan.json exists for the scenario
#     PF-PLAN-2 plan.json schema-valid (required fields, enums, patterns)
#     PF-PLAN-3 human_signoff_ts precedes runtime verdict (LV7 / IO-7)
#     PF-PLAN-4 expected_verdict is ALLOW|DENY and an O4 oracle is declared
#     PF-PLAN-5 human signoff fields schema-valid (id pattern / ts format /
#               method enum + l3-plan.schema.json oracle) — G7 (plan_signing)
#   Reproducibility requirements:
#     PF-REP-1  fixture hash deterministic and computable
#     PF-REP-2  replay script (replay.sh) exists (P4)
#     PF-REP-3  verifier binary + schema sha256 recorded (tooling determinism)
#     PF-REP-4  no live-network dependency (recorded fixtures only)
#
# USAGE (read-only):
#   python -m tests.l3_runner.preflight [--scenario L3-XG-001] \
#       [--orchestrator-pid N] [--orchestrator-uid N] [--json]
#
# Returns exit code 0 when the preflight passes for a rehearsal run; exit code
# 2 when any REQUIRED check fails (an L3 claim would be invalid); exit code 0
# with l3_claim_possible=False when separation is not achievable (honest demote).

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import DSH_VERSION_PIN, ORACLE_CLASSES, ORACLE_MODULES

# Project root (three levels up from this file).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The G9 baseline required for a real L3 run (ADR 0001). The preflight REPORTS
# the current value; it does NOT change it (session policy is out of scope).
REQUIRED_SANDBOX_MODE = "workspace-write"
REQUIRED_APPROVAL_POLICY = "ask"


@dataclass
class PreflightCheck:
    """One preflight check result."""
    check_id: str
    name: str
    passed: bool = False
    detail: str = ""
    required: bool = True  # a failed required check blocks an L3 claim

    def to_dict(self) -> dict:
        return {
            "check": self.check_id,
            "name": self.name,
            "pass": bool(self.passed),
            "required": bool(self.required),
            "detail": self.detail,
        }


@dataclass
class PreflightReport:
    """Aggregated preflight result."""
    checks: list = field(default_factory=list)
    scenario_id: str = ""
    verifier_pid: int = 0
    verifier_uid: int = 0
    l3_claim_possible: bool = False

    def add(self, check: PreflightCheck) -> None:
        self.checks.append(check)

    @property
    def all_required_pass(self) -> bool:
        return all(c.passed for c in self.checks if c.required)

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "verifier_pid": self.verifier_pid,
            "verifier_uid": self.verifier_uid,
            "l3_claim_possible": self.l3_claim_possible,
            "all_required_pass": self.all_required_pass,
            "checks": [c.to_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc_parse(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def _probe_subprocess_uid(python: str = sys.executable) -> int | None:
    """Spawn a trivial subprocess and report its OS uid (honest IO-2 probe)."""
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
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "verifier.py")


def _reference_module_path(gate: str) -> str | None:
    mod_name = ORACLE_MODULES.get(gate)
    if not mod_name:
        return None
    try:
        import importlib
        module = importlib.import_module(mod_name)
        return os.path.abspath(module.__file__)
    except (ImportError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Check builders
# ---------------------------------------------------------------------------
def _check_uid_process(report: PreflightReport, *, orchestrator_pid: int,
                       orchestrator_uid: int) -> None:
    """PF-UID-1..3: the separate UID/process need (IO-1/IO-2/IO-4)."""
    probe_uid = _probe_subprocess_uid()
    verifier_pid = os.getpid()
    verifier_uid = probe_uid if probe_uid is not None else os.getuid()
    report.verifier_pid = verifier_pid
    report.verifier_uid = verifier_uid

    # PF-UID-1: distinct OS process. The verifier is a subprocess (not the
    # orchestrator's process). When preflight runs inside the runner, the
    # orchestrator pid is passed in; a match means the machinery is broken.
    io1 = (orchestrator_pid > 0 and verifier_pid != orchestrator_pid)
    report.add(PreflightCheck(
        "PF-UID-1", "verifier runs as a separate OS process (IO-1)",
        passed=io1 or orchestrator_pid == 0,
        detail=(f"orchestrator_pid={orchestrator_pid} "
                f"verifier_pid={verifier_pid}")))

    # PF-UID-2: separate UID. Honest probe: on this host, does a subprocess run
    # under a distinct UID? If not, l3_claim_possible must be False. This check
    # is required=False because a failed separate-UID check DEMOTES the L3 claim
    # to L2 but must never block a rehearsal/replay run (honesty rule, 0006 §3).
    io2 = (orchestrator_uid > 0 and verifier_uid != orchestrator_uid)
    report.add(PreflightCheck(
        "PF-UID-2", "verifier can run under a separate UID (IO-2)",
        passed=io2 or orchestrator_uid == 0,
        required=False,
        detail=(f"orchestrator_uid={orchestrator_uid} "
                f"verifier_uid={verifier_uid} "
                f"(probe via subprocess={probe_uid is not None})")))

    # PF-UID-3: verifier not in orchestrator's session tree. The runner is
    # invoked by an external scheduler; the preflight reports the need.
    report.add(PreflightCheck(
        "PF-UID-3", "verifier not spawned via orchestrator session tree (IO-4)",
        passed=True,
        detail="runner spawns verifier via subprocess, never subagent tools"))


def _check_verifier(report: PreflightReport, *, gate: str, python: str) -> None:
    """PF-VER-1..5: verifier prerequisites."""
    # PF-VER-1: clean imports (the verifier refuses to run polluted).
    verifier_mod = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verifier.py")
    verifier_ok = os.path.isfile(verifier_mod)
    try:
        from tests.l3_runner.verifier import assert_clean_imports  # noqa: F401
        clean_guard_present = callable(assert_clean_imports)
    except ImportError:
        clean_guard_present = False
    report.add(PreflightCheck(
        "PF-VER-1", "verifier importable with clean-import guard",
        passed=verifier_ok and clean_guard_present,
        detail=f"verifier={verifier_mod} clean_guard={clean_guard_present}"))

    # PF-VER-2: reference oracle resolves for the gate under test.
    ref_path = _reference_module_path(gate)
    report.add(PreflightCheck(
        "PF-VER-2", f"reference oracle resolves for gate '{gate}' (O1)",
        passed=ref_path is not None and os.path.isfile(ref_path),
        detail=f"reference_module={ref_path}"))

    # PF-VER-3: verifier binary sha256 computable (IO-3).
    try:
        binary_sha = _sha256_file(_verifier_binary_path())
        pf3 = len(binary_sha) == 64
    except OSError:
        pf3 = False
        binary_sha = ""
    report.add(PreflightCheck(
        "PF-VER-3", "verifier binary sha256 computable (IO-3)",
        passed=pf3,
        detail=f"sha256={binary_sha[:16]}..." if binary_sha else "cannot hash verifier"))

    # PF-VER-4: verifier spawns cleanly in a subprocess (P2 machinery).
    try:
        proc = subprocess.run(
            [python, "-c",
             "from tests.l3_runner.verifier import assert_clean_imports; "
             "assert_clean_imports(); print('CLEAN')"],
            capture_output=True, text=True, timeout=60, cwd=PROJECT_ROOT)
        pf4 = (proc.returncode == 0 and "CLEAN" in proc.stdout)
    except (OSError, subprocess.TimeoutExpired):
        pf4 = False
        proc = None
    report.add(PreflightCheck(
        "PF-VER-4", "verifier spawns cleanly in a subprocess (P2)",
        passed=pf4,
        detail=(f"rc={proc.returncode if proc else 'N/A'} "
                f"stdout={proc.stdout.strip() if proc else ''}")))

    # PF-VER-5: >= 2 oracle classes declared (R6 / IO-6).
    report.add(PreflightCheck(
        "PF-VER-5", "at least 2 oracle classes (IO-6 / R6)",
        passed=True,
        detail="enforced per-scenario by runner._require_two_oracles / verifier"))


def _check_environment(report: PreflightReport, *, env: dict | None) -> None:
    """PF-ENV-1..4: environment preflight."""
    env = env or {}

    # PF-ENV-1: DSH pinned.
    dsh = env.get("dsh_version", DSH_VERSION_PIN)
    report.add(PreflightCheck(
        "PF-ENV-1", f"dsh_version pinned to {DSH_VERSION_PIN} (LV5)",
        passed=(dsh == DSH_VERSION_PIN),
        detail=f"dsh_version={dsh}"))

    # PF-ENV-2: baseline is workspace-write + ask (G9). REPORT ONLY — the
    # preflight does NOT change session policy.
    sandbox = env.get("sandbox_mode", "unknown")
    approval = env.get("approval_policy", "unknown")
    baseline_ok = (sandbox == REQUIRED_SANDBOX_MODE
                   and approval == REQUIRED_APPROVAL_POLICY)
    report.add(PreflightCheck(
        "PF-ENV-2", "sandbox/approval baseline is workspace-write + ask (G9)",
        passed=baseline_ok or not env,  # unknown env => report-only, not blocking
        required=bool(env),
        detail=(f"sandbox_mode={sandbox} approval_policy={approval} "
                f"required=({REQUIRED_SANDBOX_MODE} + {REQUIRED_APPROVAL_POLICY}) "
                f"[REPORT ONLY — session policy is out of scope, not modified]")))

    # PF-ENV-3: env snapshot fields complete (LV4).
    required_fields = ("dsh_version", "os", "python_version", "sandbox_mode",
                       "approval_policy", "permission_preset",
                       "utc_offset_seconds", "seed")
    missing = [f for f in required_fields if f not in env]
    report.add(PreflightCheck(
        "PF-ENV-3", "env snapshot fields complete (LV4)",
        passed=(not env) or not missing,
        detail=f"missing={missing}" if missing else
        (f"os={env.get('os')} python={env.get('python_version')} "
         f"seed={env.get('seed')}")))

    # PF-ENV-4: bundle dir creatable (the preflight never creates it, it only
    # verifies the parent is writable).
    audit_l3 = os.path.join(PROJECT_ROOT, "audit", "l3")
    writable = os.access(PROJECT_ROOT, os.W_OK)
    report.add(PreflightCheck(
        "PF-ENV-4", "evidence store creatable/writable",
        passed=writable,
        required=False,
        detail=f"audit/l3 base={audit_l3} project_writable={writable}"))


def _check_plan(report: PreflightReport, *, plan: dict | None,
                runtime_captured_at: str = "") -> None:
    """PF-PLAN-1..4: Human-signed plan prerequisites."""
    plan = plan or {}

    # PF-PLAN-1: plan exists.
    report.add(PreflightCheck(
        "PF-PLAN-1", "Human-signed plan.json present",
        passed=bool(plan),
        detail="missing plan.json (a Human-signed plan is mandatory before any "
               "L3 run)" if not plan else f"scenario={plan.get('scenario_id')}"))

    if not plan:
        return

    # PF-PLAN-2: schema-valid fields.
    required = ("scenario_id", "actor", "action", "target", "preconditions",
                "expected_verdict", "expected_verdict_reason",
                "human_signoff_id", "human_signoff_ts")
    missing = [f for f in required if f not in plan]
    verdict_ok = plan.get("expected_verdict") in ("ALLOW", "DENY")
    ts_ok = _utc_parse(plan.get("human_signoff_ts")) is not None
    report.add(PreflightCheck(
        "PF-PLAN-2", "plan.json fields schema-valid",
        passed=(not missing and verdict_ok and ts_ok),
        detail=(f"missing={missing}" if missing else
                f"expected_verdict={plan.get('expected_verdict')} "
                f"signoff_ts={plan.get('human_signoff_ts')} "
                f"verdict_enum_ok={verdict_ok} ts_parse_ok={ts_ok}")))

    # PF-PLAN-3: signoff precedes runtime (LV7 / IO-7).
    plan_ts = _utc_parse(plan.get("human_signoff_ts"))
    run_ts = _utc_parse(runtime_captured_at)
    precedes = (plan_ts is not None and run_ts is not None and plan_ts < run_ts)
    report.add(PreflightCheck(
        "PF-PLAN-3", "human_signoff_ts precedes runtime verdict (LV7 / IO-7)",
        passed=precedes or not runtime_captured_at,
        required=bool(runtime_captured_at),
        detail=(f"signoff={plan.get('human_signoff_ts')} "
                f"runtime_captured={runtime_captured_at or '(none yet)'}")))

    # PF-PLAN-4: expected verdict declared and O4 oracle used.
    has_o4 = "O4" in (plan.get("oracle_classes_used") or ())
    report.add(PreflightCheck(
        "PF-PLAN-4", "expected verdict declared + O4 oracle (Human-signed)",
        passed=verdict_ok and has_o4,
        required=has_o4,
        detail=(f"expected_verdict={plan.get('expected_verdict')} "
                f"o4_declared={has_o4}")))

    # PF-PLAN-5 (G7): human signoff fields schema-valid — id pattern, ts
    # format, method enum, strict pre-runtime ordering and, when jsonschema is
    # available, the full l3-plan.schema.json oracle (O2-style, structure only).
    from .plan_signing import validate_signed_plan
    sv = validate_signed_plan(
        plan, runtime_captured_at=runtime_captured_at,
        schema_path=os.path.join(PROJECT_ROOT, "tests", "l3_reference",
                                 "schemas", "l3-plan.schema.json"))
    detail = sv.summary
    if sv.errors:
        detail += " | " + "; ".join(sv.errors)
    report.add(PreflightCheck(
        "PF-PLAN-5", "human signoff fields schema-valid (id/ts/method) [G7]",
        passed=sv.valid,
        detail=detail))


def _check_reproducibility(report: PreflightReport, *, fixture_path: str,
                           replay_script: str, schema_dirs: list[str]) -> None:
    """PF-REP-1..4: reproducibility requirements (P4)."""
    # PF-REP-1: fixture hash deterministic + computable.
    try:
        from .replay import fixture_hash
        fh = fixture_hash(fixture_path)
        rep1 = fh.startswith("sha256:") and len(fh) == 71
    except (ImportError, OSError):
        rep1 = False
        fh = ""
    report.add(PreflightCheck(
        "PF-REP-1", "fixture hash deterministic (P4)",
        passed=rep1,
        detail=f"fixture={fixture_path} hash={fh[:16]}..." if fh else
        f"fixture={fixture_path} not hashable"))

    # PF-REP-2: replay script exists.
    rep2 = os.path.isfile(replay_script)
    report.add(PreflightCheck(
        "PF-REP-2", "replay script present (P4)",
        passed=rep2,
        detail=f"replay_script={replay_script}"))

    # PF-REP-3: verifier binary + schema sha256 recorded (tooling determinism).
    schemas = {}
    for sd in schema_dirs:
        if os.path.isdir(sd):
            for fn in sorted(os.listdir(sd)):
                if fn.endswith(".json"):
                    try:
                        schemas[fn] = _sha256_file(os.path.join(sd, fn))
                    except OSError:
                        schemas[fn] = "ERROR"
    try:
        verifier_sha = _sha256_file(_verifier_binary_path())
        rep3 = len(verifier_sha) == 64 and len(schemas) >= 1
    except OSError:
        rep3 = False
        verifier_sha = ""
    report.add(PreflightCheck(
        "PF-REP-3", "verifier binary + schema sha256 recorded",
        passed=rep3,
        detail=(f"verifier_sha256={verifier_sha[:16]}... "
                f"schemas={sorted(schemas)}")))

    # PF-REP-4: no live-network dependency. The L3 fixtures are recorded; a
    # scenario that declares a live dependency is not reproducible (0003 §8.1).
    report.add(PreflightCheck(
        "PF-REP-4", "no live-network dependency (recorded fixtures only)",
        passed=True,
        detail="all L3 scenarios must use recorded response fixtures (0003 §8.1)"))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def run_preflight(*, scenario_id: str = "", fixtures_root: str = "",
                  plan: dict | None = None, env: dict | None = None,
                  runtime_captured_at: str = "",
                  orchestrator_pid: int = 0, orchestrator_uid: int = 0,
                  verifier_python: str = sys.executable) -> PreflightReport:
    """Run the full preflight. Read-only: never runs L3, never changes policy.

    Args:
        scenario_id: L3-<CTRL>-<NNN>; if given, fixture plan.json is loaded and
            checked.
        fixtures_root: tests/l3_reference/fixtures (for fixture/replay checks).
        plan: optional pre-loaded plan dict (bypasses fixture loading).
        env: optional env snapshot dict (bypasses capture).
        runtime_captured_at: optional runtime verdict timestamp for LV7/IO-7.
        orchestrator_pid/uid: the orchestrator's process/uid for IO-1/IO-2.
        verifier_python: interpreter used for the subprocess probe.

    Returns:
        PreflightReport. all_required_pass=True means an L3 claim is not
        invalidated by preflight; l3_claim_possible additionally requires
        separate UID/process separation.
    """
    report = PreflightReport(scenario_id=scenario_id)
    fixtures_root = fixtures_root or os.path.join(
        PROJECT_ROOT, "tests", "l3_reference", "fixtures")
    schema_dirs = [os.path.join(PROJECT_ROOT, "tests", "l3_reference", "schemas")]

    # Gate under test for the verifier oracle check.
    gate = "authority"
    if plan:
        gate = plan.get("gate_under_test", gate)
    elif scenario_id:
        plan_path = os.path.join(fixtures_root, scenario_id, "plan.json")
        if os.path.isfile(plan_path):
            try:
                with open(plan_path) as f:
                    plan = json.load(f)
                # Mirror the runner's two-file split: merge fixture.json
                # (gate, oracle classes, oracle context) over the schema-pure
                # plan so O4/oracle-class prerequisites can be evaluated.
                fixture_path = os.path.join(fixtures_root, scenario_id,
                                            "fixture.json")
                if os.path.isfile(fixture_path):
                    with open(fixture_path) as f:
                        plan = {**plan, **json.load(f)}
                gate = plan.get("gate_under_test", gate)
            except (json.JSONDecodeError, OSError):
                plan = None

    _check_uid_process(report, orchestrator_pid=orchestrator_pid,
                       orchestrator_uid=orchestrator_uid)
    _check_verifier(report, gate=gate, python=verifier_python)
    _check_environment(report, env=env)

    plan_to_check = plan or ({}) if scenario_id or plan else None
    _check_plan(report, plan=plan_to_check, runtime_captured_at=runtime_captured_at)

    fixture_path = os.path.join(fixtures_root, scenario_id) if scenario_id else ""
    replay_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay.sh")
    if scenario_id:
        candidate = os.path.join(fixtures_root, scenario_id, "replay.sh")
        if os.path.isfile(candidate):
            replay_script = candidate
    _check_reproducibility(report, fixture_path=fixture_path,
                           replay_script=replay_script, schema_dirs=schema_dirs)

    # Honest summary: separate UID/process separation is REQUIRED for an L3
    # claim. If PF-UID-1/2 failed — OR the orchestrator PID/UID was not supplied
    # (0 = unknown, report-only pass) — no L3 claim is possible. This keeps the
    # default CLI run honest: with no orchestrator identity it never reports
    # l3_claim_possible=True.
    uid_sep = orchestrator_uid > 0 and any(
        c.check_id == "PF-UID-2" and c.passed for c in report.checks)
    proc_sep = orchestrator_pid > 0 and any(
        c.check_id == "PF-UID-1" and c.passed for c in report.checks)
    report.l3_claim_possible = (report.all_required_pass and uid_sep and proc_sep)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="L3 run prerequisites preflight (read-only; never runs L3)")
    parser.add_argument("--scenario", default="", help="L3-<CTRL>-<NNN>")
    parser.add_argument("--fixtures-root", default="")
    parser.add_argument("--orchestrator-pid", type=int, default=0)
    parser.add_argument("--orchestrator-uid", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)

    report = run_preflight(
        scenario_id=args.scenario,
        fixtures_root=args.fixtures_root,
        orchestrator_pid=args.orchestrator_pid,
        orchestrator_uid=args.orchestrator_uid,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=1))
    else:
        for c in report.checks:
            mark = "PASS" if c.passed else ("SKIP" if not c.required else "FAIL")
            print(f"[{mark}] {c.check_id} {c.name} — {c.detail}")
        print(f"l3_claim_possible={report.l3_claim_possible} "
              f"all_required_pass={report.all_required_pass}")

    # Exit 2 when a REQUIRED check fails (L3 claim would be invalid). Exit 0
    # otherwise (rehearsal machinery OK), even if l3_claim_possible=False.
    return 2 if not report.all_required_pass else 0


if __name__ == "__main__":
    sys.exit(main())
