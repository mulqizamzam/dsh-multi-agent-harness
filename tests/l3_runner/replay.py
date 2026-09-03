# tests/l3_runner/replay.py — L3 replay / reproducibility metadata (P4)
#
# Computes replay.json (E11) and provides deterministic fixture hashing so an
# auditor can rerun a scenario and obtain the same verdict byte-for-byte
# (docs/security/0003 §8, docs/security/0005 §8).

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone

from . import DSH_VERSION_PIN


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fixture_hash(fixture_dir: str) -> str:
    """Deterministic sha256 over every file under a fixture directory.

    Walks the directory sorted, hashes each file's relative path + content,
    and returns "sha256:<hex>". Missing directory => "sha256:" + zeros.
    """
    combined = []
    if os.path.isdir(fixture_dir):
        for root, dirs, files in os.walk(fixture_dir):
            dirs.sort()
            for fn in sorted(files):
                rel = os.path.relpath(os.path.join(root, fn), fixture_dir)
                try:
                    combined.append(f"{rel}:{sha256_file(os.path.join(root, fn))}")
                except OSError:
                    combined.append(f"{rel}:ERROR")
    else:
        return "sha256:" + ("0" * 64)
    digest = hashlib.sha256("\n".join(sorted(combined)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def schema_sha256(schema_dir: str) -> dict:
    """Map each schema file name to its sha256 (for replay.json)."""
    out: dict[str, str] = {}
    if os.path.isdir(schema_dir):
        for fn in sorted(os.listdir(schema_dir)):
            if fn.endswith(".json"):
                out[fn] = sha256_file(os.path.join(schema_dir, fn))
    return out


def verifier_binary_sha256(module_file: str) -> str:
    return sha256_file(module_file)


def build_replay(
    *,
    scenario_id: str,
    fixture_path: str,
    fixture_seed: int,
    verifier_binary_path: str,
    dsh_profile_path: str = "~/.dsh/profiles/web/",
    schema_dirs: list[str] | None = None,
    replay_script: str = "",
) -> dict:
    """Build replay.json (E11)."""
    schema_sha = {}
    for sd in (schema_dirs or []):
        schema_sha.update(schema_sha256(sd))

    return {
        "scenario_id": scenario_id,
        "fixture_hash": fixture_hash(fixture_path),
        "fixture_path": fixture_path,
        "command_line": f"python -m tests.l3_runner.runner --scenario {scenario_id} --mode replay",
        "dsh_version": DSH_VERSION_PIN,
        "dsh_profile_path": dsh_profile_path,
        "verifier_binary_sha256": verifier_binary_sha256(verifier_binary_path),
        "schema_sha256": schema_sha,
        "fixture_seed": fixture_seed,
        "replay_script": replay_script,
        "replay_script_sha256": sha256_file(replay_script) if replay_script and os.path.isfile(replay_script) else "",
        "captured_at": _now_iso(),
    }


def env_replay_fields() -> dict:
    """Environment fields relevant to reproducibility."""
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python_version": sys.version.split()[0],
        "dsh_version": DSH_VERSION_PIN,
    }