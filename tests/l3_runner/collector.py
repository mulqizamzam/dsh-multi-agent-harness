# tests/l3_runner/collector.py — L3 evidence bundle collector
#
# Collects all 13 required evidence items (E1..E13) for an L3 scenario and
# writes them to audit/l3/<scenario-id>/.
#
# The collector runs BEFORE the verifier computes its verdict (captures
# before.sha256, env.json, plan.json) and AFTER the runtime action completes
# (captures after.sha256, audit-log.jsonl, runtime-verdict.json). The verifier
# then produces reference-verdict.json, oracle-classes.json, verdict-match.json,
# verifier-independence.json, replay.json, and the manifest.json is written last.

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import DSH_VERSION_PIN, EVIDENCE_FILES


def hash_file(path: str) -> str:
    """SHA-256 of a file's contents (hex)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_text(data: str) -> str:
    return hash_bytes(data.encode("utf-8"))


def state_hash_tree(base: str, scopes: tuple[str, ...]) -> dict:
    """Compute a sha256 hash tree over the given scope globs.

    Returns {"algorithm": "sha256", "scope": [...], "root_hash": "hex",
             "files": {"rel/path": "hex", ...}}
    """
    files: dict[str, str] = {}
    base_abs = os.path.abspath(base)
    for scope in scopes:
        # Convert a glob-pattern like "state/registry/**" to a directory to scan
        dir_part = scope.replace("**", "").rstrip("/")
        target = os.path.join(base_abs, dir_part)
        if not os.path.isdir(target):
            continue
        for root, dirnames, filenames in os.walk(target):
            rel_dir = os.path.relpath(root, base_abs)
            for fn in sorted(filenames):
                abs_path = os.path.join(root, fn)
                rel_path = os.path.join(rel_dir, fn)
                try:
                    files[rel_path] = hash_file(abs_path)
                except (OSError, PermissionError):
                    files[rel_path] = "ERROR"

    # Root hash: sha256 of the concatenation of all sorted (rel, hash) pairs.
    combined = "".join(f"{k}:{v}" for k, v in sorted(files.items()))
    root_hash = hash_text(combined) if combined else hash_text("EMPTY")

    return {
        "algorithm": "sha256",
        "scope": list(scopes),
        "root_hash": root_hash,
        "files": files,
    }


def capture_env(seed: int = 42) -> dict:
    """Capture the environment snapshot (E2)."""
    return {
        "dsh_version": DSH_VERSION_PIN,
        "os": f"{platform.system()} {platform.release()}",
        "python_version": sys.version.split()[0],
        "sandbox_mode": "workspace-write",
        "approval_policy": "ask",
        "permission_preset": "default",
        "utc_offset_seconds": 0,
        "seed": seed,
        "harness_version": DSH_VERSION_PIN,
    }


def capture_provenance(scenario_id: str, actor_session_id: str,
                       verifier_session_id: str, delegation_chain: list,
                       children: list, collection_order: list) -> dict:
    """Capture the provenance chain (E10)."""
    return {
        "scenario_id": scenario_id,
        "actor_session_id": actor_session_id,
        "verifier_session_id": verifier_session_id,
        "delegation_chain": delegation_chain,
        "children": children,
        "collection_order": collection_order,
    }


def write_json(path: str, data) -> None:
    """Write a JSON file with sorted keys, compact separators."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True, indent=1)
        f.write("\n")


def write_sha256(path: str, data: dict) -> None:
    """Write the state hash tree as JSON (even though the extension is .sha256)."""
    write_json(path, data)


def write_audit_slice(path: str, events: list[dict]) -> None:
    """Write an audit-log.jsonl slice (JSONL, one event per line)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def write_manifest(bundle_dir: str, scenario_id: str, created_at: str = "") -> str:
    """Write manifest.json (E1) by hashing all evidence files in the bundle.

    Returns the manifest.json path.
    """
    manifest_path = os.path.join(bundle_dir, "manifest.json")
    files: dict[str, dict] = {}
    for fname in EVIDENCE_FILES:
        fpath = os.path.join(bundle_dir, fname)
        if os.path.exists(fpath):
            files[fname] = {"sha256": hash_file(fpath)}
        else:
            files[fname] = {"sha256": "MISSING"}

    manifest = {
        "scenario_id": scenario_id,
        "dsh_version": DSH_VERSION_PIN,
        "created_at": created_at or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "files": files,
    }
    write_json(manifest_path, manifest)
    return manifest_path


def write_bundle_item(bundle_dir: str, filename: str, data) -> str:
    """Write a single evidence item to the bundle directory. Returns the path."""
    path = os.path.join(bundle_dir, filename)
    if filename.endswith(".jsonl"):
        write_audit_slice(path, data)
    elif filename.endswith(".sha256"):
        write_sha256(path, data)
    else:
        write_json(path, data)
    return path


def ensure_bundle_dir(scenario_id: str, base: str = "") -> str:
    """Create and return the bundle directory path."""
    if base:
        bundle_dir = os.path.join(base, "audit", "l3", scenario_id)
    else:
        # Default: project root (three levels up from this file)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        bundle_dir = os.path.join(project_root, "audit", "l3", scenario_id)
    os.makedirs(bundle_dir, exist_ok=True)
    return bundle_dir