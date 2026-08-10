# csv_importer.py
import json

import pandas as pd

from cc3d_builder.core.dynamic_numeric import parse_dynamic_numeric
from cc3d_builder.core.rule_builder import build_rule

# ===========
# helper
# ===========
def is_blank(val):
    return pd.isna(val) or str(val).strip() == ""


def get_id(row):
    return str(row["id"] if "id" in row and not is_blank(row.get("id")) else row["rule_id"])


def get_target(row):
    val = row.get("target")
    if is_blank(val) or str(val).strip().lower() == "none":
        return None
    return str(val).strip()


def get_str(row, key, default=""):
    val = row.get(key, default)
    return default if is_blank(val) else str(val).strip()


def clean_label(value):
    text = str(value or "").strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


def get_float(row, key, default=0.0):
    val = row.get(key, default)
    return default if is_blank(val) else float(val)


def get_dynamic_number(row, key, default=0.0):
    return parse_dynamic_numeric(row.get(key, default), default)


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_bool(row, key, default=False):
    val = row.get(key, default)
    if is_blank(val):
        return default
    return str(val).strip().lower() in {"true", "1", "yes", "y"}


def base_params(row):
    params = {
        "id": get_id(row),
        "target": get_target(row),
        "when": parse_condition(row),
        "frequency": parse_safe_frequency(row.get("frequency", 1)),
        "once": get_bool(row, "once", False),
        "debug": get_bool(row, "debug", False),
    }
    if "order" in row and not is_blank(row.get("order")):
        params["order"] = get_float(row, "order")
    return params


def parse_key_value_string(text):
    if is_blank(text):
        return {}

    parsed = {}
    for part in str(text).split(","):
        if "=" not in part:
            continue
        key, value = [item.strip() for item in part.split("=", 1)]
        if key:
            parsed[key] = value
    return parsed


def parse_safe_frequency(val):
    """
    **Execution frequency parser.
    Supports plain integers, floating-point numbers, formula text strings, or JSON dynamic models wrapped in curly braces {}.**
    """
    if pd.isna(val):
        return 1  # If the frequency is not filled in the CSV, it defaults to running once per step.

    val_str = str(val).strip()

    # If the user directly writes a JSON string representing a dynamic physical model in the `frequency` column of the CSV.
    if val_str.startswith("{") and val_str.endswith("}"):
        import json
        try:
            return json.loads(val_str)
        except Exception:
            return val_str

    # If it is a plain numeric value.
    try:
        return float(val_str) if '.' in val_str else int(val_str)
    except ValueError:

        return val_str

# =========================
# VALIDATION
# =========================

def validate_growth_row(row):

    model = row["model"]

    if model == "linear" and pd.isna(row["alpha"]):
        raise ValueError("linear model requires alpha")

    if model == "hill":
        for f in ["y_min", "y_max", "k", "n"]:
            if pd.isna(row[f]):
                raise ValueError(f"hill model missing {f}")

    if model == "expression" and pd.isna(row["expression"]):
        raise ValueError("expression model requires expression")

def validate_create_row(row):

    for f in ["cell_type", "count", "dist_type"]:
        if pd.isna(row.get(f)):
            raise ValueError(f"Create behaviour missing required field: {f}")

    dist_type = row["dist_type"]

    if dist_type == "cluster":
        for f in ["center_x", "center_y", "radius"]:
            if pd.isna(row.get(f)):
                raise ValueError(f"Cluster distribution missing: {f}")

    elif dist_type == "stripe":
        if pd.isna(row.get("direction")):
            raise ValueError("Stripe distribution missing: direction")

def validate_diff_row(row):
    mode = row.get("mode")
    if pd.isna(mode):
        raise ValueError("Differentiate behaviour missing required field: mode")

    if mode == "type_switch":
        if pd.isna(row.get("new_type")):
            raise ValueError("type_switch mode requires new_type")

    elif mode == "division":
        for f in ["parent_type", "child_type", "volume_ratio", "placement_type"]:
            if pd.isna(row.get(f)):
                raise ValueError(f"division mode missing: {f}")

        placement = row.get("placement_type")
        if placement == "angle" and pd.isna(row.get("angle_deg")):
            raise ValueError("angle placement requires angle_deg")
        elif placement == "vector" and (pd.isna(row.get("dx")) or pd.isna(row.get("dy"))):
            raise ValueError("vector placement requires dx and dy")

def validate_death_row(row):

    death_mode = row.get("mode")
    if is_blank(death_mode):
        death_mode = row.get("model")

    if pd.isna(death_mode) or str(death_mode).strip() == "":
        raise ValueError("Death behaviour missing required field: behaviour or model (e.g., apoptosis, necrosis)")

    valid_models = ["apoptosis", "necrosis"]
    if str(death_mode).strip().lower() not in valid_models:
        raise ValueError(f"Invalid death model '{death_mode}'. Must be one of {valid_models}")

def validate_secrete_uptake_row(row):
    if is_blank(row.get("id")) and is_blank(row.get("rule_id")):
        raise ValueError("secrete/uptake behaviour missing required field: id")

    for f in ["field_name", "secret_mode"]:
        if pd.isna(row.get(f)) or str(row.get(f)).strip() == "":
            raise ValueError(f"secrete/uptake behaviour missing required field: {f}")

    mode = str(row["secret_mode"]).strip()

    valid_modes = [
        "secreteInsideCell", "secreteInsideCellAtBoundary", "secreteOutsideCellAtBoundary", "secreteInsideCellAtCOM",
        "uptakeInsideCell", "uptakeInsideCellAtBoundary", "uptakeOutsideCellAtBoundary", "uptakeInsideCellAtCOM",
        "secreteInsideCellAtBoundaryOnContactWith", "secreteOutsideCellAtBoundaryOnContactWith",
        "uptakeInsideCellAtBoundaryOnContactWith", "uptakeOutsideCellAtBoundaryOnContactWith"
    ]
    if mode not in valid_modes:
        raise ValueError(f"Invalid secret_mode '{mode}'. Must be one of {valid_modes}")

    if "OnContactWith" in mode:
        if pd.isna(row.get("contact_types")) or str(row.get("contact_types")).strip() == "":
            raise ValueError(f"Mode '{mode}' requires 'contact_types' (comma separated).")

def validate_dormancy_row(row):
    if pd.isna(row.get("id")) or pd.isna(row.get("target")):
        raise ValueError("Dormancy behaviour missing required fields: 'id' or 'target'")

    if pd.isna(row.get("mode")) or str(row["mode"]).strip().lower() not in ["dormant", "reactivate", "activate", "deactivate"]:
        raise ValueError("Dormancy behaviour missing or invalid 'mode'. Must be 'activate' or 'deactivate' (or 'dormant'/'reactivate')")

def validate_phagocytosis_row(row):

    if pd.isna(row.get("id")) or pd.isna(row.get("target")):
        raise ValueError("Phagocytosis behaviour missing required identity fields: 'id' or 'target'")

    phago_mode = str(row.get("mode", "engulfment")).strip().lower()
    valid_modes = ["absorption", "engulfment", "frustrated"]
    if phago_mode not in valid_modes:
        raise ValueError(f"Invalid phagocytosis mode '{phago_mode}'. Must be one of {valid_modes}")

    target_found = False
    for col in ["phago_target", "regulator", "cell_type"]:
        if not pd.isna(row.get(col)) and str(row.get(col)).strip() != "":
            target_found = True
            break

    if not target_found:
        raise ValueError("Phagocytosis behaviour requires a target cell type to eat! Please specify it in 'phago_target' or 'regulator' column.")

def validate_chemotaxis_row(row):

    import pandas as pd

    if pd.isna(row.get("id")) or pd.isna(row.get("target")):
        raise ValueError("Chemotaxis behaviour missing required identity fields: 'id' or 'target'")

    mode_param = row.get("mode_param")
    mode_values = parse_key_value_string(mode_param)
    has_field = (
        not is_blank(row.get("field_name"))
        or not is_blank(row.get("field"))
        or "field" in mode_values
    )
    has_lambda = not is_blank(row.get("lambda")) or "lambda" in mode_values

    if not has_field or not has_lambda:
        raise ValueError(
            f"Rule [ID: {row.get('id')}]: Chemotaxis requires field_name/field and lambda "
            f"either as columns or inside mode_param. Example columns: field_name=ATTR, lambda=20.0"
        )

    param_str = str(mode_param).strip() if not is_blank(mode_param) else ""
    parts = [p.strip() for p in param_str.split(",")]

    param_keys = []
    formula_name = get_str(row, "formula", mode_values.get("formula", "Standard"))

    for part in parts:
        if "=" in part:
            k = part.split("=")[0].strip().lower()
            v = part.split("=")[1].strip()
            param_keys.append(k)
            if k == "formula":
                formula_name = v

    valid_formulas = ["Standard", "Saturation", "SaturationLinear", "LogScaled"]
    if formula_name not in valid_formulas:
        raise ValueError(
            f"Rule [ID: {row.get('id')}]: Invalid chemotaxis formula '{formula_name}'. "
            f"Must be one of {valid_formulas}"
        )

def validate_force_row(row):
    if is_blank(row.get("id")) and is_blank(row.get("rule_id")):
        raise ValueError("Force behaviour missing required field: id")
    if is_blank(row.get("target")):
        raise ValueError("Force behaviour requires target cell type")

    mode = get_str(row, "mode", "vector").lower()
    valid_modes = {
        "vector",
        "stored_vector",
        "toward_position",
        "away_from_position",
        "toward_cell_id",
        "toward_nearest_type",
        "away_from_nearest_type",
        "toward_field_gradient",
        "clear",
    }
    if mode not in valid_modes:
        raise ValueError(f"Invalid force mode '{mode}'. Must be one of {sorted(valid_modes)}")

    mode_values = parse_key_value_string(row.get("mode_param", ""))
    has = lambda key: not is_blank(row.get(key)) or key in mode_values

    if mode == "vector" and not (has("dx") or has("dy") or has("dz")):
        raise ValueError("Force vector mode requires at least one of dx/dy/dz")
    if mode in {"toward_position", "away_from_position"} and not (has("x") or has("target_x")):
        raise ValueError("Force position mode requires x/y[/z] or target_x/target_y[/target_z]")
    if mode == "toward_cell_id" and not has("target_cell_id"):
        raise ValueError("Force toward_cell_id mode requires target_cell_id")
    if mode in {"toward_nearest_type", "away_from_nearest_type"} and not (has("target_type") or has("cell_type")):
        raise ValueError("Force nearest_type mode requires target_type or cell_type")
    if mode == "toward_field_gradient" and not (has("field_name") or has("field")):
        raise ValueError("Force field gradient mode requires field_name")


def validate_compartmentalize_row(row):
    if is_blank(row.get("id")) and is_blank(row.get("rule_id")):
        raise ValueError("Compartmentalize behaviour missing required field: id")
    if is_blank(row.get("target")):
        raise ValueError("Compartmentalize behaviour requires target cell type")

    action = get_str(row, "action", get_str(row, "mode", "extend_chain")).lower()
    valid_actions = {"initialize", "initialize_cluster", "init_cluster", "extend", "extend_chain", "branch", "branch_chain"}
    if action not in valid_actions:
        raise ValueError(f"Invalid compartmentalize action '{action}'. Must be one of {sorted(valid_actions)}")

    mode_values = parse_key_value_string(row.get("mode_param", ""))
    segment_type = row.get("segment_type")
    if is_blank(segment_type):
        segment_type = mode_values.get("segment_type") or row.get("cell_type")

    if action not in {"initialize", "initialize_cluster", "init_cluster"} and is_blank(segment_type):
        raise ValueError("Compartmentalize extend/branch requires segment_type or cell_type")


def validate_fpp_link_row(row):
    if is_blank(row.get("id")) and is_blank(row.get("rule_id")):
        raise ValueError("FPP link behaviour missing required field: id")
    if is_blank(row.get("target")):
        raise ValueError("FPP link behaviour requires target cell type")

    mode = get_str(row, "mode", "nearest_type").lower()
    valid_modes = {"nearest_type", "cell_id", "target_cell_id", "by_id", "all_within_distance", "within_distance", "clear", "remove_all"}
    if mode not in valid_modes:
        raise ValueError(f"Invalid FPP link mode '{mode}'. Must be one of {sorted(valid_modes)}")

    mode_values = parse_key_value_string(row.get("mode_param", ""))
    has = lambda key: not is_blank(row.get(key)) or key in mode_values
    if mode not in {"clear", "remove_all"} and not (has("partner_type") or has("target_type") or has("cell_type")):
        raise ValueError("FPP link requires partner_type, target_type, or cell_type")
    if mode in {"cell_id", "target_cell_id", "by_id"} and not (has("target_cell_id") or has("partner_cell_id")):
        raise ValueError("FPP link cell_id mode requires target_cell_id or partner_cell_id")


def validate_intracellular_model_row(row):
    if is_blank(row.get("id")) and is_blank(row.get("rule_id")):
        raise ValueError("Intracellular model behaviour missing required field: id")
    if is_blank(row.get("model")) and is_blank(row.get("model_name")):
        raise ValueError("Intracellular model behaviour requires model or model_name")

    action = get_str(row, "action", get_str(row, "mode", "advance")).lower()
    valid_actions = {
        "advance",
        "sync_inputs",
        "step",
        "step_all",
        "timestep",
        "timestep_all",
        "global_step",
        "sync_outputs",
        "reset",
        "set_variable",
    }
    if action not in valid_actions:
        raise ValueError(f"Invalid intracellular action '{action}'. Must be one of {sorted(valid_actions)}")


def validate_subcellular_row(row):
    if is_blank(row.get("id")) and is_blank(row.get("rule_id")):
        raise ValueError("Subcellular behaviour missing required field: id")
    if is_blank(row.get("system")) and is_blank(row.get("subsystem")):
        raise ValueError("Subcellular behaviour requires system or subsystem")

    action = get_str(row, "action", get_str(row, "mode", "set_stage")).lower()
    valid_actions = {
        "initialize",
        "init",
        "set_stage",
        "advance_stage",
        "set_component",
        "set_count",
        "increase_component",
        "add_component",
        "consume_component",
        "decrease_component",
        "set_localization",
        "translocate",
        "set_value",
        "assemble",
    }
    if action not in valid_actions:
        raise ValueError(f"Invalid subcellular action '{action}'. Must be one of {sorted(valid_actions)}")

# =========================
# PARSER
# -- parse a row of CSV into a parameter dictionary
# with exactly the same structure as the CLI/GUI Wizard.
# =========================
def parse_growth_row(row):
    validate_growth_row(row)

    params = base_params(row)

    model = get_str(row, "model").lower()
    params["model"] = model
    params["regulator"] = get_str(row, "regulator", "None")

    if model == "linear":
        params["alpha"] = get_float(row, "alpha")
    elif model == "hill":
        params["y_min"] = get_float(row, "y_min")
        params["y_max"] = get_float(row, "y_max")
        params["K"] = get_float(row, "k")
        params["n"] = get_float(row, "n")
    elif model == "expression":
        params["expression"] = get_str(row, "expression")
    else:
        raise ValueError(f"Unknown growth model: {model}")

    return "growth", params

def parse_create_row(row): # flattened

    validate_create_row(row)

    params = base_params(row)

    params["cell_type"] = str(row["cell_type"]).strip()
    params["count"] = get_dynamic_number(row, "count", 1)

    dist_type = str(row["dist_type"]).strip()
    dist = {}
    dist["type"] = dist_type

    if dist_type == "cluster":
        dist["center"] = [float(row["center_x"]), float(row["center_y"])]
        dist["radius"] = float(row["radius"])

    elif dist_type == "stripe":
        direction = str(row["direction"]).strip().lower()
        dist["direction"] = direction

        if direction == "vertical":
            dist["x"] = float(row["x"])
            dist["y_start"] = float(row["y_start"])

            if not pd.isna(row.get("y_gap")) and str(row["y_gap"]).strip() != "":
                dist["y_gap"] = float(row["y_gap"])
            elif not pd.isna(row.get("y_end")) and str(row["y_end"]).strip() != "":
                dist["y_end"] = float(row["y_end"])
        else:
            dist["y"] = float(row["y"])
            dist["x_start"] = float(row["x_start"])

            if not pd.isna(row.get("x_gap")) and str(row["x_gap"]).strip() != "":
                dist["x_gap"] = float(row["x_gap"])
            elif not pd.isna(row.get("x_end")) and str(row["x_end"]).strip() != "":
                dist["x_end"] = float(row["x_end"])

    params["distribution"] = dist

    return "create", params

def parse_diff_row(row):
    validate_diff_row(row)

    params = base_params(row)

    mode = str(row["mode"]).strip()
    params["mode"] = mode

    if mode == "type_switch":
        params["new_type"] = row["new_type"]
        final_behaviour = "differentiate"

    else:  # division
        final_behaviour = "differentiate"

        params["parent_type"] = row["parent_type"]
        params["child_type"] = row["child_type"]
        params["volume_ratio"] = get_dynamic_number(row, "volume_ratio", 0.5)

        params["inheritance_strategy"] = str(row.get("mode_param", "total")).strip().lower()
        params["state_key"] = "division_count"

        placement = {"type": row["placement_type"]}

        if placement["type"] == "angle":
            placement["angle_deg"] = float(row["angle_deg"])

        elif placement["type"] == "vector":
            placement["dx"] = float(row["dx"])
            placement["dy"] = float(row["dy"])

        params["placement"] = placement

    return final_behaviour, params

def parse_death_row(row):
    validate_death_row(row)
    params = base_params(row)

    params["mode"] = get_str(row, "mode", "apoptosis").lower()
    params["shrink_rate"] = get_dynamic_number(row, "shrink_rate", 0.95)
    params["terminal_volume"] = get_dynamic_number(row, "terminal_volume", 0.0)
    params["swell_rate"] = get_dynamic_number(row, "swell_rate", 1.05)
    params["max_target_volume"] = get_dynamic_number(row, "max_target_volume", 150.0)
    params["post_burst_shrink_rate"] = get_dynamic_number(row, "post_burst_shrink_rate", 0.8)
    params["color_change"] = str(row.get("color_change", "grey"))

    if "parse_fields_from_string" in globals():
        params["fields"] = parse_fields_from_string(row.get("release_fields", ""))
    else:
        params["fields"] = row.get("release_fields", "")

    return "death", params

def parse_fields_from_string(field_str):
    """
    ```python
    # Release fields for necrosis (the CSV may contain a semicolon-separated string,
    # e.g. "Oxygen:50;Glucose:10")
    ```
    """
    if not field_str or pd.isna(field_str) or str(field_str).lower() == "none":
        return []

    parsed_json = parse_dynamic_numeric(field_str, None)
    if isinstance(parsed_json, dict):
        parsed_json = [parsed_json]
    if isinstance(parsed_json, list):
        fields = []
        for item in parsed_json:
            if not isinstance(item, dict):
                continue
            name = item.get("field_name") or item.get("field")
            if not name:
                continue
            fields.append({
                "field_name": str(name).strip(),
                "amount": parse_dynamic_numeric(item.get("amount", 0.0), 0.0),
            })
        return fields

    fields = []
    # 1. Split multiple substrates by semicolons
    parts = str(field_str).split(';')
    for part in parts:
        if ':' in part:
            # 2. Split the name and value by colon
            name, amount = part.split(':', 1)
            fields.append({
                "field_name": name.strip(),
                "amount": parse_dynamic_numeric(amount.strip(), 0.0)
            })
    return fields

def parse_secrete_uptake_row(row):
    if "validate_secrete_uptake_row" in globals():
        validate_secrete_uptake_row(row)

    params = base_params(row)

    params["field_name"] = str(row["field_name"]).strip()
    mode = str(row["secret_mode"]).strip()
    params["secret_mode"] = mode

    if "uptake" in mode:
        params["amount"] = get_dynamic_number(row, "amount", 1.0)
        params["relative_uptake"] = get_dynamic_number(row, "relative_uptake", 0.1)
    else:
        params["amount"] = get_dynamic_number(row, "amount", 1.0)
        params["relative_uptake"] = 0.0

    if "OnContactWith" in mode:
        params["contact_types"] = str(row["contact_types"]).strip()
    else:
        params["contact_types"] = ""

    if not pd.isna(row.get("total_count")):
        val_str = str(row["total_count"]).strip().lower()
        params["total_count"] = val_str in ["true", "y", "1", "yes"]
    else:
        params["total_count"] = False

    return "secrete/uptake", params

def parse_dormancy_row(row):
    validate_dormancy_row(row)
    params = base_params(row)

    mode = get_str(row, "mode", "dormant").lower()
    params["action"] = {
        "activate": "dormant",
        "dormant": "dormant",
        "deactivate": "reactivate",
        "reactivate": "reactivate",
    }[mode]

    return "dormancy", params

def parse_phagocytosis_row(row):
      validate_phagocytosis_row(row)
      params = base_params(row)

      phago_mode = get_str(row, "mode", "engulfment").lower()
      target_cell_type = ""

      for col in ["phago_target", "regulator", "cell_type"]:
          if not is_blank(row.get(col)):
              target_cell_type = get_str(row, col)
              break

      params.update({
          "phago_mode": phago_mode,
          "target_cell_type": target_cell_type,
          "eating_rate": 0.0 if phago_mode == "frustrated" else get_dynamic_number(row, "value_param",
  2.0),
          "leak_field": get_str(row, "release_field", "None"),
          "leak_amount": get_dynamic_number(row, "release_amount", 0.0),
      })

      raw_release_fields = row.get("release_fields", "")
      if not is_blank(raw_release_fields) and ":" in str(raw_release_fields):
          parsed = parse_fields_from_string(raw_release_fields)
          if parsed:
              params["leak_field"] = parsed[0]["field_name"]
              params["leak_amount"] = parsed[0]["amount"]

      return "phagocytosis", params

def parse_chemotaxis_row(row):
    validate_chemotaxis_row(row)
    params = base_params(row)

    mode_param = get_str(row, "mode_param")
    mode_values = parse_key_value_string(mode_param)
    field_name = "ATTR"
    lambda_val = 20.0
    formula_name = "Standard"
    coef_val = None

    if not is_blank(row.get("field_name")):
        field_name = get_str(row, "field_name")
    elif not is_blank(row.get("field")):
        field_name = get_str(row, "field")
    elif "field" in mode_values:
        field_name = mode_values["field"]

    if not is_blank(row.get("lambda")):
        lambda_val = get_dynamic_number(row, "lambda", 20.0)
    elif "lambda" in mode_values:
        lambda_val = parse_dynamic_numeric(mode_values["lambda"], 20.0)

    if isinstance(lambda_val, str) and lambda_val.strip().upper() == "DYNAMIC":
        lambda_val = 20.0

    if not is_blank(row.get("formula")):
        formula_name = get_str(row, "formula", "Standard")
    elif "formula" in mode_values:
        formula_name = mode_values["formula"]

    if not is_blank(row.get("coef")):
        coef_val = get_dynamic_number(row, "coef", None)
    elif "coef" in mode_values:
        coef_val = parse_dynamic_numeric(mode_values["coef"], None)

    params.update({
        "mode": "chemotaxis",
        "field_name": field_name,
        "lambda": lambda_val,
        "formula": formula_name,
        "coef": coef_val,
        "target_strategy": get_str(row, "target_strategy", "break"),
        "mode_param": mode_param or f"field={field_name},lambda=DYNAMIC,formula={formula_name}",
    })

    for key in ["target_cell_id", "target_x", "target_y", "target_z"]:
        if not is_blank(row.get(key)):
            params[key] = get_float(row, key)

    return "chemotaxis", params


def parse_force_row(row):
    validate_force_row(row)
    params = base_params(row)
    mode_values = parse_key_value_string(row.get("mode_param", ""))

    params["mode"] = get_str(row, "mode", mode_values.get("mode", "vector")).lower()
    force_default = parse_dynamic_numeric(mode_values.get("force", mode_values.get("magnitude", 1.0)), 1.0)
    params["force"] = get_dynamic_number(row, "force", force_default)
    params["persist"] = get_bool(row, "persist", str(mode_values.get("persist", "false")).lower() in {"1", "true", "yes", "y"})
    decay_default = parse_dynamic_numeric(mode_values.get("decay", 1.0), 1.0)
    params["decay"] = get_dynamic_number(row, "decay", decay_default)

    for key, value in mode_values.items():
        if key not in params:
            params[key] = value

    numeric_keys = [
        "dx", "dy", "dz",
        "x", "y", "z",
        "target_x", "target_y", "target_z",
        "target_cell_id",
        "gradient_step", "step",
    ]
    text_keys = [
        "target_type",
        "cell_type",
        "target_cell_type",
        "field_name",
        "field",
        "vector_prefix",
    ]

    for key in numeric_keys:
        if not is_blank(row.get(key)):
            params[key] = get_float(row, key)
    for key in text_keys:
        if not is_blank(row.get(key)):
            params[key] = get_str(row, key)

    return "force", params


def parse_compartmentalize_row(row):
    validate_compartmentalize_row(row)
    params = base_params(row)
    mode_values = parse_key_value_string(row.get("mode_param", ""))

    params["action"] = get_str(row, "action", get_str(row, "mode", mode_values.get("action", "extend_chain"))).lower()
    params["direction_mode"] = get_str(row, "direction_mode", mode_values.get("direction_mode", "stored_vector")).lower()

    for key, value in mode_values.items():
        if key not in params:
            params[key] = value

    text_keys = [
        "segment_type",
        "tip_type",
        "cell_type",
        "field_name",
        "field",
        "site_selection_mode",
        "replace_target_types",
        "replace_types",
        "target_types",
        "target_type",
    ]
    dynamic_numeric_keys = [
        "extension_interval",
        "step_length",
        "search_radius",
        "branch_probability",
    ]
    numeric_keys = [
        "max_length",
        "link_lambda",
        "lambda_distance",
        "target_distance",
        "max_distance",
        "internal_contact_energy",
        "internal_neighbor_order",
        "direction_noise",
        "angle_noise",
        "dx", "dy", "dz",
        "x", "y", "z",
        "target_x", "target_y", "target_z",
        "gradient_step",
    ]

    for key in text_keys:
        if not is_blank(row.get(key)):
            params[key] = get_str(row, key)
    for key in dynamic_numeric_keys:
        default_value = parse_dynamic_numeric(mode_values.get(key), None)
        if not is_blank(row.get(key)) or default_value is not None:
            params[key] = get_dynamic_number(row, key, default_value)
    for key in numeric_keys:
        if not is_blank(row.get(key)):
            params[key] = get_float(row, key)

    # New boolean and numeric fields added to Compartmentalize CSV
    if not is_blank(row.get("start_with_tip")):
        params["start_with_tip"] = get_bool(row, "start_with_tip", True)
    if not is_blank(row.get("compartment_single_extend_per_branch")):
        params["compartment_single_extend_per_branch"] = get_bool(row, "compartment_single_extend_per_branch", False)
    if not is_blank(row.get("compartment_can_extend")):
        params["compartment_can_extend"] = get_bool(row, "compartment_can_extend", False)
    if not is_blank(row.get("max_active_tips_per_cluster")):
        params["max_active_tips_per_cluster"] = int(get_float(row, "max_active_tips_per_cluster", 1))
    if not is_blank(row.get("single_tip_per_cluster")):
        params["single_tip_per_cluster"] = get_bool(row, "single_tip_per_cluster", True)
    if not is_blank(row.get("single_branch_per_cluster")):
        params["single_branch_per_cluster"] = get_bool(row, "single_branch_per_cluster", False)
    if not is_blank(row.get("single_branch_selection_mode")):
        params["single_branch_selection_mode"] = get_str(row, "single_branch_selection_mode", "random")
    if not is_blank(row.get("max_branches_per_segment")):
        params["max_branches_per_segment"] = int(get_float(row, "max_branches_per_segment", 3))
    if not is_blank(row.get("max_branch_length")):
        params["max_branch_length"] = int(get_float(row, "max_branch_length", 6))
    if not is_blank(row.get("branch_angle_degrees")):
        params["branch_angle_degrees"] = get_float(row, "branch_angle_degrees", 60.0)
    if not is_blank(row.get("branch_angle_jitter_degrees")):
        params["branch_angle_jitter_degrees"] = get_float(row, "branch_angle_jitter_degrees", 0.0)
    if not is_blank(row.get("allow_occupied_site")):
        params["allow_occupied_site"] = get_bool(row, "allow_occupied_site", False)
    if not is_blank(row.get("require_replace_site")):
        params["require_replace_site"] = get_bool(row, "require_replace_site", False)
    if not is_blank(row.get("allow_replace")):
        params["allow_replace"] = get_bool(row, "allow_replace", False)

    return "compartmentalize", params


def parse_fpp_link_row(row):
    validate_fpp_link_row(row)
    params = base_params(row)
    mode_values = parse_key_value_string(row.get("mode_param", ""))

    params["mode"] = get_str(row, "mode", mode_values.get("mode", "nearest_type")).lower()

    for key, value in mode_values.items():
        if key not in params:
            params[key] = value

    text_keys = [
        "partner_type",
        "target_type",
        "cell_type",
    ]
    numeric_keys = [
        "target_cell_id",
        "partner_cell_id",
        "link_lambda",
        "lambda_distance",
        "target_distance",
        "max_distance",
        "max_search_distance",
        "search_radius",
        "max_links",
        "activation_energy",
        "fpp_activation_energy",
        "max_junctions",
        "max_number_of_junctions",
        "fpp_neighbor_order",
    ]

    for key in text_keys:
        if not is_blank(row.get(key)):
            params[key] = get_str(row, key)
    for key in numeric_keys:
        if not is_blank(row.get(key)):
            params[key] = get_float(row, key)

    return "fpp_link", params


def parse_intracellular_model_row(row):
    validate_intracellular_model_row(row)
    params = base_params(row)
    mode_values = parse_key_value_string(row.get("mode_param", ""))

    params["model"] = get_str(row, "model", get_str(row, "model_name", mode_values.get("model", "")))
    params["action"] = get_str(row, "action", get_str(row, "mode", mode_values.get("action", "advance"))).lower()
    params["sync_inputs"] = get_bool(row, "sync_inputs", str(mode_values.get("sync_inputs", "true")).lower() in {"true", "1", "yes", "y"})
    params["step_model"] = get_bool(row, "step_model", str(mode_values.get("step_model", "true")).lower() in {"true", "1", "yes", "y"})
    params["sync_outputs"] = get_bool(row, "sync_outputs", str(mode_values.get("sync_outputs", "true")).lower() in {"true", "1", "yes", "y"})

    for key in ("inputs", "input_mappings", "outputs", "output_mappings"):
        if not is_blank(row.get(key)):
            params[key] = _parse_json_cell(row.get(key), [] if "output" in key or "input" in key else {})

    for key in ("model_var", "variable", "value", "source", "from", "to", "key", "target_key"):
        if not is_blank(row.get(key)):
            params[key] = parse_dynamic_numeric(row.get(key), row.get(key)) if key == "value" else get_str(row, key)

    return "intracellular_model", params


def parse_subcellular_row(row):
    validate_subcellular_row(row)
    params = base_params(row)
    mode_values = parse_key_value_string(row.get("mode_param", ""))

    params["system"] = get_str(row, "system", get_str(row, "subsystem", mode_values.get("system", "")))
    params["action"] = get_str(row, "action", get_str(row, "mode", mode_values.get("action", "set_stage"))).lower()

    for key, value in mode_values.items():
        if key not in params:
            params[key] = parse_dynamic_numeric(value, value)

    text_keys = [
        "stage",
        "from_stage",
        "to_stage",
        "component",
        "product",
        "variable",
        "path",
        "key",
        "location",
        "from_location",
        "to_location",
    ]
    numeric_keys = [
        "value",
        "amount",
        "delta",
        "count",
        "fraction",
        "probability",
        "rate",
    ]

    for key in text_keys:
        if not is_blank(row.get(key)):
            params[key] = get_str(row, key)
    for key in numeric_keys:
        if not is_blank(row.get(key)):
            params[key] = parse_dynamic_numeric(row.get(key), row.get(key))

    requirements = _parse_mapping_cell(
        row.get("requires", row.get("required_components")),
        default={},
    )
    if requirements:
        params["requires"] = requirements

    if not is_blank(row.get("floor_zero")):
        params["floor_zero"] = get_bool(row, "floor_zero", True)

    return "subcellular", params


def import_intracellular_models_from_csv(path):
    df = pd.read_csv(path)
    models = []
    for i, row in df.iterrows():
        try:
            model_id = get_str(row, "id", get_str(row, "model_id", ""))
            if not model_id:
                raise ValueError("model id is required")
            engine = get_str(row, "engine", "sbml").lower()
            source_kind = get_str(row, "source_kind", "file").lower()
            cell_types = [part.strip() for part in get_str(row, "attach_cell_types", "").split(",") if part.strip()]
            source = {"kind": source_kind}
            if engine == "maboss":
                if source_kind == "inline":
                    source["boolean_network_text"] = get_str(
                        row,
                        "boolean_network_text",
                        get_str(row, "bnd", ""),
                    )
                    source["simulation_configuration_text"] = get_str(
                        row,
                        "simulation_configuration_text",
                        get_str(row, "cfg", ""),
                    )
                else:
                    source["boolean_network_path"] = get_str(
                        row,
                        "boolean_network_path",
                        get_str(row, "bnd_path", get_str(row, "bnd_file", "")),
                    )
                    source["simulation_configuration_path"] = get_str(
                        row,
                        "simulation_configuration_path",
                        get_str(row, "configuration_path", get_str(row, "cfg_path", get_str(row, "cfg_file", ""))),
                    )
            elif source_kind == "inline":
                source["text"] = get_str(row, "source_text", get_str(row, "model_string", ""))
            else:
                source["path"] = get_str(row, "source_path", get_str(row, "path", get_str(row, "model_file", "")))

            models.append({
                "id": model_id,
                "engine": engine,
                "model_name": get_str(row, "model_name", model_id),
                "source": source,
                "attach_to": {"cell_types": cell_types},
                "solver": {"step_size": get_float(row, "step_size", 1.0)},
                "initial_conditions": _parse_json_cell(row.get("initial_conditions"), {}),
                "inputs": _parse_json_cell(row.get("inputs"), []),
                "outputs": _parse_json_cell(row.get("outputs"), []),
            })
        except Exception as exc:
            raise ValueError(f"Error parsing intracellular model row {i}: {exc}")
    return models


def _parse_json_cell(value, default):
    if is_blank(value):
        return default
    parsed = parse_dynamic_numeric(value, None)
    if parsed is not None and not isinstance(parsed, str):
        return parsed
    try:
        return json.loads(str(value))
    except Exception:
        return default


def _parse_list_cell(value, default=None):
    if default is None:
        default = []
    if is_blank(value):
        return list(default)
    parsed = _parse_json_cell(value, None)
    if isinstance(parsed, list):
        return [clean_label(item) for item in parsed if clean_label(item)]
    if isinstance(parsed, dict):
        return [clean_label(key) for key in parsed.keys() if clean_label(key)]
    return [clean_label(part) for part in str(value).split(",") if clean_label(part)]


def _parse_mapping_cell(value, default=None):
    if default is None:
        default = {}
    if is_blank(value):
        return dict(default)
    parsed = _parse_json_cell(value, None)
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        mapping = {}
        for item in parsed:
            if isinstance(item, dict):
                key = item.get("id") or item.get("name") or item.get("component") or item.get("key")
                if key:
                    mapping[clean_label(key)] = item.get("value", item.get("count", item.get("initial_count", 0)))
            elif item:
                mapping[clean_label(item)] = 0
        return mapping

    mapping = {}
    for key, raw in parse_key_value_string(value).items():
        mapping[clean_label(key)] = parse_dynamic_numeric(raw, raw)
    return mapping


def import_subcellular_systems_from_csv(path):
    df = pd.read_csv(path)
    systems = []
    for i, row in df.iterrows():
        try:
            system_id = clean_label(get_str(row, "id", get_str(row, "system_id", get_str(row, "system", ""))))
            if not system_id:
                raise ValueError("system id is required")

            stages = _parse_list_cell(row.get("stages"), [])
            default_stage = clean_label(get_str(row, "default_stage", stages[0] if stages else "none"))
            if stages and default_stage not in stages:
                stages.insert(0, default_stage)

            cell_types = _parse_list_cell(
                row.get("attach_cell_types", row.get("cell_types")),
                [],
            )
            default_counts = _parse_mapping_cell(
                row.get("default_counts", row.get("components")),
                {},
            )
            default_localization = _parse_mapping_cell(
                row.get("default_localization", row.get("localization")),
                {},
            )

            systems.append({
                "id": system_id,
                "scope": get_str(row, "scope", "cell") or "cell",
                "stages": stages,
                "default_stage": default_stage,
                "attach_to": {"cell_types": cell_types},
                "default_counts": default_counts,
                "default_localization": default_localization,
            })
        except Exception as exc:
            raise ValueError(f"Error parsing subcellular system row {i}: {exc}")
    return systems


# =========================
# UNIFIED IMPORTER
# =========================
def import_rules_from_csv(path):
      df = pd.read_csv(path)

      if "behaviour" not in df.columns:
          raise ValueError("CSV must contain a 'behaviour' column")

      rules = []

      for i, row in df.iterrows():
          try:
              behaviour = get_str(row, "behaviour").lower()

              if behaviour == "growth":
                  actual_behaviour, params = parse_growth_row(row)
              elif behaviour == "differentiate":
                  actual_behaviour, params = parse_diff_row(row)
              elif behaviour == "create":
                  actual_behaviour, params = parse_create_row(row)
              elif behaviour == "death":
                  actual_behaviour, params = parse_death_row(row)
              elif behaviour == "secrete/uptake":
                  actual_behaviour, params = parse_secrete_uptake_row(row)
              elif behaviour == "dormancy":
                  actual_behaviour, params = parse_dormancy_row(row)
              elif behaviour == "phagocytosis":
                  actual_behaviour, params = parse_phagocytosis_row(row)
              elif behaviour == "chemotaxis":
                  actual_behaviour, params = parse_chemotaxis_row(row)
              elif behaviour == "force":
                  actual_behaviour, params = parse_force_row(row)
              elif behaviour == "compartmentalize":
                  actual_behaviour, params = parse_compartmentalize_row(row)
              elif behaviour == "fpp_link":
                  actual_behaviour, params = parse_fpp_link_row(row)
              elif behaviour == "intracellular_model":
                  actual_behaviour, params = parse_intracellular_model_row(row)
              elif behaviour == "subcellular":
                  actual_behaviour, params = parse_subcellular_row(row)
              else:
                  print(f"[Warning] Row {i}: Unknown behaviour '{behaviour}', skipping.")
                  continue

              rules.append(build_rule(actual_behaviour, params))

          except Exception as e:
              raise ValueError(f"Error parsing Row {i} (ID: {row.get('id', row.get('rule_id',
  '?'))}): {e}")

      return rules
# =========================
# (Unified Condition Parser)
# =========================

def parse_condition(row):
    """
    parse the csv colnames for condition
    """
    when_type = row.get("when_type")

    if pd.isna(when_type) or str(when_type).strip().upper() == "TRUE":
        return {"condition_type": "TRUE", "params": {}}

    when_type = str(when_type).strip().lower()

    if when_type == "time_window":
        return {
            "condition_type": "TimeWindow",
            "params": {
                "start_mcs": get_dynamic_number(row, "when_start", 0),
                "end_mcs": get_dynamic_number(row, "when_end", float("inf"))
            }
        }

    elif when_type == "probability":
        val = row.get("value")
        if pd.isna(val):
            val = row.get("p")
        return {
            "condition_type": "Probability",
            "params": {"p": parse_dynamic_numeric(val, 0.0)}
        }

    elif when_type in ["threshold", "condition", "state"]:
        reg_type = row.get("regulator_type")

        if pd.isna(reg_type) or str(reg_type).strip() == "":
            reg_type = "Environment"
        else:
            reg_type = str(reg_type).strip()

        cond_params = {
            "operator": str(row["operator"]),
            "threshold": get_dynamic_number(row, "value", 0.0)
        }

        regulator_val = str(row["regulator"]).strip()

        if reg_type == "Environment" or reg_type == "field":
            reg_type = "Environment"
            cond_params["field_name"] = regulator_val
            _attach_environment_sampling_params(row, cond_params)

        elif reg_type in ["Contact", "Distance"]:
            cond_params["target_type"] = regulator_val

        elif reg_type == "Morphology":
            if regulator_val.lower() == "elongation":
                reg_type = "Morphology_Elongation"
            elif regulator_val.lower() in ["specific_surface", "sphericity"]:
                reg_type = "Morphology_SpecificSurface"
        elif reg_type in ["State", "state"]:
            reg_type = "State"
            cond_params["regulator"] = regulator_val

        elif str(reg_type).lower() in {"intracellular", "intracellularstate", "intracellular_state"}:
            reg_type = "IntracellularState"
            cond_params["model"] = get_str(row, "model", get_str(row, "model_name", ""))
            cond_params["variable"] = regulator_val

        elif str(reg_type).lower() in {"subcellular", "subcellularstate", "subcellular_state"}:
            reg_type = "SubcellularState"
            cond_params["system"] = get_str(
                row,
                "when_system",
                get_str(row, "system", get_str(row, "subsystem", "")),
            )
            component = _first_present(row, ["when_component", "component"])
            location = _first_present(row, ["when_location", "location"])
            if not is_blank(component):
                cond_params["component"] = str(component).strip()
            elif not is_blank(location):
                cond_params["location"] = str(location).strip()
            else:
                cond_params["variable"] = regulator_val or get_str(row, "when_variable", "stage")

        return {
            "condition_type": reg_type,
            "params": cond_params
        }

    elif when_type in {"intracellular", "intracellular_state"}:
        variable = get_str(row, "when_variable", get_str(row, "regulator", ""))
        return {
            "condition_type": "IntracellularState",
            "params": {
                "model": get_str(row, "when_model", get_str(row, "model", get_str(row, "model_name", ""))),
                "variable": variable,
                "operator": get_str(row, "operator", ">"),
                "threshold": get_dynamic_number(row, "value", 0.0),
            },
        }

    elif when_type in {"subcellular", "subcellular_state"}:
        params = {
            "system": get_str(row, "when_system", get_str(row, "system", get_str(row, "subsystem", ""))),
            "operator": get_str(row, "operator", "=="),
            "threshold": parse_dynamic_numeric(row.get("value"), row.get("value")),
        }
        component = _first_present(row, ["when_component", "component"])
        location = _first_present(row, ["when_location", "location"])
        if not is_blank(component):
            params["component"] = str(component).strip()
        elif not is_blank(location):
            params["location"] = str(location).strip()
        else:
            params["variable"] = get_str(row, "when_variable", get_str(row, "regulator", "stage"))
        return {"condition_type": "SubcellularState", "params": params}

    else:
        raise ValueError(f"Unknown when_type: {when_type}")


def _attach_environment_sampling_params(row, cond_params):
    sampling_mode = _first_present(row, ["env_sampling_mode", "sampling_mode", "environment_mode"])
    if not is_blank(sampling_mode):
        cond_params["sampling_mode"] = str(sampling_mode).strip()

    radius = _first_present(row, ["env_radius", "sampling_radius"])
    if not is_blank(radius):
        cond_params["radius"] = parse_dynamic_numeric(radius, 1)

    target_type = _first_present(row, ["env_target_type", "sampling_target_type", "contact_target_type"])
    if not is_blank(target_type):
        cond_params["target_type"] = str(target_type).strip()


def _first_present(row, keys):
    for key in keys:
        if key in row and not is_blank(row.get(key)):
            return row.get(key)
    return None
