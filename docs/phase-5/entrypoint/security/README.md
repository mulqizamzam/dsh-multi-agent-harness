# Phase 5 / Front Door — Security & Contract Test Package

- **Package**: `tests/orchestrator/entrypoint/security/`
- **Docs**: `docs/phase-5/entrypoint/security/`
- **Adversarial scope**: categories A–H + static proofs (11 test modules)
- **NOT_YET_AVAILABLE guard**: the entire package skips with `NOT_YET_AVAILABLE` when
  `orchestrator.entrypoint` (Session Front Door V1) is not importable — nothing is
  fabricated.

## How to run

```bash
cd multi-agent-harness
.venv-tests/bin/python3 -m pytest tests/orchestrator/entrypoint/security/ -v
```

## Coverage summary

| Category | File | Tests | Description |
|---|---|---|---|
| A  Input Trust | `test_a_input_trust.py` | 10 | Objective/constraints are DATA, never authority |
| B  Authority Boundary | `test_b_authority_boundary.py` | 13 | Missing/unknown/expired/revoked/malformed delegation handling |
| C  Scope | `test_c_scope.py` | 10 | Empty/malformed/traversal/abs/prefix/protected scope DENY |
| D  Risk | `test_d_risk.py` | 8 | No risk/approval/review override accepted |
| E  Control-Chain Integrity | `test_e_control_chain.py` | 12 | Behavioral spies + static AST: full chain proof |
| F  Terminal States | `test_f_terminal_states.py` | 9 | No DENY/ESCALATE/exception → COMPLETE |
| G  Output Integrity | `test_g_output_integrity.py` | 11 | Honest run_id, report, audit_ids; JSON serializable |
| H  Abuse / Robustness | `test_h_abuse_robustness.py` | 10 | Oversized/unicode/repeat/duplicate/unknown fields |
| Static AST scan | `test_static_scan.py` | 17 | No raw DSH, no delegation mint, no registry write, no bypass |

**Total**: ~100 tests across 9 adversarial categories + static proofs.

## Classification

Each test classifies the observed outcome as:

| Class | Meaning |
|---|---|
| PASS | Security property holds — adversarial input neutralised |
| DENY | Authority/invocation correctly rejected |
| ESCALATE | Adversarial input triggers escalation (correct fail-closed) |
| ERROR | Adversarial or malformed input rejected at shape validation |
| UNKNOWN | Not verifiable / no claim made |
| NOT_YET_AVAILABLE | Front door not implemented — nothing fabricated |

## Posture note

The front door IS implemented (`orchestrator/entrypoint/`, Phase 5 / Front Door V1).
The NOT_YET_AVAILABLE guard exists so this package remains valid if the front door
is ever removed or is absent in an earlier checkout.

**No production code was modified during the construction of this package.**
**No existing test was weakened.**