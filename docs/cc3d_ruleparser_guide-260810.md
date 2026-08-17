# CC3D RuleParser Guide

## A JSON-Based Modeling Layer for CompuCell3D

Status: living project guide, updated for the current RuleParser/CC3D Builder codebase.

This guide is written as a brochure-style overview, offering a practical developer/user manual.

## 1. Executive Summary

 CC3D RuleParser is a project layer built around CompuCell3D. Its goal is to let modelers
  build, manage, and maintain complex code-based simulation platforms through a biologically
  meaningful semantic rule management system.

  The framework is not intended to replace CC3D. It sits above a structurally valid CC3D
  project and provides mechanisms to store rule definitions, synchronize the necessary XML/
  Python dependencies, and generate executable code for two separate workflows:

  - RuleParser-driven simulation, where the runtime rule engine evaluates ordered biological
  rules and dispatches actions inside CC3D.
  - Standalone CC3D simulation, where RuleParser exports native Python steppable code that can
  run on the CC3D platform without the RuleParser runtime engine.

  The framework provides:

- A JSON rule schema for behaviors, conditions, cell types, fields, intracellular models, and subcellular state systems.
- A GUI and CLI for constructing and editing rules.
- A runtime rule engine that evaluates conditions and dispatches actions through behavior plugins and steppables.
- Automatic synchronization of cell types, fields, contact energies, FPP dependencies, and generated Python code.
- A native CC3D code generator that exports a self-contained `SimulationStepCode.py` and `gen_code_main.py` for running a source project without the runtime rule engine.
- Time-series audit output for cell states, behavior metrics, intracellular variables, and subcellular states.
- Bulk import rules from CSV files. You're free to manage the rules using any table management tool you like, apart from RuleParser.
The core idea is simple:

```text
JSON describes what should happen.
The engine decides when it happens.
Steppables perform the actual CC3D operations.
Generated code can export the current design into a traditional CC3D steppable file.
```

## 2. What Problem This Solves

Traditional CC3D modeling usually requires editing XML and Python steppables directly. That is powerful, but complex simulations quickly become difficult to inspect, reorder, and reuse.

RuleParser adds a structured middle layer:

- Rules are visible as rows and blocks.
- Conditions and actions are explicit.
- Rule order is controlled by the order of the JSON list and GUI table.
- Reusable behaviors are implemented once and configured many times.
- Generated code provides a hand-editable CC3D-compatible export when users want to leave the RuleParser runtime.

This is most useful when a project contains many conditional behaviors.

## 3. Core Concepts

### CC3D Project

A normal CompuCell3D project with a `.cc3d` file, XML file, and Python steppable file. RuleParser expects the project to be structurally valid before import.

### Sandbox Project

The shared workspace project:

```text
Rules_project/
```

When a source CC3D project is loaded, its XML and steppable file are copied into this sandbox. Runtime editing and code generation happen here.

### Project Profile

Each source project can store its own most recent RuleParser state in:

```text
<SourceProject>/.ruleparser/rules.json
<SourceProject>/.ruleparser/metadata.json
```

This prevents one source project from accidentally inheriting rules from another source project. When the GUI or registry saves, sandbox rules are synchronized back to the active project profile.

### Registry

The registry stores project-level modeling data:

- `rules`
- `celltype_params`
- `field_params`
- `intracellular_models`
- `subcellular_systems`
- `settings`

The registry writes `rules.json`, synchronizes XML, and triggers generated code compilation.

### Rule

A rule is an ordered unit of behavior. It has:

- `id`
- `target`
- `behaviour`
- `cases`
- `frequency`
- `once`
- `debug`

### Case

A case is one condition-action block inside a rule. Cases use a strict flat schema:

```json
{
  "when": {"condition_type": "TRUE"},
  "model": "linear",
  "alpha": 0.5
}
```

Deprecated wrappers such as nested `apply` or `parameters` at the case level are rejected.

### Condition

A condition decides whether a case is active at the current MCS for a given cell.

### Behaviour

A behavior names the biological or physical action to perform, such as `growth`, `death`, `force`, or `intracellular_model`.

### Plugin

A behavior plugin converts a matched case into an execution request returned directly to the rule engine.

### Steppable Executor

A steppable executor performs the concrete CC3D operation, such as changing target volume, secreting a field, applying force, creating FPP links, or stepping an Antimony model.

## 4. High-Level Architecture

```text
User / GUI / CSV / CLI
        |
        v
Rule Builder and Registry
        |
        v
rules.json
        |
        +----------------------+
        |                      |
        v                      v
Runtime Rule Engine        Code Generator
        |                      |
        v                      v
Behavior Plugins          SimulationStepCode.py
        |
        v
Steppable Executors
        |
        v
CompuCell3D Simulation
        |
        v
Scalar fields and time-series CSV
```

A quick reminder - The runtime path and generated-code path are separate:

- Runtime mode uses `RuleEngineSteppable` plus behavior-specific steppables.
- Generated-code mode embeds the compiled rules into one standalone steppable class.

## 5. Main File Layout

```text
cc3d_builder/
  cli/
    main.py                       CLI entry point
  core/
    project_manager.py            Source project import/resume and wrapper generation
    project_profile.py            .ruleparser project profile persistence
    rule_builder.py               Converts CLI/CSV/GUI params into flat rules
    rule_schema.py                Strict rule/case schema checks
    structure_manager.py          XML cell, field, plugin, and initializer sync
    csv_importer.py               Batch import helpers
    state_key_catalog.py          Dynamic state-key reference
  engine/
    core/
      rule_engine.py              Runtime ordered rule engine
      condition_evaluator.py      Condition evaluation and field sampling
      behaviour_stats.py          Runtime behavior metrics
      intracellular_state.py      Live model/cache access
      subcellular_state.py        Coarse-grained subsystem state access
    behaviour_plugins/            Request builders for each behavior
    steppables/                   CC3D executors for each behavior
    registry/
      simulation_registry.py      Save/sync/generate pipeline
    code_generator.py             Native CC3D steppable generator
  gui/
    project_loader.py             GUI project loader
    main_editor.py                Rule wizard and main editor
    ManageRuleWindow.py           Rule table and management UI
    xml_config_editor.py          XML cell/field/initializer editor
    intracellular_model_dialog.py Intracellular model registry editor
    subcellular_system_dialog.py  Subcellular system registry editor
docs/
  generated_code_index.md
  intracellular_models.md
  subcellular_systems.md
```

## 6. User Workflow

### 6.1 Prepare A Base CC3D Project

Before using RuleParser, prepare a normal CC3D project containing:

- one `.cc3d` file
- one XML file under `Simulation/`
- one Python steppable file under `Simulation/`

The project does not need all rules implemented manually, but it should be runnable or at least structurally complete. 
Our tests confirm that you can use a minimal "empty-shell" project with no cell objects, plugins, or steppables added.

### 6.2 Load The Project

GUI entry point:

```bash
python3 -m cc3d_builder.gui.project_loader
```

CLI entry point:

```bash
python3 -m cc3d_builder.cli.main
```

The loader asks whether to:

- import new and clear RuleParser rules
- resume project rules from `.ruleparser/rules.json`

The GUI remains the richer editing surface for table editing, XML views, and visual project management. The CLI supports the main project load/save, rule import, intracellular model registry, subcellular system registry, and rule construction workflows.

### 6.3 Configure XML

Use the XML Config Editor to manage:

- cell types
- volume parameters
- PDE fields
- field diffusion/decay
- chemotaxis placeholders
- initializer regions

The XML editor writes back to the sandbox XML. Registry save then keeps rule JSON and XML dependencies aligned.

### 6.4 Register Project-Level Models

Optional registries:

- Intracellular Models: SBML, Antimony, CellML, MaBoSS.
- Subcellular Systems: coarse-grained internal state systems stored in `cell.dict`.

These are not rules by themselves. Rules reference them later.

### 6.5 Add And Order Rules

Rules can be added through:

- GUI wizard
- Manage Rules table
- CSV import (CLI interface and GUI interface with fixed templates to different behaviours)
- CLI prompt
- direct JSON editing, if the schema is followed (Not recommended)

The Manage Rules table order is the execution order.

### 6.6 Save

Saving through the registry performs several operations:

1. Writes `Rules_project/Simulation/rules.json`.
2. Synchronizes the active project profile `.ruleparser/rules.json`.
3. Ensures XML cell types from `celltype_params`.
4. Ensures XML field definitions from `field_params`.
5. Ensures required XML plugins and steppables for rule dependencies.
6. Recompiles `Rules_project/Simulation/SimulationStepCode.py`.
7. Syncs generated artifacts back to the active source project when a synced project profile is active.

### 6.7 Run In CC3D

Run the active source project or the sandbox project.

```text
/path/to/CompuCell3D/compucell3d.command -i /path/to/RuleParser/Rules_project/Rules_project.cc3d
```

For a source project synchronized to generated-code mode, the `.cc3d` file uses:

```text
Simulation/gen_code_main.py
```

`gen_code_main.py` registers `SimulationStepCode.SimulationSteppable`, so CompuCell Player runs the generated-code path directly.

The older runtime-engine path uses `Simulation/wrapper_main.py`. That wrapper registers the original project steppable, the rule engine, behavior steppables, and optional intracellular/subcellular steppables.

## 7. rules.json Anatomy

A project `rules.json` has this top-level shape:

```json
{
  "rules": [],
  "celltype_params": {},
  "field_params": {},
  "intracellular_models": [],
  "subcellular_systems": [],
  "settings": {
    "execution_semantics": "snapshot",
    "audit_interval": 50
  }
}
```

### 7.1 Rule Shape

```json
{
  "id": "1_growth_low_signal",
  "target": "CellTypeA",
  "behaviour": "growth",
  "cases": [
    {
      "when": {
        "condition_type": "Environment",
        "params": {
          "field_name": "SignalField",
          "operator": "<",
          "threshold": 0.2,
          "sampling_mode": "cell_average"
        }
      },
      "model": "linear",
      "alpha": 0.2
    }
  ],
  "frequency": 1,
  "once": false,
  "debug": false
}
```

### 7.2 Case Matching

For each rule and target cell:

1. Cases are evaluated in their listed order.
2. The first matching case is used.
3. Later cases in the same rule are skipped for that cell at that MCS.

### 7.3 Rule Order

Rule execution order is determined by the rule list index, not by the rule `id`.

  These are different concepts:

  - `id` is the rule's stable identifier. It is used to name, find, edit, or reference a rule.
  - list index is the runtime execution position. It is assigned by the current top-to-bottom
  order of the rules table.

  In the GUI, the execution index is effectively the row order in the rule table. Moving a
  rule up or down changes its list index and therefore changes when it runs. The system
  dispatches rules from top to bottom.

### 7.4 Frequency

`frequency` can be:

- an integer or float coercible to an integer MCS interval
- a dynamic dictionary, such as `state_feedback_frequency`

Static example:

```json
"frequency": 10
```

Dynamic example:

```json
{
  "type": "state_feedback_frequency",
  "state_key": "targetVolume",
  "mode": "linear",
  "base_frequency": 1,
  "slope": 0.01,
  "min_frequency": 1,
  "max_frequency": 100
}
```

### 7.5 Once

  For normal cell-targeted rules, `once: true` is tracked per individual cell, not per cell
  type.

  This means that if a rule targets one cell type, every cell of that type may still execute
  the rule once. When the first matching cell triggers the rule, only that cell is marked as
  having executed it. Other cells of the same type can still trigger the same rule later if
  their own conditions become true.

  Internally, per-cell once status is stored in each cell's `cell.dict["_internal"]
  ["once_rules"]`, keyed by rule id.

  For global rules, such as `create`, `custom_script`, and global intracellular model steps,
  `once: true` is tracked globally on the rule. After the rule triggers once, it will not
  trigger again for the whole simulation.

  In practical terms:

  ```text
  cell-targeted rule + once: true
    Cell 1 triggers rule_3 -> Cell 1 will not trigger rule_3 again
    Cell 2 can still trigger rule_3 once
    Cell 3 can still trigger rule_3 once

  global rule + once: true
    rule_3 triggers once -> rule_3 is disabled globally
  ```

## 8. Execution Semantics

RuleParser supports two execution modes:

| mode | meaning |
| --- | --- |
| `snapshot` | Collect all matching events for the current MCS first, then execute in strict rule-index order. |
| `asynchronous` | Evaluate and execute each rule immediately before moving to the next rule. |

Default:

```json
"execution_semantics": "snapshot"
```

Snapshot mode is preferred when rule order must be reproducible and independent of intermediate changes made earlier in the same MCS.

Asynchronous mode is useful when one rule is intentionally meant to affect later rule conditions during the same MCS.

## 9. Conditions

Supported condition families include:

| condition | purpose |
| --- | --- |
| `TRUE` | Always true. |
| `Environment` | Compare sampled PDE field values. |
| `TimeWindow` / `time_window` | Active between start and end MCS. |
| `Probability` / `probability` | Random trigger with probability `p`. |
| `Contact` / `contact` | Compare contact ratio with a target cell type. |
| `Duration` / `duration` | Require a nested condition to remain true for a number of MCS. |
| `Morphology_*` | Compare native cell morphology values. |
| `State` / `state` | Compare CC3D attributes or `cell.dict` state values. |
| `IntracellularState` | Compare a live or cached intracellular model variable. |
| `SubcellularState` | Compare a subsystem stage, component count, localization, or nested value. |
| `Custom` | Call an external Python condition script. |

### 9.1 Logic Conditions

Nested logic blocks are supported by `evaluate_condition`:

- `Logic_AND`
- `Logic_OR`
- `Logic_NOT`

Example:

```json
{
  "condition_type": "Logic_AND",
  "params": {
    "conditions": [
      {"condition_type": "TimeWindow", "params": {"start": 100, "end": 500}},
      {"condition_type": "Probability", "params": {"p": 0.2}}
    ]
  }
}
```

### 9.2 Environment Sampling

Environment field conditions can sample:

- cell center of mass: `com`
- cell average: `cell_average`
- cell maximum or minimum: `cell_max`, `cell_min`
- boundary average: `boundary_average`
- boundary maximum or minimum
- contact boundary average
- radius average, maximum, or minimum

This allows field conditions to represent local exposure, whole-cell exposure, or contact-localized exposure.

### 9.3 Dynamic Numeric Expressions

Some numeric fields can be strings containing state placeholders:

```text
0.02 * {volume} + 0.1
```

The engine resolves supported state keys from native cell attributes, `cell.dict`, behavior stats, field samples, intracellular caches, and subcellular state.

The state key catalog can be printed from CLI:

```bash
python3 -m cc3d_builder.cli.main --state-keys
```

In an interactive terminal, this opens a paginated reference. To print the full catalog at once, run:

```bash
python3 -m cc3d_builder.cli.main --state-keys --all
```

## 10. Behavior Coverage

| behaviour | executor | main capability |
| --- | --- | --- |
| `growth` | `GrowthSteppable` | Modify target volume using linear, Hill, or expression models. |
| `differentiate` | `DifferentiateSteppable` | Type switch or mitotic division. |
| `create` | `CreateSteppable` | Create cells using random, cluster, or stripe distributions. |
| `death` | `DeathSteppable` | Apoptosis-like shrink or necrosis-like swelling/burst/release. |
| `secrete/uptake` | `SecretionSteppable` | Call CC3D Secretor secretion and uptake modes. |
| `dormancy` | `DormancySteppable` | Mark cells dormant or reactivate them. |
| `phagocytosis` | `PhagocytosisSteppable` | Absorption, engulfment, or frustrated phagocytosis. |
| `chemotaxis` | `ChemotaxisSteppable` | Configure chemotaxis plugin data. |
| `force` | `ForceSteppable` | Apply ExternalPotential vectors and target-directed forces. |
| `fpp_link` | `FPPLinkSteppable` | Create or clear FocalPointPlasticity links. |
| `compartmentalize` | `CompartmentalizeSteppable` | Build chain or branch structures from cell segments and tips. |
| `intracellular_model` | `IntracellularModelSteppable` | Attach, step, sync, and visualize SBML/Antimony/CellML/MaBoSS models. |
| `subcellular` | `SubcellularSteppable` | Update coarse-grained internal component/stage/localization state. |
| `custom_script` | rule engine | Execute user Python logic. |

### 10.1 Growth

Models:

- `linear`
- `hill`
- `expression`

Growth changes `cell.targetVolume` and records behavior stats.

### 10.2 Differentiation

Modes:

- `type_switch`
- `division`

Division supports parent/child type configuration, volume ratio, inheritance strategy, and placement.

### 10.3 Create

Distribution examples:

- `random`
- `cluster`
- `stripe`

Create rules are global rules. They do not require a target cell.

### 10.4 Death

Modes:

- `apoptosis`
- `necrosis`

Death creates and updates a `DeathStatus` scalar field for Player visualization.

### 10.5 Secretion And Uptake

The behavior wraps CC3D Secretor methods such as:

- `secreteInsideCell`
- `secreteInsideCellAtBoundary`
- `secreteOutsideCellAtBoundary`
- `secreteInsideCellAtCOM`
- `uptakeInsideCell`
- `uptakeInsideCellAtBoundary`
- contact-specific boundary modes

`total_count` mode records CC3D returned amounts into persistent tracking and behavior stats.

### 10.6 Force

Modes include:

- `vector`
- `stored_vector`
- `toward_position`
- `away_from_position`
- `toward_cell_id`
- `toward_nearest_type`
- `away_from_nearest_type`
- `toward_field_gradient`
- `clear`

Forces can persist and decay across steps.

### 10.7 FPP Link

Modes include:

- `nearest_type`
- `cell_id`
- `within_distance`
- `all_within_distance`
- `clear`

The StructureManager can ensure FocalPointPlasticity XML dependencies from rules.

### 10.8 Compartmentalize

Actions:

- `initialize_cluster`
- `extend_chain`
- `branch_chain`

This behavior is useful for chain, branch, tip, or segment structures. It uses real CC3D cell types and may optionally create FPP links.

### 10.9 Intracellular Model

Actions:
  - `advance`: Normal full cycle. Sync inputs into the model, step the model, then sync
  outputs back to cell state.

  - `sync_inputs`: Copy CC3D/cell-state values into the intracellular model without stepping
  it.

  - `sync_outputs`: Copy model variables back to `cell.dict["state"]` or the intracellular
  cache without stepping the model.

  - `step`: Step the model once as a global CC3D-managed model action.

  - `step_all`: Global stepping alias. Runtime treats it like `step`.

  - `reset`: Clear the cell's cached model state and reapply initial conditions.

  - `set_variable`: Set one model variable directly and mirror it into the intracellular
  cache.

Supported engines:

- `sbml`
- `antimony`
- `cellml`
- `maboss`

Intracellular values are written to:

```python
cell.dict["intracellular"][model_name][variable]
```

Output mappings can also mirror them into:

```python
cell.dict["state"][key]
```

The runtime can create Player scalar fields for configured intracellular variables, such as selected ODE state variables or network nodes.

### 10.10 Subcellular System

Subcellular systems are internal state dictionaries stored per cell:

```python
cell.dict["subcellular"][system_id]
```

They do not create CC3D cell types and do not use CC3D compartment clusters.

Actions include:

  - `initialize`: Ensure the subcellular system exists for the current cell and apply
  registered default values if needed.

  - `set_stage`: Set the system stage directly, such as `inactive`, `seed`, `scaffold`, or
  `mature`.

  - `advance_stage`: Move from the current stage to another stage. If `to_stage` is omitted,
  the next stage in the registered `stages` list is used. Optional `from_stage` and
  `probability` can restrict the transition.

  - `set_component`: Set one component count to an explicit value.

  - `increase_component`: Add an amount to one component count.

  - `consume_component`: Subtract an amount from one component count. By default, the value is
  not allowed to go below zero.

  - `set_localization`: Set the amount or fraction stored in one localization pool.

  - `translocate`: Move an amount from one localization pool to another. If no source pool is
  provided, the amount is added directly to the target pool.

  - `set_value`: Write any custom nested value inside the subcellular system dictionary.

  - `assemble`: Consume required components, optionally create a product component, and
  optionally update the stage.

The runtime can create scalar fields for stage, activity, component counts, and localization values.


## 11. CSV Import

CSV import supports batch rule construction. Behaviour templates may be kept at the repository root for quick editing, and model/system templates are stored in `cc3d_builder/template/`.

- `Growth.csv`
- `Differentiate.csv`
- `Create.csv`
- `Death.csv`
- `SecreteUptake.csv`
- `DormancyRestore.csv`
- `Phagocytosis.csv`
- `Chemotaxis.csv`
- `Force.csv`
- `FPPLink.csv`
- `Compartmentalize.csv`

Registry CSV templates:

- `cc3d_builder/template/intracellular_model_registry_template.csv`
- `cc3d_builder/template/intracellular_model_rules_template.csv`
- `cc3d_builder/template/subcellular_system_registry_template.csv`
- `cc3d_builder/template/subcellular_rules_template.csv`

CSV import is best for structured, repeated rules. Complex nested conditions, custom scripts, or heavily nested mappings are easier to inspect and maintain through GUI or direct JSON.

## 12. GUI Surface
  
The GUI is implemented with PyQt5. Users need to install PyQt5 in their active Python environment, or follow the manual pipeline to create the recommended virtual environment before launching the GUI.

### Project Loader

Loads a source CC3D project into the sandbox and chooses import or resume mode.

### Main Editor

Provides:

- Add Rule
- Save
- Manage Rules
- XML Config Editor
- Intracellular Models
- Subcellular Systems
- State Key Reference
- Execution Semantics
- Import Rules CSV

### Manage Rules Window

Provides table-level editing:

- duplicate rules
- move rules up/down
- delete rules
- edit rule blocks
- manage cell and field references
- open XML, intracellular, and subcellular managers

### XML Config Editor

Manages XML-level structures:

- cell types and target/lambda volume values
- fields
- diffusion/decay
- chemotaxis settings
- initializer regions

### Intracellular Model Dialog

Manages SBML/Antimony/CellML/MaBoSS registry entries. It supports file and inline sources, attach cell types, initial values, input mappings, output mappings, and CSV import.

### Subcellular System Dialog

Manages coarse-grained subsystem definitions, including stages, default stage, attached cell types, components, and localization pools.

## 13. Runtime Data Flow

At each MCS, `RuleEngineSteppable.step(mcs)` performs:

1. Prepare each cell's `cell.dict` containers.
2. Choose `snapshot` or `asynchronous` execution.
3. Evaluate rule frequency.
4. Evaluate rule cases.
5. Build events for matching cases.
6. Dispatch each event through the behavior plugin.
7. Convert the matched case into an execution request.
8. Execute it through the behaviour steppable.
9. Update behaviour stats and state caches.
10. Audit cell state if `audit_interval` matches.
11. Write live audit CSV if `audit_export_interval` matches.

Dead cells are skipped by most behaviors. Dormant cells are skipped by most behaviors except dormancy and death.

## 14. Time-Series Audit And Visualization

The runtime audit captures:

- MCS
- cell id
- cell type
- volume
- target volume
- center of mass
- flattened `cell.dict`
- behavior stats
- intracellular cache values
- subcellular state values

Output directory:

```text
<RunningProject>/simulation_time_series/
```

If CompuCell Player opens `/Users/xiaoyue/Desktop/ProjectA/Rules_project.cc3d`, the generated-code runtime writes audit files under `/Users/xiaoyue/Desktop/ProjectA/simulation_time_series/`.

Main file:

```text
global_simulation_history.csv
```

Per-cell files:

```text
cell_id_<id>_sequence.csv
```

Settings:

```json
{
  "audit_interval": 10,
  "audit_export_interval": 10,
  "audit_cell_sequence_limit": 3
}
```

For generated-code output, `audit_cell_sequence_limit` may also be `0` to skip per-cell sequence files or `"all"` to export every observed cell id.

Key modules:

| path | role |
| --- | --- |
| `engine/core/rule_engine.py` | Runtime-engine audit capture and CSV export |
| `engine/code_generator.py` | Generated standalone steppable audit implementation |
| `engine/steppables/intracellular_model_steppable.py` | Mirrors intracellular variables into `cell.dict` and optional scalar fields |
| `engine/steppables/subcellular_steppable.py` | Mirrors subcellular stage/component/localization values into `cell.dict` and scalar fields |
| `core/state_key_catalog.py` | Documents common dynamic state keys exposed through `cell.dict` |

Runtime-engine capture:

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

Runtime-engine export:

```python
def _export_audit_data(self, final=False):
    master_df = pd.DataFrame(self._audit_buffer)
    master_df.to_csv(self.audit_output_dir / "global_simulation_history.csv", index=False)
```

Generated-code export uses the same conceptual pipeline, but writes CSV through Python's standard `csv.DictWriter` so `SimulationStepCode.py` can run without importing pandas.

The audit records whatever is present in `cell.dict`. This includes normal `state` keys, behavior statistics, intracellular caches, subcellular dictionaries, and custom values written by hooks or custom scripts.

## 15. Generated Native CC3D Code

The registry generates:

```text
Rules_project/Simulation/SimulationStepCode.py
Rules_project/Simulation/gen_code_main.py
```

`SimulationStepCode.py` is independent of the runtime rule engine. In the current synchronized source-project workflow, the source `.cc3d` points to `Simulation/gen_code_main.py`, which registers the generated steppable. Manual copying into Twedit remains useful for one-off experiments, but it is not the default sync path.

Generated code embeds:

- `COMPILED_RULES`
- `COMPILED_SETTINGS`
- `COMPILED_CELLTYPE_PARAMS`
- `COMPILED_FIELD_PARAMS`
- `COMPILED_INTRACELLULAR_MODELS`
- `COMPILED_SUBCELLULAR_SYSTEMS`

It contains one steppable class, not one steppable per rule. CC3D calls `step(mcs)`, and the generated steppable processes compiled rules in list order.

### 15.1 Custom Hooks

Custom generated-code edits belong inside:

```python
    # === USER CUSTOM HOOKS START ===
    # custom methods here
    # === USER CUSTOM HOOKS END ===
```

Rule hook:

```python
def rule_4(self, cell, payload, mcs):
    return "default"
```

Behavior hook:

```python
def handle_growth(self, cell, payload, mcs):
    return "default"
```

Hook priority:

```text
rule_<rule_id>
handle_<behaviour>
default generated handler
```

See `docs/generated_code_index.md` for the full generated-code helper index.

### 15.2 Custom Scripts

RuleParser has two custom script scopes:

- Condition-only scripts customize a `when` block and return a boolean from `validate(cell, engine, params)`.
- Full custom rule scripts use behaviour `custom_script` and provide `match(context)` plus `run(context, params)`.

Copyable templates are stored in:

```text
cc3d_builder/template/
```

Project-specific scripts should be copied into the active project, usually:

```text
Rules_project/Simulation/custom_scripts/
```

See `docs/custom_scripts.md` for the script interfaces and JSON shapes.

Parameter names such as `state_key` are ordinary user-defined values. In full custom rule scripts, literal `params.get("state_key")` calls are detected by the GUI and become editable script parameters. In condition-only scripts, `state_key` is entered in the Custom condition parameter prompt or edited in the condition JSON.

## 16. Extending The Framework

### 16.1 Add A New Behavior

Typical files to update:

1. Add a behavior plugin in `cc3d_builder/engine/behaviour_plugins/`.
2. Add a steppable executor in `cc3d_builder/engine/steppables/`.
3. Register the plugin in `RuleEngineSteppable.behaviour_registry`.
4. Register the steppable in `wrapper_main.py` generation if runtime execution needs it.
5. Add flattening logic to `core/rule_builder.py`.
6. Add GUI wizard prompts in `gui/main_editor.py`.
7. Add Manage Rules display/edit support when needed.
8. Add CSV importer columns and template CSV if useful.
9. Add XML dependency synchronization to `structure_manager.py` if the behavior requires CC3D plugins.
10. Add generated-code execution support in `engine/code_generator.py`.
11. Add or update docs and examples.

### 16.2 Add A New Condition

Typical files to update:

1. Add evaluation in `engine/core/condition_evaluator.py`.
2. Add GUI prompts in `gui/build_condition_gui.py`.
3. Add CSV parsing support in `core/csv_importer.py` if needed.
4. Add generated-code condition support in `engine/code_generator.py`.
5. Add state-key catalog entries if the condition introduces new state values.

### 16.3 Add A New Registry Type

Examples are intracellular models and subcellular systems.

Typical components:

- top-level `rules.json` key
- registry load/save support
- GUI manager dialog
- CSV import path
- runtime steppable initialization
- generated-code literal and helper logic
- visualization and audit support

## 17. Modeling Pattern Coverage

### 17.1 Multicellular Interaction Pattern

RuleParser supports multicellular simulations in which rules coordinate cell-level behaviors, state transitions, contact-dependent interactions, field-driven responses, FPP links, and morphology-related changes.

### 17.2 Component-As-Cell Submicroscopic Pattern

RuleParser can support simulations in which small biological components are represented as explicit CC3D cells. This pattern is useful when spatial movement, contact, adhesion, or force-like interactions between components matter more than storing those components as internal state only.

### 17.3 Intracellular Regulatory Model Pattern

RuleParser supports intracellular regulatory models through SBML, Antimony, CellML, and MaBoSS registry entries. These models can synchronize per-cell inputs and outputs, expose variables as Player scalar fields, write audit CSV data, and provide generated-code hooks for custom model logic.

## 18. Known Limitations

- CSV import is less suitable for deeply nested conditions and custom scripts.
- Generated code supports many behaviors, but every new behavior must be added deliberately to both runtime and generator paths.
- Subcellular systems are coarse-grained state dictionaries, not molecular geometry.
- Component-as-cell modeling is a specialized prototype, not a general molecular dynamics engine.
- CC3D Player scalar fields must be registered at runtime; an already-running Player process may need a restart after new visualization fields are added.
- Scientific validity depends on the modeler's biological assumptions, CC3D parameters, and calibration data. RuleParser organizes execution but does not validate biological correctness automatically.
- Some older files and saved sandbox snapshots may reflect previous experiments and should not be treated as canonical documentation.

## 19. Quick Reference

### Main Commands

```bash
python3 -m cc3d_builder.gui.project_loader
python3 -m cc3d_builder.cli.main
python3 -m cc3d_builder.cli.main --state-keys
python3 -m cc3d_builder.cli.main --state-keys --all
```

### Main Runtime Files

```text
Rules_project/Rules_project.cc3d
Rules_project/Simulation/gen_code_main.py
Rules_project/Simulation/rules.json
Rules_project/Simulation/SimulationStepCode.py
<RunningProject>/simulation_time_series/global_simulation_history.csv
```

### Source Project Profile

```text
<SourceProject>/.ruleparser/rules.json
<SourceProject>/.ruleparser/metadata.json
```

### Most Important Docs

```text
docs/generated_code_index.md
docs/runtime_vs_generated.md
docs/sync_and_artifacts.md
docs/audit_recording.md
docs/intracellular_models.md
docs/subcellular_systems.md
```

## 20. Glossary

| term | meaning |
| --- | --- |
| CC3D | CompuCell3D, the simulation engine. |
| MCS | Monte Carlo Step, the main CC3D simulation time index. |
| DSL | Domain-specific language. Here it means the JSON rule format. |
| registry | Python object storing rules and project-level model configuration. |
| sandbox | Shared `Rules_project` workspace used by RuleParser. |
| profile | Per-source-project `.ruleparser` folder storing RuleParser rules. |
| rule | Ordered behavior unit in `rules.json`. |
| case | One condition-action block inside a rule. |
| condition | Predicate determining whether a case applies. |
| behavior | Biological or physical action type. |
| plugin | Runtime object that converts a matched case into a request. |
| steppable executor | CC3D steppable that performs the matched action request. |
| generated code | Self-contained CC3D steppable generated from the current registry. |
| intracellular model | SBML/Antimony/CellML/MaBoSS model attached to CC3D cells. |
| subcellular system | Coarse-grained internal state dictionary stored inside each cell. |
