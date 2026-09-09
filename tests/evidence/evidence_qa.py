# tests/evidence/evidence_qa.py — Runtime evidence QA validator (structure only)
#
# Phase 3 / Session E. TEST-SUPPORT ONLY. Not production code.
#
# This module validates the STRUCTURE of a runtime-evidence bundle for the
# four live-runtime scenarios INT-01 / INT-07 / INT-11 / INT-12 (Phase 3 /
# Sessions D2, D3). It is a pure, dependency-free validator: it checks
# required fields, schema shape, hash references, provenance consistency,
# expected-vs-observed separation, evidence classification, and the
# per-scenario mandatory evidence defined in
# docs/testing/0002-runtime-evidence-qa-specification.md.
#
# It is NOT an L3 verifier:
#   - it never executes a control, a gate, or the runtime;
#   - it never claims L3 (a bundle that claims L3 without the P1-P4 property
#     set is REJECTED as a false claim);
#   - it never treats PASS, agent text, state, or audit as authority.
#
# The validator accepts the canonical contract shape and the D3 live harness
# output shape (LiveEvidenceRun.to_dict()); unknown top-level keys are
# warnings, never errors.

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field

from orchestrator.foundation.contracts import (
    SPECIALIST_ROLES as _CONTRACT_SPECIALIST_ROLES,
)

# ---------------------------------------------------------------------------
# Vocabulary (aligned with docs/testing/0002-runtime-evidence-qa-specification.md)
# ---------------------------------------------------------------------------

VALID_SCENARIOS = ("INT-01", "INT-07", "INT-11", "INT-12")
# Single source of truth is the contract tuple (PRD v0.2: 15 roles; ADR 0003).
SPECIALIST_ROLES = _CONTRACT_SPECIALIST_ROLES
EVIDENCE_SOURCES = (
    "AGENT-REPORTED",
    "RUNTIME-OBSERVED",
    "CONTROL-PLANE-DECISION",
    "INDEPENDENTLY-VERIFIED",
)
FAILURE_CLASSES = ("environment", "logic", "authorization", "unknown")
GATE_NAMES = ("risk", "evidence", "conflict", "badsector_review",
              "authority", "execution", "verification", "recovery")
STOP_REASONS = ("completed", "error", "aborted", "max-tokens", "refusal")
L3_PROPERTIES = ("p1_runtime", "p2_independent_observer",
                 "p3_external_oracle", "p4_reproducible")

# Write-class scenarios: a write (or a consequential execution) occurred, so
# artifact hashes are mandatory (R8).
WRITE_CLASS_SCENARIOS = ("INT-01", "INT-07")

_HASH_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class ValidationReport:
    """Result of one evidence-bundle validation.

    valid:
        False when any error is present (errors are rejection conditions).
    errors:
        Rejection conditions (R1..R15 + per-scenario). Non-empty → invalid.
    warnings:
        Non-rejecting observations (unknown keys, deprecated labels, etc.).
    """

    valid: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.errors.append(message)
        self.valid = False

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _dict_of(bundle: dict, key: str) -> dict:
    """Return bundle[key] when it is a dict, else {}."""
    v = bundle.get(key)
    return v if isinstance(v, dict) else {}


def _list_of(bundle: dict, key: str) -> list:
    """Return bundle[key] when it is a list, else []."""
    v = bundle.get(key)
    return v if isinstance(v, list) else []


def _non_empty_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _canonical_bundle_sha256(bundle: dict) -> str:
    """Deterministic sha256 of the canonical JSON of a bundle (for manifests)."""
    canon = json.dumps(bundle, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def file_sha256(path: str) -> str:
    """sha256 of a file on disk (for hash-reference verification)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------

def validate_evidence_bundle(bundle, scenario_id: str | None = None,
                             base: str | None = None) -> ValidationReport:
    """Validate the structure of one evidence bundle.

    Parameters
    ----------
    bundle:
        The evidence bundle dict (canonical contract or D3 harness output).
    scenario_id:
        Optional scenario override. When given, the bundle's own
        ``scenario_id`` must match (or be absent and the override is used).
    base:
        Optional workspace base for artifact-hash content verification. When
        supplied, each ``artifact_hashes`` entry whose relative path exists
        under ``base`` is checked against the declared sha256.

    Returns
    -------
    ValidationReport
        ``valid`` is True only when no rejection condition fired.
    """
    report = ValidationReport()

    # ---- R1: bundle is a dict -------------------------------------------
    if not isinstance(bundle, dict):
        report.fail(f"R1 evidence bundle must be a dict, got {type(bundle).__name__}")
        return report

    # ---- R2: scenario_id ------------------------------------------------
    sid = bundle.get("scenario_id") or scenario_id
    if scenario_id and bundle.get("scenario_id") and bundle.get("scenario_id") != scenario_id:
        report.fail(
            f"R2 scenario mismatch: bundle scenario_id {bundle.get('scenario_id')!r} "
            f"!= override {scenario_id!r}")
        return report
    if not isinstance(sid, str) or sid not in VALID_SCENARIOS:
        report.fail(f"R2 invalid or missing scenario_id: {sid!r}")
        return report

    # ---- R3: no false L3 claim ------------------------------------------
    l3_claim = bundle.get("l3_claim") is True
    l3_props = _dict_of(bundle, "l3_properties")
    if l3_claim:
        missing = [p for p in L3_PROPERTIES if l3_props.get(p) is not True]
        if missing:
            report.fail(
                f"R3 false L3 claim: l3_claim=true without P1-P4 evidence "
                f"(missing: {missing})")
    elif bundle.get("evidence_level") == "L3":
        report.fail("R3 evidence_level 'L3' requires l3_claim=true with P1-P4")

    # ---- R4: runtime identity -------------------------------------------
    ident = _dict_of(bundle, "identity")
    required_identity = ("task_id", "delegation_id", "actor", "role",
                         "flow_id", "dsh_session_id", "dsh_run_id")
    missing_ident = [k for k in required_identity
                     if not _non_empty_str(ident.get(k))]
    if missing_ident:
        report.fail(f"R4 missing runtime identity: {missing_ident}")

    # ---- R5: before/after state -----------------------------------------
    state = _dict_of(bundle, "state")
    pre = _dict_of(state, "pre_state")
    post = _dict_of(state, "post_state")
    if not pre:
        report.fail("R5 missing before state (state.pre_state)")
    if not post:
        report.fail("R5 missing after state (state.post_state)")
    for key in ("state_version_before", "state_version_after"):
        if not isinstance(state.get(key), int):
            report.fail(f"R5 missing/invalid state.{key}")

    # ---- R6: expected vs observed separation ----------------------------
    execu = _dict_of(bundle, "execution")
    if execu:
        has_expected = "expected" in execu
        has_observed = "observed" in execu
        if not (has_expected and has_observed):
            report.fail(
                "R6 missing expected/observed distinction in execution "
                f"(expected={has_expected}, observed={has_observed})")
        if has_expected and has_observed:
            exp = execu.get("expected")
            obs = execu.get("observed")
            if isinstance(exp, dict) and isinstance(obs, dict) and exp == obs:
                report.warn(
                    "execution.expected equals execution.observed verbatim — "
                    "expected/observed are not distinguished")

    # ---- R7: evidence cannot be agent-only ------------------------------
    items = _list_of(bundle, "evidence_items")
    if not items:
        report.fail("R7 evidence_items is empty")
    else:
        sources = {i.get("source") for i in items if isinstance(i, dict)}
        bad_sources = sorted(s for s in sources if s not in EVIDENCE_SOURCES)
        if bad_sources:
            report.fail(f"R7 invalid evidence source label(s): {bad_sources}")
        if not (sources & {"RUNTIME-OBSERVED", "CONTROL-PLANE-DECISION"}):
            report.fail("R7 evidence consists only of agent text "
                        "(no RUNTIME-OBSERVED or CONTROL-PLANE-DECISION item)")

    # ---- R15: INDEPENDENTLY-VERIFIED requires L3 -------------------------
    for i in items:
        if isinstance(i, dict) and i.get("source") == "INDEPENDENTLY-VERIFIED":
            if not (l3_claim and all(l3_props.get(p) is True for p in L3_PROPERTIES)):
                report.fail(
                    "R15 INDEPENDENTLY-VERIFIED evidence without L3 properties "
                    "(P1-P4) — false independence claim")

    # ---- R8/R9: artifact hashes -----------------------------------------
    hashes = _dict_of(bundle, "artifact_hashes")
    if sid in WRITE_CLASS_SCENARIOS and not hashes:
        report.fail(f"R8 missing artifact hashes for write-class scenario {sid}")
    for rel, h in hashes.items():
        if not isinstance(h, str) or not _HASH_RE.match(h):
            report.fail(f"R9 invalid hash format for {rel!r}: {h!r}")
        elif base is not None:
            # content verification against the on-disk artifact (optional)
            path = os.path.join(base, *str(rel).split("/"))
            if os.path.isfile(path) and file_sha256(path) != h.split(":", 1)[1].lower():
                report.fail(f"R9 artifact hash mismatch for {rel!r}")

    # ---- R10: PASS is never authority -----------------------------------
    auth = _dict_of(bundle, "authority")
    if auth.get("decision") == "ALLOW":
        delegation_ok = _non_empty_str(auth.get("delegation_id")) or \
            _non_empty_str(ident.get("delegation_id"))
        if not delegation_ok:
            report.fail(
                "R10 PASS treated as authority: authority decision ALLOW without "
                "a delegation id (AUTH-INV-09)")

    # ---- R11/R12: provenance children -----------------------------------
    prov = _dict_of(bundle, "provenance")
    children = [c for c in _list_of(prov, "children") if isinstance(c, dict)]
    if children:
        run_ids = [c.get("run_id") for c in children]
        dup = sorted({r for r in run_ids if _non_empty_str(r) and run_ids.count(r) > 1})
        if dup:
            report.fail(f"R11 duplicate run_id in provenance.children: {dup}")
        for c in children:
            role = c.get("role")
            if role not in SPECIALIST_ROLES:
                report.fail(f"R12 invalid child role: {role!r}")
            for k in ("task_id", "run_id", "tool_name", "stop_reason", "source"):
                if not _non_empty_str(c.get(k)):
                    report.fail(f"R12 provenance child missing {k!r}")

    # ---- R13: failure classification ------------------------------------
    failure = bundle.get("failure")
    if failure is not None:
        if not isinstance(failure, dict):
            report.fail("R13 failure must be a dict or null")
        else:
            cls = failure.get("classification")
            if cls not in FAILURE_CLASSES:
                report.fail(f"R13 invalid failure classification: {cls!r}")

    # ---- R14: per-scenario mandatory evidence ---------------------------
    _validate_scenario(bundle, sid, report)

    # ---- Warnings: unknown top-level keys (D3 harness superset OK) ------
    known_top = {
        "bundle_id", "scenario_id", "evidence_level", "l3_claim",
        "l3_properties", "created_at", "project", "identity", "state",
        "authority", "gates", "execution", "verification", "final_status",
        "audit_references", "artifact_hashes", "failure", "provenance",
        "evidence_items",
        # D3 harness output keys (LiveEvidenceRun.to_dict) — tolerated
        "phase", "flow_id", "started_at", "finished_at", "subtasks", "plans",
        "safety", "delegation", "held_version", "post_batch_version",
        "dispatch", "results", "recovery", "security", "errors", "outcome",
    }
    unknown = sorted(set(bundle) - known_top)
    if unknown:
        report.warn(f"unknown top-level key(s): {unknown}")

    return report


# ---------------------------------------------------------------------------
# Per-scenario mandatory evidence (docs/testing/0002 §3)
# ---------------------------------------------------------------------------

def _gate_decision(gates: list, name: str) -> dict | None:
    for g in gates:
        if isinstance(g, dict) and g.get("gate") == name:
            return g
    return None


def _validate_scenario(bundle: dict, sid: str, report: ValidationReport) -> None:
    gates = _list_of(bundle, "gates")
    auth = _dict_of(bundle, "authority")
    execu = _dict_of(bundle, "execution")
    verif = _dict_of(bundle, "verification")
    prov = _dict_of(bundle, "provenance")
    children = [c for c in _list_of(prov, "children") if isinstance(c, dict)]
    failure = bundle.get("failure")
    audit_refs = [r for r in _list_of(bundle, "audit_references")
                  if _non_empty_str(r)]
    items = [i for i in _list_of(bundle, "evidence_items") if isinstance(i, dict)]

    if sid == "INT-01":
        # full lifecycle proof
        for gate in ("risk", "evidence", "conflict", "badsector_review",
                     "authority", "verification"):
            if _gate_decision(gates, gate) is None:
                report.fail(f"R14 INT-01 missing gate record: {gate}")
        if auth.get("decision") != "ALLOW":
            report.fail("R14 INT-01 authority decision must be ALLOW")
        if execu.get("decision") != "ALLOW":
            report.fail("R14 INT-01 execution decision must be ALLOW")
        if verif.get("verdict") != "PASSED":
            report.fail("R14 INT-01 verification verdict must be PASSED")
        if bundle.get("final_status") != "COMPLETE":
            report.fail("R14 INT-01 final_status must be COMPLETE")
        if not audit_refs:
            report.fail("R14 INT-01 audit_references must be non-empty")
        srcs = {i.get("source") for i in items}
        if not (srcs & {"RUNTIME-OBSERVED", "CONTROL-PLANE-DECISION"}):
            report.fail("R14 INT-01 evidence must include runtime/control-plane items")

    elif sid == "INT-07":
        # planning ALLOW + execution DENY + no unauthorized mutation
        plan_auth = _gate_decision(gates, "authority")
        if plan_auth is not None and plan_auth.get("decision") != "ALLOW":
            report.fail("R14 INT-07 planning-time authority must be ALLOW")
        if auth.get("decision") != "DENY":
            report.fail("R14 INT-07 execution-time authority decision must be DENY")
        if bundle.get("final_status") == "COMPLETE":
            report.fail("R14 INT-07 must NOT be COMPLETE (revoked authority)")
        # no unauthorized mutation: children must not have executed
        if children:
            report.fail(
                "R14 INT-07 no unauthorized mutation: provenance.children must be "
                "empty (no subtask executed after revocation)")
        # audit must record the denial
        denials = [r for r in audit_refs if any(
            k in r for k in ("denial", "recheck", "authority"))]
        if not denials and not failure:
            report.fail(
                "R14 INT-07 missing execution_denial/authority_recheck audit "
                "reference or failure record")

    elif sid == "INT-11":
        # concurrent children, distinct identities, version preserved,
        # deterministic collection, provenance preserved
        if len(children) < 2:
            report.fail("R14 INT-11 requires >= 2 concurrent children")
        roles = [c.get("role") for c in children]
        if len(set(roles)) != len(roles):
            report.fail("R14 INT-11 children must have distinct roles")
        coll_order = _list_of(prov, "collection_order")
        if not coll_order:
            report.fail("R14 INT-11 missing deterministic collection_order")
        if children and len(coll_order) != len(children):
            report.fail(
                "R14 INT-11 collection_order length must match children length")
        state = _dict_of(bundle, "state")
        before = state.get("state_version_before")
        after = state.get("state_version_after")
        if isinstance(before, int) and isinstance(after, int) and before != after:
            report.fail(
                "R14 INT-11 state version changed across the batch — "
                "uncontrolled write (THREAT-021)")
        for c in children:
            if not _non_empty_str(c.get("run_id")):
                report.fail("R14 INT-11 child missing run_id (provenance)")

    elif sid == "INT-12":
        # actual child failure, propagation, recovery, no blind retry,
        # no authority expansion
        actual_failure = False
        if failure:
            actual_failure = True
        else:
            for c in children:
                if c.get("stop_reason") not in (None, "completed"):
                    actual_failure = True
            for r in _list_of(bundle, "results"):
                if isinstance(r, dict) and r.get("status") in ("FAILED", "BLOCKED"):
                    actual_failure = True
        if not actual_failure:
            report.fail("R14 INT-12 missing actual child failure evidence")
        if bundle.get("final_status") == "COMPLETE":
            report.fail("R14 INT-12 failure must propagate: final_status != COMPLETE")
        rec = failure.get("recovery") if isinstance(failure, dict) else None
        if isinstance(rec, dict):
            if rec.get("entered") is not True:
                report.fail("R14 INT-12 recovery must have entered: true")
            if rec.get("no_blind_retry") is not True:
                report.fail("R14 INT-12 missing no_blind_retry evidence")
            if rec.get("no_authority_expansion") is not True:
                report.fail("R14 INT-12 missing no_authority_expansion evidence")
        elif bundle.get("final_status") != "ESCALATED":
            report.fail(
                "R14 INT-12 missing recovery/escalation evidence "
                "(failure.recovery or final_status ESCALATED)")


# ---------------------------------------------------------------------------
# Convenience: file-based validation
# ---------------------------------------------------------------------------

def validate_bundle_file(path: str, *, scenario_id: str | None = None,
                         base: str | None = None) -> ValidationReport:
    """Validate an evidence bundle from a JSON file on disk."""
    with open(path, "r") as f:
        bundle = json.load(f)
    return validate_evidence_bundle(bundle, scenario_id=scenario_id, base=base)


__all__ = [
    "VALID_SCENARIOS", "SPECIALIST_ROLES", "EVIDENCE_SOURCES",
    "FAILURE_CLASSES", "GATE_NAMES", "STOP_REASONS", "L3_PROPERTIES",
    "ValidationReport", "validate_evidence_bundle", "validate_bundle_file",
    "file_sha256", "_canonical_bundle_sha256",
]
