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
//   - Ids are load-bearing. The live web profile names every subagent by
//     `persona: role-<id>` and defaults the root session to `orchestrator`, so
//     the ids registered here MUST be exactly role-<dirname> (15) + orchestrator.
//   - A missing source dir is logged and skipped; a preset whose parse or
//     registration fails is logged per-preset. Neither throws out of `apply`,
//     so one bad preset cannot take the host down. The registry itself records
//     an activation failure `broken` on the row rather than throwing.

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

/** Register one preset under `id` from `dir`, returning its disposer.
 *
 * `existing` guards against ids another plugin already registered (the registry
 * rejects duplicates). Both the parse and the register call share one guard so a
 * malformed `agent.cordis.yml` or a definition-level fault is logged per-preset
 * and never thrown out of `apply`. Returns null when the caller should skip:
 * already registered, no composition file, or a logged failure. An activation
 * failure is not thrown by register — the registry records it `broken`. */
async function tryRegister(presets, existing, id, dir) {
  if (existing.has(id)) return null
  try {
    const definition = await readPreset(id, dir)
    if (definition === null) return null
    return await presets.register(definition)
  } catch (error) {
    log(`preset ${id} failed to register: ${String(error)}`)
    return null
  }
}

export async function* apply(ctx) {
  const presets = ctx.agentPresets
  // Never collide with a preset another plugin already registered under the
  // same id: the registry rejects duplicates and would fail this plugin.
  const existing = new Set((await presets.list()).map((row) => row.id))
  let registered = 0

  if (existsSync(AGENTS_ROOT)) {
    const dirs = (await readdir(AGENTS_ROOT, { withFileTypes: true }))
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort()
    // Each dirname under agents/ is a role preset: agents/<id> -> role-<id>.
    for (const dir of dirs) {
      const dispose = await tryRegister(presets, existing, `role-${dir}`, path.join(AGENTS_ROOT, dir))
      if (dispose !== null) {
        yield dispose
        registered += 1
      }
    }
  } else {
    log(`agents root ${AGENTS_ROOT} does not exist; skipping role presets`)
  }

  // The orchestrator is one preset under <pkgroot>/orchestrator, no role prefix.
  if (existsSync(ORCHESTRATOR_DIR)) {
    const dispose = await tryRegister(presets, existing, ORCHESTRATOR_ID, ORCHESTRATOR_DIR)
    if (dispose !== null) {
      yield dispose
      registered += 1
    }
  } else {
    log(`orchestrator preset ${ORCHESTRATOR_DIR} does not exist; skipping`)
  }

  log(`registered ${registered} presets from ${PKG_ROOT} ` +
      `(${existing.size} already registered)`)
}
