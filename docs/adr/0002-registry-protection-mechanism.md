# ADR 0002 — Delegation Registry Protection Mechanism (Phase 1B)

- **Status**: accepted (Phase 1B decision; resolves the open design item from security spec §11.2 / design doc §17)
- **Date**: 2026-08-29
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/`. Resolves the registry-protection open item; decides the mechanism; wires the REG-* test skeletons. Does **not** modify DSH core, profiles, or presets.
- **Supersedes / completes**: security spec §11.2 ("design-time open item: dedicated registry path + toolFilter exclusion vs registry outside agent workspace") · design doc §17 (REG-001..005) · THREAT-004/007.

---

## Context

The delegation registry is the project's **authority source**. An unauthorized write to it is a forged-authority attack (THREAT-004) that can grant an actor scope it was never given, or flip a state field into a false approval (THREAT-007).

The Phase-0/1A security documents deliberately left the **concrete protection mechanism** open:

> "the concrete mechanism (dedicated registry path + toolFilter exclusion vs registry outside agent workspace) must be decided and tested in Phase 1. Until then the registry protection is L1-design, not yet enforced." — security spec §11.2

This ADR is the decision. It is bounded by two verified facts:

1. **Sandbox is per-session, not per-agent** (VERIFIED). Specialists run as subagents of the root orchestrator session and share that session's sandbox (`workspace-write` over the workspace root). Per-agent sandbox/approval is **not natively expressible** (ADR 0001 Decision 1).
2. **`toolFilter` is tool-level, not path-level** (VERIFIED). `edit`/`write`/`bash` can reach any path inside the sandboxed workspace; there is no per-path allow/deny.

---

## Candidate mechanisms

### Option A — Registry-outside-workspace
Place the registry at a path outside the workspace root, so no session tool can write it (the sandbox denies writes outside the workspace — SAN-002).

- **Problem (fatal for V1)**: the orchestrator (root session) shares the same per-session sandbox. Moving the registry outside the workspace blocks the orchestrator's own single-writer access. Making it orchestrator-writable requires **per-agent sandbox differentiation**, which is not natively expressible (ADR Decision 1) — or a dedicated out-of-session process with a different workspace root, which is a Phase-5 infrastructure change, not a Phase-1 decision.
- **Defer**: viable only as a Phase-5 hardening option with a separate process/sandbox-root.

### Option B — Dedicated registry path + control-plane protection (V1)
Registry lives in a **dedicated directory** (`state/registry/`) inside the workspace. Protection comes from a layered stack:

1. **Single-writer code path (L1)**: only the control-plane/orchestrator write function touches `state/registry/`. There is no free-form "registry" tool a specialist can call. Registry mutations go through a code function that validates schema, version, and authority — never through an agent's `edit`/`write`/`bash` call.
2. **Execution-gate path check (L1)**: for every write-capable action, the execution gate validates the **concrete target path** against the delegation's `scope.resources` AND against the protected registry paths. A target inside `state/registry/` is DENIED for any non-writer actor — code-enforced, not prompt.
3. **toolFilter (L2, where expressible)**: roles with no write need (CFO, Kai, BadSector) have `edit`/`write`/`bash` **excluded** from their allow sets (already in the mapping). This removes the registry path from their reachable tool surface at the DSH layer.
4. **Audit + detection (L1)**: every registry read/write is an audit event; any write by a non-writer actor is a **critical alert**; the registry is included in state versioning so a stale/injected copy is detected by version mismatch (REG-003).
5. **Honest residual gap**: roles with `bash`/`edit`/`write` (Zeko, CTO, Somad, Nova) could, in principle, reach the registry path through their tools. For V1 this is contained by (1)+(2)+(4): the single-writer discipline, the code-enforced gate, and detection. It is **not** hard path isolation at the DSH layer — stated explicitly, not assumed.

---

## Decision

**Adopt Option B — dedicated registry path + control-plane protection — for V1.**

- Registry location: `multi-agent-harness/state/registry/` (delegations + revocation list), schema `schemas/delegation.schema.json`.
- Single writer: the control-plane registry module (`tests/` reference implementation now; production module in a later phase under the same contract).
- Execution gate denies any write targeting `state/registry/` by a non-writer.
- Audit every registry event; non-writer write = critical alert.
- `registry-outside-workspace` is **rejected for V1** and **recorded as a Phase-5 hardening option** (separate process / dedicated sandbox root).

**Why**: Option A is impossible in V1 without per-agent sandbox (not expressible) or a new process (Phase-5 scope). Option B is implementable now at L1 (code) + partial L2 (toolFilter), matches the security docs' fail-closed posture, and keeps the residual risk explicit and detected rather than hidden.

---

## Tests wired (design doc §17 / security §18.3)

| Test | Semantics | Enforcement under test |
|---|---|---|
| REG-001 | specialist with write tools attempts registry write | DENY (execution-gate path check) |
| REG-002 | specialist with no write tools attempts registry write | DENY (no tool) |
| REG-003 | stale delegation read / injected copy | re-validated → DENY on version mismatch |
| REG-004 | concurrent registry write (two writers) | second DENY (CAS/version) |
| REG-005 | corrupted registry restore | treated absent → DENY (fail-closed) |
| DLG-001 | single-writer registry; specialist write | DENY + file unchanged + audit |

These are implemented as executable skeletons in `tests/authorization/test_authority.py` against the test-support reference module `tests/control_plane.py`.

---

## Consequences

1. Registry protection is **L1-design now, L1-enforced** at the reference-test level in Phase 1B; production enforcement module is a later phase but the contract is fixed by this ADR.
2. `state/registry/` becomes a **protected path constant** shared by the control-plane module and the execution gate — documented in `state/helpers` and the workflow skeleton.
3. Any future mechanism that lets an agent write `state/registry/` directly, or relies on "the prompt says no", contradicts this ADR and must be reopened.
4. Phase-5 hardening: evaluate a dedicated registry process / out-of-workspace sandbox root to close the residual `bash`-wielding-writer gap at the DSH layer.

---

## Addendum — writer-channel path-scoping (Session A, post-audit hardening)

**Change**: the sanctioned single-writer channels in `control/execution_gate.py` are now each scoped to their **own protected root** (per-channel `SANCTIONED_ROOTS`):

- `registry_write()` → MAY write only `state/registry/**`
- `audit_append()` → MAY write only `audit/**`

**Why**: previously `writer=True` was a blanket grant to *all* protected roots, so the writer channel could reach a root other than its own (e.g. `registry_write()` → `audit/…` or `audit_append()` → `state/registry/…`) and could also write arbitrary non-protected workspace paths. That was a writer-channel path-scoping gap (Master Audit). Protected-path bypass is **not** an authority grant.

**Enforcement (unchanged L1, code-enforced)**: `authorize_write()` validates the concrete target against the channel's sanctioned root **before any filesystem mutation**. Denied regardless of `writer=True`: cross-root protected targets, non-protected targets for a sanctioned channel, traversal/symlink escape, absolute-outside targets, malformed targets, and any target outside `multi-agent-harness/`. `writer=True` on a non-sanctioned action grants nothing. Non-protected CTO/Zeko writes (`write`/`edit`/`bash_write` on ordinary workspace paths) are unaffected. No DSH core, profile/preset, session policy, or role toolFilter changed; no Phase-2 work started.

*Status: accepted. Resolves security spec §11.2 open item. No DSH core/profile/preset modified; no production registry module authored (contract + reference + tests only).*