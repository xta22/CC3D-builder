# rule_parsing.py
# cc3d_builder/utils_extensions/rule_parsing.py
import re
import pandas as pd
from cc3d_builder.core.rule_schema import case_payload


def _add_values(target_set, value):
    if isinstance(value, list):
        for item in value:
            _add_values(target_set, item)
    elif value is not None:
        text = str(value).strip()
        if text:
            target_set.add(text)


def _collect_field_refs(value, target_set):
    field_keys = {"field_name", "field", "regulator", "leak_field"}

    if isinstance(value, dict):
        for key, item in value.items():
            if key in field_keys:
                _add_values(target_set, item)
            _collect_field_refs(item, target_set)
    elif isinstance(value, list):
        for item in value:
            _collect_field_refs(item, target_set)


def extract_celltypes_from_rule(rule):
    """
    read only -- check what cell types are mentioned in json
    """
    types = set()

    if rule.get("target"):
        types.add(rule["target"])

    if rule.get("cell_type"):
        types.add(rule["cell_type"])

    cases = rule.get("cases", [])

    for case in cases:
        when = case.get("when", {})
        cond_type = when.get("condition_type", "")
        if cond_type in ["Contact", "Distance"]:
            target_type = when.get("params", {}).get("target_type")
            if target_type:
                types.add(target_type)

        payload = case_payload(case)
        for key in (
            "new_type",
            "parent_type",
            "child_type",
            "cell_type",
            "target_cell_type",
            "target_type",
            "partner_type",
            "segment_type",
            "tip_type",
        ):
            _add_values(types, payload.get(key))
        _add_values(types, payload.get("contact_types"))

    valid_types = {str(t).strip() for t in types if t and str(t).strip()}
    system_keywords = {"medium", "environment", "duration", "timewindow", "probability", "global", "none"}
    return {t for t in valid_types if t.lower() not in system_keywords}


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
    
    # Any term listed here will NOT be treated as a Diffusion Field
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
        _collect_field_refs(params, raw_fields)

        payload = case_payload(case)

        _collect_field_refs(payload, raw_fields)

        fields_list = payload.get('fields', [])
        if isinstance(fields_list, list):
            for f_item in fields_list:
                if isinstance(f_item, dict):
                    name = f_item.get('field_name')
                    _add_values(raw_fields, name)

    valid_fields = []
    for f in raw_fields:
        f_str = str(f).lower()
        
        # pandas for check
        if pd.isna(f) or f_str == "nan" or f_str == "":
            continue
            
        if f_str in INTERNAL_KEYWORDS:
            continue
            
        valid_fields.append(f)
        
    return valid_fields
