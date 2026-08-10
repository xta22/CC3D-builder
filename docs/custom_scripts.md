# Custom Scripts

RuleParser supports two script scopes.

## Condition-Only Custom Script

Use a condition-only script when a normal RuleParser behaviour should still execute, but the `when` block needs custom Python logic.

Recommended location:

```text
Rules_project/Simulation/custom_scripts/
```

Template:

```text
cc3d_builder/condition_template/custom_condition_template.py
```

Rule shape:

```json
{
  "condition_type": "Custom",
  "script_path": "Rules_project/Simulation/custom_scripts/my_condition.py",
  "params": {
    "state_key": "custom_metric",
    "threshold": 1.0
  }
}
```

Required function:

```python
def validate(cell, engine, params):
    return True
```

`cell` is the current CC3D cell being tested. `engine` is the RuleParser runtime steppable or generated standalone steppable. `params` is the dictionary from the condition block.

Edit the copied script inside `validate(...)`. Keep the function signature unchanged.

Example edit point:

```python
def validate(cell, engine, params):
    state_key = params.get("state_key", "custom_metric")
    threshold = float(params.get("threshold", 1.0))
    value = float(cell.dict.get("state", {}).get(state_key, 0.0))
    return value >= threshold
```

`state_key` is interactive through the condition parameter block, not through automatic script scanning. In the GUI Custom condition prompt, enter:

```text
state_key=custom_metric, threshold=1.0
```

The same values are saved under the condition's `params` dictionary and can also be edited directly in JSON or through rule-block editing.

Generated standalone code also accepts:

```python
def evaluate(cell, engine, params):
    return True
```

### Minimal Condition-Only Example

Create:

```text
Rules_project/Simulation/custom_scripts/is_state_above_threshold.py
```

```python
def validate(cell, engine, params):
    if cell is None:
        return False

    state_key = params.get("state_key", "activation_score")
    threshold = float(params.get("threshold", 1.0))
    value = float(cell.dict.get("state", {}).get(state_key, 0.0))

    return value >= threshold
```

Use it inside a normal rule case:

```json
{
  "id": "activate_when_score_high",
  "target": "CellTypeA",
  "behaviour": "differentiate",
  "cases": [
    {
      "when": {
        "condition_type": "Custom",
        "script_path": "Rules_project/Simulation/custom_scripts/is_state_above_threshold.py",
        "params": {
          "state_key": "activation_score",
          "threshold": 1.0
        }
      },
      "mode": "type_switch",
      "new_type": "ActivatedCellType"
    }
  ],
  "frequency": 1,
  "once": false
}
```

In this example, the custom script only decides whether the case matches. If it returns `True`, the built-in `differentiate` behaviour executes the type switch. `state_key` is edited in the condition `params` block.

## Full Custom Rule Script

Use a full custom rule script when the whole rule action is custom and should not be handled by a built-in behaviour executor.

Recommended location:

```text
Rules_project/Simulation/custom_scripts/
```

Template:

```text
cc3d_builder/condition_template/custom_rule_script_template.py
```

Rule shape:

```json
{
  "id": "custom_1",
  "target": "global",
  "behaviour": "custom_script",
  "cases": [
    {
      "when": {"condition_type": "TRUE", "params": {}},
      "script_path": "Rules_project/Simulation/custom_scripts/my_rule.py",
      "apply_params": {
        "target_type": "CellTypeA",
        "state_key": "custom_flag",
        "value": 1.0
      }
    }
  ],
  "frequency": 1,
  "once": false
}
```

Required functions:

```python
def match(context):
    return True


def run(context, params):
    pass
```

`context` is the active RuleParser runtime steppable or generated standalone steppable. It can access CC3D helper APIs such as `cell_list`, `cell_list_by_type`, and generated helper methods when they are available. `params` is copied from `apply_params`.

Edit the copied script inside `match(...)` and `run(...)`. Keep both function signatures unchanged.

Example edit point:

```python
def run(context, params):
    target_type = params.get("target_type", "")
    state_key = params.get("state_key", "custom_flag")
    value = float(params.get("value", 1.0))

    for cell in context._target_cells(target_type):
        context._ensure_cell_dict(cell)
        cell.dict["state"][state_key] = value
```

For full custom rule scripts, parameter keys written as literal `params.get("...")` calls are scanned by the GUI when the script is selected. In the example above, `target_type`, `state_key`, and `value` become editable script parameters. The chosen values are saved under `apply_params`.

### Minimal Full Custom Rule Example

Create:

```text
Rules_project/Simulation/custom_scripts/set_state_for_target_cells.py
```

```python
def match(context):
    return True


def run(context, params):
    target_type = params.get("target_type", "CellTypeA")
    state_key = params.get("state_key", "custom_flag")
    value = float(params.get("value", 1.0))

    for cell in context._target_cells(target_type):
        context._ensure_cell_dict(cell)
        cell.dict["state"][state_key] = value
```

Use it as a `custom_script` rule:

```json
{
  "id": "set_custom_flag",
  "target": "global",
  "behaviour": "custom_script",
  "cases": [
    {
      "when": {"condition_type": "TRUE", "params": {}},
      "script_path": "Rules_project/Simulation/custom_scripts/set_state_for_target_cells.py",
      "apply_params": {
        "target_type": "CellTypeA",
        "state_key": "custom_flag",
        "value": 1.0
      }
    }
  ],
  "frequency": 1,
  "once": false
}
```

In this example, the script owns the action. It does not call a built-in behaviour. Because the script contains literal `params.get("target_type")`, `params.get("state_key")`, and `params.get("value")`, the full custom-rule GUI can expose those fields as editable parameters.

## Architecture Placement

Templates live in:

```text
cc3d_builder/condition_template/
```

Project-specific scripts should not be edited inside the template directory. Copy a template into the sandbox or source project, then reference the copied file from `rules.json`.

Use an absolute script path when portability is not required. For project-local paths, make sure the path is resolvable from the process that launches CC3D. Generated standalone code also tries paths relative to the generated `SimulationStepCode.py` directory.

Suggested project layout:

```text
Rules_project/
  Simulation/
    custom_scripts/
      my_condition.py
      my_rule.py
```

Condition-only scripts are part of condition evaluation. Full custom rule scripts are part of behaviour execution through `custom_script`.

## State Keys

`state_key` is not a reserved runtime field. It is a user-chosen string used by the template to read or write:

```python
cell.dict["state"][state_key]
```

Any stable key name can be used, such as `custom_metric`, `activation_score`, or `response_active`. Once written into `cell.dict["state"]`, the value is included in audit CSV output. It appears in CC3D Player only if a scalar visualization field is created for it.
