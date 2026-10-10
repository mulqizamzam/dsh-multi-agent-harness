# Probe-host verification method — patched composition → `agentPresets.list()`

Purpose: gate a plugin cutover on hard evidence by booting a **throwaway** DSH host
with a **patched** profile composition and reading the agent-preset registry.

Invariants (non-negotiable):
- **Never** edit `$DSH_HOME/profiles/web/` (live profile).
- **Never** start/kill/restart the live host (`pnpm dsh web`, PID 55738, GUI on `127.0.0.1:13080`).
- The probe must be a **separate** profile dir and, if it opens any port, a **different** one.

---

## 0. Verdict up front

The registry's own roster read (`agentPresets.list()` → wire `agentPresets/list`) is the
**only** authoritative health gate. The registry records `broken` in memory and its
`logger.warn` never reaches stderr/the boot log (proved: roster plugin README "Known
limitations" + the live `/tmp/dsh-web.log` contains no genuine registry `broken` line).
A stderr boot line is a **count only** and cannot detect breakage.

**Decisive count rule.** `list()` content depends on the composition:
- Full **web** composition registers **20** = 16 roster presets + 4 presets the
  `@deepseek-ai/dsh-web-app` bundle ships (`standard`,`ptc`,`minimal`,`cordis`);
  confirmed by the live boot line 18 of `/tmp/dsh-web.log`:
  `[dsh-agent-preset-roster] registered 16 presets from …/.dsh/.agent-presets (4 already registered)`.
- A **minimal** composition (registry + roster + new plugin only) registers **16**.

So gate on **"the 16 target IDs are present AND `broken` is undefined on every row"**
and *report* the total + extras — do **not** hard-gate on `total == 16`, which is only
true for a minimal composition and would false-block a good cutover on the full one.

The 16 target IDs (15 roles + orchestrator; from `runs/orchestrator-preset-2026-09-12/roster-discovery.json`):
`orchestrator, role-argus, role-atlas, role-badsector, role-cfo, role-cto, role-kai,
role-ledger, role-nova, role-quill, role-scout, role-somad, role-talon, role-tess,
role-vera, role-zeko`.

---

## 1. Verified facts (source-cited)

| Fact | Evidence |
|---|---|
| `dsh` = `/home/administrator/.local/bin/dsh` → `node …/apps/cli/lib/bin.js`; version `0.2.0-rc.2` | wrapper file; `dsh --version` run here |
| `--profile <name>` boots; `dsh <name>` alias | `apps/cli/src/args.ts:168,203` |
| `--patch <file.yml>` repeatable overlay, applied **after** the profile layer | `apps/cli/src/args.ts:26,170` `bin.ts:39` |
| `--dump-config` / `--dump-config-schema` / `--dump-default-config` are **boot-free** | `bin.ts:55-69`; `args.ts:32-50,111-135` |
| `--patch` **cannot** combine with `--dump-default-config` (Commander errors) | `args.ts:131-133` |
| `dsh --dump-config --profile headless` prints composed layers, exit 0 (run here) | this session |
| Wire RPC methods: `agentPresets/list|read|select` on `/api`; `list()` → `{presets:[{id,name?,description?,order?,broken?,isDefault}]}` | `lib/typert.remote-client.d.ts`; `registry/src/index.ts:153-174` |
| `list()` sets `broken` only when `diagnostic()` fails; sorted by `order` then `id`; re-audits mounted trees each read | `registry/src/index.ts:102-165` |
| `broken`/breakage does NOT reach stderr | roster `README.md` "Known limitations"; live log scrape |
| 4 shipped presets `standard/ptc/minimal/cordis` via `@deepseek-ai/dsh-agent-preset` rows | `packages/bundle/web-app/presets/{standard,ptc,minimal,cordis}.patch.yml` |
| headless bundle = "no Host, HTTP, or browser layer"; needs an LLM for its agent turn | `packages/bundle/headless/package.json` description + peer deps |
| RPC transport = HTTP `/api` channel, `client-request`/`server-response` envelopes, browser-token auth | `packages/client/connection/src/rpc.ts:78-95,229-251` |
| web app has `--port`; probe can bind e.g. 13099 | `packages/bundle/web-app/src/startup.ts:78,83` |
| deps resolve via hoisted `$DSH_HOME/profiles/node_modules`; a `/tmp` probe won't resolve them | `ls profiles/`; roster = symlink into `dsh-custom/plugins/` |
| prior standalone reader `@deepseek-ai/dsh-agent-presets` is now a **broken symlink** | symlink → pruned `…/dsh-web-app/node_modules/…` (missing) |

---

## 2. Gate A — static composition (boot-free, LLM-free) — *mechanism verified here*

Prove the patched composition composes and contains the right rows **without booting**:

```bash
DSH=/home/administrator/.local/bin/dsh
PROBE=probe-cutover            # the throwaway profile name (see §3)
NEW_PATCH=/abs/path/00-new-plugin.patch.yml

$DSH --dump-config --profile "$PROBE" --patch "$NEW_PATCH" | tee /tmp/probe.dumpcfg
```

Assertions on the dumped tree:
- a row for the **new plugin** under test is present;
- the registry row exists: `- id: agent-preset-registry` / `name: '@deepseek-ai/dsh-agent-preset-registry'` with `default: standard`, `selectedDefault: orchestrator`;
- the roster row exists: `dsh-agent-preset-roster`;
- for an **exactly-16** composition, the web-app preset rows (`preset-standard/ptc/minimal/cordis`, i.e. `@deepseek-ai/dsh-web-app`) are **absent**.

Bundle-layer baseline: `$DSH --dump-default-config --profile "$PROBE"` (no `--patch`).

This gate alone proves composition; it does **not** call `list()`.

---

## 3. Gate B — runtime roster read

> The actual boot+read+exit is **operator-run**: this session could create exactly one
> file (this doc) and must not create probe profiles/plugins. `dsh --version` and Gate A's
> `--dump-config` were run and pass. Everything below is derived from source and must be
> executed by you.

Build the probe profile **inside** `$DSH_HOME/profiles/<new>` (NOT `web`) so node resolves
the hoisted deps. `DSH_HOME` stays the **live** one (`/home/administrator/agent-workspace/.dsh`)
so the roster plugin reads the real `.agent-presets/` (read-only).

`$DSH_HOME/profiles/probe-cutover/package.json`:
```json
{ "name": "dsh-profile-probe-cutover", "private": true,
  "dependencies": {
    "dsh-agent-preset-roster": "link:/home/administrator/agent-workspace/dsh-custom/plugins/dsh-agent-preset-roster",
    "probe-roster-reader": "link:/home/administrator/agent-workspace/dsh-custom/plugins/.probe-cutover-reader"
  },
  "dsh": { "profile": { "bundles": [
    "@deepseek-ai/dsh-base",
    "@deepseek-ai/dsh-headless",
    "dsh-agent-preset-roster",
    "probe-roster-reader"
  ] } } }
```

`$DSH_HOME/profiles/probe-cutover/cordis.patch.yml` (registry row + kill the LLM runner + insert reader):
```yaml
- id: agent-preset-registry
  name: '@deepseek-ai/dsh-agent-preset-registry'
  config: { default: standard, selectedDefault: orchestrator }
- id: headless-startup
  name: '@deepseek-ai/dsh-headless/startup'
  disabled: true
- id: headless-runner
  name: '@deepseek-ai/dsh-headless'
  disabled: true
- insert:
  - id: probe-roster-reader
    name: probe-roster-reader
```
> To also load the plugin under test minimally, add its bundle here and/or insert its row
> in the `--patch` overlay. Prefer the full plugin set (see caveat in §5/R1).

Reader plugin `dsh-custom/plugins/.probe-cutover-reader/index.js` (mirrors the roster plugin's
named-export shape):
```js
export const name = 'probe-roster-reader'
export const inject = ['agentPresets']
export async function* apply(ctx, config) {
  const rows = await ctx.agentPresets.list()
  const TARGET = ['role-argus','role-atlas','role-badsector','role-cfo','role-cto','role-kai',
    'role-ledger','role-nova','role-quill','role-scout','role-somad','role-talon','role-tess',
    'role-vera','role-zeko','orchestrator']
  const ids = rows.map(r => r.id)
  const missing   = TARGET.filter(t => !ids.includes(t))
  const brokenAll = rows.filter(r => r.broken !== undefined)
                     .map(r => ({ id: r.id, broken: String(r.broken).slice(0,200) }))
  const extras    = ids.filter(i => !TARGET.includes(i))
  const out = { total: rows.length, targetPresent: TARGET.length - missing.length,
    missing, brokenAll, extras,
    defaultId: (rows.find(r => r.isDefault) || {}).id || null }
  process.stdout.write('PROBE_ROSTER ' + JSON.stringify(out) + '\n')
  const pass = missing.length === 0 && brokenAll.length === 0
  setTimeout(() => process.exit(pass ? 0 : 1), 25)
}
```

Boot (no LLM turn because the headless runner is disabled; no port because headless has no
HTTP layer) and capture:
```bash
PROBE=dsh-profile-probe-cutover
( cd "$DSH_HOME/profiles/probe-cutover"
  # make link: deps resolvable the same way the web profile does:
  #   dsh plugin --profile probe-cutover add <pkgs>   # (one-time) OR copy the web profile's node_modules layout
  DSH_HOME=/home/administrator/agent-workspace/.dsh \
    /home/administrator/.local/bin/dsh --profile "$PROBE" 2>/tmp/probe.err \
  | tee /tmp/probe.out )
grep PROBE_ROSTER /tmp/probe.out
```
Gate PASS ⇔ `missing == []` AND `brokenAll == []`. Also inspect `extras`:
`[]` means minimal(16); `[cordis,minimal,ptc,standard]` means full(20). `defaultId` should be
`orchestrator` (from `selectedDefault`).

Boot-free dry run first (recommended): `… --dump-config --profile "$PROBE" --patch <overlay>`.

### 3b. Alternative R2 — faithful external read over HTTP (full composition, no spurious breakage)

Only if you must read `list()` from **outside** the host with the **full** dependency set
(so the 16 are genuinely healthy, matching the prior "20, 0 broken" evidence):

```bash
ss -ltn | grep 13099 || DSH_HOME=/home/administrator/agent-workspace/.dsh \
  /home/administrator/.local/bin/dsh --profile <web-copy> --port 13099 &   # a COPY of web, never profiles/web
# then call the authenticated API channel:
#   POST/WS  http://127.0.0.1:13099/api/agentPresets/list
#   envelope: {"type":"client-request","rpcId":"probe-1","method":"agentPresets/list","payload":{}}
#   auth via the browser-token exchange (startup.ts prints/derives the operator URL)
```
The **token acquisition** step is the one piece not proven here — confirm the exact
boot-printed URL/token from `packages/client/connection/src/rpc.ts` (`authorizeIndex`,
`authenticatedUrl`) + `packages/bundle/web-app/src/startup.ts`. Expect total 20, extras
`[cordis,minimal,ptc,standard]`, `brokenAll == []`.

---

## 4. Gate L — fallback: boot-log scrape (count only, WEAK)

```bash
grep -\[dsh-agent-preset-roster\] /tmp/probe.err | tail -1
# live today in /tmp/dsh-web.log:
#   "registered 16 presets from …/.agent-presets (4 already registered)"
```
Necessary but **not sufficient**: proves registration *count*, cannot detect `broken`
(breakage never reaches stderr). Use only if Gate B is unavailable.

---

## 5. Risks / caveats

1. **16 vs 20** is composition-driven (see §0). Gate on target-present + 0-broken, not raw total.
2. **Minimal probe may report spurious `broken`** if the 16 presets' `agent.cordis.yml`
   children reference plugins only present in the full stack. If you trim the composition
   too far you get a *false* gate failure — prefer the full set (R2) for a true health read,
   or keep the dependencies the presets need.
3. `headless` opens **no** port → no 13080 conflict. If you use a web probe, bind a free
   `--port` (check `ss -ltn`) and never reuse 13080.
4. Keep `headless-runner`/`headless-startup` **disabled** so no LLM turn fires (no cost/side
   effects); the reader exits the process itself.
5. Probe profile is a **separate dir** under `$DSH_HOME/profiles/`; `profiles/web` and the
   live host are untouched; no restart.
6. Same `DSH_HOME` so the roster reads the real `.agent-presets/` (read-only). Don't repoint
   `DSH_HOME` unless you also copy the preset dir.
7. `/tmp` probe dirs won't resolve deps (node walk-up misses hoisted `profiles/node_modules`);
   put the probe under `$DSH_HOME/profiles/` or `dsh plugin --profile probe add …` first.
8. Session sandbox/approval: the headless probe runs **no** session/turn → no approval prompts,
   and the live `context-optimizer` executor sandbox (live patch only) is not inherited.
9. Prior standalone reader `@deepseek-ai/dsh-agent-presets` is a **broken symlink** now —
   reproduce via the reader-plugin + `list()`, not that package.
10. `mountPreset`/session `select` are **not** exercised by a `list()` read (ADR 0006 §5.3);
    this proves registration + pre-mount health, not that a session can start on a preset.

## 6. What is verified vs unverified (this session)

- **Verified here:** `dsh --version`; `--dump-config --profile headless` (boot-free, exit 0);
  live boot line 16+4; the 4 shipped preset IDs; wire method `agentPresets/list`; roster
  plugin behaviour; headless = no HTTP; web `--port` exists.
- **Unverified (operator-run):** the actual Gate B boot + `list()` + clean exit; the R2
  token-acquisition/curl step; expected `brokenAll == []` on a trimmed composition.
