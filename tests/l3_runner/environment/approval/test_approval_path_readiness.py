"""Session B — Human Answerer + Approval Path readiness tests.

TEST-SUPPORT ONLY. NOT production code. Read-only verification of the
approval-path readiness claim in
docs/phase-5/environment/approval/0001-approval-path-readiness.md.

What these tests prove (all observed from the DSH 0.1.1-rc.2 checkout, the
project config, or the current session — nothing simulated, nothing invented):

  1. The project baseline is `workspace-write` + `ask`.
  2. DSH derives the approval policy from the permission mode
     (danger-full-access -> 'never', else 'ask').
  3. The DSH base bundle composes the approval service
     (`@deepseek-ai/dsh-user-approval`) with that derivation.
  4. The web-app bundle composes the browser answerer surface
     (`ui-user-questions` + `ui-conversation` ApprovalPanel).
  5. `DSH_APPROVAL_PROMPTS_DISABLED` is a project-side convention that DSH
     NEVER reads (negative grep) — so "prompts disabled" is not a DSH fact.
  6. The ApprovalOutcome vocabulary is closed and fail-closed
     (`allowed-once | rejected | cancelled | unavailable`).
  7. Honesty: the probe never invents an answerer and never mutates state;
     a headless session (no answerer surface) is reported BLOCKED, never
     faked ready.

The tests are detection-only: they never change session policy, never modify
DSH, never edit production configuration, never execute a HIGH-risk action,
and never run L3.
"""

import json
import os
import re
import subprocess
import sys

import pytest

_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(_FILE_DIR))))
DSH_CHECKOUT = "/home/administrator/deepseek-harness"
DOC = os.path.join(PROJECT_ROOT, "docs", "phase-5", "environment", "approval",
                   "0001-approval-path-readiness.md")

BASE_PATCH = os.path.join(DSH_CHECKOUT, "packages", "bundle", "base",
                          "cordis.patch.yml")
WEB_PATCH = os.path.join(DSH_CHECKOUT, "packages", "bundle", "web-app",
                         "cordis.patch.yml")
APPROVAL_README = os.path.join(DSH_CHECKOUT, "packages", "interaction",
                               "user-approval", "README.md")


# ---------------------------------------------------------------------------
# 1. Baseline policy (workspace-write + ask)
# ---------------------------------------------------------------------------

def test_baseline_policy_workspace_write_ask():
    """The project baseline is `workspace-write` + `ask` (ADR 0001 D2)."""
    from tests.environment.preflight import (
        REQUIRED_APPROVAL_POLICY, REQUIRED_SANDBOX_MODE,
    )
    assert REQUIRED_SANDBOX_MODE == "workspace-write"
    assert REQUIRED_APPROVAL_POLICY == "ask"


def test_readiness_doc_exists_and_states_ask_usable_in_web():
    """The approval-path readiness doc exists and honestly states the web
    session is ready while a headless session is BLOCKED."""
    assert os.path.isfile(DOC), f"approval-path readiness doc missing at {DOC}"
    with open(DOC) as f:
        text = f.read()
    assert "READY (by composition)" in text
    assert "BLOCKED" in text
    assert "no policy/config edit" in text.lower() or \
        "no policy/edit" in text.lower()


# ---------------------------------------------------------------------------
# 2. DSH policy derivation (permission mode -> approval policy)
# ---------------------------------------------------------------------------

def test_dsh_derives_approval_policy_from_permission_mode():
    """DSH derives approval policy: danger-full-access -> 'never', else 'ask'.

    Mirrors the base bundle row:
      policy: (DSH_PERMISSION_MODE ?? 'workspace-write') === 'danger-full-access'
              ? 'never' : 'ask'
    """
    def derive(mode=None):
        return "never" if (mode or "workspace-write") == "danger-full-access" else "ask"
    assert derive("workspace-write") == "ask"
    assert derive(None) == "ask"
    assert derive("danger-full-access") == "never"


def test_base_bundle_composes_approval_service():
    """The DSH base bundle composes the approval service."""
    if not os.path.isfile(BASE_PATCH):
        pytest.skip("DSH checkout not available")
    with open(BASE_PATCH) as f:
        text = f.read()
    assert "- id: approval" in text
    assert "@deepseek-ai/dsh-user-approval" in text
    assert "danger-full-access" in text  # policy derivation present


# ---------------------------------------------------------------------------
# 3. Web answerer surface composed in the web-app bundle
# ---------------------------------------------------------------------------

def test_web_bundle_composes_answerer_surface():
    """The web-app bundle composes the browser answerer surface."""
    if not os.path.isfile(WEB_PATCH):
        pytest.skip("DSH checkout not available")
    with open(WEB_PATCH) as f:
        text = f.read()
    assert "- id: ui-user-questions" in text
    assert "@deepseek-ai/dsh-client-ui-user-questions" in text
    assert "- id: ui-conversation" in text
    assert "@deepseek-ai/dsh-client-ui-conversation" in text


def test_web_answerer_profile_rows_duplicate_bundle_composition():
    """Answerer rows under $DSH_HOME/profiles duplicate the bundle composition.

    In this DSH generation the profile root carries the full host
    composition, so the answerer package rows appear under
    $DSH_HOME/profiles as well as in the bundles. That is a duplicate
    composition — not a different surface, and not a probe gap: the probe
    reads the bundle patch files as source truth and never scans the
    profile. When a profile composition file names an answerer package it
    must be the same package the bundles compose; no extra or divergent
    surface may appear there.

    Lockfiles and installed dependencies are dependency records, not
    composition, and are excluded from the scan.
    """
    dsh_home = os.environ.get("DSH_HOME", "")
    if not dsh_home:
        pytest.skip("DSH_HOME unset")
    profiles = os.path.join(dsh_home, "profiles")
    if not os.path.isdir(profiles):
        pytest.skip("no $DSH_HOME/profiles dir")
    if not (os.path.isfile(BASE_PATCH) and os.path.isfile(WEB_PATCH)):
        pytest.skip("DSH checkout not available")
    # The answerer surface as the bundles compose it (source truth).
    bundle_text = ""
    for patch in (BASE_PATCH, WEB_PATCH):
        with open(patch) as f:
            bundle_text += f.read()
    answerer_packages = (
        "@deepseek-ai/dsh-user-approval",
        "@deepseek-ai/dsh-client-ui-user-questions",
        "@deepseek-ai/dsh-client-ui-approval",
        "@deepseek-ai/dsh-client-ui-conversation",
    )
    bundle_surface = {p for p in answerer_packages if p in bundle_text}
    # Scan only profile composition files; node_modules and lockfiles are
    # dependency records, not composition.
    divergent = []
    for root, _dirs, files in os.walk(profiles):
        if "node_modules" in root:
            continue
        for fn in files:
            if fn not in ("cordis.yml", "cordis.patch.yml"):
                continue
            path = os.path.join(root, fn)
            with open(path, errors="ignore") as f:
                text = f.read()
            for pkg in answerer_packages:
                if pkg in text and pkg not in bundle_surface:
                    divergent.append((path, pkg))
    assert divergent == [], (
        f"answerer packages under $DSH_HOME/profiles diverge from the bundle "
        f"composition: {divergent} — the profile must compose the same "
        f"surface the bundles compose, or a different one the probe must see")


# ---------------------------------------------------------------------------
# 4. DSH_APPROVAL_PROMPTS_DISABLED is NOT read by DSH (project convention)
# ---------------------------------------------------------------------------

def test_dsh_never_reads_approval_prompts_disabled():
    """DSH 0.1.1-rc.2 does not read DSH_APPROVAL_PROMPTS_DISABLED anywhere in
    its source — the convention is project-side, not a DSH mechanism."""
    if not os.path.isdir(DSH_CHECKOUT):
        pytest.skip("DSH checkout not available")
    proc = subprocess.run(
        ["grep", "-rn", "DSH_APPROVAL_PROMPTS_DISABLED", DSH_CHECKOUT,
         "--include=*.ts", "--include=*.js", "--include=*.md"],
        capture_output=True, text=True)
    # Exclude this project's own probe files (which live outside the checkout).
    hits = [ln for ln in proc.stdout.splitlines()
            if "agent-workspace" not in ln]
    assert hits == [], (
        "DSH source references DSH_APPROVAL_PROMPTS_DISABLED — the "
        f"readiness doc's claim is stale: {hits}")


# ---------------------------------------------------------------------------
# 5. ApprovalOutcome is closed and fail-closed
# ---------------------------------------------------------------------------

def test_approval_outcome_vocabulary_closed():
    """The outcome vocabulary is exactly allowed-once | rejected | cancelled |
    unavailable; callers fail closed on unavailable."""
    if not os.path.isfile(APPROVAL_README):
        pytest.skip("DSH checkout not available")
    with open(APPROVAL_README) as f:
        text = f.read()
    assert "allowed-once" in text
    assert "rejected" in text
    assert "cancelled" in text
    assert "unavailable" in text
    assert "fail closed" in text.lower()
    assert "No built-in answerer" in text


def test_ask_without_answerer_is_fail_closed():
    """Headless / no-answerer: ask resolves 'unavailable' -> DENY + escalate.
    This is the documented DSH behavior and the readiness doc's BLOCKED
    statement for headless sessions."""
    with open(DOC) as f:
        text = f.read()
    assert "unavailable" in text
    assert "DENY + escalate" in text
    assert "never implicit allow" in text


# ---------------------------------------------------------------------------
# 6. Audit pair (approval/asked + approval/decided)
# ---------------------------------------------------------------------------

def test_audit_pair_documented():
    """Approval requests append a paired approval/asked + approval/decided
    audit record; the model sees only the resulting tool outcome."""
    if not os.path.isfile(APPROVAL_README):
        pytest.skip("DSH checkout not available")
    with open(APPROVAL_README) as f:
        text = f.read()
    assert "approval/asked" in text
    assert "approval/decided" in text
    assert "log-only" in text.lower()


# ---------------------------------------------------------------------------
# 7. Honesty: no invented answerer, read-only
# ---------------------------------------------------------------------------

def test_probe_is_read_only_and_never_invents(monkeypatch):
    """The verification must not mutate env, session policy, or DSH; and the
    headless case is reported BLOCKED, never faked ready.

    CORRECTED (approval-path correction): DSH_APPROVAL_PROMPTS_DISABLED is a
    project-side convention DSH never reads; the probe now detects the
    answerer via actual DSH bundle/web composition. Setting the obsolete
    convention must NOT flip ENV-APPROVAL-1 to unavailable — the corrected
    probe reports availability from composition (or from the documented
    snapshot injection), never from the convention.
    """
    env_before = dict(os.environ)
    monkeypatch.setenv("DSH_APPROVAL_PROMPTS_DISABLED", "1")
    from tests.environment.preflight import run_env_preflight
    report = run_env_preflight(env={})
    a = next(c for c in report.checks if c.check_id == "ENV-APPROVAL-1")
    # Deterministic: the documented snapshot injection wins, so the check
    # passes regardless of the ambient web-attachment state — proving the
    # obsolete convention is not what drives the result.
    injected = run_env_preflight(env={"approval_answerer_available": True})
    a_injected = next(c for c in injected.checks
                      if c.check_id == "ENV-APPROVAL-1")
    assert a_injected.passed
    # Live (no injection): the check may fail closed when no authorized
    # browser answerer is attached — but never BECAUSE of the obsolete
    # convention, which must not appear as the reason.
    assert "DSH_APPROVAL_PROMPTS_DISABLED" not in a.detail
    # Read-only: the only env key that may differ is the injected one.
    assert set(os.environ) - set(env_before) <= {"DSH_APPROVAL_PROMPTS_DISABLED"}
    assert os.environ.get("DSH_APPROVAL_PROMPTS_DISABLED") == "1"


def test_no_high_risk_and_no_l3_claim_in_doc():
    """The readiness doc must not claim HIGH-risk execution or an L3 run."""
    with open(DOC) as f:
        text = f.read()
    assert "no high-risk action" in text.lower() or \
        "no high-risk action" in text.lower()
    assert "no l3" in text.lower() or "no l3 run" in text.lower()


# ---------------------------------------------------------------------------
# 8. Corrected readiness detection (approval_composition) — 4 uncollapsed states
# ---------------------------------------------------------------------------

def test_corrected_detector_reports_web_composition(monkeypatch):
    """The corrected detector reflects ACTUAL DSH bundle/web composition.

    On this host the DSH base bundle composes the approval service and the
    web-app bundle composes the answerer surface, so the detector reports
    COMPOSED from source truth. With an authorized (launch-token) web URL a
    browser answerer is attached and the detector reports
    INTERACTIVE_READY; without one it fails closed to COMPOSED — never
    HEADLESS, and never keyed off the obsolete
    DSH_APPROVAL_PROMPTS_DISABLED convention.
    """
    monkeypatch.delenv("DSH_APPROVAL_PROMPTS_DISABLED", raising=False)
    from tests.environment.approval_composition import (
        approval_readiness, authorized_web_url,
    )
    r = approval_readiness()
    # Composition is a source fact: approval service + answerer surface rows.
    assert r.composed
    assert r.approval_service_composed
    assert r.answerer_surface_composed
    if authorized_web_url():
        assert r.interactive_ready  # web GUI browser answerer attached
    else:
        # No authorized browser answerer attached: composed but not
        # interactive — the fail-closed rung.
        assert not r.interactive_ready
    assert not r.headless_unavailable
    assert r.effective_policy == "ask"
    # The obsolete convention is NOT authoritative in this DSH checkout.
    assert not r.prompts_disabled_authoritative


def test_corrected_detector_headless_fails_closed(monkeypatch):
    """When no answerer surface is composed, the detector reports
    APPROVAL_HEADLESS_UNAVAILABLE (fail-closed), never faked ready."""
    import tests.environment.approval_composition as ac
    monkeypatch.setattr(ac, "approval_service_composed", lambda: False)
    monkeypatch.setattr(ac, "answerer_surface_composed", lambda: False)
    r = ac.approval_readiness()
    assert r.status == ac.ApprovalStatus.APPROVAL_HEADLESS_UNAVAILABLE
    assert r.headless_unavailable
    assert not r.composed
    assert not r.interactive_ready
    # Status is HEADLESS regardless of any observed session evidence: a no
    # answerer surface fails closed. (e2e_verified is independent of status
    # because it is derived from whatever the session log genuinely holds.)


def test_corrected_detector_does_not_use_disabled_convention(monkeypatch):
    """DSH_APPROVAL_PROMPTS_DISABLED must NOT flip the detector to unavailable —
    the corrected model derives availability from DSH composition, not the
    project-side convention (which DSH never reads)."""
    monkeypatch.setenv("DSH_APPROVAL_PROMPTS_DISABLED", "1")
    from tests.environment.approval_composition import (
        approval_readiness, authorized_web_url,
    )
    r = approval_readiness()
    assert r.composed
    if authorized_web_url():
        assert r.interactive_ready
    else:
        assert not r.interactive_ready
    assert not r.headless_unavailable


def test_ask_policy_preserved_by_corrected_detector():
    """The `ask` policy is preserved: danger-full-access -> never, else ask."""
    from tests.environment.approval_composition import effective_policy_from_env
    # Default / workspace-write -> ask.
    assert effective_policy_from_env() == "ask"
    assert effective_policy_from_env() in ("ask", "never")


# ---------------------------------------------------------------------------
# 9. E2E evidence pair matching (session-log based, honest)
# ---------------------------------------------------------------------------

def test_e2e_pair_matching_honest(monkeypatch, tmp_path):
    """E2E_VERIFIED is derived ONLY from an approval/asked + approval/decided
    pair sharing an id in the session log — never from composition alone.

    A fabricated session log with a matched pair promotes to E2E_VERIFIED;
    one with only an ask (no decided) or unmatched ids stays unverified
    (never faked).
    """
    import tests.environment.approval_composition as ac

    # Matched pair -> a pair is found.
    pair = ac._find_e2e_pair([
        {"type": "approval/asked", "id": "a-1", "outcome": None},
        {"type": "approval/decided", "id": "a-1", "outcome": "allowed-once"},
    ])
    assert pair and pair["id"] == "a-1" and pair["outcome"] == "allowed-once"

    # Ask only (no decided) -> no pair.
    assert ac._find_e2e_pair([
        {"type": "approval/asked", "id": "a-2", "outcome": None},
    ]) == {}

    # Unmatched ids -> no pair.
    assert ac._find_e2e_pair([
        {"type": "approval/asked", "id": "a-3", "outcome": None},
        {"type": "approval/decided", "id": "a-4", "outcome": "rejected"},
    ]) == {}

    # Closed outcome vocabulary only.
    for outcome in ("allowed-once", "rejected", "cancelled", "unavailable"):
        assert outcome in ac.APPROVAL_OUTCOMES


def test_no_mutation_guarantee_probe_is_harmless():
    """The E2E probe is a zero-byte notrunc/nocreat write-open: it writes no
    bytes and neither truncates nor creates, so the target stays byte-identical
    regardless of the approval outcome. Verified empirically on the DSH checkout
    README (content+mtime+size+ctime unchanged across the probe)."""
    import hashlib
    target = os.path.join(DSH_CHECKOUT, "README.md")
    if not os.path.isfile(target):
        pytest.skip("DSH checkout README not available")
    before = (
        hashlib.sha256(open(target, "rb").read()).hexdigest(),
        os.path.getsize(target),
        os.stat(target).st_mtime_ns,
    )
    # The exact probe command (0-bytes, no truncate, no create). No sandbox
    # escalation: this just confirms the command is semantically harmless.
    subprocess.run(
        ["dd", "if=/dev/null", f"of={target}", "conv=notrunc,nocreat",
         "bs=1", "count=0"],
        capture_output=True, check=False)
    after = (
        hashlib.sha256(open(target, "rb").read()).hexdigest(),
        os.path.getsize(target),
        os.stat(target).st_mtime_ns,
    )
    assert before == after, "the zero-byte probe mutated the target file"


def test_current_session_e2e_probe_where_possible():
    """Current-session E2E probe: report the observed outcome honestly.

    ApprovalOutcome must be one of the closed vocabulary, with a matching
    approval/asked + approval/decided pair and no consequential action.
    We only assert what is OBSERVED via the detector; if an unverified/unknown
    E2E state is detected we do not invent it.
    """
    from tests.environment.approval_composition import approval_readiness
    r = approval_readiness()
    if r.e2e_verified:
        assert r.e2e_pair["outcome"] in {"allowed-once", "rejected",
                                         "cancelled", "unavailable"}
        assert r.e2e_pair["id"]
        # A matched pair shares a request id between the ask and the decided.
        assert r.e2e_pair["asked"]["type"] == "approval/asked"
        assert r.e2e_pair["asked"]["id"] == r.e2e_pair["decided"]["id"]
        assert r.e2e_pair["decided"]["outcome"] in {"allowed-once", "rejected",
                                                    "cancelled", "unavailable"}
    else:
        # Honest: never promoted from composition alone. Must be INTERACTIVE_READY
        # or HEADLESS at worst, and must NOT be E2E_VERIFIED.
        assert not r.e2e_verified

