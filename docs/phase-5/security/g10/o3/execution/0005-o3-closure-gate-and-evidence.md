# G10 O3 — Item 9–10: G10 Closure Gate + Evidence Required at Each Step

- **In**: `docs/phase-5/security/g10/o3/execution/` (part of the execution-readiness package)
- **Companion**: `0001` (master handoff) · `0002` (approvals + infrastructure) · `0003` (backups, freeze, migration) · `0004` (acceptance, rollback)
- **Status**: GATE DEFINITION + EVIDENCE MATRIX. **No closure is claimed. G10 remains OPEN / BLOCKING. No evidence was generated this session beyond the current-state probes in `0001` §3.**

---

## 1. G10 closure gate (item 9)

### 1.1 What the closure gate is

The G10 closure gate is the **Human decision H5** (decision package §3, `0001` §1.1 of this package). It is the final gate after all implementation, migration, and verification steps are complete. No test, no session, no automated process decides G10 closure — only the Human decision-maker.

### 1.2 The six conditions (from FINAL 0002 §4.1, authoritative)

G10 closure is **conditionally** available only when **all six** conditions hold:

| # | Condition | Criterion | Proved by |
|---|---|---|---|
| **C1** | **A+B isolation** deployed | Roots outside `workspaceRoot` (Option A) AND dedicated OS UID (Option B, defense-in-depth). An in-workspace layout is NOT O3 and permits no closure claim. | `0002` §3 provisioning verification + `0003` §3 Phase A verification |
| **C2** | **`state/projects/**` extension implemented** | The daemon owns all three roots (registry + audit + projects), not just registry/audit. Without this, `state/projects/**` remains CAS-detected only and R is not closed for that root. | FINAL 0002 §3 per-root determination + O3-DAEMON-004, O3-ISO-003 |
| **C3** | **Write path is fully switched** | No direct-write path to the three roots remains reachable in the control plane. Static proof `O3-FC-005` (grep for `atomic_write`/`append_event`/`write_through` targeting the three roots) shows only daemon-client calls. | O3-FC-005 (static proof) + code review |
| **C4** | **No silent fallback** | Daemon down ⇒ writes to the three roots **block** (`WRITER_UNAVAILABLE`). A fallback is a design violation and would restore the residual. | O3-FC-001, O3-FC-006 |
| **C5** | **Verification passes** | The FINAL 0004 acceptance suite (DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON) all pass; the full G10 suite passes; `validate_config` passes; the full Phase-5 regression passes (or pre-existing failures documented). | `0004` §1 expected pass/fail counts |
| **C6** | **Human approval (H3 + H4 + H5)** | H3 (approve O3 infrastructure) and H4 (approve `state/projects/**` extension) are recorded before implementation. H5 (closure decision) is recorded after verification. | `0002` §1.2 approval recording procedure |

### 1.3 Closure record format

When the Human decides to close G10 (H5), the closure must be recorded as:

A document at `docs/phase-5/security/g10/o3/final/0005-o3-closure-record.md` (or an appropriate updated document) containing:

- **Date**: ISO 8601 timestamp of the decision.
- **Decision maker**: Human identifier.
- **Six conditions**: each verified with its evidence reference.
- **Per-root residual after O3**: from FINAL 0002 §3, with the closure state for each root.
- **Accepted residuals (T4, T5, T8)**: recorded (not regressions).
- **G10 matrix row re-derived**: the G10 row in the security closure matrix is updated to CLOSED.
- **Production still BLOCKED**: a statement that G10 closure is necessary but not sufficient for production (G13 OPEN/UNKNOWN, B1/B2/B3/B7/B8 remain).
- **No earlier closure claim overwritten**: the historical G10 OPEN/BLOCKING records are preserved.

### 1.4 What does NOT close G10

The following scenarios are **not** G10 closure:

- **O3 designed but not implemented** (current state) — G10 remains OPEN/BLOCKING.
- **O3 implemented without A+B isolation** (e.g., in-workspace root) — this is NOT O3; it's a weaker O2-style partial mitigation; no closure claim permitted.
- **O3 implemented without the `state/projects/**` extension** — `state/projects/**` remains CAS-detected only; R is not closed for that root; G10 is not fully closed.
- **O3 implemented with a fallback to direct-write when the daemon is down** — the fallback restores the residual; no closure claim permitted.
- **O3 implemented but the acceptance suite has failures** — verification is incomplete; no closure claim permitted.
- **O3 implemented without Human approval H3/H4/H5** — no test or session decides closure; the Human must decide.

### 1.5 What remains blocking after G10 closure

Even after G10 is closed (under C1–C6), production remains BLOCKED. The operator must understand this:

| Condition | Status after G10 closure | Class |
|---|---|---|
| G10 prevention gap (3 roots) | CLOSED (only under C1–C6) | CLOSED |
| **G13** prompt-injection | Deterministic defenses verified; live DSH child behavior + DSH driver-internal isolation UNKNOWN | **OPEN / UNKNOWN — BLOCKING** |
| **L3** independent verification | Zero controls L3; same-UID sandbox prevents any L3 claim | **BLOCKED** |
| D4/D7 live bridge marker | `DSH_LIVE_BRIDGE_ACTIVE` unset; live dispatch + live variants blocked | **BLOCKED** |
| Approval answerer E2E | E2E approval status UNKNOWN | **BLOCKED** / UNKNOWN |
| HIGH-risk independent verification (VER-2) | Independent measurement channel not built | **BLOCKED** |
| Production deployment | **NOT STARTED / NOT PRODUCTION-READY** | **BLOCKED** |

**One sentence:** *G10 closure unblocks exactly one gate (G10) and is necessary but not sufficient for production.*

---

## 2. Evidence required at each step (item 10)

### 2.1 Consolidated evidence matrix

The table below lists **every step** in the O3 execution sequence, the **evidence artifact** it must produce, the **verification command** that checks it, and the **recorded location**.

| Step | Phase | Evidence artifact | Verification command | Recorded location |
|---|---|---|---|---|
| **H3/H4 approval** | Pre | Approval record (signed document) | `ls docs/phase-5/security/g10/implementation/backups/o3-pre/` | `docs/phase-5/security/g10/implementation/backups/o3-pre/` |
| **P1: dsh-writer user** | Pre | User existence | `id dsh-writer` | Operator log |
| **P2: daemon root** | Pre | Root existence + permissions | `stat -c '%U %G %a' /var/lib/dsh-registry-writer/` | Operator log |
| **P3: systemd unit** | Pre | Unit enabled + loaded | `systemctl is-enabled dsh-registry-writer.service` | Operator log |
| **P4: HMAC secret** | Pre | Secret file exists + permissions | `stat -c '%U %G %a' /etc/dsh-registry-writer/hmac-secret` | Operator log |
| **P5: dsh group** | Pre | Group membership | `getent group dsh`; `groups administrator` | Operator log |
| **A2: daemon implemented** | A | New files present | `ls registry_writer/`, `ls schemas/ipc.py`, `ls config/registry-writer.yaml` | Git diff or file listing |
| **A3: acceptance (temp root)** | A | Test output (P0–P7 all pass) | `pytest tests/g10/o3-execution/ -v --tb=long` | `/tmp/o3-acceptance-output.txt` |
| **A4: daemon deployed + ready** | A | systemd status + health check | `systemctl status dsh-registry-writer.service`; `health?name=ready` | Operator log |
| **A5–A7: data copy** | A | Copy command output | `cp -a` exit code 0 | Operator log |
| **A8: data SHA-256 match** | A | SHA-256 manifest | `sha256sum -c MANIFEST.sha256` (all OK) | `docs/phase-5/security/g10/implementation/backups/o3-pre/MANIFEST.sha256` |
| **A9: shadow mode reads** | A | IPC reads return identical data | `registry_read` output vs `safe_read` output | Test output |
| **A10: health/authn/fail-closed** | A | IPC-001, IPC-002, FC-001, FC-002 pass | `pytest -k "O3-IPC-001 or O3-IPC-002 or O3-FC-001 or O3-FC-002"` | Test output |
| **A11: pre-switch regression** | A | `tests/g10/`, `validate_config`, `tests/phase5_security/` all green | `pytest tests/g10/ -q`; `python tests/validate_config.py` | Test output |
| **A12: pre-change backups** | A | Backup files + MANIFEST.sha256 | `sha256sum -c MANIFEST.sha256` (all OK) | `docs/phase-5/security/g10/implementation/backups/o3-pre/` |
| **B1: freeze start** | B | Freeze announcement + pre-freeze hashes | `echo` + file hashes committed | Operator log + evidence doc |
| **B2–B3: write path switch** | B | Code diff showing the switch | `diff` between backup and live file | `0003` §2.3 Phase B-3 checklist |
| **B4: direct-write removed** | B | O3-FC-005 static proof passes | `pytest -k O3-FC-005` | Test output |
| **B5: roots removed from workspace** | B | `ls state/registry/`, `ls audit/runtime/`, `ls state/projects/` → absent or stub | `ls` output | Operator log |
| **B6: single-writer verified** | B | No dual-writer window detected | Log/instrumentation check | Operator log |
| **B7: resume** | B | Resume announcement + timestamp | `echo` + timestamp | Operator log |
| **B8: post-switch regression** | B | Full G10 + O3 acceptance + validate_config + phase5_security | `pytest tests/g10/ -q`; `python tests/validate_config.py` | Test output |
| **C1: roots absent from workspace** | C | `ls -la` of all three old paths | `ls` output | Operator log |
| **C2: isolation probes re-derived** | C | O3-ISO-001..004 pass (raw write DENIED) | `pytest -k "O3-ISO-001 or O3-ISO-002 or O3-ISO-003 or O3-ISO-004"` | Test output |
| **C3: channeled writes work** | C | O3-ISO-005 pass (IPC writes succeed) | `pytest -k O3-ISO-005` | Test output |
| **C4: no in-workspace mirror** | C | O3-ISO-006 pass | `pytest -k O3-ISO-006` | Test output |
| **C5: full suite** | C | All 8 test categories + G10 + validate_config + phase5_security + authorization + resilience + g13 | `pytest tests/g10/ tests/phase5_security/ tests/authorization/ tests/resilience/ tests/g13/ -q` | Test output |
| **C6: full regression** | C | `pytest tests/ -q` | All green (or documented pre-existing failures) | Test output |
| **C7: residual re-derived** | C | Updated residual record per root | Document read | `docs/phase-5/security/g10/o3/final/` |
| **C8: monitored period** | C | 30 min of normal operation | No anomalies detected | Operator log |
| **C9: honesty tests** | C | O3-HON-001..005 pass | `pytest -k "O3-HON"` | Test output |
| **H5: G10 closure decision** | Post | Closure record signed by Human | Signed document exists | `docs/phase-5/security/g10/o3/final/0005-o3-closure-record.md` |

### 2.2 Evidence integrity rules

1. **Every test output must be recorded with a timestamp** and the exact command used. Use `tee` to capture output to a file.
2. **Every file hash must be recorded in a MANIFEST.sha256** and verified with `sha256sum -c`. No manual checksum transcription.
3. **Every operator log entry must include** the date, the operator's identity, the exact command, and the exit code/output.
4. **No step may be skipped or inferred.** If a step's evidence cannot be produced, the step is not complete.
5. **Historical evidence is preserved.** The pre-O3 state (V1 direct-write) is backed up and never overwritten. The current G10 OPEN/BLOCKING records remain in the closure matrix.

### 2.3 Evidence location map

| Evidence type | Location |
|---|---|
| Approval records | `docs/phase-5/security/g10/implementation/backups/o3-pre/` |
| Pre-change backups | `docs/phase-5/security/g10/implementation/backups/o3-pre/` |
| Operator logs | `/var/log/dsh-registry-writer/` (or operator's designated log path) |
| Test output (acceptance) | `/tmp/o3-acceptance-*.txt` (or CI artifact store) |
| Test output (regression) | `/tmp/phase5-regression-*.txt` |
| SHA-256 manifests | `docs/phase-5/security/g10/implementation/backups/o3-pre/MANIFEST.sha256` |
| Daemon health/audit logs | `journalctl -u dsh-registry-writer.service` |
| Per-root residual record | `docs/phase-5/security/g10/o3/final/` (updated during Phase C) |
| G10 closure record | `docs/phase-5/security/g10/o3/final/0005-o3-closure-record.md` (post-H5) |

---

## 3. Summary: the complete execution path

```
                            ┌─────────────────────┐
                            │  H3 + H4 APPROVED   │
                            │  (Human decision)    │
                            └───────┬─────────────┘
                                    │
                            ┌───────▼─────────────┐
                            │  P1–P5 PROVISIONED  │
                            │  (user, root, unit,  │
                            │   secret, group)     │
                            └───────┬─────────────┘
                                    │
                            ┌───────▼─────────────┐
                            │  DAEMON IMPLEMENTED  │
                            │  + acceptance suite  │
                            │  (throwaway temp)    │
                            └───────┬─────────────┘
                                    │
                            ┌───────▼─────────────┐
                            │  PHASE A: PREPARE    │
                            │  (deploy alongside,  │
                            │   copy data, verify, │
                            │   shadow mode,       │
                            │   pre-change backup) │
                            └───────┬─────────────┘
                                    │
                            ┌───────▼─────────────┐
                            │  FREEZE: STOP WRITES │
                            └───────┬─────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  PHASE B: SWITCH       │
                        │  (flip paths, remove   │
                        │   direct-write, remove │
                        │   roots from workspace)│
                        └───────────┬───────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │  VERIFY: single-writer, no    │
                    │  dual-window, chain continuity │
                    └───────────────┬───────────────┘
                    ┌───────────────▼───────────────┐
                    │  PASS? → RESUME writes        │
                    │  FAIL? → ROLLBACK (0004 §2)   │
                    └───────────────┬───────────────┘
                                    │
                            ┌───────▼─────────────┐
                            │  PHASE C: VERIFY     │
                            │  (isolation probes,  │
                            │   full suite, full   │
                            │   regression,        │
                            │   re-derive residual)│
                            └───────┬─────────────┘
                                    │
                            ┌───────▼─────────────┐
                            │  H5: G10 CLOSURE?    │
                            │  (Human decides)     │
                            └───────┬─────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  YES → RECORD CLOSURE │
                        │  NO  → ROLLBACK       │
                        │        (0004 §2)      │
                        └───────────────────────┘
```

---

*Status: GATE DEFINITION + EVIDENCE MATRIX (items 9–10). G10 closure gate defined as the six-condition Human decision (C1–C6 / H5). Evidence matrix covers 30+ steps across all phases with exact verification commands and recorded locations. No closure is claimed. G10 remains OPEN / BLOCKING. No evidence was generated this session beyond the current-state probes in `0001` §3. Production remains BLOCKED by non-G10 conditions regardless of G10 closure.*