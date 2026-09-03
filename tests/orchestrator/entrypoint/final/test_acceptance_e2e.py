# tests/orchestrator/entrypoint/final/test_acceptance_e2e.py — FINAL E2E
# ACCEPTANCE for orchestrator.entrypoint (Front Door V1)
#
# Phase 5 / FINAL ACCEPTANCE HARDENING.
#
# Fresh-execution acceptance baseline for:
#   CLI / JSON stdin → FrontDoor → resolve existing Delegation →
#   ProductionRun → structured terminal result.
#
# Every test seeds a FRESH disposable workspace (tmp_path) and runs the REAL
# module `python -m orchestrator.entrypoint` via subprocess with a REAL
# FileDelegationProvider against a REAL registry document — no stub, no
# in-process shortcut. Results recorded are the current, exact outcomes.
#
# Write-only scope: tests/orchestrator/entrypoint/final/ (+ docs).
# No production implementation, ProductionRun/ExecutionFlow, DSH, session
# policy, roles/config, G10/G13/L3 change. No idempotency/web server/new DSH
# tool.

import json
import os

import pytest

from _fixtures import (
    DEFAULT_DELEGATION_ID,
    parse_envelope,
    run_cli,
    seed_workspace,
    sha256,
    ledger_event_ids,
)

COMPLETE, BLOCKED, ESCALATED, ERROR = "COMPLETE", "BLOCKED", "ESCALATED", "ERROR"

HAPPY_ARGS = ["--objective", "research",
              "--scope", "docs/notes.md",
              "--delegation-id", DEFAULT_DELEGATION_ID]


def _assert_registry_unchanged(paths, pre_hashes):
    """Assert delegation + revocation registry files are byte-identical."""
    for key in ("delegations", "revocations"):
        assert sha256(paths[key]) == pre_hashes[key], (
            f"{key}.json mutated by the front door (registry write!)")


# ---------------------------------------------------------------------------
# 1. COMPLETE — happy path
# ---------------------------------------------------------------------------

class TestCompleteHappyPath:
    def test_happy_path_complete(self, ws):
        """research/docs with a valid ACTIVE delegation → COMPLETE, exit 0."""
        paths = seed_workspace(ws)
        pre = {"delegations": sha256(paths["delegations"]),
               "revocations": sha256(paths["revocations"])}
        proc = run_cli(HAPPY_ARGS, ws=ws)
        env = parse_envelope(proc)

        assert proc.returncode == 0, proc.stderr
        assert env["status"] == COMPLETE
        assert env["schema"] == "run-result@1"
        # A run actually started: run_id + state + report exist.
        assert env["run_id"] and env["run_id"].startswith("prod-")
        assert env["state"] is not None
        assert env["state"]["outcome"] == "complete"
        assert env["state"]["run_id"] == env["run_id"]
        assert env["report"] is not None
        # COMPLETE requires verification PASSED (AUTH-INV-15).
        assert env["report"]["outcome"] == "COMPLETE"
        assert env["report"]["verification"]["verdict"] == "PASSED"
        assert env["errors"] == []
        # Registry read-only: byte-identical pre/post.
        _assert_registry_unchanged(paths, pre)

    def test_happy_path_audit_ids_are_real_events(self, ws):
        """Every audit_id in the COMPLETE envelope exists on-disk in the
        ledger audit/<project>/events.jsonl — no fabricated ids."""
        paths = seed_workspace(ws)
        proc = run_cli(HAPPY_ARGS, ws=ws)
        env = parse_envelope(proc)
        assert env["status"] == COMPLETE
        ids = env.get("audit_ids") or []
        assert len(ids) > 0, "COMPLETE run must record audit events"
        on_disk = ledger_event_ids(paths["audit_ledger"])
        for aid in ids:
            assert aid in on_disk, \
                f"audit_id {aid!r} not found in ledger {paths['audit_ledger']}"

    def test_happy_path_state_written_on_disk(self, ws):
        """The on-disk project state shows task-1 COMPLETE after a COMPLETE
        envelope — no fabricated state."""
        paths = seed_workspace(ws)
        proc = run_cli(HAPPY_ARGS, ws=ws)
        env = parse_envelope(proc)
        assert env["status"] == COMPLETE
        with open(paths["state"]) as f:
            state = json.load(f)
        tasks = state.get("task_machines", {})
        assert tasks.get("task-1", {}).get("state") == "COMPLETE", state


# ---------------------------------------------------------------------------
# 2. BLOCKED — unknown delegation
# ---------------------------------------------------------------------------

class TestBlockedUnknownDelegation:
    def test_unknown_delegation_blocked(self, ws):
        """delegation-unknown-999 → BLOCKED, exit 2, no run created."""
        seed_workspace(ws)
        proc = run_cli(["--objective", "research",
                        "--scope", "docs/notes.md",
                        "--delegation-id", "delegation-unknown-999"],
                       ws=ws)
        env = parse_envelope(proc)
        assert proc.returncode == 2
        assert env["status"] == BLOCKED
        # run_id only exists when a run actually starts.
        assert env["run_id"] is None
        assert env["state"] is None
        assert env["report"] is None
        assert env["audit_ids"] == []
        assert len(env["errors"]) > 0
        assert "does not match" in env["errors"][0]

    def test_blocked_no_registry_mutation(self, ws):
        """BLOCKED path also leaves the registry untouched."""
        paths = seed_workspace(ws)
        pre = {"delegations": sha256(paths["delegations"]),
               "revocations": sha256(paths["revocations"])}
        run_cli(["--objective", "research",
                 "--scope", "docs/notes.md",
                 "--delegation-id", "delegation-unknown-999"],
                ws=ws)
        _assert_registry_unchanged(paths, pre)


# ---------------------------------------------------------------------------
# 3. ESCALATED — evidence failure
# ---------------------------------------------------------------------------

class TestEscalatedEvidence:
    def test_escalated_evidence_gate(self, ws):
        """MEDIUM write action with no evidence → ESCALATED at the evidence
        gate (EVID-001), exit 3. No fabricated report."""
        seed_workspace(ws)
        proc = run_cli(["--objective", "engineering",
                        "--scope", "agents/cto/output.txt",
                        "--delegation-id", DEFAULT_DELEGATION_ID],
                       ws=ws)
        env = parse_envelope(proc)
        assert proc.returncode == 3
        assert env["status"] == ESCALATED
        # The run started (run_id exists) but did not complete.
        assert env["run_id"] and env["run_id"].startswith("prod-")
        assert env["state"] is not None
        assert env["state"]["outcome"] in ("escalated", "stopped")
        # No fabricated success report from an escalated run.
        assert env["report"] is None
        err_text = " ".join(env["errors"]).lower()
        assert "evidence" in err_text and "evid-001" in err_text, env["errors"]

    def test_escalated_audit_ids_are_real_events(self, ws):
        """ESCALATED audit ids reflect the actual gate-denial events."""
        paths = seed_workspace(ws)
        proc = run_cli(["--objective", "engineering",
                        "--scope", "agents/cto/output.txt",
                        "--delegation-id", DEFAULT_DELEGATION_ID],
                       ws=ws)
        env = parse_envelope(proc)
        assert env["status"] == ESCALATED
        ids = env.get("audit_ids") or []
        assert len(ids) > 0, "an escalated run must record gate events"
        on_disk = ledger_event_ids(paths["audit_ledger"])
        for aid in ids:
            assert aid in on_disk, \
                f"audit_id {aid!r} not found in ledger for ESCALATED run"

    def test_escalated_no_registry_mutation(self, ws):
        """ESCALATED path leaves the registry untouched."""
        paths = seed_workspace(ws)
        pre = {"delegations": sha256(paths["delegations"]),
               "revocations": sha256(paths["revocations"])}
        run_cli(["--objective", "engineering",
                 "--scope", "agents/cto/output.txt",
                 "--delegation-id", DEFAULT_DELEGATION_ID],
                ws=ws)
        _assert_registry_unchanged(paths, pre)


# ---------------------------------------------------------------------------
# 4. ERROR — malformed / empty input
# ---------------------------------------------------------------------------

class TestErrorMalformedInput:
    @pytest.mark.parametrize("argv, needle", [
        (["--objective", "", "--scope", "docs/notes.md",
          "--delegation-id", DEFAULT_DELEGATION_ID], "objective"),
        (["--objective", "research", "--scope", "docs/notes.md"], "delegation"),
        (["--objective", "research", "--scope", "docs/notes.md",
          "--delegation-id", ""], "delegation"),
    ], ids=["empty-objective", "missing-delegation", "empty-delegation"])
    def test_malformed_input_error(self, ws, argv, needle):
        """Malformed/empty required fields → ERROR, exit 1, no run."""
        seed_workspace(ws)
        proc = run_cli(argv, ws=ws)
        env = parse_envelope(proc)
        assert proc.returncode == 1
        assert env["status"] == ERROR
        assert env["run_id"] is None
        assert env["state"] is None
        assert env["report"] is None
        err_text = " ".join(env["errors"]).lower()
        assert needle in err_text, env["errors"]


# ---------------------------------------------------------------------------
# 5. JSON stdin
# ---------------------------------------------------------------------------

class TestJsonStdin:
    def test_json_stdin_happy(self, ws):
        """JSON stdin request → COMPLETE, exit 0 (same path as CLI)."""
        seed_workspace(ws)
        payload = json.dumps({
            "objective": "research",
            "scope": ["docs/notes.md"],
            "delegation_id": DEFAULT_DELEGATION_ID,
        })
        proc = run_cli([], ws=ws, stdin=payload, json_stdin=True)
        env = parse_envelope(proc)
        assert proc.returncode == 0, proc.stderr
        assert env["status"] == COMPLETE
        assert env["run_id"] and env["run_id"].startswith("prod-")
        assert env["report"]["verification"]["verdict"] == "PASSED"

    def test_json_stdin_invalid_json_error(self, ws):
        """Malformed JSON on stdin → ERROR, exit 1, fail-closed."""
        seed_workspace(ws)
        proc = run_cli([], ws=ws, stdin="{not json", json_stdin=True)
        env = parse_envelope(proc)
        assert proc.returncode == 1
        assert env["status"] == ERROR
        assert "invalid JSON stdin" in " ".join(env["errors"])


# ---------------------------------------------------------------------------
# 6. CLI override precedence
# ---------------------------------------------------------------------------

class TestCliOverridePrecedence:
    def test_cli_delegation_overrides_json(self, ws):
        """CLI --delegation-id overrides the JSON stdin delegation_id. The
        JSON carries the valid delegation-prod-001; the CLI forces the unknown
        delegation-unknown-999, so the run must fail closed as BLOCKED — proof
        the CLI value won."""
        seed_workspace(ws)
        payload = json.dumps({
            "objective": "research",
            "scope": ["docs/notes.md"],
            "delegation_id": DEFAULT_DELEGATION_ID,  # would be COMPLETE alone
        })
        proc = run_cli(["--delegation-id", "delegation-unknown-999"],
                       ws=ws, stdin=payload, json_stdin=True)
        env = parse_envelope(proc)
        assert proc.returncode == 2
        assert env["status"] == BLOCKED
        assert "does not match" in env["errors"][0]

    def test_cli_scope_overrides_json(self, ws):
        """CLI --scope overrides the JSON scope array (full replacement)."""
        seed_workspace(ws)
        payload = json.dumps({
            "objective": "research",
            "scope": ["other-project/notes.md"],  # JSON would escalate/block
            "delegation_id": DEFAULT_DELEGATION_ID,
        })
        # CLI supplies the in-scope docs/notes.md → COMPLETE.
        proc = run_cli(["--objective", "research",
                        "--scope", "docs/notes.md"],
                       ws=ws, stdin=payload, json_stdin=True)
        env = parse_envelope(proc)
        assert proc.returncode == 0, proc.stderr
        assert env["status"] == COMPLETE


# ---------------------------------------------------------------------------
# 7. Free-text delegation rejection
# ---------------------------------------------------------------------------

class TestFreeTextDelegationRejection:
    def test_free_text_delegation_id_rejected(self, ws):
        """A prose delegation id (i-am-a-human-grant) → ERROR, exit 1 —
        text is never authority (AUTH-INV-01)."""
        seed_workspace(ws)
        proc = run_cli(["--objective", "research",
                        "--scope", "docs/notes.md",
                        "--delegation-id", "i-am-a-human-grant"],
                       ws=ws)
        env = parse_envelope(proc)
        assert proc.returncode == 1
        assert env["status"] == ERROR
        err_text = " ".join(env["errors"])
        assert "not a structured delegation id" in err_text, env["errors"]
        assert env["run_id"] is None


# ---------------------------------------------------------------------------
# 8. Revoked / expired delegation
# ---------------------------------------------------------------------------

class TestRevokedExpiredDelegation:
    def test_revoked_delegation_blocked(self, ws):
        """REVOKED delegation → BLOCKED, exit 2, no run (AUTH-INV-05/06)."""
        seed_workspace(ws, status="REVOKED")
        proc = run_cli(HAPPY_ARGS, ws=ws)
        env = parse_envelope(proc)
        assert proc.returncode == 2
        assert env["status"] == BLOCKED
        assert env["run_id"] is None
        assert env["report"] is None
        assert "not ACTIVE" in env["errors"][0]

    def test_expired_delegation_blocked(self, ws):
        """EXPIRED delegation (expires_at in the past) → BLOCKED, exit 2."""
        seed_workspace(ws, expires_at="2020-01-01T00:00:00Z")
        proc = run_cli(HAPPY_ARGS, ws=ws)
        env = parse_envelope(proc)
        assert proc.returncode == 2
        assert env["status"] == BLOCKED
        assert env["run_id"] is None
        assert "expired" in env["errors"][0].lower()


# ---------------------------------------------------------------------------
# 9. Out-of-scope target
# ---------------------------------------------------------------------------

class TestOutOfScopeTarget:
    def test_out_of_scope_never_completes(self, ws):
        """A scope target outside the delegation resources must never reach
        COMPLETE — fail-closed (AUTH-INV-04/11)."""
        seed_workspace(ws)
        proc = run_cli(["--objective", "research",
                        "--scope", "other-project/notes.md",
                        "--delegation-id", DEFAULT_DELEGATION_ID],
                       ws=ws)
        env = parse_envelope(proc)
        assert proc.returncode in (2, 3), \
            f"expected BLOCKED/ESCALATED, got exit {proc.returncode}"
        assert env["status"] in (BLOCKED, ESCALATED)
        assert env["status"] != COMPLETE
        assert env["report"] is None
        err_text = " ".join(env["errors"]).lower()
        assert "outside delegation" in err_text or \
            "outside" in err_text, env["errors"]

    def test_out_of_scope_no_fabricated_state(self, ws):
        """The envelope must not claim a completed run for an out-of-scope
        target."""
        seed_workspace(ws)
        proc = run_cli(["--objective", "research",
                        "--scope", "other-project/notes.md",
                        "--delegation-id", DEFAULT_DELEGATION_ID],
                       ws=ws)
        env = parse_envelope(proc)
        assert env["status"] != COMPLETE
        if env["state"]:
            assert env["state"]["outcome"] != "complete"
        assert env["report"] is None


# ---------------------------------------------------------------------------
# 10. Intrinsic HIGH cannot be downgraded
# ---------------------------------------------------------------------------

class TestIntrinsicHighNotDowngradable:
    def test_no_risk_override_surface(self):
        """The front-door request schema has no declared_risk / approval /
        review field — a caller cannot downgrade intrinsic HIGH (AUTH-INV-10).
        Passing such a field is a hard shape error."""
        from orchestrator.entrypoint import FrontDoorRequest
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FrontDoorRequest)}
        for banned in ("declared_risk", "risk", "approval_reference",
                       "review", "status", "permissions"):
            assert banned not in fields, \
                f"FrontDoorRequest must not accept {banned!r}"

    def test_write_action_classified_medium_never_low(self, ws):
        """A write-domain objective is deterministically MEDIUM (never LOW) —
        the classifier is authoritative, not the caller."""
        from orchestrator.production import ObjectivePlanner
        from orchestrator.production.planner import _WRITE_DOMAINS
        planner = ObjectivePlanner(project="multi-agent-harness")
        plan = planner.plan(
            objective="engineering",
            scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
        )
        assert plan.execute_plan.action == "write"
        assert plan.declared_risk == "MEDIUM", plan.declared_risk

    def test_intrinsic_high_write_declared_low_rejected(self, ws):
        """Declaring LOW on an intrinsically-HIGH signal (write on a
        credential-token target) → the planner refuses (AUTH-INV-10) and the
        front door surfaces BLOCKED — never a downgraded COMPLETE."""
        from orchestrator.production import ObjectivePlanner, \
            ObjectiveNotActionable
        planner = ObjectivePlanner(project="multi-agent-harness")
        with pytest.raises(ObjectiveNotActionable):
            planner.plan(
                objective="engineering",
                scope=("other-project/secret.txt",),
                required_authority_context="delegation-prod-001",
                declared_risk="LOW",  # downgrade attempt
            )

    def test_high_signal_through_cli_fails_closed(self, ws):
        """Through the real CLI, an intrinsically-HIGH signal (write touching
        a credential token) fails closed — never COMPLETE (exit 2 observed)."""
        seed_workspace(ws)
        proc = run_cli(["--objective", "engineering",
                        "--scope", "other-project/secret.txt",
                        "--delegation-id", DEFAULT_DELEGATION_ID],
                       ws=ws)
        env = parse_envelope(proc)
        assert proc.returncode in (2, 3)
        assert env["status"] in (BLOCKED, ESCALATED)
        assert env["status"] != COMPLETE
        assert env["report"] is None


# ---------------------------------------------------------------------------
# Cross-cutting verification checks
# ---------------------------------------------------------------------------

class TestCrossCuttingVerification:
    def test_run_id_only_when_run_starts(self, ws):
        """run_id exists iff a run actually started. COMPLETE/ESCALATED runs
        carry run_id; BLOCKED/ERROR pre-run failures carry None."""
        seed_workspace(ws)

        # BLOCKED (unknown delegation) — no run.
        p = run_cli(["--objective", "research",
                     "--scope", "docs/notes.md",
                     "--delegation-id", "delegation-unknown-999"],
                    ws=ws)
        assert parse_envelope(p)["run_id"] is None

        # ERROR (empty objective) — no run.
        p = run_cli(["--objective", "", "--scope", "docs/notes.md",
                     "--delegation-id", DEFAULT_DELEGATION_ID], ws=ws)
        assert parse_envelope(p)["run_id"] is None

    def test_exit_codes_exact(self):
        """Exit codes are exactly COMPLETE=0, ERROR=1, BLOCKED=2, ESCALATED=3."""
        from orchestrator.entrypoint.__main__ import _EXIT_CODE
        from orchestrator.entrypoint import COMPLETE as C, ERROR as E, \
            BLOCKED as B, ESCALATED as X
        assert _EXIT_CODE[C] == 0
        assert _EXIT_CODE[E] == 1
        assert _EXIT_CODE[B] == 2
        assert _EXIT_CODE[X] == 3

    def test_complete_requires_verification_passed(self, ws):
        """COMPLETE is only emitted with a PASSED verification verdict."""
        seed_workspace(ws)
        proc = run_cli(HAPPY_ARGS, ws=ws)
        env = parse_envelope(proc)
        assert env["status"] == COMPLETE
        assert env["report"]["verification"]["verdict"] == "PASSED"
        flow = env["state"].get("flow_result", {})
        assert flow.get("outcome") == "COMPLETE"
        assert flow.get("final_state") == "COMPLETE"

    def test_no_delegation_mutation_across_all_paths(self, ws):
        """One workspace per path; registry bytes identical before/after for
        every terminal state that reaches the registry."""
        for name, argv in [
            ("complete", HAPPY_ARGS),
            ("blocked", ["--objective", "research", "--scope", "docs/notes.md",
                         "--delegation-id", "delegation-unknown-999"]),
            ("escalated", ["--objective", "engineering",
                           "--scope", "agents/cto/output.txt",
                           "--delegation-id", DEFAULT_DELEGATION_ID]),
        ]:
            base = ws + "-" + name
            paths = seed_workspace(base)
            pre = {"delegations": sha256(paths["delegations"]),
                   "revocations": sha256(paths["revocations"])}
            run_cli(argv, ws=base)
            _assert_registry_unchanged(paths, pre)
