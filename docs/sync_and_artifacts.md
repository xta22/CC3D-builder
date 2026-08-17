# Project Sync And Artifacts

RuleParser works with two project locations.

## Source Project

The source project is the user CC3D project, for example:

```text
/Users/xiaoyue/Desktop/ProjectA
```

This is the project opened by CompuCell Player.

## Sandbox Project

The sandbox is the working copy inside this repository:

```text
Rules_project/
```

RuleParser edits and rebuilds project files here first.

## Project Profile

Each source project stores its latest RuleParser state under:

```text
<SourceProject>/.ruleparser/rules.json
```

This file is used when resuming a project.

The source project may also contain:

```text
<SourceProject>/Simulation/rules.json
```

This is the runtime/project copy of the same rule state.

The sandbox contains:

```text
Rules_project/Simulation/rules.json
```

## Three Rule Copies

In a synchronized project, these should represent the same rule state:

```text
Rules_project/Simulation/rules.json
<SourceProject>/Simulation/rules.json
<SourceProject>/.ruleparser/rules.json
```

If only one of them is edited manually, the next resume or save may overwrite the change.

## Generated Artifacts

RuleParser generates or syncs these main files:

```text
Rules_project.cc3d
Simulation/Rules_project.xml
Simulation/Rules_project_Steppables.py
Simulation/SimulationStepCode.py
Simulation/gen_code_main.py
Simulation/rules.json
Simulation/_settings.sqlite
```

For generated-code execution, the important files are:

```text
Rules_project.cc3d
Simulation/gen_code_main.py
Simulation/SimulationStepCode.py
Simulation/Rules_project.xml
```

## Original Backup

When a source project is first imported, RuleParser stores an original snapshot under:

```text
<SourceProject>/.ruleparser/original/
```

This backup is not overwritten by normal save or sync operations.

It is used as the baseline for reset/import-new workflows.

## Resume vs Import New

Resume means:

```text
load the current project profile and continue editing
```

Import New or initialize means:

```text
restore from the original baseline, reset rules/profile state, then rebuild current artifacts
```

## Manual Edits

Manual edit effects depend on what is edited.

Editing `rules.json` changes stored rule data, but generated-code simulation will not change until `SimulationStepCode.py` is regenerated.

Editing `SimulationStepCode.py` changes generated-code runtime immediately, but the change can be overwritten the next time code is regenerated.

Editing XML can affect CC3D structure, but RuleParser may rebuild XML from registry state during save.

Best practice:

```text
persistent model change -> edit through RuleParser GUI/CLI/CSV
temporary runtime experiment -> edit SimulationStepCode.py
manual JSON change -> update all rule copies and regenerate generated code
```
