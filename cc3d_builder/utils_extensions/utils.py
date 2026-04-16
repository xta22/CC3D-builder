import re
def extract_celltypes_from_rule(rule):
    """
    catch cell types
    """
    types = set()

    if rule.get("target"):
        types.add(rule["target"])
    
    if rule.get("cell_type"):
        types.add(rule["cell_type"])

    cases = rule.get("cases", [rule]) 
    
    for case in cases:
        when = case.get("when", {})
        cond_type = when.get("condition_type", "")
        if cond_type in ["Contact", "Distance"]:
            target_type = when.get("params", {}).get("target_type")
            if target_type:
                types.add(target_type)

        apply_data = case.get("apply", {})
        print(f"APPLY_DATA:{apply_data}")
        if apply_data.get("new_type"):
            types.add(apply_data["new_type"])
            
        if apply_data.get("parent_type"):
            types.add(apply_data["parent_type"])
            
        if apply_data.get("child_type"):
            types.add(apply_data["child_type"])

        if apply_data.get("cell_type"):
            types.add(apply_data["cell_type"]) 

    valid_types = {str(t).strip() for t in types if t and str(t).strip()}
    
    system_keywords = {"Medium", "Environment", "Duration", "TimeWindow", "Probability"}
    
    return valid_types - system_keywords


def ask_celltype_params(name):

    print(f"\n[New CellType Detected] {name}")

    target = float(input("targetVolume: "))
    lam = float(input("lambdaVolume: "))

    return {
        "targetVolume": target,
        "lambdaVolume": lam
    }


def handle_new_rule_registration(registry, rule, ask_params_func):
    """
    registry: 
    rule: {}
    ask_params_func: （CLI with input，GUI with window）
    """
    from utils_extensions.utils import extract_celltypes_from_rule
    from injector.inject import process_and_inject_rule

    # 1. extract new cell types
    new_types = extract_celltypes_from_rule(rule)
    for ct in new_types:
        if ct not in registry.celltype_params:
            params_ct = ask_params_func(ct)
            if params_ct:
                registry.add_celltype_params(
                    ct, params_ct["targetVolume"], params_ct["lambdaVolume"]
                )
    
    # 2. write in new rules 
    registry.add_rule(rule)

    # 3. XML and steppable injection
    process_and_inject_rule(registry.project_path, registry, rule)

def process_custom_script(file_path, registry, ask_params_func, extract_params_func=None, existing_params=None):
        """
        scanning the scripts, find and register for new cells, pop out the editting window.
        """
        # A. static (Params)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()


        if extract_params_func:
            # passed in as an argument
            detected_keys = extract_params_func(content)
        else:
            # local extract_params
            detected_keys = extract_params(content)

        # B. dynamic (Cell Types)
        import importlib.util
        new_types = []
        try:
            spec = importlib.util.spec_from_file_location("temp_mod", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            new_types = getattr(module, "REQUIRED_CELL_TYPES", [])
        except Exception as e:
            print(f"Type detection skip: {e}")

        # C. register for new cells
        for ct in new_types:
            if ct not in registry.celltype_params:
                p = ask_params_func(ct)
                if p:
                    registry.add_celltype_params(ct, p["targetVolume"], p["lambdaVolume"])

        # D. pop out parameter editting tools
        from gui.ManageRuleWindow import ParamEditorDialog
        dialog = ParamEditorDialog(detected_keys, existing_params or {})
        if dialog.exec_():
            final_p = dialog.get_final_params()
            final_p["manual_types"] = new_types 
            return final_p
        
        return None


def extract_params(content):
    # 1. match params['key']
    # 2. match params.get('key', ...)
    pattern = r"params(?:\[['\"]|\.get\(['\"])(.+?)(?:['\"][, \)]|['\"]\])"
    
    matches = re.findall(pattern, content)
    # exclude get 
    unique_params = sorted(list(set(m for m in matches if m != 'get')))
    print(f">>> DEBUG: Regex extracted: {unique_params}")
    return unique_params
