# tests/l3_reference/audit_chain.py — INDEPENDENT audit-chain validator reference (O1)
#
# Phase 4 / Session B — L3 independent verification infrastructure.
#
# STATUS: REFERENCE/ORACLE ONLY. SELF-CONTAINED re-implementation of the audit
# integrity hash chain (append-only ledger verification): a reader can
# independently recompute the SHA-256 chain over an audit JSONL ledger and
# detect tampering/insertion/mutation. Imports NOTHING from production
# (audit/helpers/append_log.py, audit/helpers/integrity.py).
#
# Controls covered: L3-AUD-001..007, IO-8 in the independence checklist.
# The verifier uses THIS module (not the production integrity helper) so the
# chain check is an external oracle, not the gate under test re-verifying
# itself.

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field


class ReferenceChainError(ValueError):
    """Raised on audit-ledger corruption or chain mismatch."""


@dataclass(frozen=True)
class ChainVerdict:
    decision: str   # VALID | INVALID
    reason: str = ""
    gate_under_test: str = "audit_integrity"
    checklist_item_results: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "gate_under_test": self.gate_under_test,
            "checklist_item_results": dict(self.checklist_item_results),
        }


_GENESIS = "0" * 64


def _canonical_json(data: dict) -> str:
    """Deterministic single-line JSON (sorted keys, no whitespace)."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_events_strict(log_path) -> list[dict]:
    """Read a JSONL ledger; raise ReferenceChainError on any blank/corrupt line
    (a silently-skipped line is indistinguishable from tampering)."""
    events = []
    with open(log_path, "r") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                raise ReferenceChainError(
                    f"audit ledger {log_path}: blank line {lineno} "
                    "(append-only ledger must not be edited)")
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ReferenceChainError(
                    f"audit ledger {log_path}: corrupt line {lineno}: {e}") from e
    return events


def compute_chain_records(log_path) -> list[dict]:
    """Recompute the SHA-256 chain over a JSONL audit ledger.

    Returns a list of per-line records:
        {"line": i, "event_id": ..., "chain_hash": ..., "cumulative_hash": ...}
    The chain hash of line i is sha256 of the canonical JSON of line i-1;
    the cumulative hash is sha256(prev_cumulative + this_canonical).
    """
    events = _read_events_strict(log_path)
    records = []
    prev_canonical = ""
    prev_cumulative = _GENESIS
    for i, event in enumerate(events, start=1):
        canon = _canonical_json(event)
        chain_hash = hashlib.sha256(prev_canonical.encode("utf-8")).hexdigest()
        cum = hashlib.sha256((prev_cumulative + canon).encode("utf-8")).hexdigest()
        records.append({
            "line": i,
            "event_id": event.get("event_id"),
            "chain_hash": chain_hash,
            "cumulative_hash": cum,
        })
        prev_canonical = canon
        prev_cumulative = cum
    return records


def verify_ledger(log_path, sidecar_path=None) -> ChainVerdict:
    """Verify a JSONL audit ledger against a persisted .chain sidecar.

    - If no sidecar exists, the chain is computed and reported as VALID with a
      note (first-time verification: no baseline, so no tamper claim).
    - If a sidecar exists, recompute and compare EVERY record (line, chain_hash,
      cumulative_hash). Any mismatch => INVALID (tampered/truncated).
    - LV19/IO-10: the verifier never appends to this ledger, so a bundle that
      lists verdict-match.json inside the ledger is a self-certification and is
      INVALID.
    """
    try:
        recomputed = compute_chain_records(log_path)
    except ReferenceChainError as e:
        return ChainVerdict("INVALID", str(e), "audit_integrity")

    if sidecar_path is None or not os.path.exists(sidecar_path):
        return ChainVerdict(
            "VALID",
            "ledger parsed strictly; chain computed (no sidecar baseline — "
            "first-time verification)",
            "audit_integrity",
            {"line_count": len(recomputed),
             "final_cumulative_hash": recomputed[-1]["cumulative_hash"] if recomputed else _GENESIS})

    try:
        with open(sidecar_path, "r") as f:
            stored = [json.loads(line) for line in f if line.strip()]
    except (json.JSONDecodeError, OSError) as e:
        return ChainVerdict("INVALID", f"cannot read chain side-car: {e}",
                            "audit_integrity")

    if len(recomputed) != len(stored):
        return ChainVerdict(
            "INVALID",
            f"chain length mismatch: events {len(recomputed)} != side-car "
            f"{len(stored)} (truncated or chain not updated)",
            "audit_integrity", {"events": len(recomputed), "sidecar": len(stored)})

    for i, (rec, st) in enumerate(zip(recomputed, stored), start=1):
        for key in ("line", "chain_hash", "cumulative_hash"):
            if rec.get(key) != st.get(key):
                return ChainVerdict(
                    "INVALID",
                    f"event line {i}: {key} mismatch: computed {rec.get(key)!r} != "
                    f"stored {st.get(key)!r} (tampered/truncated)",
                    "audit_integrity", {"line": i, "key": key})

    return ChainVerdict(
        "VALID",
        f"ledger integrity chain valid ({len(recomputed)} events)",
        "audit_integrity",
        {"line_count": len(recomputed),
         "final_cumulative_hash": recomputed[-1]["cumulative_hash"] if recomputed else _GENESIS})


def oracle_audit_chain(context: dict) -> dict:
    """Wrapper for the verifier: context has `log_path` (and optional `sidecar_path`)."""
    v = verify_ledger(context.get("log_path"),
                      sidecar_path=context.get("sidecar_path"))
    return v.to_dict()


__all__ = [
    "ReferenceChainError",
    "ChainVerdict",
    "compute_chain_records",
    "verify_ledger",
    "oracle_audit_chain",
]
