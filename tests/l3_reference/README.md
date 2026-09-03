# tests/l3_reference — L3 Reference / Oracle Implementations (O1)

**INDEPENDENT REFERENCE/ORACLE IMPLEMENTATIONS. NOT production gates.**

This directory holds the **reference re-implementations** (O1 external oracles)
that the L3 verifier loads to compute its verdict. Each file is a SELF-CONTAINED
re-implementation of a control-plane gate with NO shared imports from the
production control modules (`control/*`, `orchestrator/foundation/*`,
`audit/helpers/*`, `state/helpers/*`).

- Phase: 4 / Session B — L3 independent verification infrastructure
- Version pin: DeepSeek Harness `0.1.1-rc.2`
- Companion specs: `docs/security/0003-l3-independent-verification-plan.md`
  · `docs/design/0002-l3-verification-specification.md`
  · `docs/security/0005-l3-evidence-infrastructure-specification.md`
  · `docs/testing/0003-l3-evidence-validation-specification.md`

## Independence property

The verifier (`tests/l3_runner/verifier.py`) loads gate re-implementations
from THIS directory, never from the production control modules. This prevents
the "gate approves itself by referring to its own table" tautology (P3 —
external oracle). If the reference agrees with the runtime's verdict, that is
independent evidence; if it disagrees, the runtime failed the oracle.

## Contents

```
tests/l3_reference/
├── __init__.py          # package marker + independence notice
├── README.md            # this file
├── authority_gate.py    # O1: authority-gate re-implementation (14-item checklist)
├── execution_gate.py    # O1: path-aware execution gate (protected paths, traversal)
├── delegation_gate.py   # O1: delegation validation (expiry, revocation, scope)
├── role_gate.py         # O1: role isolation (capability matrix, tool enumeration)
├── recovery_gate.py     # O1: recovery rules (no blind retry, privilege bounded)
├── verification_gate.py # O1: verification rules (COMPLETE requires verified outcome)
├── transition_gate.py   # O1: state transition machine (legal-transition graph)
├── audit_chain.py       # O1: audit integrity chain (SHA-256 ledger verification)
├── schemas/             # JSON Schemas for each L3 evidence file (O2 oracle)
├── fixtures/            # Inert plan.json / fixture.json templates
└── fixtures.py          # Test-only fixture helpers
```

## Oracle modules

| Gate | Module | Entrypoint | Controls covered |
|------|--------|------------|-----------------|
| `authority` | `authority_gate.py` | `oracle_authority(context)` | L3-AUTH-001..009 |
| `execution_gate` | `execution_gate.py` | `oracle_execution_gate(context)` | L3-PATH-001..008, L3-XG-001..009 |
| `delegation` | `delegation_gate.py` | `oracle_delegation(context)` | L3-DLG-001..007 |
| `role_isolation` | `role_gate.py` | `oracle_role(context)` | L3-ISO-001..010 |
| `recovery` | `recovery_gate.py` | `oracle_recovery(context)` | L3-REC-001..007 |
| `verification` | `verification_gate.py` | `oracle_verification(context)` | L3-VER-001..006 |
| `state_transition` | `transition_gate.py` | `oracle_transition(context)` | L3-ST-001..008 |
| `audit_integrity` | `audit_chain.py` | `oracle_audit_chain(context)` | L3-AUD-001..007 |

## Usage

Each oracle module is independently loadable:

```python
from tests.l3_reference.authority_gate import oracle_authority
verdict = oracle_authority({
    "actor": "orchestrator",
    "action": "code_write",
    "target": "agents/cto/x.txt",
    "delegation": {"id": "delegation-1", "status": "ACTIVE", ...},
    "environment": "dev",
    "project": "multi-agent-harness",
})
# verdict["decision"] == "ALLOW" | "DENY" | "ESCALATE"
```

## Design principles

1. **No production imports.** Each file is verified at module load time by
   `assert_clean_imports()` in the verifier, which refuses to run if any
   `control.*`, `orchestrator.foundation.*`, `audit.helpers.*`, or
   `state.helpers.*` module is imported in the same process.

2. **Different data structures.** The reference implementations use a decision
   table / checklist approach (authority_gate has a 14-item checklist,
   execution_gate uses an explicit classification table) rather than mirroring
   the production's `if`-chain, so they are structurally different code.

3. **Self-contained.** Each oracle can be loaded independently without importing
   other reference oracles (minimal duplication of `target_in_scope` and
   `_parse_dt` utilities is intentional — keeps each oracle independently
   verifiable).

4. **Deterministic.** All oracles are pure functions of their input (no
   randomness, no network, no file system for the core logic). The execution
   gate oracle defaults the workspace base to the project root deterministically
   (two levels up from `tests/l3_reference/`).

## Honesty

These reference implementations are **O1 oracles** — one of the two required
oracle classes (P3). Every L3 scenario must also carry at least one additional
oracle class (O2 schema-as-oracle, O3 on-disk-state-as-oracle, or O4
Human-signed expectation). A build that uses only an O1 oracle is **not L3**.