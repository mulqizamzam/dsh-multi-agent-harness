"""Recovery hardening — idempotency guard, staleness detection, restoration verification, budget enforcement.

Phase 5 / Session C. Extends the existing `control/recovery.py` and
`state/helpers/recovery.py` where concrete gaps exist. Does NOT duplicate the
existing RecoveryController or RecoveryRecord; each module is a focused
extension that imports and wraps the existing primitives.
"""