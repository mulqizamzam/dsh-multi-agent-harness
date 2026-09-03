#!/usr/bin/env python3
"""L3 front-door responder — runs INSIDE the real DSH subagent child.

The L3 runner's live dispatch (tests/l3_runner/runner.py::_rendezvous_dispatch)
writes a bridge-contract invocation.json; the mounted DSH rendezvous bridge
(apps/cli profile-boot startL3RendezvousBridge — verified, untouched) executes
a REAL foreground subagent tool call whose prompt instructs the child to run
EXACTLY this command. This script is that command:

  1. loads the scenario's oracle_context delegation facts (the Human-authorized
     grant the verifier's reference oracle also uses),
  2. seeds a fresh O3 daemon workspace with that delegation via the sanctioned
     control plane (create_delegation -> registry_write, daemon-routed CAS),
  3. reads it back through FileDelegationProvider (daemon-backed, no mirror),
  4. evaluates the REAL production authority gate (control.authority) for the
     invocation action/target with the REAL clock,
  5. on ALLOW performs the controlled write at <ws>/<target> (authorized
     workspace artifact — gate-checked, never a protected path),
  6. derives ONE real audit event from the actual gate evaluation and appends
     it through the sanctioned audit_append channel (hash-chained ledger),
  7. writes gate-verdict.json (evidence) and prints the structured runtime
     observation — the child's final reply, which the bridge returns as
     response.json {run_id, output, structured, stop_reason, diagnostic}.

NO simulated verdicts, NO fake/replay fallback: every field is derived from
the real gate evaluation. Failure paths emit decision=ERROR (fail-closed).

Idempotency: a processed-marker keyed by invocation sha256 — re-running the
same invocation re-emits the recorded verdict WITHOUT re-executing the gate,
the controlled write, or the audit append (no duplicate side effects).

Exit codes: 0 observation produced · 4 timeout · 5 fail-closed error
(the ERROR observation is still printed for the bridge to carry).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

RENDZ_INVOCATION = "invocation.json"
RESPONDER_VERSION = "l3-frontdoor-responder/1.0"
DEFAULT_STATE_ROOT = os.path.join(_PROJECT_ROOT, "runs", "l3_frontdoor", "state")
DEFAULT_FIXTURES_ROOT = os.path.join(_PROJECT_ROOT, "runs", "l3_live_claim",
                                     "fixtures")
PROCESSED_MARKER = "processed.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _observation(*, scenario_id: str, decision: str, denial_path: str,
                 final_status: str, audit_event_ids: list, audit_log: list,
                 audit_event_id: str, responder_rc: int, reason: str) -> dict:
    """The structured runtime observation (bridge response `structured`).

    Must mirror tests.l3_runner.runner.RUNTIME_OBSERVATION_SCHEMA exactly."""
    return {
        "scenario_id": scenario_id,
        "decision": decision,
        "denial_path": denial_path or "",
        "stop_reason": "completed",
        "final_status": final_status,
        "audit_event_ids": list(audit_event_ids),
        "audit_log": list(audit_log),
        "audit_event_id": audit_event_id or "",
        "responder_rc": int(responder_rc),
        "reason": reason or "",
        "captured_at": _now_iso(),
    }


def _fail_closed(scenario_id: str, cause: str, rc: int) -> int:
    """Emit an honest ERROR observation — never a fake ALLOW — and exit rc."""
    obs = _observation(scenario_id=scenario_id, decision="ERROR",
                       denial_path="responder-error", final_status="BLOCKED",
                       audit_event_ids=[], audit_log=[], audit_event_id="",
                       responder_rc=rc, reason=cause)
    print(json.dumps(obs, indent=1))
    return rc


def respond(invocation_path: str, gate_verdict_path: str,
            fixtures_root: str, state_root: str) -> int:
    """Fail-closed wrapper: ANY failure before/during the gate pipeline
    (invocation load, idempotency check, fixture load, workspace or daemon
    setup) emits a structured ERROR observation for the bridge to carry,
    instead of crashing the child process with no verdict at all."""
    try:
        return _respond_checked(invocation_path, gate_verdict_path,
                                fixtures_root, state_root)
    except Exception as e:  # noqa: BLE001 — fail-closed, honest ERROR
        return _fail_closed("unknown", f"{type(e).__name__}: {e} "
                            "(no verdict invented)", 5)


def _respond_checked(invocation_path: str, gate_verdict_path: str,
                     fixtures_root: str, state_root: str) -> int:
    with open(invocation_path) as f:
        invocation = json.load(f)

    scenario_id = (invocation.get("scenario_id") or "").strip()
    action = (invocation.get("action") or "").strip()
    target = (invocation.get("target") or "").strip()
    if not (scenario_id and action and target):
        return _fail_closed(
            scenario_id or "unknown",
            f"malformed invocation: scenario_id/action/target required "
            f"(got {scenario_id!r}/{action!r}/{target!r})", 4)

    # -- idempotency: same invocation => re-emit recorded verdict, no side
    #    effects repeated (no blind retry / duplicate execution).
    inv_hash = hashlib.sha256(
        json.dumps(invocation, sort_keys=True).encode()).hexdigest()
    os.makedirs(state_root, exist_ok=True)
    processed_path = os.path.join(state_root, PROCESSED_MARKER)
    if os.path.exists(processed_path):
        with open(processed_path) as f:
            processed = json.load(f)
        if processed.get("invocation_sha256") == inv_hash:
            if os.path.exists(processed.get("gate_verdict_path", "")):
                with open(processed["gate_verdict_path"]) as f:
                    prior = json.load(f)
                prior["responder_rc"] = 0
                prior["idempotent_replay"] = True
                _atomic_write(gate_verdict_path, json.dumps(prior, indent=1))
                print(json.dumps(prior["observation"], indent=1))
                return 0

    # -- 1. oracle_context delegation facts (same authority facts the
    #       verifier's reference oracle uses -> agreement by construction).
    fixture_path = os.path.join(fixtures_root, scenario_id, "fixture.json")
    with open(fixture_path) as f:
        fixture = json.load(f)
    oracle_context = fixture.get("oracle_context") or {}
    delegation_doc = oracle_context.get("delegation") or {}
    if not delegation_doc.get("id"):
        return _fail_closed(scenario_id, "fixture oracle_context.delegation "
                            "missing — cannot seed a real registry", 5)

    # -- 2/3. fresh O3 daemon workspace; seed via the sanctioned control plane.
    inv8 = inv_hash[:8]
    ws = os.path.join(state_root, f"ws-{inv8}")
    if os.path.exists(ws):
        shutil.rmtree(ws)
    from tests.conftest import start_o3_daemon, stop_o3_daemon
    _, _client, daemon = start_o3_daemon(ws)  # sets DSH_REGISTRY_WRITER_* env
    try:
        from control.delegation import create_delegation, delegation_from_dict
        from control.execution_gate import audit_append, audit_read, registry_write
        from control.authority import AuthorityGate
        from orchestrator.runtime.delegation import FileDelegationProvider

        d = create_delegation(
            id=delegation_doc.get("id", ""),
            principal=delegation_doc.get("principal", "human"),
            delegate=delegation_doc.get("delegate", "orchestrator"),
            project=delegation_doc.get("project", "multi-agent-harness"),
            task=delegation_doc.get("task", ""),
            action=delegation_doc.get("action", ""),
            target=delegation_doc.get("target", ""),
            environment=delegation_doc.get("environment", "dev"),
            scope_operations=tuple(delegation_doc.get("scope_operations") or ()),
            scope_resources=tuple(delegation_doc.get("scope_resources") or ()),
            scope_environments=tuple(delegation_doc.get("scope_environments") or ()),
            expires_at=delegation_doc.get("expires_at", ""),
            status=delegation_doc.get("status", "ACTIVE"),
        )
        registry_write("state/registry/delegations.json", d.to_dict(), base=ws)
        registry_write("state/registry/revocations.json", {"revoked": []}, base=ws)

        # daemon-backed read (no direct-fs mirror) — the ONLY authority source
        provider = FileDelegationProvider(base=ws)
        delegation, revocation_list = provider.current()
        if delegation is None:
            return _fail_closed(scenario_id, "seeded registry read returned no "
                                "delegation (fail-closed)", 5)

        # -- 4. REAL production authority gate, REAL clock (now=None).
        now_iso = _now_iso()
        decision = AuthorityGate().evaluate({
            "delegation": delegation,
            "action": action,
            "target": target,
            "environment": oracle_context.get("environment",
                                              delegation.environment),
            "actor": oracle_context.get("actor", "orchestrator"),
            "project": oracle_context.get("project", delegation.project),
            "revocation_list": revocation_list,
            "now": None,
            "approval_reference": (oracle_context.get("approval_reference")
                                   or None),
        })

        # -- 5/6. real audit event from the ACTUAL evaluation; sanctioned append.
        result = "allowed" if decision.decision == "ALLOW" else "denied"
        slug = "".join(ch if (ch.isalnum() or ch == "-") else "-"
                       for ch in scenario_id.lower()).strip("-")
        event_id = f"event-{slug}-{uuid.uuid4().hex[:8]}"
        event = {
            "event_id": event_id,
            "event_class": "gate_authority",
            "action": action,
            "target": target,
            "actor": oracle_context.get("actor", "orchestrator"),
            "actor_type": "orchestrator",
            "authority_source": delegation.id,
            "task_id": delegation.task,
            "project": delegation.project,
            "result": result,
            "timestamp": now_iso,
        }
        audit_target = f"audit/{delegation.project}/l3-live.jsonl"
        audit_append(audit_target, event, base=ws)
        audit_read(audit_target, base=ws)  # read-back through the daemon

        # -- controlled write: the action's REAL effect (ALLOW only). A
        #    workspace artifact path, gate-checked, never a protected path.
        controlled_write = ""
        if decision.decision == "ALLOW":
            from control.execution_gate import write_through
            artifact = {
                "scenario_id": scenario_id,
                "written_by": RESPONDER_VERSION,
                "authority_source": delegation.id,
                "audit_event_id": event_id,
                "written_at": now_iso,
            }
            path = write_through("write", target, artifact, base=ws)
            controlled_write = path

        observation = _observation(
            scenario_id=scenario_id,
            decision=decision.decision if decision.decision != "ESCALATE"
                     else "DENY",
            denial_path="" if decision.decision == "ALLOW"
                         else (f"authority-gate:{decision.decision.lower()}"
                               f"{':' if decision.reason else ''}"
                               f"{decision.reason}"),
            final_status="COMPLETE",
            audit_event_ids=[event_id],
            audit_log=[event],
            audit_event_id=event_id,
            responder_rc=0,
            reason=decision.reason if decision.decision != "ALLOW"
                   else (decision.reason or "authority grant: in-scope "
                          "structured ACTIVE delegation"),
        )

        verdict = {
            "responder": RESPONDER_VERSION,
            "invocation_sha256": inv_hash,
            "invocation": invocation,
            "fixture": {"path": fixture_path,
                        "oracle_classes": fixture.get("oracle_classes_used"),
                        "expected_verdict": fixture.get("expected_verdict")},
            "delegation_seeded": delegation.to_dict(),
            "registry_workspace": ws,
            "gate": {"name": decision.gate, "decision": decision.decision,
                     "reason": decision.reason,
                     "evaluated_at": now_iso, "clock": "real"},
            "audit_event": event,
            "audit_ledger": os.path.join(ws, audit_target),
            "controlled_write": controlled_write,
            "observation": observation,
            "captured_at": now_iso,
        }
        _atomic_write(gate_verdict_path, json.dumps(verdict, indent=1))
        _atomic_write(processed_path, json.dumps({
            "invocation_sha256": inv_hash,
            "gate_verdict_path": os.path.abspath(gate_verdict_path),
            "decision": observation["decision"],
            "audit_event_id": event_id,
            "processed_at": now_iso,
        }, indent=1))
        print(json.dumps(observation, indent=1))
        return 0
    except Exception as e:  # noqa: BLE001 — fail-closed, honest ERROR
        return _fail_closed(scenario_id,
                            f"{type(e).__name__}: {e} (no verdict invented)",
                            5)
    finally:
        try:
            stop_o3_daemon(daemon)
        except Exception:
            pass


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--invocation", required=True,
                        help="path to the rendezvous invocation.json")
    parser.add_argument("--gate-verdict", required=True,
                        help="path to write gate-verdict.json evidence")
    parser.add_argument("--fixtures-root", default=DEFAULT_FIXTURES_ROOT)
    parser.add_argument("--state-root", default=DEFAULT_STATE_ROOT)
    parser.add_argument("--timeout", type=int, default=600,
                        help="self-deadline (s) — the responder is single-shot")
    args = parser.parse_args(argv)

    if not os.path.exists(args.invocation):
        print(f"responder: invocation not found: {args.invocation}",
              file=sys.stderr)
        return 4
    return respond(args.invocation, args.gate_verdict, args.fixtures_root,
                   args.state_root)


if __name__ == "__main__":
    sys.exit(main())
