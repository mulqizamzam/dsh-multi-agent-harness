# tests/live_dsh/live_gate.py — conditional live-DSH gating for pytest
#
# TEST-SUPPORT ONLY. Not production code.
#
# The live-variant tests (Phase-2C INT-01/02/11/12 + ISO-LIVE-006) can only
# make a LIVE claim when two things hold in the running process:
#
#   1. the D4/D7 composition is mounted and the mount marker is set
#      (DSH_LIVE_BRIDGE_ACTIVE=1, post-mount convention);
#   2. a session-recorded REAL child result is available to feed the bridge —
#      pytest itself cannot dispatch a DSH child (the dispatch plane is the
#      orchestrator session; tests/live_evidence/harness.py:116-118).
#
# Without both, the tests SKIP with that explicit reason. That is a
# conditional, honest gate — not the old unconditional `raise
# NotImplementedError` skeletons. The deterministic equivalents keep running
# in every mode.

import glob
import json
import os

LIVE_MARKER_ENV = "DSH_LIVE_BRIDGE_ACTIVE"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

_RECORDED_DIRS = (
    # 2026-09-07 mount-verification artifacts (orchestrator session produced)
    os.path.join(_PROJECT_ROOT, "runs", "mount-verification-2026-09-07"),
    os.path.join(_PROJECT_ROOT, "tests", "live_evidence", "run",
                 "2026-09-07-mount-verification"),
)


def live_marker_on() -> bool:
    """True only when the D4/D7 mount marker is set in this process."""
    return os.environ.get(LIVE_MARKER_ENV, "").lower() in ("1", "true", "yes")


def skip_reason(what: str) -> str:
    return (
        f"live DSH bridge not active in this process ({what}): "
        f"{LIVE_MARKER_ENV} unset or no session-recorded real child result; "
        "deterministic equivalents cover the contract offline. Live recipe: "
        "tests/live_dsh/README.md")


def live_available(what: str) -> bool:
    return live_marker_on()


def find_recorded_result(*basenames: str) -> dict | None:
    """Return the first session-recorded live result file whose name matches,
    across the known timestamped evidence directories (env override first)."""
    dirs = [os.environ.get("DSH_LIVE_RESULTS_DIR", "")] + list(_RECORDED_DIRS)
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for name in basenames:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                with open(path) as f:
                    return json.load(f)
            for hit in glob.glob(os.path.join(d, f"{name}*")):
                with open(hit) as f:
                    return json.load(f)
    return None


def load_recorded(path_env_key: str, *basenames: str) -> dict | None:
    explicit = os.environ.get(path_env_key, "")
    if explicit and os.path.isfile(explicit):
        with open(explicit) as f:
            return json.load(f)
    return find_recorded_result(*basenames)
