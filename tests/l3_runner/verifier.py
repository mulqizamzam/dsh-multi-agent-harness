# tests/l3_runner/verifier.py — The independent L3 verifier process (P2/P3)
#
# INDEPENDENT OBSERVER. This is a STANDALONE OS process that computes the
# oracle verdict (P3) for one L3 scenario, independently of the orchestrator
# and independently of the runtime's own verdict. It is invoked by the runner
# via `subprocess` — never via DSH subagent tools, never inside the
# orchestrator's session tree.
#
# HARD REQUIREMENTS (enforced in code below):
#   1. MUST NOT import any production gate under test. `assert_clean_imports()`
#      refuses to run if control.* / orchestrator.foundation.gates /
#      audit.helpers / state.helpers are imported.
#   2. MUST NOT run as a DSH subagent (it is a subprocess, and the runner
#      refuses to spawn it via subagent tools).
#   3. MUST NOT read the orchestrator's session log — it reads ONLY the
#      on-disk artifacts in the bundle directory and the captured action
#      fixture (passed as a JSON file, not via message).
#   4. MUST NOT share the orchestrator's process — the runner records distinct
#      PIDs and (where supported) UIDs.
#   5. MUST NOT receive authority from the orchestrator — the verdict is
#      computed from the REFERENCE oracles (tests/l3_reference/*) + the
#      Human-signed plan, and it is computed BEFORE the runtime verdict is
#      read (no post-hoc rationalisation).
#
# OUTPUTS (written into the bundle directory):
#   reference-verdict.json      — the oracle verdict (computed FIRST)
#   oracle-classes.json         — which O1..O4 classes were used (>= 2 required)
#   verdict-match.json          — reference vs runtime decision match + failure class
#   verifier-independence.json  — IO-1..IO-10 checklist
#
# USAGE (as a separate process):
#   python -m tests.l3_runner.verifier --bundle-dir <dir> --fixture <context.json> \
#       --orchestrator-pid <pid> --orchestrator-uid <uid> \
#       --orchestrator-session <id> --parent-session <id|empty> [--rehearsal]

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from datetime import datetime, timezone

from . import ORACLE_MODULES
from .independence import compute_independence, sha256_file
from .replay import fixture_hash
from .claim_gate import evaluate_l3_claim

# ---------------------------------------------------------------------------
# Independence enforcement 1: no production gate imports
# ---------------------------------------------------------------------------
FORBIDDEN_PREFIXES = (
    "control.",
    "orchestrator.foundation.gates",
    "audit.helpers",
    "state.helpers",
    "tests.control_plane",
    "tests.execution_gate",
)


def assert_clean_imports() -> None:
    """Refuse to run if any production gate (or its test reference twin) is
    already imported. The verifier computes its verdict only from the
    tests/l3_reference/* oracles, which share no imports with production."""
    loaded = [name for name in list(sys.modules)
              if any(name == p or name.startswith(p) for p in FORBIDDEN_PREFIXES)]
    if loaded:
        raise RuntimeError(
            "L3 verifier independence violation: production gate modules are "
            f"imported in this process: {sorted(loaded)}. The verifier must "
            "run in a clean process that imports only tests.l3_reference "
            "oracles.")


# ---------------------------------------------------------------------------
# Oracle loading (P3: external oracle, O1)
# ---------------------------------------------------------------------------
class OracleRegistry:
    """Maps a gate_under_test name to its independent reference implementation.

    The registry lives in tests/l3_runner/__init__.py (ORACLE_MODULES) and
    loads modules by dotted name — the verifier never touches production code.
    """

    @staticmethod
    def load(gate: str):
        mod_name = ORACLE_MODULES.get(gate)
        if not mod_name:
            raise KeyError(f"no reference oracle registered for gate {gate!r}; "
                           f"known gates: {sorted(ORACLE_MODULES)}")
        module = importlib.import_module(mod_name)
        entry = getattr(module, f"oracle_{gate}", None)
        if entry is None:
            # Some gates use a different entrypoint naming; fall back to the
            # generic oracle_<gate> convention.
            for name, obj in vars(module).items():
                if name.startswith("oracle_") and callable(obj):
                    entry = obj
                    break
        if entry is None:
            raise AttributeError(
                f"reference module {mod_name} has no oracle entrypoint")
        return entry


# ---------------------------------------------------------------------------
# Failure classification (docs/security/0003 §9)
# ---------------------------------------------------------------------------
def classify_failure(runtime_decision: str, reference_decision: str,
                     independence_all_pass: bool, oracle_classes: list,
                     replayable: bool) -> str:
    """Return the L3 failure class for a run.

    L3-PASS                                runtime == oracle, independent, >=2 oracles
    L3-FAIL-RUNTIME-EXCEEDS-EXPECTATION    runtime allowed what oracle denies
    L3-FAIL-RUNTIME-UNDER-EXCEEDS-EXPECTATION  runtime denied what oracle allows
    L3-INDEPENDENCE-VIOLATION              independence checklist failed
    L3-ORACLE-INADEQUATE                   fewer than 2 oracle classes
    L3-NON-REPRODUCIBLE                    fixture not pinned / not replayable
    """
    if len(set(oracle_classes)) < 2:
        return "L3-ORACLE-INADEQUATE"
    if not independence_all_pass:
        return "L3-INDEPENDENCE-VIOLATION"
    if not replayable:
        return "L3-NON-REPRODUCIBLE"
    if runtime_decision != reference_decision:
        if runtime_decision == "ALLOW" and reference_decision == "DENY":
            return "L3-FAIL-RUNTIME-EXCEEDS-EXPECTATION"
        return "L3-FAIL-RUNTIME-UNDER-EXCEEDS-EXPECTATION"
    return "L3-PASS"


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------
class Verifier:
    """Runs the full independent verification flow for one scenario.

    Ordering is strict (prevents post-hoc rationalisation):
      1. read the Human-signed plan + captured action fixture (O4 oracle)
      2. compute the reference verdict from the O1 oracle  -> reference-verdict.json
      3. read the runtime verdict (on-disk runtime-verdict.json)
      4. compute the match + failure class                  -> verdict-match.json
      5. compute the IO-1..IO-10 independence checklist     -> verifier-independence.json
      6. record the oracle classes used                     -> oracle-classes.json
    """

    def __init__(self, bundle_dir: str, fixture: dict, *,
                 orchestrator_pid: int, orchestrator_uid: int,
                 orchestrator_session: str, parent_session,
                 verifier_session: str = "", rehearsal: bool = False):
        self.bundle_dir = bundle_dir
        self.fixture = fixture or {}
        self.rehearsal = rehearsal
        self.orchestrator_pid = int(orchestrator_pid or 0)
        self.orchestrator_uid = int(orchestrator_uid or 0)
        self.orchestrator_session = orchestrator_session or ""
        self.parent_session = parent_session or None
        self.verifier_session = verifier_session or f"verifier-{os.getpid()}"

        self.scenario_id = self.fixture.get("scenario_id") or os.path.basename(bundle_dir)
        self.gate = self.fixture.get("gate_under_test", "authority")
        self.oracle_classes_used = list(self.fixture.get("oracle_classes_used") or [])

        self.reference_verdict: dict | None = None
        self.runtime_verdict: dict | None = None
        self.independence: dict | None = None
        self.evidence_checks: dict | None = None
        # True when a pre-existing (orchestrator-written / stale)
        # verifier-independence.json was found and overwritten by this run.
        self._independence_overwrite: bool = False

    # -- 1. fixture / plan (O4) --------------------------------------------
    def read_plan(self) -> dict:
        plan_path = os.path.join(self.bundle_dir, "plan.json")
        with open(plan_path) as f:
            return json.load(f)

    # -- 2. reference verdict (O1, computed BEFORE reading runtime) ---------
    def compute_reference_verdict(self) -> dict:
        oracle = OracleRegistry.load(self.gate)
        context = dict(self.fixture.get("oracle_context") or self.fixture)
        context.setdefault("scenario_id", self.scenario_id)
        context.setdefault("gate_under_test", self.gate)
        result = oracle(context)
        result.setdefault("computed_at",
                          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        verifier_file = os.path.abspath(__file__)
        result.setdefault("verifier_binary_sha256", sha256_file(verifier_file))
        result.setdefault("scenario_id", self.scenario_id)
        result.setdefault("gate_under_test", self.gate)
        self.reference_verdict = result
        self._write("reference-verdict.json", result)
        return result

    # -- 3. runtime verdict (read AFTER reference computed) ----------------
    def read_runtime_verdict(self) -> dict:
        path = os.path.join(self.bundle_dir, "runtime-verdict.json")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"runtime-verdict.json missing in {self.bundle_dir}; the runtime "
                "must record its verdict before the verifier reads it")
        with open(path) as f:
            self.runtime_verdict = json.load(f)
        return self.runtime_verdict

    # -- 4. match + failure class ------------------------------------------
    def compute_match(self) -> dict:
        if self.reference_verdict is None:
            raise RuntimeError("reference verdict must be computed first")
        if self.runtime_verdict is None:
            raise RuntimeError("runtime verdict must be read first")

        ref = self.reference_verdict.get("decision", "DENY")
        run = self.runtime_verdict.get("decision", "ERROR")
        match = (run == ref)

        # Evidence verification (requirement 2): provenance + replay metadata
        # + state hashes must all pass, else the run is NOT a valid L3
        # candidate (fail-closed). Any evidence failure forces match=False.
        evidence = self.verify_evidence()
        evidence_ok = self._evidence_ok()
        if not evidence_ok:
            match = False

        # Independence must be computed before we can classify; compute it here
        # (it is also persisted separately).
        ind = self._compute_independence()
        ind_pass = ind.get("all_pass", False)
        replayable = bool(self.fixture.get("replayable", True))
        failure_class = classify_failure(run, ref, ind_pass,
                                         self.oracle_classes_used, replayable)

        # L3 claim gate (requirement 8): the SINGLE code-enforced decision.
        # A rehearsal always forces l3_claim=false.
        plan = self.read_plan() if os.path.exists(
            os.path.join(self.bundle_dir, "plan.json")) else {}
        replay = {}
        replay_path = os.path.join(self.bundle_dir, "replay.json")
        if os.path.isfile(replay_path):
            try:
                with open(replay_path) as f:
                    replay = json.load(f)
            except (json.JSONDecodeError, OSError):
                replay = {}
        runtime = self.runtime_verdict or {}
        gate = evaluate_l3_claim(
            bundle_dir=self.bundle_dir,
            runtime_decision=run,
            reference_decision=ref,
            rehearsal=self.rehearsal,
            verifier_pid=os.getpid(),
            orchestrator_pid=self.orchestrator_pid,
            verifier_uid=os.getuid(),
            orchestrator_uid=self.orchestrator_uid,
            independence_all_pass=ind_pass,
            oracle_classes=self.oracle_classes_used,
            fixture_hash=replay.get("fixture_hash", ""),
            verifier_binary_sha256=replay.get("verifier_binary_sha256", ""),
            schema_sha256=replay.get("schema_sha256") or {},
            plan_signoff_ts=plan.get("human_signoff_ts", ""),
            runtime_captured_at=runtime.get("captured_at", ""),
            unresolved_unknowns=self.fixture.get("unresolved_unknowns") or [],
        )
        l3_claim = bool(gate.l3_claim)

        delta_summary = ""
        if not match:
            if not evidence_ok:
                delta_summary = (
                    f"evidence verification failed: {evidence}")
            else:
                delta_summary = (
                    f"runtime decision {run!r} != reference decision {ref!r} "
                    f"(failure class {failure_class})")

        result = {
            "scenario_id": self.scenario_id,
            "match": match,
            "runtime_decision": run,
            "reference_decision": ref,
            "delta_summary": delta_summary,
            "failure_class": failure_class,
            "l3_claim": l3_claim,
            "claim_gate": gate.to_dict(),
            "independent_observer_id": f"verifier-process-{os.getpid()}",
            "replay_command": f"python -m tests.l3_runner.runner --scenario "
                              f"{self.scenario_id} --mode replay",
            "evidence_checks": evidence,
            "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._write("verdict-match.json", result)
        return result

    # -- 5. independence checklist -----------------------------------------
    def _compute_independence(self) -> dict:
        plan = self.read_plan() if os.path.exists(
            os.path.join(self.bundle_dir, "plan.json")) else {}
        runtime = self.runtime_verdict or {}
        before = self._read_state_hash("before.sha256")
        after = self._read_state_hash("after.sha256")
        plan_ts = plan.get("human_signoff_ts", "")
        runtime_ts = runtime.get("captured_at", "")
        deny_protected = (runtime.get("decision") == "DENY"
                          and self.fixture.get("target_is_protected", False))

        # Audit chain validity: recompute independently (IO-8).
        audit_log = os.path.join(self.bundle_dir, "audit-log.jsonl")
        chain_valid = self._verify_audit_chain(audit_log)

        # IO-10: verdict-match.json must NOT appear inside the audit log.
        verdict_match_in_audit = self._verdict_match_in_audit(audit_log)

        ref_modules = []
        for gate in (self.gate,):
            mod = ORACLE_MODULES.get(gate)
            if mod:
                try:
                    ref_modules.append(os.path.abspath(importlib.import_module(mod).__file__))
                except (ImportError, AttributeError):
                    pass

        ind = compute_independence(
            scenario_id=self.scenario_id,
            orchestrator_pid=self.orchestrator_pid,
            orchestrator_uid=self.orchestrator_uid,
            orchestrator_session_id=self.orchestrator_session,
            verifier_pid=os.getpid(),
            verifier_uid=os.getuid(),
            verifier_session_id=self.verifier_session,
            parent_session_id=self.parent_session,
            verifier_binary_path=os.path.abspath(__file__),
            reference_modules=ref_modules,
            oracle_classes_used=self.oracle_classes_used,
            plan_ts=plan_ts,
            runtime_ts=runtime_ts,
            audit_log_path=audit_log,
            audit_chain_valid=chain_valid,
            before_root_hash=before.get("root_hash", ""),
            after_root_hash=after.get("root_hash", ""),
            deny_protected_path=deny_protected,
            verdict_match_in_audit=verdict_match_in_audit,
        )
        self.independence = ind.to_dict()
        self._write("verifier-independence.json", self.independence)
        return self.independence

    def _read_state_hash(self, name: str) -> dict:
        path = os.path.join(self.bundle_dir, name)
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            return json.load(f)

    def _verify_audit_chain(self, audit_log: str) -> bool:
        if not os.path.exists(audit_log):
            return True  # no audit slice = no claim; treated as pass for IO-8
        from tests.l3_reference.audit_chain import verify_ledger
        verdict = verify_ledger(audit_log, sidecar_path=audit_log + ".chain")
        return verdict.decision == "VALID"

    def _verdict_match_in_audit(self, audit_log: str) -> bool:
        """IO-10: the verifier's own output must not be inside the audit slice
        it certifies (otherwise it certifies itself)."""
        if not os.path.exists(audit_log):
            return False
        with open(audit_log) as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_id", "").startswith("verdict-match"):
                    return True
                if ev.get("actor") == "l3-verifier":
                    return True
        return False

    # -- 6. oracle classes -------------------------------------------------
    def record_oracle_classes(self) -> dict:
        data = {
            "scenario_id": self.scenario_id,
            "oracle_classes_used": sorted(set(self.oracle_classes_used)),
            "rationale": self.fixture.get("oracle_rationale",
                                          "reference re-implementation + "
                                          "Human-signed expectation"),
        }
        self._write("oracle-classes.json", data)
        return data

    # -- 7. evidence verification (provenance + replay metadata) -----------
    # Requirement 2: the verifier must verify evidence provenance and replay
    # metadata, and fail closed on any discrepancy. These checks are recorded
    # in the evidence_checks dict. ABSENCE of a file is recorded (not a
    # failure — the claim gate evaluates completeness); MALFORMATION of a
    # present file IS a failure.

    def verify_evidence(self) -> dict:
        """Independently verify the bundle's evidence items.

        Checks (each recorded as a checklist item):
          - provenance.json (E10): if present, must have delegation_chain +
            children structure;
          - replay.json (E11): if present, must have fixture_hash /
            verifier_binary_sha256 / schema_sha256 pins;
          - before.sha256 / after.sha256 (E4/E5): if present, must be valid
            JSON with algorithm/root_hash fields.
        Returns the evidence-check result dict (never raises).
        """
        results: dict[str, str] = {}

        # E10 — provenance.
        prov_path = os.path.join(self.bundle_dir, "provenance.json")
        if os.path.isfile(prov_path):
            try:
                with open(prov_path) as f:
                    prov = json.load(f)
                has_chain = isinstance(prov.get("delegation_chain"), list)
                has_children = "children" in prov
                results["evidence_provenance"] = (
                    "pass" if (has_chain and has_children) else "fail")
                results["evidence_provenance_detail"] = (
                    f"delegation_chain={has_chain} children={has_children}")
            except (json.JSONDecodeError, OSError):
                results["evidence_provenance"] = "fail"
                results["evidence_provenance_detail"] = "malformed provenance.json"
        else:
            results["evidence_provenance"] = "absent"
            results["evidence_provenance_detail"] = "provenance.json not in bundle"

        # E11 — replay metadata.
        replay_path = os.path.join(self.bundle_dir, "replay.json")
        if os.path.isfile(replay_path):
            try:
                with open(replay_path) as f:
                    replay = json.load(f)
                pins_ok = (
                    bool(replay.get("fixture_hash"))
                    and bool(replay.get("verifier_binary_sha256"))
                    and bool(replay.get("schema_sha256")))
                results["replay_metadata"] = (
                    "pass" if pins_ok else "fail")
                results["replay_metadata_detail"] = (
                    f"fixture+verifier+schema pins={pins_ok}")
            except (json.JSONDecodeError, OSError):
                results["replay_metadata"] = "fail"
                results["replay_metadata_detail"] = "malformed replay.json"
        else:
            results["replay_metadata"] = "absent"
            results["replay_metadata_detail"] = "replay.json not in bundle"

        # E4/E5 — state hashes.
        before_path = os.path.join(self.bundle_dir, "before.sha256")
        after_path = os.path.join(self.bundle_dir, "after.sha256")
        if os.path.isfile(before_path) and os.path.isfile(after_path):
            try:
                with open(before_path) as f:
                    b = json.load(f)
                with open(after_path) as f:
                    a = json.load(f)
                hash_ok = (isinstance(b, dict) and "root_hash" in b
                           and isinstance(a, dict) and "root_hash" in a)
                results["state_hashes"] = "pass" if hash_ok else "fail"
                results["state_hashes_detail"] = (
                    f"before=present({b.get('root_hash','')[:8]}...) "
                    f"after=present({a.get('root_hash','')[:8]}...)")
            except (json.JSONDecodeError, OSError):
                results["state_hashes"] = "fail"
                results["state_hashes_detail"] = "malformed state hash file"
        else:
            results["state_hashes"] = "absent"
            results["state_hashes_detail"] = "before/after.sha256 not in bundle"

        self.evidence_checks = results
        return results

    def _evidence_ok(self) -> bool:
        """True when every REQUIRED evidence-check item passes (present items
        must be valid; absent items are recorded but not a verdict blocker).
        The claim gate evaluates completeness independently."""
        for k, v in (self.evidence_checks or {}).items():
            if k.endswith("_detail"):
                continue
            if v == "fail":  # present but malformed = evidence failure
                return False
        return True

    # -- helpers -----------------------------------------------------------
    def _write(self, name: str, data) -> str:
        path = os.path.join(self.bundle_dir, name)
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=True, indent=1)
            f.write("\n")
        return path

    def run(self) -> dict:
        """Execute the full verification flow. Returns the verdict-match dict.

        NOTE: the production-import guard is enforced at the PROCESS entry
        point (main()), not here, because this library method may legitimately
        be called in-process (tests, inline runner mode) where other modules
        have already imported production code. The standalone verifier process
        (CLI) runs the guard in a fresh interpreter and refuses to start when
        polluted."""
        # Independence-file guard (G8 / requirement 5): verifier-independence.json
        # (E12) must be computed by the VERIFIER process, never by the
        # orchestrator (docs/security/0005 §3.3 rule 3). A pre-existing file in
        # the bundle directory is orchestrator-written (or stale) and must never
        # be trusted: it is removed before the verifier computes the checklist
        # from its own process state (os.getpid()/os.getuid()), so no forged
        # content can survive into the bundle.
        ind_path = os.path.join(self.bundle_dir, "verifier-independence.json")
        self._independence_overwrite = os.path.exists(ind_path)
        if self._independence_overwrite:
            os.remove(ind_path)

        self.compute_reference_verdict()   # 2. oracle FIRST
        self.read_runtime_verdict()        # 3. then the runtime
        self.record_oracle_classes()       # 6. oracle classes (before claim gate)
        self.compute_match()               # 4. match + classification (writes verdict-match.json last)
        return self.independence or self.compute_match()

    def exit_code(self) -> int:
        """R8 (runner contract): exit 0 only when match=true AND l3_claim=true
        AND independence all-pass AND oracle classes >= 2 AND the claim gate
        passes."""
        match_path = os.path.join(self.bundle_dir, "verdict-match.json")
        ind_path = os.path.join(self.bundle_dir, "verifier-independence.json")
        oc_path = os.path.join(self.bundle_dir, "oracle-classes.json")
        try:
            with open(match_path) as f:
                m = json.load(f)
            with open(ind_path) as f:
                ind = json.load(f)
            with open(oc_path) as f:
                oc = json.load(f)
        except (OSError, json.JSONDecodeError):
            return 1
        oracle_classes = oc.get("oracle_classes_used", [])
        gate_ok = (m.get("claim_gate") or {}).get("l3_claim") is True
        if not (m.get("match") and m.get("l3_claim")
                and ind.get("all_pass") and len(set(oracle_classes)) >= 2
                and gate_ok):
            return 1
        return 0


# ---------------------------------------------------------------------------
# CLI: standalone process entrypoint
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Independent L3 verifier (standalone process)")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--fixture", required=True,
                        help="JSON file: captured action request + oracle context")
    parser.add_argument("--orchestrator-pid", type=int, default=0)
    parser.add_argument("--orchestrator-uid", type=int, default=0)
    parser.add_argument("--orchestrator-session", default="")
    parser.add_argument("--parent-session", default="")
    parser.add_argument("--verifier-session", default="")
    parser.add_argument("--rehearsal", action="store_true",
                        help="mark the run as a machinery rehearsal (l3_claim=false)")
    args = parser.parse_args(argv)

    # Independence guard: a fresh subprocess must not have production gates
    # already imported. This runs in a clean interpreter when the verifier is
    # spawned via subprocess (the real deployment model). In-process callers
    # (tests, inline runner mode) skip this check.
    assert_clean_imports()

    with open(args.fixture) as f:
        fixture = json.load(f)

    verifier = Verifier(
        args.bundle_dir, fixture,
        orchestrator_pid=args.orchestrator_pid,
        orchestrator_uid=args.orchestrator_uid,
        orchestrator_session=args.orchestrator_session,
        parent_session=args.parent_session,
        verifier_session=args.verifier_session,
        rehearsal=args.rehearsal,
    )
    verifier.run()
    return verifier.exit_code()


if __name__ == "__main__":
    sys.exit(main())
