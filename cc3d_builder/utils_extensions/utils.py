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
        
        if apply_data.get("new_type"):
            types.add(apply_data["new_type"])
            
        if apply_data.get("parent_type"):
            types.add(apply_data["parent_type"])
            
        if apply_data.get("child_type"):
            types.add(apply_data["child_type"])

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


