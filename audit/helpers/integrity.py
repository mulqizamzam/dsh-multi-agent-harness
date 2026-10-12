# Audit integrity verification — audit/helpers/integrity.py
#
# Phase 1E / Session B. Provides hash-chain-based integrity verification for
# the append-only audit ledger. The chain lets a reader verify that no event
# has been truncated, reordered, or overwritten since the chain was persisted.
#
# Design:
#   The events file (audit/<project>/events.jsonl) stays SCHEMA-PURE: it holds
#   only events that validate against schemas/audit-event.schema.json. The
#   hash chain lives in a SIDE-CAR file `<events>.chain` (one JSON object per
#   line):
#     {"line": 1, "event_id": "event-...", "chain_hash": "<sha256 of previous
#      line's canonical JSON>", "cumulative_hash": "<sha256 of all lines up to
#      and including this one>"}
#   A tampered/truncated events file will produce a chain/cumulative hash
#   mismatch at the first divergent line when verified against the side-car.
#
#   compute_chain() returns the event dicts annotated with an in-memory
#   `_integrity` key (the event dicts on disk are never modified) and persists
#   the side-car. verify_chain() recomputes the chain and compares against the
#   persisted side-car, raising AuditIntegrityError on the first mismatch.
#
# The chain is OPTIONAL: an existing ledger without a .chain file can still be
# checked for truncation/ordering/uniqueness via verify_append_only() in
# append_log.py. The hash chain adds tamper DETECTION (not prevention, and not
# cryptographic authenticity — there is no signing key): a reader can detect
# that the ledger diverged from the writer's version.

import hashlib
import json
import os
import tempfile

from .append_log import AuditIntegrityError, read_events_strict

_GENESIS = "0" * 64  # SHA-256 is 64 hex chars


def chain_path_for(log_path) -> str:
    """The side-car chain file for a given events file."""
    return f"{log_path}.chain"


def _canonical_json(data) -> str:
    """Deterministic single-line JSON for hashing (sorted keys, no whitespace)."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _chain_hash(prev_canonical: str) -> str:
    return hashlib.sha256(prev_canonical.encode("utf-8")).hexdigest()


def _compute_cumulative(prev_cumulative: str, this_canonical: str) -> str:
    combined = prev_cumulative + this_canonical
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _read_sidecar(chain_path):
    """Read the side-car chain file; return None if missing."""
    if not os.path.exists(chain_path):
        return None
    rows = []
    with open(chain_path, "r") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise AuditIntegrityError(
                    f"chain side-car {chain_path}: corrupt line {lineno}: {e}") from e
    return rows


def _write_sidecar(chain_path, records):
    """Atomically write the side-car chain file (temp + fsync + replace)."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp", prefix=".chain_",
                                        dir=os.path.dirname(chain_path) or ".")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            for rec in records:
                f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, chain_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _annotate_events(events, records):
    """Return a NEW list of events, each annotated with `_integrity` from the
    corresponding chain record. The original event dicts are not modified."""
    result = []
    for ev, rec in zip(events, records):
        annotated = dict(ev)
        annotated["_integrity"] = rec
        result.append(annotated)
    return result


def compute_chain(log_path) -> list[dict]:
    """Read the ledger, compute the hash chain, persist the side-car, and
    return the events annotated with in-memory `_integrity` fields.

    The side-car is persisted so that a subsequent verify_chain() call can
    detect tampering.

    Args:
        log_path: path to the .jsonl file

    Returns:
        list of event dicts, each augmented with `_integrity`:
            {"line": int, "chain_hash": str, "cumulative_hash": str}

    Raises:
        AuditIntegrityError on corrupt lines (strict read)
    """
    events = read_events_strict(log_path)
    records = []
    prev_canonical = ""
    prev_cumulative = _GENESIS
    for i, event in enumerate(events, start=1):
        clean = {k: v for k, v in event.items() if k != "_integrity"}
        canon = _canonical_json(clean)
        ch = _chain_hash(prev_canonical)
        cum = _compute_cumulative(prev_cumulative, canon)
        records.append({
            "line": i,
            "event_id": event.get("event_id"),
            "chain_hash": ch,
            "cumulative_hash": cum,
        })
        prev_canonical = canon
        prev_cumulative = cum

    _write_sidecar(chain_path_for(log_path), records)
    return _annotate_events(events, records)


def verify_chain(log_path) -> list[dict]:
    """Verify the events file against its persisted side-car chain.

    Re-computes the chain over the current events and compares every record
    against the side-car. If the side-car is missing, it is computed and
    persisted (first-time verification — no baseline to compare against, so
    no tamper claim can be made).

    Args:
        log_path: path to the .jsonl file

    Returns:
        list of event dicts annotated with `_integrity` (verified)

    Raises:
        AuditIntegrityError on the first mismatch or corrupt line
    """
    events = read_events_strict(log_path)
    chain_path = chain_path_for(log_path)
    stored = _read_sidecar(chain_path)

    recomputed = []
    prev_canonical = ""
    prev_cumulative = _GENESIS
    for i, event in enumerate(events, start=1):
        clean = {k: v for k, v in event.items() if k != "_integrity"}
        canon = _canonical_json(clean)
        ch = _chain_hash(prev_canonical)
        cum = _compute_cumulative(prev_cumulative, canon)
        recomputed.append({
            "line": i,
            "event_id": event.get("event_id"),
            "chain_hash": ch,
            "cumulative_hash": cum,
        })
        prev_canonical = canon
        prev_cumulative = cum

    if stored is None:
        # First-time verification: no baseline to compare against. Persist the
        # current chain so future verifications have a baseline, and return the
        # annotated events (no tamper claim can be made).
        _write_sidecar(chain_path, recomputed)
        return _annotate_events(events, recomputed)

    # Compare against the persisted baseline
    if len(recomputed) != len(stored):
        raise AuditIntegrityError(
            f"chain length mismatch: events {len(recomputed)} != side-car "
            f"{len(stored)} (truncated or chain not updated)")

    for i, (rec, st) in enumerate(zip(recomputed, stored), start=1):
        for key in ("line", "chain_hash", "cumulative_hash"):
            if rec.get(key) != st.get(key):
                raise AuditIntegrityError(
                    f"event line {i}: {key} mismatch: computed {rec.get(key)!r} != "
                    f"stored {st.get(key)!r} (tampered/truncated)")

    return _annotate_events(events, recomputed)


def append_chained_event(log_path, event, encoder=None):
    """Append an audit event AND update the side-car chain.

    Args:
        log_path: path to the .jsonl file
        event: dict matching schemas/audit-event.schema.json
        encoder: optional custom JSONEncoder

    Returns:
        the `_integrity` dict of the last (appended) event, or None on empty

    Raises:
        AuditIntegrityError if the existing ledger is corrupt — the append is
        NOT performed, so a partial (durably written but unchained) event can
        never reach the ledger (FINAL architecture §4.7: never a partial
        append).
    """
    from .append_log import append_event
    # Validate the existing ledger BEFORE writing: appending first and only
    # then computing the chain would leave a durable but unchained event in
    # the ledger whenever compute_chain() fails, and every later append for
    # that project would then fail CORRUPTION_DETECTED.
    read_events_strict(log_path)
    append_event(log_path, event, encoder=encoder)
    events = compute_chain(log_path)
    return events[-1]["_integrity"] if events else None


def persist_chain(log_path) -> list[dict]:
    """Alias for compute_chain: compute + persist side-car, return annotated events."""
    return compute_chain(log_path)


def detect_truncation(log_path, known_cumulative_hash: str, known_line_count: int):
    """Detect if the ledger has been truncated since a known good state.

    Re-computes the chain and compares line count + final cumulative hash
    against caller-supplied known-good values (e.g. from the last persisted
    chain or an external marker).

    Args:
        log_path: path to the .jsonl file
        known_cumulative_hash: the cumulative_hash of the last line when the
            ledger was last verified (hex string, 64 chars)
        known_line_count: the line count at that time

    Returns:
        (ok: bool, problems: list[str])

    Raises:
        AuditIntegrityError on corrupt lines
    """
    problems = []
    events = read_events_strict(log_path)
    # recompute the chain in-memory (no side-car write needed for detection)
    prev_canonical = ""
    prev_cumulative = _GENESIS
    for i, event in enumerate(events, start=1):
        clean = {k: v for k, v in event.items() if k != "_integrity"}
        canon = _canonical_json(clean)
        cum = _compute_cumulative(prev_cumulative, canon)
        prev_canonical = canon
        prev_cumulative = cum

    actual_count = len(events)
    if actual_count < known_line_count:
        problems.append(
            f"truncation detected: {actual_count} lines < expected {known_line_count}")
        return False, problems
    if actual_count == known_line_count and events:
        if prev_cumulative != known_cumulative_hash:
            problems.append(
                f"hash mismatch at same line count: ledger may have been "
                f"overwritten (hash {prev_cumulative!r} != expected "
                f"{known_cumulative_hash!r})")
            return False, problems
    return True, problems