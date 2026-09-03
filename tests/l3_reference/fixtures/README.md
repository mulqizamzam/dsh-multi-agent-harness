# tests/l3_reference/fixtures — L3 scenario fixtures (inert templates)

**INERT SPECIFICATION SUPPORT. NOT signed evidence. NOT an L3 run.**

Each directory under `fixtures/` is one L3 scenario. It carries the **shapes**
that a Human-signed `plan.json` and a seeded environment take. These fixtures
carry **no authority** (AUTH-INV-14) and are **not** actual signed evidence —
they are placeholders that a Human must fill and sign **before** any real
(recorded-vs-live) L3 run.

## Layout

```
tests/l3_reference/fixtures/
├── shared/env.template.json          # env.json template (pinned DSH version)
├── INT-01/plan.json                  # INT-01 happy-path plan template
├── INT-07/plan.json                  # INT-07 revocation-DENY plan template
├── INT-11/plan.json                  # INT-11 parallel-collection plan template
├── INT-12/plan.json                  # INT-12 failure/recovery plan template
├── L3-TEST-001/                      # SYNTHETIC test scenario (ALLOW)
│   ├── plan.json                     #   schema-valid Human-signed plan
│   ├── fixture.json                  #   verifier oracle context (gate, classes)
│   └── runtime-recorded.json         #   recorded runtime verdict + audit slice
└── L3-TEST-002/                      # SYNTHETIC test scenario (DENY protected path)
    ├── plan.json
    ├── fixture.json
    └── runtime-recorded.json
```

## The two-file split

- **`plan.json`** — schema-pure (`l3-plan.schema.json`): the Human-signed
  expectation (O4 oracle). It contains ONLY the fields the evidence bundle's
  `plan.json` requires.
- **`fixture.json`** — scenario-driving inputs merged by the runner: the
  `gate_under_test`, `oracle_classes_used`, `oracle_context` (captured action
  request), delegation chain, children, and provenance. It is NOT part of the
  evidence bundle; it is the input the verifier consumes.

The runner (`tests/l3_runner/runner.py`) loads `plan.json`, merges
`fixture.json`, and writes the schema-pure `plan.json` into the evidence bundle.

## Safety

The `L3-TEST-*` scenarios are SYNTHETIC and used only by the infrastructure
test suite (`tests/l3_runner/test_l3_infrastructure.py`) with the safe
`RecordedRuntimeDriver`. They are never executed against a live DSH session and
never claim L3 status (rehearsal bundles carry `l3_claim: false`).