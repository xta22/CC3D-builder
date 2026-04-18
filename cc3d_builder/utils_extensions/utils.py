# cc3d_builder/utils_extensions/utils.py
from cc3d_builder.utils_extensions.rule_parsing import (
    extract_celltypes_from_rule,
    extract_params,
)

def ask_celltype_params(name):
    print(f"\n[New CellType Detected] {name}")
    target = float(input("targetVolume: "))
    lam = float(input("lambdaVolume: "))
    return {"targetVolume": target, "lambdaVolume": lam}


def handle_new_rule_registration(registry, rule, ask_params_func):
    new_types = extract_celltypes_from_rule(rule)
    for ct in new_types:
        if ct not in registry.celltype_params:
            params_ct = ask_params_func(ct)
            if params_ct:
                registry.add_celltype_params(
                    ct, params_ct["targetVolume"], params_ct["lambdaVolume"]
                )

    registry.add_rule(rule)

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