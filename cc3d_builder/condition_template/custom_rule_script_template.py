"""
Template for a RuleParser full custom rule script.

Use this when the rule behaviour is custom_script and the script owns the full
action logic. The rule engine passes the steppable-like runtime context as
`context`; the generated standalone code does the same.

Expected JSON case payload:

{
    "script_path": "Rules_project/Simulation/custom_scripts/my_rule.py",
    "apply_params": {
        "target_type": "CellTypeA",
        "state_key": "custom_flag",
        "value": 1.0
    }
}

Runtime entry points:
    match(context) -> bool
    run(context, params) -> None

Where to edit:
    1. Keep match(context) and run(context, params) signatures unchanged.
    2. Add any needed project cell types to REQUIRED_CELL_TYPES.
    3. Edit match(...) when the whole custom rule needs a global guard.
    4. Edit run(...) to implement the custom action.

Interactive parameters:
    The GUI scans literal params.get("...") keys in this file for full custom
    rule scripts. In this template, target_type, state_key, and value become
    editable script parameters when the script is selected through the GUI.
"""

# EDIT HERE: list cell types this script may need the project to register.
REQUIRED_CELL_TYPES = []


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iter_cells(context, target_type=""):
    """Return all cells or cells of a requested CC3D type name."""
    target_type = str(target_type or "").strip()

    if target_type and hasattr(context, "_target_cells"):
        return list(context._target_cells(target_type))

    if target_type and hasattr(context, "cell_list_by_type"):
        type_id = getattr(context, target_type.upper(), None)
        if type_id is not None:
            return list(context.cell_list_by_type(type_id))

    return list(getattr(context, "cell_list", []) or [])


def match(context):
    """Return True when this custom rule should run in the current MCS."""
    # EDIT HERE: add global checks, such as MCS windows or project-wide state.
    return True


def run(context, params):
    """Execute custom model logic."""
    # EDIT HERE: these keys are detected by the full custom rule GUI wizard.
    target_type = params.get("target_type", "")
    state_key = params.get("state_key", "custom_flag")
    value = _to_float(params.get("value", 1.0), 1.0)

    # EDIT HERE: replace this example state write with project-specific logic.
    for cell in _iter_cells(context, target_type):
        if cell is None:
            continue
        if hasattr(context, "_ensure_cell_dict"):
            context._ensure_cell_dict(cell)
        else:
            cell.dict.setdefault("state", {})
        cell.dict["state"][state_key] = value
