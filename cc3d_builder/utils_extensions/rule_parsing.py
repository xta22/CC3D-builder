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

    def _search(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                # 检查所有可能的 Key 名
                if k in ["field_name", "regulator", "field"]:
                    if isinstance(v, str):
                        found_fields.add(v)
                else:
                    _search(v)
        elif isinstance(obj, list):
            for item in obj:
                _search(item)

    _search(rule)
    # 过滤掉 CC3D 内置的场（如果有的话）
    return list(found_fields)