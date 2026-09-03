# tests/l3_runner/uid_readiness.py — G6: separate-process / separate-UID readiness
#
# Phase 5 / Session F — L3 execution readiness (G6 gap closure).
#
# PURPOSE
#   Detects, honestly, whether THIS host can run the L3 verifier under a
#   credential separate from the orchestrator (IO-2), documents what a
#   separate-UID launch requires (per docs/security/0007 §1.2), and keeps
#   `l3_claim_possible=False` whenever IO-2 cannot be achieved. It is a pure
#   detection/documentation module: it NEVER fakes a UID separation, NEVER
#   modifies credentials, NEVER changes session policy, and NEVER runs L3.
#
# HONESTY RULE (load-bearing, docs/security/0007 §1.2, 0006 §3)
#   IO-2 (`verifier_uid != orchestrator_uid`) can only pass on a host where the
#   verifier actually runs under a distinct credential. On a same-UID host the
#   probe returns the same UID, io2 passes=False, and the module reports
#   l3_claim_possible=False. The infrastructure never fakes a credential
#   separation it did not achieve.
#
# SEPARATE-UID LAUNCH OPTIONS (what a real L3 run requires; 0007 §1.2):
#   1. setuid wrapper  — the runner spawns the verifier via a setuid helper so
#      the verifier process drops into a dedicated, low-privilege account.
#   2. separate user   — orchestrator and verifier run as different OS users;
#      the verifier account has read-only access to the evidence bundle dir.
#   3. separate host   — the verifier runs on a different host that mounts the
#      evidence bundle read-only (strongest isolation; removes local UID races).
#
# USAGE (read-only):
#   from tests.l3_runner.uid_readiness import assess_uid_readiness
#   report = assess_uid_readiness(orchestrator_uid=os.getuid())
#   report.l3_claim_possible  # False on this same-UID sandbox

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Documented separate-UID launch options (docs/security/0007 §1.2). Each entry
# is (option_id, title, what it requires, isolation property gained).
SEPARATE_UID_LAUNCH_OPTIONS: tuple[tuple[str, str, str, str], ...] = (
    (
        "setuid-wrapper",
        "setuid launch wrapper",
        "A setuid helper (root-owned, mode 4755) that drops the verifier "
        "subprocess into a dedicated low-privilege account before it reads the "
        "evidence bundle; the wrapper must be audited and version-pinned.",
        "verifier runs under a distinct UID on the same host (IO-2 satisfied)",
    ),
    (
        "separate-user",
        "separate OS user account",
        "The orchestrator and the verifier run as different OS users; the "
        "verifier account holds read-only ACLs on the evidence bundle "
        "directory and no write authority over orchestrator-owned paths.",
        "distinct UID plus filesystem-level read/write separation",
    ),
    (
        "separate-host",
        "separate host / separate trust domain",
        "The verifier runs on a different host that mounts the evidence "
        "bundle (or a copy) read-only; no shared UID space and no local "
        "credential races with the orchestrator host.",
        "strongest isolation: distinct UID AND distinct trust domain",
    ),
)

# Options that THIS module may never use (honesty): nothing here modifies
# credentials or session policy. The module only REPORTS which option a future
# authorized L3 run would need.


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def probe_subprocess_uid(python: str = sys.executable) -> int | None:
    """Spawn a trivial subprocess and report its OS uid (honest IO-2 probe).

    A distinct-UID host is one where this probe returns a uid DIFFERENT from
    the orchestrator's uid. On this same-UID sandbox the probe returns the
    same uid as the caller, so IO-2 fails honestly.
    """
    try:
        proc = subprocess.run(
            [python, "-c", "import os; print(os.getuid())"],
            capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return None
        return int(proc.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


@dataclass
class UidReadinessReport:
    """Honest separate-UID readiness assessment for one host."""
    orchestrator_uid: int = 0
    verifier_probe_uid: int | None = None
    probe_ok: bool = False
    same_uid: bool = True
    io2_pass: bool = False
    l3_claim_possible: bool = False
    launch_requirement: str = ""
    launch_option: str = "separate-user"
    captured_at: str = ""
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "assessment": "uid-readiness",
            "orchestrator_uid": self.orchestrator_uid,
            "verifier_probe_uid": self.verifier_probe_uid,
            "probe_ok": self.probe_ok,
            "same_uid": self.same_uid,
            "io2_pass": self.io2_pass,
            "l3_claim_possible": self.l3_claim_possible,
            "launch_requirement": self.launch_requirement,
            "launch_option": self.launch_option,
            "captured_at": self.captured_at,
            "notes": list(self.notes),
        }


def assess_uid_readiness(*, orchestrator_uid: int | None = None,
                         python: str = sys.executable,
                         verifier_probe_uid: int | None = None) -> UidReadinessReport:
    """Assess whether a separate-UID verifier is achievable on this host.

    Args:
        orchestrator_uid: the orchestrator's host UID. When None, os.getuid()
            of this process is used (the caller is treated as the orchestrator
            side of the run).
        python: interpreter for the subprocess UID probe.
        verifier_probe_uid: an externally supplied verifier UID (e.g. from a
            real setuid launch). When provided, the probe is skipped and this
            value is used — the caller asserts it observed a distinct UID.

    Returns:
        UidReadinessReport. l3_claim_possible is True ONLY when IO-2 is
        genuinely satisfied (distinct, non-zero UIDs and a successful probe).
        The report never claims separation it did not observe.
    """
    orch_uid = int(orchestrator_uid) if orchestrator_uid else int(os.getuid())
    probe_uid = verifier_probe_uid
    probe_ok = probe_uid is not None
    if probe_uid is None:
        probe_uid = probe_subprocess_uid(python)
        probe_ok = probe_uid is not None

    same_uid = (probe_uid is not None and probe_uid == orch_uid)
    io2_pass = (probe_ok and orch_uid > 0 and probe_uid > 0 and probe_uid != orch_uid)

    # The required launch mechanism depends on the host situation.
    if not probe_ok:
        launch_requirement = (
            "cannot probe a subprocess UID on this host; a separate-UID "
            "verifier launch must be verified out-of-band (setuid wrapper, "
            "separate user, or separate host) before any L3 claim")
        launch_option = "separate-host"
    elif same_uid:
        launch_requirement = (
            "same-UID host: the verifier subprocess runs under the "
            f"orchestrator UID {orch_uid}. A real L3 run requires launching "
            "the verifier under a distinct credential via setuid wrapper, a "
            "separate user account, or a separate host (docs/security/0007 "
            "§1.2). IO-2 fails honestly; no L3 claim is possible here.")
        launch_option = "separate-user"
    else:
        launch_requirement = (
            "distinct-UID host detected: verifier probe uid "
            f"{probe_uid} != orchestrator uid {orch_uid}. IO-2 is satisfied "
            "for the probed launch path; keep the verifier account "
            "read-only over the evidence bundle for the full P2 property.")
        launch_option = "separate-user"

    notes = []
    if same_uid:
        notes.append(
            "honesty: IO-2 fails on this same-UID host; l3_claim_possible=False")
    notes.append(
        "readiness is detection only — no credential or session-policy change")

    return UidReadinessReport(
        orchestrator_uid=orch_uid,
        verifier_probe_uid=probe_uid,
        probe_ok=probe_ok,
        same_uid=same_uid,
        io2_pass=io2_pass,
        l3_claim_possible=io2_pass,
        launch_requirement=launch_requirement,
        launch_option=launch_option,
        captured_at=_now_iso(),
        notes=notes,
    )


def launch_options_documented() -> list[dict]:
    """Return the documented separate-UID launch options (0007 §1.2)."""
    return [
        {
            "option_id": oid,
            "title": title,
            "requirement": req,
            "isolation": iso,
        }
        for (oid, title, req, iso) in SEPARATE_UID_LAUNCH_OPTIONS
    ]


def main(argv=None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(
        description="L3 separate-UID readiness assessment (read-only, honest)")
    parser.add_argument("--orchestrator-uid", type=int, default=None)
    parser.add_argument("--verifier-probe-uid", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = assess_uid_readiness(
        orchestrator_uid=args.orchestrator_uid,
        verifier_probe_uid=args.verifier_probe_uid,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=1))
    else:
        print(f"orchestrator_uid={report.orchestrator_uid} "
              f"verifier_probe_uid={report.verifier_probe_uid} "
              f"probe_ok={report.probe_ok} same_uid={report.same_uid}")
        print(f"io2_pass={report.io2_pass} "
              f"l3_claim_possible={report.l3_claim_possible}")
        print(f"launch_requirement: {report.launch_requirement}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
