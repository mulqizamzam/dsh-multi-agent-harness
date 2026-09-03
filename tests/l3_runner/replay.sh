#!/usr/bin/env bash
# tests/l3_runner/replay.sh — L3 replay / reproducibility entry (P4)
#
# Reruns an L3 scenario against its captured fixture with a deterministic seed
# and produces a byte-identical verdict-match.json (when the fixture is
# unchanged). An auditor executes this script to reproduce a scenario's
# PASS/FAIL outcome — docs/security/0003 §8.
#
# Usage:
#   tests/l3_runner/replay.sh L3-TEST-001 [--bundle-base DIR] [--seed N]
#
# SAFETY: uses the RecordedRuntimeDriver (replay mode) — it never runs a live
# DSH session and never executes a destructive/high-impact action.

set -euo pipefail

SCENARIO="${1:?usage: replay.sh <L3-SCENARIO-ID> [--bundle-base DIR] [--seed N]}"
shift || true

BUNDLE_BASE="${BUNDLE_BASE:-$(mktemp -d)}"
SEED="${SEED:-42}"

# Resolve the project root (two levels up from tests/l3_runner/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "L3 replay: scenario=${SCENARIO} seed=${SEED} bundle_base=${BUNDLE_BASE}"
cd "${PROJECT_ROOT}"

PYTHON="${PYTHON:-python3}"
exec "${PYTHON}" -m tests.l3_runner.runner \
    --scenario "${SCENARIO}" \
    --mode replay \
    --seed "${SEED}" \
    --bundle-base "${BUNDLE_BASE}" \
    "$@"
