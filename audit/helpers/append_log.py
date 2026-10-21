# Audit log helpers — append-only write + read
#
# The audit ledger is append-only: events are APPENDED to a JSON Lines file
# (one JSON object per line). Never overwrite, never edit. The single writer
# is the orchestrator/control plane (enforced by the execution gate and
# tool surface — see ADR 0002).
#
# File: audit/<project>/events.jsonl
# Each line: one JSON object matching schemas/audit-event.schema.json
#
# Hardening (Phase 1E / Session B):
#   - append_event now validates the event minimally (a JSON object, non-empty
#     event_id) before writing, so a malformed event can never enter the ledger.
#   - read_events_strict() raises on ANY corrupt/blank line instead of silently
#     skipping: a silently skipped line is indistinguishable from tampering.
#   - verify_append_only() detects ledger tampering (truncation, overwrite,
#     reordering) against a caller-supplied or embedded expectation.
#   - An audit entry NEVER grants authority (AUTH-INV-14); the helpers expose
#     audit_is_authority_source() which always returns False, and the authority
#     gate never reads audit as a grant.

import json, os, sys


class AuditIntegrityError(ValueError):
    """Raised when the audit ledger fails an integrity check (tampering or
    corruption detected — treat as a critical alert, not a silent skip)."""


def append_event(log_path, event, encoder=None):
    """Append one audit event to the JSON Lines log.

    Args:
        log_path: path to the .jsonl file
        event: dict matching schemas/audit-event.schema.json
        encoder: optional custom JSONEncoder

    Returns:
        True on success

    Raises:
        TypeError if `event` is not a dict / has no non-empty event_id
        IOError if the write fails
    """
    if not isinstance(event, dict):
        raise TypeError(f"audit event must be a dict, got {type(event).__name__}")
    if not (event.get("event_id") or "").strip():
        raise ValueError("audit event requires a non-empty event_id")

    # A bare relative filename ("events.jsonl") has no directory component;
    # os.makedirs("") raises FileNotFoundError, so fall back to ".".
    d = os.path.dirname(log_path)
    os.makedirs(d or ".", exist_ok=True)
    with open(log_path, "a") as f:
        line = json.dumps(event, cls=encoder, ensure_ascii=False, sort_keys=True) + "\n"
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    return True


def _iter_lines(log_path):
    """Yield (lineno, raw_line) for every physical line in the log."""
    if not os.path.exists(log_path):
        return
    with open(log_path, "r") as f:
        for lineno, line in enumerate(f, start=1):
            yield lineno, line


def read_events(log_path, decoder=None):
    """Read all events from a JSON Lines log.

    Lenient variant: corrupt/blank lines are skipped (legacy behavior).
    For integrity-sensitive reads use read_events_strict() instead.

    Args:
        log_path: path to the .jsonl file
        decoder: optional custom JSONDecoder

    Returns:
        List of decoded event dicts (empty list if missing/empty)
    """
    events = []
    for lineno, line in _iter_lines(log_path):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line, cls=decoder))
        except json.JSONDecodeError:
            continue  # lenient: skip corrupt lines (append-only, rare)
    return events


def read_events_strict(log_path, decoder=None):
    """Strict variant: raise AuditIntegrityError on ANY corrupt or blank line.

    A corrupt/blank line in an append-only ledger is evidence of tampering or
    truncation — it must surface, never be silently dropped.

    Args:
        log_path: path to the .jsonl file
        decoder: optional custom JSONDecoder

    Returns:
        List of decoded event dicts (empty list if missing)

    Raises:
        AuditIntegrityError on the first corrupt line
    """
    events = []
    for lineno, line in _iter_lines(log_path):
        if not line.strip():
            raise AuditIntegrityError(f"audit ledger {log_path}: blank line {lineno} "
                                      "(append-only ledger must not be edited)")
        try:
            events.append(json.loads(line, cls=decoder))
        except json.JSONDecodeError as e:
            raise AuditIntegrityError(
                f"audit ledger {log_path}: corrupt line {lineno}: {e}") from e
    return events


def read_events_by_class(log_path, event_class):
    """Read all events of a specific event_class from the log.

    Args:
        log_path: path to the .jsonl file
        event_class: string matching audit-event.event_class enum

    Returns:
        List of matching event dicts
    """
    return [e for e in read_events(log_path) if e.get("event_class") == event_class]


def verify_append_only(log_path, expected_event_ids=None, expected_count=None):
    """Verify the ledger is internally consistent with append-only semantics.

    Checks:
      1. Every line parses (strict read — a corrupt line fails the check).
      2. event_id uniqueness: the same event_id never appears twice (an
         overwrite/replay would duplicate or replace an id).
      3. timestamp monotonicity (non-decreasing) when events carry ISO
         timestamps — an out-of-order entry indicates reordering/tampering.
      4. If `expected_event_ids` is supplied, the ledger must contain exactly
         that set of ids in order (truncation detection — a ledger missing a
         previously observed event is a critical alert).
      5. If `expected_count` is supplied, the ledger must have exactly that
         many events (truncation/duplication detection).

    Args:
        log_path: path to the .jsonl file
        expected_event_ids: optional ordered list of event_ids previously
            observed (e.g. from a verified snapshot)
        expected_count: optional expected event count

    Returns:
        (ok: bool, problems: list[str])

    Raises:
        AuditIntegrityError if the file cannot be read (missing file is ok —
        an empty ledger is consistent).
    """
    problems = []
    events = read_events_strict(log_path)

    seen = set()
    prev_ts = None
    for e in events:
        eid = e.get("event_id")
        if not (eid and isinstance(eid, str)):
            problems.append(f"event without a string event_id: {e!r}")
            continue
        if eid in seen:
            problems.append(f"duplicate event_id {eid!r} (replay/overwrite?)")
        seen.add(eid)

        ts = e.get("timestamp")
        if isinstance(ts, str) and ts:
            norm = ts.replace("Z", "+00:00")
            try:
                from datetime import datetime, timezone
                parsed = datetime.fromisoformat(norm)
            except ValueError:
                problems.append(f"event {eid}: non-ISO timestamp {ts!r}")
                continue
            # Timestamps may mix naive and aware forms (a "Z"-suffixed event
            # followed by a bare one). Normalize naive values to UTC so the
            # monotonicity comparison cannot raise TypeError.
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if prev_ts is not None and parsed < prev_ts:
                problems.append(f"event {eid}: timestamp {ts} out of order")
            else:
                prev_ts = parsed

    if expected_event_ids is not None:
        actual_ids = [e.get("event_id") for e in events]
        if actual_ids != list(expected_event_ids):
            problems.append(
                f"event sequence mismatch: expected {list(expected_event_ids)}, "
                f"actual {actual_ids} (truncation/reorder?)")
    if expected_count is not None and len(events) != expected_count:
        problems.append(f"event count {len(events)} != expected {expected_count}")

    return (len(problems) == 0), problems


def audit_is_authority_source(event) -> bool:
    """AUTH-INV-14: an audit record can never grant authority.

    This ALWAYS returns False regardless of the event content. It exists so the
    invariant is code-enforced at the point where someone might be tempted to
    read audit as a grant: an audit entry describing an approval is a RECORD of
    an approval, not the approval itself. The authority gate reads only the
    delegation registry + Human approval records, never audit.

    Args:
        event: an audit event dict (content is irrelevant)

    Returns:
        False — always. Audit never grants.
    """
    return False
