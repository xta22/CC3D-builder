# utils.py
# cc3d_builder/utils_extensions/utils.py
from cc3d_builder.utils_extensions.rule_parsing import (
    extract_celltypes_from_rule,
    extract_fields_from_rule,
    extract_params,
)
from cc3d_builder.core.rule_builder import build_rule
from cc3d_builder.core.rule_schema import validate_rule_schema


def _ask_cli_float(prompt, default):
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"Invalid number, using default {default}")
        return default


def _ask_cli_bool(prompt, default=False):
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{prompt} ({suffix}): ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "1", "true", "on"}


def _ask_field_params_cli(name):
    print(f"\n[New Field: {name}] Configure diffusion field")
    solver = input("Solver [DiffusionSolverFE]: ").strip() or "DiffusionSolverFE"
    diffusion = _ask_cli_float("Diffusion constant", 0.01)
    decay = _ask_cli_float("Decay constant", 0.0001)
    initial = input("Initial concentration expression [0.0]: ").strip() or "0.0"
    python_secretion = _ask_cli_bool("Control secretion through Python", False)

    boundary_conditions = {}
    if _ask_cli_bool("Configure boundary conditions", False):
        for axis in ["X", "Y", "Z"]:
            bc_type = input(f"{axis} boundary type [Periodic/ConstantDerivative/ConstantValue, default Periodic]: ").strip()
            bc_type = bc_type or "Periodic"
            if bc_type == "Periodic":
                boundary_conditions[axis] = {"type": "Periodic"}
            else:
                boundary_conditions[axis] = {
                    "type": bc_type,
                    "min_val": _ask_cli_float(f"{axis}.min value", 0.0),
                    "max_val": _ask_cli_float(f"{axis}.max value", 0.0),
                }

    return {
        "solver": solver,
        "diffusion_constant": diffusion,
        "decay_constant": decay,
        "initial_expression": initial,
        "boundary_conditions": boundary_conditions,
        "chemotaxis": [],
        "python_secretion": python_secretion,
    }

def ask_params_cli(mode, name, registry = None):
    """ CLI entry """
    if mode == "celltype":
        v = float(input(f"\n[New Type: {name}] Target Volume [50]: ") or 50)
        l = float(input(f"[New Type: {name}] Lambda Volume [10]: ") or 10)
        return {"targetVolume": v, "lambdaVolume": l}
    elif mode == "field":
        return _ask_field_params_cli(name)

    return None

def ask_params_gui(mode, name, parent):
    """
    Generic parameter retriever: supports both CellType and Field
    """
    from PyQt5.QtWidgets import QInputDialog, QDialog

    print(f"DEBUG: ask_params_gui called with mode='{mode}', name='{name}'")
    if mode == "celltype":
        target, ok1 = QInputDialog.getDouble(
            parent, f"New CellType: {name}", "targetVolume:", 50
        )
        lam, ok2 = QInputDialog.getDouble(
            parent, f"New CellType: {name}", "lambdaVolume:", 10
        )
        if ok1 and ok2:
            return {"targetVolume": target, "lambdaVolume": lam}
            

    elif mode == "field":
        available_cells = list(parent.registry.celltype_params.keys())
        from cc3d_builder.gui.field_setup_dialog import FieldSetupDialog
        dialog = FieldSetupDialog(name, available_cells, None, parent)
        
        if dialog.exec_() == QDialog.Accepted:
            field_params = dialog.get_data()
            
            if field_params.pop("ControlSecretionPython", False):
                
                flat_params = {
                    "id": f"auto_secrete_{name}",
                    "target": "global",
                    "field_name": name,
                    "secret_mode": "secreteInsideCell",
                    "amount": 0.1,                     
                    "relative_uptake": 0.0,
                    "contact_types": "",
                    "total_count": False            
                }
                
                secrete_rule = build_rule("secrete/uptake", flat_params)
                
                parent.registry.add_rule(secrete_rule)
                print(f"✅ [Auto Gen] Seamlessly generated new standard secrete/uptake rule for {name}")
                
            return field_params

def handle_new_rule_registration(registry, rule, input_handler, sm, injector):
    # Rules must already be compiled by build_rule into strict flat cases.
    if "cases" not in rule or not rule["cases"]:
        raise ValueError("Rule registration expects build_rule() output with non-empty flat cases")

    validate_rule_schema(rule)
    summary = {
        "rule_id": rule.get("id"),
        "new_celltypes": [],
        "reused_celltypes": [],
        "new_fields": [],
        "reused_fields": [],
        "ignored_field_tokens": [],
    }

    # 1. Handle new cell types (unchanged, since cell_type extraction is usually reliable)
    new_types = extract_celltypes_from_rule(rule)
    for ct in new_types:
        if ct not in registry.celltype_params:
            print(f"🐣 [New CellType] Found: {ct}. Requesting parameters...")
            params_ct = input_handler("celltype", ct, registry)
            if params_ct:
                registry.add_celltype_params(
                    ct,
                    params_ct['targetVolume'],
                    params_ct['lambdaVolume'],
                    autosave=False,
                    rebuild_artifacts=False,
                )
                summary["new_celltypes"].append(ct)
        else:
            summary["reused_celltypes"].append(ct)

    # 2. Global field scanning (no longer relying on c_type, but directly inspecting fields in the rule)
    # extract_fields_from_rule internally scans when.field_name and flat case payload fields.
    new_fields = extract_fields_from_rule(rule)
    # Define keywords to exclude (morphology, contact logic, etc.)
    # These may appear in regulator positions but are NOT diffusion fields
    morph_keywords = ["elongation", "contact", "distance", "sphericity", "surface"]
    
    for f_name in new_fields:
        # Only trigger configuration if not excluded and not already registered
        if f_name.lower() not in morph_keywords:
            in_registry = f_name in registry.field_params
            if f_name not in registry.field_params:
                print(f"🧪 [New Field Detected] Found: {f_name}.")
                print(f"⚙️ [Configure] Opening diffusion setup for: {f_name}")
                params = input_handler("field", f_name, registry)
                if params:
                    registry.add_field_params(f_name, params, autosave=False, rebuild_artifacts=False)
                    summary["new_fields"].append(f_name)
            elif in_registry:
                summary["reused_fields"].append(f_name)
        else:
            summary["ignored_field_tokens"].append(f_name)

    # 3. Registry persistence. Artifact rebuild/code generation happens once
    # at the final commit step, not during each rule registration.
    if rule not in registry.rules:
        registry.rules.append(rule)
    registry._build_index()
    registry.last_registration_summary = summary
    registry.save(rebuild_artifacts=False, quiet=True)

    print(f"✅ [Handle] Rule {rule.get('id')} registered in project state.\n")
    return summary

def _register_auto_secretion(registry, f_name):
    auto_rule = build_rule(
        "secrete/uptake",
        {
            "id": f"auto_sec_{f_name}",
            "target": "global",
            "field_name": f_name,
            "secret_mode": "secreteInsideCell",
            "amount": 0.1,
            "relative_uptake": 0.0,
            "contact_types": [],
            "total_count": False,
        },
    )
    if not any(r.get('id') == auto_rule['id'] for r in registry.rules):
        registry.rules.append(auto_rule)

def process_custom_script(file_path, registry, ask_params_func, extract_params_func=None, existing_params=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if extract_params_func:
        detected_keys = extract_params_func(content)
    else:
        detected_keys = extract_params(content)

    import importlib.util
    new_types = []
    try:
        spec = importlib.util.spec_from_file_location("temp_mod", file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        new_types = getattr(module, "REQUIRED_CELL_TYPES", [])
    except Exception as e:
        print(f"Type detection skip: {e}")

    for ct in new_types:
        if ct not in registry.celltype_params:
            p = ask_params_func(ct)
            if p:
                registry.add_celltype_params(ct, p["targetVolume"], p["lambdaVolume"])

    from cc3d_builder.gui.ManageRuleWindow import ParamEditorDialog
    dialog = ParamEditorDialog(detected_keys, existing_params or {})
    if dialog.exec_():
        final_p = dialog.get_final_params()
        final_p["manual_types"] = new_types
        return final_p

    return None
