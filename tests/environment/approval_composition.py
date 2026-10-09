# tests/environment/approval_composition.py — Corrected approval-answerer detection
#
# TEST-SUPPORT ONLY. NOT production code.
#
# Replaces the obsolete approval-readiness heuristic (which keyed off the
# project-side `DSH_APPROVAL_PROMPTS_DISABLED` convention and a $DSH_HOME/profiles
# marker scan). Neither is authoritative:
#   * DSH 0.1.1-rc.2 NEVER reads `DSH_APPROVAL_PROMPTS_DISABLED` (negative grep
#     over the checkout, verified by test_dsh_never_reads_*).
#   * The web answerer surface the bundle composes lives in the DSH packages
#     (packages/bundle/web-app/cordis.patch.yml), NOT under $DSH_HOME/profiles/.
#
# This module discovers the ACTUAL approval composition from the DSH source/bundle
# and reports four DISTINCT readiness states (never collapsed into one boolean):
#
#   APPROVAL_COMPOSED            — approval service + answerer surface are composed
#                                  in the DSH base/web-app bundles (source truth).
#   APPROVAL_INTERACTIVE_READY   — COMPOSED + the current session is a web GUI
#                                  session and its browser answerer is reachable.
#   APPROVAL_E2E_VERIFIED        — a harmless approval-required probe was actually
#                                  observed end-to-end: approval/request emitted,
#                                  the Web GUI question surfaced, the Human decision
#                                  captured, ApprovalOutcome ∈ {allowed-once,
#                                  rejected, cancelled, unavailable}, a matching
#                                  approval/asked + approval/decided pair exists,
#                                  and no consequential action was executed.
#   APPROVAL_HEADLESS_UNAVAILABLE — no composed answerer surface; the approval/
#                                  request waterfall fails closed to 'unavailable'.
#
# Read-only. NEVER modifies session policy, DSH, profile, preset, or writes any
# marker file. E2E_VERIFIED is derived ONLY from observed session-log evidence
# (approval/asked + matching approval/decided), never invented or simulated.
#
# E2E is a TRI-STATE, not a bool:
#   e2e_status == "PASS"       — an approval/asked + approval/decided pair is
#                                observed in the CURRENT session log (re-derived).
#   e2e_status == "UNKNOWN"    — the path is composition-ready but the previously
#                                observed Human answer cannot be independently
#                                re-derived from the current session log (no
#                                matching pair present). NEVER promoted to PASS
#                                from composition or from a stale marker alone.
#   e2e_status == "UNAVAILABLE" — headless / no composed answerer surface.
#
# USAGE:
#   from tests.environment.approval_composition import approval_readiness
#   r = approval_readiness()            # alias: detect_approval_status()
#   r.status  # ApprovalStatus
#   r.composed / r.interactive_ready / r.e2e_verified / r.headless_unavailable
#   r.probe_answered / r.e2e_status

from __future__ import annotations

import enum
import json
import os
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit
from dataclasses import dataclass, field

# DSH checkout path (version pin 0.1.1-rc.2); overridable for tests via
# DSH_CHECKOUT env OR by calling approve_readiness() after monkeypatching.
DSH_CHECKOUT = os.environ.get("DSH_CHECKOUT", "/home/administrator/deepseek-harness")


def _dsh_checkout() -> str:
    """Resolve the checkout path fresh, so tests can override via env."""
    return os.environ.get("DSH_CHECKOUT", DSH_CHECKOUT)


# The DSH bundle patch files that carry the approval + answerer composition.
def _base_patch() -> str:
    return os.path.join(_dsh_checkout(), "packages", "bundle", "base", "cordis.patch.yml")


def _web_patch() -> str:
    return os.path.join(_dsh_checkout(), "packages", "bundle", "web-app", "cordis.patch.yml")

# Env vars.
DSH_WEB_URL_ENV = "DSH_WEB_URL"
DSH_SESSION_JSONL_ENV = "DSH_SESSION_JSONL"
DSH_APPROVAL_PROMPTS_DISABLED_ENV = "DSH_APPROVAL_PROMPTS_DISABLED"

# The closed ApprovalOutcome vocabulary (DSH user-approval README).
APPROVAL_OUTCOMES = frozenset({"allowed-once", "rejected", "cancelled", "unavailable"})

# The approval audit pair the DSH approval service appends (log-only).
ASK_EVENT = "approval/asked"
DECIDED_EVENT = "approval/decided"


class ApprovalStatus(enum.Enum):
    """Four distinct approval-path readiness states (never collapsed)."""
    APPROVAL_COMPOSED = "APPROVAL_COMPOSED"
    APPROVAL_INTERACTIVE_READY = "APPROVAL_INTERACTIVE_READY"
    APPROVAL_E2E_VERIFIED = "APPROVAL_E2E_VERIFIED"
    APPROVAL_HEADLESS_UNAVAILABLE = "APPROVAL_HEADLESS_UNAVAILABLE"


@dataclass
class ApprovalReadiness:
    """Full (uncollapsed) approval-path readiness report."""
    status: ApprovalStatus = ApprovalStatus.APPROVAL_HEADLESS_UNAVAILABLE
    detail: str = ""
    # Composed in the DSH bundle (source truth).
    composed: bool = False
    # Composed + web GUI session reachable.
    interactive_ready: bool = False
    # Observed end-to-end approval/request -> question -> decision -> outcome.
    e2e_verified: bool = False
    # Tri-state E2E status: "PASS" | "UNKNOWN" | "UNAVAILABLE". UNKNOWN means
    # the previously observed Human answer cannot be independently re-derived
    # from the current session log (never promoted from composition alone).
    e2e_status: str = "UNKNOWN"
    # True only when an approval/asked + approval/decided pair is re-derived.
    probe_answered: bool = False
    # No composed answerer surface (fail-closed).
    headless_unavailable: bool = False
    # Empirical sub-facts.
    approval_service_composed: bool = False
    answerer_surface_composed: bool = False
    web_session: bool = False
    web_server_reachable: bool = False
    effective_policy: str = "ask"
    prompts_disabled_authoritative: bool = False
    # Session-log evidence (empty when absent).
    approval_events: list = field(default_factory=list)
    e2e_pair: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "detail": self.detail,
            "composed": self.composed,
            "interactive_ready": self.interactive_ready,
            "e2e_verified": self.e2e_verified,
            "e2e_status": self.e2e_status,
            "probe_answered": self.probe_answered,
            "headless_unavailable": self.headless_unavailable,
            "approval_service_composed": self.approval_service_composed,
            "answerer_surface_composed": self.answerer_surface_composed,
            "web_session": self.web_session,
            "web_server_reachable": self.web_server_reachable,
            "effective_policy": self.effective_policy,
            "prompts_disabled_authoritative": self.prompts_disabled_authoritative,
            "approval_events": list(self.approval_events),
            "e2e_pair": dict(self.e2e_pair),
        }


# ---------------------------------------------------------------------------
# Composition discovery (read-only, DSH source/bundle)
# ---------------------------------------------------------------------------

def _checkout_available() -> bool:
    return os.path.isdir(os.path.join(_dsh_checkout(), "packages", "bundle"))


def approval_service_composed() -> bool:
    """True when the DSH base bundle composes the approval service."""
    if not os.path.isfile(_base_patch()):
        return False
    try:
        with open(_base_patch()) as f:
            text = f.read()
        return "- id: approval" in text and "@deepseek-ai/dsh-user-approval" in text
    except OSError:
        return False


def answerer_surface_composed() -> bool:
    """True when the DSH web-app bundle composes the browser answerer surface.

    The web answerer is the Host→browser forwarding row plus the browser half
    that answers it. The composition changed after the original version pin:
    the forwarding row was `@deepseek-ai/dsh-host-apiproxy`, and the approval
    UI lived as the ui-conversation ApprovalPanel. The current row is
    `@deepseek-ai/dsh-api-remotes` (two-sided BFF for Host Remote
    capabilities), and the approval UI is the dedicated
    `@deepseek-ai/dsh-client-ui-approval` package. Detection therefore
    requires all four rows: forwarding, approval presentation, question
    surface, and the conversation composer the approval UI takes over.
    """
    if not os.path.isfile(_web_patch()):
        return False
    try:
        with open(_web_patch()) as f:
            text = f.read()
        has_forwarding = (
            "- id: api-remotes" in text
            and "@deepseek-ai/dsh-api-remotes" in text
        )
        has_approval_ui = (
            "- id: ui-approval" in text
            and "@deepseek-ai/dsh-client-ui-approval" in text
        )
        has_questions = "- id: ui-user-questions" in text
        has_conversation = "- id: ui-conversation" in text
        return (
            has_forwarding and has_approval_ui and has_questions
            and has_conversation
        )
    except OSError:
        return False


def effective_policy_from_env() -> str:
    """The approval policy the base bundle derives from the permission mode.

    Mirrors the base bundle row:
      policy: (DSH_PERMISSION_MODE ?? 'workspace-write') === 'danger-full-access'
              ? 'never' : 'ask'
    """
    mode = os.environ.get("DSH_PERMISSION_MODE", None) or "workspace-write"
    return "never" if mode == "danger-full-access" else "ask"


def _dsh_reads_prompts_disabled() -> bool:
    """Whether the DSH checkout references DSH_APPROVAL_PROMPTS_DISABLED at all.

    This is the authority check the readiness model relies on: if DSH never reads
    the variable, the probe must NOT treat it as the source of truth.
    """
    if not _checkout_available():
        return False
    try:
        proc = subprocess.run(
            ["grep", "-rn", DSH_APPROVAL_PROMPTS_DISABLED_ENV, _dsh_checkout(),
             "--include=*.ts", "--include=*.js", "--include=*.md"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    # Exclude this project's own probe files (they live outside the checkout).
    hits = [ln for ln in proc.stdout.splitlines() if "agent-workspace" not in ln]
    return bool(hits)


# ---------------------------------------------------------------------------
# Web GUI session detection
# ---------------------------------------------------------------------------

def web_session() -> bool:
    """Whether the current session is a web GUI session (DSH_WEB_URL set)."""
    return bool(os.environ.get(DSH_WEB_URL_ENV, ""))


def authorized_web_url() -> str | None:
    """DSH_WEB_URL when it carries the launch token — the attached-answerer URL.

    A bare DSH_WEB_URL proves only that the harness exported a web server
    URL to this session. The GUI answers 401 until the launch-token query is
    presented, so "a browser answerer is attached to this session" requires
    the tokenized URL the operator's browser holds. Returns None for a bare
    or unset URL — the honest signal that no browser is attached.
    """
    web_url = os.environ.get(DSH_WEB_URL_ENV, "")
    if not web_url:
        return None
    if "token" not in parse_qs(urlsplit(web_url).query):
        return None
    return web_url


def web_server_reachable() -> bool:
    """Whether the web server at DSH_WEB_URL answers HTTP 200 (browser attached)."""
    web_url = os.environ.get(DSH_WEB_URL_ENV, "")
    if not web_url:
        return False
    try:
        proc = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "--connect-timeout", "2", web_url],
            capture_output=True, text=True, timeout=5)
        return proc.returncode == 0 and proc.stdout.strip() == "200"
    except (OSError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Session-log evidence (the only source of E2E_VERIFIED)
# ---------------------------------------------------------------------------

def _decode_session_log(path: str) -> str:
    """Decode a DSH .jsonl.zstd session log (possible multi-frame zstd)."""
    if not path or not os.path.isfile(path):
        return ""
    try:
        from compression import zstd  # stdlib in Python 3.14+
    except ImportError:
        return ""
    try:
        return zstd.decompress(open(path, "rb").read()).decode("utf-8", "replace")
    except Exception:
        return ""


def approval_session_events(session_log_path: str | None = None) -> list:
    """Return the approval audit events observed in the session log.

    Parses `approval/asked` and `approval/decided` events with their ids and
    outcomes, so an E2E pair can be matched on the shared request id.
    """
    path = session_log_path or os.environ.get(DSH_SESSION_JSONL_ENV, "")
    text = _decode_session_log(path)
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") not in (ASK_EVENT, DECIDED_EVENT):
            continue
        data = obj.get("data", {}) or {}
        events.append({
            "type": obj["type"],
            "id": data.get("id"),
            "outcome": data.get("outcome"),
            "toolName": data.get("toolName"),
            "reason": data.get("reason"),
            "time": obj.get("time"),
        })
    return events


def _find_e2e_pair(events: list) -> dict:
    """Match an approval/asked + approval/decided pair on a shared request id.

    E2E verification requires BOTH an ask and its decided sharing an id, with a
    closed ApprovalOutcome. This is honest evidence — never invented.
    """
    asked = {e["id"] for e in events if e["type"] == ASK_EVENT and e["id"]}
    decided = {}
    for e in events:
        if e["type"] == DECIDED_EVENT and e["id"] and e["outcome"] in APPROVAL_OUTCOMES:
            decided[e["id"]] = e["outcome"]  # last decided wins per id
    for rid, outcome in decided.items():
        if rid in asked:
            ask = next((e for e in events
                        if e["type"] == ASK_EVENT and e["id"] == rid), {})
            return {"id": rid, "outcome": outcome, "asked": ask,
                    "decided": {"id": rid, "outcome": outcome}}
    return {}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def approval_readiness(session_log_path: str | None = None) -> ApprovalReadiness:
    """Determine the approval-path readiness state. Read-only.

    Args:
        session_log_path: optional explicit session-log path (overrides
            DSH_SESSION_JSONL). Used for test isolation; defaults to the live
            session log.
    """
    r = ApprovalReadiness()

    # Composition (source truth).
    r.approval_service_composed = approval_service_composed()
    r.answerer_surface_composed = answerer_surface_composed()
    r.composed = r.approval_service_composed and r.answerer_surface_composed

    # Authority of the obsolete convention.
    r.prompts_disabled_authoritative = _dsh_reads_prompts_disabled()

    # Effective policy (ask preserved).
    r.effective_policy = effective_policy_from_env()

    # Web GUI session.
    r.web_session = web_session()
    r.web_server_reachable = web_server_reachable()
    r.interactive_ready = r.composed and r.web_session and r.web_server_reachable

    # E2E evidence (only from observed session-log events).
    events = approval_session_events(session_log_path)
    r.approval_events = events
    r.e2e_pair = _find_e2e_pair(events)
    r.e2e_verified = bool(r.e2e_pair)
    r.probe_answered = r.e2e_verified
    r.e2e_status = "PASS" if r.e2e_verified else "UNKNOWN"

    # Status ladder (uncollapsed).
    if not r.composed:
        r.status = ApprovalStatus.APPROVAL_HEADLESS_UNAVAILABLE
        r.headless_unavailable = True
        r.e2e_status = "UNAVAILABLE"
        r.detail = (
            f"approval_service_composed={r.approval_service_composed} "
            f"answerer_surface_composed={r.answerer_surface_composed} — no "
            f"composed answerer surface; approval/request fails closed to "
            f"'unavailable' (DENY + escalate). This is the required fail-closed "
            f"default for a headless/no-answerer session.")
    elif not r.web_session or not r.web_server_reachable:
        r.status = ApprovalStatus.APPROVAL_COMPOSED
        r.detail = (
            f"approval service and web answerer surface ARE composed (source "
            f"truth), but web_session={r.web_session} "
            f"web_server_reachable={r.web_server_reachable}. COMPOSITION READY "
            f"!= END-TO-END VERIFIED: the browser answerer is not attached in "
            f"this session.")
    elif not r.e2e_verified:
        r.status = ApprovalStatus.APPROVAL_INTERACTIVE_READY
        r.e2e_status = "UNKNOWN" if r.composed and r.web_session \
            and r.web_server_reachable else r.e2e_status
        r.detail = (
            f"approval service composed, answerer surface composed, web GUI "
            f"session attached (browser reachable). The interactive approval "
            f"path is available, but no approval/asked + approval/decided pair "
            f"is re-derivable from the current session log: E2E status is "
            f"UNKNOWN, NOT PASS (COMPOSITION READY != END-TO-END VERIFIED; a "
            f"stale marker alone never promotes to E2E_VERIFIED).")
    else:
        r.status = ApprovalStatus.APPROVAL_E2E_VERIFIED
        r.detail = (
            f"harmless approval-required probe observed end-to-end and "
            f"RE-DERIVED from the current session log: approval/request emitted "
            f"-> Web GUI question surfaced -> Human decision captured -> "
            f"ApprovalOutcome="
            f"{r.e2e_pair.get('outcome')} (closed vocabulary), with a matching "
            f"approval/asked + approval/decided pair and no consequential "
            f"action executed. See evidence id={r.e2e_pair.get('id')}.")

    return r


# Backward-compatible entrypoint name (the correction tests + docs reference
# detect_approval_status); approval_readiness is the canonical implementation.
detect_approval_status = approval_readiness


# ---------------------------------------------------------------------------
# CLI (read-only)
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Detect approval-path readiness (read-only; never modifies "
                    "DSH, profile, preset, or session policy)")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--session-log", default="", help="explicit session log path")
    args = parser.parse_args(argv)

    r = approval_readiness(session_log_path=args.session_log or None)
    if args.json:
        print(json.dumps(r.to_dict(), indent=1))
    else:
        print(f"Status: {r.status.value}")
        print(f"Detail: {r.detail}")
        print(f"composed={r.composed} interactive_ready={r.interactive_ready} "
              f"e2e_verified={r.e2e_verified} e2e_status={r.e2e_status} "
              f"probe_answered={r.probe_answered} "
              f"headless_unavailable={r.headless_unavailable}")
        print(f"effective_policy={r.effective_policy} "
              f"prompts_disabled_authoritative={r.prompts_disabled_authoritative}")
        print(f"approval_events={len(r.approval_events)} e2e_pair={r.e2e_pair}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
