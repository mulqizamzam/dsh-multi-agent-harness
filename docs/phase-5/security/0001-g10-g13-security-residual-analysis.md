# Phase 5 / Session G — Security Residual Analysis (G10 + G13)

- **Milestone**: Phase 5 / Session G — SECURITY RESIDUAL ANALYSIS
- **Status**: ANALYSIS (verification + residual documentation; **no new security claim, no DSH change, no path-isolation closure claimed**)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/security/` + `multi-agent-harness/tests/phase5_security/` (write-only).
- **Companion**: `docs/phase-4/0005-production-readiness-assessment.md` (G10/G13, §5, §7.6) · `docs/phase-5/0001-security-hardening-analysis.md` (Session G G10 root doc) · `docs/adr/0002-registry-protection-mechanism.md` · `docs/security/0001..0003` · `tests/adversarial/`.

---

## 1. G10 — DSH path-isolation limitation

### 1.1 The residual (proven OPEN)

A bash-capable role (Zeko, CTO, Somad, Nova) can, in principle, reach a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a **raw DSH `bash`/`edit`/`write` tool call** that bypasses the project write channel. The project execution gate (`control/execution_gate.py`) governs writes that **route through the project channel**; it does not intercept raw tool calls.

Root causes (documented in `docs/phase-5/0001-security-hardening-analysis.md` §1.2, ADR 0001/0002):
1. **Sandbox is per-session, not per-agent** (ADR 0001 Decision 1) — every child shares the orchestrator session's `workspace-write` sandbox.
2. **toolFilter is tool-level, not path-level** (ADR 0002) — `bash`/`edit`/`write` can reach any path inside the sandboxed workspace.
3. **The execution gate is a code channel, not a DSH interception point** (ADR 0002).

### 1.2 Can it be closed WITHOUT DSH capability changes? — VERDICT: PARTIAL

From the actual DSH 0.1.1-rc.2 capabilities (verified in the DSH checkout, read-only):

| Option | DSH capability change? | What it would require | Status |
|---|---|---|---|
| **O5 — reduce bash surface** (remove `bash` from Somad/Nova allow sets) | **NO** (config change only) | Reopen the D4/D7 composition exception (Human approval); force writes through the project channel | **CLOSABLE-WITHOUT-DSH-CHANGE for non-shell roles** — but Zeko/CTO legitimately need bash for ops/engineering; removing bash from them is a capability regression |
| **O3 — dedicated out-of-process registry process** | **NO** (new process) | Separate process with its own workspace root; only that process writes the registry | **CLOSABLE-WITHOUT-DSH-CHANGE** (high effort; ADR 0002 consequence 4) |
| **O2 — registry outside workspace** | **NO** (config/path relocation) | Move registry to a path outside the sandboxed workspace | **CLOSABLE-WITHOUT-DSH-CHANGE** (medium effort; rejected for V1) |
| **O4 — per-agent sandbox** | **YES** (DSH capability) | Per-agent sandbox differentiation in DSH | **NOT CLOSABLE WITHOUT DSH CHANGE** — not available in 0.1.1-rc.2 |

**Conclusion**: The residual is **partially closable without DSH changes** — via O5 (for non-shell roles), O3, or O2 — but **none is applied in this session** (each requires a Human-approved composition change or new process; no silent change is permitted). The **prevention** gap at the DSH layer for bash-capable roles cannot be fully closed without either removing bash from those roles (O5, a capability regression) or adding a DSH capability (O4, not available). **Detection** at the project layer (L1 gate + append-only + hash-chain + CAS) remains the containment for V1.

### 1.3 What G10 is / is not

- **IS**: an analysis of whether the residual can be closed without DSH capability changes (answer: partial, with named options).
- **IS NOT**: a claim that path isolation is closed, a DSH change, a config change, or a silent mitigation.

**G10 verdict: OPEN** (partial closability; nothing applied; prevention for bash-capable roles remains a DSH-capability gap).

---

## 2. G13 — Prompt-injection / external-content verification

### 2.1 Entry points × existing defenses (verified)

| Entry point | Defense (verified deterministic) | Test |
|---|---|---|
| Child structured output (`TaskResult`) | Collected as DATA; schema-validated; role identity checked; never grants authority | `test_external_content_data.py::TestExternalContentCannotGrantAuthority` |
| Child text output | Not used as a gate input; authority is read from the registry, not child prose | (covered by authority gate tests) |
| `extra_context` passed to a child | Authority-shaped keys stripped + recorded (`build_task_context`, THREAT-020) | `test_authority_keys_removed_from_context` |
| Message payloads | `assert_no_authority_in_payload` refuses authority-bearing bodies | `test_assert_no_authority_in_payload` |
| Subdelegation attempt | DENY BY DEFAULT by actor (DLG-003), regardless of content | `test_specialist_cannot_delegate_even_with_claim` |
| Reported SUCCESS | Not verification — COMPLETE requires observed outcome (THREAT-016/AUTH-INV-15) | `test_claim_without_observed_outcome_no_complete` |

### 2.2 What is verified vs unverified

**Verified (deterministic, this session, 8 tests in `tests/phase5_security/`):**
- external content is treated as DATA (authority keys stripped, payloads refused);
- a malicious child result cannot grant authority, flip a gate, or escalate scope;
- subdelegation denial holds against adversarial content;
- reported success without observed outcome never reaches COMPLETE.

**Unverified (UNKNOWN, no claim):**
- live DSH child behavior under prompt-injection payloads (requires the D4/D7 mount — BLOCKED this session);
- whether DSH's own subagent driver has any content-isolation weakness beyond the adapter's enforcement (ADR 0001 UNKNOWN #1; no claim made).

### 2.3 Honesty

- **No prompt-injection claim** is made. The defenses verified are the adapter's data-not-instructions treatment; the full DSH content-isolation posture remains UNKNOWN.
- The verification is deterministic (no live mount); live injection testing is a future BLOCKED item.

**G13 verdict: OPEN** (defenses verified; full closure unverified/UNKNOWN; no claim).

---

## 3. Security test status

```text
$ .venv-tests/bin/python -m pytest tests/phase5_security/ -q
14 passed
```

Coverage: G10 negative path-isolation (raw write lands, channeled write DENIED, traversal DENIED, no closure claim) + G13 external-content-as-data (authority keys stripped, malicious result cannot grant authority, subdelegation denied, reported≠verified).

## 4. Scope check

**In scope:** `docs/phase-5/security/` (this + `0002-g13-external-content-verification.md`), `tests/phase5_security/` (additive). `docs/phase-5/0001-security-hardening-analysis.md` (G10 root) read-only.

**Not modified:** `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `config/`, `schemas/`, `tests/adversarial/`, DSH core/profile/preset/session policy. No new tools, no web_fetch, no Agent Teams.

---

*Status: ANALYSIS. G10 partial-closability documented (OPEN). G13 defenses verified (OPEN, no claim). No new security claim. No DSH or production change.*
