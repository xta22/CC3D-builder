# Runtime Recording And Audit Output

RuleParser records simulation state into CSV files during runtime.

Both the runtime engine path and generated-code path can write audit output.

## Output Location

Audit files are written relative to the CC3D project that is currently running.

If CompuCell Player opens:

```text
/Users/xiaoyue/Desktop/ProjectA/Rules_project.cc3d
```

then output goes to:

```text
/Users/xiaoyue/Desktop/ProjectA/simulation_time_series/
```

This folder is created by the running simulation. It is not copied there by RuleParser sync.

## Main Files

```text
global_simulation_history.csv
cell_id_<id>_sequence.csv
```

`global_simulation_history.csv` contains all audited cell rows.

Each `cell_id_<id>_sequence.csv` contains one observed cell's time sequence.

## What Gets Recorded

Each audit row records base cell values:

```text
MCS
Cell_ID
Cell_Type
Volume
TargetVolume
X_COM
Y_COM
Z_COM
```

It also flattens `cell.dict`.

For example:

```python
cell.dict["state"]["oxygen_signal"]
```

becomes:

```text
state_oxygen_signal
```

Nested values are flattened with underscores.

Common recorded groups include:

```text
state keys
behaviour_stats
intracellular caches
subcellular state
death/dormancy state
force state
compartmentalize state
custom script values
```

## Settings

Common settings:

```json
{
  "audit_interval": 10,
  "audit_cell_sequence_limit": 3
}
```

`audit_interval` controls how often cell state is captured.

`audit_cell_sequence_limit` controls how many per-cell sequence files are exported.

Supported values:

```text
3       export first 3 observed cell IDs
0       do not export per-cell sequence files
"all"   export every observed cell ID
```

`"all"` means all cell IDs that ever appeared in the audit buffer. If a cell dies or is deleted during the simulation, its sequence file still contains the rows recorded while it existed. Deleted cells are not padded with empty rows after deletion.

## Dynamic Values

`audit_cell_sequence_limit` is a global export setting. It is not a per-cell expression.

Use numbers, `0`, or `"all"`.

Do not use cell-specific expressions such as:

```text
{volume}
{division_count}
```

If a project needs conditional per-cell export later, it should use a separate filter setting instead of overloading the limit value.
