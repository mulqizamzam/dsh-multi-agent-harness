# audit/hardening/chain.py — Audit chain verification extensions
#
# Phase 5 / Session D. Extends audit/helpers/integrity.py with focused chain
# checks: sidecar comparison, missing-chain detection, forced recompute, and
# cumulative-hash verification. Reuses the existing primitives (compute_chain,
# verify_chain, chain_path_for); does NOT create a second ledger.

from __future__ import annotations

import json
import os

from audit.helpers.integrity import (
    chain_path_for, compute_chain, verify_chain, _canonical_json,
    _compute_cumulative, _GENESIS,
)
from audit.helpers.append_log import (
    read_events_strict, AuditIntegrityError,
)


class ChainVerificationError(AuditIntegrityError):
    """A chain verification failure (tampering / truncation)."""


def sidecar_exists(log_path: str) -> bool:
    return os.path.exists(chain_path_for(log_path))


def verify_chain_with_sidecar(log_path: str) -> list:
    """Verify the events file against its sidecar chain.

    Raises ChainVerificationError when the sidecar is missing (a ledger with
    events but no chain baseline cannot be verified — fail-closed).
    """
    if not os.path.exists(log_path):
        return []
    if not sidecar_exists(log_path):
        raise ChainVerificationError(
            f"audit chain verification: no sidecar chain for {log_path}; "
            f"cannot verify (fail-closed — run compute_chain to establish a "
            f"baseline first)")
    try:
        return verify_chain(log_path)
    except AuditIntegrityError as e:
        raise ChainVerificationError(f"audit chain verification failed: {e}")


def recompute_and_compare(log_path: str) -> dict:
    """Recompute the chain and compare cumulative hashes against the existing
    sidecar (if any). Returns {ok, problems}."""
    if not os.path.exists(log_path):
        return {"ok": True, "problems": []}
    events = read_events_strict(log_path)
    recomputed = []
    prev_canonical = ""
    prev_cumulative = _GENESIS
    for i, event in enumerate(events, start=1):
        clean = {k: v for k, v in event.items() if k != "_integrity"}
        canon = _canonical_json(clean)
        cum = _compute_cumulative(prev_cumulative, canon)
        recomputed.append({"line": i, "event_id": event.get("event_id"),
                           "cumulative_hash": cum})
        prev_canonical = canon
        prev_cumulative = cum

    problems = []
    sidecar = chain_path_for(log_path)
    if os.path.exists(sidecar):
        with open(sidecar) as f:
            rows = [json.loads(l) for l in f if l.strip()]
        if len(rows) != len(recomputed):
            problems.append(
                f"chain length mismatch: sidecar {len(rows)} vs events {len(recomputed)}")
        for row, rc in zip(rows, recomputed):
            if row.get("cumulative_hash") != rc["cumulative_hash"]:
                problems.append(
                    f"cumulative hash mismatch at line {rc['line']} "
                    f"(event {rc['event_id']!r})")
                break
    return {"ok": not problems, "problems": problems}


__all__ = ["ChainVerificationError", "sidecar_exists",
           "verify_chain_with_sidecar", "recompute_and_compare"]
