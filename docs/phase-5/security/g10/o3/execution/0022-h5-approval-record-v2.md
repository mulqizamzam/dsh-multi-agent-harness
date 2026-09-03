# G10 H5 (v2) — Human Decision Record: APPROVED against `0021`

- **Milestone**: Phase 5 / G10 — H5 HUMAN DECISION (second edition): **APPROVED**
- **Status**: **H5 = APPROVED (explicit Human decision, recorded against `0021`). G10 = CLOSED (project-layer) per the closure gate `0005` §1.2.**
- **Date**: 2026-09-01 (this session)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Decision source**: Direct Human instruction — *"H5 is explicitly APPROVED by Human against 0021."*
- **Evidence package this approval is granted against**: `docs/phase-5/security/g10/o3/execution/0021-h5-closure-package-v2-wsl-final-verification.md`
- **Supersedes**: `0016-h5-approval-record.md` — the first H5 decision, granted 2026-09-01 against `0015`. `0016` is **preserved unmodified** and is not retracted; it is superseded because the deployment it described was materially different (see §4).
- **Scope**: Record the H5 decision, update the existing G10 closure matrix, verify G10 = CLOSED, run a fresh G13 pre-gate. **No Phase B/C re-execution. No G13 scenario executed. No L3 executed. No DSH/session-policy/role change. No delegation or approval fabricated. No bridge marker set, nothing mounted. No REAL simulated. No inferred approvals.**

---

## 1. The Human decision

The Human **APPROVED H5** against the `0021` evidence package.

| # | Approved item | Basis in `0021` |
|---|---|---|
| 1 | **C1** — A+B isolation **including credential confidentiality** | §3 — 4 independent secret-read paths, socket connect, daemon-root traverse, and write probes into all 4 daemon roots, all **DENIED** to uid 1000 (the role-agent principal) |
| 2 | **C2** — `state/projects/**` extension (H4) | §4 — protected/sanctioned root wiring + daemon `project_write`/`project_read` channels; no drift |
| 3 | **C3** — complete write-path migration, direct protected writers = **ZERO** | §5 — exhaustive O3-FC-005 scan; deny-before-mutation confirmed at runtime with the file absent afterwards |
| 4 | **C4** — no silent direct-fs fallback | §6 — no `except → atomic_write` branch anywhere; live negative proof from the 19:03–20:02 daemon-unreachable window |
| 5 | **C5** — verification passes | §7 — full regression 3115 passed / 19 skipped / **0 failed**; validate-config 194/0; compileall 0 errors; live operational arm restored (operator-attested) |
| 6 | **G10 technical/prevention residual closure** (project-layer) | C1–C5 satisfied simultaneously; C6 now complete (H3 ✅ H4 ✅ **H5 ✅**) |

The Human explicitly did **NOT** approve by this decision:

| # | Not approved |
|---|---|
| 1 | G13 closure |
| 2 | L3 claim |
| 3 | production readiness |
| 4 | O4 upstream DSH capability closure |
| 5 | any DSH / session-policy / role change |

---

## 2. What this approval means (precise)

**H5 = APPROVED means** the six conditions of the G10 closure gate (`0005` §1.2) are all satisfied: C1–C5 verified by the `0021` evidence package, and C6 (H3 ✅ + H4 ✅ + H5 ✅) is now complete. The G10 **project-layer** prevention gap — a raw direct-filesystem write to `state/registry/**`, `audit/**`, or `state/projects/**` bypassing the sanctioned channel — is **closed**: the O3 daemon owns all three roots outside the workspace under a dedicated UID, the control plane reaches them only via HMAC IPC as a **separate OS principal** (`dsh-control`), no direct-fs fallback exists, fail-closed is verified, and the credential is confidential to the role-agent principal.

**H5 = APPROVED does NOT mean** the DSH-layer path-isolation gap is closed. A raw-write-capable role (`{zeko, cto}`) can still reach workspace paths via raw DSH tools in principle. That is the separately-tracked **O4 upstream DSH capability residual**, explicitly not approved here and not closed by this decision.

**H5 = APPROVED does NOT mean** production readiness. Per `0005` §1.5, G10 closure unblocks exactly one gate and is necessary but not sufficient: G13 remains OPEN/UNKNOWN, L3 remains NOT CLAIMABLE, and the D4/D7 mount and approval-answerer conditions remain unmet.

---

## 3. Pre-decision drift gate (verified before recording)

H5 must be recorded against the state `0021` actually verified. Re-probed immediately before writing this record:

| Item | `0021` baseline | At recording | Drift |
|---|---|---|---|
| Daemon | `active`/`enabled`, PID 389112, start 20:02:11, `NRestarts=0` | identical | **none** |
| Secret | `dsh-writer:dsh-control 0640`, size 65, mtime 18:53:05.300162076, inode 31422 | identical | **none** |
| Daemon root | `dsh-writer:dsh-control 0750` | identical | **none** |
| Live `socket_group` | `dsh-control` | identical | **none** |
| Group DB | `dsh:985:dsh-writer` · `dsh-writer:986:` · `dsh-control:984:dsh-control` | identical | **none** |
| uid 1000 secret read | DENIED | **DENIED** | **none** |
| uid 1000 socket connect | DENIED | **DENIED** | **none** |

**Zero drift.** The approval is recorded against the exact state that was verified.

---

## 4. Why `0016` could not simply be reused

Recorded for the audit trail, because reusing the earlier approval would have been the easy and wrong path:

1. `0016` was granted against `0015`, whose §1 host facts were **later falsified** by `0018`: `administrator ∈ dsh-writer, dsh`, so the HMAC credential was readable by every `bash`-capable role agent **at the moment that approval was given**. C1's confidentiality sub-property was not satisfied then.
2. The deployment has materially changed since: a new control-plane principal (`dsh-control` uid 997), a rotated credential, a regrouped socket and daemon root, and a new daemon process (PID 389112).
3. `0016` §1 records the explicit Human instruction *"Do not infer or fabricate additional approvals."* Carrying a prior approval forward onto a different technical state would be inferring authority from stale text.

Hence a fresh Human decision was required, and this record documents that decision — not a re-derivation of the old one. `0016` remains valid as the historical record of the first decision.

---

## 5. Closure verification (minimal, post-decision — Phase B/C NOT repeated)

No drift was detected in code, config, or migration state, so per `0005` §1.4 and the task constraint, Phase B/C was not re-executed.

| # | Check | Result |
|---|---|---|
| 1 | Daemon active/enabled | ✅ PID 389112, `NRestarts=0` |
| 2 | Credential confidentiality (uid 1000) | ✅ DENIED via `cat`, `dd`, `sha256sum`, Python `open()` |
| 3 | Socket unreachable (uid 1000) | ✅ `PermissionError`; daemon-root traverse DENIED |
| 4 | Daemon roots unwritable (uid 1000) | ✅ all 4 DENIED |
| 5 | Direct protected writers | ✅ **ZERO** (O3-FC-005 static scan) |
| 6 | Deny-before-mutation | ✅ all 3 protected roots DENIED, file absent after; non-protected control ALLOWED |
| 7 | O3 daemon suite | ✅ 50 passed |
| 8 | G10 suite | ✅ 339 passed, 4 skipped |
| 9 | phase5_security | ✅ 14 passed |
| 10 | validate-config | ✅ 194 passed, 0 failed |
| 11 | compileall | ✅ 0 errors |
| 12 | Rollback readiness | ✅ `o3-pre` manifest 5/5 hashes VERIFIED |

Full evidence, including the F-SELF / F-OP evidence-class split, is in `0021`.

---

## 6. G10 closure record (per `0005` §1.3)

- **Date of decision**: 2026-09-01
- **Decision maker**: Human (direct instruction, this session)
- **Six conditions**: C1 ✅ · C2 ✅ · C3 ✅ · C4 ✅ · C5 ✅ · C6 ✅ (H3 + H4 + H5) — evidence per §1
- **Per-root residual after O3**: `state/registry/**` ✅ closed · `audit/**` ✅ closed · `state/projects/**` ✅ closed (H4 extension) — all owned by the daemon outside the workspace
- **Accepted residuals**: T4, T5, T8 recorded as accepted (not regressions), per FINAL 0002
- **G10 matrix row re-derived**: updated to **CLOSED** in `docs/phase-5/final/0001-security-closure-matrix.md` §1, with roll-up, §5 condition 4, §6 blocker B5, §7 item 4, and Addendum E
- **Production still BLOCKED**: G10 closure is necessary but not sufficient. G13 OPEN/UNKNOWN; L3 NOT CLAIMABLE; B1 (D4/D7 mount), B2 (approval answerer), B3 (same-UID), B4 (live driver), B6 (G13), B7 (VER-2), B8 (session-policy guard) all remain
- **No earlier closure claim overwritten**: `0015`, `0016`, `0018`, `0019`, `0020`, `0021` are all preserved unmodified; supersession is recorded explicitly

---

## 7. Known consequence: stale G10-OPEN assertions in the test suite

Recorded rather than silently resolved, because it touches tests.

Several tests encode *"G10 is OPEN"* as a **state fact**, written when that was true:

| Location | Assertion | Effect of this closure |
|---|---|---|
| `tests/g13/gate/test_g13_live_recheck.py:312` (`test_axis_11_g10_open_blocking`) | requires the literal `**OPEN**` inside the G10 row of the closure matrix | **FAILS** — the row now reads `**CLOSED**` |
| `tests/g13/gate/test_g13_live_recheck.py:82` | `g10_blocking = True` hardcoded in `recheck_verdict()` | still *passes* mechanically, but now reports G10 as blocking when it is closed — **factually stale** |
| `tests/phase-5/final/audit/test_audit_consistency.py` (`TestG10VerdictConsistency`) | `G10.*OPEN\|G10.*BLOCKING` must match a line in 4 docs | continues to pass via preserved **historical** text (Addendum A) — not a live-state assertion |

`test_axis_11_g10_open_blocking` is an honesty gate whose failure message is *"G10 no longer recorded as OPEN in closure matrix — re-assess"*. It fired correctly earlier in this session when the document was ahead of verified state. It now fires because an authorized Human decision moved the state, and the assertion encodes the superseded state.

**No test has been modified, weakened, skipped, or deleted.** Updating a stale state-fact assertion is a legitimate action — it is not the same as weakening a security assertion — but it is a **test modification**, which was outside the authorization for this step. It is reported as a blocker in the accompanying status report, with the exact remedy, for explicit authorization.

---

## 8. Honesty statement

1. **This approval was given by the Human, not inferred.** The instruction was explicit and is quoted verbatim in the header. No approval was self-granted or fabricated.
2. **No delegation, approval record, signature, or provenance was fabricated.** No `approval-<id>` was invented.
3. **Zero drift was verified before recording** (§3), so the approval attaches to the state that was actually verified.
4. **Phase B/C was not repeated.** G13 scenarios were not executed. L3 was not executed. Nothing was mounted; no bridge marker was set. Nothing REAL was simulated.
5. **The `dsh-control` PASS results underpinning C5's live arm remain operator-attested**, not independently re-derivable from inside the sandbox — that impossibility is precisely what makes C1 pass. This limitation was stated in `0021` §2/§9 before the decision and is not re-characterised now that the decision is favourable.
6. **The regression consequence in §7 is disclosed, not hidden**, and no test was touched to make the result look clean.
7. **G13 remains OPEN/UNKNOWN. L3 remains NOT CLAIMABLE. O4 remains open. Production readiness remains NOT DECLARED.** No DSH core, session-policy, or role change was made.

---

*Status: **H5 = APPROVED** (explicit Human decision, 2026-09-01, recorded against `0021`). C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ✅ C6 ✅ — all six closure-gate conditions satisfied. **G10 = CLOSED (project-layer).** Zero drift verified pre-recording. Phase B/C not repeated. O4 upstream DSH capability residual NOT closed — separately tracked. G13 not executed (OPEN/UNKNOWN). L3 not executed (NOT CLAIMABLE). Production readiness NOT declared. Known consequence: one stale G10-OPEN honesty assertion now fails (§7) — disclosed, no test modified.*
