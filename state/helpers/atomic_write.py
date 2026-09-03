# Atomic write / safe read / compare-and-swap helpers
#
# Pattern (atomic write):
#   1. Write to a temp file in the same directory (same filesystem -> rename is atomic)
#   2. os.fsync() the temp file
#   3. os.replace() temp -> target (atomic on POSIX)
#   4. fsync the parent directory (optional, for durability)
#
# Pattern (safe read):
#   1. Read the file
#   2. Return None if missing / corrupt (fail-closed -- never return partial data)
#   3. JSON-decode and return
#
# Pattern (compare-and-swap):
#   1. Read current version
#   2. Compare with expected_version
#   3. If match: atomic_write with bumped version
#   4. If mismatch: raise or return False (caller re-reads and re-validates)
#
# Hardening (Phase 1E / Session B):
#   - defense-in-depth path guard: reject targets that escape the intended
#     directory (`..`, absolute-vs-relative confusion, NUL bytes) BEFORE any
#     filesystem access, so a helper call can never write outside its scope
#     even if the caller forgot to run the execution gate first
#   - pre-serialization check: verify `data` is JSON-serializable BEFORE
#     opening any temp file, so a bad payload cannot leave a stray temp file
#   - size cap: refuse to write or read a document larger than MAX_DOC_BYTES
#     (protects the runtime from unbounded state/audit documents)
#   - CAS now enforces STRICT MONOTONIC versioning: the new version must equal
#     expected_version + 1. A stale writer that passes any other version is
#     refused (THREAT-021 lost-update / THREAT-022 stale-recovery protection).

import json
import os
import tempfile

ATOMIC_TEMP_DIR = None  # set by the caller or defaults to same directory

# Defense-in-depth cap on the size of any single state document. Prevents a
# corrupted/bloated file from exhausting memory during read or silently
# producing an oversized state document during write.
MAX_DOC_BYTES = 16 * 1024 * 1024  # 16 MiB


class StatePathError(ValueError):
    """Raised when a target path is malformed or escapes the allowed scope."""


def _atomic_temp_dir(target_path):
    """Return the directory for temp files — same filesystem as target."""
    return ATOMIC_TEMP_DIR or os.path.dirname(os.path.abspath(target_path))


def _guard_target(path, base=None):
    """Defense-in-depth path guard (workspace-write scope).

    Rejects:
      - non-string / empty / NUL-byte targets (fail-closed)
      - targets that escape `base` (or the target's own parent directory when
        no base is given) via `..`, symlink-resolved escapes, or absolute
        paths when a base is expected relative

    Returns the canonical absolute target path.

    This is a BELT-AND-SUSPENDERS check. The authoritative path enforcement is
    the execution gate (control/execution_gate.py, ADR 0002); this helper-level
    guard ensures a state write cannot silently land outside its directory even
    if a future caller bypasses the gate.
    """
    if path is None or not isinstance(path, str) or not path.strip():
        raise StatePathError(f"malformed path: {path!r}")
    if "\x00" in path:
        raise StatePathError("malformed path: NUL byte")

    if base is None:
        base = os.path.dirname(os.path.abspath(path))
    base_abs = os.path.abspath(base)

    # Resolve the deepest existing ancestor for symlink safety (mirrors the
    # execution gate's realpath handling so a dangling symlink cannot smuggle
    # a path outside the base).
    t = path if os.path.isabs(path) else os.path.join(base_abs, path)
    lex = os.path.normpath(os.path.abspath(t))
    if os.path.lexists(lex):
        real = os.path.realpath(lex)
    else:
        probe = lex
        while not os.path.lexists(probe) and probe != os.path.dirname(probe):
            probe = os.path.dirname(probe)
        head = os.path.realpath(probe) if os.path.lexists(probe) else os.path.abspath(probe)
        tail = lex[len(probe):] if lex.startswith(probe) else ""
        real = os.path.normpath(head + tail)

    base_real = os.path.realpath(base_abs)
    try:
        within = os.path.commonpath([real, base_real]) == base_real
    except ValueError:
        within = False
    if not within:
        raise StatePathError(f"path escapes allowed directory: {path!r}")
    return real


def _check_serializable(data):
    """Raise TypeError if `data` is not JSON-serializable (checked first)."""
    # Cheap recursive probe mirrors json.dumps' serializability without writing
    # anything to disk yet.
    try:
        json.dumps(data, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as e:
        raise TypeError(f"data not JSON-serializable: {e}") from e


def atomic_write(path, data, encoder=None, base=None):
    """Write JSON `data` to `path` atomically: temp -> fsync -> replace.

    Args:
        path: target file path (string)
        data: JSON-serializable Python object
        encoder: optional custom JSONEncoder subclass
        base: optional authorized directory the target must stay inside.
            Defaults to the target's own parent directory (a no-op containment
            check); pass an explicit base (e.g. the workspace root or a state
            directory) to get real traversal protection.

    Returns:
        True on success

    Raises:
        StatePathError if the path escapes the allowed directory
        TypeError if `data` is not JSON-serializable
        IOError if the write fails (partial state is never left at target_path)
    """
    target = _guard_target(path, base=base)
    _check_serializable(data)

    blob = json.dumps(data, cls=encoder, indent=2, ensure_ascii=False, sort_keys=True)
    if len(blob.encode("utf-8")) > MAX_DOC_BYTES:
        raise ValueError(f"serialized document exceeds MAX_DOC_BYTES ({MAX_DOC_BYTES})")

    tmp_dir = _atomic_temp_dir(target)
    os.makedirs(tmp_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tmp", prefix=".atomic_",
        dir=tmp_dir, delete=False
    ) as f:
        tmp_path = f.name
        f.write(blob)
        f.flush()
        os.fsync(f.fileno())

    try:
        os.replace(tmp_path, target)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # fsync the parent directory for durability
    try:
        fd = os.open(os.path.dirname(target), os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except OSError:
        pass  # best-effort directory fsync

    return True


def safe_read(path, decoder=None):
    """Read and JSON-decode `path`. Return None on missing/corrupt (fail-closed).

    Args:
        path: file path (string)
        decoder: optional custom JSONDecoder

    Returns:
        Decoded Python object, or None
    """
    if not os.path.exists(path):
        return None
    try:
        size = os.path.getsize(path)
        if size > MAX_DOC_BYTES:
            return None  # oversized -> treat as corrupt (fail-closed)
        with open(path, "r") as f:
            return json.load(f, cls=decoder)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def compare_and_swap(path, expected_version, new_data, version_key="version"):
    """Atomically write `new_data` iff `path`'s current version == expected_version.

    This is the CAS (compare-and-swap) primitive for state concurrency.

    Hardened: the written version is REQUIRED to be exactly
    `expected_version + 1` (strict monotonic). A stale writer that supplies a
    different version is refused (returns (False, current_version)), so a
    version can never be reused or skipped silently (THREAT-021/022).

    Args:
        path: target file path
        expected_version: expected current version (int)
        new_data: replacement data dict (must include `version_key`)
        version_key: key in data for the version field (default "version")

    Returns:
        (True, new_version) on success
        (False, current_version) on mismatch (caller re-reads, re-validates, retries)

    Raises:
        StatePathError if the path escapes the allowed directory
        ValueError if the current version is not an integer, or if
            new_data[version_key] is not a valid strictly-monotonic successor
    """
    current = safe_read(path)
    current_version = current.get(version_key, 0) if current else 0

    if not isinstance(current_version, int):
        raise ValueError(f"non-integer version at {path}: {current_version!r}")

    if current_version != expected_version:
        return False, current_version

    # Strict monotonicity: the new version must be exactly expected+1. Writing
    # anything else (reuse, skip) would break the optimistic-concurrency chain.
    if version_key in new_data:
        provided = new_data[version_key]
        if not isinstance(provided, int) or provided != expected_version + 1:
            raise ValueError(
                f"CAS requires monotonic version {expected_version + 1}, got {provided!r} "
                f"at {path}")
        new_version = provided
    else:
        new_version = expected_version + 1
        new_data[version_key] = new_version

    atomic_write(path, new_data)
    return True, new_version
