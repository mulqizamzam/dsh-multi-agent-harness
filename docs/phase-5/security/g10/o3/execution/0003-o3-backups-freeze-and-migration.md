# G10 O3 — Item 4–6: Pre-Change Backups + Freeze-Window Procedure + Phase A/B/C Migration Order

- **In**: `docs/phase-5/security/g10/o3/execution/` (part of the execution-readiness package)
- **Companion**: `0001` (master handoff) · `0002` (approvals + infrastructure) · `0004` (acceptance, rollback) · `0005` (closure gate, evidence)
- **Status**: OPERATOR/ENGINEERING RUNBOOK (exact, actionable). **No backups were created, no freeze window was scheduled, no migration was performed this session.** All commands below are **prescribed** — documented, not executed.

---

## 1. Exact pre-change backups (item 4)

### 1.1 Purpose

The pre-change backups are the **mandatory rollback precondition** (decision package §7, FINAL 0001 §4.11). Before the write-path switch (Phase B), every file that Phase B will modify must be backed up byte-for-byte with a recorded SHA-256 manifest. Without these backups, **rollback is not authorized**.

### 1.2 Files to back up

**A. Control-plane files (Phase B will modify these):**

| # | File | Role |
|---|---|---|
| B1 | `control/execution_gate.py` | `registry_write()` and `audit_append()` will be switched from direct-write to daemon client |
| B2 | `orchestrator/runtime/store.py` | `RuntimeStore.persist()`/`ensure_state()`/`load_project_state()` will be switched to daemon client |
| B3 | `orchestrator/runtime/delegation.py` | `FileDelegationProvider.current()` will be switched to daemon client `registry_read()` |
| B4 | `orchestrator/runtime/audit.py` | `RuntimeAudit.emit()` will route through daemon-backed `audit_append()`; audit reads → daemon |
| B5 | `config/registry-writer.yaml` | New daemon config (created during implementation, will be referenced by the daemon client) |

**B. Data files (Phase A will copy these; Phase B will remove them from the workspace):**

| # | File/Directory | Role |
|---|---|---|
| D1 | `state/registry/` (entire directory) | Delegation/revocation documents — will be moved to daemon root |
| D2 | `state/projects/` (entire directory) | Project state documents — will be moved to daemon root |
| D3 | `audit/runtime/` (entire directory) | Audit ledgers + chain sidecars — will be moved to daemon root |

### 1.3 Backup procedure (exact steps)

**Step 1: Create the backup directory** (following the O5 convention: `docs/phase-5/security/g10/implementation/backups/o3-pre/`):

```bash
BACKUP_DIR="docs/phase-5/security/g10/implementation/backups/o3-pre"
mkdir -p "$BACKUP_DIR"
```

**Step 2: Copy the five control-plane files** (B1–B5):

```bash
cp control/execution_gate.py "$BACKUP_DIR/execution_gate.py"
cp orchestrator/runtime/store.py "$BACKUP_DIR/store.py"
cp orchestrator/runtime/delegation.py "$BACKUP_DIR/delegation.py"
cp orchestrator/runtime/audit.py "$BACKUP_DIR/audit.py"
cp config/registry-writer.yaml "$BACKUP_DIR/registry-writer.yaml"
```

**Step 3: Record SHA-256 manifest** (exact command):

```bash
cd "$BACKUP_DIR"
sha256sum execution_gate.py store.py delegation.py audit.py registry-writer.yaml > MANIFEST.sha256
cat MANIFEST.sha256
```

**Step 4: Verify the manifest:**

```bash
sha256sum -c MANIFEST.sha256
# Expected: all files: OK
```

**Step 5: Copy the three data directories** (D1–D3, as a snapshot — **after Phase A copy but before Phase B switch**):

```bash
cp -a state/registry "$BACKUP_DIR/state-registry"
cp -a state/projects "$BACKUP_DIR/state-projects"
cp -a audit/runtime "$BACKUP_DIR/audit-runtime"
# Record SHA-256 for the snapshot
find "$BACKUP_DIR" -type f -name "*.json" -o -name "*.jsonl" -o -name "*.chain" | sort | xargs sha256sum >> "$BACKUP_DIR/MANIFEST.sha256"
```

**Step 6: Store the backup immutably** (outside the workspace is preferred, but inside `docs/` is acceptable per the O5 convention). If outside the workspace:

```bash
sudo cp -a "$BACKUP_DIR" /var/lib/dsh-registry-writer/backup/pre-change-manifest
```

### 1.4 Verification (operator)

```bash
# Verify the backup matches the live files (BEFORE Phase B)
cd docs/phase-5/security/g10/implementation/backups/o3-pre
sha256sum -c MANIFEST.sha256
# All files: OK

# Record the current hashes as the rollback reference
cat MANIFEST.sha256
```

### 1.5 Baseline hashes (this session, for reference)

The control-plane files' SHA-256 as of this session (execution-package authoring time) are recorded in `0001` §4. These are the **pre-implementation baseline** — evidence that the files are still the V1 originals. The operator must re-capture fresh hashes at the moment backups are made (Step 3 above) because the files may change between this session and the implementation session.

---

## 2. Freeze-window procedure (item 5)

### 2.1 Purpose

The freeze window is a scheduled period during which **writes to the three G10 residual roots (`state/registry/**`, `audit/**`, `state/projects/**`) are stopped** so that the write path can be switched atomically and the single-writer contract verified (threat model T6). No window where both the old direct-write path and the new daemon IPC path write the same root.

### 2.2 Scheduling

| Property | Requirement |
|---|---|
| Duration | **Minimum: 30 minutes.** Estimated: 15 min for the switch + 10 min for verification + 5 min holdback. |
| Notification | The Human operator announces the freeze start/end to all active session participants. |
| Window type | **Maintenance window** — no production deployment is possible (G10 is OPEN/BLOCKING, production is BLOCKED, so there is no production traffic to schedule around). |
| Holdback | 5 minutes after the switch is verified before resuming writes. If verification fails, the operator triggers rollback within the holdback (see `0004` §2). |

### 2.3 Freeze window checklist

**Phase B-1: Pre-freeze (operator, 5 min before freeze start)**

- [ ] Verify the pre-change backups exist and are verified (`sha256sum -c MANIFEST.sha256` — all OK).
- [ ] Verify the daemon is running and healthy (`health?name=ready` returns `ok`).
- [ ] Verify the daemon acceptance suite passed (FINAL 0004 suite in a throwaway temp root — see `0004` §1).
- [ ] Announce freeze start + expected duration to all participants.
- [ ] Record the current audit chain's final cumulative hash (`audit_read` / `audit_verify`).
- [ ] Record the current registry version (read `state/registry/delegations.json` version field).
- [ ] Record the current project state version (read `state/projects/multi-agent-harness.json` version field).

**Phase B-2: Freeze (operator, 0 min — writes STOPPED)**

- [ ] **Stop all delegation/state mutations** (pause the orchestrator or disable the delegation path). This is a control-plane operation: the orchestrator stops calling `registry_write()` and `RuntimeStore.persist()`.
- [ ] **Verify no writes are in-flight** (check that no running subagent is mid-write to the three roots).
- [ ] **Pause any scheduled backups or periodic integrity checks** (they would attempt reads, which are safe, but better to freeze completely).
- [ ] **Start the switch timer** (T+0).

**Phase B-3: Switch (engineering, T+0 to T+10 min)**

- [ ] Flip `execution_gate.registry_write()` → daemon client `registry_write`.
- [ ] Flip `execution_gate.audit_append()` → daemon client `audit_append`.
- [ ] Flip `RuntimeStore.persist()` / `ensure_state()` → daemon client `project_write`.
- [ ] Flip `RuntimeStore.load_project_state()` → daemon client `project_read`.
- [ ] Flip `FileDelegationProvider.current()` → daemon client `registry_read`.
- [ ] Flip audit reads → daemon client `audit_read` / `audit_verify`.
- [ ] **Remove the direct-write code paths** — not conditional; they are deleted or `# dead`-commented with a rationale. This is enforced by `O3-FC-005` (static grep: no `atomic_write`/`append_event`/`write_through` direct call targeting the three roots).
- [ ] Remove the three roots from the session workspace (or leave as `dsh-writer`-owned stubs, session-UID denied).
- [ ] **No in-workspace mirror** is created (FINAL 0001 §4.1 finalized decision).

**Phase B-4: Single-writer verification (engineering, T+10 to T+15 min)**

- [ ] Verify the daemon is the sole writer: attempt a direct fs write to `state/registry/` (in the workspace) → **DENIED** (root no longer writable perms or doesn't exist).
- [ ] Verify the daemon IPC `registry_write` / `audit_append` / `project_write` all succeed.
- [ ] Verify no dual-writer window: check logs/instrumentation that only the daemon wrote during the switch.
- [ ] Verify the audit chain continues from the pre-freeze cumulative hash (no chain break, event-id continues from max pre-freeze).
- [ ] Verify registry + project versions continue from pre-freeze versions.

**Phase B-5: Resume (operator, T+15 min — writes RESUMED)**

- [ ] Announce freeze end to all participants.
- [ ] Resume delegation/state mutations (re-enable the orchestrator).
- [ ] Start the monitored period (30 min watch — see Phase C).

### 2.4 Rollback during freeze window

If any verification step in Phase B-4 fails and is not remediable in-window (within the holdback):

- Trigger **rollback immediately** per `0004` §2.
- Announce freeze aborted + rollback to all participants.
- Do NOT resume writes until rollback is complete.

---

## 3. Phase A/B/C migration order (item 6)

### 3.1 Phase A — Prepare (before the freeze window)

**Goal:** Deploy the daemon alongside the existing V1 infrastructure; prove data continuity; no write-path change yet.

| Step | Action | Evidence to record |
|---|---|---|
| A1 | Provision P1–P5 (user, root, systemd, secret, group) per `0002` §3 | Provisioning verification results (V1–V9) |
| A2 | Implement the daemon code (all 9 components from FINAL 0001 §6 component inventory) | `git status` (or `ls`) showing the new files |
| A3 | Run the FINAL 0004 acceptance suite in a **throwaway temp root** (daemon spawned locally, all O3-DAEMON/IPC/SOCKET/ISO/MIG/REC/FC/HON tests pass) | Test output: all 47+ acceptance tests pass |
| A4 | Deploy the daemon as a systemd service; start it; verify `health?name=ready` | `systemctl status` + `health` response |
| A5 | Copy `state/registry/` → daemon root `state/registry/` | `cp -a` |
| A6 | Copy `state/projects/` → daemon root `state/projects/` | `cp -a` |
| A7 | Copy `audit/runtime/` → daemon root `audit/` | `cp -a` |
| A8 | Verify copied data SHA-256-identical to originals | `sha256sum` on both sides; all match |
| A9 | Run the daemon in **shadow mode** (reads only via IPC; all writes still go through the V1 direct path) | `registry_read` returns data identical to `safe_read`; `audit_read` returns identical events |
| A10 | Verify health, authn, fail-closed responses (IPC-001, IPC-002, FC-001, FC-002) | All pass |
| A11 | Run the full G10 suite + `validate_config` + `tests/phase5_security/` to confirm no regression | All green (should match or exceed the baselines in `0001` §3) |
| A12 | Capture pre-change backups (item 4, §1 above) | Backups exist; `MANIFEST.sha256` verified |

**Gate to Phase B:** All A1–A12 steps complete; all acceptance tests pass; H3+H4 approvals recorded.

### 3.2 Phase B — Switch (under the freeze window)

**Goal:** Atomically switch the write + read paths to the daemon; remove the direct-write paths; no in-workspace mirror.

| Step | Action | Evidence to record |
|---|---|---|
| B1 | Execute the freeze window procedure (§2 above) | Freeze start/end timestamps; pre-freeze hashes |
| B2 | Flip write paths (execution_gate, store, audit) to daemon client | Git diff (or file-level diff) showing the switch |
| B3 | Flip read paths (delegation, store.load, audit reads) to daemon client | Same diff |
| B4 | **Remove** the direct-write code paths — not conditional, removed | `O3-FC-005` static proof passes (grep shows no direct `atomic_write`/`append_event` to the three roots) |
| B5 | Remove the three roots from the session workspace (or `dsh-writer`-owned stubs, session-UID denied) | `ls state/registry/` → absent or owned by `dsh-writer`; `ls audit/runtime/` → absent |
| B6 | Verify single-writer (§2.4) | Single-writer proof; no dual-writer window |
| B7 | Resume writes (§2.5) | Resume timestamp |
| B8 | Run the full G10 suite + O3 acceptance suite + `validate_config` + `tests/phase5_security/` | All green |

**Gate to Phase C:** B1–B8 complete; all tests green; no rollback triggered.

### 3.3 Phase C — Verify (post-switch, monitored period)

**Goal:** Prove the isolation is working; re-derive the residual; run the full regression.

| Step | Action | Evidence to record |
|---|---|---|
| C1 | Verify the three roots are absent from the session workspace (or session-UID-denied) | `ls -la state/registry/` → no files; `ls -la audit/runtime/` → no files; `ls -la state/projects/` → no files |
| C2 | Re-derive the isolation probes: `test_raw_write_reaches_protected_path_unintercepted` → **DENIED** (O3-ISO-001..004) | All four probes pass (write denied by sandbox/OS) |
| C3 | Verify channeled writes still work through IPC (O3-ISO-005) | `registry_write`/`audit_append`/`project_write` via IPC succeed; files exist under daemon root |
| C4 | Verify no in-workspace mirror exists (O3-ISO-006) | No readable/writable mirror; canonical reads are IPC-only |
| C5 | Run the full G10 suite + O3 acceptance suite + `validate_config` + `tests/phase5_security/` + `tests/authorization/` + `tests/resilience/` + `tests/g13/` | All green |
| C6 | Run the full Phase-5 regression (`pytest tests/ -q`) | All green (or documented pre-existing failures) |
| C7 | Re-derive the per-root residual (FINAL 0002 §3) and record it | Residual record document updated |
| C8 | Monitored period: 30 minutes of normal operation with the daemon serving all writes | No anomalies; audit trails show writes routed through the daemon |
| C9 | Run the O3-HON-001..005 honesty tests | All pass (no false closure claim, no fabricated live result, no real state touched) |

**Gate to G10 closure decision:** C1–C9 complete; all tests green; residual re-derived; Human closure decision (H5) is the only remaining step.

---

*Status: RUNBOOK (items 4–6). No backups were created, no freeze window was scheduled, no migration was performed this session. All steps are prescribed as exact operator/engineering actions. The pre-change backup procedure (item 4) covers 5 control-plane files + 3 data directories with SHA-256 manifest. The freeze window (item 5) covers 5 phases from pre-freeze to resume, with a rollback trigger at any verification failure. The Phase A/B/C migration order (item 6) covers 12 + 8 + 9 steps with precise gates between each phase. G10 remains OPEN / BLOCKING. No closure claimed. No provisioning performed.*