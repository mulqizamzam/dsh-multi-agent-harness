#!/usr/bin/env python3
"""G13 63/63 LIVE campaign — runner launcher + manifest builder.

Starts the L3 runner CLI (`--mode live --no-rehearsal`) for every G13-LIVE
scenario under runs/g13_campaign/fixtures, each with its own rendezvous dir.
Each runner writes invocation.json and blocks until response.json appears.

The orchestrator agent performs the REAL subagent_<id> dispatch per scenario
and writes response.json (the rendezvous bridge), then each runner completes
and produces its evidence bundle.

Output: runs/g13_campaign/manifest.json — one entry per scenario with its
scenario_id, affected role, rendezvous dir, and invocation content.
"""
import json
import os
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_ROOT))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

FIXTURES_ROOT = os.path.join(_ROOT, "fixtures")
BUNDLE_BASE = os.path.join(_ROOT, "bundle_base")
RENDEZVOUS_BASE = os.path.join(_ROOT, "rendezvous")
MANIFEST = os.path.join(_ROOT, "manifest.json")

PYTHON = os.environ.get("L3_PYTHON") or os.path.join(
    _PROJECT_ROOT, ".venv-tests", "bin", "python3")

TIMEOUT = int(os.environ.get("L3_RENDEZVOUS_TIMEOUT", "3600"))


def scenario_ids() -> list[str]:
    ids = []
    for name in sorted(os.listdir(FIXTURES_ROOT)):
        d = os.path.join(FIXTURES_ROOT, name)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "plan.json")):
            ids.append(name)
    return ids


def main() -> None:
    ids = scenario_ids()
    print(f"Campaign: {len(ids)} scenarios")
    os.makedirs(RENDEZVOUS_BASE, exist_ok=True)
    manifest = {}

    # Start one runner per scenario in the background.
    for sid in ids:
        rdz = os.path.join(RENDEZVOUS_BASE, sid)
        os.makedirs(rdz, exist_ok=True)
        for f in ("invocation.json", "response.json"):
            try:
                os.unlink(os.path.join(rdz, f))
            except FileNotFoundError:
                pass
        env = dict(os.environ)
        env["DSH_LIVE_BRIDGE_ACTIVE"] = "1"
        cmd = [
            PYTHON, "-m", "tests.l3_runner.runner",
            "--scenario", sid,
            "--mode", "live",
            "--no-rehearsal",
            "--fixtures-root", FIXTURES_ROOT,
            "--bundle-base", BUNDLE_BASE,
            "--live-rendezvous-dir", rdz,
            "--live-rendezvous-timeout", str(TIMEOUT),
            "--orchestrator-session", os.environ.get("DSH_SESSION_ID", ""),
        ]
        # Redirect stdout/stderr to a per-scenario log.
        log = os.path.join(_ROOT, f"logs", sid)
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log + ".out.log", "w") as out, open(log + ".err.log", "w") as err:
            proc = subprocess.Popen(cmd, cwd=_PROJECT_ROOT, env=env,
                                    stdout=out, stderr=err)
        manifest[sid] = {
            "scenario_id": sid,
            "rendezvous_dir": rdz,
            "log_out": log + ".out.log",
            "log_err": log + ".err.log",
            "pid": proc.pid,
        }
        print(f"  started {sid} (pid={proc.pid})")

    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"Manifest: {MANIFEST}")
    print("Waiting for invocation.json from each runner...")

    # Wait for all invocations (up to 120s).
    deadline = time.time() + 120
    while time.time() < deadline:
        ready = 0
        for sid, entry in manifest.items():
            inv = os.path.join(entry["rendezvous_dir"], "invocation.json")
            if os.path.isfile(inv):
                ready += 1
        if ready == len(manifest):
            break
        time.sleep(1)
    print(f"invocations ready: {ready}/{len(manifest)}")

    # Enrich manifest with invocation contents.
    for sid, entry in manifest.items():
        inv = os.path.join(entry["rendezvous_dir"], "invocation.json")
        if os.path.isfile(inv):
            with open(inv) as f:
                entry["invocation"] = json.load(f)
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main()
