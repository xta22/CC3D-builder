# rule_builder.py
def _is_blank(val):
    if val is None:
        return True
    try:
        if val != val:  # NaN check without importing pandas/numpy.
            return True
    except Exception:
        pass
    return str(val).strip() == ""


def _safe_number(val, default=0.0):
    if isinstance(val, (dict, list)):
        return val
    if _is_blank(val):
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val

    text = str(val).strip()
    try:
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
        return float(text)
    except (ValueError, TypeError):
        return val


def _safe_bool(val, default=False):
    if _is_blank(val):
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    return str(val).strip().lower() in {"true", "1", "yes", "y"}


def _clean_label(val):
    text = str(val or "").strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


def _clean_frequency(val):
    if isinstance(val, dict):
        return val
    return _safe_number(val, 1)


def _reject_deprecated_wrappers(params):
    if "apply" in params:
        raise ValueError("Deprecated rule wrapper 'apply' is not supported; pass flat case fields directly")


def _merge_model_builder_parameters(params):
    """
    Flatten the current model_builder payload shape used by growth only.

    This is not rule-schema compatibility: strict case output still exposes
    physical parameters directly as flat case keys.
    """
    merged = dict(params)
    nested = merged.pop("parameters", None)
    if isinstance(nested, dict):
        merged.update(nested)
    return merged


def _contact_list(val):
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    if _is_blank(val):
        return []
    return [part.strip() for part in str(val).split(",") if part.strip()]


def _flatten_growth(params):
    data = _merge_model_builder_parameters(params)
    model = str(data.get("model", "")).strip().lower()

    if model == "linear":
        return {
            "model": "linear",
            "regulator": data.get("regulator"),
            "alpha": _safe_number(data.get("alpha", 0.0)),
        }

    if model == "hill":
        return {
            "model": "hill",
            "regulator": data.get("regulator"),
            "y_min": _safe_number(data.get("y_min", 0.0)),
            "y_max": _safe_number(data.get("y_max", 1.0)),
            "K": _safe_number(data.get("K", data.get("k", 1.0))),
            "n": _safe_number(data.get("n", 2.0)),
        }

    if model == "expression":
        return {
            "model": "expression",
            "regulator": data.get("regulator"),
            "expression": data.get("expression", ""),
        }

    raise ValueError(f"Unsupported growth model: {model}")


def _flatten_differentiate(params):
    data = params
    mode = data.get("mode")

    if mode == "type_switch":
        return {
            "mode": "type_switch",
            "new_type": data["new_type"],
        }

    if mode == "division":
        return {
            "mode": "division",
            "parent_type": data["parent_type"],
            "child_type": data["child_type"],
            "volume_ratio": _safe_number(data.get("volume_ratio", 0.5)),
            "inheritance_strategy": data.get("inheritance_strategy", "total"),
            "state_key": data.get("state_key", "division_count"),
            "placement": data.get("placement", {"type": "random"}),
        }

    raise ValueError("Invalid differentiate mode")


def _flatten_create(params):
    data = params
    return {
        "cell_type": data["cell_type"],
        "count": _safe_number(data.get("count", 1)),
        "distribution": data.get("distribution", {"type": "random"}),
    }


def _flatten_death(params):
    data = params
    mode = str(data.get("mode", "apoptosis")).strip().lower()

    if mode == "apoptosis":
        return {
            "mode": "apoptosis",
            "model": "shrink_model",
            "shrink_rate": _safe_number(data.get("shrink_rate", 0.95)),
            "terminal_volume": _safe_number(data.get("terminal_volume", 0.0)),
            "color_change": data.get("color_change", "grey"),
        }

    if mode == "necrosis":
        fields = data.get("fields", [])
        if not fields:
            release_field = data.get("release_field")
            if release_field and release_field != "None":
                fields = [{
                    "field_name": release_field,
                    "amount": _safe_number(data.get("release_amount", 50.0)),
                }]

        return {
            "mode": "necrosis",
            "model": "swell_model",
            "swell_rate": _safe_number(data.get("swell_rate", 1.05)),
            "max_target_volume": _safe_number(data.get("max_target_volume", 150.0)),
            "post_burst_shrink_rate": _safe_number(data.get("post_burst_shrink_rate", 0.8)),
            "fields": fields,
            "color_change": data.get("color_change", "grey"),
        }

    raise ValueError(f"Invalid death mode: {mode}")


def _flatten_secrete_uptake(params):
    data = params
    field_name = data.get("field_name")
    if not field_name:
        raise ValueError("Secretion/Uptake behaviour requires field_name")

    return {
        "field_name": field_name,
        "secret_mode": data.get("secret_mode", "secreteInsideCell"),
        "amount": _safe_number(data.get("amount", 1.0)),
        "relative_uptake": _safe_number(data.get("relative_uptake", 0.0)),
        "contact_types": _contact_list(data.get("contact_types", [])),
        "total_count": _safe_bool(data.get("total_count", False)),
    }


def _flatten_dormancy(params):
    data = params
    action = str(data.get("action", "dormant")).strip().lower()
    action = {
        "activate": "dormant",
        "dormant": "dormant",
        "deactivate": "reactivate",
        "reactivate": "reactivate",
    }.get(action, action)
    return {"action": action}


def _flatten_phagocytosis(params):
    data = params
    return {
        "phago_mode": data.get("phago_mode", "engulfment"),
        "target_cell_type": data.get("target_cell_type", "?"),
        "eating_rate": _safe_number(data.get("eating_rate", 2.0)),
        "leak_field": data.get("leak_field", "None"),
        "leak_amount": _safe_number(data.get("leak_amount", 0.0)),
    }


def _flatten_chemotaxis(params):
    data = params
    payload = {
        "mode": "chemotaxis",
        "field_name": data.get("field_name", "ATTR"),
        "lambda": _safe_number(data.get("lambda", 20.0)),
        "formula": data.get("formula", "Standard"),
        "coef": _safe_number(data.get("coef")) if data.get("coef") is not None else None,
        "target_strategy": data.get("target_strategy", "break"),
        "mode_param": data.get("mode_param", ""),
    }

    for key in ["target_cell_id", "target_x", "target_y", "target_z"]:
        if data.get(key) is not None:
            payload[key] = _safe_number(data.get(key))

    return payload


def _flatten_force(params):
    data = params
    mode = str(data.get("mode", "vector")).strip().lower()

    payload = {
        "mode": mode,
        "force": _safe_number(data.get("force", data.get("magnitude", 1.0)), 1.0),
        "persist": _safe_bool(data.get("persist", False), False),
        "decay": _safe_number(data.get("decay", 1.0), 1.0),
    }

    optional_keys = [
        "dx", "dy", "dz",
        "x", "y", "z",
        "target_x", "target_y", "target_z",
        "target_cell_id",
        "target_type", "cell_type", "target_cell_type",
        "field_name", "field",
        "gradient_step", "step",
        "vector_prefix",
    ]
    for key in optional_keys:
        if key in data and not _is_blank(data.get(key)):
            payload[key] = _safe_number(data.get(key)) if key not in {
                "target_type", "cell_type", "target_cell_type", "field_name", "field", "vector_prefix"
            } else data.get(key)

    return payload


def _flatten_compartmentalize(params):
    data = params
    payload = {
        "action": str(data.get("action", "extend_chain")).strip().lower(),
        "segment_type": data.get("segment_type"),
        "tip_type": data.get("tip_type"),
        "direction_mode": str(data.get("direction_mode", "stored_vector")).strip().lower(),
        "site_selection_mode": str(data.get("site_selection_mode", "empty_first")).strip().lower(),
        "extension_interval": _safe_number(data.get("extension_interval", 1), 1),
        "step_length": _safe_number(data.get("step_length", 1.0), 1.0),
        "max_length": _safe_number(data.get("max_length", 0), 0),
        "search_radius": _safe_number(data.get("search_radius", 3), 3),
        "direction_noise": _safe_number(data.get("direction_noise", data.get("angle_noise", 0.0)), 0.0),
        "allow_occupied_site": _safe_bool(data.get("allow_occupied_site", data.get("allow_replace", False)), False),
        "require_replace_site": _safe_bool(data.get("require_replace_site", False), False),
        "use_fpp_link": _safe_bool(data.get("use_fpp_link", False), False),
        "link_lambda": _safe_number(data.get("link_lambda", data.get("lambda_distance", 10.0)), 10.0),
        "target_distance": _safe_number(data.get("target_distance", 0.0), 0.0),
        "max_distance": _safe_number(data.get("max_distance", 0.0), 0.0),
        "branch_probability": _safe_number(data.get("branch_probability", 1.0), 1.0),
        # Compartmentalize-specific control fields
        "start_with_tip": _safe_bool(data.get("start_with_tip", True), True),
        "compartment_single_extend_per_branch": _safe_bool(data.get("compartment_single_extend_per_branch", False), False),
        "compartment_can_extend": _safe_bool(data.get("compartment_can_extend", False), False),
        "max_active_tips_per_cluster": _safe_number(data.get("max_active_tips_per_cluster", 1), 1),
        "single_tip_per_cluster": _safe_bool(data.get("single_tip_per_cluster", True), True),
        "single_branch_per_cluster": _safe_bool(data.get("single_branch_per_cluster", False), False),
        "single_branch_selection_mode": (data.get("single_branch_selection_mode") or "random"),
        "max_branches_per_segment": _safe_number(data.get("max_branches_per_segment", 3), 3),
        "max_branch_length": _safe_number(data.get("max_branch_length", data.get("max_length", 6)), 6),
        "branch_angle_degrees": _safe_number(data.get("branch_angle_degrees", 60.0), 60.0),
        "branch_angle_jitter_degrees": _safe_number(data.get("branch_angle_jitter_degrees", 0.0), 0.0),
    }

    optional_keys = [
        "cell_type",
        "dx", "dy", "dz",
        "x", "y", "z",
        "target_x", "target_y", "target_z",
        "field_name", "field",
        "gradient_step",
        "internal_contact_energy",
        "internal_neighbor_order",
        "replace_target_types",
        "replace_types",
        "target_types",
        "target_type",
    ]
    for key in optional_keys:
        if key in data and not _is_blank(data.get(key)):
            payload[key] = _safe_number(data.get(key)) if key not in {
                "cell_type", "field_name", "field",
                "replace_target_types", "replace_types", "target_types", "target_type",
            } else data.get(key)

    if _is_blank(payload.get("segment_type")) and not _is_blank(payload.get("cell_type")):
        payload["segment_type"] = payload.get("cell_type")
    if _is_blank(payload.get("tip_type")):
        payload["tip_type"] = payload.get("segment_type")

    return payload


def _flatten_fpp_link(params):
    data = params
    payload = {
        "mode": str(data.get("mode", "nearest_type")).strip().lower(),
        "link_lambda": _safe_number(data.get("link_lambda", data.get("lambda_distance", 10.0)), 10.0),
        "target_distance": _safe_number(data.get("target_distance", 0.0), 0.0),
        "max_distance": _safe_number(data.get("max_distance", 0.0), 0.0),
        "max_search_distance": _safe_number(data.get("max_search_distance", data.get("search_radius", 0.0)), 0.0),
        "max_links": _safe_number(data.get("max_links", 1), 1),
    }

    optional_keys = [
        "partner_type",
        "target_type",
        "cell_type",
        "target_cell_id",
        "partner_cell_id",
        "activation_energy",
        "fpp_activation_energy",
        "max_junctions",
        "max_number_of_junctions",
        "fpp_neighbor_order",
    ]
    for key in optional_keys:
        if key in data and not _is_blank(data.get(key)):
            payload[key] = _safe_number(data.get(key)) if key not in {
                "partner_type", "target_type", "cell_type"
            } else data.get(key)

    return payload


def _flatten_intracellular_model(params):
    data = params
    model_name = data.get("model") or data.get("model_name")
    if _is_blank(model_name):
        raise ValueError("intracellular_model behaviour requires model or model_name")

    action = str(data.get("action", "advance")).strip().lower()
    payload = {
        "model": str(model_name).strip(),
        "action": action,
        "sync_inputs": _safe_bool(data.get("sync_inputs", True), True),
        "step_model": _safe_bool(data.get("step_model", True), True),
        "sync_outputs": _safe_bool(data.get("sync_outputs", True), True),
    }

    for key in ("inputs", "input_mappings", "outputs", "output_mappings"):
        if key in data and not _is_blank(data.get(key)):
            payload[key] = data.get(key)

    for key in ("model_var", "variable", "value", "source", "from", "to", "key", "target_key"):
        if key in data and not _is_blank(data.get(key)):
            payload[key] = data.get(key)

    return payload


def _flatten_subcellular(params):
    data = params
    system = data.get("system") or data.get("subsystem")
    if _is_blank(system):
        raise ValueError("subcellular behaviour requires system or subsystem")

    action = str(data.get("action", "set_stage")).strip().lower()
    payload = {
        "system": _clean_label(system),
        "action": action,
    }

    optional_keys = (
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
        "value",
        "amount",
        "delta",
        "count",
        "fraction",
        "probability",
        "rate",
        "requires",
        "required_components",
        "floor_zero",
    )
    for key in optional_keys:
        if key in data and not _is_blank(data.get(key)):
            value = data.get(key)
            if key in {
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
            }:
                value = _clean_label(value)
            elif key in {"requires", "required_components"} and isinstance(value, dict):
                value = {_clean_label(component): amount for component, amount in value.items()}
            payload[key] = value

    return payload


def _flatten_custom_script(params):
    data = params
    excluded = {
        "id",
        "rule_id",
        "target",
        "when",
        "frequency",
        "order",
        "once",
        "debug",
        "manual_types",
        "parameters",
    }
    return {key: value for key, value in data.items() if key not in excluded}


def build_rule(behaviour, params):
    _reject_deprecated_wrappers(params)

    behaviour = str(behaviour).strip().lower()
    if behaviour == "secrete_uptake":
        behaviour = "secrete/uptake"

    builders = {
        "growth": _flatten_growth,
        "differentiate": _flatten_differentiate,
        "create": _flatten_create,
        "death": _flatten_death,
        "secrete/uptake": _flatten_secrete_uptake,
        "dormancy": _flatten_dormancy,
        "phagocytosis": _flatten_phagocytosis,
        "chemotaxis": _flatten_chemotaxis,
        "force": _flatten_force,
        "compartmentalize": _flatten_compartmentalize,
        "fpp_link": _flatten_fpp_link,
        "intracellular_model": _flatten_intracellular_model,
        "subcellular": _flatten_subcellular,
        "custom_script": _flatten_custom_script,
    }

    if behaviour not in builders:
        raise ValueError(f"Unsupported behaviour: {behaviour}")

    rule_id = params.get("id", params.get("rule_id"))
    if _is_blank(rule_id):
        raise ValueError("Rule id is required")

    when = params.get("when", {"condition_type": "TRUE", "params": {}})
    case_payload = builders[behaviour](params)

    rule = {
        "id": str(rule_id),
        "target": params.get("target"),
        "behaviour": behaviour,
        "cases": [{"when": when, **case_payload}],
        "frequency": _clean_frequency(params.get("frequency", 1)),
        "once": _safe_bool(params.get("once", False)),
        "debug": _safe_bool(params.get("debug", False)),
    }

    if not _is_blank(params.get("order")):
        try:
            rule["order"] = float(params.get("order"))
        except (TypeError, ValueError):
            rule["order"] = params.get("order")

    return rule
