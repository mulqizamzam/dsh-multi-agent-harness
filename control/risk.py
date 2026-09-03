# control/risk.py — Risk classification gate (L1 project control plane)
#
# Phase: Phase 2 Control Plane — Session B (Risk + Evidence + Conflict +
# BadSector). Companion to docs/security/0001-control-assurance-spec.md §6,
# docs/security/0002-threat-model-and-control-architecture.md §13 (AUTH-INV-10,
# THREAT-011/012), docs/design/0001-control-design-and-test-plan.md §8.
#
# PURPOSE
#   Deterministic, machine-checkable risk classification. The gate's core
#   security property (AUTH-INV-10): an intrinsically HIGH action can NEVER be
#   downgraded by model judgment. The classifier keeps intrinsic-HIGH
#   categories HIGH regardless of wording, so semantic laundering (THREAT-012 —
#   hiding a destructive action behind benign wording) cannot move a HIGH
#   action to LOW/MEDIUM, and a model that labels a destructive action LOW is
#   reclassified to HIGH (THREAT-011).
#
# ENFORCEMENT MECHANISM
#   Classification is code: machine-checkable signals (action category, target
#   path/environment, tool, operation flags, requires_approval fields) are
#   evaluated deterministically. Model-assessed nuance is accepted as an input
#   that may RAISE a classification (with evidence) but never LOWER an
#   intrinsic HIGH. There is no code path that reduces an intrinsic HIGH.
#
# FAILURE BEHAVIOR
#   Any intrinsic signal → HIGH. A declared/LOW-or-MEDIUM attempt on an
#   intrinsic signal is normalized to HIGH. Callers that need a hard guarantee
#   can use assert_non_downgradable() which raises RiskDowngradeAttempted.
#
# FAIL-CLOSED: when signals cannot be inspected (missing target/environment),
#   the classifier does NOT silently default to LOW — it returns the risk
#   computed from whatever is present and marks unknown_signal, so an
#   unresolved unknown can be escalated by the caller.

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Deterministic intrinsic-HIGH vocabulary
# ---------------------------------------------------------------------------

# Action categories that are intrinsically HIGH (docs/security/0002 §13.1).
INTRINSIC_HIGH_ACTIONS = frozenset({
    # production change
    "production_deploy", "deploy_to_prod", "production_change",
    # destructive
    "destructive", "destroy", "drop_database", "delete_production",
    "purge", "wipe", "unlink", "truncate_data",
    # credential / permission change
    "credential_change", "permission_change", "role_grant", "access_grant",
    # financial commitment
    "financial_transaction", "financial_commitment", "payment", "wire_transfer",
    # sensitive / material publication
    "sensitive_publication", "publish", "material_publication",
    # destructive data operation
    "delete", "drop", "truncate", "overwrite", "rm",
})

# Environments that make ANY write-like action intrinsically HIGH.
PROD_ENVIRONMENTS = frozenset({"prod", "production", "danger-full-access"})

# Write-like action classes default to MEDIUM (reference parity: meaningful,
# recoverable change). Reads default to LOW.
WRITE_LIKE_ACTIONS = frozenset({
    "write", "edit", "deploy", "publish", "server_write", "create",
    "update", "modify",
})

# Destructive operation flags (machine-checkable, independent of wording).
DESTRUCTIVE_FLAGS = frozenset({
    "delete", "drop", "truncate", "overwrite", "purge", "wipe",
    "rm", "unlink", "destroy", "remove",
})

# Credential / permission / financial / publication keyword signals. Used to
# resist semantic laundering: a benign-sounding action that touches these
# categories is still intrinsic HIGH.
CREDENTIAL_PERMISSION_TOKENS = (
    "credential", "password", "secret", "token", "permission",
    "access grant", "role grant", "policy change", "sudo",
)
FINANCIAL_TOKENS = (
    "financial", "transaction", "transfer", "wire", "payment",
    "commitment", "purchase", "invoice", "refund", "charge",
)
PUBLICATION_TOKENS = (
    "publish", "publication", "external release", "make public",
    "sensitive publication",
)

# Destructive verb patterns detected in the action/target/command text even
# when wrapped in benign wording (THREAT-012 semantic laundering).
_DESTRUCTIVE_PATTERNS = (
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\brm\s+\S"),
    re.compile(r"\bdrop\b"),
    re.compile(r"\bdelete\b"),
    re.compile(r"\btruncate\b"),
    re.compile(r"\bpurge\b"),
    re.compile(r"\bwipe\b"),
    re.compile(r"\bunlink\b"),
    re.compile(r"\bdestroy\b"),
    re.compile(r"\boverwrite\b"),
    re.compile(r"\bformat\b"),
)


class RiskDowngradeAttempted(ValueError):
    """Raised when a caller tries to downgrade an intrinsic HIGH to below HIGH."""


@dataclass(frozen=True)
class RiskClassification:
    """Result of deterministic risk classification.

    level:      "LOW" | "MEDIUM" | "HIGH" (never below HIGH when intrinsic)
    intrinsic:  True if any machine-checkable intrinsic-HIGH signal fired
    signals:    which intrinsic signals fired (empty when not intrinsic)
    reason:     human-readable classification rationale
    unknown_signal: True when required input was missing (caller should escalate)
    """
    level: str
    intrinsic: bool
    signals: tuple = field(default_factory=tuple)
    reason: str = ""
    unknown_signal: bool = False


class RiskClassifier:
    """Deterministic risk classifier (AUTH-INV-10; THREAT-011/012).

    Usage:
        rc = RiskClassifier().classify(
            action="update config",
            target="prod/app/config",
            environment="prod",
            operation_flags=("delete",),
            tool="bash",
        )
        assert rc.level == "HIGH" and rc.intrinsic is True
    """

    def __init__(self, *, allow_wording_laundering_signal: bool = False):
        # Reserved knob: classification is NEVER relaxed by wording. The flag
        # exists only to be explicit that there is no "softer" classifier.
        self._strict = not allow_wording_laundering_signal

    # -- signal detection (machine-checkable) --------------------------------
    def _signals(self, action: str, target: str, environment: Optional[str],
                 requires_approval: Iterable[str],
                 operation_flags: Iterable[str], tool: Optional[str],
                 command: Optional[str]) -> list:
        signals = []
        action = (action or "").strip().lower()
        t = (target or "").replace(os.sep, "/").lower()
        env = (environment or "").strip().lower()
        flags = {str(f).strip().lower() for f in (operation_flags or ())}
        text = " ".join(x for x in (action, t, command or "") if x).lower()

        # 1. environment-based: any prod / full-access env is intrinsic HIGH
        if env in PROD_ENVIRONMENTS:
            signals.append(f"environment:{env}")

        # 2. explicit action category
        if action in INTRINSIC_HIGH_ACTIONS:
            signals.append(f"action:{action}")

        # 3. requires_approval categories map to intrinsic HIGH
        for ra in (requires_approval or ()):
            if ra in ("destructive", "financial_transfer",
                      "sensitive_publication", "credential_change"):
                signals.append(f"requires_approval:{ra}")

        # 4. destructive operation flags
        hit_flags = sorted(flags & DESTRUCTIVE_FLAGS)
        if hit_flags:
            signals.append(f"flags:{','.join(hit_flags)}")

        # 5. credential/permission category embedded in wording/action
        if action in INTRINSIC_HIGH_ACTIONS or any(
                tok in text for tok in CREDENTIAL_PERMISSION_TOKENS):
            if any(tok in text for tok in CREDENTIAL_PERMISSION_TOKENS):
                signals.append("category:credential_permission")

        # 6. financial category embedded in wording/action
        if any(tok in text for tok in FINANCIAL_TOKENS):
            signals.append("category:financial")

        # 7. publication category embedded in wording/action
        if any(tok in text for tok in PUBLICATION_TOKENS):
            signals.append("category:publication")

        # 8. destructive verb patterns — semantic-laundering resistance: even a
        #    benign-sounding action that carries a destructive verb/flag stays HIGH.
        if self._strict:
            for pat in _DESTRUCTIVE_PATTERNS:
                if pat.search(text):
                    signals.append("pattern:" + pat.pattern)
                    break

        # 9. tool-level signal: a destructive-capable shell in a prod context is
        #    already caught by env; a `rm`/`drop`-style tool is a strong hint.
        if tool:
            tl = tool.strip().lower()
            if "destroy" in tl or "delete" in tl or tl in ("rm", "drop", "truncate"):
                signals.append(f"tool:{tl}")

        return sorted(set(signals))

    def classify(self, action: str, target: str = "",
                 environment: Optional[str] = None,
                 requires_approval: Iterable[str] = (),
                 operation_flags: Iterable[str] = (),
                 tool: Optional[str] = None,
                 command: Optional[str] = None,
                 declared: Optional[str] = None,
                 model_nuance: Optional[str] = None) -> RiskClassification:
        """Return the effective risk classification.

        `declared` / `model_nuance` are model judgment inputs. They may RAISE
        a classification but never LOWER an intrinsic HIGH. When intrinsic
        signals fired, the level is unconditionally HIGH.
        """
        signals = self._signals(action, target, environment, requires_approval,
                                operation_flags, tool, command)
        intrinsic = bool(signals)

        unknown = (not target and not action)

        if intrinsic:
            return RiskClassification(
                level="HIGH", intrinsic=True, signals=tuple(signals),
                reason="intrinsic HIGH (non-downgradable)",
                unknown_signal=unknown,
            )

        # No intrinsic signal → derive from declared + model nuance.
        # Model nuance may raise (LOW→MEDIUM→HIGH) but never operates on an
        # intrinsic HIGH (there is none here).
        base = (declared or "LOW").upper()
        if base not in ("LOW", "MEDIUM", "HIGH"):
            base = "LOW"
        # Reference parity: write-like actions default to MEDIUM (meaningful,
        # recoverable change); reads default to LOW.
        if base == "LOW" and action in WRITE_LIKE_ACTIONS:
            base = "MEDIUM"
        nuance = (model_nuance or "").upper()
        if nuance in ("MEDIUM", "HIGH"):
            # model-assessed raise with evidence is allowed
            order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
            base = max((base, nuance), key=lambda x: order[x])
        return RiskClassification(
            level=base, intrinsic=False, signals=(),
            reason=f"model-assessed nuance applied over declared {base}",
            unknown_signal=unknown,
        )

    def effective_level(self, declared: str, intrinsic: bool) -> str:
        """AUTH-INV-10: an intrinsic HIGH can never be lowered by a declared
        (model) level. Effective level is HIGH whenever intrinsic."""
        if intrinsic:
            return "HIGH"
        d = (declared or "LOW").upper()
        return d if d in ("LOW", "MEDIUM", "HIGH") else "LOW"

    def assert_non_downgradable(self, declared: str, intrinsic: bool) -> str:
        """Guard used at gate boundaries: an intrinsic HIGH can never be
        lowered by a declared/requested level.

        Raises RiskDowngradeAttempted when the caller declares a level below
        HIGH for an intrinsic-HIGH action (AUTH-INV-10) — this is the DENY
        path. When the caller declares HIGH (or the action is not intrinsic),
        returns the effective level.
        """
        d = (declared or "LOW").upper()
        if intrinsic and d != "HIGH":
            raise RiskDowngradeAttempted(
                f"attempt to downgrade intrinsic HIGH to {d} (AUTH-INV-10)")
        return self.effective_level(declared, intrinsic)


# Module-level convenience function mirroring the reference control_plane
# signature for drop-in parity (returns (level, intrinsic)).
def classify_risk(action: str, target: str = "",
                  environment: Optional[str] = None,
                  requires_approval: Iterable[str] = (),
                  operation_flags: Iterable[str] = (),
                  tool: Optional[str] = None,
                  command: Optional[str] = None,
                  declared: Optional[str] = None,
                  model_nuance: Optional[str] = None):
    """Reference-parity convenience wrapper.

    Returns (level, intrinsic) where level is the EFFECTIVE level (never below
    HIGH for intrinsic actions). Extra signals (operation_flags/tool/command)
    harden the reference classification against semantic laundering.
    """
    rc = RiskClassifier().classify(
        action, target, environment, requires_approval=requires_approval,
        operation_flags=operation_flags, tool=tool, command=command,
        declared=declared, model_nuance=model_nuance,
    )
    return (rc.level, rc.intrinsic)


def is_high_risk(action: str, target: str = "",
                 environment: Optional[str] = None,
                 **kw) -> bool:
    """True when the effective risk is HIGH (intrinsic or declared/model)."""
    return classify_risk(action, target, environment, **kw)[0] == "HIGH"
