# Human Answerer + Approval Path Readiness — Exact Minimum Operator Action

- **Milestone**: Phase 5 / Session B — HUMAN ANSWERER + APPROVAL PATH READINESS
- **Status**: ASSESSED (read-only verification; **no session-policy change, no DSH
  change, no production-config edit, no answerer invented, no HIGH-risk action,
  no L3 run**) — **§5.3 superseded by `0002-approval-path-correction.md`**
  (probe correction applied in this session)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope (write-only)**: `docs/phase-5/environment/approval/` +
  `tests/l3_runner/environment/approval/`. Everything else read-only.
- **Companion**: `docs/phase-4/0003-approval-readiness.md` ·
  `docs/phase-5/environment/0001-environment-readiness-spec.md` (§3) ·
  `docs/phase-5/environment/final/0001-operator-infrastructure-checklist.md`
  (items 3–4) · `tests/environment/preflight.py` (ENV-APPROVAL-1) ·
  `tests/l3_runner/environment/readiness.py` (L3ENV-ANS-1/2) ·
  DSH checkout `packages/interaction/user-approval/` +
  `packages/host/apiproxy/` + `packages/bundle/{base,web-app}/cordis.patch.yml`.

---

## 1. What this document answers

*Is the `ask` approval path usable in the current environment, and what is the
exact minimum operator action required to make it usable?* The answer, with
source evidence: the **DSH approval seam is composed and the effective policy is
`ask`**; in a **web GUI session** a live Human answerer **exists by composition**
(the browser's `ui-user-questions` + `ui-conversation` ApprovalPanel answer the
`approval/request` waterfall). The project's *probe* currently reports the
answerer as **absent** because it keys off a project-side convention
(`DSH_APPROVAL_PROMPTS_DISABLED`) that DSH never reads, and scans
`$DSH_HOME/profiles/` for marker rows that the bundle-composed answerer does
not create. The minimum operator action is therefore **not** "enable prompts"
(they are not disabled at the DSH layer); it is to **verify the browser is
connected and attached to the session** (or, for headless/automated use, to
compose an explicit `approval/request` answerer row).

---

## 2. Current state (verified this session, read-only)

| Fact | Value | Source |
|---|---|---|
| File sandbox policy | `workspace-write` | runtime-context snapshot (current session) |
| Approval policy | `ask` | runtime-context snapshot; session event `approval/policy` → `{"policy":"ask"}` |
| `DSH_PERMISSION_MODE` | unset | `env` |
| `DSH_APPROVAL_PROMPTS_DISABLED` | **unset** (and **never read by DSH**) | `env`; negative grep over the DSH checkout |
| DSH approval service | composed in the base bundle (`- id: approval`, `@deepseek-ai/dsh-user-approval`) | `packages/bundle/base/cordis.patch.yml:187–191` |
| Approval policy derivation | `policy: (DSH_PERMISSION_MODE ?? 'workspace-write') === 'danger-full-access' ? 'never' : 'ask'` | `packages/bundle/base/cordis.patch.yml:190` |
| Web answerer (browser half) | composed: `ui-user-questions` (`@deepseek-ai/dsh-client-ui-user-questions`) and `ui-conversation` (ApprovalPanel) | `packages/bundle/web-app/cordis.patch.yml:209–210, 291–293` |
| `ask_user_question` tool | routed through `ctx.userQuestions.ask` → browser composer | `packages/interaction/tool-ask-user/src/index.ts` |
| Approval outcome vocabulary | `allowed-once \| rejected \| cancelled \| unavailable` | `packages/interaction/user-approval/README.md` |
| Audit pair | `approval/asked` + `approval/decided` (log-only; model sees only the tool outcome) | `packages/interaction/user-approval/src/index.ts` |
| Session type | **web GUI** (`DSH_WEB_URL=http://127.0.0.1:13080`; web server responding HTTP 200) | `env`; live probe |
| Project probe `ENV-APPROVAL-1` / `L3ENV-ANS-1` | currently reports **FAIL/absent** | `tests/environment/preflight.py:126–138`; `tests/l3_runner/environment/readiness.py:205–220, 444–468` |

**Bottom line**: the *mechanism* for `ask` is present and live in a web session;
the *probe* under-detects it. The remainder of this document gives the exact
operator action and the exact evidence required to confirm `ask` usability
without changing session policy or DSH.

---

## 3. How `ask` resolves today (exact flow)

1. A consequential/HIGH action calls the DSH approval seam (`ctx.approval.request`)
   or the project gate's `ask` backstop.
2. `ApprovalService.request()` applies the effective policy. Effective policy is
   the last `approval/policy` event, falling back to service config — the base
   bundle composes `policy: 'ask'` unless the permission mode is
   `danger-full-access` (which yields `never`). Verified this session:
   `approval/policy` event = `ask`.
3. Under `ask`, the service dispatches the `approval/request` **waterfall** to
   composed answerers. In a web session the answerer is the browser:
   - `apiproxy` listens on `approval/request` and forwards a frame to the client
     (`packages/host/apiproxy/src/api-proxy.ts:1363–1415`);
   - `ui-conversation`'s `ApprovalPanel` renders a "Waiting for approval" card
     with refuse/allow actions (one-shot; answer → `approval/resolved` →
     outcome);
   - `ui-user-questions` answers `ask_user_question` calls through the composer.
4. The first answer occupies the decision slot. Missing/throwing/non-owning
   answerer → `unavailable` (fail-closed). The audit pair
   `approval/asked`+`approval/decided` is appended (log-only).

**Fail-closed rule (unchanged):** with no answering surface reachable, `ask`
resolves `unavailable` → DENY + escalate. This is the correct safety default and
is preserved in every configuration.

---

## 4. READY / BLOCKED

| Scope | Readiness | Why |
|---|---|---|
| `ask` usable in a **web GUI session with the browser attached** | **READY (by composition)** | approval service composed (`policy: ask`); browser answerer composed (`ui-user-questions` + `ui-conversation` ApprovalPanel); session is web GUI |
| `ask` usable in a **headless / automated / unattached session** | **BLOCKED** | no composed answerer reaches a Human; `approval/request` waterfall has no answering surface → `unavailable` (fail-closed) |
| **Interactive / HIGH-risk execution** | **BLOCKED at the project level** | independent verifier for HIGH-risk `independent` categories (VER-2) not built (unchanged, out of this task's scope) |
| **L3 Human-signed plan** | **BLOCKED** | requires a real Human signoff mechanism + durable identity + pre-commit oracle (unchanged, out of scope here) |

**Precision:** this task verifies the *approval path*, not the L3 claim path. The
approval path is **READY in the current web session** and **BLOCKED only when no
Human surface is attached**.

---

## 5. Minimum operator action (exact)

### 5.1 Web GUI session (the current environment)

1. **Verify the browser is connected to the session** (the web app is open on
   `http://127.0.0.1:13080` and the session is the active one). The Human at the
   GUI is the live answerer; an approval request surfaces as the amber
   "Waiting for approval" panel.
2. **No policy edit is required**: `ask` is already the effective policy
   (verified via the `approval/policy` session event). Do **not** set
   `DSH_APPROVAL_PROMPTS_DISABLED` (DSH never reads it) and do **not** edit
   production configuration.
3. **Confirm with one benign approval-gated interaction** (optional): trigger a
   single approval-gated action with a Human present and observe the
   `ApprovalOutcome` (`allowed-once`/`rejected`) and the audit pair.

### 5.2 Headless / automated session (operator/operator-infra)

1. **Compose an `approval/request` answerer** in the session composition — e.g.
   a terminal answerer row that returns a decision for owned agents (the ACP
   automation bridge provides one-shot machine decisions for sessions it owns;
   `packages/interaction/user-approval/README.md`).
2. OR **pre-record a structured `approval-<id>` reference** in the delegation
   registry for each approval-dependent action (single-writer channel, ADR 0002),
   matching the delegation record at execution-time re-check
   (`control/authority.py::_check_approval`). The reference is generated ONLY by
   the Human (or a documented Human-authorized process) — never by an agent,
   workflow output, audit entry, or model text.
3. **Keep the policy `ask`** (the DSH-layer backstop). Do not set
   `DSH_PERMISSION_MODE=danger-full-access` (that flips the policy to `never` and
   removes the fail-closed escalation).

### 5.3 Project probe correction (applied — targeted approval-probe repair)

The project's detection in `tests/environment/preflight.py` `_answerer_available`
and `tests/l3_runner/environment/readiness.py` `_answerer_available` previously
keyed off the obsolete `DSH_APPROVAL_PROMPTS_DISABLED` (DSH never reads it) and
a `$DSH_HOME/profiles/*` marker scan. The targeted approval-probe repair
(referenced in 0002-approval-path-correction.md §5a) wired the corrected detector
into the readiness probe. The obsolete detection is removed; the readiness probe
now accurately represents the actual DSH web approval composition.

---

## 6. Exact evidence required to confirm `ask` usability

| # | Evidence | How to obtain | Required value |
|---|---|---|---|
| 1 | Effective approval policy | session event `approval/policy` (or runtime-context snapshot) | `"ask"` |
| 2 | Approval service composed | DSH base bundle row `- id: approval` (`@deepseek-ai/dsh-user-approval`) | present |
| 3 | Answerer surface composed | web-app bundle rows `ui-user-questions` + `ui-conversation` | present (web session) |
| 4 | Browser attached to the session | web server reachable (`HTTP 200`) + active session; Human present at the GUI | connected |
| 5 | Approval outcome capturable | one benign approval-gated interaction → `approval/decided` event with outcome in `{allowed-once, rejected, cancelled}` | audit pair recorded |
| 6 | Audit pair present | session log contains `approval/asked` + matching `approval/decided` | 1:1 pair |
| 7 | Fail-closed when no answerer | headless path: `approval/request` waterfall with no owner → `unavailable` | `unavailable` (never implicit allow) |

**No evidence is fabricated.** The evidence rows above are the *minimum* a Human
needs before relying on `ask`; the probe records what is observed, never invents
an answerer.

---

## 7. ROLLBACK

- **Nothing is changed by this task** (read-only verification; the two write-only
  targets are a document + a test module under `tests/l3_runner/environment/approval/`).
- If the approval-path test module is later removed: delete
  `tests/l3_runner/environment/approval/`; no other file is affected.
- If an operator later composes an answerer (headless path) and must revert:
  remove the composed answerer row and reload the session; the policy stays
  `ask` and the fail-closed `unavailable` default returns.
- **Reversibility: HIGH** — no session-policy change, no DSH change, no
  production-config change is made or required.

---

## 8. Honesty statement

1. **No session-policy change, no DSH change, no production-config edit.** The
   write-only targets are `docs/phase-5/environment/approval/` and
   `tests/l3_runner/environment/approval/`.
2. **No Human answerer is invented.** The web-session answerer is *observed* to
   be composed (bundle rows + live session); a headless session reports BLOCKED,
   never a fake answerer.
3. **No HIGH-risk action is executed and no L3 is run.**
4. **The probe gap is reported, not silently fixed**: the detection modules in
   `tests/environment/` and `tests/l3_runner/environment/` were NOT modified
   (outside the write-only targets); the recommended correction is recorded in
   §5.3.
5. **All evidence above is from the DSH 0.1.1-rc.2 checkout (read-only) or the
   live session log; nothing is assumed.**

---

*Status: ASSESSED. `ask` is usable in the current web GUI session (approval
service composed, policy `ask`, browser answerer composed). Headless sessions
remain BLOCKED (fail-closed `unavailable`). Minimum operator action for the web
session: verify the browser is attached (no policy/config edit). For headless:
compose an `approval/request` answerer or pre-record `approval-<id>` references.
No policy change, no DSH change, no answerer invented, no HIGH-risk action, no L3.*

---

## UPDATE 2026-10-09 — re-verification against DSH 0.2.0-rc.2

This repository was re-verified against the current DSH checkout
(`0.2.0-rc.2`; the pin above is `0.1.1-rc.2`, and the README requires
re-verification for later releases). Three composition facts changed, and the
probe plus its tests were corrected to the observed state — no claim was
weakened and nothing was faked ready:

1. **The forwarding row changed.** `@deepseek-ai/dsh-host-apiproxy` no longer
   exists. The Host→browser forwarding row is now
   `@deepseek-ai/dsh-api-remotes` (the two-sided BFF for Host Remote
   capabilities), and the browser approval UI is the dedicated
   `@deepseek-ai/dsh-client-ui-approval` package, not the ui-conversation
   ApprovalPanel. `answerer_surface_composed()` now detects the current
   generation (forwarding + approval presentation + question surface +
   conversation composer).
2. **The profile composition changed.** The web profile root
   (`$DSH_HOME/profiles/web/cordis.yml`) now carries the full host
   composition, so the answerer package rows appear there as well as in the
   bundles. That is a duplicate composition, not a probe gap: the probe reads
   the bundle patches as source truth and never scans the profile. The former
   "no marker row under `$DSH_HOME/profiles/`" claim is obsolete; the test
   now asserts profile rows never diverge from the bundle-composed surface.
3. **`DSH_WEB_URL` proves less than before.** A bare exported URL only proves
   a web server URL was exported to the session. The GUI answers 401 without
   the launch-token query, so "a browser answerer is attached" requires the
   tokenized URL. The ladder therefore fails closed to
   `APPROVAL_COMPOSED` in a bare-URL (headless agent) session, and tests that
   asserted the attached rung are now environment-conditional instead of
   assuming an operator session.

The fail-closed invariants are unchanged: a composed-but-unattached surface
never counts as a live Human answerer, `DSH_APPROVAL_PROMPTS_DISABLED` remains
a project-side convention DSH never reads, and no approval/signature is
invented.
