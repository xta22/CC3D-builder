# Intracellular Model Integration

RuleParser treats SBML, Antimony, CellML, and MaBoSS models as optional CC3D runtime models. They are not part of the rule parser itself; rules only decide when values are synchronized and when a model advances.

## Project Model Registry

Project-level model definitions are stored in `rules.json` under:

```json
"intracellular_models": []
```

Each entry defines one CC3D model attachment:

```json
{
  "id": "SignalModel",
  "engine": "maboss",
  "model_name": "SignalModel",
  "source": {
    "kind": "file",
    "boolean_network_path": "models/signal_model.bnd",
    "simulation_configuration_path": "models/signal_model.cfg"
  },
  "attach_to": {
    "cell_types": ["CellTypeA", "CellTypeB"]
  },
  "solver": {
    "step_size": 1.0
  },
  "initial_conditions": {
    "response_node": false
  },
  "inputs": [
    {"model_var": "input_signal", "from": "field", "field_name": "SignalField"}
  ],
  "outputs": [
    {"model_var": "response_node", "to": "state", "key": "response_active"}
  ]
}
```

Supported engines:

```text
sbml
antimony
cellml
maboss
```

Supported source modes:

```text
file
inline
```

For SBML, Antimony, and CellML file mode, use `source.path`. For MaBoSS file mode, use `source.boolean_network_path` and `source.simulation_configuration_path`.

## Runtime Rule Behaviour

Use behaviour `intracellular_model` to run a model action from the ordered rule list.

Common actions:

```text
advance       sync inputs, step model, sync outputs
sync_inputs   only write mapped CC3D values into model variables
step          run the CC3D global timestep method for that model family
sync_outputs  only read model variables into RuleParser/CC3D state
reset         reset the RuleParser cache and reapply initial values
set_variable  write one model variable
```

`advance` is the normal per-cell action. `step`, `step_all`, `timestep`, `timestep_all`, and `global_step` are treated as global actions and do not require a target cell.

## Mapping Inputs Into Models

Input mappings write CC3D or RuleParser state into model variables before a model step.

Supported `from` values:

| `from` | Source |
| --- | --- |
| `constant` / `value` | `mapping.value` |
| `time` / `mcs` / `global_time` | Current MCS |
| `cell_attribute` / `cell_attr` | `getattr(cell, mapping.key)` |
| `field` / `field_sample` / `environment` | PDE field sampling through existing condition sampling helpers |
| `contact` / `contact_ratio` | Contact ratio with `target_type` |
| `neighbor_average` / `neighbor_avg` | Average intracellular variable over neighboring cells |
| `cell_dict` | Nested `cell.dict` path such as `state.damage` |
| `state` | Shortcut for `cell.dict["state"][key]` |
| `model_variable` / `intracellular` | Another cached/live model variable |

## Mapping Outputs Back To Cells

Output mappings read model variables after a model step.

Supported `to` values:

| `to` | Target |
| --- | --- |
| `intracellular` / `cache` | `cell.dict["intracellular"][model_name][variable]` |
| `state` | `cell.dict["state"][key]` |
| `cell_dict` | Nested `cell.dict` path |
| `cell_attribute` / `cell_attr` | `setattr(cell, key, value)` |

The live CC3D model remains the primary source when available. The RuleParser cache is the stable bridge for rule conditions, time-series logging, and generated-code customization.

## Naming

Use one stable model name whenever possible:

```text
id == model_name
```

`model_name` is the name used by rules, generated code, and CC3D live model access. `id` exists for registry bookkeeping. The optional `alias` key is only retained for backward compatibility with older JSON blocks and should not be used for new models.

There are two different variable-name layers:

| Name | Meaning | Customizable |
| --- | --- | --- |
| `model_var` | Variable, species, parameter, or node inside the intracellular model | It must match the model, except for external variables intentionally declared for input |
| `state` key | RuleParser cell state stored under `cell.dict["state"][key]` | Yes, choose a stable project-specific name |

For example, `response_node -> state:response_active` reads the model variable `response_node` and writes the result to `cell.dict["state"]["response_active"]`.

## Model-level And Rule-level Mappings

Most projects should define `inputs` and `outputs` on the model registry entry. Then every `advance` rule can simply reference the model and choose whether to sync inputs, step, and sync outputs.

The GUI edits these mappings with tables and dropdowns. The saved project file still stores them as structured JSON so runtime execution and generated CC3D code can use the same schema.

Rule-level `inputs` and `outputs` are optional. They are appended to the model-level mappings and are useful only when one specific rule needs extra synchronization.

## Generated Code

Generated native CC3D code embeds the model registry as:

```python
COMPILED_INTRACELLULAR_MODELS = [...]
```

Model setup happens in `start()` through `_initialize_intracellular_models()`. Rule execution calls `_execute_intracellular_model(cell, payload, mcs)`.

Custom generated-code hooks can read either:

```python
self._intracellular_value(cell, "SignalModel", "response_node")
```

or, when the CC3D live model exists:

```python
cell.maboss.SignalModel["response_node"]
```

Both paths are compatible. The helper prefers the live model value, then falls back to `cell.dict["intracellular"]["SignalModel"]["response_node"]`.

## CSV Import

There are two separate CSV import paths:

```text
Intracellular Models -> Import Registry CSV
Import Rules CSV
```

The model registry CSV defines `intracellular_models`. It is opened from the `Intracellular Models` manager window. The rules CSV defines ordered `intracellular_model` behaviour rules that operate on those registered models.

Example file:

```text
docs/intracellular_model_registry_example.csv
```

Required or common columns:

| column | meaning |
| --- | --- |
| `id` | Registry id for the model |
| `engine` | `maboss`, `sbml`, `antimony`, or `cellml` |
| `model_name` | Runtime model name used by rules and generated code |
| `source_kind` | `file` or `inline` |
| `boolean_network_path`, `simulation_configuration_path` | MaBoSS file-mode paths |
| `source_path` | SBML/Antimony/CellML file-mode path |
| `attach_cell_types` | Comma-separated CC3D cell type names |
| `step_size` | Solver step size |
| `initial_conditions` | JSON object stored in one CSV cell |
| `inputs` | JSON array of input mappings stored in one CSV cell |
| `outputs` | JSON array of output mappings stored in one CSV cell |

For a generic MaBoSS file-based model:

```csv
id,engine,model_name,source_kind,boolean_network_path,simulation_configuration_path,source_path,attach_cell_types,step_size,initial_conditions,inputs,outputs
SignalModel,maboss,SignalModel,file,models/signal_model.bnd,models/signal_model.cfg,,"CellTypeA",1.0,"{""response_node"": false}","[{""model_var"": ""input_signal"", ""from"": ""field"", ""field_name"": ""SignalField"", ""default"": 0.0}]","[{""model_var"": ""response_node"", ""to"": ""state"", ""key"": ""response_active""}]"
```
