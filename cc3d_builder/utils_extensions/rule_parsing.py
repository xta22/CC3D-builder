# cc3d_builder/utils_extensions/rule_parsing.py
import re

def extract_celltypes_from_rule(rule):
    """
    read only -- check what cell types are mentioned in json
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
        if apply_data.get("cell_type"):
            types.add(apply_data["cell_type"])

    valid_types = {str(t).strip() for t in types if t and str(t).strip()}
    system_keywords = {"Medium", "Environment", "Duration", "TimeWindow", "Probability"}
    return valid_types - system_keywords


def extract_params(content):
    pattern = r"params(?:\[['\"]|\.get\(['\"])(.+?)(?:['\"][, \)]|['\"]\])"
    matches = re.findall(pattern, content)
    unique_params = sorted(list(set(m for m in matches if m != 'get')))
    print(f">>> DEBUG: Regex extracted: {unique_params}")
    return unique_params

  
def extract_fields_from_rule(rule: dict) -> list:
    """
    read only -- Search for field_name in rule dict
    """
    found_fields = set()
    if 'cases' in rule and len(rule['cases']) > 0:
        when_cfg = rule['cases'][0].get('when', {})
    else:
        when_cfg = rule.get('when', {})
        
    c_type = when_cfg.get('condition_type') or when_cfg.get('type')

    if c_type == "Environment":
        f_name = when_cfg.get('params', {}).get('field_name')
        if f_name:
            found_fields.add(f_name)

    if c_type == "Environment":
        regulator = rule.get('apply', {}).get('regulator')
        if regulator and isinstance(regulator, str):
            found_fields.add(regulator)

    built_in = ["elongation", "volume", "surface", "none", "nan"]
    return [f for f in found_fields if f.lower() not in built_in]

