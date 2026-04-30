# cc3d_builder/utils_extensions/rule_parsing.py
import re
import pandas as pd

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

  
def extract_fields_from_rule(rule):
    """
    screen all places possibly storing fields
    """
    raw_fields = set()
    
    # # Any term listed here will NOT be treated as a Diffusion Field
    INTERNAL_KEYWORDS = {
        "elongation", "sphericity", "surface", "contact", 
        "distance", "volume", "area", "none", "nan", "true", "false"
    }

    for case in rule.get('cases', []):
        when = case.get('when', {})
        params = when.get('params', {})
        
        f_name = params.get('field_name') or when.get('field_name')
        if f_name:
            raw_fields.add(str(f_name).strip())

        apply = case.get('apply', {})
        reg = apply.get('regulator')
        if reg:
            raw_fields.add(str(reg).strip())

    valid_fields = []
    for f in raw_fields:
        f_str = str(f).lower()
        
        if pd.isna(f) or f_str == "nan" or f_str == "":
            continue
            
        if f_str in INTERNAL_KEYWORDS:
            continue
            
        valid_fields.append(f)
        
    return valid_fields