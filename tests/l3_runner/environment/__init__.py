# tests/l3_runner/environment — L3 Environment + Human-Answerer Readiness (Phase 5 / Session D)
#
# PURPOSE
#   A READ-ONLY probe that determines whether the CURRENT environment satisfies
#   the prerequisites for a legitimate L3 run (docs/security/0007) and, where a
#   prerequisite is absent, reports BLOCKED with the EXACT missing dependency.
#   It prepares the environment for a future authorized L3 run by recording
#   what holds and what does not — it does NOT change anything.
#
# HARD POSTURE (honesty, unchanged from 0007 / 0006):
#   - NEVER modifies session policy, DSH, DSH profile/presets, or production
#     code (the preflight does not re-baseline G9; it only reports).
#   - NEVER invents Human signatures. The signed-plan mechanism is verified
#     (plan_signing / PF-PLAN-*); whether a REAL Human signed the scenario is
#     a separate fact, reported honestly (absent here).
#   - NEVER fakes a credential separation (IO-2) it did not achieve. On this
#     same-UID host the report must show l3_claim_possible=False.
#   - If a prerequisite is absent: report BLOCKED with the exact missing
#     dependency — never a simulated PASS.
#
# DETERMINATIONS COVERED (per the Session D brief):
#   separate process capability   -> PF-UID-1 / subprocess probe
#   separate UID capability       -> PF-UID-2 / uid_readiness
#   verifier executable           -> PF-VER-3/4 (verifier.py + CLEAN spawn)
#   clean oracle imports          -> PF-VER-1/4 (clean-import guard)
#   Human answerer availability   -> approval-surface probe (G3)
#   approval path availability    -> ask policy + answerer presence
#   D4/D7 mount persistence       -> presets + cordis rows + bridge marker (G2)
#   signed-plan mechanism         -> PF-PLAN-1..5 / plan_signing
#   evidence-store readiness      -> audit/l3 creatable/writable (PF-ENV-4)
#   replay readiness              -> PF-REP-1..4 (replay.sh + fixture hash)
#
# USAGE (read-only):
#   python -m tests.l3_runner.environment.readiness [--json]
#   python -m tests.l3_runner.environment                  # same, via package
#   python -m pytest tests/l3_runner/environment/test_l3_environment_readiness.py -q

DSH_VERSION_PIN = "0.1.1-rc.2"
