// dsh-multi-agent-harness — file-driven preset registration
//
// This repository (the multi-agent control plane) is also a DSH Cordis plugin.
// It registers the 16 agent presets — the 15 `role-*` specialists under
// `agents/<id>/` and the `orchestrator` root-session preset under
// `orchestrator/` — directly from the repo's own files with the agent-preset
// registry, so sessions can select them in the Web GUI. It replaces
// `dsh-agent-preset-roster`: there is no `.agent-presets/` deployment copy,
// because these repository files are the single source of truth.
//
// Contract (mirrors dsh-agent-preset-roster, rooted differently):
//   - Self-locating. The package root is the directory of this file
//     (`import.meta.url`); no env vars and no configuration are read. The
//     source of truth is the repo itself: agents root = <pkgroot>/agents,
//     orchestrator preset = <pkgroot>/orchestrator.
//   - `agent.cordis.yml` is parsed with the Loader's own entry-list dialect
//     (`entryListSchema` from cordis-plugin-include), so `!!js` expressions
//     survive as `{ __jsExpr }` nodes and are evaluated by the Loader at
//     activation, exactly as profile rows are.
//   - `preset.yml` contributes the description only (display metadata).
//   - Registration is a generator effect: each `register()` disposer is
//     yielded, so HMR or host teardown unregisters cleanly.
//   - Ids are load-bearing. The delegation tool's `allowedAgentPresets`
//     names every role preset, and the root session defaults to
//     `orchestrator`, so the ids registered here MUST be exactly
//     role-<dirname> (15) + orchestrator.
//   - A missing source dir is logged and skipped; a preset whose parse or
//     registration fails is logged per-preset. Neither throws out of `apply`,
//     so one bad preset cannot take the host down. The registry itself records
//     an activation failure `broken` on the row rather than throwing.
//   - No roster snapshot is read at apply time. `agentPresets.list()`
//     re-audits every mounted preset and, while any of them still has a
//     pending row, awaits the host Loader (agent-preset-registry
//     src/index.ts:135-139) — and that await waits on THIS row's own
//     activation, so calling it from `apply` would hang host boot the moment
//     any listed preset has a pending row. The registry rejects a duplicate
//     id atomically before any await (src/index.ts:82-85), and the per-preset
//     catch below absorbs that rejection, so no snapshot is needed.
//   - Boot diagnostics are honest: registration success is not activation
//     success, so one deferred roster read (scheduled, never awaited — see
//     the audit note in `apply`) reports how many presets are `broken`.

import { existsSync } from 'node:fs'
import { readdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import yaml from 'js-yaml'
import { entryListSchema } from '@deepseek-ai/cordis-plugin-include'

export const name = 'dsh-multi-agent-harness'
export const inject = ['agentPresets']

const TAG = '[dsh-multi-agent-harness]'
const COMPOSITION_FILE = 'agent.cordis.yml'
const METADATA_FILE = 'preset.yml'

// Self-locating package root: the directory that holds this index.js. Every
// source path is derived from here, so the plugin reads the repo it ships in
// regardless of cwd or env.
const PKG_ROOT = path.dirname(fileURLToPath(import.meta.url))
const AGENTS_ROOT = path.join(PKG_ROOT, 'agents')
const ORCHESTRATOR_DIR = path.join(PKG_ROOT, 'orchestrator')
const ORCHESTRATOR_ID = 'orchestrator'

/** One tagged line to stderr, the host's boot-log channel. */
function log(message) {
  process.stderr.write(`${TAG} ${message}\n`)
}

/** Read one preset directory into a registry definition, or null to skip.
 * Semantics mirror dsh-agent-preset-roster's readPreset exactly: the
 * composition is parsed with the Loader's entry-list dialect; the optional
 * preset.yml contributes the description when it is a non-empty string. */
async function readPreset(id, dir) {
  const compositionPath = path.join(dir, COMPOSITION_FILE)
  if (!existsSync(compositionPath)) return null
  const composition = await readFile(compositionPath, 'utf8')
  const plugins = yaml.load(composition, { schema: entryListSchema })
  const definition = { id, plugins }
  const metadataPath = path.join(dir, METADATA_FILE)
  if (existsSync(metadataPath)) {
    const metadata = (yaml.load(await readFile(metadataPath, 'utf8'))) ?? {}
    if (typeof metadata.description === 'string' && metadata.description) {
      definition.description = metadata.description
    }
  }
  return definition
}

/** Register one preset under `id` from `dir`.
 *
 * Returns `{ dispose, reason }`:
 *   - `{ dispose, 'registered' }` — the registry accepted the definition and
 *     activation settled; the caller yields `dispose`.
 *   - `{ null, 'duplicate' }` — another plugin already owns the id. The
 *     registry throws before any await, so this is decided atomically.
 *   - `{ null, 'absent' }` — the directory holds no composition file.
 *   - `{ null, 'failed' }` — parse or registration fault, logged per preset.
 *
 * An activation failure is NOT a failure here: the registry records it
 * `broken` on the row and still returns the disposer, so the preset stays
 * visible in the roster and the deferred audit reports it.
 */
async function tryRegister(presets, id, dir) {
  try {
    const definition = await readPreset(id, dir)
    if (definition === null) return { dispose: null, reason: 'absent' }
    const dispose = await presets.register(definition)
    return { dispose, reason: 'registered' }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    if (message.startsWith('Duplicate agent preset')) {
      return { dispose: null, reason: 'duplicate' }
    }
    log(`preset ${id} failed to register: ${message}`)
    return { dispose: null, reason: 'failed' }
  }
}

export async function* apply(ctx) {
  const presets = ctx.agentPresets
  let registered = 0
  let skipped = 0
  let failed = 0

  let dirs = []
  if (existsSync(AGENTS_ROOT)) {
    try {
      dirs = (await readdir(AGENTS_ROOT, { withFileTypes: true }))
        .filter((entry) => entry.isDirectory())
        .map((entry) => entry.name)
        .sort()
    } catch (error) {
      log(`agents root ${AGENTS_ROOT} unreadable: ${String(error)}`)
    }
  } else {
    log(`agents root ${AGENTS_ROOT} does not exist; skipping role presets`)
  }
  // Each dirname under agents/ is a role preset: agents/<id> -> role-<id>.
  for (const dir of dirs) {
    const outcome = await tryRegister(presets, `role-${dir}`, path.join(AGENTS_ROOT, dir))
    if (outcome.reason === 'registered') {
      yield outcome.dispose
      registered += 1
    } else if (outcome.reason === 'duplicate') skipped += 1
    else if (outcome.reason === 'failed') failed += 1
  }

  // The orchestrator is one preset under <pkgroot>/orchestrator, no role prefix.
  if (existsSync(ORCHESTRATOR_DIR)) {
    const outcome = await tryRegister(presets, ORCHESTRATOR_ID, ORCHESTRATOR_DIR)
    if (outcome.reason === 'registered') {
      yield outcome.dispose
      registered += 1
    } else if (outcome.reason === 'duplicate') skipped += 1
    else if (outcome.reason === 'failed') failed += 1
  } else {
    log(`orchestrator preset ${ORCHESTRATOR_DIR} does not exist; skipping`)
  }

  log(`registered ${registered} presets from ${PKG_ROOT} ` +
      `(skipped ${skipped} already registered, ${failed} failed)`)

  // Boot-log honesty. `register()` settles activation without throwing, so
  // the count above includes presets the registry recorded `broken`; the
  // registry warns through its own logger, which this tagged line cannot
  // see. One deferred roster read reports the activation outcomes. It is
  // scheduled and never awaited: this row's activation settles first, so the
  // registry's host-Loader await inside `list()` can no longer wait on this
  // row — reading the roster from inside `apply` is the boot deadlock the
  // snapshot removal above avoids.
  const audit = setTimeout(() => {
    presets.list().then((rows) => {
      const broken = rows.filter((row) => row.broken !== undefined)
      const summary = broken.length === 0
        ? `${rows.length} presets in roster, none broken`
        : `${rows.length} presets in roster, ${broken.length} broken — ` +
          broken.map((row) => `${row.id}: ${row.broken}`).join(' | ')
      log(`roster audit: ${summary}`)
    }, (error) => {
      log(`roster audit failed: ${String(error)}`)
    })
  }, 0)
  // Yielded last, so teardown clears the timer before the disposers that
  // unregister the presets it would read.
  yield () => clearTimeout(audit)
}
