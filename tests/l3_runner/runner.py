# tests/l3_runner/runner.py — L3 scenario runner (R1..R8 runner contract)
#
# The runner executes ONE L3 scenario end-to-end:
#   R1  invoked by an external scheduler / CLI (never by the orchestrator)
#   R2  spawns the verifier as a SEPARATE OS process (subprocess) with its own
#       PID; separate UID is attempted where the OS/credentials allow
#   R3  pre-commits plan.json (Human-signed) BEFORE any runtime activity
#   R4  captures before.sha256 before the attempt and after.sha256 after
#   R5  triggers the verifier BEFORE reading the runtime verdict (P2)
#   R6  records oracle-classes.json and refuses to write verdict-match.json
#       when fewer than 2 oracle classes are present
#   R7  computes manifest.json and writes the bundle to audit/l3/<scenario-id>/
#   R8  exits 0 only when verdict-match.json reports match=true AND l3_claim=true
#       AND the bundle is complete
#
# MODES
#   --mode replay  : use the RecordedRuntimeDriver (safe, deterministic). This
#                    is what the infrastructure tests and the P4 replay path
#                    use. NO live session, NO destructive action.
#   --mode live    : REQUIRES a human-signed plan.json, a real DSH session, and
#                    an authorized LiveDSHRuntimeDriver passed as
#                    `live_driver=` whose dispatch_available() is True. Without
#                    it the run is REFUSED — never downgraded to the recorded
#                    driver (no silent LIVE -> FAKE fallback).
#
# REHEARSAL vs CLAIM-CAPABLE
#   rehearsal=True (default, --rehearsal is implied): the verifier forces
#     l3_claim=false. Machinery-only; a placeholder signoff timestamp is
#     acceptable because the bundle can never be L3 evidence.
#   rehearsal=False (--no-rehearsal): claim-capable. The runner REFUSES unless
#     the fixture carries a real Human signoff (no placeholder id/timestamp).
#     It never invents a signature, an id, or a timestamp.
#
# INDEPENDENCE (hard requirement)
#   The verifier is spawned via `subprocess` (never a DSH subagent tool), runs
#   in its own process, imports only tests.l3_reference oracles, reads only the
#   bundle directory + fixture, and computes its verdict before reading the
#   runtime verdict. The runner records the distinct PIDs in the independence
#   checklist (IO-1..IO-2).

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

from .collector import (
    capture_env,
    capture_provenance,
    ensure_bundle_dir,
    hash_text,
    state_hash_tree,
    write_bundle_item,
    write_json,
)
from .replay import build_replay, fixture_hash
from .runtime_driver import LiveDSHRuntimeDriver, RecordedRuntimeDriver

# Project root (three levels up from this file).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Default rendezvous directory for the live dispatch file-based bridge.
DEFAULT_RENDEZVOUS_DIR = os.path.join(PROJECT_ROOT, "runs", "l3_rendezvous")
INVOCATION_FILENAME = "invocation.json"
RESPONSE_FILENAME = "response.json"
GATE_VERDICT_FILENAME = "gate-verdict.json"

# Structured runtime-observation schema the REAL bridge child must satisfy
# (bridge contract: output_schema is executed verbatim by the real subagent
# tool call). The responder derives every field from the production authority
# gate; nothing here is simulated.
RUNTIME_OBSERVATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "scenario_id", "decision", "denial_path", "stop_reason",
        "front_door_status", "front_door_child_run_id", "responder_rc",
        "audit_event_id",
    ],
    "properties": {
        "scenario_id": {"type": "string", "minLength": 1},
        "decision": {"enum": ["ALLOW", "DENY", "ERROR"]},
        "denial_path": {"type": "string"},
        "stop_reason": {"type": "string"},
        "front_door_status": {"type": "string"},
        "front_door_child_run_id": {"type": "string"},
        "responder_rc": {"type": "integer"},
        "audit_event_id": {"type": "string"},
        "reason": {"type": "string"},
    },
}

_RUNTIME_DECISIONS = ("ALLOW", "DENY", "ERROR", "INVALID")


def _map_bridge_response(resp: dict) -> dict:
    """Map a mounted-DSH-bridge response to the runtime observation contract.

    The bridge response carries the REAL observation:
    ``run_id`` (real child subagent execution id), ``output``,
    ``structured`` (the runtime verdict computed by the production authority
    gate inside the real child), ``stop_reason``, ``diagnostic``.

    Mapping rule (never invent):
    - ``decision`` ← structured.decision (validated against the runtime
      contract); missing/invalid → ERROR with the diagnostic as failure cause.
    - ``tool_call_id`` ← run_id (the real child execution id).
    - everything else ← structured first, then legacy flat keys.
    """
    structured = resp.get("structured") if isinstance(resp.get("structured"),
                                                     dict) else {}
    if not structured:
        # The bridge leaves `structured` absent when the child's final message
        # was not machine-parsed as JSON. The child was instructed to echo the
        # responder's observation verbatim; real children habitually wrap the
        # object in a markdown code fence. Recover the REAL observation by
        # parsing the final text block (fence-tolerant, last block first).
        # A block that still fails to parse contributes nothing: the mapping
        # falls through to the honest ERROR below — nothing is invented.
        for _block in reversed(resp.get("output") or []):
            if not (isinstance(_block, dict) and _block.get("type") == "text"):
                continue
            _text = str(_block.get("text") or "")
            _fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", _text, re.S)
            _candidate = _fenced.group(1) if _fenced else _text.strip()
            try:
                _parsed = json.loads(_candidate)
            except (ValueError, TypeError):
                continue
            if isinstance(_parsed, dict):
                structured = _parsed
                break
    diagnostic = resp.get("diagnostic") or ""
    decision = structured.get("decision") or resp.get("decision")
    if decision not in _RUNTIME_DECISIONS:
        return {
            "decision": "ERROR",
            "denial_path": "live-rendezvous-malformed",
            "tool_call_id": resp.get("run_id"),
            "audit_event_ids": [],
            "stopReason": resp.get("stop_reason", "completed"),
            "captured_at": _now_iso(),
            "final_status": "BLOCKED",
            "failure": {
                "class": "environment",
                "cause": (f"bridge response carries no valid runtime decision "
                          f"(structured={bool(structured)}): "
                          f"{diagnostic or resp.get('output', '')[:200]}"),
            },
        }
    return {
        "decision": decision,
        "denial_path": (structured.get("denial_path")
                        if structured.get("denial_path") is not None
                        else resp.get("denial_path")),
        "tool_call_id": resp.get("run_id"),
        "audit_event_ids": (structured.get("audit_event_ids")
                            if structured.get("audit_event_ids") is not None
                            else resp.get("audit_event_ids", [])),
        "stopReason": resp.get("stop_reason", "completed"),
        "captured_at": (structured.get("captured_at")
                        if structured.get("captured_at") is not None
                        else resp.get("captured_at") or _now_iso()),
        "final_status": (structured.get("final_status")
                         if structured.get("final_status") is not None
                         else resp.get("final_status", "COMPLETE")),
        "state_version_before": (structured.get("state_version_before")
                                 if structured.get("state_version_before") is not None
                                 else resp.get("state_version_before")),
        "state_version_after": (structured.get("state_version_after")
                                if structured.get("state_version_after") is not None
                                else resp.get("state_version_after")),
        "failure": (structured.get("failure")
                    if structured.get("failure") is not None
                    else resp.get("failure")),
        "audit_log": (structured.get("audit_log")
                      if structured.get("audit_log") is not None
                      else resp.get("audit_log", [])),
    }

# State scopes for the before/after hash tree (O3 oracle).
STATE_SCOPES = (
    "state/registry/**",
    "audit/**",
    "state/projects/**",
    "state/decisions/**",
    "state/approvals/**",
)

# Oracle classes that must be present (at least 2; O1..O4).
VALID_ORACLE_CLASSES = ("O1", "O2", "O3", "O4")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ScenarioNotFoundError(FileNotFoundError):
    pass


def _load_scenario_def(scenario_id: str, fixtures_root: str) -> dict:
    """Load a scenario definition (plan + fixture) by L3 scenario id.

    Expected layout: tests/l3_reference/fixtures/<SCENARIO_ID>/plan.json and
    optional fixture.json. Scenario ids use L3-<CTRL>-<NNN>.
    """
    if not (scenario_id.startswith("L3-") or scenario_id.startswith("G13-")):
        raise ScenarioNotFoundError(
            f"scenario id must be of the form L3-<CTRL>-<NNN> or G13-<CTRL>-<NNN>, "
            f"got {scenario_id!r}")
    dirpath = os.path.join(fixtures_root, scenario_id)
    plan_path = os.path.join(dirpath, "plan.json")
    if not os.path.exists(plan_path):
        raise ScenarioNotFoundError(
            f"no Human-signed plan.json for scenario {scenario_id} at {plan_path}. "
            "A Human-signed plan is mandatory before any L3 run.")
    with open(plan_path) as f:
        plan = json.load(f)
    fixture = dict(plan)
    fixture_path = os.path.join(dirpath, "fixture.json")
    if os.path.exists(fixture_path):
        with open(fixture_path) as f:
            fixture.update(json.load(f))
    fixture["scenario_id"] = scenario_id
    return fixture


def _require_two_oracles(fixture: dict) -> list:
    """R6: return the oracle classes; refuse the run if fewer than 2."""
    classes = list(fixture.get("oracle_classes_used") or ())
    if len(set(classes)) < 2:
        raise RuntimeError(
            "R6 violation: fewer than 2 oracle classes. Every L3 scenario must "
            f"use at least two of {VALID_ORACLE_CLASSES}. Got: {classes}")
    for c in classes:
        if c not in VALID_ORACLE_CLASSES:
            raise RuntimeError(f"invalid oracle class: {c!r} (must be in "
                               f"{VALID_ORACLE_CLASSES})")
    return sorted(set(classes))


def run_scenario(scenario_id: str, *, fixtures_root: str, bundle_base: str,
                 mode: str = "replay", seed: int = 42,
                 orchestrator_pid: int = 0, orchestrator_uid: int = 0,
                 orchestrator_session: str = "", parent_session: str = "",
                 verifier_mode: str = "subprocess",
                 verifier_python: str = sys.executable,
                 verifier_separate_uid: bool = False,
                 rehearsal: bool = True,
                 live_driver=None) -> dict:
    """Execute one L3 scenario and return the bundle directory path + summary.

    This is the main entry point used by both the CLI and the tests.

    Args:
        rehearsal: when True (default) the verifier is told this is a machinery
            rehearsal and forces ``l3_claim=false``. An actual L3 claim requires
            ``rehearsal=False``, which additionally requires a real Human
            signoff timestamp in the fixture — the runner refuses to substitute
            a placeholder (see below).
        live_driver: a ``LiveDSHRuntimeDriver`` whose ``dispatch_available()``
            is True. Required for ``mode="live"``; without it live mode is
            refused rather than downgraded to a recorded/FAKE runtime.
        verifier_separate_uid: when True, the verifier subprocess is launched
            inside a fresh user namespace (``unshare -U``), so the verifier
            process runs under a distinct OS UID from the orchestrator
            (IO-2 / separate-UID). This is the honest same-host mechanism the
            infrastructure prescribes (docs/security/0007 §1.2 option 2 /
            "separate user" via a credential-isolated launch). It is only
            effective when the OS allows unprivileged user namespaces; if the
            launch fails the run is refused, never silently downgraded to
            same-UID.

    Raises:
        RuntimeError: for ``mode="live"`` without an authorized live driver, or
            for ``rehearsal=False`` without a real Human signoff.
    """
    if mode not in ("replay", "live"):
        raise ValueError(f"unknown mode {mode!r} (must be 'replay' or 'live')")

    live_ready = bool(live_driver is not None
                      and getattr(live_driver, "dispatch_available", None)
                      and live_driver.dispatch_available())
    if mode == "live" and not live_ready:
        # No silent LIVE -> FAKE downgrade: refuse instead of falling back to
        # the recorded driver.
        raise RuntimeError(
            "live L3 mode is NOT executable: it requires a human-signed "
            "plan.json, a re-baseline to workspace-write + ask, and a real DSH "
            "session (no authorized live driver was injected: pass "
            "live_driver=LiveDSHRuntimeDriver({... 'dispatch': <callable>, "
            "'live_execution_authorized': True}) whose dispatch_available() is "
            "True). Use --mode replay for safe infrastructure/replay runs.")

    fixture = _load_scenario_def(scenario_id, fixtures_root)
    oracle_classes = _require_two_oracles(fixture)

    # R3: pre-commit the Human-signed plan BEFORE any runtime activity.
    plan = {k: fixture[k] for k in
            ("scenario_id", "actor", "action", "target", "preconditions",
             "expected_verdict", "expected_verdict_reason", "human_signoff_id",
             "human_signoff_ts", "human_signoff_method",
             "human_signoff_provenance")
            if k in fixture}
    if rehearsal:
        # Rehearsal bundles are never L3 evidence, so a placeholder timestamp is
        # acceptable here (the claim gate refuses the bundle regardless).
        plan["human_signoff_ts"] = plan.get("human_signoff_ts",
                                            "2026-08-31T00:00:00Z")
    else:
        # A non-rehearsal (claim-capable) run must NOT invent any part of the
        # Human signoff, and must NOT accept a fixture that merely carries the
        # SHAPE of a signoff. The authoritative discriminator is the same one
        # the environment probe uses (environment/readiness.py
        # ::_real_human_signoff_observed): method in {interactive,
        # signed-assertion} AND a durable id AND a timestamp AND
        # human_signoff_provenance == "recorded". Synthetic fixture ids such as
        # human-2026-08-31-101 have the shape but not the provenance.
        from .environment.readiness import _real_human_signoff_observed
        if not _real_human_signoff_observed(plan):
            raise RuntimeError(
                f"non-rehearsal L3 run refused for {scenario_id}: the fixture "
                f"carries no REAL Human signoff "
                f"(human_signoff_id={plan.get('human_signoff_id')!r}, "
                f"human_signoff_ts={plan.get('human_signoff_ts')!r}, "
                f"human_signoff_method={plan.get('human_signoff_method')!r}, "
                f"human_signoff_provenance="
                f"{plan.get('human_signoff_provenance')!r}). A claim-capable "
                f"run requires a Human-signed plan, committed BEFORE the run, "
                f"whose provenance is recorded. The runner never invents a "
                f"signature, an id, a timestamp, or a provenance.")

    bundle_dir = ensure_bundle_dir(scenario_id, base=bundle_base)

    # R4a: capture before.sha256 BEFORE any runtime activity.
    before = state_hash_tree(PROJECT_ROOT, STATE_SCOPES)
    write_bundle_item(bundle_dir, "before.sha256", before)

    # Runtime.
    recorded = os.path.join(fixtures_root, scenario_id, "runtime-recorded.json")
    if mode == "live":
        # Authorized live dispatch through the injected REAL driver. The
        # observation comes from the driver; the runner invents no part of it.
        runtime_result = live_driver.execute(
            scenario_id, plan.get("action", ""), plan.get("target", ""))
        audit_slice = runtime_result.audit_log if hasattr(runtime_result, "audit_log") else []
    elif mode == "replay" and os.path.exists(recorded):
        driver = RecordedRuntimeDriver(recorded)
        runtime_result = driver.execute(scenario_id, plan.get("action", ""),
                                        plan.get("target", ""))
        audit_slice = driver.audit_log_events
    else:
        # No recorded fixture: a minimal DENY-for-safety default so the bundle
        # is still honest (a run without a runtime cannot claim a verdict).
        runtime_result = None
        audit_slice = []

    # Capture env + provenance (E2, E10).
    env = capture_env(seed=seed)
    provenance = capture_provenance(
        scenario_id=scenario_id,
        actor_session_id=orchestrator_session or "actor-session-unset",
        verifier_session_id=f"verifier-{os.getpid()}",
        delegation_chain=fixture.get("delegation_chain", []),
        children=fixture.get("children", []),
        collection_order=fixture.get("collection_order", []),
    )
    write_bundle_item(bundle_dir, "env.json", env)
    write_bundle_item(bundle_dir, "plan.json", plan)
    write_bundle_item(bundle_dir, "provenance.json", provenance)

    # Runtime verdict + audit slice (recorded).
    if runtime_result is not None:
        runtime_verdict = runtime_result.to_dict()
        runtime_verdict["scenario_id"] = scenario_id
        write_bundle_item(bundle_dir, "runtime-verdict.json", runtime_verdict)
        write_bundle_item(bundle_dir, "audit-log.jsonl", audit_slice)
    else:
        write_bundle_item(bundle_dir, "runtime-verdict.json", {
            "scenario_id": scenario_id,
            "decision": "ERROR",
            "denial_path": "no-runtime",
            "tool_call_id": None,
            "audit_event_ids": [],
            "stopReason": "error",
            "captured_at": _now_iso(),
            "final_status": "BLOCKED",
        })
        write_bundle_item(bundle_dir, "audit-log.jsonl", [])

    # R4b: capture after.sha256 AFTER the attempt.
    after = state_hash_tree(PROJECT_ROOT, STATE_SCOPES)
    write_bundle_item(bundle_dir, "after.sha256", after)

    # E11 replay metadata — written BEFORE the verifier runs so the verifier
    # can independently verify replay metadata (requirement 2: verify replay
    # metadata; G5). Previously replay.json was written after the verifier,
    # so the verifier recorded replay_metadata=absent. The verifier now sees
    # the pinned fixture/verifier/schema hashes.
    replay_script_candidates = [
        os.path.join(fixtures_root, scenario_id, "replay.sh"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay.sh"),
    ]
    replay_script = next((p for p in replay_script_candidates if os.path.isfile(p)), "")
    replay = build_replay(
        scenario_id=scenario_id,
        fixture_path=os.path.join(fixtures_root, scenario_id),
        fixture_seed=seed,
        verifier_binary_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "verifier.py"),
        schema_dirs=[os.path.join(PROJECT_ROOT, "tests", "l3_reference", "schemas")],
        replay_script=os.path.join(fixtures_root, scenario_id, "replay.sh"),
    )
    write_bundle_item(bundle_dir, "replay.json", replay)

    # R5: trigger the verifier (subprocess, separate process).
    fixture_path = _write_verifier_fixture(bundle_dir, fixture, oracle_classes)
    if verifier_mode == "subprocess":
        cmd = [
            verifier_python, "-m", "tests.l3_runner.verifier",
            "--bundle-dir", bundle_dir,
            "--fixture", fixture_path,
            "--orchestrator-pid", str(orchestrator_pid or os.getppid()),
            "--orchestrator-uid", str(orchestrator_uid or os.getuid()),
            "--orchestrator-session", orchestrator_session,
            "--parent-session", parent_session,
        ]
        if rehearsal:
            cmd.append("--rehearsal")
        # Optional separate-UID launch via user namespace (IO-2).
        if verifier_separate_uid:
            cmd = ["unshare", "-U", "--"] + cmd
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=PROJECT_ROOT, timeout=120)
        if proc.returncode not in (0, 1):
            raise RuntimeError(
                f"verifier subprocess failed: rc={proc.returncode}\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
        # Exit code 0 means a real L3 claim passed; in rehearsal mode the
        # verifier reports l3_claim=false so exit code 1 is expected for the
        # machinery-only run. We surface the bundle for inspection either way.
    else:
        # inline mode (tests): run in-process but still record a distinct pid.
        from .verifier import Verifier
        v = Verifier(bundle_dir, fixture,
                     orchestrator_pid=orchestrator_pid or os.getppid(),
                     orchestrator_uid=orchestrator_uid or os.getuid(),
                     orchestrator_session=orchestrator_session,
                     parent_session=parent_session,
                     rehearsal=rehearsal)
        v.run()

    # R6: oracle-classes already recorded by the verifier; verify count.
    oracle_path = os.path.join(bundle_dir, "oracle-classes.json")
    if os.path.exists(oracle_path):
        with open(oracle_path) as f:
            recorded_classes = json.load(f).get("oracle_classes_used", [])
        if len(set(recorded_classes)) < 2:
            raise RuntimeError(
                "R6 violation: oracle-classes.json has fewer than 2 classes")

    # R7: manifest.json last (certifies every other file).
    from .collector import write_manifest
    write_manifest(bundle_dir, scenario_id)

    # Summary.
    summary = {
        "scenario_id": scenario_id,
        "bundle_dir": bundle_dir,
        "mode": mode,
        "rehearsal": rehearsal,
        "oracle_classes": oracle_classes,
        "fixture_hash": fixture_hash(os.path.join(fixtures_root, scenario_id)),
        "completed_at": _now_iso(),
    }
    return summary


def _write_verifier_fixture(bundle_dir: str, fixture: dict, oracle_classes: list) -> str:
    """Write the captured action request the verifier consumes. This is a
    signed fixture file, NOT a message from the orchestrator."""
    vf = {
        "scenario_id": fixture.get("scenario_id"),
        "gate_under_test": fixture.get("gate_under_test", "authority"),
        "oracle_classes_used": oracle_classes,
        "oracle_rationale": fixture.get("oracle_rationale", ""),
        "oracle_context": fixture.get("oracle_context", {}),
        "replayable": fixture.get("replayable", True),
        "target_is_protected": fixture.get("target_is_protected", False),
        # The captured action request (structured, not model prose).
        "actor": fixture.get("actor", "orchestrator"),
        "action": fixture.get("action", ""),
        "target": fixture.get("target", ""),
        "environment": fixture.get("environment", "dev"),
        "project": fixture.get("project", "multi-agent-harness"),
    }
    path = os.path.join(bundle_dir, "verifier-fixture.json")
    with open(path, "w") as f:
        json.dump(vf, f, sort_keys=True, indent=1)
    return path


def _build_live_driver(fixture: dict, rendezvous_dir: str,
                       timeout: int = 600) -> LiveDSHRuntimeDriver:
    """Build a LiveDSHRuntimeDriver with a real dispatch callable.

    The dispatch callable uses the file-based rendezvous bridge (mechanism B,
    the established REAL dispatch mechanism from the live DSH session). It
    writes the invocation to a well-known rendezvous file and waits for the
    orchestrator agent to perform the actual ``subagent_<id>`` tool call and
    write the response.

    The response carries the REAL runtime observation: the child's run_id,
    stop_reason, and the observed decision (ALLOW/DENY/ERROR/INVALID). The
    runner never invents any part of the observation.

    Args:
        fixture: The loaded scenario fixture (plan + fixture.json merged).
        rendezvous_dir: Directory for the rendezvous files.
        timeout: Max seconds to wait for a response.

    Returns:
        A configured ``LiveDSHRuntimeDriver`` whose ``dispatch_available()``
        is True, ready for ``run_scenario(..., live_driver=...)``.
    """
    inv_path = os.path.join(rendezvous_dir, INVOCATION_FILENAME)
    resp_path = os.path.join(rendezvous_dir, RESPONSE_FILENAME)
    gate_verdict_path = os.path.join(rendezvous_dir, GATE_VERDICT_FILENAME)
    os.makedirs(rendezvous_dir, exist_ok=True)

    # LIVE bridge mode (front-door seam): when the orchestrator-side entrypoint
    # (runs/l3_front_door/run.py) provides the authorized responder command, the
    # invocation is written in the REAL rendezvous-bridge contract consumed by
    # the mounted DSH bridge (apps/cli profile-boot startL3RendezvousBridge):
    # description/prompt/role/output_schema, executed as a real
    # run_in_background=false subagent call. Without it the scenario-shaped
    # invocation is written unchanged (infrastructure tests; the bridge would
    # honestly reject it as malformed — never a simulated dispatch).
    responder_cmd = os.environ.get("L3_RESPONDER_CMD", "")
    responder_role = os.environ.get("L3_RESPONDER_ROLE", "cto")

    def _rendezvous_dispatch(scenario_id: str, action: str, target: str,
                             **kwargs) -> dict:
        """Real dispatch callable: rendezvous bridge to the orchestrator agent.

        Writes the invocation, waits for the mounted DSH bridge to execute the
        real ``subagent`` tool call, and returns the observed dict.
        """
        role = fixture.get("actor", "orchestrator")
        expected_verdict = fixture.get("expected_verdict", "DENY")
        preconditions = fixture.get("preconditions", [])

        invocation = {
            "scenario_id": scenario_id,
            "action": action,
            "target": target,
            "role": role,
            "expected_verdict": expected_verdict,
            "preconditions": preconditions,
            "plan_summary": {
                "actor": fixture.get("actor"),
                "action": fixture.get("action"),
                "target": fixture.get("target"),
                "expected_verdict": fixture.get("expected_verdict"),
            },
            "created_at": _now_iso(),
        }
        if responder_cmd:
            # Bridge contract (REAL dispatch): the child performs the
            # authorized front-door observation and returns the structured
            # runtime verdict. The bridge executes it with
            # run_in_background=false and preserves description/prompt/
            # output_schema/run_id/stop_reason/diagnostic verbatim.
            command = (responder_cmd
                       .replace("{invocation}", os.path.abspath(inv_path))
                       .replace("{gate_verdict}", os.path.abspath(gate_verdict_path)))
            invocation["description"] = (
                f"L3 live runtime observation for {scenario_id} "
                f"(authorized rendezvous dispatch)")
            invocation["prompt"] = (
                f"Authorized L3 live runtime observation for scenario "
                f"{scenario_id} (action={action!r}, target={target!r}).\n"
                f"Run EXACTLY this command and use its final printed JSON as "
                f"your reply (one JSON object, no other text):\n\n"
                f"{command} --invocation {os.path.abspath(inv_path)}\n\n"
                f"Reply with ONLY the command's final printed JSON object — "
                f"raw JSON, no markdown code fence, no prose, no annotation. "
                f"Do not modify any file outside this command. Do not infer a "
                f"verdict yourself: the command computes the authoritative "
                f"decision from the structured delegation registry through the "
                f"production authority gate.")
            invocation["role"] = responder_role
            invocation["output_schema"] = RUNTIME_OBSERVATION_SCHEMA
        with open(inv_path, "w") as f:
            json.dump(invocation, f, indent=1)

        # Poll for the response
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(resp_path):
                with open(resp_path) as f:
                    resp = json.load(f)
                os.unlink(resp_path)
                # Remove the invocation too: the bridge re-dispatches any dir
                # that still holds an invocation without a response, so leaving
                # it behind makes every poll-consume cycle spawn a duplicate
                # child execution (observed: idempotent re-emit, but a real
                # second dispatch). Consumed = both files gone.
                try:
                    os.unlink(inv_path)
                except OSError:
                    pass
                return _map_bridge_response(resp)
            time.sleep(1)

        # Timeout: no response received
        return {
            "decision": "ERROR",
            "denial_path": "live-rendezvous-timeout",
            "tool_call_id": None,
            "audit_event_ids": [],
            "stopReason": "error",
            "captured_at": _now_iso(),
            "final_status": "BLOCKED",
            "failure": {
                "class": "environment",
                "cause": (f"rendezvous dispatch timed out after {timeout}s "
                          f"at {resp_path}"),
            },
        }

    # Probe the runtime environment
    d4_d7_mounted = os.environ.get("DSH_LIVE_BRIDGE_ACTIVE", "").strip().lower() in (
        "1", "true", "yes")
    approval_available = False
    try:
        from .environment.readiness import _answerer_available as _probe_answerer
        approval_available = _probe_answerer(None)
    except ImportError:
        pass

    config = {
        "dispatch": _rendezvous_dispatch,
        "live_execution_authorized": True,
        "plan": {
            "human_signoff_id": fixture.get("human_signoff_id", ""),
            "human_signoff_ts": fixture.get("human_signoff_ts", ""),
            "human_signoff_method": fixture.get("human_signoff_method", ""),
        },
        "d4_d7_mounted": d4_d7_mounted,
        "approval_answerer_available": approval_available,
        "sandbox_mode": "workspace-write",
        "approval_policy": "ask",
        "execution_gate_routes_writes": True,
    }
    return LiveDSHRuntimeDriver(config)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="L3 scenario runner")
    parser.add_argument("--scenario", required=True, help="L3-<CTRL>-<NNN>")
    parser.add_argument("--mode", default="replay", choices=("replay", "live"))
    parser.add_argument("--fixtures-root", default=None)
    parser.add_argument("--bundle-base", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--orchestrator-pid", type=int, default=0)
    parser.add_argument("--orchestrator-uid", type=int, default=0)
    parser.add_argument("--orchestrator-session", default="")
    parser.add_argument("--parent-session", default="")
    parser.add_argument("--verifier-mode", default="subprocess",
                        choices=("subprocess", "inline"))
    parser.add_argument("--verifier-separate-uid", action="store_true",
                        help="launch the verifier subprocess inside a fresh "
                             "user namespace so it runs under a distinct OS "
                             "UID from the orchestrator (IO-2 / separate-UID). "
                             "Requires unprivileged user namespaces.")
    parser.add_argument("--no-rehearsal", action="store_true",
                        help="claim-capable run: do NOT mark the bundle as a "
                             "machinery rehearsal. Requires a real Human "
                             "signoff in the fixture (the runner refuses to "
                             "substitute a placeholder) and, for --mode live, "
                             "an authorized live driver.")
    # Live-mode rendezvous configuration
    parser.add_argument("--live-rendezvous-dir", default=None,
                        help="Directory for the live-dispatch rendezvous files "
                             "(invocation.json / response.json). Only used in "
                             "--mode live.")
    parser.add_argument("--live-rendezvous-timeout", type=int, default=600,
                        help="Max seconds to wait for a rendezvous response "
                             "(default: 600s).")
    args = parser.parse_args(argv)

    fixtures_root = args.fixtures_root or os.path.join(PROJECT_ROOT, "tests",
                                                       "l3_reference", "fixtures")
    bundle_base = args.bundle_base or PROJECT_ROOT

    # Build the live driver when --mode live is requested
    live_driver = None
    if args.mode == "live":
        from .runner import _load_scenario_def as _ld
        _fixture = _ld(args.scenario, fixtures_root)
        rendezvous_dir = args.live_rendezvous_dir or os.path.join(
            DEFAULT_RENDEZVOUS_DIR, args.scenario)
        live_driver = _build_live_driver(_fixture, rendezvous_dir,
                                         timeout=args.live_rendezvous_timeout)

    kwargs = {}
    if live_driver is not None:
        kwargs["live_driver"] = live_driver

    summary = run_scenario(
        args.scenario, fixtures_root=fixtures_root, bundle_base=bundle_base,
        mode=args.mode, seed=args.seed,
        orchestrator_pid=args.orchestrator_pid,
        orchestrator_uid=args.orchestrator_uid,
        orchestrator_session=args.orchestrator_session,
        parent_session=args.parent_session,
        verifier_mode=args.verifier_mode,
        verifier_separate_uid=args.verifier_separate_uid,
        rehearsal=not args.no_rehearsal,
        **kwargs,
    )
    print(json.dumps(summary, indent=1))

    # R8: the runner exit code is the acceptance gate, not a courtesy 0.
    # In LIVE mode the run is complete only when the independent verifier
    # matched, the L3 claim is true, and the bundle validates completely.
    if args.mode == "live":
        from .validator import validate_bundle_dir
        bundle_dir = summary.get("bundle_dir")
        match = l3_claim = bundle_ok = False
        if bundle_dir:
            try:
                with open(os.path.join(bundle_dir, "verdict-match.json")) as f:
                    _vm = json.load(f)
                    match = bool(_vm.get("match"))
                    l3_claim = bool(_vm.get("l3_claim"))
                bundle_ok = bool(validate_bundle_dir(bundle_dir).passed)
            except (OSError, ValueError) as exc:
                print(f"exit-gate: unreadable acceptance evidence: {exc}",
                      file=sys.stderr)
        exit_ok = bool(match and l3_claim and bundle_ok)
        print(f"exit-gate: match={match} l3_claim={l3_claim} "
              f"bundle_complete={bundle_ok} -> exit {0 if exit_ok else 1}")
        return 0 if exit_ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
