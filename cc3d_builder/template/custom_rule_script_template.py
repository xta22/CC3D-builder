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

Runtime helpers available in both RuleEngine and generated-code runtimes:
    Canonical catalog:
        cc3d_builder.template.custom_runtime_helpers.CUSTOM_RUNTIME_HELPERS

    Runtime introspection:
        context.available_helpers()

    context.available_helpers() -> dict
    context.ensure_cell_state(cell) -> dict
    context.get_current_mcs() -> int
    context.resolve_numeric(value, cell=None, default=0.0) -> float
    context.target_cells(target_type_name_or_all) -> list[cell]
    context.get_cell_type_id(type_name) -> int | None
    context.get_cell_type_name(cell) -> str
    context.get_field_value(field_name, cell) -> float
    context.get_neighbor_data(cell, include_medium=False) -> list[(cell, area)]
    context.get_neighbor_cells(cell) -> list[cell]
    context.get_contact_ratio(cell, target_type_name) -> float
    context.get_min_distance_to_type(cell, target_type_name) -> float
    context.get_specific_surface_area(cell) -> float
    context.get_elongation_ratio(cell) -> float
    context.get_intracellular_value(cell, model_name, variable, default=0.0) -> value
    context.get_subcellular_value(cell, system, variable="stage", default=0.0) -> value

Template-local conversion helpers included below:
    _to_float(value, default=0.0) -> float
    _to_int(value, default=0) -> int

Parameter convention:
    Numeric parameters should use context.resolve_numeric(...). It accepts both
    static numbers and dynamic expressions such as {volume} * 0.01.
    String/name parameters should use params.get(<key>) or "default" so blank
    GUI/CLI inputs still fall back to the default.

Interactive parameters:
    GUI/CLI scans literal parameter reads in this file for full custom
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


def _to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _iter_cells(context, target_type=""):
    """Return all cells or cells of a requested CC3D type name."""
    target_type = str(target_type or "").strip()
    return list(context.target_cells(target_type or "all"))


def match(context):
    """Return True when this custom rule should run in the current MCS."""
    # EDIT HERE: add global checks, such as MCS windows or project-wide state.
    return True


def run(context, params):
    """Execute custom model logic."""
    # EDIT HERE: these keys are detected by the full custom rule GUI wizard.
    target_type = params.get("target_type") or ""
    state_key = params.get("state_key") or "custom_flag"
    raw_value = params.get("value", 1.0)

    # EDIT HERE: replace this example state write with project-specific logic.
    for cell in _iter_cells(context, target_type):
        if cell is None:
            continue
        state = context.ensure_cell_state(cell)
        value = context.resolve_numeric(raw_value, cell, 1.0)
        state[state_key] = value
