# validate_config.py — config/invariant/schema validation (module form)
#
# This module implements the validation referenced by config/agents.yaml and
# config/permissions.yaml ("enforced by tests/validate-config.py"). It is
# importable by pytest (tests/unit/test_config.py) and by the standalone
# wrapper tests/validate-config.py (hyphenated) which is the file the configs
# name. It NEVER executes anything consequential — it only reads and validates.
#
# Version pin: DeepSeek Harness 0.1.1-rc.2 (tool names verified).

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
# Tool catalog — verified against DSH 0.1.1-rc.2 (docs/tool-catalog.md), with
# 0.2.0-rc.2 additions noted below. Mirrored here so validation runs without
# loading the docs.
#
# The fifteen subagent_<id> names are the per-role tool-subagent instance
# tools (7 baseline deployed 2026-09-07; 8 expansion registered PRD v0.2 —
# mount is the separate Human gate, ADR 0003 D8). Since 2026-10-11 the instance
# rows live in orchestrator/agent.cordis.yml (moved from global-layer rows in
# $DSH_HOME/profiles/web/cordis.patch.yml), so they remain part of every
# specialist child's inherited (restrictable) surface and are valid allow/deny
# names for tools.restrict() — verified against the engine (packages/core/tools
# restrict(): throws on names outside the child's global+ancestor-chain
# surface).
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
subagent_zeko subagent_cto subagent_cfo subagent_kai subagent_somad
subagent_badsector subagent_nova
subagent_vera subagent_argus subagent_atlas subagent_tess
subagent_quill subagent_scout subagent_talon subagent_ledger
""".split())

# Baseline seven first, then the PRD v0.2 expansion eight (ADR 0003 D1 order).
BASELINE_IDS = ("zeko", "cto", "cfo", "kai", "somad", "badsector", "nova")
EXPANSION_IDS = ("vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger")
SPECIALIST_IDS = set(BASELINE_IDS) | set(EXPANSION_IDS)
# Delegation tools a specialist must never hold in ALLOW. Beyond the generic
# orchestrator-side delegation tools, the fourteen sibling subagent_<id>
# instances are the exact delegation surface a specialist child actually sees
# (restriction matching is exact-name, so the generic "subagent" deny never
# blocked them) — subdelegation DENY BY DEFAULT is enforced on both sides.
DELEGATION_TOOLS = {
    "subagent", "subagent_fork", "send_message", "interrupt_agent",
    "list_agents", "workflow", "ralph",
    "subagent_zeko", "subagent_cto", "subagent_cfo", "subagent_kai",
    "subagent_somad", "subagent_badsector", "subagent_nova",
    "subagent_vera", "subagent_argus", "subagent_atlas", "subagent_tess",
    "subagent_quill", "subagent_scout", "subagent_talon", "subagent_ledger",
}
WRITE_EXEC_TOOLS = {"bash", "edit", "write", "str_replace_editor", "run_code", "pwsh"}
# Permission-matrix vocabulary (config/permissions.yaml, PRD §8 normalized)
CAPABILITY_VALUES = {"yes", "scoped", "review", "approval", "scoped_approval", "no"}
# Protected paths per ADR 0002 (any write targeting these by a non-writer DENY)
PROTECTED_PATHS = ("state/registry/", "audit/")
# Invariants every role policy must declare (security spec + ADR 0002)
REQUIRED_POLICY_INVARIANTS = ("no_self_delegation", "subdelegation_deny_by_default")


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
        tf = entry.get("tool_filter", {})
        allow, deny = set(tf.get("allow", [])), set(tf.get("deny", []))
        pol = policies.get(rid, {})
        pol_tf = pol.get("tool_filter", {})
        check(f"{rid} allow∩deny=∅", not (allow & deny), f"{allow & deny}")
        check(f"{rid} mapping==policy allow", allow == set(pol_tf.get("allow", [])),
              f"{allow ^ set(pol_tf.get('allow', []))}")
        check(f"{rid} mapping==policy deny", deny == set(pol_tf.get("deny", [])),
              f"{deny ^ set(pol_tf.get('deny', []))}")
        unknown = (allow | deny) - VERIFIED_TOOLS
        check(f"{rid} tool names verified", not unknown, f"{unknown}")
        check(f"{rid} no delegation tools", not (allow & DELEGATION_TOOLS), f"{allow & DELEGATION_TOOLS}")
        check(f"{rid} max_depth 1", entry.get("tool_instance", {}).get("max_depth") == 1)
        # Sibling-instance deny contract: a role's deny list must name every
        # OTHER specialist's subagent_<id> (14 siblings) — the exact-name
        # surface a child actually inherits. (ADR 0003 D4; PRD v0.2 §17.)
        expected_siblings = {f"subagent_{o}" for o in SPECIALIST_IDS - {rid}}
        missing_sibs = expected_siblings - deny
        check(f"{rid} deny covers sibling instances", not missing_sibs,
              f"missing {sorted(missing_sibs)}")
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
            a = set(mapped_roles.get(rid, {}).get("tool_filter", {}).get("allow", []))
            bad = a & {"edit", "write"}
            check(f"{rid} code_write=no excludes edit/write from allow", not bad, f"{bad}")

    # (b) allow-set uniqueness: two roles with identical allow sets have no
    #     tool-layer boundary between them. Identical sets are only allowed
    #     inside a declared tool_surface_equivalence group (permissions.yaml),
    #     and every declared group must actually share one allow set.
    declared_groups = [set(g) for g in perms.get("tool_surface_equivalence", [])]
    by_allow: dict = {}
    for rid, entry in mapped_roles.items():
        a = frozenset(entry.get("tool_filter", {}).get("allow", []))
        by_allow.setdefault(a, set()).add(rid)
    for a, rids in by_allow.items():
        if len(rids) < 2:
            continue
        covered = any(rids <= g for g in declared_groups)
        check(f"identical allow set declared {sorted(rids)}", covered,
              f"{sorted(rids)} not covered by tool_surface_equivalence")
    for i, g in enumerate(declared_groups):
        member_sets = {frozenset(mapped_roles[r]["tool_filter"]["allow"])
                       for r in g if r in mapped_roles}
        check(f"tool_surface_equivalence[{i}] shares allow set",
              len(member_sets) <= 1, f"{[sorted(s) for s in member_sets]}")

    # --- orchestrator mapping ----------------------------------------------
    orch = mapping.get("orchestrator", {})
    orch_tf = orch.get("tool_filter", {})
    orch_allow = set(orch_tf.get("allow", []))
    orch_deny = set(orch_tf.get("deny", []))
    check("orchestrator delegation tools in allow", set(orch.get("delegation_tools", [])) <= orch_allow)
    check("orchestrator allow∩deny=∅", not (orch_allow & orch_deny), f"{orch_allow & orch_deny}")
    check("orchestrator tool names verified", not ((orch_allow | orch_deny) - VERIFIED_TOOLS),
          f"{(orch_allow | orch_deny) - VERIFIED_TOOLS}")
    # Every specialist instance must be named by the declared allow set: the
    # orchestrator is the only delegator (consistency_rules.delegation_orchestrator_only),
    # and ADR 0004 D3 derives the preset's row deletions from exactly this set, so
    # an instance missing here is an un-enforced narrowing of the delegation surface.
    missing_instances = {f"subagent_{o}" for o in SPECIALIST_IDS} - orch_allow
    check("orchestrator allow covers all 15 instances", not missing_instances,
          f"missing {sorted(missing_instances)}")

    # --- orchestrator policy (declaration ↔ mapping consistency) ------------
    # orchestrator/policy.yaml COPIES the mapping's tool_filter; without these
    # checks the copy is prose that can silently diverge from the config.
    orch_pol_tf = orch_policy.get("tool_filter", {})
    pol_allow = set(orch_pol_tf.get("allow", []))
    pol_deny = set(orch_pol_tf.get("deny", []))
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

    # --- ADR 0002 protected-path discipline ---------------------------------
    # Any role's allow set must NOT grant a way to write protected paths unless
    # that role is the registry writer (orchestrator). For roles with generic
    # write tools (bash/edit/write), the execution-gate path check must be
    # required; this is recorded in each policy's invariants and enforced at
    # the reference level (tests/control_plane.py). Here we assert the config
    # declares the invariant.
    for rid, pol in policies.items():
        check(f"{rid} registry-protection invariant declared",
              pol.get("invariants", {}).get("no_self_delegation") is True)

    # --- Phase 1C draft artifacts (mounted 2026-09-07, Human-approved D4/D7) -
    draft = mapping.get("draft_artifacts", {})
    check("draft status is mounted", draft.get("status") == "mounted")
    check("draft mount_required false", draft.get("mount_required") is False)
    check("draft instances file exists", os.path.exists(os.path.join(root, draft.get("instances_draft_path", ""))))
    check("draft preset ref valid", "agent.cordis.yml" in draft.get("preset_draft_path", ""))

    instances = load_yaml(os.path.join(root, "config", "tool-subagent-instances.yaml"))
    check("instances status mounted", instances.get("status") == "mounted")
    insert = instances.get("insert_draft", [])
    check("instances count 15", len(insert) == 15, f"{len(insert)}")
    instance_map = {}
    for row in insert:
        cfg = row.get("config", {})
        tf = cfg.get("toolFilter", {})
        allow, deny = set(tf.get("allow", [])), set(tf.get("deny", []))
        instance_map[cfg.get("toolName")] = (allow, deny)

        unknown = (allow | deny) - VERIFIED_TOOLS
        check(f"instance {cfg.get('toolName')} tool names verified", not unknown, f"{unknown}")
        check(f"instance {cfg.get('toolName')} allow∩deny=∅", not (allow & deny), f"{allow & deny}")
        check(f"instance {cfg.get('toolName')} no delegation tools",
              not (allow & DELEGATION_TOOLS), f"{allow & DELEGATION_TOOLS}")
        check(f"instance {cfg.get('toolName')} provider spawn", cfg.get("provider") == "spawn")
        check(f"instance {cfg.get('toolName')} continuable", cfg.get("backgroundMode") == "continuable")
        check(f"instance {cfg.get('toolName')} max_depth 1", cfg.get("maxDepth") == 1)

    # instance == mapping consistency
    for rid, entry in mapped_roles.items():
        expected_name = f"subagent_{rid}"
        if expected_name not in instance_map:
            check(f"instance {expected_name} present", False)
            continue
        inst_allow, inst_deny = instance_map[expected_name]
        map_allow = set(entry.get("tool_filter", {}).get("allow", []))
        map_deny = set(entry.get("tool_filter", {}).get("deny", []))
        check(f"instance {expected_name}==mapping allow", inst_allow == map_allow, f"{inst_allow ^ map_allow}")
        check(f"instance {expected_name}==mapping deny", inst_deny == map_deny, f"{inst_deny ^ map_deny}")

    # preset draft files parse as YAML lists
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
        description="Validate multi-agent-harness config/invariants/schemas (DSH 0.1.1-rc.2)")
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
