"""
Template for a RuleParser Custom condition block.

Use this when only the condition is custom and the rule action should still be
handled by a normal RuleParser behaviour.

Expected JSON shape:

{
    "condition_type": "Custom",
    "script_path": "Rules_project/Simulation/custom_scripts/my_condition.py",
    "params": {
        "state_key": "custom_metric",
        "threshold": 1.0
    }
}

Runtime entry point:
    validate(cell, engine, params) -> bool

Generated-code entry point:
    validate(cell, engine, params) -> bool
    or evaluate(cell, engine, params) -> bool

Where to edit:
    1. Keep the function signatures unchanged.
    2. Edit the parameter names read from params.get(...).
    3. Edit the logic inside validate(...).

Runtime helpers available in both RuleEngine and generated-code runtimes:
    Canonical catalog:
        cc3d_builder.template.custom_runtime_helpers.CUSTOM_RUNTIME_HELPERS

    Runtime introspection:
        engine.available_helpers()

    engine.available_helpers() -> dict
    engine.ensure_cell_state(cell) -> dict
    engine.get_current_mcs() -> int
    engine.resolve_numeric(value, cell=None, default=0.0) -> float
    engine.target_cells(target_type_name_or_all) -> list[cell]
    engine.get_cell_type_id(type_name) -> int | None
    engine.get_cell_type_name(cell) -> str
    engine.get_field_value(field_name, cell) -> float
    engine.get_neighbor_data(cell, include_medium=False) -> list[(cell, area)]
    engine.get_neighbor_cells(cell) -> list[cell]
    engine.get_contact_ratio(cell, target_type_name) -> float
    engine.get_min_distance_to_type(cell, target_type_name) -> float
    engine.get_specific_surface_area(cell) -> float
    engine.get_elongation_ratio(cell) -> float
    engine.get_intracellular_value(cell, model_name, variable, default=0.0) -> value
    engine.get_subcellular_value(cell, system, variable="stage", default=0.0) -> value

Template-local conversion helpers included below:
    _to_float(value, default=0.0) -> float
    _to_int(value, default=0) -> int

Parameter convention:
    Numeric parameters should use engine.resolve_numeric(...). It accepts both
    static numbers and dynamic expressions such as {volume} * 0.01.
    String/name parameters should use params.get(<key>) or "default" so blank
    GUI/CLI inputs still fall back to the default.

Interactive parameters:
    GUI/CLI scans literal params.get(...) keys in this file and pre-fills
    their defaults. You can accept defaults, edit values, or add manual keys.
    For this template:

        state_key=custom_metric, threshold=1.0
"""


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


def validate(cell, engine, params):
    """Return True when the custom condition matches."""
    if cell is None:
        return False

    # EDIT HERE: choose which user-provided parameters this condition reads.
    state_key = params.get("state_key") or "custom_metric"
    threshold = engine.resolve_numeric(params.get("threshold", 1.0), cell, 1.0)

    # EDIT HERE: replace this state lookup with project-specific condition logic.
    state = engine.ensure_cell_state(cell)
    value = engine.resolve_numeric(state.get(state_key, 0.0), cell, 0.0)

    # EDIT HERE: return True when the rule case should match.
    return value >= threshold


def evaluate(cell, engine, params):
    """Alias used by generated code when validate is not present."""
    return validate(cell, engine, params)
