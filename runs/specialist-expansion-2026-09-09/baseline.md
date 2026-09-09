# Baseline Regression — Specialist Pool Expansion (PRD v0.2)

**Date:** 2026-09-09 (04:04 UTC session start; run 324.26s)
**Commit:** `2bda13b` (master, clean HEAD via `git stash push -u` → run → `git stash pop`)
**Command:** `.venv-tests/bin/python -m pytest tests/ -q --maxfail=0 --basetemp=/tmp/pbt/pytest -p no:cacheprovider` (TMPDIR=/tmp/pbt)

## Result

```
1 failed, 3261 passed, 5 skipped in 324.26s (0:05:24)
```

## The single pre-existing failure (NOT expansion-related)

`tests/l3_runner/environment/approval/test_approval_path_readiness.py::test_web_answerer_is_not_in_dsh_home_profiles`

- Walks the LIVE `$DSH_HOME/profiles` tree and asserts no answerer marker rows
  (`user-approval`, `ui-user-questions`, `approval/request`,
  `dsh-client-ui-conversation`) exist in profile yml files.
- The operator's live profile composition contains at least one such marker
  (environment drift, not repo code). Reproduced at clean HEAD before any
  expansion edit — this is the recorded known-red baseline exception.
- Expansion work must not touch `$DSH_HOME`; the failure is expected to remain
  and is out of scope (live-environment reconciliation is the operator's).

## Environment notes (for reproducibility)

- `/tmp` is ephemeral between bash calls in this environment; pytest basetemp
  MUST be a short path (`/tmp/pbt/pytest`). Long basetemp paths under the repo
  break the autouse O3 daemon fixture (`ipc.sock` exceeds the 108-char
  AF_UNIX limit → "O3 daemon did not start").
- Two pytest runs must never share a basetemp (tmp dirs + O3 daemons collide).
- A KILLED pytest run leaves stale `ipc.sock` files in the numbered per-test
  basetemp dirs; the next run reuses the numbering and the daemon `bind()`
  fails → every test ERRORs at setup. Always `rm -rf` the basetemp before a
  fresh pytest run.

## Post-expansion target

Full suite green except: (a) this recorded baseline exception, (b) the
documented expected-red live-rows parity test
(`test_live_rows_match_config`) until the Human-approved mount exception
(ADR 0003 D8) executes.
