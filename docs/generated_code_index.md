# Generated CC3D Code Index

This document indexes the structure of `SimulationStepCode.py`. It is not a replacement for `rules.json`; it is a map for code-level customization after the generated steppable is built.

## Generated File Location

The registry currently writes generated native CC3D code to:

```text
Rules_project/Simulation/SimulationStepCode.py
```

This file is a complete traditional CC3D steppable file. In the current generated-code workflow, the source project `.cc3d` points to `Simulation/gen_code_main.py`, and `gen_code_main.py` registers `SimulationStepCode.SimulationSteppable`.

Manual copying into Twedit is still possible for one-off experiments, but it is not the default project-sync path.

## Runtime Model

The generated code contains one CC3D steppable class. It does not create one steppable per rule.

CC3D calls the generated steppable once per MCS:

```text
step(mcs)
```

The generated steppable then processes `COMPILED_RULES` strictly in list order:

```text
COMPILED_RULES[index 0]
COMPILED_RULES[index 1]
COMPILED_RULES[index 2]
...
```

Each rule may contain multiple cases. Each case evaluates its `when` condition. A matching case creates an event, and that event is executed by a behaviour handler or a user hook.

```text
one steppable
  -> many rules, ordered by rule index
    -> many cases per rule
      -> zero or more events
        -> one behaviour handler or one user hook
```

## Rule Hooks And Behaviour Hooks

Custom code belongs inside the preserved block near the end of the generated file:

```python
    # === USER CUSTOM HOOKS START ===
    # custom methods here
    # === USER CUSTOM HOOKS END ===
```

The generator preserves this block when it rewrites `SimulationStepCode.py`.

### Per-rule Hook

Use a per-rule hook to override one specific rule:

```python
    def rule_4(self, cell, payload, mcs):
        return "default"
```

Naming rule:

```text
rule_<rule_id>
```

Examples:

```text
rule id: 4        -> rule_4
rule id: 1_copy   -> rule_1_copy
rule id: host-A   -> rule_host_A
```

### Per-behaviour Hook

Use a per-behaviour hook to override all rules with the same behaviour:

```python
    def handle_differentiate(self, cell, payload, mcs):
        return "default"
```

Naming rule:

```text
handle_<behaviour>
```

Characters that are not valid in Python identifiers are converted to `_`:

```text
secrete/uptake -> handle_secrete_uptake
fpp_link       -> handle_fpp_link
```

### Hook Priority

For each event, generated code searches hooks in this order:

```text
rule_<rule_id>
handle_<behaviour>
default generated handler
```

If `rule_<rule_id>` exists and returns `"default"` or `NotImplemented`, execution goes directly to the default generated handler. It does not continue to `handle_<behaviour>`.

Hook return values:

```text
True or None      handled successfully
False             not executed or failed
"default"         fall back to the generated default handler
NotImplemented    fall back to the generated default handler
```

### Payload And Default Fallback

`payload` is the runtime action-parameter dictionary for the current matched event. It is not the same object as the GUI/CLI `params` used by `rule_builder.py`, and it is not the temporary builder-side `data` variable.

```text
GUI / CLI / CSV input
  -> params
  -> rule_builder.py
  -> rules.json
  -> matched rule case
  -> payload for the current cell and MCS
```

The `payload` contains the matched case content after dynamic values are resolved. It excludes the `when` condition block because `when` has already been evaluated before the hook is called.

Editing `payload` inside a hook changes only the current event. It does not rewrite `rules.json` or `COMPILED_RULES`.

Example:

```python
    def rule_slow_growth(self, cell, payload, mcs):
        if cell is not None and cell.dict.get("state", {}).get("p21", 0.0) > 1.0:
            payload["rate"] = 0.2

        return "default"
```

Here, `"default"` means execution fallback. It is not a default parameter value. The generated steppable will continue by calling the default behaviour executor, such as `_execute_growth(cell, payload, mcs)`, using the modified `payload`.

If a rule id and behaviour name produce similar method names, they still do not collide because their prefixes are different:

```text
rule id: growth   -> rule_growth
behaviour: growth -> handle_growth
```

The rule hook has priority. If `rule_<rule_id>` exists and returns `"default"` or `NotImplemented`, generated code goes directly to the default generated handler and does not call `handle_<behaviour>`.

## Behaviour Handler Index

These are the generated behaviour execution entry points. Hooks may call them directly, but their names should not be changed.

| behaviour | handler | main mode/action values |
| --- | --- | --- |
| `growth` | `_execute_growth(cell, payload, mcs)` | growth model / physical model |
| `differentiate` | `_execute_differentiate(cell, payload, mcs)` | `type_switch`, `division` |
| `create` | `_execute_create(cell, payload, mcs)` | distribution: `random`, `cluster`, `stripe` |
| `death` | `_execute_death(cell, payload, mcs)` | `apoptosis`, `necrosis` |
| `secrete/uptake` | `_execute_secrete_uptake(cell, payload, mcs)` | CC3D secretor method from `secret_mode` |
| `dormancy` | `_execute_dormancy(cell, payload, mcs)` | `dormant`, `reactivate` |
| `phagocytosis` | `_execute_phagocytosis(cell, payload, mcs)` | `engulfment`, `absorption`, `frustrated` |
| `chemotaxis` | `_execute_chemotaxis(cell, payload, mcs)` | target strategy: `break`, `id`, `coord` |
| `force` | `_execute_force(cell, payload, mcs)` | `vector`, `stored_vector`, `toward_position`, `away_from_position`, `toward_cell_id`, `toward_nearest_type`, `away_from_nearest_type`, `toward_field_gradient`, `clear` |
| `fpp_link` | `_execute_fpp_link(cell, payload, mcs)` | `nearest_type`, `cell_id`, `within_distance`, `clear` |
| `compartmentalize` | `_execute_compartmentalize(cell, payload, mcs)` | `initialize`, `extend_chain`, `branch_chain` |
| `intracellular_model` | `_execute_intracellular_model(cell, payload, mcs)` | `advance`, `sync_inputs`, `step`, `sync_outputs`, `reset`, `set_variable` |
| `subcellular` | `_execute_subcellular(cell, payload, mcs)` | `initialize`, `set_stage`, `advance_stage`, `set_component`, `increase_component`, `consume_component`, `set_localization`, `translocate`, `set_value`, `assemble` |
| `custom_script` | `_execute_custom_script(rule)` | external Python script |

## Execution Pipeline Helpers

These functions control event scheduling and dispatch. They are usually not called directly from hooks.

| function | role |
| --- | --- |
| `start()` | Initializes the DeathStatus field, celltype constraints, `cell.dict` fields, and subcellular scalar fields |
| `step(mcs)` | Main entry point for every MCS |
| `finish()` / `on_stop()` | Exports audited cell-state CSV files when the simulation completes or stops |
| `_step_snapshot(mcs)` | Collects all events first, then executes them in rule-index order |
| `_step_asynchronous(mcs)` | Evaluates and executes each rule immediately |
| `_ordered_rules()` | Returns `enumerate(self.rules)`, preserving list index order |
| `_events_for_rule(rule, original_index, mcs, seq_start)` | Converts matching cases for one rule into events |
| `_execute_event(event, mcs)` | Shared hook and behaviour-handler dispatch point |
| `_run_continuous_processes(mcs)` | Advances death progression, persistent force, and dormancy tracking |
| `_audit_all_cells(mcs)` | Captures flattened `cell.dict` values and core cell metrics for CSV output |

## Generated Data Recording

The generated steppable records simulation data into `simulation_time_series/` under the CC3D project that is currently running.

For example, if CompuCell Player opens:

```text
/Users/xiaoyue/Desktop/ProjectA/Rules_project.cc3d
```

the output directory is:

```text
/Users/xiaoyue/Desktop/ProjectA/simulation_time_series/
```

Main output files:

```text
global_simulation_history.csv
cell_id_<id>_sequence.csv
```

Key functions:

| function | role |
| --- | --- |
| `_configure_audit_output_dir()` | Resolves and creates the `simulation_time_series` output directory |
| `_audit_interval_matches(mcs)` | Checks `settings["audit_interval"]` |
| `_audit_cell_sequence_limit()` | Reads `settings["audit_cell_sequence_limit"]` |
| `_flatten_cell_dict(mapping)` | Converts nested `cell.dict` values into flat CSV columns |
| `_audit_value(value)` | Converts non-scalar values into CSV-safe values |
| `_audit_all_cells(mcs)` | Captures one row per cell for the current MCS |
| `_export_audit_data()` | Writes global and selected per-cell CSV files |
| `_write_audit_csv(path, rows, fieldnames)` | Writes CSV using `csv.DictWriter` |

Minimal code slice:

```python
def _audit_all_cells(self, mcs):
    for cell in self.cell_list:
        snapshot = {
            "MCS": mcs,
            "Cell_ID": cell.id,
            "Cell_Type": cell.type,
            "Volume": cell.volume,
            "TargetVolume": cell.targetVolume,
            "X_COM": cell.xCOM,
            "Y_COM": cell.yCOM,
            "Z_COM": cell.zCOM,
        }
        if cell.dict:
            snapshot.update(self._flatten_cell_dict(cell.dict))
        self._audit_buffer.append(snapshot)
```

Because `cell.dict` is flattened, user-defined state keys, intracellular caches, subcellular state, behavior statistics, and hook-written values are all captured if they exist at the audited MCS.

`audit_cell_sequence_limit` controls per-cell sequence export:

```text
3       export first 3 observed cell IDs
0       do not export per-cell sequence files
"all"   export every observed cell ID
```

`"all"` means all cell IDs that appeared in the audit buffer. If a cell is deleted during the simulation, its sequence contains the rows recorded while it existed.

## Condition Helpers

These functions evaluate conditions and are useful from custom hooks.

| function | role |
| --- | --- |
| `_evaluate_condition(block, cell)` | Recursively evaluates `Logic_AND`, `Logic_OR`, `Logic_NOT`, and normal conditions |
| `_evaluate_single_condition(cond, cell)` | Evaluates one condition block |
| `_environment_value(params, cell)` | Reads PDE field values using COM, boundary, radius, or contact-boundary sampling |
| `_contact_ratio(cell, target_type_name)` | Computes contact ratio with a target cell type |
| `_morphology_value(cell, indicator)` | Reads morphology or mechanics values such as volume, surface, COM, and lambda values |
| `_frequency_state_value(cell, state_key)` | Reads numeric state from cell attributes or `cell.dict` |
| `_intracellular_value(cell, model_name, variable, default=0.0)` | Reads a live `cell.sbml`/`cell.maboss` value first, then the RuleParser cache |
| `_subcellular_value(cell, system, variable="stage", default=0.0)` | Reads `cell.dict["subcellular"][system]` values for `SubcellularState` conditions |
| `_compare(value, operator, threshold)` | Applies `>`, `>=`, `<`, `<=`, `==`, or `!=` |

## Cell, Field, And Geometry Helpers

These functions are useful from custom hooks.

| function | role |
| --- | --- |
| `_ensure_cell_dict(cell)` | Ensures `state`, `_internal`, `behaviour_stats`, and related dictionaries exist |
| `_cell_type_id(type_name)` | Converts a cell type name to a CC3D type id |
| `_target_cells(target)` | Returns cells matching a target name |
| `_apply_celltype_constraints(cell, type_name)` | Applies `targetVolume` and `lambdaVolume` |
| `_field_value(field_name, cell)` | Reads a field value at the cell COM |
| `_sample_field_at(field, x, y, z)` | Reads a field value at a lattice coordinate |
| `_cell_pixels(cell)` | Returns lattice pixels belonging to a cell |
| `_neighbor_sites(x, y, z)` | Returns neighboring lattice coordinates |
| `_nearest_cell_by_type(cell, type_name)` | Finds the nearest cell of one type |
| `_nearest_cell_by_types(cell, type_names)` | Finds the nearest cell across several candidate types |
| `_normalize(vector)` | Normalizes a vector |
| `_to_float(value, default)` | Safely converts a value to float |
| `_as_bool(value)` | Safely converts a value to bool |

## Intracellular Model Helpers

These functions attach CC3D intracellular models, synchronize values, and expose the values to rule conditions and hooks.

| function | role |
| --- | --- |
| `_initialize_intracellular_models()` | Attaches configured models to the configured cell types during `start()` |
| `_ensure_intracellular_model_for_cell(cell, spec)` | Lazily attaches a model to a cell when a rule first needs it |
| `_sync_intracellular_inputs(cell, spec, payload, mcs)` | Writes mapped CC3D values into solver variables before stepping |
| `_step_intracellular_cell_or_global(cell, spec, payload, mcs)` | Advances the live per-cell model when available, otherwise falls back to CC3D global timestep APIs |
| `_sync_intracellular_outputs(cell, spec, payload, mcs)` | Reads solver variables into `cell.dict["intracellular"]`, `cell.dict["state"]`, cell attributes, or nested `cell.dict` paths |
| `_write_live_intracellular_value(cell, model_name, variable, value)` | Writes directly into `cell.sbml.<model>` or `cell.maboss.<model>` when CC3D exposes the model |
| `_write_intracellular_cache(cell, model_name, variable, value)` | Writes the RuleParser cache copy under `cell.dict["intracellular"][model_name][variable]` |

## Subcellular System Helpers

These functions implement coarse-grained internal cell state. They do not create CC3D cell types and do not use CC3D compartment clusters.

| function | role |
| --- | --- |
| `_initialize_subcellular_systems(mcs=0)` | Applies `COMPILED_SUBCELLULAR_SYSTEMS` defaults to attached cell types |
| `_ensure_subcellular_system(cell, spec_or_name, mcs=None)` | Creates `cell.dict["subcellular"][system]` and applies defaults |
| `_subcellular_value(cell, system, variable="stage", default=0.0)` | Reads `stage`, `components.<name>`, `localization.<name>`, or a nested path |
| `_set_subcellular_value(cell, system, variable, value, mcs=None)` | Writes a nested subsystem value |
| `_create_subcellular_visualization_fields()` | Creates CC3D Player scalar fields for stage, activity, component counts, and localizations |
| `_update_subcellular_visualization_fields(mcs)` | Mirrors `cell.dict["subcellular"]` values into those scalar fields every step |
| `_advance_subcellular_stage(cell, system, payload, mcs)` | Moves between registered stages, with optional `from_stage` and `probability` |
| `_assemble_subcellular_component(cell, system, payload, mcs)` | Consumes required components and creates a product component |

## Tracking Helpers

These functions write execution state into `cell.dict["behaviour_stats"]`.

| function | role |
| --- | --- |
| `_record_event(cell, behaviour, mcs, amount=None)` | Records a discrete event |
| `_record_active_step(cell, behaviour, mcs, delta=None)` | Records a continuously active state |
| `_record_activation(cell, behaviour, mcs)` | Records activation time |
| `_record_deactivation(cell, behaviour, mcs)` | Records deactivation time |
| `_record_field_delta(cell, behaviour, field_name, mcs, delta)` | Records secretion or uptake deltas for a field |
| `_set_metric(cell, behaviour, key, value)` | Writes a custom metric |

## Code-level Override Example

This example overrides rule id `4`. It changes the rule's code-level condition and execution logic rather than only changing JSON parameters.

```python
    # === USER CUSTOM HOOKS START ===

    def rule_4(self, cell, payload, mcs):
        if cell is None:
            return False

        self._ensure_cell_dict(cell)

        last = cell.dict["_internal"].get("last_rule_4_mcs", -10**9)
        if mcs - last < 200:
            return False

        signal = self._environment_value(
            {"field_name": "SignalField", "sampling_mode": "boundary_max"},
            cell,
        )
        neighbor_contact = (
            self._contact_ratio(cell, "NeighborTypeA")
            + self._contact_ratio(cell, "NeighborTypeB")
        )

        if signal < 0.12 and neighbor_contact <= 0:
            return False

        payload["new_type"] = "ActivatedCellType"
        ok = self._execute_differentiate(cell, payload, mcs)

        if ok:
            cell.dict["_internal"]["last_rule_4_mcs"] = mcs

        return ok

    # === USER CUSTOM HOOKS END ===
```

## Practical Rule

Prefer `rule_<rule_id>` for local edits. Use `handle_<behaviour>` only when the same custom logic should apply to every rule with that behaviour.
