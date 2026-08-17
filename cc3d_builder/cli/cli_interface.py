# cli_interface.py
import json
import sys
from pathlib import Path
from cc3d_builder.core.rule_builder import build_rule
from cc3d_builder.core.csv_importer import (
    import_intracellular_models_from_csv,
    import_rules_from_csv,
    import_subcellular_systems_from_csv,
)
from cc3d_builder.engine.registry.simulation_registry import SimulationRegistry
from cc3d_builder.utils_extensions.utils import handle_new_rule_registration, ask_params_cli
from cc3d_builder.core.model_builder import build_model


def _clean_user_label(value):
    text = str(value or "").strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


def _parse_scalar(text):
    value = str(text).strip()
    lowered = value.lower()
    if lowered in {"true", "yes", "y", "on"}:
        return True
    if lowered in {"false", "no", "n", "off"}:
        return False
    if lowered in {"none", "null"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _split_csv_labels(text):
    return [_clean_user_label(part) for part in str(text or "").split(",") if _clean_user_label(part)]


def _ask_bool(prompt, default=False):
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{prompt} ({suffix}): ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "true", "1", "on"}


def _parse_key_value_mapping(text):
    mapping = {}
    for part in str(text or "").split(","):
        if "=" not in part:
            continue
        key, value = [item.strip() for item in part.split("=", 1)]
        key = _clean_user_label(key)
        if key:
            mapping[key] = _parse_scalar(value)
    return mapping


def _ask_mapping_or_json(prompt, default=None):
    if default is None:
        default = {}
    while True:
        raw = input(f"{prompt} (JSON object or key=value pairs, blank for none): ").strip()
        if not raw:
            return dict(default)
        if raw.startswith("{"):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"Invalid JSON: {exc}")
                continue
            if isinstance(parsed, dict):
                return parsed
            print("Expected a JSON object.")
            continue
        parsed = _parse_key_value_mapping(raw)
        if parsed:
            return parsed
        print("Use JSON object syntax or comma-separated key=value pairs.")


def _ask_json_block(prompt, default, expected_types):
    while True:
        raw = input(f"{prompt} (JSON, blank to skip): ").strip()
        if not raw:
            return default
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON: {exc}")
            continue
        if isinstance(parsed, expected_types):
            return parsed
        names = ", ".join(t.__name__ for t in expected_types)
        print(f"Expected JSON type: {names}.")


def _save_registry_state(registry):
    if hasattr(registry, "save_state"):
        registry.save_state(quiet=True)
    else:
        registry.save(rebuild_artifacts=False, quiet=True)


def _spec_aliases(spec, keys):
    aliases = set()
    if not isinstance(spec, dict):
        return aliases
    for key in keys:
        value = spec.get(key)
        if value:
            aliases.add(str(value))
    return aliases


def _merge_specs_by_alias(current, incoming, alias_keys):
    items = [item for item in (current or []) if isinstance(item, dict)]
    index_by_alias = {}
    for index, spec in enumerate(items):
        for alias in _spec_aliases(spec, alias_keys):
            index_by_alias[alias] = index

    added = 0
    updated = 0
    for spec in incoming:
        aliases = _spec_aliases(spec, alias_keys)
        match = next((index_by_alias[alias] for alias in aliases if alias in index_by_alias), None)
        if match is None:
            items.append(spec)
            new_index = len(items) - 1
            for alias in aliases:
                index_by_alias[alias] = new_index
            added += 1
        else:
            items[match] = spec
            for alias in aliases:
                index_by_alias[alias] = match
            updated += 1
    return items, added, updated


def _choose_registered_name(names, title, manual_prompt):
    names = [str(name) for name in names if str(name).strip()]
    if not names:
        return input(manual_prompt).strip()

    print(f"\n{title}:")
    for index, name in enumerate(names, 1):
        print(f"  {index} - {name}")
    raw = input("Choice or explicit name [1]: ").strip()
    if not raw:
        return names[0]
    if raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(names):
            return names[index]
    return raw


def _intracellular_model_names(registry):
    names = []
    for spec in getattr(registry, "intracellular_models", []) or []:
        if not isinstance(spec, dict):
            continue
        name = spec.get("model_name") or spec.get("alias") or spec.get("id")
        if name:
            names.append(str(name))
    return names


def _subcellular_system_names(registry):
    names = []
    for spec in getattr(registry, "subcellular_systems", []) or []:
        if not isinstance(spec, dict):
            continue
        name = spec.get("id") or spec.get("name") or spec.get("system")
        if name:
            names.append(str(name))
    return names

def _ask_parameter_or_model(param_name, default_val=1.0):
    """
    CLI advanced parameter configuration wizard:
    Allows the user to choose a fixed numeric value, a state/native expression,
    or a field-regulated physical model assembled by build_model.
    """
    print(f"\n>>> Configuring parameter: [{param_name}]")
    print(f"  1 - Fixed constant value (number only; default: {default_val})")
    print("  2 - State/native expression (uses {state_key}, e.g., {volume} * 0.01)")
    print("  3 - Field-regulated physical model (diffusion fields only; Hill / Linear / Expression)")

    choice = input("Please enter your choice (1/2/3, default 1): ").strip()
    if choice == "3":
        return build_model()
    if choice == "2":
        expr = input(
            f"Please enter expression for [{param_name}] "
            "(state/native examples: {volume} * 0.01, {division_count} + 1): "
        ).strip()
        return expr or default_val
    else:
        while True:
            val = input(f"Please enter numeric constant for [{param_name}] (press Enter to use default {default_val}): ").strip()
            if not val:
                return default_val
            try:
                return float(val)
            except ValueError:
                print("Invalid fixed value. Use option 2 for {state_key} expressions such as {volume} * 0.01.")


def _ask_float(prompt, default):
    raw = input(f"{prompt} (default {default}): ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"Invalid number, using default {default}")
        return default


def _ask_frequency_control():
    print("\n=================================")
    print(">>> Rule Trigger Frequency Control:")
    print("Should this rule execute at a constant interval, or be controlled by cell-history feedback?")
    print("  1 - Constant execution frequency (fixed MCS interval)")
    print("  2 - Dynamic state-feedback frequency (free state_key or expression)")

    freq_choice = input("Please enter your choice (1 or 2, default 1): ").strip()
    if freq_choice == "2":
        return _ask_dynamic_frequency_control()

    raw_f = input("Please enter constant execution interval (MCS steps, default 1): ").strip()
    return int(raw_f) if raw_f.isdigit() else 1


def _ask_dynamic_frequency_control():
    print("\n--- Dynamic Frequency Feedback Control ---")
    print("This controls the rule check interval. Larger values mean the rule is checked less often.")
    print("State keys are free text. To view available built-in keys, run:")
    print("  python3 -m cc3d_builder.cli.main --state-keys")
    state_key = input("State key (default division_count): ").strip() or "division_count"

    print("\nFeedback mode:")
    print("  1 - Linear slowdown: interval = base + slope * state")
    print("  2 - Exponential slowdown: interval = base * factor ** state")
    print("  3 - Custom expression using mcs, state, and cell.dict numeric keys")
    mode_choice = input("Feedback mode (1/2/3, default 1): ").strip()

    min_frequency = _ask_float("Minimum interval", 1.0)
    max_frequency = _ask_float("Maximum interval", 1000.0)

    spec = {
        "type": "state_feedback_frequency",
        "state_key": state_key,
        "min_frequency": min_frequency,
        "max_frequency": max_frequency,
    }

    if mode_choice == "2":
        spec["mode"] = "exponential"
        spec["base_frequency"] = _ask_float("Base interval", 1.0)
        spec["factor"] = _ask_float("Exponential factor", 1.25)
    elif mode_choice == "3":
        spec["mode"] = "expression"
        print("Example: 1 + 2 * division_count")
        print("Example: 5 + 0.01 * mcs")
        print("Example: 10 + 0.2 * behaviour_stats_growth_total_delta")
        expression = input("Frequency expression: ").strip() or f"1 + {state_key}"
        spec["expression"] = expression
    else:
        spec["mode"] = "linear"
        spec["base_frequency"] = _ask_float("Base interval", 1.0)
        spec["slope"] = _ask_float("Slowdown slope per state unit", 1.0)

    return spec


def _rule_id_exists(registry, rule_id):
    return any(str(rule.get("id")) == str(rule_id) for rule in registry.rules)


def _ask_rule_id(registry):
    while True:
        rule_id = input("Rule ID: ").strip()
        if not rule_id:
            print("Rule ID cannot be empty.")
            continue

        if not _rule_id_exists(registry, rule_id):
            return rule_id, None

        while True:
            print(f"⚠️ Rule ID '{rule_id}' already exists.")
            print("  1 - Overwrite existing rule(s) with this ID")
            print("  2 - Re-enter a different Rule ID")
            print("  3 - Keep duplicate ID and add another rule")

            choice = input("Please choose (1/2/3, default 2): ").strip().lower() or "2"
            if choice in {"1", "o", "overwrite"}:
                return rule_id, "overwrite"
            if choice in {"2", "r", "reenter", "re-enter", "reinput", "re-input"}:
                break
            if choice in {"3", "k", "keep", "duplicate", "same"}:
                return rule_id, "keep"

            print("Invalid choice. Please choose 1, 2, or 3.")


def _replace_rules_by_id(registry, rule_id, new_rule):
    kept_rules = []
    first_match_index = None
    removed = 0

    for rule in registry.rules:
        if str(rule.get("id")) == str(rule_id):
            if first_match_index is None:
                first_match_index = len(kept_rules)
            removed += 1
        else:
            kept_rules.append(rule)

    if first_match_index is None:
        first_match_index = len(kept_rules)

    kept_rules.insert(first_match_index, new_rule)
    registry.rules = kept_rules
    if removed and hasattr(registry, "_build_index"):
        registry._build_index()
    return removed


def _print_intracellular_models(registry):
    models = [item for item in getattr(registry, "intracellular_models", []) or [] if isinstance(item, dict)]
    if not models:
        print("No intracellular models registered.")
        return

    print("\nRegistered intracellular models:")
    for index, spec in enumerate(models, 1):
        source = spec.get("source", {}) if isinstance(spec.get("source"), dict) else {}
        attach = spec.get("attach_to", {}) if isinstance(spec.get("attach_to"), dict) else {}
        cell_types = attach.get("cell_types") or spec.get("cell_types") or []
        if isinstance(cell_types, list):
            cell_types = ", ".join(str(item) for item in cell_types)
        source_text = (
            source.get("path")
            or source.get("boolean_network_path")
            or source.get("bnd_path")
            or source.get("kind")
            or ""
        )
        print(
            f"  {index}. {spec.get('id', '?')} "
            f"[{spec.get('engine', 'sbml')}] model={spec.get('model_name', spec.get('alias', ''))} "
            f"source={source_text or 'inline/unspecified'} attach={cell_types or 'none'}"
        )


def _collect_intracellular_model_spec():
    print("\n--- Add / Update Intracellular Model Registry Entry ---")
    model_id = ""
    while not model_id:
        model_id = input("Model ID: ").strip()
        if not model_id:
            print("Model ID is required.")

    engines = {
        "1": "sbml",
        "2": "antimony",
        "3": "cellml",
        "4": "maboss",
    }
    print("\nEngine:")
    print("  1 - sbml")
    print("  2 - antimony")
    print("  3 - cellml")
    print("  4 - maboss")
    engine = engines.get(input("Engine [1]: ").strip() or "1", "sbml")
    model_name = input(f"Model name [{model_id}]: ").strip() or model_id

    source_kind = input("Source kind [file/inline, default file]: ").strip().lower() or "file"
    if source_kind not in {"file", "inline"}:
        print("Unknown source kind, using file.")
        source_kind = "file"

    source = {"kind": source_kind}
    if engine == "maboss":
        if source_kind == "inline":
            source["boolean_network_text"] = input("Inline MaBoSS .bnd text: ")
            source["simulation_configuration_text"] = input("Inline MaBoSS .cfg text: ")
        else:
            source["boolean_network_path"] = input("MaBoSS boolean network path (.bnd): ").strip()
            source["simulation_configuration_path"] = input("MaBoSS simulation config path (.cfg): ").strip()
    elif source_kind == "inline":
        source["text"] = input("Inline model text: ")
    else:
        source["path"] = input("Model source path (relative to Simulation/ or absolute): ").strip()

    cell_types = _split_csv_labels(input("Attach cell types (comma-separated, blank for none): ").strip())
    step_size = _ask_float("Solver step size", 1.0)
    initial_conditions = _ask_mapping_or_json("Initial conditions")
    inputs = _ask_json_block("Input mappings", [], (list, dict))
    outputs = _ask_json_block("Output mappings", [], (list, dict))

    return {
        "id": model_id,
        "engine": engine,
        "model_name": model_name,
        "source": source,
        "attach_to": {"cell_types": cell_types},
        "solver": {"step_size": step_size},
        "initial_conditions": initial_conditions,
        "inputs": inputs,
        "outputs": outputs,
    }


def cli_manage_intracellular_models(registry):
    changed = False
    while True:
        print("\n=== Intracellular Model Registry ===")
        print("  1 - List registered models")
        print("  2 - Add/update model")
        print("  3 - Import model registry CSV")
        print("  4 - Delete model")
        print("  5 - Done")
        choice = input("Choice [1]: ").strip() or "1"

        if choice == "1":
            _print_intracellular_models(registry)
        elif choice == "2":
            spec = _collect_intracellular_model_spec()
            current = getattr(registry, "intracellular_models", []) or []
            merged, added, updated = _merge_specs_by_alias(current, [spec], ("id", "model_name", "alias"))
            registry.intracellular_models = merged
            _save_registry_state(registry)
            changed = True
            print(f"Saved model registry entry: {spec['id']} ({added} added, {updated} updated).")
        elif choice == "3":
            csv_path = input("Model registry CSV path: ").strip()
            if not csv_path:
                print("CSV path is required.")
                continue
            imported = import_intracellular_models_from_csv(csv_path)
            current = getattr(registry, "intracellular_models", []) or []
            merged, added, updated = _merge_specs_by_alias(current, imported, ("id", "model_name", "alias"))
            registry.intracellular_models = merged
            _save_registry_state(registry)
            changed = True
            print(f"Imported {len(imported)} model(s): {added} added, {updated} updated.")
        elif choice == "4":
            models = [item for item in getattr(registry, "intracellular_models", []) or [] if isinstance(item, dict)]
            _print_intracellular_models(registry)
            if not models:
                continue
            raw = input("Delete model number or ID (blank to cancel): ").strip()
            if not raw:
                continue
            delete_index = None
            if raw.isdigit() and 1 <= int(raw) <= len(models):
                delete_index = int(raw) - 1
            else:
                for index, spec in enumerate(models):
                    if raw in _spec_aliases(spec, ("id", "model_name", "alias")):
                        delete_index = index
                        break
            if delete_index is None:
                print("No matching model.")
                continue
            removed = models.pop(delete_index)
            registry.intracellular_models = models
            _save_registry_state(registry)
            changed = True
            print(f"Deleted model: {removed.get('id', raw)}")
        elif choice == "5":
            return changed
        else:
            print("Invalid choice.")


def _print_subcellular_systems(registry):
    systems = [item for item in getattr(registry, "subcellular_systems", []) or [] if isinstance(item, dict)]
    if not systems:
        print("No subcellular systems registered.")
        return

    print("\nRegistered subcellular systems:")
    for index, spec in enumerate(systems, 1):
        attach = spec.get("attach_to", {}) if isinstance(spec.get("attach_to"), dict) else {}
        cell_types = attach.get("cell_types") or spec.get("cell_types") or []
        if isinstance(cell_types, list):
            cell_types = ", ".join(str(item) for item in cell_types)
        stages = spec.get("stages") or []
        if isinstance(stages, list):
            stages = ", ".join(str(item) for item in stages)
        components = spec.get("default_counts") or spec.get("components") or {}
        if isinstance(components, dict):
            components = ", ".join(f"{key}:{value}" for key, value in components.items())
        print(
            f"  {index}. {spec.get('id', spec.get('name', '?'))} "
            f"default_stage={spec.get('default_stage', '') or 'none'} "
            f"stages={stages or 'none'} components={components or 'none'} attach={cell_types or 'none'}"
        )


def _collect_subcellular_system_spec():
    print("\n--- Add / Update Subcellular System Registry Entry ---")
    system_id = ""
    while not system_id:
        system_id = _clean_user_label(input("System ID: "))
        if not system_id:
            print("System ID is required.")

    stages = _split_csv_labels(input("Stages (comma-separated, e.g. G1,S,G2,M): ").strip())
    default_stage = _clean_user_label(input(f"Default stage [{stages[0] if stages else 'unassigned'}]: "))
    if not default_stage:
        default_stage = stages[0] if stages else "unassigned"
    if stages and default_stage not in stages:
        stages.insert(0, default_stage)

    cell_types = _split_csv_labels(input("Attach cell types (comma-separated, blank for none): ").strip())
    default_counts = _ask_mapping_or_json("Default component counts")
    default_localization = _ask_mapping_or_json("Default localization values")

    return {
        "id": system_id,
        "scope": "cell",
        "stages": stages,
        "default_stage": default_stage,
        "attach_to": {"cell_types": cell_types},
        "default_counts": default_counts,
        "default_localization": default_localization,
    }


def cli_manage_subcellular_systems(registry):
    changed = False
    while True:
        print("\n=== Subcellular System Registry ===")
        print("  1 - List registered systems")
        print("  2 - Add/update system")
        print("  3 - Import system registry CSV")
        print("  4 - Delete system")
        print("  5 - Done")
        choice = input("Choice [1]: ").strip() or "1"

        if choice == "1":
            _print_subcellular_systems(registry)
        elif choice == "2":
            spec = _collect_subcellular_system_spec()
            current = getattr(registry, "subcellular_systems", []) or []
            merged, added, updated = _merge_specs_by_alias(current, [spec], ("id", "name", "system"))
            registry.subcellular_systems = merged
            _save_registry_state(registry)
            changed = True
            print(f"Saved subcellular system: {spec['id']} ({added} added, {updated} updated).")
        elif choice == "3":
            csv_path = input("Subcellular system registry CSV path: ").strip()
            if not csv_path:
                print("CSV path is required.")
                continue
            imported = import_subcellular_systems_from_csv(csv_path)
            current = getattr(registry, "subcellular_systems", []) or []
            merged, added, updated = _merge_specs_by_alias(current, imported, ("id", "name", "system"))
            registry.subcellular_systems = merged
            _save_registry_state(registry)
            changed = True
            print(f"Imported {len(imported)} system(s): {added} added, {updated} updated.")
        elif choice == "4":
            systems = [item for item in getattr(registry, "subcellular_systems", []) or [] if isinstance(item, dict)]
            _print_subcellular_systems(registry)
            if not systems:
                continue
            raw = input("Delete system number or ID (blank to cancel): ").strip()
            if not raw:
                continue
            delete_index = None
            if raw.isdigit() and 1 <= int(raw) <= len(systems):
                delete_index = int(raw) - 1
            else:
                for index, spec in enumerate(systems):
                    if raw in _spec_aliases(spec, ("id", "name", "system")):
                        delete_index = index
                        break
            if delete_index is None:
                print("No matching system.")
                continue
            removed = systems.pop(delete_index)
            registry.subcellular_systems = systems
            _save_registry_state(registry)
            changed = True
            print(f"Deleted subcellular system: {removed.get('id', raw)}")
        elif choice == "5":
            return changed
        else:
            print("Invalid choice.")


def _subcellular_stages_for(registry, system_name):
    requested = _clean_user_label(system_name)
    for spec in getattr(registry, "subcellular_systems", []) or []:
        if not isinstance(spec, dict):
            continue
        aliases = _spec_aliases(spec, ("id", "name", "system"))
        if requested not in aliases:
            continue
        return [_clean_user_label(item) for item in spec.get("stages", []) if _clean_user_label(item)]
    return []


def _ask_subcellular_stage(registry, system_name, prompt, allow_blank=False):
    stages = _subcellular_stages_for(registry, system_name)
    if stages:
        print("Registered stages:")
        for index, stage in enumerate(stages, 1):
            print(f"  {index} - {stage}")
    raw = input(prompt).strip()
    if not raw and allow_blank:
        return ""
    if not raw and stages:
        return stages[0]
    if raw.isdigit() and stages:
        index = int(raw) - 1
        if 0 <= index < len(stages):
            return stages[index]
    return _clean_user_label(raw)


def _collect_intracellular_model_rule_params(registry):
    model = _choose_registered_name(
        _intracellular_model_names(registry),
        "Intracellular models",
        "Model registry id or model_name: ",
    )
    if not model:
        raise Exception("Intracellular model is required")

    actions = {
        "1": "advance",
        "2": "sync_inputs",
        "3": "step",
        "4": "sync_outputs",
        "5": "reset",
        "6": "set_variable",
    }
    print("\nIntracellular action:")
    print("  1 - advance (sync inputs, step model, sync outputs)")
    print("  2 - sync_inputs")
    print("  3 - step / global_step")
    print("  4 - sync_outputs")
    print("  5 - reset")
    print("  6 - set_variable")
    action = actions.get(input("Action [1]: ").strip() or "1", "advance")
    params = {"model": model, "action": action}

    if action == "advance":
        params["sync_inputs"] = _ask_bool("Sync mapped CC3D values into model before stepping", True)
        params["step_model"] = _ask_bool("Advance the intracellular model", True)
        params["sync_outputs"] = _ask_bool("Sync model values back into cell state after stepping", True)

    if action == "set_variable":
        variable = input("Variable to set: ").strip()
        if not variable:
            raise Exception("Variable is required for set_variable")
        params["variable"] = variable
        params["value"] = _parse_scalar(input("Value: ").strip())

    if action in {"advance", "sync_inputs"}:
        mappings = _ask_json_block("Rule-specific input mappings", [], (list, dict))
        if mappings:
            params["inputs"] = mappings
    if action in {"advance", "sync_outputs"}:
        mappings = _ask_json_block("Rule-specific output mappings", [], (list, dict))
        if mappings:
            params["outputs"] = mappings

    return params


def _collect_subcellular_rule_params(registry):
    system = _choose_registered_name(
        _subcellular_system_names(registry),
        "Subcellular systems",
        "System ID: ",
    )
    if not system:
        raise Exception("Subcellular system is required")

    actions = {
        "1": "initialize",
        "2": "set_stage",
        "3": "advance_stage",
        "4": "set_component",
        "5": "increase_component",
        "6": "consume_component",
        "7": "set_localization",
        "8": "translocate",
        "9": "set_value",
        "10": "assemble",
    }
    print("\nSubcellular action:")
    print("  1 - initialize")
    print("  2 - set_stage")
    print("  3 - advance_stage")
    print("  4 - set_component")
    print("  5 - increase_component")
    print("  6 - consume_component")
    print("  7 - set_localization")
    print("  8 - translocate")
    print("  9 - set_value")
    print("  10 - assemble")
    action = actions.get(input("Action [2]: ").strip() or "2", "set_stage")
    params = {"system": _clean_user_label(system), "action": action}

    if action == "set_stage":
        stage = _ask_subcellular_stage(registry, system, "Stage (name or registered stage number): ")
        if not stage:
            raise Exception("Stage is required for set_stage")
        params["stage"] = stage
    elif action == "advance_stage":
        from_stage = _ask_subcellular_stage(
            registry,
            system,
            "Optional required current stage (blank to allow any): ",
            allow_blank=True,
        )
        if from_stage:
            params["from_stage"] = from_stage
        to_stage = _ask_subcellular_stage(
            registry,
            system,
            "Target stage (blank to use next registered stage): ",
            allow_blank=True,
        )
        if to_stage:
            params["to_stage"] = to_stage
        params["probability"] = _ask_parameter_or_model("subcellular_stage_probability", default_val=1.0)
    elif action in {"set_component", "increase_component", "consume_component"}:
        component = input("Component name: ").strip()
        if not component:
            raise Exception("Component is required")
        params["component"] = _clean_user_label(component)
        if action == "set_component":
            params["count"] = _ask_parameter_or_model("component_count", default_val=1.0)
        else:
            params["amount"] = _ask_parameter_or_model("component_amount", default_val=1.0)
            if action == "consume_component":
                params["floor_zero"] = _ask_bool("Prevent component count from going below zero", True)
    elif action == "set_localization":
        location = input("Localization key: ").strip()
        if not location:
            raise Exception("Localization key is required")
        params["location"] = _clean_user_label(location)
        params["value"] = _ask_parameter_or_model("localization_value", default_val=1.0)
    elif action == "translocate":
        from_location = input("Optional source location (blank for external source): ").strip()
        to_location = input("Target location: ").strip()
        if not to_location:
            raise Exception("Target location is required")
        if from_location:
            params["from_location"] = _clean_user_label(from_location)
        params["to_location"] = _clean_user_label(to_location)
        params["amount"] = _ask_parameter_or_model("translocation_amount", default_val=0.1)
    elif action == "set_value":
        variable = input("Nested variable path: ").strip()
        if not variable:
            raise Exception("Variable path is required")
        params["variable"] = _clean_user_label(variable)
        params["value"] = _parse_scalar(input("Value: ").strip())
    elif action == "assemble":
        product = input("Product component or assembled unit: ").strip()
        if not product:
            raise Exception("Product is required")
        params["product"] = _clean_user_label(product)
        params["amount"] = _ask_parameter_or_model("assembled_product_amount", default_val=1.0)
        requirements = _ask_mapping_or_json("Required component counts")
        if requirements:
            params["requires"] = requirements
        to_stage = _ask_subcellular_stage(
            registry,
            system,
            "Optional stage after assembly (blank for no stage change): ",
            allow_blank=True,
        )
        if to_stage:
            params["to_stage"] = to_stage

    return params


def cli_add_rule(registry, sm, injector):

    params = {}

    # =========================
    # basic information
    # =========================

    params["id"], duplicate_rule_action = _ask_rule_id(registry)
    print("=================================")
    target = input("Target cell type (or None): ").strip()
    params["target"] = None if target.lower() == "none" else target

    print("\nBehaviour:")
    print("1 - growth")
    print("2 - differentiate")
    print("3 - create")
    print("4 - death")
    print("5 - secrete/uptake")
    print("6 - dormancy/Restore")
    print("7 - phagocytosis")
    print("8 - chemotaxis")
    print("9 - force")
    print("10 - compartmentalize")
    print("11 - fpp_link")
    print("12 - intracellular_model")
    print("13 - subcellular")
    choice = input("Choice: ").strip()

    if choice == "1":
        behaviour = "growth"

    elif choice == "2":
        behaviour = "differentiate"

    elif choice == "3":
        behaviour = "create"

    elif choice == "4":
        behaviour = "death"

    elif choice == "5":
        behaviour = "secrete/uptake"

    elif choice == "6":
        behaviour = "dormancy"

    elif choice == "7":
        behaviour = "phagocytosis"

    elif choice == "8":
        behaviour = "chemotaxis"

    elif choice == "9":
        behaviour = "force"

    elif choice == "10":
        behaviour = "compartmentalize"

    elif choice == "11":
        behaviour = "fpp_link"

    elif choice == "12":
        behaviour = "intracellular_model"

    elif choice == "13":
        behaviour = "subcellular"

    else:
        raise Exception("Invalid behaviour")

    # =========================
    # CONDITION
    # =========================

    from cc3d_builder.cli.condition_builder import build_condition
    params["when"] = build_condition(registry)

    # ============================================================
    # GROWTH
    # ============================================================

    if behaviour == "growth":
        params.update(build_model())

    # ============================================================
    # DIFFERENTIATE
    # ============================================================

    elif behaviour == "differentiate":

        print("\nDifferentiation mode:")
        print("1 - type_switch (A → B)")
        print("2 - division (A → X + Y)")

        mode_choice = input("Choice: ").strip()

        if mode_choice == "1":

            params["mode"] = "type_switch"
            params["new_type"] = input("New type: ").strip()

        elif mode_choice == "2":

            params["mode"] = "division"

            print("\nDivision type:")
            print("1 - symmetric (B + B)")
            print("2 - asymmetric (B + C)")

            div_type = input("Choice: ").strip()

            if div_type == "1":
                params["division_type"] = "symmetric"
                d_type = input("Daughter type: ").strip()
                params["parent_type"] = d_type
                params["child_type"] = d_type

            elif div_type == "2":

                params["division_type"] = "asymmetric"
                params["parent_type"] = input("Mother new type: ").strip()
                params["child_type"] = input("Daughter type: ").strip()

            else:
                raise Exception("Invalid division type")

            params["volume_ratio"] = _ask_parameter_or_model("volume_ratio", default_val=0.5)

            print("\nMemory tracking inheritance strategy:")
            print("1 - total (Both cells keep aging clock / Inherit full division count)")
            print("2 - reset (Mother cell ages +1, Daughter cell resets as brand new at 0)")

            strat_choice = input("Choice (default 1): ").strip()
            if strat_choice == "2":
                params["inheritance_strategy"] = "reset"
            else:
                params["inheritance_strategy"] = "total"

            params["state_key"] = "division_count"

            print("\nOrientation strategy:")
            print("1 - random")
            print("2 - specify angle")
            print("3 - specify direction vector")

            orient_choice = input("Choice: ").strip()

            if orient_choice == "1":
                params["placement"] = {"type": "random"}

            elif orient_choice == "2":
                angle = float(input("Angle (degrees): "))
                params["placement"] = {
                    "type": "angle",
                    "angle_deg": angle
                }

            elif orient_choice == "3":
                dx = float(input("dx: "))
                dy = float(input("dy: "))
                params["placement"] = {
                    "type": "vector",
                    "dx": dx,
                    "dy": dy
                }

            else:
                params["placement"] = {"type": "random"}

        else:
            raise Exception("Invalid differentiate mode")

    # ============================================================
    # CREATE
    # ============================================================

    elif behaviour == "create":

        params["cell_type"] = input("New cell type: ").strip()

        params["count"] = _ask_parameter_or_model("create_count", default_val=1)

        print("\nDistribution:")
        print("1 - random")
        print("2 - cluster")
        print("3 - stripe")

        d = input("Choice: ").strip()

        if d == "1":

            use_region = input("Specify region? (y/n): ").strip().lower()

            if use_region == "y":

                params["distribution"] = {
                    "type": "random",
                    "x_start": int(input("x_start: ")),
                    "x_end": int(input("x_end: ")),
                    "y_start": int(input("y_start: ")),
                    "y_end": int(input("y_end: "))
                }

            else:
                params["distribution"] = {"type": "random"}

        elif d == "2":

            params["distribution"] = {
                "type": "cluster",
                "center": [
                    int(input("center x: ")),
                    int(input("center y: "))
                ],
                "radius": int(input("radius: "))
            }

        elif d == "3":

            print("\nStripe direction:")
            print("1 - vertical")
            print("2 - horizontal")

            dir_choice = input("Choice: ").strip()

            if dir_choice == "1":

                direction = "vertical"

                x = int(input("x position: "))
                y_start = int(input("y_start: "))

                print("\nMode:")
                print("1 - start + gap")
                print("2 - start + end")

                mode = input("Choice: ").strip()

                dist = {
                    "type": "stripe",
                    "direction": direction,
                    "x": x,
                    "y_start": y_start
                }

                if mode == "1":
                    y_gap = int(input("y_gap: "))
                    dist["y_gap"] = y_gap

                elif mode == "2":
                    y_end = int(input("y_end: "))
                    dist["y_end"] = y_end

                else:
                    raise Exception("Invalid mode")

                params["distribution"] = dist

            elif dir_choice == "2":

                direction = "horizontal"

                y = int(input("y position: "))
                x_start = int(input("x_start: "))

                print("\nMode:")
                print("1 - start + gap")
                print("2 - start + end")

                mode = input("Choice: ").strip()

                dist = {
                    "type": "stripe",
                    "direction": direction,
                    "y": y,
                    "x_start": x_start
                }

                if mode == "1":
                    x_gap = int(input("x_gap: "))
                    dist["x_gap"] = x_gap

                elif mode == "2":
                    x_end = int(input("x_end: "))
                    dist["x_end"] = x_end

                else:
                    raise Exception("Invalid mode")

                params["distribution"] = dist

            else:
                raise Exception("Invalid direction")

        else:
            raise Exception("Invalid distribution")

    # ============================================================
    # Cell Death (Apoptosis & Necrosis)
    # ============================================================
    elif behaviour == "death":
        print("\nDeath Mode:")
        print("1 - apoptosis")
        print("2 - necrosis")

        death_choice = input("Choice: ").strip()

        if death_choice == "1":
            params["mode"] = "apoptosis"
            params["shrink_rate"] = _ask_parameter_or_model("shrink_rate", default_val=0.95)
            params["terminal_volume"] = _ask_parameter_or_model("terminal_volume", default_val=0.0)
            params["color_change"] = input("Color change to (default grey): ").strip() or "grey"
        elif death_choice == "2":
            params["mode"] = "necrosis"
            params["swell_rate"] = _ask_parameter_or_model("swell_rate", default_val=1.05)
            params["max_target_volume"] = _ask_parameter_or_model("max_target_volume", default_val=150.0)
            params["post_burst_shrink_rate"] = _ask_parameter_or_model("post_burst_shrink_rate", default_val=0.8)
            params["color_change"] = input("Color change to (default grey): ").strip() or "grey"
            fields = []
            while True:
                f_name = input("Release field name (or enter to skip): ").strip()
                if not f_name: break
                amount = _ask_parameter_or_model(f"release_amount_for_{f_name}", default_val=50.0)
                fields.append({"field_name": f_name, "amount": amount})
            params["fields"] = fields

        else:
            print("Invalid choice, defaulting to apoptosis.")
            params["mode"] = "apoptosis"
            params["shrink_rate"] = 0.95
            params["terminal_volume"] = 0.0

    # ============================================================
    # SECRETE / UPTAKE
    # ============================================================
    elif behaviour == "secrete/uptake":
        print("\n--- FieldSecretor (Secretion & Uptake) Wizard ---")
        params["field_name"] = input("Target chemical field name (e.g., VEGF): ").strip()

        print("\nSupported Modes:")
        print(" [1] secreteInsideCell                  [5] uptakeInsideCell")
        print(" [2] secreteInsideCellAtBoundary        [6] uptakeInsideCellAtBoundary")
        print(" [3] secreteOutsideCellAtBoundary       [7] uptakeOutsideCellAtBoundary")
        print(" [4] secreteInsideCellAtCOM             [8] uptakeInsideCellAtCOM")
        print(" [9] secreteInsideCellAtBoundaryOnContactWith")
        print(" [10] secreteOutsideCellAtBoundaryOnContactWith")
        print(" [11] uptakeInsideCellAtBoundaryOnContactWith")
        print(" [12] uptakeOutsideCellAtBoundaryOnContactWith")

        mode_map = {
            "1": "secreteInsideCell", "2": "secreteInsideCellAtBoundary",
            "3": "secreteOutsideCellAtBoundary", "4": "secreteInsideCellAtCOM",
            "5": "uptakeInsideCell", "6": "uptakeInsideCellAtBoundary",
            "7": "uptakeOutsideCellAtBoundary", "8": "uptakeInsideCellAtCOM",
            "9": "secreteInsideCellAtBoundaryOnContactWith",
            "10": "secreteOutsideCellAtBoundaryOnContactWith",
            "11": "uptakeInsideCellAtBoundaryOnContactWith",
            "12": "uptakeOutsideCellAtBoundaryOnContactWith"
        }
        choice = input("Select Mode [1]: ").strip() or "1"
        params["secret_mode"] = mode_map.get(choice, "secreteInsideCell")

        if "uptake" in params["secret_mode"]:
            params["amount"] = _ask_parameter_or_model("max_uptake_amount", default_val=1.0)
            params["relative_uptake"] = _ask_parameter_or_model("relative_uptake_rate", default_val=0.1)
        else:
            params["amount"] = _ask_parameter_or_model("secretion_concentration", default_val=1.0)
            params["relative_uptake"] = 0.0

        if "OnContactWith" in params["secret_mode"]:
            params["contact_types"] = input("Contact cell types (comma separated, e.g. Tumor,Normal): ").strip()

        params["total_count"] = input("Track total amount? (y/n) [n]: ").strip().lower() == "y"

    # ============================================================
    # DORMANCY
    # ============================================================
    elif behaviour == "dormancy":
        print("\n--- Dormancy & Reactivation (Sleep/Restore) Wizard ---")
        print("Select Mode:")
        print(" [1] dormant    (Enter sleep state, block actions)")
        print(" [2] reactivate (Wake up, restore cell cycle)")
        mode_choice = input("Select Mode [1]: ").strip() or "1"

        params["action"] = "reactivate" if mode_choice == "2" else "dormant"

    # ============================================================
    # PHAGOCYTOSIS
    # ============================================================
    elif behaviour == "phagocytosis":
        print("\n--- Phagocytosis (Cell Engulfment) Wizard ---")

        target_cell = input("Target cell type to engulf/eat (e.g., ApoptoticCell): ").strip()
        while not target_cell:
            target_cell = input("Target cell type cannot be empty. Please re-enter: ").strip()

        print("\nSelect Phagocytosis Mode based on cargo size:")
        print(" [1] absorption (Small targets/Bacteria: concurrent eating)")
        print(" [2] engulfment  (Large cells/Apoptotic: one-by-one locking)")
        print(" [3] frustrated  (Huge targets/Parasites: frustrated eating)")
        mode_choice = input("Select Mode [2]: ").strip() or "2"

        if mode_choice == "1":
            phago_mode = "absorption"
        elif mode_choice == "3":
            phago_mode = "frustrated"
        else:
            phago_mode = "engulfment"

        if phago_mode != "frustrated":
            eating_rate = _ask_parameter_or_model("eating_rate", default_val=2.0)
        else:
            print("In 'frustrated' mode, volumetric rate is set to 0 (Fusion triggered instead).")
            eating_rate = 0.0

        print("\n[Optional] Do you want this cell to leak chemicals/fields into environment while eating?")
        leak_field = input("Enter Field Name (Leave blank for none/Clean Eating): ").strip()

        if leak_field:
            leak_amount = _ask_parameter_or_model(f"leakage_amount_of_{leak_field}", default_val=10.0)
        else:
            leak_field = "None"
            leak_amount = 0.0

        params.update({
            "phago_mode": phago_mode,
            "target_cell_type": target_cell,
            "eating_rate": eating_rate,
            "leak_field": leak_field,
            "leak_amount": leak_amount
        })

    # ============================================================
    # CHEMOTAXIS
    # ============================================================
    elif behaviour == "chemotaxis":
        params["mode"] = "chemotaxis"

        print("\nTargeting Strategy:")
        print("1 - break (Random Selection)")
        print("2 - specify cell ID")
        print("3 - specify position coordinates")
        t_choice = input("Choice: ").strip()

        if t_choice == "1":
            params["target_strategy"] = "break"
        elif t_choice == "2":
            params["target_strategy"] = "id"
            params["target_cell_id"] = int(input("Enter Cell ID: "))
        elif t_choice == "3":
            params["target_strategy"] = "coordinate"
            params["target_x"] = int(input("X coordinate: "))
            params["target_y"] = int(input("Y coordinate: "))
            params["target_z"] = int(input("Z coordinate (default 0): ") or 0)

        print("\n--- CC3D Core Chemotaxis Parameters ---")
        params["field_name"] = input("Chemical Field Name (e.g., ATTR): ").strip() or "ATTR"

        params["lambda"] = _ask_parameter_or_model("chemotaxis_lambda", default_val=20.0)

        print("\nFormula Modification:")
        print("1 - Standard\n2 - Saturation\n3 - SaturationLinear\n4 - LogScaled")
        f_choice = input("Choice (default 1): ").strip()

        params["formula"] = "Standard"
        if f_choice == "2":
            params["formula"] = "Saturation"
            params["coef"] = _ask_parameter_or_model("saturation_coef", default_val=200.0)
        elif f_choice == "3":
            params["formula"] = "SaturationLinear"
            params["coef"] = _ask_parameter_or_model("saturation_linear_coef", default_val=2.0)
        elif f_choice == "4":
            params["formula"] = "LogScaled"
            params["coef"] = _ask_parameter_or_model("log_scaled_coef", default_val=3.0)

        if "coef" in params:
            coef_marker = "DYNAMIC" if isinstance(params["coef"], (dict, list)) else params["coef"]
            coef_part = f",coef={coef_marker}"
        else:
            coef_part = ""
        params["mode_param"] = f"field={params['field_name']},lambda=DYNAMIC,formula={params['formula']}{coef_part}"

    # ============================================================
    # FORCE
    # ============================================================
    elif behaviour == "force":
        print("\n--- ExternalPotential Force Wizard ---")
        modes = {
            "1": "vector",
            "2": "stored_vector",
            "3": "toward_position",
            "4": "away_from_position",
            "5": "toward_cell_id",
            "6": "toward_nearest_type",
            "7": "away_from_nearest_type",
            "8": "toward_field_gradient",
            "9": "clear",
        }
        print("1 - vector")
        print("2 - stored_vector")
        print("3 - toward_position")
        print("4 - away_from_position")
        print("5 - toward_cell_id")
        print("6 - toward_nearest_type")
        print("7 - away_from_nearest_type")
        print("8 - toward_field_gradient")
        print("9 - clear")
        mode_choice = input("Force mode [1]: ").strip() or "1"
        params["mode"] = modes.get(mode_choice, "vector")

        if params["mode"] != "clear":
            params["force"] = _ask_parameter_or_model("external_potential_force", default_val=10.0)
            params["persist"] = input("Persist force until clear/overwrite? (y/n) [n]: ").strip().lower() == "y"
            if params["persist"]:
                params["decay"] = _ask_parameter_or_model("force_decay_multiplier", default_val=1.0)

        if params["mode"] == "vector":
            params["dx"] = _ask_float("dx", 1.0)
            params["dy"] = _ask_float("dy", 0.0)
            params["dz"] = _ask_float("dz", 0.0)
        elif params["mode"] == "stored_vector":
            params["vector_prefix"] = input("cell.dict vector prefix [orientation]: ").strip() or "orientation"
        elif params["mode"] in {"toward_position", "away_from_position"}:
            params["target_x"] = _ask_float("target x", 0.0)
            params["target_y"] = _ask_float("target y", 0.0)
            params["target_z"] = _ask_float("target z", 0.0)
        elif params["mode"] == "toward_cell_id":
            params["target_cell_id"] = int(input("Target cell ID: ").strip())
        elif params["mode"] in {"toward_nearest_type", "away_from_nearest_type"}:
            params["target_type"] = input("Target cell type: ").strip()
        elif params["mode"] == "toward_field_gradient":
            params["field_name"] = input("Field name: ").strip()
            params["gradient_step"] = _ask_float("Gradient finite-difference step", 1.0)

    # ============================================================
    # COMPARTMENT
    # ============================================================
    elif behaviour == "compartmentalize":
        print("\n--- Compartmentalize Chain Wizard ---")
        actions = {
            "1": "initialize_cluster",
            "2": "extend_chain",
            "3": "branch_chain",
        }
        print("1 - initialize_cluster")
        print("2 - extend_chain")
        print("3 - branch_chain")
        action_choice = input("Action [2]: ").strip() or "2"
        params["action"] = actions.get(action_choice, "extend_chain")

        params["segment_type"] = input("Segment cell type (body compartment): ").strip()
        tip_type = input("Tip cell type [same as segment_type]: ").strip()
        params["tip_type"] = tip_type or params["segment_type"]

        direction_modes = {
            "1": "stored_vector",
            "2": "vector",
            "3": "random_persistent",
            "4": "toward_position",
            "5": "toward_field_gradient",
            "6": "inherit_force_vector",
        }
        print("\nDirection mode:")
        print("1 - stored_vector")
        print("2 - vector")
        print("3 - random_persistent")
        print("4 - toward_position")
        print("5 - toward_field_gradient")
        print("6 - inherit_force_vector")
        d_choice = input("Direction mode [1]: ").strip() or "1"
        params["direction_mode"] = direction_modes.get(d_choice, "stored_vector")

        if params["direction_mode"] == "vector":
            params["dx"] = _ask_float("dx", 1.0)
            params["dy"] = _ask_float("dy", 0.0)
            params["dz"] = _ask_float("dz", 0.0)
        elif params["direction_mode"] == "toward_position":
            params["target_x"] = _ask_float("target x", 0.0)
            params["target_y"] = _ask_float("target y", 0.0)
            params["target_z"] = _ask_float("target z", 0.0)
        elif params["direction_mode"] == "toward_field_gradient":
            params["field_name"] = input("Field name: ").strip()
            params["gradient_step"] = _ask_float("Gradient finite-difference step", 1.0)

        params["extension_interval"] = _ask_parameter_or_model("extension_interval", default_val=1.0)
        params["step_length"] = _ask_parameter_or_model("step_length", default_val=1.0)
        params["max_length"] = _ask_float("Max chain length, 0 means unlimited", 0.0)
        params["search_radius"] = _ask_parameter_or_model("search_radius", default_val=3.0)
        print("\nSite selection mode:")
        print("1 - empty_first: prefer medium/empty sites, fallback to replacement")
        print("2 - occupied_first: prefer replacing allowed occupied cell pixels")
        print("3 - front_occupied_first: only prefer replacement exactly in front")
        site_choice = input("Site selection mode [1]: ").strip() or "1"
        params["site_selection_mode"] = {
            "1": "empty_first",
            "2": "occupied_first",
            "3": "front_occupied_first",
        }.get(site_choice, "empty_first")
        params["direction_noise"] = _ask_float("Direction noise in radians per extension", 0.0)
        params["allow_occupied_site"] = input("Allow replacing occupied target pixels? (y/n) [n]: ").strip().lower() == "y"
        if params["allow_occupied_site"]:
            params["replace_target_types"] = input("Replace target cell types, comma-separated [HostCell]: ").strip() or "HostCell"
        params["internal_contact_energy"] = _ask_float("ContactInternal energy between chain compartments", 2.0)
        params["internal_neighbor_order"] = int(_ask_float("ContactInternal NeighborOrder", 4.0))

        if params["action"] == "branch_chain":
            params["branch_probability"] = _ask_parameter_or_model("branch_probability", default_val=1.0)

        params["use_fpp_link"] = input("Create INTERNAL FPP link between compartment segments? (y/n) [n]: ").strip().lower() == "y"
        if params["use_fpp_link"]:
            params["link_lambda"] = _ask_float("Internal FPP lambda distance", 10.0)
            params["target_distance"] = _ask_float("Internal FPP target distance", 0.0)
            params["max_distance"] = _ask_float("Internal FPP max distance", 0.0)

    # ============================================================
    # FPP LINK
    # ============================================================
    elif behaviour == "fpp_link":
        print("\n--- FPP Link Wizard ---")
        print("This creates ordinary FocalPointPlasticity links between cells.")
        modes = {
            "1": "nearest_type",
            "2": "cell_id",
            "3": "all_within_distance",
            "4": "clear",
        }
        print("1 - nearest_type: link this cell to nearest partner cell type")
        print("2 - cell_id: link this cell to a specific partner cell id")
        print("3 - all_within_distance: link this cell to partner cells within radius")
        print("4 - clear: remove ordinary FPP links from this cell")
        mode_choice = input("Mode [1]: ").strip() or "1"
        params["mode"] = modes.get(mode_choice, "nearest_type")

        if params["mode"] != "clear":
            params["partner_type"] = input("Partner cell type for XML pair and lookup: ").strip()
            if params["mode"] == "cell_id":
                params["target_cell_id"] = _ask_float("Target/partner cell id", 0.0)
            if params["mode"] in {"nearest_type", "all_within_distance"}:
                params["max_search_distance"] = _ask_float("Max search distance, 0 means unlimited", 0.0)
            if params["mode"] == "all_within_distance":
                params["max_links"] = int(_ask_float("Maximum links to create per trigger", 1.0))

            params["link_lambda"] = _ask_float("FPP lambda distance", 10.0)
            params["target_distance"] = _ask_float("FPP target distance", 0.0)
            params["max_distance"] = _ask_float("FPP max distance", 0.0)

    # ============================================================
    # INTRACELLULAR MODEL
    # ============================================================
    elif behaviour == "intracellular_model":
        params.update(_collect_intracellular_model_rule_params(registry))

    # ============================================================
    # SUBCELLULAR SYSTEM
    # ============================================================
    elif behaviour == "subcellular":
        params.update(_collect_subcellular_rule_params(registry))

    # ============================================================
    # Frequency Control Wizard
    # ============================================================
    params["frequency"] = _ask_frequency_control()

    params["once"] = input("\nTrigger once? (y/n): ").strip().lower() == "y"
    params["debug"] = input("Debug mode? (y/n): ").strip().lower() == "y"

    # =========================
    # build rule
    # =========================

    rule = build_rule(behaviour, params)

    if duplicate_rule_action == "overwrite":
        removed = _replace_rules_by_id(registry, params["id"], rule)
        print(f"♻️ Overwriting Rule ID {params['id']}: removed {removed} existing rule(s).")

    handle_new_rule_registration(registry, rule, lambda m, n, _:ask_params_cli(m, n, registry), sm, injector)

    return rule

def cli_import_csv(csv_path, registry, sm, injector):
    print(f"📂 Importing rules from: {csv_path}...")

    compiled_rules = import_rules_from_csv(csv_path)
    if not compiled_rules:
        print("⚠️ No valid rules found in CSV.")
        return

    for standard_rule in compiled_rules:
        try:
            handle_new_rule_registration(
                registry,
                standard_rule,
                ask_params_cli,
                sm,
                injector
            )
            print(f"✅ Rule [ID: {standard_rule.get('id')}] synced.")
        except Exception as e:
            print(f"❌ Error syncing rule: {e}")
            continue

    summary = registry.commit_artifacts(quiet=True)
    print(f"🚀 Successfully imported {len(compiled_rules)} rules.")
    print(f"XML updated: {'yes' if summary.get('xml_updated') else 'no'}")
    print(f"Generated code: {'yes' if summary.get('code_generated') else 'no'}")
    print(f"Source project artifacts synced: {'yes' if summary.get('source_artifacts_synced') else 'no'}")
    if summary.get("source_artifact_error"):
        print(f"Source artifact sync error: {summary['source_artifact_error']}")
