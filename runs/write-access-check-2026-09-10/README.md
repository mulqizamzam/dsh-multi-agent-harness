# Write-access probe — 15 roles toolFilter re-check (2026-09-10)

Scope: fresh live re-probe of the raw file-write surface across mounted
`subagent_<id>` instances, requested by the Human this session ("cek ada
statement subagen tidak punya akses tulis file, apakah harus demikian?").

Why: the 2026-09-10 liveness run (`runs/live-parallel-15-roles-2026-09-10/`)
explicitly did NOT probe the tool surface, and a hot-memory claim ("subagen
tidak punya bash/write") contradicted the verified design (raw-write actor
set = {cto} only, per the 2026-09-07 zeko discriminator).

## Method

- Two children dispatched in parallel (background), minimal prompts, no
  domain work: `subagent_cto` (expected: write capable) and `subagent_vera`
  (expected: read-only control).
- Each child: list tools, attempt to create its own file in this directory,
  report bash presence. No workarounds allowed.
- Parent-side verification: artifact existence checked on disk after settle.

## Results (live probe, this session)

| Role | Write tool present | Attempt outcome | bash | Disk evidence |
|---|---|---|---|---|
| cto | yes (`write`, `edit`) | SUCCESS via `write` | yes (not run) | `cto.txt` = "cto write-ok" (verified by parent) |
| vera | ABSENT | WRITE TOOL ABSENT | no | `vera.txt` not created (verified by parent) |

Config cross-check (same turn, live profile
`$DSH_HOME/profiles/web/cordis.patch.yml`, all 15 rows dumped):

- `subagent_cto` allow = [bash, read, read_image, **edit, write**, glob, grep, job_*, web_search, skill, exit_plan_mode, todo_write] — the ONLY subagent row with `edit`/`write`.
- All other 14 rows: `edit`/`write` absent from allow; cfo/kai/somad/vera/argus/atlas/tess/quill/scout/talon/ledger additionally deny them by exact name; badsector/nova also deny (nova additionally lacks bash+web in allow); zeko's allow has no edit/write (2026-09-07 discriminator comment present in the row).

Matches `config/role-preset-mapping.yaml` (mapping_version 2) and
`config/permissions.yaml` (matrix_version 2: `code_write: yes` for cto only).

## Conclusion

The blanket statement "subagen tidak punya akses tulis file" is an
overgeneralization. Design intent (least privilege, PRD §8 + PRD v0.2 §12 +
ADR 0003 D3): 14/15 specialists are write-denied BY DESIGN; `cto` is the
single deliberate raw-write actor among subagents; the orchestrator root
session holds edit/write/bash under the B-lite carve-out (execution-gated).
Hot memory corrected accordingly (2026-09-10).

## Integrity

- No repository mutation outside this directory. Commit remains an explicit
  Human action (project convention).
