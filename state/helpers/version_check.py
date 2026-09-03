# Version-check helpers for project state
#
# Project state documents carry a monotonic `version` integer. Every write
# checks that the writer's expected version matches the current version
# (compare-and-swap). This prevents lost updates from parallel workers
# (THREAT-021) and stale-state recovery (THREAT-022).
#
# See state/helpers/atomic_write.py for the CAS write primitive.
#
# Hardening (Phase 1E / Session B):
#   - validate_version_monotonic(): a successor version must be EXACTLY
#     current+1 (strict monotonicity — versions can never be reused or skipped)
#   - assert_current_version(): raises on stale reads instead of returning a
#     bool, for critical paths that must fail loudly
#   - is_stale(): combines the equality check with an explicit reason, so a
#     stale read is not just detectable but diagnosable

import os


class StaleStateError(ValueError):
    """Raised when a critical read/transition observes a stale version."""


def read_version(path, version_key="version"):
    """Read the version field from a JSON file at `path`.

    Args:
        path: file path
        version_key: key in the JSON for the version (default "version")

    Returns:
        version integer, or 0 if the file is missing/corrupt (fail-closed)
    """
    from .atomic_write import safe_read
    data = safe_read(path)
    if data is None:
        return 0
    v = data.get(version_key, 0)
    return v if isinstance(v, int) else 0


def bump_version(data, version_key="version"):
    """Increment the version key in `data` in-place.

    Args:
        data: mutable dict
        version_key: key for the version field

    Returns:
        The new version integer
    """
    current = data.get(version_key, 0)
    new_v = (current if isinstance(current, int) else 0) + 1
    data[version_key] = new_v
    return new_v


def validate_version_monotonic(current_version, next_version):
    """Verify that `next_version` is a valid successor of `current_version`.

    Strict monotonicity: `next_version` must equal `current_version + 1`.
    Reused or skipped versions break the optimistic-concurrency chain
    (THREAT-021 lost update / THREAT-022 stale recovery).

    Args:
        current_version: the version currently committed (int)
        next_version: the version a writer proposes (int)

    Returns:
        True when strictly monotonic

    Raises:
        ValueError when either version is not an integer, or when
            `next_version` is not exactly `current_version + 1`
    """
    if not isinstance(current_version, int):
        raise ValueError(f"current_version must be an integer, got {current_version!r}")
    if not isinstance(next_version, int):
        raise ValueError(f"next_version must be an integer, got {next_version!r}")
    if next_version != current_version + 1:
        raise ValueError(
            f"non-monotonic version: current {current_version}, proposed {next_version} "
            f"(must be {current_version + 1})")
    return True


def validate_version_staleness(path, expected_version, version_key="version"):
    """Check that the file at `path` has NOT been modified since `expected_version`.

    This is the read-side staleness check (not a CAS write). Use it to detect
    stale state before planning or before passing data to a parallel worker.

    Args:
        path: file path
        expected_version: the version the caller read
        version_key: key for the version field

    Returns:
        True if current version matches expected
        False if stale (caller must re-read and re-validate authority)
    """
    current_version = read_version(path, version_key)
    return current_version == expected_version


def is_stale(path, expected_version, version_key="version"):
    """Diagnosable staleness report: returns (stale: bool, current, expected, reason).

    Like validate_version_staleness but returns a structured result so a stale
    read can be audited with a reason (missing file, version mismatch).

    Args:
        path: file path
        expected_version: the version the caller read
        version_key: key for the version field

    Returns:
        (False, current_version, expected_version, "") when current
        (True, current_version, expected_version, reason) when stale
    """
    current_version = read_version(path, version_key)
    if current_version == expected_version:
        return False, current_version, expected_version, ""
    if current_version == 0:
        reason = "state file missing or corrupt (treated as absent)"
    elif current_version < expected_version:
        reason = "state is OLDER than expected (rolled back or replaced)"
    else:
        reason = "state is NEWER than expected (lost update detected)"
    return True, current_version, expected_version, reason


def assert_current_version(path, expected_version, version_key="version"):
    """Fail loudly when the file at `path` is not at `expected_version`.

    For critical paths (authority re-check before execution, recovery
    re-validation) a silent staleness is dangerous — this raises
    StaleStateError so the caller cannot proceed on stale state.

    Args:
        path: file path
        expected_version: the version the caller read
        version_key: key for the version field

    Returns:
        The confirmed current version (== expected_version)

    Raises:
        StaleStateError when the file is missing/corrupt/out-of-version
    """
    stale, current, expected, reason = is_stale(path, expected_version, version_key)
    if stale:
        raise StaleStateError(
            f"stale state at {path}: {reason} (current={current}, expected={expected})")
    return current
