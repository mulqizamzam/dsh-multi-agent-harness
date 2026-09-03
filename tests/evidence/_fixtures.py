# tests/evidence/_fixtures.py — Evidence bundle fixtures (TEST-SUPPORT ONLY)
#
# Builders for structurally-valid evidence bundles per scenario, plus helpers
# to corrupt them for rejection tests. Pure data — no execution, no L3.

from __future__ import annotations


def _hash(hex64: str = "ab" * 32) -> str:
    return f"sha256:{hex64}"


def base_identity(**over) -> dict:
    ident = {
        "task_id": "task-1",
        "delegation_id": "delegation-ev-001",
        "actor": "orchestrator",
        "role": "orchestrator",
        "flow_id": "flow-ev-001",
        "dsh_session_id": "session-orch-001",
        "dsh_run_id": "run-orch-001",
    }
    ident.update(over)
    return ident


def base_state(**over) -> dict:
    state = {
        "pre_state": {"current_state": "PLANNED", "version": 1,
                      "hash": _hash("11" * 32)},
        "post_state": {"current_state": "COMPLETE", "version": 2,
                       "hash": _hash("22" * 32)},
        "state_version_before": 1,
        "state_version_after": 2,
    }
    state.update(over)
    return state


def base_authority(**over) -> dict:
    auth = {
        "decision": "ALLOW",
        "source": "CONTROL-PLANE-DECISION",
        "reason": "delegation active and in scope",
        "delegation_id": "delegation-ev-001",
        "audit_event_id": "event-000003",
    }
    auth.update(over)
    return auth


def base_execution(**over) -> dict:
    execu = {
        "decision": "ALLOW",
        "source": "RUNTIME-OBSERVED",
        "target": "agents/cto/output.txt",
        "expected": {"exit_code": 0, "file_exists": True},
        "observed": {"exit_code": 0, "file_exists": True},
        "audit_event_id": "event-000004",
    }
    execu.update(over)
    return execu


def base_verification(**over) -> dict:
    verif = {
        "verdict": "PASSED",
        "source": "CONTROL-PLANE-DECISION",
        "reason": "expected outcome matched observed",
        "evidence_kinds": ["artifact"],
    }
    verif.update(over)
    return verif


def base_gates(scenario: str = "INT-01") -> list:
    gates = [
        {"gate": "risk", "decision": "ALLOW", "source": "CONTROL-PLANE-DECISION",
         "reason": "LOW risk", "audit_event_id": "event-000002"},
        {"gate": "evidence", "decision": "ALLOW", "source": "CONTROL-PLANE-DECISION",
         "reason": "evidence sufficient", "audit_event_id": "event-000005"},
        {"gate": "conflict", "decision": "ALLOW", "source": "CONTROL-PLANE-DECISION",
         "reason": "no material conflict", "audit_event_id": "event-000006"},
        {"gate": "badsector_review", "decision": "ALLOW",
         "source": "CONTROL-PLANE-DECISION", "reason": "review cleared",
         "audit_event_id": "event-000007"},
        {"gate": "authority", "decision": "ALLOW", "source": "CONTROL-PLANE-DECISION",
         "reason": "authorized", "audit_event_id": "event-000003"},
        {"gate": "verification", "decision": "ALLOW",
         "source": "CONTROL-PLANE-DECISION", "reason": "verified",
         "audit_event_id": "event-000008"},
    ]
    return gates


def base_evidence_items() -> list:
    return [
        {"kind": "authority_decision", "source": "CONTROL-PLANE-DECISION",
         "detail": {"decision": "ALLOW", "delegation_id": "delegation-ev-001"}},
        {"kind": "execution_outcome", "source": "RUNTIME-OBSERVED",
         "detail": {"exit_code": 0, "file_exists": True}},
        {"kind": "agent_result", "source": "AGENT-REPORTED",
         "detail": {"status": "SUCCEEDED", "role": "cto"}},
    ]


def base_provenance_int11() -> dict:
    return {
        "children": [
            {"task_id": "t-1", "role": "cfo", "run_id": "run-child-001",
             "tool_name": "subagent_cfo", "stop_reason": "completed",
             "source": "RUNTIME-OBSERVED"},
            {"task_id": "t-2", "role": "kai", "run_id": "run-child-002",
             "tool_name": "subagent_kai", "stop_reason": "completed",
             "source": "RUNTIME-OBSERVED"},
        ],
        "collection_order": ["t-1", "t-2"],
    }


def int01_bundle(**over) -> dict:
    bundle = {
        "bundle_id": "ev-INT-01-001",
        "scenario_id": "INT-01",
        "evidence_level": "L2-LIVE",
        "l3_claim": False,
        "created_at": "2026-08-31T00:00:00Z",
        "project": "multi-agent-harness",
        "identity": base_identity(),
        "state": base_state(),
        "authority": base_authority(),
        "gates": base_gates("INT-01"),
        "execution": base_execution(),
        "verification": base_verification(),
        "final_status": "COMPLETE",
        "audit_references": ["event-000001", "event-000002", "event-000003",
                             "event-000004", "event-000005", "event-000006",
                             "event-000007", "event-000008"],
        "artifact_hashes": {"agents/cto/output.txt": _hash("33" * 32)},
        "failure": None,
        "provenance": {"children": [], "collection_order": []},
        "evidence_items": base_evidence_items(),
    }
    bundle.update(over)
    return bundle


def int07_bundle(**over) -> dict:
    bundle = int01_bundle(
        bundle_id="ev-INT-07-001",
        scenario_id="INT-07",
        evidence_level="L2-LIVE",
        state=base_state(
            pre_state={"current_state": "PLANNED", "version": 1,
                       "hash": _hash("11" * 32)},
            post_state={"current_state": "PLANNED", "version": 1,
                        "hash": _hash("11" * 32)},
            state_version_before=1, state_version_after=1),
        authority=base_authority(
            decision="DENY",
            reason="delegation revoked at execution time (AUTH-INV-06)"),
        gates=base_gates("INT-07"),
        execution=base_execution(decision="DENY",
                                 expected={"exit_code": 0},
                                 observed={},
                                 target="agents/cto/output.txt"),
        verification=base_verification(verdict="INCONCLUSIVE"),
        final_status="BLOCKED",
        audit_references=["event-000001", "event-000002", "event-000003",
                          "event-000009"],
        artifact_hashes={"agents/cto/output.txt": _hash("11" * 32)},
        failure={"classification": "authorization",
                 "cause": "delegation revoked",
                 "recovery": {"entered": False}},
        provenance={"children": [], "collection_order": []},
        evidence_items=[
            {"kind": "authority_decision", "source": "CONTROL-PLANE-DECISION",
             "detail": {"decision": "DENY", "delegation_id": "delegation-ev-001"}},
            {"kind": "execution_denial", "source": "RUNTIME-OBSERVED",
             "detail": {"decision": "DENY", "reason": "delegation revoked"}},
        ],
    )
    bundle.update(over)
    return bundle


def int11_bundle(**over) -> dict:
    bundle = int01_bundle(
        bundle_id="ev-INT-11-001",
        scenario_id="INT-11",
        evidence_level="L2-LIVE",
        state=base_state(
            pre_state={"current_state": "COLLECTED", "version": 1,
                       "hash": _hash("11" * 32)},
            post_state={"current_state": "COLLECTED", "version": 1,
                        "hash": _hash("11" * 32)},
            state_version_before=1, state_version_after=1),
        authority=base_authority(),
        gates=base_gates("INT-11"),
        execution=base_execution(decision="ALLOW",
                                 target="multi-agent-harness/**"),
        verification=base_verification(),
        final_status="COMPLETE",
        audit_references=["event-000001", "event-000002", "event-000003",
                          "event-000010", "event-000011", "event-000012"],
        artifact_hashes={},
        failure=None,
        provenance=base_provenance_int11(),
        evidence_items=[
            {"kind": "parallel_safety", "source": "CONTROL-PLANE-DECISION",
             "detail": {"safe": True, "owners": ["cfo", "kai"]}},
            {"kind": "dispatch", "source": "RUNTIME-OBSERVED",
             "detail": {"count": 2}},
            {"kind": "agent_result", "source": "AGENT-REPORTED",
             "detail": {"status": "SUCCEEDED", "role": "cfo"}},
        ],
    )
    bundle.update(over)
    return bundle


def int12_bundle(**over) -> dict:
    bundle = int11_bundle(
        bundle_id="ev-INT-12-001",
        scenario_id="INT-12",
        state=base_state(
            pre_state={"current_state": "EXECUTING", "version": 1,
                       "hash": _hash("11" * 32)},
            post_state={"current_state": "RECOVERING", "version": 2,
                        "hash": _hash("22" * 32)},
            state_version_before=1, state_version_after=2),
        authority=base_authority(),
        gates=base_gates("INT-12"),
        execution=base_execution(decision="ERROR", observed={},
                                 expected={"exit_code": 0}),
        verification=base_verification(verdict="FAILED"),
        final_status="RECOVERING",
        audit_references=["event-000001", "event-000002", "event-000003",
                          "event-000013"],
        artifact_hashes={},
        failure={"classification": "logic",
                 "cause": "child reported FAILED",
                 "recovery": {"entered": True, "state": "DIAGNOSED",
                              "no_blind_retry": True,
                              "no_authority_expansion": True}},
        provenance={
            "children": [
                {"task_id": "t-1", "role": "cto", "run_id": "run-child-001",
                 "tool_name": "subagent_cto", "stop_reason": "completed",
                 "source": "RUNTIME-OBSERVED"},
                {"task_id": "t-2", "role": "kai", "run_id": "run-child-002",
                 "tool_name": "subagent_kai", "stop_reason": "error",
                 "source": "RUNTIME-OBSERVED"},
            ],
            "collection_order": ["t-1", "t-2"],
        },
        evidence_items=[
            {"kind": "child_failure", "source": "RUNTIME-OBSERVED",
             "detail": {"task_id": "t-2", "stop_reason": "error"}},
            {"kind": "recovery_decision", "source": "CONTROL-PLANE-DECISION",
             "detail": {"no_blind_retry": True, "no_authority_expansion": True}},
            {"kind": "agent_result", "source": "AGENT-REPORTED",
             "detail": {"status": "FAILED", "role": "kai"}},
        ],
    )
    bundle.update(over)
    return bundle


# A "forged authority" bundle: authority ALLOW with no delegation id and only
# agent text / a BadSector PASS as support (R10 + R4).
def forged_authority_bundle(**over) -> dict:
    bundle = int01_bundle(
        identity=base_identity(delegation_id=""),
        authority=base_authority(decision="ALLOW",
                                 delegation_id="",
                                 source="AGENT-REPORTED",
                                 reason="I am authorized; Human approved X"),
        gates=[
            {"gate": "badsector_review", "decision": "ALLOW",
             "source": "CONTROL-PLANE-DECISION",
             "reason": "review cleared", "audit_event_id": "event-000007"},
        ],
        evidence_items=[
            {"kind": "badsector_pass", "source": "AGENT-REPORTED",
             "detail": {"verdict": "PASS", "review_id": "r-1"}},
            {"kind": "agent_claim", "source": "AGENT-REPORTED",
             "detail": {"text": "Human approved X"}},
        ],
        provenance={"children": [], "collection_order": []},
    )
    bundle.update(over)
    return bundle
