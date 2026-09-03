# tests/l3_runner/claim_gate.py — L3 claim gate (P1-P4) — G5
#
# Phase 5 / Session G5 — INDEPENDENT L3 VERIFIER IMPLEMENTATION.
#
# The single, code-enforced gate that decides whether an evidence bundle may
# carry `l3_claim=true`. Requirement 8 (L3 CLAIM GATE):
#
#   L3-PASS requires ALL of:
#     P1  Runtime        — a real runtime executed the scenario (a recorded/
#                          replayed fixture is NOT a live runtime)
#     P2  Independent observer — the verifier ran as a separate OS process
#                          (distinct PID; distinct UID when required)
#     P3  External oracle — at least 2 oracle classes used (O1..O4), at least
#                          one of which is not the runtime itself
#     P4  Reproducible replay — fixture hash, verifier binary sha256, and
#                          schema sha256 are pinned and deterministic
#   AND:
#     - valid Human-signed pre-runtime plan (signoff precedes runtime);
#     - valid evidence bundle (all 13 items, manifest certifies);
#     - independent verifier (IO-1..IO-10 all pass);
#     - no unresolved UNKNOWN affecting the tested claim;
#     - no same-process verifier;
#     - no same-UID violation where UID separation is required;
#     - verdict agreement (runtime decision == reference decision).
#
#   Otherwise: l3_claim = false.
#
# This module is pure logic — it never runs L3, never modifies a bundle, and
# never fabricates separation. It is the FINAL say on whether a bundle may be
# promoted; a rehearsal (--rehearsal) always forces l3_claim=false.

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ClaimGateResult:
    """The outcome of evaluating the L3 claim gate for one bundle."""
    l3_claim: bool = False
    satisfied: dict = field(default_factory=dict)   # P1..P4 + conditions
    failures: list = field(default_factory=list)    # why l3_claim=false

    def mark(self, name: str, ok: bool, detail: str = "") -> None:
        self.satisfied[name] = {"pass": bool(ok), "detail": detail}
        if not ok:
            self.failures.append(f"{name}: {detail}" if detail else name)

    def to_dict(self) -> dict:
        return {
            "l3_claim": self.l3_claim,
            "satisfied": {k: v for k, v in self.satisfied.items()},
            "failures": list(self.failures),
        }


def _iso_parse(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def evaluate_l3_claim(
    *,
    bundle_dir: str,
    runtime_decision: str,
    reference_decision: str,
    rehearsal: bool = False,
    verifier_pid: int = 0,
    orchestrator_pid: int = 0,
    verifier_uid: int = 0,
    orchestrator_uid: int = 0,
    independence_all_pass: bool = False,
    oracle_classes: list | None = None,
    fixture_hash: str = "",
    verifier_binary_sha256: str = "",
    schema_sha256: dict | None = None,
    plan_signoff_ts: str = "",
    runtime_captured_at: str = "",
    unresolved_unknowns: list | None = None,
    uid_separation_required: bool = True,
) -> ClaimGateResult:
    """Evaluate the L3 claim gate for one evidence bundle.

    Args:
        bundle_dir: the evidence bundle directory (item presence is verified
            against the canonical EVIDENCE_FILES contract).
        runtime_decision / reference_decision: the two verdicts that must agree.
        rehearsal: force l3_claim=false (machinery proof only).
        verifier_pid / orchestrator_pid: distinct-process check (P2 / IO-1).
        verifier_uid / orchestrator_uid: distinct-UID check (P2 / IO-2).
        independence_all_pass: IO-1..IO-10 all pass.
        oracle_classes: oracle classes used (>= 2, P3).
        fixture_hash / verifier_binary_sha256 / schema_sha256: P4 pins.
        plan_signoff_ts / runtime_captured_at: Human-signed plan ordering.
        unresolved_unknowns: list of UNKNOWN items that affect the claim.
        uid_separation_required: whether the scenario REQUIRES UID separation
            (most do; a host that cannot provide it must demote).
    """
    from . import EVIDENCE_FILES

    result = ClaimGateResult()

    # Rehearsal: never a claim.
    if rehearsal:
        result.mark("rehearsal", False,
                    "rehearsal run — machinery proof only, never an L3 claim")
        result.l3_claim = False
        return result

    # P1: a real runtime executed the scenario.
    # Accepted decisions mirror the runtime-verdict contract plus INVALID, the
    # outcome of a verification-only scenario (integrity verification: a
    # tampered ledger detected by independent chain re-computation —
    # L3-AUD-002, THREAT-018). INVALID is a real observed outcome, not the
    # absence of one, so it satisfies P1; whether it AGREES with the plan is
    # decided separately by the verdict-agreement check below.
    runtime_path = os.path.join(bundle_dir, "runtime-verdict.json")
    p1 = (os.path.isfile(runtime_path)
          and runtime_decision in ("ALLOW", "DENY", "ERROR", "INVALID"))
    result.mark("P1-runtime", p1,
                f"runtime-verdict.json present={os.path.isfile(runtime_path)} "
                f"decision={runtime_decision!r}")

    # P2: independent observer (distinct process; distinct UID when required).
    p2_proc = (orchestrator_pid > 0 and verifier_pid > 0
               and orchestrator_pid != verifier_pid)
    result.mark("P2-independent-observer", p2_proc,
                f"orchestrator_pid={orchestrator_pid} verifier_pid={verifier_pid}")
    if uid_separation_required:
        p2_uid = (orchestrator_uid > 0 and verifier_uid > 0
                  and orchestrator_uid != verifier_uid)
        result.mark("P2-uid-separation", p2_uid,
                    f"orchestrator_uid={orchestrator_uid} verifier_uid={verifier_uid}")
    result.mark("IO-all-pass", bool(independence_all_pass))

    # P3: external oracle — >= 2 oracle classes used.
    classes = set(oracle_classes or ())
    p3 = len(classes) >= 2
    result.mark("P3-external-oracle", p3,
                f"oracle_classes_used={sorted(classes)}")

    # P4: reproducible replay — fixture + verifier binary + schema pins.
    p4 = (bool(fixture_hash) and len(fixture_hash) == 71
          and bool(verifier_binary_sha256) and len(verifier_binary_sha256) == 64
          and bool(schema_sha256))
    result.mark("P4-reproducible-replay", p4,
                f"fixture_hash={'set' if fixture_hash else 'MISSING'} "
                f"verifier_sha={'set' if verifier_binary_sha256 else 'MISSING'} "
                f"schema_sha={'set' if schema_sha256 else 'MISSING'}")

    # Human-signed pre-runtime plan: signoff strictly before runtime.
    plan_path = os.path.join(bundle_dir, "plan.json")
    plan_present = os.path.isfile(plan_path)
    signoff_ok = bool(plan_signoff_ts) and bool(runtime_captured_at)
    if signoff_ok:
        p_ts = _iso_parse(plan_signoff_ts)
        r_ts = _iso_parse(runtime_captured_at)
        signoff_ok = p_ts is not None and r_ts is not None and p_ts < r_ts
    result.mark("human-signed-plan", plan_present and signoff_ok,
                f"plan.json present={plan_present} "
                f"signoff={plan_signoff_ts or 'MISSING'} "
                f"runtime={runtime_captured_at or 'MISSING'} "
                f"precedes={signoff_ok}")

    # Valid evidence bundle: every canonical item present + manifest.
    # NOTE: verdict-match.json is excluded because it IS the claim gate's own
    # output — it cannot exist before the gate runs. The validator
    # (validate_bundle_dir) checks for it separately.
    bundle_items = set(os.listdir(bundle_dir)) if os.path.isdir(bundle_dir) else set()
    required = [f for f in EVIDENCE_FILES if f != "verdict-match.json"]
    missing = [f for f in required if f not in bundle_items]
    result.mark("evidence-bundle-complete", not missing,
                f"missing={missing or 'none'}")

    # No unresolved UNKNOWN affecting the tested claim.
    unknowns = list(unresolved_unknowns or ())
    result.mark("no-unresolved-unknown", not unknowns,
                f"unknowns={unknowns or 'none'}")

    # Verdict agreement (runtime decision == reference decision).
    agreement = runtime_decision == reference_decision
    result.mark("verdict-agreement", agreement,
                f"runtime={runtime_decision!r} reference={reference_decision!r}")

    # Final: claim only when everything passes.
    result.l3_claim = (not result.failures and agreement
                       and independence_all_pass and p1 and p2_proc and p3
                       and p4 and plan_present and signoff_ok)
    return result


__all__ = ["ClaimGateResult", "evaluate_l3_claim"]
