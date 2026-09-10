# Live same-role parallel write smoke — 3× CTO (2026-09-10)

Scope: first recorded live smoke of **three instances of the same specialist
role** (`subagent_cto`) running simultaneously and writing distinct content
to distinct paths in the same workspace.

Distinct from prior runs:
- `runs/live-parallel-7-roles-2026-09-09/` — 7 *different* roles, one
  instance each, tool-less smoke.
- `runs/7role_smoke/` (2026-09-04) — harness-layer mission, recorder backend
  + fixtures, not live children.
- `runs/write-access-check-2026-09-10/` — single-CTO write probe.

Authority: direct user request this session, 2026-09-10 ("smoke test, 3 cto
berjalan bersamaan, menulis hal yg berbeda di tempat berbeda"). Smoke only —
no specialist domain work performed.

## Method

- Parent pre-created disjoint directories: `cto-a/`, `cto-b/`, `cto-c/`.
- One parallel tool block: 3 × `subagent_cto` (background continuable),
  identical prompt template with per-instance assignment: own `REPORT.md`
  path + distinct topic (A: in-memory caching, B: retry & backoff,
  C: feature-flag config), plus explicit boundary "touch nothing else;
  siblings are writing in neighboring directories of the same workspace".
- Isolation model: **one-writer-per-path discipline** — disjoint path
  assignment inside the delegation, NOT sandbox enforcement. All three
  children share the same workspace.

## Evidence — 3/3 spawned, 3/3 completed, zero collisions

- **Concurrency**: `list_agents` snapshot taken immediately after dispatch
  showed all three `[running]` at once, before any had completed.
- **Overlapping write window** (timestamps read from file contents and
  verified by the parent, not taken from child claims alone):
  B 14:20:11Z, C 14:20:44Z, A 14:21:02Z — a ~51 s window entirely inside
  the observed concurrent period.
- **File census**: `find` over this directory returned **exactly 3 files**
  (the three `REPORT.md`), no stray files, no cross-directory writes.
- **Content check per file**: correct title marker (CTO-A/B/C smoke),
  assigned topic present, no cross-topic content.

| Instance | Child run id | Path | Topic | Written (UTC) |
|---|---|---|---|---|
| A | `9297722f-75cd-4f5e-ba45-cf7b8996ac61` | `cto-a/REPORT.md` | in-memory caching | 14:21:02 |
| B | `108b7ed8-523e-4306-babe-8f9f386f0955` | `cto-b/REPORT.md` | retry & backoff | 14:20:11 |
| C | `6faa5eb0-b0de-4392-8191-7442ef4e6b34` | `cto-c/REPORT.md` | feature-flag config | 14:20:44 |

## What this does NOT verify

- **No sandbox-level write isolation is claimed.** A same-path assignment
  to two instances would still race. The working guard is the delegation
  contract: disjoint paths / pinned interfaces (operator execution
  preference: multi-`subagent_cto` allowed under one-writer-per-path
  discipline).
- ToolFilter surface beyond "wrote to its assigned path"; the deny contract
  (sibling `subagent_*` denied, max_depth 1) is unchanged from the mount
  verification and was not re-probed here.

## Integrity

- No repository mutation outside this directory. Not committed —
  committing remains an explicit Human action (project convention).
