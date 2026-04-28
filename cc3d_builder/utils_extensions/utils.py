# cc3d_builder/utils_extensions/utils.py
from cc3d_builder.utils_extensions.rule_parsing import (
    extract_celltypes_from_rule,
    extract_fields_from_rule,
    extract_params,
)
from PyQt5.QtWidgets import (
    QInputDialog, QDialog, QApplication
)
import sys

def ask_params_cli(mode, name, registry = None):
    """ CLI entry """
    if mode == "celltype":
        v = float(input(f"\n[New Type: {name}] Target Volume [50]: ") or 50)
        l = float(input(f"[New Type: {name}] Lambda Volume [10]: ") or 10)
        return {"targetVolume": v, "lambdaVolume": l}
    elif mode == "field":
        print("Launching Diffusion Equation Solvers Now...")
        from cc3d_builder.gui.field_setup_dialog import FieldSetupDialog
        app = QApplication.instance()
        
        if not app:
            app = QApplication(sys.argv) # ??? 

        available_cells = [] # compatibility ??
        if registry:
            available_cells = list(registry.celltype_params.keys())
        dialog = FieldSetupDialog(name, available_cells)
        
        # 3. 运行对话框
        if dialog.exec_() == QDialog.Accepted:
            result = dialog.get_data()
            print(f"✅ Configuration received from GUI.")
            return result

    return None

def ask_params_gui(mode, name, parent):
    """
    Generic parameter retriever: supports both CellType and Field
    """
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
                secrete_rule = {
                    "id": f"auto_secrete_{name}",
                    "behaviour": "secrete",
                    "target": "global",
                    "apply": {"field": name, "rate": 0.1}
                }
                parent.registry.add_rule(secrete_rule)
                print(f"✅ Auto-generated secretion rule for {name}")
                
            return field_params
    return None

def handle_new_rule_registration(registry, rule, input_handler, sm, injector):
    '''
    input_handler: A function to retrieve parameters for new types or new fields
    GUI: self.ask_field_params_gui
    CLI: self.ask_field_params_cli
    '''
    new_types = extract_celltypes_from_rule(rule)
    for ct in new_types:
        if ct not in registry.celltype_params:
            params_ct = input_handler("celltype", ct, None)
            if params_ct:
                injector.ensure_volume_start_code(ct, params_ct['targetVolume'], params_ct['lambdaVolume'])
                registry.add_celltype_params(ct, params_ct['targetVolume'], params_ct['lambdaVolume'])

    extracted_fields = extract_fields_from_rule(rule)
    
    # Only process the rule when the regulator_type is explicitly set to Environment.
    actual_new_fields = []
    
    # Check the condition types within the rule.
    condition_type = rule.get('when', {}).get('condition_type')
    
    if condition_type == "Environment":
        actual_new_fields = extracted_fields
    else:
        print(f"ℹ️ Skipping field sync for {extracted_fields} because condition type is {condition_type}")
        actual_new_fields = []

    for f_name in actual_new_fields:
        if f_name not in registry.field_params:
            if sm.ensure_field(f_name):
                params = input_handler("field", f_name, None)
                if params:
                    registry.add_field_params(f_name, params)
            else:
                print(f"ℹ️ Field {f_name} already exists in registry.")
                
    if condition_type == "Morphology":
        prop_name = rule.get('when', {}).get('params', {}).get('field_name') 
        print(f"🛠️ Detecting Morphology: {prop_name}. Ensuring XML Plugins...")
        sm.ensure_plugin("MomentOfInertia")

    registry.rules.append(rule)
    from cc3d_builder.injector.inject import process_and_inject_rule
    process_and_inject_rule(registry.project_path, registry, rule)


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
