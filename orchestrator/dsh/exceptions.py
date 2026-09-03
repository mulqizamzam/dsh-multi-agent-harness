# orchestrator.dsh.exceptions — typed failure vocabulary for the DSH integration adapter
#
# Phase 3 / Session B. Scope: multi-agent-harness/ only.
#
# The adapter fails CLOSED: every delegation outcome that is not a validated
# success raises one of these typed errors, so the orchestrator's recovery path
# can branch without parsing prose. These names are the adapter's contract with
# the orchestrator runtime (runbooks 01/07/08 consume them).

from __future__ import annotations


class DSHError(Exception):
    """Base class for every DSH-integration-adapter error (fail-closed)."""


class RoleResolutionError(DSHError):
    """A role id cannot be resolved to an approved `subagent_<id>` instance.

    Raised for an unknown role, for the orchestrator itself (never a
    delegation target), and for D4/D7 composition drift (fail-closed)."""


class DelegationDenied(DSHError):
    """The delegation is not usable for this delegation attempt.

    Inactive / expired / revoked delegation, task scope outside the
    delegation's authorized resources (AUTH-INV-04), or a malformed authority
    record. A denied delegation is treated as ABSENT (AUTH-INV-05)."""


class ProhibitedDelegation(DelegationDenied):
    """V1 subdelegation DENY BY DEFAULT (DLG-003).

    Any actor other than the orchestrator attempting a specialist delegation,
    or any specialist-to-specialist delegation path, is denied here — not by a
    prompt."""


class DelegationTimeout(DSHError):
    """The child did not settle within its tool-call deadline."""


class DelegationAborted(DSHError):
    """The delegation was aborted (cancellation signal / DSH stopReason aborted)."""


class ChildFailure(DSHError):
    """The child failed or refused (DSH stopReason error / max-tokens / refusal).

    Carries the provider diagnostic and the raw outcome for the orchestrator's
    recovery record (runbook 07)."""

    def __init__(self, reason: str, *, diagnostic: str = "", outcome=None):
        super().__init__(f"child failure: {reason}")
        self.reason = reason
        self.diagnostic = diagnostic
        self.outcome = outcome


class MalformedResult(DSHError):
    """The child's structured output is not a valid TaskResult.

    Missing/invalid fields, unknown keys (schema `additionalProperties: false`),
    or a role-identity / task-id mismatch. The child's output is DATA — an
    invalid claim never becomes a collected result (AUTH-INV-13)."""
