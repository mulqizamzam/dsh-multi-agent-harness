"""Deployment-sync regression: the 16 deployed presets ARE their repo sources, byte for byte.

Agent presets are DEPLOYED BY HAND. There is no deploy script in this repo: nothing
copies `orchestrator/*.yml` and `agents/<id>/*.yml` into the live user preset root at
`$DSH_HOME/.agent-presets/`, so repo<->deployed drift carries no automatic signal at
all. That is the same class of gap ADR 0004 records for the `standard`-preset
derivation — where `tests/unit/test_orchestrator_preset_derivation.py` is the
mechanism. This file is the mechanism for this one.

What had already drifted, found while measuring this gate (2026-09-12): 6 of the 16
deployed `agent.cordis.yml` files were STALE — their header comment still said
`DRAFT — NOT MOUNTED` while the repo source and reality both said `Mounted 2026-09-07`.
The composition rows were identical; only the comment block had fallen behind. (That
count is the measurement taken before this file existed; the pre-fix copies were
re-synced and are gone, so the six are recorded rather than re-verifiable here. What IS
reproducible: a comment-only change leaves `yaml.safe_load` output equal while the bytes
differ, and it is the case a data comparison loses.) A comparison that parsed the YAML
and diffed data would have called all six in sync, which is why assertion 1 compares
SHA-256 over the raw BYTES: the header comment is part of the artifact an operator reads
out of the live preset root, and "the machine-relevant rows still match" is not the
invariant. Those six have been re-synced; 32/32 file pairs match today, and that is what
this test pins.

Everything is derived from the repo side, never from the deployment:
`config/agents.yaml` is the canonical registry, so the expected set is its 15
specialists plus the orchestrator = 16 presets x 2 files (`agent.cordis.yml`,
`preset.yml`) = 32 file pairs.

Three assertions (the last split into two functions so a directory split and a file
split fail independently):

  1. content sync      — each repo file is byte-identical to its deployed counterpart
  2. set completeness  — deployed preset dirs == repo-sourced preset ids, exactly
  3. mode uniformity   — all 16 deployed dirs share ONE mode; all 32 files share ONE

Assertion 3 asserts UNIFORMITY, never a specific value. The defect it guards is a
SPLIT — as measured on this host, two deployment batches left 8 preset directories at
one mode and 8 at another, since corrected. A split is invisible to any single-file
check and visible only as a spread. Hard-coding `600`/`700`
would freeze this machine's umask into the gate and make it fire on any host that
deployed with a different one, i.e. a false alarm whose likely outcome is the gate
being loosened or skipped instead of a real split being fixed. The Human's chosen
posture — preset directories 700, preset files 600, owner-only, set on 2026-09-12 — is
recorded here as intent; the assertion stays deliberately weaker than that record so it
can only ever report the actual defect.

Environment: the module-scoped `deployment` fixture SKIPs (so all four tests skip
together, same idiom as `test_orchestrator_preset_derivation.py`) when `DSH_HOME` is
unset or the deployed preset root is absent. A machine with no live DSH home has no
deployment to compare against; "not deployed here" is not drift, and must not be
reported as a failure.
"""

import hashlib
import os
import re
import stat

import pytest
import yaml

# Resolved at fixture time, never cached at import: the falsification runs point this
# env var at a shadow root, and the skip proof unsets it.
PRESET_ROOT_ENV = "DSH_HOME"
DEPLOYED_DIR_NAME = ".agent-presets"

ORCHESTRATOR_ID = "orchestrator"
# Deployed directory name for a specialist preset id: agents/<id>/ -> role-<id>/.
DEPLOYED_PREFIX = "role-"
# The two files deployed per preset. Both are repo-sourced; `preset.yml` became a repo
# source only on 2026-09-12, and the 15 deployed copies had no counterpart at all
# before that (see the set-completeness failure message).
PRESET_FILES = ("agent.cordis.yml", "preset.yml")

# A deployed directory counts as a preset exactly when DSH would mount it: the live
# scanner keeps `child.isDirectory() && PRESET_ID.test(child.name)` and skips the rest
# rather than reporting ".DS_Store-grade residue" (read-only checkout,
# packages/preset/agent-presets/src/discovery.ts:150 + preset.ts:18). Reusing that rule
# here keeps "orphan" meaning *a preset the live roster can actually select*, and stops
# an inert `role-cto.old` backup from firing a drift alarm. Consequence, stated plainly:
# residue that fails this regex is outside this gate — it is inert, not unsynchronised.
DEPLOYED_PRESET_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def deployed_root():
    """`$DSH_HOME/.agent-presets` from the CURRENT environment, or None if unset."""
    dsh_home = os.environ.get(PRESET_ROOT_ENV, "")
    if not dsh_home:
        return None
    return os.path.join(dsh_home, DEPLOYED_DIR_NAME)


def deployed_dir_name(preset_id):
    """Repo preset id -> deployed directory name (the orchestrator keeps its own)."""
    return preset_id if preset_id == ORCHESTRATOR_ID else DEPLOYED_PREFIX + preset_id


def repo_preset_sources(project_root):
    """{preset id: {file: repo source path}}, from the canonical registry.

    Registry order, orchestrator first: `config/agents.yaml` `agents[]` names the 15
    specialists, and the orchestrator is registered separately there (it is not a
    sixteenth specialist), so it is prepended rather than looked up in `agents[]`.
    """
    registry_path = os.path.join(project_root, "config", "agents.yaml")
    with open(registry_path, encoding="utf-8") as fh:
        registry = yaml.safe_load(fh)
    ids = [ORCHESTRATOR_ID] + [entry["id"] for entry in registry["agents"]]
    sources = {}
    for preset_id in ids:
        src_dir = (
            ORCHESTRATOR_ID
            if preset_id == ORCHESTRATOR_ID
            else os.path.join("agents", preset_id)
        )
        sources[preset_id] = {
            name: os.path.join(src_dir, name) for name in PRESET_FILES
        }
    return sources


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _plural(count, singular, plural):
    return singular if count == 1 else plural


# Appended to every content-drift failure: what the reader is supposed to DO.
DEPLOY_ACTION = (
    "ACTION: re-deploy from the repo source — copy the listed repo file over its "
    f"deployed counterpart under ${{{PRESET_ROOT_ENV}}}/*/{DEPLOYED_DIR_NAME}/. "
    "Deployment is MANUAL: this repo has no deploy script, so a repo edit propagates "
    "to nothing and no other check notices the lag. If instead the DEPLOYED copy was "
    "hand-edited, fix the repo source first and re-deploy from it — the repo is the "
    "source of truth, and a live-only edit is unversioned, unreviewed and invisible to "
    "tests/validate_config.py."
)


@pytest.fixture(scope="module")
def deployment(project_root):
    """The deployed preset root + the repo-side source map, or a clean SKIP.

    Returns (root, sources). Module-scoped so every test in this file skips together
    when there is no deployment to inspect.
    """
    root = deployed_root()
    if root is None:
        pytest.skip(
            f"{PRESET_ROOT_ENV} is unset, so the live user preset root "
            f"${PRESET_ROOT_ENV}/{DEPLOYED_DIR_NAME} cannot be located and the "
            f"deployed side of this invariant (repo source -> {DEPLOYED_DIR_NAME}/) "
            "cannot be read in this environment"
        )
    if not os.path.isdir(root):
        pytest.skip(
            f"the deployed preset root {os.path.join(root, '')} does not exist (or is "
            f"not a directory), so nothing has been deployed in ${PRESET_ROOT_ENV}="
            f"{os.environ.get(PRESET_ROOT_ENV, '')} to compare the repo sources "
            "against"
        )
    sources = repo_preset_sources(project_root)
    missing = [
        path
        for files in sources.values()
        for path in files.values()
        if not os.path.isfile(path)
    ]
    assert not missing, (
        f"the repo itself is missing {len(missing)} preset source file(s) that "
        f"`config/agents.yaml` implies must exist: {missing}. Deployment cannot be "
        "checked against a source that is not there; author or restore them first."
    )
    return root, sources


# ---------------------------------------------------------------------------
# 1. content sync
# ---------------------------------------------------------------------------


def test_deployed_files_are_byte_identical_to_their_repo_sources(deployment):
    """sha256(repo file) == sha256(deployed file) for all 16 presets x 2 files.

    Bytes, not parsed data: the drift that was actually found was in a comment block
    (see module docstring), which a YAML-equality check cannot see.
    """
    root, sources = deployment
    drift = []
    for preset_id in sorted(sources):
        target = deployed_dir_name(preset_id)
        for name in PRESET_FILES:
            repo_path = sources[preset_id][name]
            deployed_path = os.path.join(root, target, name)
            if not os.path.isfile(deployed_path):
                drift.append(
                    f"{target}/{name}: no deployed file at {deployed_path} "
                    f"(repo source {repo_path})"
                )
                continue
            repo_digest, deployed_digest = _sha256(repo_path), _sha256(deployed_path)
            if repo_digest != deployed_digest:
                drift.append(
                    f"{target}/{name}: CONTENT DRIFT — repo {repo_path} is "
                    f"sha256 {repo_digest[:16]}..., deployed {deployed_path} is "
                    f"{deployed_digest[:16]}... (not byte-identical; a comment-only or "
                    "whitespace-only change counts, and here counts as drift)"
                )
    total = len(sources) * len(PRESET_FILES)
    assert not drift, (
        f"{len(drift)} of {total} deployed preset files do not match their repo "
        "source:\n  " + "\n  ".join(drift) + "\n" + DEPLOY_ACTION
    )


# ---------------------------------------------------------------------------
# 2. set completeness
# ---------------------------------------------------------------------------


def test_deployed_preset_set_is_exactly_the_repo_sourced_set(deployment):
    """Nothing deployed without a repo source; nothing sourced without a deployment.

    Two distinct failures with two distinct messages: an orphan is an unauthored live
    artifact, a gap is a preset the live roster can never select.
    """
    root, sources = deployment
    expected = {deployed_dir_name(preset_id) for preset_id in sources}
    present = {
        entry.name
        for entry in os.scandir(root)
        if entry.is_dir() and DEPLOYED_PRESET_ID.match(entry.name)
    }

    orphaned = sorted(present - expected)
    assert not orphaned, (
        f"DEPLOYED BUT UNSOURCED — {len(orphaned)} live preset "
        f"{_plural(len(orphaned), 'directory', 'directories')} under {root} with no repo "
        f"source: {orphaned}. The repo is the source of truth, so these are unauthored "
        "and unversioned: no repo file, no registry entry in `config/agents.yaml`, "
        "nothing for tests/validate_config.py or any doc to check, nothing to review or "
        "roll back — and they are live and selectable anyway. This is exactly the hole "
        "the 15 `preset.yml` files sat in until 2026-09-12, when they were deployed with "
        "no repo counterpart at all. ACTION: if it is a real preset, author its source "
        "in the repo (`orchestrator/` or `agents/<id>/`, registered in "
        "`config/agents.yaml`) and re-deploy from there; otherwise remove the directory "
        "from the live preset root. Do not leave a preset that exists only in the "
        "deployment."
    )

    undeployed = sorted(expected - present)
    assert not undeployed, (
        f"SOURCED BUT NOT DEPLOYED — {len(undeployed)} repo-sourced preset "
        f"{_plural(len(undeployed), 'directory', 'directories')} missing under {root}: "
        f"{undeployed}. They exist in the repo and in the registry, and AGENTS.md / "
        "`config/role-preset-mapping.yaml` claim every one of them is mounted, so "
        "either that claim is now false or the deployment was removed or half-done. The "
        "live roster cannot select a preset that is not deployed, so any session "
        "believing it runs one of these silently does not. ACTION: deploy it manually by "
        "copying both files into the expected directory (there is no deploy script), then "
        "re-run this test; or, if the preset was deliberately undeployed, update the "
        "registry and the mapping claims in the same change."
    )


# ---------------------------------------------------------------------------
# 3. mode uniformity
# ---------------------------------------------------------------------------


def _split_message(singular, plural, modes, counted):
    """Failure text for a permission split — names the modes, never demands a value."""
    lines = "\n  ".join(
        f"{mode:03o}: {sorted(names)}" for mode, names in sorted(modes.items())
    )
    return (
        f"MODE SPLIT — deployed preset {plural} are not uniformly permissioned: "
        f"{counted} {plural} carry {len(modes)} different modes —\n  {lines}\n"
        f"ACTION: bring every deployed preset {singular} to one mode. This gate "
        "asserts UNIFORMITY only, never a value: the defect it exists to catch is a "
        "split between deployment batches (8 directories at one mode, 8 at another), "
        "which no per-file check can see. The owner's chosen posture — directories "
        "700, files 600, owner-only — was set on 2026-09-12 and is recorded in the "
        "module docstring as intent, NOT as an assertion: a host whose umask deployed "
        "different bits is not a defect, so do not 'fix' this by hard-coding 600/700 "
        "here. Make the deployment consistent."
    )


def test_all_deployed_preset_directories_share_one_mode(deployment):
    """Uniformity across the deployed preset directories — no expected value."""
    root, sources = deployment
    dirs = [
        os.path.join(root, deployed_dir_name(preset_id))
        for preset_id in sorted(sources)
    ]
    present = [d for d in dirs if os.path.isdir(d)]
    modes = {}
    for path in present:
        modes.setdefault(_mode(path), []).append(os.path.basename(path))
    assert len(modes) <= 1, _split_message(
        "directory", "directories", modes, len(present)
    )


def test_all_deployed_preset_files_share_one_mode(deployment):
    """Uniformity across the 32 deployed preset files — no expected value."""
    root, sources = deployment
    files = [
        os.path.join(root, deployed_dir_name(preset_id), name)
        for preset_id in sorted(sources)
        for name in PRESET_FILES
    ]
    present = [p for p in files if os.path.isfile(p)]
    modes = {}
    for path in present:
        modes.setdefault(_mode(path), []).append(os.path.relpath(path, root))
    assert len(modes) <= 1, _split_message("file", "files", modes, len(present))
