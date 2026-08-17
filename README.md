# CC3D RuleParser / CC3D Builder

CC3D RuleParser is a rule-management layer for CompuCell3D projects.

The project does not replace CompuCell3D. It sits above a valid CC3D project and manages the rule JSON, XML dependencies, generated Python runtime, and project-level model registries.

## Purpose

RuleParser is designed to make complex CompuCell3D model construction easier for non-coding users and for large-scale simulation projects.

Instead of requiring users to manually edit long Python steppables and XML configuration files, RuleParser lets users describe biological behaviors as structured rules. These rules can define cell growth, differentiation, death, secretion, chemotaxis, force, compartmentalization, intracellular models, and other interactions through GUI, CLI, CSV templates, or JSON.

The main goal is to reduce the difficulty of building and maintaining large simulation systems. For ordinary simulation users, it lowers the coding barrier. For complex projects, it makes model logic easier to inspect, modify, reuse, debug, and extend.

## What It Does

- Build ordered biological rules with GUI, CLI, CSV import, or direct JSON editing.
- Manage CC3D cell types, volume parameters, PDE fields, initializer regions, and required XML plugins.
- Support rule behaviours such as growth, differentiation, creation, death, secretion/uptake, dormancy, phagocytosis, chemotaxis, force, compartmentalization, FPP links, intracellular models, subcellular systems, and custom scripts.
- Compile the current rule set into generated CC3D code through `SimulationStepCode.py`.
- Run source CC3D projects directly through generated-code mode with `Simulation/gen_code_main.py`.
- Record runtime audit CSV files for cell state, behaviour stats, intracellular values, and subcellular state.
- Keep a per-source-project `.ruleparser/` profile and original backup for safer import/resume workflows.

## Main Workflows

GUI project loader:

```bash
python3 -m cc3d_builder.gui.project_loader
```

CLI:

```bash
python3 -m cc3d_builder.cli.main
```

View state-key reference:

```bash
python3 -m cc3d_builder.cli.main --state-keys
```

Import rules from CSV:

```bash
python3 -m cc3d_builder.cli.main path/to/rules.csv
```

## Runtime Paths

RuleParser has two execution paths.

Runtime engine path:

```text
rules.json -> wrapper_main.py -> RuleEngineSteppable -> plugins/steppables
```

Generated-code path:

```text
rules.json / registry -> code_generator.py -> SimulationStepCode.py -> gen_code_main.py
```

The current synchronized source-project workflow uses generated-code mode by default. The source `.cc3d` points to:

```text
Simulation/gen_code_main.py
```

## Important Directories

```text
cc3d_builder/          main application code
cc3d_builder/cli/      command-line interface
cc3d_builder/gui/      PyQt GUI
cc3d_builder/core/     project, rule, CSV, XML, and state-key logic
cc3d_builder/engine/   rule runtime, generated-code runtime, plugins, steppables
cc3d_builder/template/ custom script and CSV templates
docs/                  user and developer documentation
Rules_project/         local sandbox working project
tools/                 utility scripts
```

`Rules_project/` is a working sandbox and may contain local generated output. Treat it as runtime/project state, not as the main source of framework logic.

## Documentation

Start with:

- [`docs/cc3d_ruleparser_guide-260810.md`](docs/cc3d_ruleparser_guide-260810.md): overall guide, architecture, workflow, behaviours, and extension notes.
- [`docs/runtime_vs_generated.md`](docs/runtime_vs_generated.md): difference between the runtime engine path and generated-code path.
- [`docs/sync_and_artifacts.md`](docs/sync_and_artifacts.md): source project, sandbox, profile, original backup, and artifact synchronization.
- [`docs/audit_recording.md`](docs/audit_recording.md): runtime CSV output, recorded keys, and audit settings.
- [`docs/generated_code_index.md`](docs/generated_code_index.md): structure of generated `SimulationStepCode.py`, hooks, helpers, and customization points.
- [`docs/custom_scripts.md`](docs/custom_scripts.md): condition-only scripts, full custom rule scripts, parameters, and helper APIs.
- [`docs/intracellular_models.md`](docs/intracellular_models.md): SBML, Antimony, CellML, and MaBoSS model registry and rule execution.
- [`docs/subcellular_systems.md`](docs/subcellular_systems.md): coarse-grained internal state systems stored in `cell.dict`.
- [`docs/README.md`](docs/README.md): documentation index.

Additional notes:

- [`docs/cc3d_builder.txt`](docs/cc3d_builder.txt): compact file-structure notes.
- CSV templates are in `cc3d_builder/template/`.
- Behaviour CSV examples also exist at the repository root, such as `Growth.csv`, `Force.csv`, `Compartmentalize.csv`, and `SecreteUptake.csv`.

## Slides

No `slides/` directory is currently tracked in this repository. ## 

## Runtime Output

When a source project is run in CompuCell Player, audit output is written under the running project root:

```text
<RunningProject>/simulation_time_series/
```

Typical files:

```text
global_simulation_history.csv
cell_id_<id>_sequence.csv
```

These files are generated by the simulation runtime. They are not documentation files and usually should not be treated as source code.
