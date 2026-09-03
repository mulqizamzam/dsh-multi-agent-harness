# G10 O5 Application Record — Remove `write`/`edit` from Somad and Nova (Containment Only)

- **Milestone**: Phase 5 / Session A — G10 O5 CONTAINMENT IMPLEMENTATION
- **Decision**: **APPROVE O5** (Human-approved D4/D7 composition exception, ADR 0001 Decision 4/7 — applied as a containment step). O3 (dedicated registry/audit writer) is **HOLD**.
- **Status**: **O5 APPLIED** — containment by surface reduction. **G10 remains OPEN / BLOCKING for production; NO closure of prevention is claimed.**
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Supersedes**: `0001-o5-o3-implementation-plan.md` §1 actor set (pre-O5 snapshot) for the *current* state; the plan remains the historical planning artifact.
- **Companion**: `0001-o5-o3-implementation-plan.md` (plan) · `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` (decision record) · `docs/phase-5/security/g10/0001-g10-filesystem-isolation-assessment.md` (Session C) · `docs/phase-5/final/0001-security-closure-matrix.md` (G10 row, blocker B5) · `docs/phase-5/final/0002-g10-formal-residual-proof.md`.

---

## 1. What O5 does (and does NOT do)

| | |
|---|---|
| **Applies** | Removes `write` and `edit` from the DSH `toolFilter.allow` of `somad` and `nova` in mapping, instances, policies, and the live `cordis.patch.yml`. |
| **Effect** | Raw-write actor set **shrinks from `{zeko, cto, somad, nova}` to `{zeko, cto}`**. Somad/Nova become read-only at the DSH tool level; their draft/manuscript content is channel-routed (orchestrator persists via `write_through`, which is already gated). |
| **Does NOT** | Close G10, change the sandbox, add per-path/per-agent isolation, protect `state/registry`/`audit` from `{zeko, cto}`, alter the residual proof for the two remaining actors, change any authority semantics, or change any other role. **G10 remains OPEN / BLOCKING for production.** |
| **Character** | **Containment by surface reduction** (final/0001 §2.4), not hard isolation. |

---

## 2. Files changed (exact, applied together in one step for consistency)

| # | File | Change |
|---|---|---|
| 1 | `config/role-preset-mapping.yaml` | `roles[].somad.tool_filter.allow` and `roles[].nova.tool_filter.allow` — removed `edit`, `write`; `notes` updated to channel-routed. |
| 2 | `config/tool-subagent-instances.yaml` | `insert_draft[].tool-subagent-somad.config.toolFilter.allow` and `...tool-subagent-nova...` — removed `edit`, `write`. |
| 3 | `agents/somad/policy.yaml` | `tool_filter.allow` — removed `edit`, `write`; comment + `notes` updated (channel-routed drafting). |
| 4 | `agents/nova/policy.yaml` | `tool_filter.allow` — removed `edit`, `write`; comment updated (channel-routed manuscript work). |
| 5 | `$DSH_HOME/profiles/web/cordis.patch.yml` (**live enforcement point**, outside workspace) | `tool-subagent-somad` and `tool-subagent-nova` rows — removed `edit`, `write` from `toolFilter.allow`. |

**Not changed by O5:** `config/permissions.yaml`, `control/`, `orchestrator/`, `state/`, `audit/`, `schemas/`, DSH core/presets/session policy, `agents/zeko/`, `agents/cto/`, all other role allow/deny entries, persona/provider/backgroundMode/maxDepth, sandbox/approval intent.

---

## 3. BEFORE state — backup, SHA-256, concurrent-modification detection

**Backup location:** `docs/phase-5/security/g10/implementation/backups/o5-pre/` (byte-for-byte copies + `MANIFEST.sha256`).

**Pre-O5 SHA-256 (from `MANIFEST.sha256`, pre-application):**

| File | SHA-256 (pre-O5) |
|---|---|
| `config/role-preset-mapping.yaml` | `d09418aeeb0ebc58dba9769ea554733486b4ffe6e1af897103217754b291abfd` |
| `config/tool-subagent-instances.yaml` | `360d9e405c013d3c8201513e4fd0d4951cd37ecae7f2ac05e217129d4f341103` |
| `agents/somad/policy.yaml` | `54f111860ec9a311dad179ed87aac34f90434f0d18fcbeec6f676a78fb287681` |
| `agents/nova/policy.yaml` | `e470a4ba04f81857fef38f4cae230136ca5b793d8c7cd5fbeb9fac71838b2b18` |
| `cordis.patch.yml` (live) | `d88956c3b30d9cc6a96f9a8adb91f17b9512c0020fec5669fe549837bb5896ae` |

**Post-O5 SHA-256 (current, recorded after application):**

| File | SHA-256 (post-O5) |
|---|---|
| `config/role-preset-mapping.yaml` | `1826c6f8a3fc7c7b624410f67e1279bb9156bc42c9dcce6cc5c5665fa8f3c776` |
| `config/tool-subagent-instances.yaml` | `be960cbfb0ac40cae3ba686b477bb531865dcb9d93999ca66670ae18cdd8dc69` |
| `agents/somad/policy.yaml` | `af08ca0713431c0e51ed6237c9bd5488c93066826edef66a9fc0e43f0fd20f80` |
| `agents/nova/policy.yaml` | `ed0d762986f53c0ccc596627cea69372b16b8d67190b98d4fe0b256b2881d712` |
| `cordis.patch.yml` (live) | `847ab951b6e6a4cd3e885ec55be935e03fa826a47173f17aaeeb5a2e4db74195` |

**Concurrent-modification note (honest):** a parallel session was observed modifying O5-adjacent files during this application (timestamps around 17:43–17:49, incl. the plan doc header and the O5 test assertions). The concurrent edits are **consistent** with this record's post-O5 state — re-hashed config/policy/live-patch values match exactly, and all validation below passes. No divergence was found at the time of recording.

---

## 4. AFTER verification (all passed)

| Invariant | Result |
|---|---|
| `mapping == policy == instance` | **PASS** — `tests/validate_config.py` (194 checks) |
| `allow ∩ deny == ∅` (all 7 roles + orchestrator) | **PASS** — `validate_config` + `tests/g10/` |
| Somad/Nova no `write`/`edit` in allow | **PASS** — new guard `test_o5_somad_nova_deny_write_edit` (`tests/g10/test_role_restrictions.py`) |
| Raw-write actor set == exactly `{zeko, cto}` | **PASS** — `tests/g10/` + `tests/g10/final/` |
| All 7 roles valid (resolution, toolFilter, prohibited tools, delegation denial) | **PASS** — `tests/phase5_role_validation/` (28) |
| Live patch `cordis.patch.yml` matches mapping for all 7 `subagent_<id>` rows | **PASS** — scripted equality check |
| Zeko/CTO unchanged (still `bash`+`write`/`edit`) | **PASS** — `tests/g10/`, `tests/live_dsh/`, `tests/authorization/` |
| Read-only roles (cfo/kai/badsector) unchanged | **PASS** |
| No new capability or authority introduced | **PASS** — diff shows removals only (`write`/`edit` from somad/nova allow + notes); nothing added anywhere |
| G10 remains OPEN / BLOCKING | **PASS** — no closure claim in any doc or test (honesty guards) |

**Test battery (run this session):**

| Suite | Result |
|---|---|
| `tests/validate_config.py` | 194 passed, 0 failed |
| `tests/g10/` (incl. new O5 guard) | 78 passed |
| `tests/phase5_role_validation/` | 28 passed |
| `tests/live_dsh/` | 75 passed |
| `tests/authorization/` | 178 passed |
| `tests/phase5_security/` | 14 passed |
| `tests/resilience/` | 45 passed, 1 skipped |
| `tests/g13/` | 107 passed |
| `tests/unit/test_config.py` | 5 passed |

**Test files updated for O5** (assertions moved to the post-O5 set):
- `tests/g10/test_role_restrictions.py` — actor-set assertion → `{zeko, cto}`; new O5 guard added; docstring updated.
- `tests/g10/final/test_g10_final_decision.py` — actor-set assertion → `{zeko, cto}`.
- `tests/g10/planning/test_o5_o3_planning.py` — post-approval honesty guards (plan doc references this application record; actor set post-O5).
- `tests/phase5_role_validation/harness.py` — `WRITE_CAPABLE_ROLES = ("zeko", "cto")`.
- `tests/live_dsh/test_role_adapters.py` — write-capable role list → `("cto", "zeko")`.
- `tests/authorization/test_authority.py` — spot-checked write roles → `("zeko", "cto")`.

---

## 5. Rollback (file-level; the project is NOT a git repository)

Restore order (reverse of apply), each from `backups/o5-pre/`:
1. `$DSH_HOME/profiles/web/cordis.patch.yml` (live) → restore from backup.
2. `agents/{somad,nova}/policy.yaml` → restore.
3. `config/{role-preset-mapping,tool-subagent-instances}.yaml` → restore.
4. Reload/restart the DSH session (stand-alone mounts drop on reload).
5. Verify: `write`/`edit` re-exposed for somad/nova at the instance level; `tests/validate_config.py` passes; `tests/g10/` actor-set tests pass again with `{zeko, cto, somad, nova}`.
6. Audit the rollback event.

**Reversibility: HIGH** (a reversible config/policy/composition change).

---

## 6. Honesty statement

1. **O5 is containment only.** It shrinks the raw-write actor set to `{zeko, cto}`; it does NOT close G10, does NOT hard-isolate any path, and does NOT change the sandbox.
2. **G10 remains OPEN / BLOCKING for production.** No prevention closure is claimed anywhere in this record, the plan, the final decision record, or any test.
3. **No new capability or authority was introduced** — the diff is removals only.
4. **The live enforcement point** (`$DSH_HOME/profiles/web/cordis.patch.yml`) was changed and verified byte-consistent with the config; a session reload is required for the change to take effect in live resolution.
5. **No production deployment was started.** The residual `{zeko, cto}` retains raw write in principle (contained by detection at the project layer).

---

*Status: O5 APPLIED (containment only). G10 remains OPEN / BLOCKING. Raw-write actor set: `{zeko, cto, somad, nova}` → `{zeko, cto}`. O3 HOLD. No closure of prevention claimed.*
