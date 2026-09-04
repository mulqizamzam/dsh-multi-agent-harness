"""CTO smoke: single reversible invariant proof."""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class TestCtoSmokeInvariant:
    def test_cto_smoke_root_completes_only_when_done_evidence_reviews_accepted(self):
        from orchestrator.organization import TypedHandoff
        from orchestrator.organization.root import build_verdict

        ho_done = TypedHandoff(
            mission_id="cto-smoke-20250903-001", task_id="impl", owner="kai", role="kai",
            status="done", summary="done", findings=("f",),
            evidence=("test:log", "artifact:patch"), artifacts=(), changed_files=(), risks=(), unknowns=(), next=(),
        )
        ho_missing_evidence = TypedHandoff(
            mission_id="cto-smoke-20250903-001", task_id="impl", owner="kai", role="kai",
            status="done", summary="done", findings=("f",),
            evidence=("test:log",), artifacts=(), changed_files=(), risks=(), unknowns=(), next=(),
        )
        ho_blocked = TypedHandoff(
            mission_id="cto-smoke-20250903-001", task_id="impl", owner="kai", role="kai",
            status="blocked", summary="blocked", findings=("f",),
            evidence=("test:log", "artifact:patch"), artifacts=(), changed_files=(), risks=(), unknowns=(), next=(),
        )
        req_evidence = {"impl": ("test", "artifact")}
        expected_reviewers = {"impl": ("badsector",)}
        reviews_accepted = [{"reviewer": "badsector", "target_task_id": "impl", "action": "accept"}]

        # missing evidence must BLOCK even with done + accepted review
        v1 = build_verdict(mission_id="cto-smoke-20250903-001", handoffs={"impl": ho_missing_evidence},
                           expected_tasks=("impl",), reviews=reviews_accepted,
                           required_evidence=req_evidence, expected_reviewers=expected_reviewers)
        assert v1.outcome == "BLOCKED" and "evidence" in v1.reason.lower()

        # missing reviewer acceptance must BLOCK even with done + full evidence
        v2 = build_verdict(mission_id="cto-smoke-20250903-001", handoffs={"impl": ho_done},
                           expected_tasks=("impl",), reviews=[],
                           required_evidence=req_evidence, expected_reviewers=expected_reviewers)
        assert v2.outcome == "BLOCKED" and "review" in v2.reason.lower()

        # not done must BLOCK even with evidence + accepted review
        v3 = build_verdict(mission_id="cto-smoke-20250903-001", handoffs={"impl": ho_blocked},
                           expected_tasks=("impl",), reviews=reviews_accepted,
                           required_evidence=req_evidence, expected_reviewers=expected_reviewers)
        assert v3.outcome == "BLOCKED"

        # all satisfied → COMPLETE
        v4 = build_verdict(mission_id="cto-smoke-20250903-001", handoffs={"impl": ho_done},
                           expected_tasks=("impl",), reviews=reviews_accepted,
                           required_evidence=req_evidence, expected_reviewers=expected_reviewers)
        assert v4.outcome == "COMPLETE"
