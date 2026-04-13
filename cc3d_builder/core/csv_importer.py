import pandas as pd

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

# =========================
# PARSER
# =========================
def parse_growth_row(row):

    validate_growth_row(row)

    params = {}

    params["id"] = str(row["id"])
    params["target"] = None if pd.isna(row["target"]) else row["target"]

    # condition
    params["when"] = parse_condition(row)

    model = row["model"]

    if model == "linear":
        parameters = {"alpha": float(row["alpha"])}

    elif model == "hill":
        parameters = {
            "y_min": float(row["y_min"]),
            "y_max": float(row["y_max"]),
            "k": float(row["k"]),
            "n": float(row["n"])
        }

    elif model == "expression":
        parameters = {"expression": str(row["expression"])}

    else:
        raise ValueError(f"Unknown model: {model}")

    params["apply"] = {
        "model": model,
        "regulator": row["regulator"],
        "parameters": parameters
    }

    params["once"] = str(row["once"]).lower() == "true"
    params["debug"] = str(row["debug"]).lower() == "true"

    return "growth", params


def parse_create_row(row):
    validate_create_row(row)

    params = {}
    params["id"] = str(row["id"])
    params["target"] = None if pd.isna(row["target"]) else row["target"]

    # condition
    params["when"] = parse_condition(row)

    # distribution
    dist_type = row["dist_type"]
    dist = {"type": dist_type}

    if dist_type == "cluster":
        dist["center"] = [float(row["center_x"]), float(row["center_y"])]
        dist["radius"] = float(row["radius"])

    elif dist_type == "stripe":
            dist["direction"] = row["direction"]
            if row["direction"] == "vertical":
                dist["x"] = float(row["x"])
                dist["y_start"] = float(row["y_start"])
                
                if not pd.isna(row.get("y_gap")):
                    dist["y_gap"] = float(row["y_gap"])
                elif not pd.isna(row.get("y_end")):
                    dist["y_end"] = float(row["y_end"])
            else:
                dist["y"] = float(row["y"])
                dist["x_start"] = float(row["x_start"])
                if not pd.isna(row.get("x_gap")):
                    dist["x_gap"] = float(row["y_gap"])
                elif not pd.isna(row.get("x_end")):
                    dist["yxend"] = float(row["x_end"])

    params["distribution"] = dist

    params["once"] = str(row["once"]).lower() == "true"
    params["debug"] = str(row["debug"]).lower() == "true"

    return "create", params


def parse_diff_row(row):
    validate_diff_row(row)

    params = {}
    params["id"] = str(row["id"])
    params["target"] = row["target"]

    # condition
    params["when"] = parse_condition(row)

    mode = row["mode"]
    params["mode"] = mode

    if mode == "type_switch":
        params["new_type"] = row["new_type"]

    else:  # division
        params["parent_type"] = row["parent_type"]
        params["child_type"] = row["child_type"]
        params["volume_ratio"] = float(row["volume_ratio"])

        placement = {"type": row["placement_type"]}

        if placement["type"] == "angle":
            placement["angle_deg"] = float(row["angle_deg"])

        elif placement["type"] == "vector":
            placement["dx"] = float(row["dx"])
            placement["dy"] = float(row["dy"])

        params["placement"] = placement

    params["once"] = str(row["once"]).lower() == "true"
    params["debug"] = str(row["debug"]).lower() == "true"

    return "differentiate", params

# =========================
# UNIFIED IMPORTER
# =========================
def import_rules_from_csv(path):
    import pandas as pd
    df = pd.read_csv(path)

    if "behaviour" not in df.columns:
        raise ValueError("CSV must contain a 'behaviour' column (e.g., growth, differentiate, create)")

    results = []

    for i, row in df.iterrows():
        try:
            behaviour = str(row["behaviour"]).strip().lower()

            if behaviour == "growth":
                _, params = parse_growth_row(row)
                results.append(("growth", params))

            elif behaviour == "differentiate":
                _, params = parse_diff_row(row)
                results.append(("differentiate", params))

            elif behaviour == "create":
                _, params = parse_create_row(row)
                results.append(("create", params))

            else:
                print(f"[Warning] Row {i}: Unknown behaviour '{behaviour}', skipping.")

        except Exception as e:
            raise ValueError(f"Error parsing Row {i} (ID: {row.get('id', '?')}): {e}")

    return results
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
                "start_mcs": int(row["when_start"]),
                "end_mcs": int(row["when_end"])
            }
        }

    elif when_type == "probability":
        val = row.get("value")
        if pd.isna(val):
            val = row.get("p") 
        return {
            "condition_type": "Probability",
            "params": {"p": float(val)}
        }

    elif when_type in ["threshold", "condition", "state"]:
        reg_type = row.get("regulator_type")

        if pd.isna(reg_type) or str(reg_type).strip() == "":
            reg_type = "Environment"
        else:
            reg_type = str(reg_type).strip()

        cond_params = {
            "operator": str(row["operator"]),
            "threshold": float(row["value"])
        }

        regulator_val = str(row["regulator"]).strip()

        if reg_type == "Environment" or reg_type == "field":
            reg_type = "Environment" 
            cond_params["field_name"] = regulator_val
            
        elif reg_type in ["Contact", "Distance"]:
            cond_params["target_type"] = regulator_val
            
        elif reg_type == "Morphology":
            if regulator_val.lower() == "elongation":
                reg_type = "Morphology_Elongation"
            elif regulator_val.lower() in ["specific_surface", "sphericity"]:
                reg_type = "Morphology_SpecificSurface"

        return {
            "condition_type": reg_type,
            "params": cond_params
        }

    else:
        raise ValueError(f"Unknown when_type: {when_type}")