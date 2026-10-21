# validate_config.py — config/invariant/schema validation (module form)
#
# This module implements the validation referenced by config/agents.yaml and
# config/permissions.yaml ("enforced by tests/validate-config.py"). It is
# importable by pytest (tests/unit/test_config.py) and by the standalone
# wrapper tests/validate-config.py (hyphenated) which is the file the configs
# name. It NEVER executes anything consequential — it only reads and validates.
#
# Version pin: DeepSeek Harness 0.2.1-rc.2 (tool names verified).

import os
import re
import sys

import yaml

# Safe constructor for DSH's !!js YAML tag (used in preset drafts like
# `disabled: !!js process.platform === 'win32'`): parse as an opaque string,
# never evaluate. This lets the validator read agent.cordis.yml drafts without
# executing anything.
def _js_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return str(loader.construct_scalar(node))
    if isinstance(node, yaml.SequenceNode):
        return str(loader.construct_sequence(node))
    return str(loader.construct_mapping(node))

yaml.SafeLoader.add_constructor('tag:yaml.org,2002:js', _js_constructor)

try:
    import jsonschema
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:  # pragma: no cover - degraded mode without jsonschema
    jsonschema = None
    Draft202012Validator = None
    ValidationError = Exception

# ---------------------------------------------------------------------------
# Tool catalog — verified against DSH 0.2.1-rc.2 (docs/tool-catalog.md).
# Mirrored here so validation runs without loading the docs.
#
# The fifteen `subagent_<id>` names are GONE. DSH 0.2.1-rc.2 collapsed the
# per-role `tool-subagent` instances into ONE delegation tool (`subagent`) and
# removed the per-instance `persona` / `toolFilter` config keys, so a role is
# selected by the model-facing `agent_preset` argument, not by a tool name.
# A preset-bound child's tool surface is the tool PLUGINS its preset mounts.
#
# `present` added 2026-10-11: verified against the running 0.2.0-rc.2 harness
# (packages/deliverables/tool-present/src/index.ts registers the tool name
# 'present'); carried into the orchestrator preset by the Human-approved
# re-derivation the same day.
# ---------------------------------------------------------------------------
VERIFIED_TOOLS = frozenset("""
ask_user_question bash cordis_define cordis_inspect_list cordis_inspect_query
cordis_inspect_self cordis_run cordis_stop cordis_undefine create_goal edit
exit_plan_mode followup_task get_goal glob grep interrupt_agent job_kill
job_list job_output list_agents lsp present pwsh ralph read read_image report run_code
schedule_create schedule_delete schedule_list send_message session_event_read
session_event_search session_event_trace session_search session_trace skill
spawn_teammate str_replace_editor subagent subagent_fork team_task_create
team_task_get team_task_list team_task_update terminal_close terminal_list
terminal_open terminal_read terminal_send terminal_signal todo_write update_goal
wait_agent web_fetch web_search workflow write
""".split())

# The tool PLUGINS a role preset mounts, and the tools each one exposes.
# `tool-fs` and `tool-web` narrow themselves per tool in 0.2.1-rc.2, so the
# exposed set depends on the row's own config — see `preset_tool_surface`.
TOOL_PLUGIN_BY_TOOL = {
    "bash": "@deepseek-ai/dsh-tool-bash",
    "read": "@deepseek-ai/dsh-tool-fs",
    "read_image": "@deepseek-ai/dsh-tool-fs",
    "write": "@deepseek-ai/dsh-tool-fs",
    "edit": "@deepseek-ai/dsh-tool-fs",
    "glob": "@deepseek-ai/dsh-tool-fs-search",
    "grep": "@deepseek-ai/dsh-tool-fs-search",
    "job_kill": "@deepseek-ai/dsh-tool-jobs",
    "job_list": "@deepseek-ai/dsh-tool-jobs",
    "job_output": "@deepseek-ai/dsh-tool-jobs",
    "skill": "@deepseek-ai/dsh-tool-skill",
    "exit_plan_mode": "@deepseek-ai/dsh-plan-mode",
    "web_search": "@deepseek-ai/dsh-tool-web",
    "web_fetch": "@deepseek-ai/dsh-tool-web",
    "todo_write": "@deepseek-ai/dsh-tool-todo",
}

# Baseline seven first, then the PRD v0.2 expansion eight (ADR 0003 D1 order).
BASELINE_IDS = ("zeko", "cto", "cfo", "kai", "somad", "badsector", "nova")
EXPANSION_IDS = ("vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger")
SPECIALIST_IDS = set(BASELINE_IDS) | set(EXPANSION_IDS)
# Delegation tools a specialist must never hold in ALLOW. Since 0.2.1-rc.2
# there is ONE delegation tool per provider, so there is no per-sibling tool
# to name: subdelegation DENY BY DEFAULT is structural — a specialist's preset
# mounts no delegation plugin at all, and the delegation tool's maxDepth: 1
# rejects a second hop.
DELEGATION_TOOLS = {
    "subagent", "subagent_fork", "send_message", "interrupt_agent",
    "list_agents", "workflow", "ralph",
}
WRITE_EXEC_TOOLS = {"bash", "edit", "write", "str_replace_editor", "run_code", "pwsh"}
# Permission-matrix vocabulary (config/permissions.yaml, PRD §8 normalized)
CAPABILITY_VALUES = {"yes", "scoped", "review", "approval", "scoped_approval", "no"}
# The in-force DeepSeek Harness pin, defined ONCE here and cross-checked
# against config/role-preset-mapping.yaml, all 15 agents/<id>/policy.yaml and
# orchestrator/policy.yaml below. A pin bump moves this constant and the 16
# policy files together.
VERSION_PIN = "deepseek-harness-0.2.1-rc.2"
# Protected paths per ADR 0002 (any write targeting these by a non-writer DENY)
PROTECTED_PATHS = ("state/registry/", "audit/")
# Invariants every role policy must declare (security spec + ADR 0002)
REQUIRED_POLICY_INVARIANTS = ("no_self_delegation", "subdelegation_deny_by_default")


def _composition_rows(path):
    """Every plugin row of one Agent Preset composition, groups flattened."""
    comp = load_yaml(path)
    rows = list(comp) if isinstance(comp, list) else []
    for row in rows:
        if row.get("group"):
            rows.extend(row.get("config") or [])
    return rows


def preset_tool_surface(path):
    """The tools one Agent Preset composition exposes to the agent it composes.

    A preset narrows by COMPOSITION: the tool PLUGINS it mounts, each with its
    own per-tool config applied. 0.2.1-rc.2 gave the two multi-tool plugins
    this roster uses that granularity (`tool-fs`: read / readImage / write /
    edit; `tool-web`: search / fetch), so the exposed set is exactly the tool
    list the role's allow list named before the per-instance `toolFilter` was
    removed from the host.

    A row disabled by a `!!js` platform condition (tool-bash on win32) is
    counted as enabled: the condition is opaque to this reader.
    @param path - the composition file.
    @returns The exposed tool names.
    """
    exposed = set()
    for row in _composition_rows(path):
        name = row.get("name")
        cfg = row.get("config") or {}
        if name == "@deepseek-ai/dsh-tool-bash":
            exposed.add("bash")
        elif name == "@deepseek-ai/dsh-tool-fs":
            if cfg.get("read", True):
                exposed.add("read")
            if cfg.get("readImage", True):
                exposed.add("read_image")
            if cfg.get("write", True):
                exposed.add("write")
            if cfg.get("edit", True):
                exposed.add("edit")
        elif name == "@deepseek-ai/dsh-tool-fs-search":
            exposed.update({"glob", "grep"})
        elif name == "@deepseek-ai/dsh-tool-jobs":
            exposed.update({"job_kill", "job_list", "job_output"})
        elif name == "@deepseek-ai/dsh-tool-skill":
            exposed.add("skill")
        elif name == "@deepseek-ai/dsh-plan-mode":
            exposed.add("exit_plan_mode")
        elif name == "@deepseek-ai/dsh-tool-web":
            if cfg.get("search", True):
                exposed.add("web_search")
            if cfg.get("fetch", True):
                exposed.add("web_fetch")
        elif name == "@deepseek-ai/dsh-tool-todo":
            exposed.add("todo_write")
    return exposed


def project_root():
    """The multi-agent-harness project root (two levels up from this file's dir)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_yaml(path):
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def load_json(path):
    import json
    with open(path, "r") as fh:
        return json.load(fh)


def all_failures(root=None):
    """Run every check; return a list of failure strings (empty = all pass)."""
    root = root or project_root()
    failures = []
    results = run_checks(root)
    for name, ok, detail in results:
        if not ok:
            failures.append(f"{name}: {detail}")
    return failures


def run_checks(root):
    """Run every check; return [(name, ok, detail), ...]."""
    out = []

    def check(name, ok, detail=""):
        out.append((name, bool(ok), detail))

    # --- load everything ---------------------------------------------------
    cfg_root = os.path.join(root, "config")
    agents_path = os.path.join(cfg_root, "agents.yaml")
    perms_path = os.path.join(cfg_root, "permissions.yaml")
    mapping_path = os.path.join(cfg_root, "role-preset-mapping.yaml")
    schemas_dir = os.path.join(root, "schemas")
    agents_dir = os.path.join(root, "agents")

    try:
        agents = load_yaml(agents_path)
    except Exception as e:
        check("agents.yaml parse", False, str(e))
        return out
    perms = load_yaml(perms_path)
    mapping = load_yaml(mapping_path)
    policies = {}
    for rid in sorted(SPECIALIST_IDS):
        p = os.path.join(agents_dir, rid, "policy.yaml")
        try:
            policies[rid] = load_yaml(p)
        except Exception as e:
            policies[rid] = {}
            check(f"agents/{rid}/policy.yaml load", False, str(e))
    # The orchestrator is bound to the root session, so it has no agents/<id>/
    # directory and role-definition.schema.json closes `role` to the fifteen
    # specialist ids: it gets its own file and its own schema.
    try:
        orch_policy = load_yaml(os.path.join(root, "orchestrator", "policy.yaml")) or {}
    except Exception as e:
        orch_policy = {}
        check("orchestrator/policy.yaml load", False, str(e))

    schemas = {}
    for fn in os.listdir(schemas_dir):
        if fn.endswith(".schema.json"):
            schemas[fn] = load_json(os.path.join(schemas_dir, fn))

    # --- schema conformance ------------------------------------------------
    if Draft202012Validator is not None:
        def schema_valid(doc, schema_key, label):
            sch = schemas.get(schema_key)
            if sch is None:
                return check(f"{label} schema missing", False, schema_key)
            try:
                Draft202012Validator(sch).validate(doc)
                check(f"{label} schema", True)
            except ValidationError as e:
                check(f"{label} schema", False, f"{e.message} at {list(e.absolute_path)}")

        schema_valid(agents, "agent-registry.schema.json", "agents.yaml")
        schema_valid(mapping, "role-mapping.schema.json", "role-preset-mapping.yaml")
        for rid, pol in policies.items():
            schema_valid(pol, "role-definition.schema.json", f"agents/{rid}/policy.yaml")
        schema_valid(orch_policy, "orchestrator-policy.schema.json", "orchestrator/policy.yaml")
    else:  # pragma: no cover
        check("jsonschema available", False, "jsonschema not installed; schema checks skipped")

    # --- registry invariants (agents.yaml) ---------------------------------
    reg_inv = agents.get("invariants", {})
    ag = agents.get("agents", [])
    check("registry 15 specialists", len(ag) == 15, f"{len(ag)}")
    check("registry specialist ids", {a["id"] for a in ag} == SPECIALIST_IDS)
    check("registry unique ids", len({a["id"] for a in ag}) == 15)
    check("registry specialist_count invariant",
          reg_inv.get("specialist_count") == 15, f"{reg_inv.get('specialist_count')}")
    check("registry orchestrator coordination", agents.get("orchestrator", {}).get("kind") == "coordination")
    check("registry orchestrator id", agents.get("orchestrator", {}).get("id") == "orchestrator")
    check("registry peer_relationship", reg_inv.get("peer_relationship") is True)
    check("registry badsector reviewer", reg_inv.get("badsector_is_reviewer_not_authorizer") is True)
    check("registry zeko operations", reg_inv.get("zeko_is_operations_not_supervisor") is True)
    check("registry orchestrator not 8th", reg_inv.get("orchestrator_is_coordination_not_eighth_specialist") is True)
    check("registry role_mapping ref", os.path.exists(os.path.join(root, agents.get("role_mapping", ""))))
    for a in ag:
        check(f"registry {a['id']} policy exists", os.path.exists(os.path.join(root, a.get("default_policy", ""))))

    # --- permission-matrix invariants (permissions.yaml) -------------------
    perm_inv = perms.get("invariants", {})
    caps = perms.get("capabilities", {})
    check("perm no self-grant", perm_inv.get("no_agent_grants_itself_authority") is True)
    check("perm badsector never executes",
          perm_inv.get("badsector_never_executes") is True and
          caps.get("adversarial_review", {}).get("badsector") == "yes")
    check("perm kai never executes", perm_inv.get("kai_never_executes") is True)
    check("perm cfo no transaction", perm_inv.get("cfo_no_transaction_by_default") is True and
          caps.get("financial_transaction", {}).get("cfo") == "no")
    check("perm destructive approval/denied",
          perm_inv.get("destructive_always_requires_approval_or_denied") is True and
          all(caps.get("destructive_action", {}).get(rid) in ("approval", "no") for rid in SPECIALIST_IDS))

    # --- permission-matrix shape hardening ---------------------------------
    # Every capability must use the closed vocabulary and cover all 7 agents.
    perm_agents = set(perms.get("agents", []))
    check("perm agents list matches specialists", perm_agents == SPECIALIST_IDS,
          f"{perm_agents ^ SPECIALIST_IDS}")
    for cap, row in caps.items():
        bad_values = {v for v in row.values() if v not in CAPABILITY_VALUES}
        check(f"perm {cap} vocabulary", not bad_values, f"{bad_values}")
        missing = SPECIALIST_IDS - set(row.keys())
        check(f"perm {cap} covers all agents", not missing, f"missing {missing}")
    # Read-only sandbox intent must be paired with approval never (least
    # privilege: a read-only role cannot request an escalation/approval ask).
    for rid, defaults in perms.get("agent_defaults", {}).items():
        if defaults.get("sandbox") == "read-only":
            check(f"perm {rid} read-only approval never", defaults.get("approval") == "never",
                  f"{defaults.get('approval')}")

    # --- PRD v0.2 expansion hardening (ADR 0003) ----------------------------
    # (a) adversarial_review is reserved to badsector: no other specialist may
    #     hold it in any form (reviewers of record stay singular).
    adv = caps.get("adversarial_review", {})
    for rid in sorted(SPECIALIST_IDS - {"badsector"}):
        check(f"perm adversarial_review reserved (not {rid})", adv.get(rid) == "no",
              f"{adv.get(rid)!r}")
    # (b) every expansion analyst is a read-only/never sandbox role.
    defaults_map = perms.get("agent_defaults", {})
    for rid in EXPANSION_IDS:
        d = defaults_map.get(rid, {})
        check(f"perm {rid} defaults read-only", d.get("sandbox") == "read-only",
              f"{d.get('sandbox')!r}")
        check(f"perm {rid} defaults approval never", d.get("approval") == "never",
              f"{d.get('approval')!r}")
    # (c) every specialist policy declares never_authorizes (AUTH-INV-13: a
    #     specialist's PASS/verdict is data, never authorization).
    for rid, pol in policies.items():
        check(f"{rid} never_authorizes invariant declared",
              pol.get("invariants", {}).get("never_authorizes") is True)

    # --- role→policy→mapping consistency -----------------------------------
    mapped_roles = {r["id"]: r for r in mapping.get("roles", [])}
    check("mapping covers all roles", set(mapped_roles) == SPECIALIST_IDS)
    for rid, entry in mapped_roles.items():
        ts = entry.get("tool_surface", {})
        allow, deny = set(ts.get("allow", [])), set(ts.get("deny", []))
        pol = policies.get(rid, {})
        pol_ts = pol.get("tool_surface", {})
        check(f"{rid} allow∩deny=∅", not (allow & deny), f"{allow & deny}")
        check(f"{rid} mapping==policy allow", allow == set(pol_ts.get("allow", [])),
              f"{allow ^ set(pol_ts.get('allow', []))}")
        check(f"{rid} mapping==policy deny", deny == set(pol_ts.get("deny", [])),
              f"{deny ^ set(pol_ts.get('deny', []))}")
        unknown = (allow | deny) - VERIFIED_TOOLS
        check(f"{rid} tool names verified", not unknown, f"{unknown}")
        check(f"{rid} no delegation tools", not (allow & DELEGATION_TOOLS), f"{allow & DELEGATION_TOOLS}")
        ti = entry.get("tool_instance", {})
        check(f"{rid} max_depth 1", ti.get("max_depth") == 1)
        check(f"{rid} provider spawn", ti.get("provider") == "spawn")
        check(f"{rid} tool_name is the single delegation tool",
              ti.get("tool_name") == "subagent", f"{ti.get('tool_name')!r}")
        check(f"{rid} agent_preset names its own preset",
              ti.get("agent_preset") == entry.get("preset"),
              f"{ti.get('agent_preset')!r} != {entry.get('preset')!r}")
        # read-only roles have no write/exec tools
        if pol.get("sandbox_approval_intent", {}).get("sandbox") == "read-only":
            check(f"{rid} read-only no write tools", not (allow & WRITE_EXEC_TOOLS), f"{allow & WRITE_EXEC_TOOLS}")

    # --- capability discriminators (2026-09-07, Human-approved) -------------
    # (a) capabilities.code_write == 'no' is ENFORCEABLE, not advisory: such a
    #     role must not hold edit/write in its allow set, regardless of
    #     sandbox intent (closes the gap where no enforcement layer read the
    #     matrix — zeko held a code-mutation surface identical to cto).
    code_write = caps.get("code_write", {})
    for rid in SPECIALIST_IDS:
        if code_write.get(rid) == "no":
            a = set(mapped_roles.get(rid, {}).get("tool_surface", {}).get("allow", []))
            bad = a & {"edit", "write"}
            check(f"{rid} code_write=no excludes edit/write from allow", not bad, f"{bad}")

    # (b) allow-set uniqueness: two roles with identical allow sets have no
    #     tool-layer boundary between them. Identical sets are only allowed
    #     inside a declared tool_surface_equivalence group (permissions.yaml),
    #     and every declared group must actually share one allow set.
    declared_groups = [set(g) for g in perms.get("tool_surface_equivalence", [])]
    by_allow: dict = {}
    for rid, entry in mapped_roles.items():
        a = frozenset(entry.get("tool_surface", {}).get("allow", []))
        by_allow.setdefault(a, set()).add(rid)
    for a, rids in by_allow.items():
        if len(rids) < 2:
            continue
        covered = any(rids <= g for g in declared_groups)
        check(f"identical allow set declared {sorted(rids)}", covered,
              f"{sorted(rids)} not covered by tool_surface_equivalence")
    for i, g in enumerate(declared_groups):
        member_sets = {frozenset(mapped_roles[r]["tool_surface"]["allow"])
                       for r in g if r in mapped_roles}
        check(f"tool_surface_equivalence[{i}] shares allow set",
              len(member_sets) <= 1, f"{[sorted(s) for s in member_sets]}")

    # --- orchestrator mapping ----------------------------------------------
    orch = mapping.get("orchestrator", {})
    orch_ts = orch.get("tool_surface", {})
    orch_allow = set(orch_ts.get("allow", []))
    orch_deny = set(orch_ts.get("deny", []))
    check("orchestrator delegation tools in allow", set(orch.get("delegation_tools", [])) <= orch_allow)
    check("orchestrator allow∩deny=∅", not (orch_allow & orch_deny), f"{orch_allow & orch_deny}")
    check("orchestrator tool names verified", not ((orch_allow | orch_deny) - VERIFIED_TOOLS),
          f"{(orch_allow | orch_deny) - VERIFIED_TOOLS}")
    # The delegation surface is the ONE `subagent` tool since 0.2.1-rc.2: the
    # fifteen per-role `subagent_<id>` tools no longer exist, so a role is
    # reached through the model-facing `agent_preset` argument instead.
    check("orchestrator allow names the single delegation tool", "subagent" in orch_allow)
    per_role_tools = {f"subagent_{r}" for r in SPECIALIST_IDS}
    check("orchestrator allow names no per-role delegation tool",
          not (orch_allow & per_role_tools),
          f"{sorted(orch_allow & per_role_tools)}")

    # --- orchestrator policy (declaration ↔ mapping consistency) ------------
    # orchestrator/policy.yaml COPIES the mapping's tool_filter; without these
    # checks the copy is prose that can silently diverge from the config.
    orch_pol_ts = orch_policy.get("tool_surface", {})
    pol_allow = set(orch_pol_ts.get("allow", []))
    pol_deny = set(orch_pol_ts.get("deny", []))
    check("orchestrator policy allow∩deny=∅", not (pol_allow & pol_deny), f"{pol_allow & pol_deny}")
    check("orchestrator mapping==policy allow", pol_allow == orch_allow, f"{pol_allow ^ orch_allow}")
    check("orchestrator mapping==policy deny", pol_deny == orch_deny, f"{pol_deny ^ orch_deny}")
    orch_pol_deleg = orch_policy.get("delegation", {})
    check("orchestrator mapping==policy delegation_tools",
          set(orch_pol_deleg.get("delegation_tools", [])) == set(orch.get("delegation_tools", [])),
          f"{set(orch_pol_deleg.get('delegation_tools', [])) ^ set(orch.get('delegation_tools', []))}")
    # Same invariant the specialist section asserts (ADR 0002), plus the V1
    # subdelegation rule the mapping's consistency_rules declare for the root
    # session: the orchestrator must be the only delegator and may not delegate
    # to itself.
    check("orchestrator no_self_delegation invariant declared",
          orch_policy.get("invariants", {}).get("no_self_delegation") is True,
          f"{orch_policy.get('invariants', {}).get('no_self_delegation')!r}")
    check("orchestrator delegation_orchestrator_only declared",
          orch_pol_deleg.get("delegation_orchestrator_only") is True,
          f"{orch_pol_deleg.get('delegation_orchestrator_only')!r}")

    # --- per-role no_self_delegation declaration ----------------------------
    # What this block actually verifies: every specialist policy DECLARES the
    # no_self_delegation invariant (a role cannot expand its own scope or
    # delegate to itself); the delegation layer enforces it
    # (control/delegation.py). It is not a protected-path check — no role
    # policy declares any protected-path invariant. ADR 0002's protected-path
    # discipline is enforced in code, not declared in role policies:
    # control/execution_gate.py (classify_target/authorize_write) DENYs any
    # non-writer write targeting state/registry/, audit/, or state/projects/.
    for rid, pol in policies.items():
        check(f"{rid} no_self_delegation invariant declared",
              pol.get("invariants", {}).get("no_self_delegation") is True)

    # --- version pin cross-check --------------------------------------------
    # One in-force pin everywhere: the mapping, all 15 role policies and the
    # orchestrator policy. schemas/role-definition.schema.json only requires
    # the `^deepseek-harness-` prefix, so without these equality checks any
    # pin string would validate and the 16 policies could drift apart
    # silently. (It happened: 15 policies + orchestrator carried
    # 0.1.1-rc.2 while the mapping carried 0.2.0-rc.2.)
    check("mapping version_pin", mapping.get("version_pin") == VERSION_PIN,
          f"{mapping.get('version_pin')!r} != {VERSION_PIN!r}")
    for rid, pol in policies.items():
        check(f"{rid} version_pin", pol.get("version_pin") == VERSION_PIN,
              f"{pol.get('version_pin')!r} != {VERSION_PIN!r}")
    check("orchestrator version_pin",
          orch_policy.get("version_pin") == VERSION_PIN,
          f"{orch_policy.get('version_pin')!r} != {VERSION_PIN!r}")

    # --- Phase 1C draft artifacts (mounted 2026-09-07, Human-approved D4/D7) -
    draft = mapping.get("draft_artifacts", {})
    check("draft status is mounted", draft.get("status") == "mounted")
    check("draft mount_required false", draft.get("mount_required") is False)
    check("draft instances file exists", os.path.exists(os.path.join(root, draft.get("instances_draft_path", ""))))
    check("draft preset ref valid", "agent.cordis.yml" in draft.get("preset_draft_path", ""))

    instances = load_yaml(os.path.join(root, "config", "tool-subagent-instances.yaml"))
    check("instances status mounted", instances.get("status") == "mounted")

    # --- the ONE delegation tool (0.2.1-rc.2) --------------------------------
    # The host removed the per-instance persona / toolFilter config keys and
    # collapsed the fifteen per-role instances into a single delegation tool
    # whose model-facing `agent_preset` argument selects the role preset.
    insert = instances.get("insert_draft", [])
    check("instances count 1 (one delegation tool)", len(insert) == 1, f"{len(insert)}")
    if insert:
        cfg = insert[0].get("config", {})
        check("delegation row provider spawn", cfg.get("provider") == "spawn")
        check("delegation row toolName subagent", cfg.get("toolName") == "subagent")
        check("delegation row maxDepth 1", cfg.get("maxDepth") == 1)
        for removed in ("persona", "toolFilter", "backgroundMode", "enableRunInBackground"):
            check(f"delegation row has no {removed}", removed not in cfg)
        allowed = list(cfg.get("allowedAgentPresets", []))
        expected_presets = {f"role-{r}" for r in SPECIALIST_IDS}
        check("delegation row allowlist covers all 15 role presets",
              set(allowed) == expected_presets,
              f"missing {sorted(expected_presets - set(allowed))}")
        check("delegation row allowlist has no duplicates", len(allowed) == len(set(allowed)))

    # --- the fifteen Agent Preset declarations -------------------------------
    declared = {d.get("id"): d for d in instances.get("agent_presets", [])}
    check("instances declare all 15 role presets",
          set(declared) == {f"role-{r}" for r in SPECIALIST_IDS},
          f"missing {sorted({f'role-{r}' for r in SPECIALIST_IDS} - set(declared))}")
    for rid, entry in mapped_roles.items():
        pid = entry.get("preset")
        dec = declared.get(pid)
        if dec is None:
            check(f"preset {pid} declared", False)
            continue
        check(f"preset {pid} source exists",
              os.path.exists(os.path.join(root, dec.get("source", ""))))
        dec_ts = dec.get("tool_surface", {})
        map_ts = entry.get("tool_surface", {})
        check(f"preset {pid} allow matches mapping",
              set(dec_ts.get("allow", [])) == set(map_ts.get("allow", [])),
              f"{set(dec_ts.get('allow', [])) ^ set(map_ts.get('allow', []))}")
        check(f"preset {pid} deny matches mapping",
              set(dec_ts.get("deny", [])) == set(map_ts.get("deny", [])),
              f"{set(dec_ts.get('deny', [])) ^ set(map_ts.get('deny', []))}")

    # --- the preset composition IS the tool surface -------------------------
    # The host narrowed a preset by COMPOSITION (the tool plugins it mounts),
    # not by a runtime filter, so the declared allow list and the composition
    # must agree tool for tool. This is the check that keeps the removed
    # per-instance `toolFilter` boundary from silently widening.
    for rid, entry in mapped_roles.items():
        comp_path = os.path.join(root, "agents", rid, "agent.cordis.yml")
        if not os.path.exists(comp_path):
            continue
        try:
            exposed = preset_tool_surface(comp_path)
        except Exception as e:
            check(f"preset {rid} composition readable", False, str(e))
            continue
        allow = set(entry.get("tool_surface", {}).get("allow", []))
        check(f"{rid} allow == preset composition tool surface", exposed == allow,
              f"composition={sorted(exposed)} mapping={sorted(allow)}")

    # --- preset draft files parse as YAML lists -----------------------------
    for rid in SPECIALIST_IDS:
        p = os.path.join(root, "agents", rid, "agent.cordis.yml")
        check(f"preset draft {rid} exists", os.path.exists(p))
        if os.path.exists(p):
            try:
                comp = load_yaml(p)
                check(f"preset draft {rid} is list", isinstance(comp, list) and len(comp) >= 5,
                      f"type={type(comp).__name__}, len={len(comp) if isinstance(comp, list) else 'n/a'}")
            except Exception as e:
                check(f"preset draft {rid} parses", False, str(e))

    return out


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        description="Validate multi-agent-harness config/invariants/schemas (DSH 0.2.1-rc.2)")
    parser.add_argument("--root", default=None, help="project root (default: derived from this file)")
    args = parser.parse_args(argv)

    results = run_checks(args.root or project_root())
    failed = [r for r in results if not r[1]]
    passed = [r for r in results if r[1]]
    print(f"validate-config: {len(passed)} passed, {len(failed)} failed")
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
