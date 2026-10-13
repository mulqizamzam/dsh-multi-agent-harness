# PRD — On-Demand Specialist Pool Expansion

**Project:** Multi-Agent Harness
**Parent System:** DeepSeek Harness `0.1.1-rc.2` — *superseded: the repo pin was re-verified and moved to `0.2.0-rc.2` on 2026-10-09 (README.md §Version pin)*
**PRD Version:** `0.2`
**Status:** Implementation Baseline
**Scope:** Incremental expansion of the on-demand specialist capability pool

---

## 1. Purpose

Extend the existing Multi-Agent Harness from its current seven operational specialist agents to a larger **on-demand specialist capability pool**, without redesigning the established authority model or modifying DSH core.

The existing seven specialists remain the stable baseline:

* **Zeko** — Operations
* **CTO** — Engineering
* **CFO** — Finance
* **Kai** — Research
* **Somad** — Social
* **BadSector** — Adversarial Review
* **Nova** — Writing

The expansion adds narrowly bounded specialist capabilities that the existing pool does not explicitly cover.

All specialists remain **on-demand**. Registration of a specialist does not imply permanent activation, standing authority, or continuous execution.

---

# 2. Problem Statement

The current seven-specialist pool provides broad coverage but leaves several recurring capability gaps:

* independent verification and evidence assessment;
* security engineering;
* architecture analysis;
* failure and recovery analysis;
* policy/specification translation into executable constraints;
* integration and compatibility analysis;
* reliability engineering;
* audit and provenance analysis.

The system requires these capabilities without creating overlapping authority or broadening existing specialist roles unnecessarily.

The solution is to extend the existing pool with narrowly scoped specialists using the same registry, permission, policy, preset, workflow, and test mechanisms already established for the seven baseline agents.

---

# 3. Product Objective

Provide the Orchestrator with a scalable **capability-driven specialist pool**.

The system must be able to:

1. identify required capabilities from task scope;
2. select one or more suitable specialists;
3. delegate bounded work;
4. execute specialists on demand;
5. collect results and evidence;
6. invoke required verification and adversarial review;
7. pass applicable control-plane gates;
8. perform only transitions supported by valid authority.

The system must not require every specialist to participate in every workflow.

---

# 4. Goals

## 4.1 Primary Goals

1. Add new specialist roles without redesigning the existing architecture.
2. Preserve the seven existing specialists as a regression baseline.
3. Define explicit responsibilities and non-responsibilities for every new specialist.
4. Integrate each specialist into:

   * agent registry;
   * permission matrix;
   * DSH preset/toolFilter mapping;
   * role policy;
   * validation and test suite.
5. Support capability-based, on-demand routing.
6. Preserve Human ultimate authority.
7. Preserve delegated-authority boundaries for the Orchestrator.
8. Preserve separation between implementation, verification, adversarial review, and authorization.
9. Preserve DSH version pin `0.2.0-rc.2` *(superseded 2026-10-09: was `0.1.1-rc.2` at v0.2 authoring; re-verified and moved — README.md §Version pin)*.
10. Add lifecycle controls for child execution, failure, cancellation, timeout, and incomplete execution.
11. Require evidence-backed verification before a workflow may claim completion.

## 4.2 Secondary Goals

1. Minimize role overlap.
2. Make specialist additions repeatable.
3. Allow future specialist additions without architectural redesign.
4. Improve control-plane observability and provenance.

---

# 5. Non-Goals

This PRD does not:

1. replace the seven existing specialists;
2. convert specialists into permanently running workers;
3. redesign the Orchestrator architecture;
4. change Human authority;
5. grant the Orchestrator permanent or unrestricted authority;
6. allow specialist self-authorization;
7. permit unrestricted specialist-to-specialist delegation;
8. change the meaning of BadSector `PASS`;
9. treat verification as authorization;
10. treat project state as authority;
11. treat model-generated text as authority;
12. modify DSH core;
13. upgrade DSH beyond the pinned version without re-verification *(pinned `0.2.0-rc.2` since the 2026-10-09 re-verification; was `0.1.1-rc.2`)*;
14. introduce blind automatic retries;
15. permit silent scope expansion.

---

# 6. Canonical Authority Model

The authority model remains:

```text
Human
  │
  ▼
Orchestrator
  │
  ▼
On-Demand Specialist Pool
```

## 6.1 Human

The Human is the ultimate authority.

The Human may:

* approve;
* delegate;
* revoke;
* override.

No specialist may override Human authority.

## 6.2 Orchestrator

The Orchestrator is:

* coordinator;
* workflow owner;
* routing authority within delegated scope;
* delegated decision-maker.

The Orchestrator does **not** possess permanent unrestricted authority.

The Orchestrator may perform an action or authorize a transition only where:

1. the applicable authority has been explicitly delegated;
2. the requested action remains within that delegated scope;
3. required control-plane gates pass.

## 6.3 Specialists

Specialists are peer capabilities.

A specialist may:

* analyze;
* research;
* implement delegated work;
* review;
* verify;
* produce evidence;
* provide recommendations.

A specialist may not:

* self-authorize;
* expand its own scope;
* create standing authority;
* authorize another specialist;
* redefine project policy;
* bypass required gates.

---

# 7. Core Invariants

The following invariants are mandatory.

```text
HUMAN = ultimate authority

ORCHESTRATOR_AUTHORITY = delegated authority only

SPECIALIST_CAPABILITY ≠ AUTHORITY

VERIFIED ≠ AUTHORIZED

BADSECTOR_PASS ≠ AUTHORIZED

MODEL_TEXT ≠ AUTHORITY

PROJECT_STATE ≠ AUTHORITY

REGISTRATION ≠ ACTIVATION

REGISTRATION ≠ STANDING_AUTHORITY

SUBDELEGATION = DENY BY DEFAULT

NO_COMPLETE_WITHOUT_VERIFICATION

NO_BLIND_RETRY

NO_SCOPE_EXPANSION

NO_DSH_CORE_MODIFICATION
```

These invariants must be represented in policy and executable tests where applicable.

---

# 8. Existing Specialist Baseline

The following seven specialists are existing and operational and must be treated as regression baseline:

| Specialist | Domain             | Primary Responsibility                                    |
| ---------- | ------------------ | --------------------------------------------------------- |
| Zeko       | Operations         | Operational execution and operational analysis            |
| CTO        | Engineering        | Engineering implementation and technical decisions        |
| CFO        | Finance            | Financial and resource analysis                           |
| Kai        | Research           | Research and evidence gathering                           |
| Somad      | Social             | Social, audience, stakeholder, and human-context analysis |
| BadSector  | Adversarial Review | Adversarial challenge of proposals/results                |
| Nova       | Writing            | Communication and document production                     |

The expansion must not silently redefine these roles.

---

# 9. New Specialist Roles

The first expansion introduces eight specialists.

## 9.1 Vera — Verification & Evidence

### Purpose

Independently determine whether requirements, claims, outcomes, and completion conditions are supported by sufficient evidence.

### Responsibilities

* acceptance-criteria verification;
* test-result inspection;
* evidence completeness;
* claimed-result validation;
* expected-vs-observed comparison;
* unsupported completion detection.

### Non-responsibilities

* authorization;
* policy creation;
* implementation of the reviewed work;
* adversarial review as a substitute for BadSector.

### Mandatory invariant

```text
Vera verification result ≠ authorization
```

---

## 9.2 Argus — Security Engineering

### Purpose

Assess security properties of systems, workflows, permissions, trust boundaries, and data flows.

### Responsibilities

* threat modeling;
* privilege analysis;
* trust-boundary analysis;
* permission analysis;
* isolation analysis;
* injection analysis;
* security control recommendations.

### Non-responsibilities

* authorization;
* general completion verification;
* unrestricted implementation.

---

## 9.3 Atlas — Architecture

### Purpose

Assess architecture, interfaces, component boundaries, dependencies, and architectural trade-offs.

### Responsibilities

* architecture review;
* dependency-boundary analysis;
* interface analysis;
* coupling analysis;
* component ownership analysis;
* architectural trade-offs;
* consistency checks.

### Non-responsibilities

* replacing CTO;
* authorization;
* adversarial review.

---

## 9.4 Tess — Failure Engineering

### Purpose

Analyze system behavior under failure and degraded execution.

### Responsibilities

* timeout analysis;
* cancellation analysis;
* partial-failure analysis;
* race-condition analysis;
* failure injection;
* degraded-state analysis;
* recovery-path analysis.

### Non-responsibilities

* authorization;
* general security ownership;
* final completion verification.

---

## 9.5 Quill — Policy / Specification Engineering

### Purpose

Translate already-authorized policy and project contracts into explicit, machine-checkable constraints.

### Responsibilities

* policy decomposition;
* invariant definition;
* rule definition;
* schema implications;
* executable-test mapping;
* contract consistency checks.

### Non-responsibilities

* creating policy;
* overruling Human decisions;
* creating authority;
* authorizing state transitions.

### Mandatory invariant

```text
Quill translates authority-approved policy;
Quill does not create policy authority.
```

---

## 9.6 Scout — Integration & Compatibility

### Purpose

Assess compatibility across components, APIs, plugins, dependencies, versions, and environments.

### Responsibilities

* integration analysis;
* API compatibility;
* plugin compatibility;
* dependency compatibility;
* environment compatibility;
* version-drift detection;
* integration test planning.

### Non-responsibilities

* authorization;
* ownership of another specialist;
* unrestricted scope expansion.

---

## 9.7 Talon — Reliability Engineering

### Purpose

Assess system reliability across repetition, retries, restarts, failure, and recovery.

### Responsibilities

* idempotency;
* retry semantics;
* durability;
* rollback;
* recovery semantics;
* repeated-execution consistency;
* reliability failure modes.

### Non-responsibilities

* general operations ownership;
* general security ownership;
* authorization.

---

## 9.8 Ledger — Audit & Provenance

### Purpose

Validate audit integrity, provenance, decision lineage, and traceability.

### Responsibilities

* audit-event validation;
* provenance analysis;
* decision lineage;
* evidence-source linkage;
* state-transition traceability;
* audit completeness.

### Non-responsibilities

* creating authority;
* approving state transitions;
* altering audit history outside approved mechanisms.

---

# 10. Specialist Pool

The resulting pool is:

```text
SPECIALIST POOL
│
├── DOMAIN
│   ├── Zeko
│   ├── CTO
│   ├── CFO
│   ├── Kai
│   ├── Somad
│   └── Nova
│
├── ASSURANCE
│   ├── Vera
│   ├── Quill
│   └── Ledger
│
├── TECHNICAL ASSURANCE
│   ├── Argus
│   ├── Atlas
│   ├── Scout
│   ├── Talon
│   └── Tess
│
└── ADVERSARIAL
    └── BadSector
```

Target roster after this expansion: **15 specialists**.

`15` is a roster count, not an architectural limit.

---

# 11. BadSector Boundary

BadSector remains the adversarial specialist.

BadSector:

* reviews;
* challenges;
* attempts to falsify;
* identifies weaknesses;
* identifies overlooked failure modes.

BadSector does not:

* authorize;
* become the final authority;
* execute the plan it is reviewing.

The following statement remains mandatory:

```text
BadSector PASS ≠ authorization
```

No additional execution exception is introduced by this PRD.

---

# 12. DSH Boundary

DSH-native controls remain one enforcement layer of a larger control architecture.

The three layers remain:

```text
Human authority
        +
Project control plane
        +
DSH-native enforcement
```

DSH `toolFilter` and related subagent configuration are used for capability shaping and execution constraints.

They must **not** be treated as the sole authority boundary.

The project control plane remains responsible for:

* role definition;
* delegation;
* authorization;
* scope;
* state transitions;
* audit requirements;
* gate evaluation.

DSH version remains pinned to:

```text
0.2.0-rc.2  (re-verified 2026-10-09; was 0.1.1-rc.2 at v0.2 authoring)
```

Any later release requires explicit re-verification before adoption.

---

# 13. On-Demand Lifecycle

A specialist follows this conceptual lifecycle:

```text
REGISTERED
   │
   ▼
SELECTED
   │
   ▼
DELEGATED
   │
   ▼
INVOKED
   │
   ▼
RUNNING
   │
   ├──── SUCCESS
   │
   ├──── FAILURE
   │
   ├──── CANCELLED
   │
   ├──── TIMEOUT
   │
   └──── BLOCKED / INCOMPLETE
          │
          ▼
       COLLECT
          │
          ▼
      VERIFICATION
          │
          ▼
      REQUIRED GATES
```

A specialist is not considered successfully completed merely because invocation occurred.

The parent workflow must distinguish at minimum:

```text
SUCCESS
FAILURE
CANCELLED
TIMEOUT
BLOCKED
INCOMPLETE
```

No terminal state may be falsely interpreted as successful completion.

---

# 14. Failure and Cancellation Requirements

The system must handle:

1. specialist timeout;
2. specialist cancellation;
3. child execution failure;
4. blocked/stuck execution;
5. partial result;
6. missing completion signal;
7. parent workflow continuing after specialist failure;
8. stale or incomplete specialist state.

The following must be prohibited:

```text
child failure → implicit success
missing completion → implicit success
partial evidence → COMPLETE
timeout → blind retry
```

Retry behavior, where separately authorized, must remain explicit and bounded.

---

# 15. Capability Routing

The Orchestrator selects specialists according to task capability requirements.

Conceptual flow:

```text
TASK
  │
  ▼
INTENT / SCOPE ANALYSIS
  │
  ▼
CAPABILITY REQUIREMENTS
  │
  ▼
SPECIALIST SELECTION
  │
  ▼
BOUNDED DELEGATION
  │
  ▼
ON-DEMAND EXECUTION
  │
  ▼
RESULT COLLECTION
  │
  ├──── VERIFICATION
  │
  └──── ADVERSARIAL REVIEW
  │
  ▼
CONTROL-PLANE GATES
  │
  ▼
AUTHORIZED ACTION / STATE TRANSITION
```

Not every task requires every specialist.

Default behavior should be **minimum sufficient specialist set**.

---

# 16. Example Routing

## 16.1 Policy Change

Possible specialists:

```text
Kai
  research evidence

Quill
  translate approved policy into rules/invariants

Atlas
  assess architectural impact

CTO
  implement

Argus
  security review

Vera
  verify requirements and evidence

Ledger
  verify provenance/audit implications

BadSector
  adversarial challenge
```

The exact set is determined by task scope.

---

## 16.2 Reliability Incident

Possible specialists:

```text
Zeko
  operational diagnosis

Talon
  reliability analysis

Tess
  failure analysis

CTO
  remediation

Vera
  verification

BadSector
  adversarial challenge
```

---

## 16.3 Integration Change

Possible specialists:

```text
Scout
  compatibility analysis

Atlas
  architectural fit

Argus
  security boundary

CTO
  implementation

Vera
  integration verification
```

---

# 17. Implementation Structure

For every new specialist `<agent>`:

```text
agents/<agent>/
├── AGENT.md
└── policy.yaml
```

Required central integration points:

```text
config/agents.yaml
config/permissions.yaml
config/role-preset-mapping.yaml
```

Potential validation/schema changes:

```text
schemas/
```

Required test integration:

```text
tests/unit/
tests/authorization/
tests/adversarial/
tests/workflow/
tests/scenarios/
```

Existing control-plane helper mechanisms under:

```text
state/
audit/
```

must be reused rather than bypassed.

---

# 18. Configuration Requirements

Each new specialist must have:

* stable identifier;
* unique role name;
* capability set;
* explicit lifecycle designation;
* explicit permission set;
* role-specific policy;
* DSH preset/toolFilter mapping;
* delegation constraints;
* applicable verification requirements.

No specialist should inherit broader permissions merely because another specialist has them.

---

# 19. Permission Requirements

Permission definitions must use least privilege.

For each specialist:

```text
role
  →
required capabilities
  →
required tools
  →
allowed operations
  →
explicitly prohibited operations
```

Negative authorization tests are required for sensitive boundaries.

---

# 20. Verification Requirements

Every new specialist requires test coverage validating:

1. correct invocation;
2. correct tool/capability access;
3. denied unauthorized access;
4. bounded delegation;
5. scope preservation;
6. expected result collection;
7. correct failure behavior;
8. cancellation/timeout behavior where applicable.

Verification itself must not imply authorization.

The project retains:

```text
NO COMPLETE WITHOUT VERIFICATION
```

---

# 21. Audit and Provenance Requirements

Specialist activity must remain traceable.

At minimum, the control plane must be able to associate:

```text
initiating authority
        ↓
workflow
        ↓
specialist
        ↓
delegated scope
        ↓
capability/tool boundary
        ↓
execution result
        ↓
evidence
        ↓
verification
        ↓
resulting decision/state transition
```

State must not be treated as proof of authority by itself.

Audit records must not become mutable evidence simply because current project state says an action occurred.

---

# 22. Regression Requirements

The seven existing specialists constitute the regression baseline.

Adding the new pool must not silently change:

* role boundaries;
* permissions;
* toolFilter behavior;
* authority semantics;
* BadSector semantics;
* workflow assumptions;
* state invariants;
* audit invariants.

Regression suite must verify all seven existing specialists remain functional after expansion.

---

# 23. Security Requirements

The expansion must test for:

* privilege escalation;
* capability leakage;
* unauthorized tool access;
* scope expansion;
* specialist impersonation;
* unauthorized nested delegation;
* stale delegation;
* state/audit divergence;
* false completion;
* result spoofing;
* verification spoofing;
* authority confusion.

Particular attention must be given to:

```text
model output → mistaken as authority
project state → mistaken as authority
verification → mistaken as authorization
BadSector PASS → mistaken as authorization
toolFilter → mistaken as complete security boundary
```

---

# 24. Implementation Phases

## Phase A — Role Definitions

Deliver:

```text
8 AGENT.md files
8 policy.yaml files
responsibility boundaries
non-responsibility boundaries
capability definitions
role-overlap review
```

## Phase B — Registry and Permissions

Deliver:

```text
agents.yaml updates
permissions.yaml updates
role-preset-mapping.yaml updates
required schema changes
```

## Phase C — Assurance Integration

Deliver:

```text
Vera
Quill
Ledger
```

with unit, authorization, isolation, adversarial, and workflow tests.

## Phase D — Technical Specialist Integration

Deliver:

```text
Argus
Atlas
Scout
Talon
Tess
```

with corresponding role, permission, policy, and workflow coverage.

## Phase E — Workflow Integration

Deliver:

```text
capability-driven routing
on-demand invocation
fan-out/collect integration
verification integration
audit integration
failure-state handling
```

## Phase F — Hardening

Deliver:

```text
scope-expansion tests
nested-delegation tests
timeout tests
cancellation tests
failure propagation tests
false-completion tests
state/audit consistency tests
regression suite
```

---

# 25. Acceptance Criteria

The expansion is accepted only when all required criteria pass.

## 25.1 Specialist Registration

* All eight new specialists are registered.
* Every specialist has a unique identifier.
* Every specialist has a bounded role.
* Registration does not activate the specialist permanently.

## 25.2 Authority

* Human remains ultimate authority.
* Orchestrator acts only within delegated authority.
* Specialists cannot self-authorize.
* Specialists cannot create standing authority.
* Specialist results cannot independently authorize state transitions.

## 25.3 Permissions

* Every specialist has explicit permissions.
* Unauthorized capabilities are denied.
* Existing seven specialist permissions remain unchanged unless explicitly approved.

## 25.4 DSH

* Each specialist maps to a valid DSH preset/toolFilter configuration.
* DSH remains pinned to `0.2.0-rc.2` *(re-verified 2026-10-09; was `0.1.1-rc.2` at v0.2 authoring — README.md §Version pin)*.
* No DSH core modification is required.
* ToolFilter is not treated as the sole authorization/security boundary.

## 25.5 Workflow

* Every new specialist can be invoked on demand.
* Delegation scope is recorded.
* Results can be collected.
* Failure is propagated correctly.
* Cancellation is propagated correctly.
* Timeout is represented correctly.
* Blocked/incomplete execution cannot become successful completion.

## 25.6 Verification

* Every new specialist has verification coverage.
* Verification is distinguishable from authorization.
* No COMPLETE state is accepted without required verification evidence.

## 25.7 BadSector

* BadSector remains adversarial reviewer only.
* BadSector cannot authorize.
* BadSector cannot execute the plan under review.
* `PASS` does not imply authorization.

## 25.8 Audit

* Specialist invocation is auditable.
* Delegated scope is auditable.
* Evidence provenance is preserved.
* State and audit remain consistent.

## 25.9 Regression

* All seven existing specialists pass regression.
* Existing authority boundaries remain intact.
* Existing workflows remain valid.
* No existing safety invariant is weakened.

---

# 26. Success Criteria

The expansion is successful when:

1. The 15-specialist roster is registered.
2. All 15 specialists can be invoked on demand.
3. Capability routing can select only the specialists required by a task.
4. Existing seven specialists remain behaviorally compatible.
5. No specialist introduces unauthorized authority.
6. Verification remains independent from implementation.
7. Adversarial review remains independent from authorization.
8. Failure, cancellation, timeout, and incomplete execution are represented safely.
9. Audit/provenance remains intact.
10. No DSH core modification is needed.
11. Future specialist additions can reuse the same extension pattern.

---

# 27. Reference Specialist Extension Pattern

A future specialist must follow:

```text
DEFINE ROLE
    ↓
DEFINE RESPONSIBILITIES
    ↓
DEFINE NON-RESPONSIBILITIES
    ↓
DEFINE CAPABILITIES
    ↓
DEFINE PERMISSIONS
    ↓
DEFINE DSH PRESET / TOOLFILTER
    ↓
REGISTER
    ↓
TEST POSITIVE CAPABILITIES
    ↓
TEST NEGATIVE CAPABILITIES
    ↓
TEST AUTHORITY BOUNDARY
    ↓
TEST LIFECYCLE
    ↓
RUN FULL REGRESSION
    ↓
ACTIVATE AS ON-DEMAND CAPABILITY
```

This pattern is the intended extensibility mechanism.

---

# 28. Final Architecture

```text
                           HUMAN
                     ultimate authority
                            │
                            ▼
                     ORCHESTRATOR
              routing / delegation / gates
                            │
                            ▼
              ON-DEMAND SPECIALIST POOL
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
      DOMAIN             ASSURANCE          TECHNICAL
        │                   │                   │
 Zeko CTO CFO           Vera Quill          Argus Atlas
 Kai Somad Nova         Ledger              Scout Talon
                                              Tess
        │
        └───────────────────┬───────────────────┘
                            │
                     ADVERSARIAL REVIEW
                            │
                        BadSector
                            │
                            ▼
                  CONTROL-PLANE GATES
                            │
                            ▼
                AUTHORIZED STATE TRANSITION
```

The governing principle is:

> **Capability may be delegated on demand. Authority may not be inferred from capability, verification, state, or model output.**

The seven existing specialists remain the stable operational baseline. The eight new specialists extend capability coverage without changing the underlying authority model.
