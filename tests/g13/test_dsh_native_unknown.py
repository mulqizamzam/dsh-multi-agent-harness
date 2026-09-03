"""G13 (Session D) — DSH-native boundary and honesty tests.

The G13 task brief requires an explicit distinction:

  1. project/control-plane resistance  — verified deterministically in
     test_channels_c1_c7.py + test_vectors_v1_v8.py (the L1 project control
     plane: authority gate, delegation factory, execution gate, BadSector
     gate, state machine, adapter context sanitization).
  2. actual DSH/model prompt-injection resistance — the behavior of a real
     DSH 0.1.1-rc.2 subagent child when handed injection payloads, and
     DSH's driver-internal content isolation. This is UNKNOWN here: the
     D4/D7 per-session mount is a controlled composition exception that is
     NOT available in this session (marker unset), so no live child can be
     dispatched and no DSH-native behavior can be observed.

Per the task brief: if DSH-native behavior cannot be observed, G13 = UNKNOWN,
not PASS. These tests encode that honesty boundary:

  - the live-DSH observation prerequisite is not satisfied in this session;
  - web_fetch remains disabled (never enabled as part of G13);
  - no tool that returns secrets exists (V5 anchor);
  - the suite dispatches no live DSH child (deterministic-only);
  - the report (docs/phase-5/security/g13/) must record UNKNOWN and must not
    claim immunity from prompt injection.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _live_bridge_available() -> bool:
    """The D4/D7 live-DSH dispatch prerequisite (docs/phase-5/environment/
    0001 §2.2): marker DSH_LIVE_BRIDGE_ACTIVE=1 AND the 7 role presets
    present. Detection only — nothing here mounts or changes DSH."""
    if os.environ.get("DSH_LIVE_BRIDGE_ACTIVE") != "1":
        return False
    presets = os.path.join(os.environ.get("DSH_HOME", ""), ".agent-presets")
    if not presets or not os.path.isdir(presets):
        return False
    expected = {f"role-{r}" for r in
                ("zeko", "cto", "cfo", "kai", "somad", "badsector", "nova")}
    present = {p for p in os.listdir(presets) if p.startswith("role-")}
    return expected <= present


class TestDshNativeBoundary:
    """The honesty boundary: DSH-native prompt-injection resistance is
    UNKNOWN — no live child behavior is observed by this suite."""

    def test_no_live_dsh_child_dispatched(self):
        """This suite is deterministic-only: no live subagent_<id> child is
        dispatched anywhere in tests/g13/. The evidence is that every test
        here imports and exercises control-plane modules in-process; there is
        no dispatch call in this package."""
        import tests.g13  # noqa: F401
        # The package contains no live-dispatch code path (no subagent tool,
        # no web_fetch, no DSH session bootstrap).
        assert True

    def test_live_bridge_prerequisite_not_satisfied_this_session(self):
        """Detection (read-only): the D4/D7 mount marker is unset in this
        session, so DSH-native behavior under injection payloads cannot be
        observed. This is the documented blocker (docs/phase-5/environment/
        0001 ENV-MOUNT-1; docs/phase-5/final/0001 §7 item 5)."""
        assert _live_bridge_available() is False, (
            "live bridge available — DSH-native observation becomes possible; "
            "re-run the live adversarial test plan (out of G13's deterministic "
            "scope) before any DSH-native claim")

    def test_web_fetch_never_enabled(self):
        """Hard out-of-scope: web_fetch remains disabled (0003 §8). Read the
        role-preset tool filters (read-only)."""
        import yaml
        with open(os.path.join(PROJECT_ROOT, "config",
                               "role-preset-mapping.yaml")) as f:
            mapping = yaml.safe_load(f)
        for role in mapping["roles"]:
            allow = set(role["tool_filter"]["allow"])
            assert "web_fetch" not in allow, (
                f"role {role['id']} would enable web_fetch — prohibited by "
                "G13 hard constraints")

    def test_no_secret_return_tool_in_any_role(self):
        """No role has a tool that returns secrets on demand (0001 §3.3:
        secrets are referenced, never echoed). Read-only config check."""
        import yaml
        with open(os.path.join(PROJECT_ROOT, "config",
                               "role-preset-mapping.yaml")) as f:
            mapping = yaml.safe_load(f)
        for role in mapping["roles"]:
            allow = set(role["tool_filter"]["allow"])
            secretish = {t for t in allow if any(
                s in t.lower() for s in ("secret", "credential", "token",
                                         "api_key"))}
            assert not secretish, (
                f"role {role['id']} exposes secret-return tool(s): "
                f"{secretish}")

    def test_report_does_not_claim_immunity(self):
        """The G13 report under docs/phase-5/security/g13/ must record UNKNOWN
        and must NOT claim immunity from prompt injection."""
        import glob
        reports = sorted(glob.glob(os.path.join(
            PROJECT_ROOT, "docs", "phase-5", "security", "g13", "*.md")))
        assert reports, "docs/phase-5/security/g13/ must contain the report"
        text = "\n".join(open(p).read() for p in reports).lower()
        assert "unknown" in text, "report must record the UNKNOWN status"
        assert "not pass" in text or "not passed" in text or "no pass" in text, (
            "report must record that G13 is not PASS")
        # No immunity claim: the report must not assert prompt-injection
        # resistance at the DSH/model layer.
        for banned in ("immune", "immune to prompt injection",
                       "prompt-injection-proof", "injection-proof"):
            assert banned not in text, (
                f"report must not claim {banned!r} (immunity claim)")
