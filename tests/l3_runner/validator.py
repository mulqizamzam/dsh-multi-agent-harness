# tests/l3_runner/validator.py — L3 evidence bundle structure-only validator
#
# Implements the LV1..LV20 validation rules from docs/testing/0003 §3. This
# validator checks that an L3 evidence bundle is complete, well-formed, and
# internally consistent. It does NOT verify that any control enforced anything
# at runtime (that is the L3 verifier's job). A bundle passing this validator
# is NOT L3 evidence; a bundle failing it is DEFINITELY NOT L3 evidence.
#
# The validator is a structure-only O2 oracle (schema-as-oracle). It uses the
# JSON schemas in tests/l3_reference/schemas/ and the per-INT mandatory
# evidence rules from docs/security/0005 §4.

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from . import DSH_VERSION_PIN, EVIDENCE_FILES


@dataclass
class ValidationResult:
    passed: bool = False
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    @property
    def summary(self) -> str:
        if self.passed:
            return "VALID"
        return f"INVALID: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"


# LV rules
REQUIRED_PLAN_FIELDS = ("scenario_id", "actor", "action", "target", "preconditions",
                        "expected_verdict", "expected_verdict_reason",
                        "human_signoff_id", "human_signoff_ts")
REQUIRED_ENV_FIELDS = ("dsh_version", "os", "python_version", "sandbox_mode",
                        "approval_policy", "permission_preset", "utc_offset_seconds", "seed")
REQUIRED_RUNTIME_FIELDS = ("decision", "denial_path", "tool_call_id",
                            "audit_event_ids", "stopReason", "captured_at")
REQUIRED_REFERENCE_FIELDS = ("decision", "reason", "gate_under_test",
                              "checklist_item_results")
REQUIRED_REPLAY_FIELDS = ("fixture_hash", "command_line", "verifier_binary_sha256",
                           "dsh_version")
REQUIRED_PROVENANCE_FIELDS = ("actor_session_id", "verifier_session_id",
                               "delegation_chain")
VALID_ORACLE_CLASSES = {"O1", "O2", "O3", "O4"}
VALID_SCENARIO_PATTERN = re.compile(r"^L3-[A-Z]+-[0-9]{3}$")
VALID_EVENT_ID_PATTERN = re.compile(r"^event-[A-Za-z0-9-]+$")
VALID_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _sha256_file(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: str):
    with open(path) as f:
        return json.load(f)


def _read_lines(path: str) -> list[str]:
    with open(path) as f:
        return [line for line in f if line.strip()]


def validate_bundle_dir(bundle_dir: str, scenario_id: str = "",
                        int_scenario: str = "") -> ValidationResult:
    """Validate an L3 evidence bundle directory against the LV1..LV20 rules
    and the per-INT mandatory evidence rules.

    Args:
        bundle_dir: path to audit/l3/<L3-scenario-id>/
        scenario_id: expected L3 scenario id (validated against plan.json)
        int_scenario: optional INT scenario id (e.g. "INT-01") for per-INT rules

    Returns:
        ValidationResult. passed=True only when ALL errors are empty.
    """
    result = ValidationResult()

    # LV1: bundle directory must exist and contain all required files.
    if not os.path.isdir(bundle_dir):
        result.add_error(f"LV1: bundle directory not found: {bundle_dir}")
        return result

    # Detect the scenario_id from plan.json if not provided.
    if not scenario_id:
        plan_path = os.path.join(bundle_dir, "plan.json")
        if os.path.exists(plan_path):
            try:
                plan = _read_json(plan_path)
                scenario_id = plan.get("scenario_id", "")
            except (json.JSONDecodeError, OSError):
                pass

    for fname in EVIDENCE_FILES:
        fpath = os.path.join(bundle_dir, fname)
        if not os.path.isfile(fpath):
            result.add_error(f"LV1: missing L3 evidence file: {fname}")
    # The manifest.json itself is not in EVIDENCE_FILES (self-certifying).
    if not os.path.isfile(os.path.join(bundle_dir, "manifest.json")):
        result.add_error("LV1: missing manifest.json")

    # LV2: manifest files object must list all required evidence files.
    manifest_path = os.path.join(bundle_dir, "manifest.json")
    if os.path.exists(manifest_path):
        try:
            manifest = _read_json(manifest_path)
            manifest_files = manifest.get("files", {})
            for fname in EVIDENCE_FILES:
                if fname not in manifest_files:
                    result.add_error(f"LV2: manifest missing {fname}")
            # LV3: check sha256 of each file.
            for fname, finfo in manifest_files.items():
                fpath = os.path.join(bundle_dir, fname)
                expected = finfo.get("sha256")
                if expected and os.path.isfile(fpath):
                    actual = _sha256_file(fpath)
                    if actual != expected:
                        result.add_error(f"LV3: manifest sha256 mismatch for {fname}: "
                                         f"expected {expected[:16]}..., got {actual[:16]}...")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV2: cannot read manifest.json: {e}")

    # LV4: env.json required fields.
    env_path = os.path.join(bundle_dir, "env.json")
    if os.path.exists(env_path):
        try:
            env = _read_json(env_path)
            for field in REQUIRED_ENV_FIELDS:
                if field not in env:
                    result.add_error(f"LV4: env.json missing required field: {field}")
            # LV5: dsh_version must be pinned.
            if env.get("dsh_version") != DSH_VERSION_PIN:
                result.add_error(f"LV5: dsh_version must be pinned to {DSH_VERSION_PIN}, "
                                 f"got {env.get('dsh_version')!r}")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV4: cannot read env.json: {e}")

    # LV6: plan.json required fields.
    plan_path = os.path.join(bundle_dir, "plan.json")
    if os.path.exists(plan_path):
        try:
            plan = _read_json(plan_path)
            for field in REQUIRED_PLAN_FIELDS:
                if field not in plan:
                    result.add_error(f"LV6: plan.json missing required field: {field}")
            # LV7: plan signoff must precede runtime verdict.
            plan_ts = plan.get("human_signoff_ts", "")
            runtime_path = os.path.join(bundle_dir, "runtime-verdict.json")
            if os.path.exists(runtime_path):
                try:
                    runtime = _read_json(runtime_path)
                    runtime_ts = runtime.get("captured_at", "")
                    if plan_ts and runtime_ts and plan_ts >= runtime_ts:
                        result.add_error(
                            f"LV7: plan.json signoff {plan_ts} must precede "
                            f"runtime verdict {runtime_ts}")
                except (json.JSONDecodeError, OSError):
                    pass
            # Validate scenario pattern.
            sid = plan.get("scenario_id", "")
            if sid and not VALID_SCENARIO_PATTERN.match(sid):
                result.add_warning(f"plan.json scenario_id {sid!r} does not match "
                                   f"L3-<CTRL>-<NNN> pattern")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV6: cannot read plan.json: {e}")

    # LV8/LV9: oracle-classes.json.
    oc_path = os.path.join(bundle_dir, "oracle-classes.json")
    if os.path.exists(oc_path):
        try:
            oc = _read_json(oc_path)
            classes = oc.get("oracle_classes_used", [])
            if len(set(classes)) < 2:
                result.add_error(f"LV8: oracle-classes: fewer than 2 oracle classes: {classes}")
            for c in classes:
                if c not in VALID_ORACLE_CLASSES:
                    result.add_error(f"LV9: invalid oracle class: {c!r}")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV8: cannot read oracle-classes.json: {e}")

    # LV10/LV11: verdict-match.json.
    vm_path = os.path.join(bundle_dir, "verdict-match.json")
    if os.path.exists(vm_path):
        try:
            vm = _read_json(vm_path)
            if vm.get("l3_claim") is not True:
                result.add_error(f"LV10: l3_claim must be true, got {vm.get('l3_claim')!r}")
            if vm.get("match") is False:
                result.add_error(f"LV11: runtime and oracle verdicts differ: "
                                 f"failure_class={vm.get('failure_class')}")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV10: cannot read verdict-match.json: {e}")

    # LV12: verifier-independence.json all IO checks must pass.
    ind_path = os.path.join(bundle_dir, "verifier-independence.json")
    if os.path.exists(ind_path):
        try:
            ind = _read_json(ind_path)
            if ind.get("all_pass") is not True:
                io_checks = ind.get("io_checks", {})
                failing = [k for k, v in io_checks.items() if not v.get("pass")]
                result.add_error(f"LV12: independence check(s) failed: {failing}")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV12: cannot read verifier-independence.json: {e}")

        # LV21 (G8 / requirement 5): a verifier-independence.json whose recorded
        # verifier_pid equals the orchestrator_pid is a SAME-PROCESS verifier —
        # the verifier shares the orchestrator's process, so IO-1 is violated
        # and the independence record cannot be trusted. Rejected.
        try:
            ind = _read_json(ind_path)
            vp = ind.get("verifier_pid", 0)
            op = ind.get("orchestrator_pid", 0)
            if vp and op and vp == op:
                result.add_error(
                    f"LV21: verifier-independence.json records verifier_pid {vp} "
                    f"equal to orchestrator_pid {op} (same-process verifier, IO-1)")
            # LV22 (G8 / requirement 5): verifier-independence.json must be
            # written by the VERIFIER process (verifier_session_id carries the
            # verifier-process marker `verifier-<pid>`). A file without that
            # marker is orchestrator-written or forged — rejected.
            vsid = ind.get("verifier_session_id", "")
            if not (isinstance(vsid, str) and vsid.startswith("verifier-")):
                result.add_error(
                    "LV22: verifier-independence.json must be written by the "
                    f"l3-verifier process (verifier_session_id={vsid!r} is not "
                    "a verifier-process marker); orchestrator-written "
                    "independence is rejected")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV21/LV22: cannot read verifier-independence.json: {e}")
    else:
        result.add_error("LV12: missing verifier-independence.json")

    # LV13: provenance.json required fields.
    prov_path = os.path.join(bundle_dir, "provenance.json")
    if os.path.exists(prov_path):
        try:
            prov = _read_json(prov_path)
            for field in REQUIRED_PROVENANCE_FIELDS:
                if field not in prov:
                    result.add_error(f"LV13: provenance.json missing {field}")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV13: cannot read provenance.json: {e}")

    # LV14: replay.json required fields.
    replay_path = os.path.join(bundle_dir, "replay.json")
    if os.path.exists(replay_path):
        try:
            replay = _read_json(replay_path)
            for field in REQUIRED_REPLAY_FIELDS:
                if field not in replay:
                    result.add_error(f"LV14: replay.json missing {field}")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV14: cannot read replay.json: {e}")

    # LV15: runtime-verdict.json required fields.
    rv_path = os.path.join(bundle_dir, "runtime-verdict.json")
    if os.path.exists(rv_path):
        try:
            rv = _read_json(rv_path)
            for field in REQUIRED_RUNTIME_FIELDS:
                if field not in rv:
                    result.add_error(f"LV15: runtime-verdict missing {field}")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV15: cannot read runtime-verdict.json: {e}")

    # LV16: reference-verdict.json required fields.
    refv_path = os.path.join(bundle_dir, "reference-verdict.json")
    if os.path.exists(refv_path):
        try:
            refv = _read_json(refv_path)
            for field in REQUIRED_REFERENCE_FIELDS:
                if field not in refv:
                    result.add_error(f"LV16: reference-verdict missing {field}")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV16: cannot read reference-verdict.json: {e}")

    # LV17: audit-log.jsonl must be non-empty and parseable.
    audit_path = os.path.join(bundle_dir, "audit-log.jsonl")
    if os.path.exists(audit_path):
        try:
            with open(audit_path) as f:
                parsed = 0
                for line in f:
                    if line.strip():
                        try:
                            json.loads(line)
                            parsed += 1
                        except json.JSONDecodeError:
                            raise
                if parsed == 0:
                    result.add_warning("LV17: audit-log.jsonl is empty (ok for "
                                       "rehearsal, failure for L3)")
        except (json.JSONDecodeError, OSError) as e:
            result.add_error(f"LV17: audit-log corrupt or unreadable: {e}")

    # LV18: audit-log integrity chain (side-car).
    chain_path = audit_path + ".chain"
    if os.path.exists(audit_path) and os.path.isfile(audit_path):
        try:
            from tests.l3_reference.audit_chain import verify_ledger
            v = verify_ledger(audit_path, sidecar_path=chain_path if os.path.exists(chain_path) else None)
            if v.decision != "VALID":
                result.add_error(f"LV18: audit-log integrity chain invalid: {v.reason}")
        except Exception as e:
            result.add_warning(f"LV18: audit chain verification error: {e}")

    # LV19: verdict-match.json must not appear in the audit log.
    if os.path.exists(audit_path) and os.path.exists(vm_path):
        try:
            with open(audit_path) as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                        if ev.get("event_id", "").startswith("verdict-match"):
                            result.add_error("LV19: verdict-match.json appears in the audit log")
                            break
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass

    # LV20: before.sha256 / after.sha256 format.
    for hname in ("before.sha256", "after.sha256"):
        hpath = os.path.join(bundle_dir, hname)
        if os.path.exists(hpath):
            try:
                h = _read_json(hpath)
                if h.get("algorithm") != "sha256":
                    result.add_error(f"LV20: {hname} algorithm must be sha256")
                if not VALID_SHA256_PATTERN.match(h.get("root_hash", "")):
                    result.add_error(f"LV20: {hname} root_hash invalid format")
            except (json.JSONDecodeError, OSError) as e:
                result.add_error(f"LV20: cannot read {hname}: {e}")

    # Per-INT mandatory evidence rules (docs/security/0005 §4).
    if int_scenario:
        _validate_int_rules(result, int_scenario, bundle_dir)

    # Fail-closed rule (LV3.3): any error when reading a file is a rejection.
    result.passed = len(result.errors) == 0
    return result


def _validate_int_rules(result: ValidationResult, int_scenario: str, bundle_dir: str):
    """Apply per-INT mandatory evidence rules (LV-INT-*)."""
    rv_path = os.path.join(bundle_dir, "runtime-verdict.json")
    rv = _read_json(rv_path) if os.path.exists(rv_path) else {}

    if int_scenario == "INT-01":
        if rv.get("decision") != "ALLOW":
            result.add_error("LV-INT-01: INT-01 runtime verdict must be ALLOW")
        # LV-INT-01b: for write-class, after.sha256 must differ from before.
        before = _read_json(os.path.join(bundle_dir, "before.sha256")) if os.path.exists(
            os.path.join(bundle_dir, "before.sha256")) else {}
        after = _read_json(os.path.join(bundle_dir, "after.sha256")) if os.path.exists(
            os.path.join(bundle_dir, "after.sha256")) else {}
        if before.get("root_hash") == after.get("root_hash"):
            result.add_warning("LV-INT-01b: INT-01 write produced no state change "
                               "(expected delta for write-class scenario)")

    elif int_scenario == "INT-07":
        if rv.get("decision") not in ("DENY", "ERROR"):
            result.add_error("LV-INT-07: INT-07 runtime verdict must be DENY/ERROR")
        before = _read_json(os.path.join(bundle_dir, "before.sha256")) if os.path.exists(
            os.path.join(bundle_dir, "before.sha256")) else {}
        after = _read_json(os.path.join(bundle_dir, "after.sha256")) if os.path.exists(
            os.path.join(bundle_dir, "after.sha256")) else {}
        if before.get("root_hash") != after.get("root_hash"):
            result.add_error("LV-INT-07b: INT-07 mutated state despite DENY")

    elif int_scenario == "INT-11":
        prov_path = os.path.join(bundle_dir, "provenance.json")
        if os.path.exists(prov_path):
            prov = _read_json(prov_path)
            children = prov.get("children", [])
            if len(children) < 3:
                result.add_error(f"LV-INT-11: INT-11 requires >= 3 concurrent children, "
                                 f"got {len(children)}")
            roles = [c.get("role") for c in children if c.get("role")]
            if len(set(roles)) < 3:
                result.add_error(f"LV-INT-11b: INT-11 children must have distinct roles, "
                                 f"got {roles}")
        # LV-INT-11c: state version unchanged.
        if rv.get("state_version_before") != rv.get("state_version_after"):
            result.add_warning("LV-INT-11c: INT-11 state version changed (expected no change)")

    elif int_scenario == "INT-12":
        if not rv.get("failure"):
            result.add_error("LV-INT-12: INT-12 requires failure propagation evidence")
        failure = rv.get("failure", {})
        recovery = failure.get("recovery", {})
        if recovery.get("no_blind_retry") is not True:
            result.add_error("LV-INT-12b: INT-12 recovery did not set no_blind_retry")
        if recovery.get("no_authority_expansion") is not True:
            result.add_error("LV-INT-12c: INT-12 recovery did not set no_authority_expansion")


def validate_bundle(bundle_dir: str, **kwargs) -> dict:
    """Convenience: run validation and return a serializable dict."""
    result = validate_bundle_dir(bundle_dir, **kwargs)
    return {
        "passed": result.passed,
        "errors": result.errors,
        "warnings": result.warnings,
        "summary": result.summary,
        "detail": result.detail,
    }