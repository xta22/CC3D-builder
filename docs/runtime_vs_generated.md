# Runtime Engine vs Generated Code

RuleParser has two execution paths.

## Runtime Engine Path

This path uses RuleParser at simulation time:

```text
rules.json
  -> wrapper_main.py
  -> RuleEngineSteppable
  -> behaviour plugins
  -> behaviour steppable executors
  -> CC3D simulation
```

This mode is useful during framework development because behaviour logic stays split across plugins and steppables.

## Generated Code Path

This path compiles the current project state into normal CC3D Python code:

```text
rules.json / registry
  -> code_generator.py
  -> SimulationStepCode.py
  -> gen_code_main.py
  -> CC3D simulation
```

The generated file embeds project state as Python constants:

```python
COMPILED_RULES
COMPILED_SETTINGS
COMPILED_CELLTYPE_PARAMS
COMPILED_FIELD_PARAMS
COMPILED_INTRACELLULAR_MODELS
COMPILED_SUBCELLULAR_SYSTEMS
```

When the source project `.cc3d` points to:

```xml
<PythonScript Type="PythonScript">Simulation/gen_code_main.py</PythonScript>
```

CompuCell Player runs the generated-code path by default.

## Important Difference

Generated code does not read `rules.json` at every MCS. It runs the rules compiled into `SimulationStepCode.py`.

Therefore:

```text
changing rules.json alone does not change generated simulation behaviour
```

To make a JSON change affect generated-code execution, regenerate `SimulationStepCode.py` and sync it to the source project.

## Rule Order

Generated code executes rules by their list position in `COMPILED_RULES`.

```text
COMPILED_RULES[0]
COMPILED_RULES[1]
COMPILED_RULES[2]
...
```

The `order` field may still appear in rule data for compatibility, but generated code uses the actual list order.

## Snapshot And Asynchronous Modes

`snapshot` first collects all matching events for the current MCS, then executes them in rule-list order.

`asynchronous` evaluates and executes each rule before moving to the next rule. Earlier rules can affect later rule conditions in the same MCS.

## Global Rules

Most behaviours are cell-level:

```text
target cells -> condition per cell -> event per matching cell
```

Some behaviours are global-looking:

```text
one rule-level event -> executor or script decides what cells are affected
```

Examples include:

```text
create
custom_script
intracellular_model global step actions
```

Global rules still have a position in the rule list. They are not unordered. The difference is that they do not start with one current target cell.

## Continuous State

Some effects continue after the original rule trigger. Generated code advances these after rule execution in each MCS.

Examples include:

```text
active force
death progression
dormancy active tracking
```

These are not new rule triggers. They are persistent state updates.
