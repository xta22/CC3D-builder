# Subcellular System Integration

Subcellular systems are coarse-grained internal states stored inside each CC3D cell. They are intended for internal stages, component pools, localization pools, or other bookkeeping that should not become CC3D cell types.

This system does not use CC3D compartment clusters and does not create additional CC3D cell types. It writes to:

```python
cell.dict["subcellular"][system_id]
```

## Registry Block

`rules.json` stores subsystem definitions at the top level:

```json
{
  "subcellular_systems": [
    {
      "id": "internal_process",
      "scope": "cell",
      "stages": [
        "inactive",
        "primed",
        "active",
        "complete"
      ],
      "default_stage": "inactive",
      "attach_to": {
        "cell_types": ["CellTypeA"]
      },
      "default_counts": {
        "component_a": 0,
        "component_b": 0,
        "product": 0
      },
      "default_localization": {
        "source_pool": 1.0,
        "target_pool": 0.0
      }
    }
  ]
}
```

`attach_to.cell_types` must name real CC3D cell types already registered in XML. The subcellular system is initialized inside those cells.

## Behaviour Rule

Use behaviour `subcellular` to update a subsystem from the ordered rule list.

```json
{
  "id": "4",
  "target": "CellTypeA",
  "behaviour": "subcellular",
  "cases": [
    {
      "when": {
        "condition_type": "SubcellularState",
        "params": {
          "system": "internal_process",
          "variable": "stage",
          "operator": "==",
          "threshold": "primed"
        }
      },
      "system": "internal_process",
      "action": "assemble",
      "requires": {
        "component_a": 2,
        "component_b": 1
      },
      "product": "product",
      "amount": 1,
      "to_stage": "complete"
    }
  ],
  "frequency": 10,
  "once": false,
  "debug": false
}
```

## Supported Actions

| action | purpose | main fields |
| --- | --- | --- |
| `initialize` | Ensure the subsystem state exists | `system` |
| `set_stage` | Set the current assembly/state label | `stage` |
| `advance_stage` | Move to `to_stage` or the next registered stage | `from_stage`, `to_stage`, `probability` |
| `set_component` | Set one component count | `component`, `count` or `value` |
| `increase_component` | Add to one component count | `component`, `amount` |
| `consume_component` | Subtract from one component count | `component`, `amount`, `floor_zero` |
| `set_localization` | Set a localization value/fraction | `location`, `value` |
| `translocate` | Move amount between localization pools | `from_location`, `to_location`, `amount` |
| `set_value` | Write an arbitrary nested subsystem value | `variable`, `value` |
| `assemble` | Consume required components and create a product | `requires`, `product`, `amount`, `to_stage` |

## Conditions

Use `SubcellularState` conditions to test subsystem values.

Stage:

```json
{
  "condition_type": "SubcellularState",
  "params": {
    "system": "internal_process",
    "variable": "stage",
    "operator": "==",
    "threshold": "complete"
  }
}
```

Component count:

```json
{
  "condition_type": "SubcellularState",
  "params": {
    "system": "internal_process",
    "component": "product",
    "operator": ">=",
    "threshold": 1
  }
}
```

Localization:

```json
{
  "condition_type": "SubcellularState",
  "params": {
    "system": "internal_process",
    "location": "target_pool",
    "operator": ">=",
    "threshold": 0.5
  }
}
```

## CSV Import

Subsystem registry CSV files are imported from the Subcellular Systems dialog.

```text
docs/subcellular_system_registry_example.csv
```

Ordered rule CSV files use the normal Import Rules CSV button. Use behaviour `subcellular`.

```text
docs/subcellular_rules_example.csv
```

## Generated Code

Generated native CC3D code embeds the registry as:

```python
COMPILED_SUBCELLULAR_SYSTEMS = [...]
```

The generated steppable initializes systems through `_initialize_subcellular_systems()` and executes rules through `_execute_subcellular(cell, payload, mcs)`.

For custom generated-code edits, override a specific rule:

```python
def rule_4(self, cell, payload, mcs):
    if self._subcellular_value(cell, "internal_process", "components.product", 0) >= 2:
        payload["to_stage"] = "complete"
    return self._execute_subcellular(cell, payload, mcs)
```

## Observing Metrics

Subcellular values live in `cell.dict`, so CC3D Player cannot display them unless they are mirrored into scalar fields. The runtime steppable and generated code create these cell-level scalar fields automatically for each registered system:

| field pattern | meaning |
| --- | --- |
| `SubcellularStage_<system>` | Numeric stage index from the registered `stages` list |
| `SubcellularActive_<system>` | `1` when the system was updated on the current MCS, otherwise `0` |
| `SubcellularCount_<system>_<component>` | Component count from `components[component]` |
| `SubcellularLoc_<system>_<location>` | Localization value from `localization[location]` |

For a system id `internal_process`, example Player fields would be `SubcellularStage_internal_process`, `SubcellularActive_internal_process`, `SubcellularCount_internal_process_component_a`, `SubcellularCount_internal_process_product`, and `SubcellularLoc_internal_process_target_pool`.

The runtime rule engine and generated native code also write time-series snapshots to `simulation_time_series/global_simulation_history.csv` when the simulation finishes. The audit interval can be changed with `settings.audit_interval` in `rules.json`.
