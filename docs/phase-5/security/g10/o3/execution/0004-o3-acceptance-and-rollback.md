# G10 O3 — Item 7–8: Acceptance Test Order + Rollback

- **In**: `docs/phase-5/security/g10/o3/execution/` (part of the execution-readiness package)
- **Companion**: `0001` (master handoff) · `0002` (approvals + infrastructure) · `0003` (backups, freeze, migration) · `0005` (closure gate, evidence)
- **Status**: OPERATOR/ENGINEERING RUNBOOK (exact, actionable). **No acceptance tests were run (no daemon), no rollback was performed this session.** All commands are **prescribed** — documented, not executed.

---

## 1. Acceptance test order (item 7)

### 1.1 Test groups (from FINAL 0004, authoritative)

The O3 acceptance suite is defined in FINAL 0004 as eight categories. The order of execution below is designed to prove the most foundational properties first, so that a failure in a basic property (daemon won't start) blocks higher-level tests (migration, fail-closed) early.

| Priority | Group | Tests | What it proves | Blocking for |
|---|---|---|---|---|
| **P0** | **HONESTY** | O3-HON-001..005 | No false closure claim; no fabricated live result; no real state touched; prerequisites asserted | ALL other groups |
| **P1** | **DAEMON** | O3-DAEMON-001..010 | Daemon is the sole writer; path scoping; CAS; monotonic version; schema validation; self-audit | IPC, ISO, MIG, REC, FC |
| **P2** | **IPC** | O3-IPC-001..008 | Round-trip; authn (HMAC, replay, window); authz (channel→method→root); malformed requests | ISO, MIG, REC, FC |
| **P3** | **SOCKET** | O3-SOCKET-001..004 | Cross-UID connectivity; group-writable socket; primary HMAC gate; no TCP listener | DEPLOYMENT (integration-level) |
| **P4** | **ISOLATION** | O3-ISO-001..006 | Raw session write DENIED to daemon roots; channeled write through IPC still works; no in-workspace mirror | MIG, REC, CLOSURE |
| **P5** | **MIGRATION** | O3-MIG-001..006 | Copied data identical; chain survives; event-id continues; single-writer during cutover; read path switched | SWITCH (Phase B) |
| **P6** | **RECOVERY** | O3-REC-001..006 | Restart with intact/corrupted ledger; backup/restore verified; tampered backup refused; authority path unchanged | OPERATIONS |
| **P7** | **FAILCLOSED** | O3-FC-001..006 | Daemon down ⇒ BLOCKED; no fallback; static proof of no direct-write path; cold-start ordering | CLOSURE |

### 1.2 Execution order across phases

| Phase | Which tests run | Environment | Gate |
|---|---|---|---|
| **Pre-implementation** (this package) | O3-HON-001..005 (planning honesty guards) | `tests/g10/o3-planning/` + `tests/g10/decision/` + `tests/g10/o3-execution/` | All pass (current count: 123 + 32 + execution stubs) |
| **Phase A** (after daemon implementation) | **Full suite** (P0–P7) in a throwaway temp daemon root | Temp dir (e.g. `tmp_path` fixture from `tests/g10/conftest.py`); daemon spawned locally by the test process | All 47+ acceptance tests pass |
| **Phase A** (after shadow mode deployment) | MIG-001..004 (data continuity); IPC-001, IPC-002 (shadow-mode reads) | Daemon running on the real root in shadow mode; reads only; writes still V1 direct | All pass |
| **Phase B** (during freeze window) | MIG-005 (single-writer during cutover); MIG-006 (read path switched) | On the real root, during the freeze window | All pass |
| **Phase B** (after switch) | ISO-001..006 (re-derived isolation probes); FC-001, FC-005, FC-006 (fail-closed + static proof + cold-start) | On the real root, post-switch | All pass |
| **Phase C** (verification) | Full suite (P0–P7) re-run on the real root; plus full G10 suite + `validate_config` + `tests/phase5_security/` + `tests/authorization/` + `tests/resilience/` + `tests/g13/` + full Phase-5 regression | Real deployed daemon with real state | All green |
| **Post-implementation** (sustained) | O3-HON-001..005 (no closure drift); O3-REC-001..006 (recovery); O3-FC-001..006 (fail-closed) | Real daemon; periodic integrity checks | All pass |

### 1.3 Acceptance test runner command (prescribed)

```bash
# Pre-condition: the venv is active (or .venv-tests/bin/python is used)
cd /home/administrator/agent-workspace/multi-agent-harness

# Run the full O3 acceptance suite (P0–P7) in a throwaway temp root
.venv-tests/bin/python -m pytest tests/g10/o3-execution/ -v --tb=long 2>&1 | tee /tmp/o3-acceptance-output.txt

# Run the full G10 suite (post-O3)
.venv-tests/bin/python -m pytest tests/g10/ -v --tb=long 2>&1 | tee /tmp/g10-suite-output.txt

# Run validate_config
.venv-tests/bin/python tests/validate_config.py 2>&1 | tee /tmp/validate-config-output.txt

# Run the full Phase-5 regression
.venv-tests/bin/python -m pytest tests/ -v --tb=long 2>&1 | tee /tmp/full-regression-output.txt
```

### 1.4 Expected pass/fail counts

| Suite | Expected Pass | Notes |
|---|---|---|
| O3 acceptance (P0–P7) | 47+ (all tests in the spec) | All must pass for closure |
| `tests/g10/` | ≥ 233 (current baseline) | Post-O3, the isolation probes are re-derived (O3-ISO-001..004 replace the V1 probes) |
| `tests/g10/o3-planning/` | ≥ 123 (current baseline) | Pristine suite; no change expected |
| `tests/g10/decision/` | ≥ 32 (current baseline) | Pristine suite; no change expected |
| `tests/g10/o3-execution/` | All execution-gate tests pass | Consistency checks for this package |
| `tests/validate_config.py` | PASS (as script) | Must pass |
| `tests/phase5_security/` + `tests/authorization/` | ≥ 192 (current baseline) | Must pass |
| Full Phase-5 regression | All green (or documented pre-existing isolation failures) | Pre-existing failures documented in the reconciliation report (10 entrypoint isolation failures pass in isolation) |

**Note:** the current `tests/g10/` baseline (233) has grown since the earlier documented counts (150 / 201). This is consistent with the reconciliation report R13. The operator should record the **current** baseline at the start of the implementation session and verify that the post-O3 suite adds new tests (O3-DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON) without removing or modifying existing ones.

---

## 2. Rollback (item 8)

### 2.1 Rollback precondition (MANDATORY)

**Before any rollback is attempted, the pre-change backups must exist and be verified** (per `0003` §1). Without these, **rollback is not authorized**. The backups must include:

- `control/execution_gate.py` — pre-change SHA-256
- `orchestrator/runtime/store.py` — pre-change SHA-256
- `orchestrator/runtime/delegation.py` — pre-change SHA-256
- `orchestrator/runtime/audit.py` — pre-change SHA-256
- `config/registry-writer.yaml` — pre-change SHA-256
- `state/registry/`, `state/projects/`, `audit/runtime/` — pre-change snapshot SHA-256

### 2.2 Rollback trigger conditions

Any of the following triggers an immediate rollback:

| # | Trigger | Detectable by |
|---|---|---|
| R1 | Any acceptance criterion A1–A5 fails and is not remediable in-window | Failed acceptance test |
| R2 | Migration continuity breaks during/after Phase B: SHA-256 mismatch, audit chain break, event-id gap/re-allocation, CAS version mismatch | Verification step (MIG-001..004) |
| R3 | A dual-writer window is detected during cutover (threat model T6) | Log/instrumentation |
| R4 | Daemon fail-closed outage exceeds the operator's tolerance and cannot be recovered by restart | Health check / alerting |
| R5 | Human rejects closure at H5 (this is a scheduled rollback, not an emergency) | Human decision |

### 2.3 Rollback sequence (file-level, no git — exact steps)

**Emergency rollback (R1–R4 triggers during the freeze window):**

```bash
# Step 1: Stop the daemon; disable its service unit
sudo systemctl stop dsh-registry-writer.service
sudo systemctl disable dsh-registry-writer.service

# Step 2: Restore the four control-plane files from pre-change backups
BACKUP_DIR="docs/phase-5/security/g10/implementation/backups/o3-pre"
cp "$BACKUP_DIR/execution_gate.py" control/execution_gate.py
cp "$BACKUP_DIR/store.py" orchestrator/runtime/store.py
cp "$BACKUP_DIR/delegation.py" orchestrator/runtime/delegation.py
cp "$BACKUP_DIR/audit.py" orchestrator/runtime/audit.py

# Step 3: Restore the data roots to the session workspace
cp -a "$BACKUP_DIR/state-registry"/* state/registry/
cp -a "$BACKUP_DIR/state-projects"/* state/projects/
cp -a "$BACKUP_DIR/audit-runtime"/* audit/runtime/

# Step 4: Restore ownership/permissions if needed
chown -R administrator:administrator state/registry/ state/projects/ audit/runtime/

# Step 5: Verify audit chain + hash sidecar + CAS versions intact
.venv-tests/bin/python -m pytest tests/g10/ -k "test_audit_integrity or test_chain" -q --tb=short
# Expected: all pass

# Step 6: Restart the affected orchestrator processes (or reload the Python modules)
# (exact mechanism depends on the orchestrator deployment; hot-reload or restart as appropriate)

# Step 7: Run validation
.venv-tests/bin/python tests/validate_config.py
.venv-tests/bin/python -m pytest tests/g10/ -q --tb=short
# Expected: all green (pre-O3 state restored)

# Step 8: Audit the rollback event
echo "ROLLBACK $(date -u +%Y-%m-%dT%H:%M:%SZ) trigger=R1/R2/R3/R4 daemon=stopped files=restored verify=passed" >> audit/runtime/rollback-events.log
```

**Scheduled rollback (R5 — Human rejects closure):**

Same as above, but performed during a scheduled maintenance window (not an emergency). The operator may also choose to leave the daemon running but with writes still routed through the old direct path (i.e., undo Phase B but keep Phase A infrastructure). This is allowed only if the shutdown is not a security-compromise scenario.

### 2.4 Post-rollback verification

After any rollback, the operator must verify:

| Check | Command | Expected |
|---|---|---|
| V1 | `sha256sum control/execution_gate.py` | Matches the pre-change backup hash |
| V2 | `sha256sum orchestrator/runtime/store.py` | Matches the pre-change backup hash |
| V3 | `sha256sum orchestrator/runtime/delegation.py` | Matches the pre-change backup hash |
| V4 | `sha256sum orchestrator/runtime/audit.py` | Matches the pre-change backup hash |
| V5 | `tests/validate_config.py` | PASS |
| V6 | `tests/g10/` full suite | All green (≥233) |
| V7 | `tests/g10/o3-planning/` + `tests/g10/decision/` | All green (≥123 + ≥32) |
| V8 | `state/registry/` exists and is readable in-workspace | Yes (restored) |
| V9 | `audit/runtime/` exists and is readable in-workspace | Yes (restored) |
| V10 | Daemon is stopped and disabled | `systemctl is-active dsh-registry-writer.service` → inactive |

### 2.5 Rollback reversibility

**Reversibility: MEDIUM** (the write path is the most sensitive surface). Rollback is straightforward if the pre-change backups are intact and the migration continuity checks pass. The risks are:

- **Cosmetic dirt:** the backup/restore cycle may leave a `config/registry-writer.yaml` file that was created during Phase A but is no longer referenced. This is harmless and can be cleaned up manually.
- **Event-id gap:** if writes occurred during the freeze window between the pre-change snapshot and the switch, those writes may be reflected in the daemon audit root but not in the restored V1 workspace. The operator should verify the audit chain continuity and, if needed, manually append the missing events.
- **No git:** there is no commit history to revert to; all operations are file-level. The backup manifest is the single source of truth for the pre-change state.

---

*Status: RUNBOOK (items 7–8). Acceptance test order is prescribed (P0→P1→P2→P3→P4→P5→P6→P7 across phases, with expected pass/fail counts). Rollback is documented with exact commands (file-level, no git), 5 trigger conditions, 8 post-rollback verification checks, and a note on reversibility (MEDIUM). No acceptance tests were run this session (no daemon); no rollback was performed. G10 remains OPEN / BLOCKING. No closure claimed.*