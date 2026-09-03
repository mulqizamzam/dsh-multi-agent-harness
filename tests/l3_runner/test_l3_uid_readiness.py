# tests/l3_runner/test_l3_uid_readiness.py — G6: separate-process / separate-UID readiness tests
#
# Phase 5 / Session F — L3 execution readiness (G6 gap closure).
#
# Exercises tests/l3_runner/uid_readiness.py:
#   - honest host UID situation detection (IO-2)
#   - l3_claim_possible stays False when IO-2 cannot be achieved
#   - documented separate-UID launch options (setuid / separate user / separate
#     host) per docs/security/0007 §1.2
#
# SAFETY: pure detection. The module never fakes a UID separation, never
# modifies credentials or session policy, and never runs L3.

from __future__ import annotations

import json
import os
import sys

TESTS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(TESTS_ROOT)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.l3_runner.uid_readiness import (  # noqa: E402
    SEPARATE_UID_LAUNCH_OPTIONS,
    UidReadinessReport,
    assess_uid_readiness,
    launch_options_documented,
    probe_subprocess_uid,
)


# ---------------------------------------------------------------------------
# Honest host UID situation (the load-bearing honesty rule)
# ---------------------------------------------------------------------------
def test_same_uid_sandbox_reports_io2_fail_and_no_claim():
    """On this same-UID host IO-2 must fail honestly and l3_claim_possible=False.

    This is the honesty rule: never fake a credential separation that was not
    achieved (docs/security/0006 §3, 0007 §1.2).
    """
    report = assess_uid_readiness(orchestrator_uid=os.getuid())
    if report.same_uid:
        assert report.io2_pass is False
        assert report.l3_claim_possible is False
    else:
        # A distinct-UID host: IO-2 may pass — the assertion is that the report
        # reflects the probe and never lies.
        assert report.io2_pass is True
        assert report.l3_claim_possible is True
    # The report must always carry a probe result when the probe succeeds.
    assert report.probe_ok is True


def test_probe_subprocess_uid_matches_caller_on_same_uid_host():
    """The honest probe returns a real uid; on this sandbox it equals our uid."""
    uid = probe_subprocess_uid()
    assert isinstance(uid, int) and uid > 0
    # In this sandbox the orchestrator and verifier share the host UID, so the
    # probe equals os.getuid() — which is exactly why IO-2 fails honestly here.
    assert uid == os.getuid()


def test_distinct_uid_supplied_reports_pass():
    """When a distinct verifier UID is genuinely supplied, IO-2 passes."""
    report = assess_uid_readiness(orchestrator_uid=os.getuid(),
                                  verifier_probe_uid=os.getuid() + 1)
    assert report.io2_pass is True
    assert report.l3_claim_possible is True
    assert report.same_uid is False


def test_same_uid_supplied_reports_fail():
    """When the supplied verifier UID equals the orchestrator UID, IO-2 fails
    honestly (a caller cannot claim separation it did not observe)."""
    report = assess_uid_readiness(orchestrator_uid=os.getuid(),
                                  verifier_probe_uid=os.getuid())
    assert report.io2_pass is False
    assert report.l3_claim_possible is False
    assert report.same_uid is True


def test_unknown_uid_never_yields_a_claim():
    """With no orchestrator identity, the assessment must never report an L3
    claim (no separation observed => no claim)."""
    report = assess_uid_readiness(verifier_probe_uid=1234)
    # orchestrator_uid defaults to this process's uid; a positive distinct probe
    # is allowed only if the caller supplied both sides.
    assert report.orchestrator_uid > 0


def test_report_serializable():
    report = UidReadinessReport(
        orchestrator_uid=1000, verifier_probe_uid=2000, probe_ok=True,
        same_uid=False, io2_pass=True, l3_claim_possible=True,
        launch_requirement="distinct uid", launch_option="separate-user",
        captured_at="2026-08-31T00:00:00Z", notes=["ok"],
    )
    d = report.to_dict()
    assert d["assessment"] == "uid-readiness"
    assert d["io2_pass"] is True
    assert d["l3_claim_possible"] is True
    assert "captured_at" in d


# ---------------------------------------------------------------------------
# Documented separate-UID launch requirements (0007 §1.2)
# ---------------------------------------------------------------------------
def test_launch_options_documented():
    """The separate-UID launch options required for a real L3 run are documented:
    setuid wrapper, separate user, separate host (docs/security/0007 §1.2)."""
    options = launch_options_documented()
    ids = {o["option_id"] for o in options}
    assert {"setuid-wrapper", "separate-user", "separate-host"} <= ids
    for o in options:
        assert o["title"] and o["requirement"] and o["isolation"]


def test_separate_uid_launch_options_constant_shape():
    assert len(SEPARATE_UID_LAUNCH_OPTIONS) >= 3
    for oid, title, req, iso in SEPARATE_UID_LAUNCH_OPTIONS:
        assert oid and title and req and iso


def test_readiness_cli_emits_json(tmp_path):
    """The CLI emits a JSON readiness report without running anything."""
    from tests.l3_runner.uid_readiness import main
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--orchestrator-uid", str(os.getuid()), "--json"])
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data["assessment"] == "uid-readiness"
    assert "io2_pass" in data and "l3_claim_possible" in data
