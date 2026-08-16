# rule_parsing.py
# cc3d_builder/utils_extensions/rule_parsing.py
import re
import pandas as pd
from cc3d_builder.core.rule_schema import case_payload

try:
    from cc3d_builder.core.state_key_catalog import STATE_KEY_CATALOG
except Exception:
    STATE_KEY_CATALOG = []


FIELD_KEYS = {"field_name", "field", "leak_field"}
PHYSICAL_MODEL_NAMES = {"hill", "linear", "expression"}


def _add_values(target_set, value):
    if isinstance(value, list):
        for item in value:
            _add_values(target_set, item)
    elif value is not None:
        text = str(value).strip()
        if text:
            target_set.add(text)


def _collect_explicit_field_refs(value, target_set):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FIELD_KEYS:
                _add_values(target_set, item)
            _collect_explicit_field_refs(item, target_set)
    elif isinstance(value, list):
        for item in value:
            _collect_explicit_field_refs(item, target_set)


def _collect_physical_model_regulators(value, target_set):
    if isinstance(value, dict):
        model_name = str(value.get("model", "")).strip().lower()
        if model_name in PHYSICAL_MODEL_NAMES and "regulator" in value:
            _add_values(target_set, value.get("regulator"))

        for item in value.values():
            _collect_physical_model_regulators(item, target_set)
    elif isinstance(value, list):
        for item in value:
            _collect_physical_model_regulators(item, target_set)


def _collect_environment_condition_fields(when, target_set):
    condition_type = str(when.get("condition_type", "")).strip().lower()
    if condition_type != "environment":
        return

    params = when.get("params", {})
    if isinstance(params, dict):
        _add_values(
            target_set,
            params.get("field_name") or params.get("field") or params.get("regulator"),
        )
    _add_values(target_set, when.get("field_name") or when.get("field"))


def _known_state_keys():
    state_keys = set()
    for category in STATE_KEY_CATALOG:
        for item in category.get("items", []):
            if not item:
                continue
            key = str(item[0]).strip()
            if not key or "<" in key or ">" in key:
                continue
            state_keys.add(key.lower())
    return state_keys


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
    screen all places explicitly storing CC3D diffusion fields.

    The same key name, especially "regulator", is used by both field-regulated
    physical models and state conditions. Only collect regulators from physical
    model payloads; state/native regulators such as division_count are not
    diffusion fields.
    """
    raw_fields = set()
    
    # Any term listed here will NOT be treated as a Diffusion Field
    INTERNAL_KEYWORDS = {
        "elongation", "sphericity", "surface", "contact", 
        "distance", "volume", "area", "none", "nan", "true", "false"
    } | _known_state_keys()

    for case in rule.get('cases', []):
        when = case.get('when', {})
        params = when.get('params', {})

        _collect_environment_condition_fields(when, raw_fields)
        _collect_explicit_field_refs(params, raw_fields)
        _collect_physical_model_regulators(params, raw_fields)

        payload = case_payload(case)

        _collect_explicit_field_refs(payload, raw_fields)
        _collect_physical_model_regulators(payload, raw_fields)

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
