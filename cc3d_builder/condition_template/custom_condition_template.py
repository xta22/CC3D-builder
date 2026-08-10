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

Interactive parameters:
    Condition-only scripts do not auto-scan this file for parameter names.
    Enter values in the Custom condition parameter prompt or edit the condition
    params JSON manually. For this template, enter:

        state_key=custom_metric, threshold=1.0
"""


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def validate(cell, engine, params):
    """Return True when the custom condition matches."""
    if cell is None:
        return False

    # EDIT HERE: choose which user-provided parameters this condition reads.
    state_key = params.get("state_key", "custom_metric")
    threshold = _to_float(params.get("threshold", 1.0), 1.0)

    # EDIT HERE: replace this state lookup with project-specific condition logic.
    state = getattr(cell, "dict", {}).get("state", {})
    value = _to_float(state.get(state_key, 0.0), 0.0)

    # EDIT HERE: return True when the rule case should match.
    return value >= threshold


def evaluate(cell, engine, params):
    """Alias used by generated code when validate is not present."""
    return validate(cell, engine, params)
