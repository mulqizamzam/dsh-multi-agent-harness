# Live parallel spawn — all 7 roles at once (2026-09-09)

Scope: first recorded **live** parallel spawn of all seven specialist
`subagent_<id>` instances through the mounted DSH web profile.

NOT to be confused with `runs/7role_smoke/` (2026-09-04): that one runs a
bounded mission through the harness organization layer with a **recorder
backend and fixture handoffs** (`runs/7role_smoke_driver.py` docstring) —
no live DSH children. This run spawned real children via the live tool
instances.

Authority: direct user request this session, 2026-09-09 ("berikan contoh
saat mereka berjalan bersamaan ke tujuhnya"). Smoke test only — no
specialist domain work was requested or performed.

## Dispatch method

- One parallel tool block: 7 calls, `subagent_{zeko,cto,cfo,kai,somad,badsector,nova}`,
  background continuable, identical one-sentence prompt (state your primary
  role + domain; use no tools).
- Dispatched ~2026-09-09T03:33Z. Concurrency snapshot (list_agents,
  ~03:34Z) showed 4 agents between-turns + 3 still running — direct
  evidence of overlap. All 7 settled before 03:34:10Z (time of this record).

## Results — 7/7 spawned, 7/7 completed

| # | Role | Child run id | Persona reported | Matches `config/agents.yaml` |
|---|---|---|---|---|
| 1 | zeko | `2df90103-51f1-4135-a963-84d0625cab7c` | Operations & Infrastructure | yes |
| 2 | cto | `ce885940-e865-4433-adbe-1bc5efe814ef` | Engineering | yes |
| 3 | cfo | `fb41aaea-b580-4deb-b7d1-9d9b52d28155` | Finance, Pricing & Economics | yes |
| 4 | kai | `b70e30bc-3cf9-45e5-ba87-4990ab232b4e` | Research, News & Trends | yes |
| 5 | somad | `f67a6e33-b39b-4eaa-b518-7495d064dd4b` | Social Media & Distribution | yes |
| 6 | badsector | `1364247c-4b37-44e0-9f45-796c2d490b3a` | Adversarial Review | yes |
| 7 | nova | `35a47873-8b4d-46fc-b578-20746fdeaffc` | Writing & Novel | yes |

Child run ids are DSH subagent ids; persona resolution comes from the
mounted `role-<id>` presets (`$DSH_HOME/.agent-presets/role-*/`).

## What this run does NOT verify

- **ToolFilter / deny contract** — children were instructed not to use any
  tool, so no tool surface was probed. ToolFilter enforcement evidence
  remains `runs/mount-verification-2026-09-07/` (INT-01 live probe: persona
  resolved, `bash`/`edit`/`write` present for cto, sibling `subagent_*`
  absent) plus the yaml-parity tests.
- Domain-work quality, channel-routed writes, approval gates, and
  subdelegation deny were not exercised.

## Prior related evidence

- `runs/mount-verification-2026-09-07/` — live spawn verified per-instance;
  most roles live-proven (INT-01/07/11/12), max 3 concurrent (INT-11:
  cfo+kai+nova). No earlier all-7 live parallel spawn is recorded in this
  repo's runs/ or verification docs.
- `runs/7role_smoke/` (2026-09-04) — all-7 mission coverage at the harness
  layer with a recorder backend (fixtures), not live children.

## Integrity

- No repository mutation outside this directory. Runtime evidence only;
  committed to git 2026-09-10 by explicit Human request (project
  convention: commit stays an explicit Human action; see
  mount-verification README §3).
