# control/recovery_hardening/restoration.py — Restoration verification
#
# Phase 5 / Session C. REC-003 support: independent restoration verification.
# The existing RecoveryController.verify_restoration requires evidence +
# verifier strings; this module adds a concrete, independent file-state check
# (sha256 before/after) so a rollback can be proven restored without trusting
# the executor's own claim. It is a HELPER for the recovery path — it does not
# replace the controller and never grants authority.

from __future__ import annotations

import hashlib
import os


class RestorationVerificationError(ValueError):
    """Restoration could not be independently verified (REC-003)."""


def file_sha256(path: str) -> str | None:
    """sha256 of a file; None when absent (absent-file restorations compare
    against None)."""
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_restoration_hashes(before: dict, after: dict,
                              *, task_id: str = "") -> None:
    """REC-003: verify the after-state matches the before-state for every
    tracked path.

    ``before`` / ``after``: {path: sha256|None}. A mismatch (or a path tracked
    in before but missing in after) fails verification.
    """
    problems = []
    for path, before_hash in (before or {}).items():
        after_hash = (after or {}).get(path)
        if after_hash != before_hash:
            problems.append(
                f"path {path!r}: before={before_hash!r} after={after_hash!r}")
    if problems:
        raise RestorationVerificationError(
            f"restoration verification failed (REC-003) task {task_id!r}: "
            + "; ".join(problems))


def capture_restoration_state(paths, *, base: str = "") -> dict:
    """Capture {path: sha256} for a set of paths (independent evidence)."""
    out = {}
    for p in paths or ():
        full = os.path.join(base, p) if base else p
        out[p] = file_sha256(full)
    return out


__all__ = ["RestorationVerificationError", "file_sha256",
           "verify_restoration_hashes", "capture_restoration_state"]
