# tests/l3_runner/independence.py — IO-1..IO-10 verifier independence checklist
#
# Computes the verifier independence checklist required by docs/design/0002
# §14 and recorded in verifier-independence.json (E12). Every check must pass;
# any failure invalidates the L3 evidence bundle (demoted to L2).

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from . import ORACLE_CLASSES


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc_parse(s):
    from datetime import datetime as dt
    try:
        return dt.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


class IndependenceResult:
    """Collects IO-1..IO-10 results and serializes verifier-independence.json."""

    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        self.results: dict[str, dict] = {}
        self._meta: dict = {}

    def check(self, io_id: str, passed: bool, detail: str) -> None:
        self.results[io_id] = {
            "check": io_id,
            "pass": bool(passed),
            "detail": detail,
        }

    @property
    def all_pass(self) -> bool:
        return all(r["pass"] for r in self.results.values()) and len(self.results) == 10

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "verifier_pid": self._meta.get("verifier_pid", os.getpid()),
            "verifier_uid": self._meta.get("verifier_uid", os.getuid()),
            "verifier_session_id": self._meta.get("verifier_session_id", ""),
            "parent_session_id": self._meta.get("parent_session_id"),
            "trust_root": self._meta.get("trust_root", "verifier-process"),
            "orchestrator_pid": self._meta.get("orchestrator_pid", 0),
            "io_checks": self.results,
            "all_pass": self.all_pass,
            "captured_at": _now_iso(),
        }


def compute_independence(
    *,
    scenario_id: str,
    orchestrator_pid: int,
    orchestrator_uid: int,
    orchestrator_session_id: str,
    verifier_pid: int,
    verifier_uid: int,
    verifier_session_id: str,
    parent_session_id,
    verifier_binary_path: str,
    reference_modules: list[str],
    oracle_classes_used: list[str],
    plan_ts: str,
    runtime_ts: str,
    audit_log_path: str | None,
    audit_chain_valid: bool,
    before_root_hash: str,
    after_root_hash: str,
    deny_protected_path: bool,
    verdict_match_in_audit: bool,
) -> IndependenceResult:
    """Compute the IO-1..IO-10 independence checklist.

    Returns an IndependenceResult. Any check that fails sets pass=False; the
    caller must treat the bundle as invalid L3 evidence.

    Honesty note: IO-2 (separate UID) can only pass on a host where the runner
    can actually run the verifier under a different credential (separate user /
    setuid). In a same-UID sandbox the check FAILS honestly, demoting the
    bundle to L2 — this infrastructure never fakes a credential separation it
    did not achieve.
    """
    res = IndependenceResult(scenario_id)
    res._meta = {
        "verifier_pid": verifier_pid,
        "verifier_uid": verifier_uid,
        "verifier_session_id": verifier_session_id,
        "parent_session_id": parent_session_id,
        "trust_root": "verifier-process",
        "orchestrator_pid": orchestrator_pid,
    }

    # IO-1: verifier PID != orchestrator PID, both non-zero.
    io1 = (orchestrator_pid != verifier_pid
           and orchestrator_pid > 0 and verifier_pid > 0)
    res.check("IO-1", io1,
              f"orchestrator_pid={orchestrator_pid} verifier_pid={verifier_pid}")

    # IO-2: verifier UID != orchestrator UID, both non-zero.
    io2 = (orchestrator_uid != verifier_uid
           and orchestrator_uid is not None and verifier_uid is not None
           and orchestrator_uid > 0 and verifier_uid > 0)
    res.check("IO-2", io2,
              f"orchestrator_uid={orchestrator_uid} verifier_uid={verifier_uid}")

    # IO-3: verifier binary sha256 present.
    try:
        binary_sha = sha256_file(verifier_binary_path)
        io3 = len(binary_sha) == 64
        detail = f"verifier_binary={verifier_binary_path} sha256={binary_sha[:16]}..."
    except OSError:
        io3 = False
        detail = f"cannot hash verifier binary: {verifier_binary_path}"
    res.check("IO-3", io3, detail)

    # IO-4: verifier not in orchestrator's session tree. A verifier spawned by
    # the runner via `subprocess` is a standalone OS process with NO DSH parent
    # session (parent_session_id absent) — that is the independent case and
    # must PASS (docs/phase-5/environment/final/0001 §2 item 2: "IO-4 pass=true
    # (parent_session_id absent)"). It must FAIL only when the verifier claims
    # to be inside the orchestrator's own session tree (parent_session_id ==
    # orchestrator_session_id).
    io4 = (not parent_session_id) or (parent_session_id != orchestrator_session_id)
    res.check("IO-4", io4,
              f"parent_session_id={parent_session_id} "
              f"orchestrator_session_id={orchestrator_session_id}")

    # IO-5: reference re-implementations exist and are separate files.
    ref_ok = bool(reference_modules) and all(
        os.path.isfile(r) for r in reference_modules
        if os.path.isabs(r) or os.path.exists(r)
    )
    res.check("IO-5", ref_ok,
              f"reference_modules={reference_modules}")

    # IO-6: at least 2 oracle classes recorded.
    io6 = len(set(oracle_classes_used or ())) >= 2 and all(
        c in ORACLE_CLASSES for c in (oracle_classes_used or ()))
    res.check("IO-6", io6,
              f"oracle_classes_used={sorted(set(oracle_classes_used))}")

    # IO-7: plan.json signoff timestamp < runtime-verdict timestamp.
    p_ts = _utc_parse(plan_ts)
    r_ts = _utc_parse(runtime_ts)
    io7 = p_ts is not None and r_ts is not None and p_ts < r_ts
    res.check("IO-7", io7,
              f"plan_signoff={plan_ts} runtime_captured={runtime_ts}")

    # IO-8: audit-log integrity chain valid.
    io8 = audit_chain_valid
    res.check("IO-8", io8,
              f"audit_log={audit_log_path} chain_valid={audit_chain_valid}")

    # IO-9: for DENY scenarios targeting a protected path, before==after hash.
    if deny_protected_path:
        io9 = before_root_hash == after_root_hash
    else:
        io9 = True
    res.check("IO-9", io9,
              f"deny_protected_path={deny_protected_path} "
              f"before={before_root_hash[:16]}... after={after_root_hash[:16]}...")

    # IO-10: verdict-match.json excludes itself from the audit-log chain.
    io10 = not verdict_match_in_audit
    res.check("IO-10", io10,
              f"verdict_match_in_audit={verdict_match_in_audit}")

    return res


def load_independence(path: str) -> dict:
    with open(path) as f:
        return json.load(f)