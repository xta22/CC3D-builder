# condition_evaluator.py
import json
import math
import random
import re
from pathlib import Path
import importlib.util

from cc3d_builder.engine.core.intracellular_state import read_intracellular_value
from cc3d_builder.engine.core.subcellular_state import clean_subcellular_text, read_subcellular_value


ENVIRONMENT_SAMPLING_ALIASES = {
    "": "com",
    "center": "com",
    "centre": "com",
    "cell_center": "com",
    "cell_com": "com",
    "com": "com",
    "cell": "cell_average",
    "cell_avg": "cell_average",
    "cell_average": "cell_average",
    "cell_mean": "cell_average",
    "cell_max": "cell_max",
    "cell_min": "cell_min",
    "boundary": "boundary_average",
    "boundary_avg": "boundary_average",
    "boundary_average": "boundary_average",
    "boundary_mean": "boundary_average",
    "boundary_max": "boundary_max",
    "boundary_min": "boundary_min",
    "contact_boundary": "contact_boundary_average",
    "contact_boundary_avg": "contact_boundary_average",
    "contact_boundary_average": "contact_boundary_average",
    "contact_boundary_mean": "contact_boundary_average",
    "contact_boundary_max": "contact_boundary_max",
    "contact_boundary_min": "contact_boundary_min",
    "radius": "radius_average",
    "radius_avg": "radius_average",
    "radius_average": "radius_average",
    "radius_mean": "radius_average",
    "radius_max": "radius_max",
    "radius_min": "radius_min",
}


def evaluate_single_condition(cond, cell, engine):
    if cell is None:
        cond_type = cond.get("condition_type", cond.get("type"))
        if cond_type == "Environment":
            return False

    cond_type = cond.get("condition_type", cond.get("type"))
    p = cond.get("params", cond)

    if cond_type == "TRUE":
        return True

    # --- Environment Condition ---
    elif cond_type == "Environment":
        field_name = str(p.get("field_name", "") or "").strip()
        operator = p.get("operator", ">")
        threshold = resolve_condition_number(p.get("threshold", p.get("value", 0.0)), 0.0, cell, engine)

        if not field_name:
            print("[Environment Error] field_name missing")
            return False

        try:
            if cell:
                val = sample_environment_value(p, cell, engine)
            else:
                return False
        except Exception as e:
            print(f"[Environment Error] Failed to sample field '{field_name}' at cell {cell.id}: {e}")
            return False

        # logic comparison
        return compare_values(val, operator, threshold)
    # ---------------------------

    elif cond_type in ["time_window", "TimeWindow"]:
        start = resolve_condition_number(p.get("start", p.get("start_mcs", 0)), 0.0, cell, engine)
        end = resolve_condition_number(p.get("end", p.get("end_mcs", float("inf"))), float("inf"), cell, engine)
        return start <= engine.current_mcs < end

    elif cond_type in ["probability", "Probability"]:
        prob = resolve_condition_number(p.get("p", 0), 0.0, cell, engine)
        prob = max(0.0, min(1.0, prob))
        return random.random() < prob

    elif cond_type in ["contact", "Contact"]:
        target_type = p.get("target_type")
        operator = p.get("operator", ">")
        threshold = resolve_condition_number(p.get("threshold", 0.0), 0.0, cell, engine)

        value = engine.get_contact_ratio(cell, target_type)

        return compare_values(value, operator, threshold)

    elif cond_type in ["duration", "Duration"]:
        threshold_mcs = resolve_condition_number(p.get("threshold_mcs", 0), 0.0, cell, engine)
        sub_condition = p.get("sub_condition")

        if sub_condition is None:
            return False

        sub_ok = evaluate_condition(sub_condition, cell, engine)

        if cell is None:
            return False

        engine._ensure_cell_dict(cell)
        internal = cell.dict["_internal"]

        cond_key = json.dumps(sub_condition, sort_keys=True)

        if sub_ok:
            if cond_key not in internal:
                internal[cond_key] = engine.current_mcs

            elapsed = engine.current_mcs - internal[cond_key]
            debug_duration = (
                cond.get("debug")
                or p.get("debug")
                or getattr(engine, "debug_conditions", False)
                or getattr(engine, "debug", False)
            )
            if debug_duration:
                print(
                    f"[Duration] cell={cell.id} mcs={engine.current_mcs} "
                    f"sub_ok={sub_ok} start={internal[cond_key]} elapsed={elapsed} "
                    f"threshold={threshold_mcs}"
                )

            return elapsed >= threshold_mcs
        else:
            if cond_key in internal:
                del internal[cond_key]
            return False

    elif cond_type.startswith("Morphology"):
        indicator = cond_type.split("_")[1] if "_" in cond_type else "volume"
        val = getattr(cell, indicator.lower(), 0.0) # Assuming CC3D cell Object has this attribute

        op = p.get("operator", ">")
        thr = resolve_condition_number(p.get("threshold", 0.0), 0.0, cell, engine)

        return compare_values(val, op, thr)

    elif cond_type == "Custom":
        script_path_str = cond.get("script_path")
        if not script_path_str:
            print("[Custom Error] Script path missing")
            return False

        script_path = Path(script_path_str)

        if not script_path.exists():
            print(f"[Custom Error] Script not found: {script_path}")
            return False

        try:
            spec = importlib.util.spec_from_file_location("custom_mod", script_path)
            if spec is None or spec.loader is None:
                print(f"[Custom Error] Cannot load module from {script_path}")
                return False

            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            return module.validate(cell, engine, p)
        except Exception as e:
            print(f"[Custom Error] Execution failed: {e}")
            return False

    elif cond_type in ["state", "State"]:
        regulator_name = p.get("regulator", "").strip()
        operator = p.get("operator", "==")
        threshold = p.get("threshold", 0.0)

        if regulator_name == "dormant":
            val = cell.dict.get("dormant", False)
            threshold_bool = str(threshold).lower() in ["true", "1", "yes"]
            return val == threshold_bool

        elif regulator_name == "mcs_since_birth":
            val = cell.dict.get("mcs_since_birth", 0)

        else:
            if hasattr(engine, "_frequency_state_value"):
                val = engine._frequency_state_value(cell, regulator_name)
            else:
                val = cell.dict.get(regulator_name, 0.0)

        threshold = resolve_condition_number(threshold, 0.0, cell, engine)

        return compare_values(val, operator, threshold)

    elif cond_type in {"IntracellularState", "intracellular_state"}:
        if cell is None:
            return False
        model_name = str(p.get("model") or p.get("model_name") or "").strip()
        variable = str(p.get("variable") or p.get("model_var") or p.get("var") or "").strip()
        operator = p.get("operator", ">")
        raw_threshold = p.get("threshold", p.get("value", 0.0))
        value = read_intracellular_value(cell, model_name, variable, default=0.0)
        threshold = _boolean_threshold(raw_threshold) if isinstance(value, bool) else resolve_condition_number(raw_threshold, 0.0, cell, engine)
        return compare_values(value, operator, threshold)

    elif cond_type in {"SubcellularState", "subcellular_state"}:
        if cell is None:
            return False
        system = clean_subcellular_text(p.get("system") or p.get("subsystem"))
        variable = clean_subcellular_text(p.get("variable") or p.get("path") or p.get("key") or "stage")
        if p.get("component"):
            variable = f"components.{clean_subcellular_text(p.get('component'))}"
        elif p.get("location"):
            variable = f"localization.{clean_subcellular_text(p.get('location'))}"
        operator = p.get("operator", "==")
        raw_threshold = p.get("threshold", p.get("value", 0.0))
        value = read_subcellular_value(cell, system, variable, default=0.0)
        if isinstance(value, bool):
            threshold = _boolean_threshold(raw_threshold)
        elif isinstance(value, (int, float)):
            threshold = resolve_condition_number(raw_threshold, 0.0, cell, engine)
        else:
            threshold = clean_subcellular_text(raw_threshold)
        return compare_values(value, operator, threshold)

    return False


def compare_values(value, operator, threshold):
    try:
        left = float(value)
        right = float(threshold)
    except (TypeError, ValueError):
        left = value
        right = threshold

    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    return False


def _boolean_threshold(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def resolve_condition_number(value, default, cell, engine):
    if value in (None, ""):
        return float(default)

    if isinstance(value, bool):
        return float(value)

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        if "model" in value and "parameters" in value and hasattr(engine, "_solve_physical_model"):
            try:
                return float(engine._solve_physical_model(value, cell))
            except Exception as exc:
                print(f"[Condition] Physical model evaluation failed: {exc}")
                return float(default)
        return float(default)

    text = str(value).strip()
    if text.lower() in {"inf", "+inf", "infinity", "+infinity"}:
        return float("inf")

    try:
        return float(text)
    except ValueError:
        pass

    expr = text
    for key in re.findall(r"\{([^{}]+)\}", text):
        state_value = _state_value(cell, engine, key)
        expr = expr.replace(f"{{{key}}}", str(state_value))

    try:
        context = _condition_context(cell, engine)
        return float(eval(expr, {"__builtins__": None}, context))
    except Exception as exc:
        print(f"[Condition] Dynamic numeric evaluation failed for {value!r}: {exc}")
        return float(default)


def sample_environment_value(params, cell, engine):
    field_name = str(params.get("field_name", "")).strip()
    field = getattr(engine.field, field_name, None)

    if field is None:
        print(f"[Environment Error] Field '{field_name}' not found. Available: {dir(engine.field)}")
        return 0.0

    mode = _environment_sampling_mode(params.get("sampling_mode", params.get("environment_mode", "com")))

    if mode == "com":
        return _sample_field_at(field, cell.xCOM, cell.yCOM, cell.zCOM, engine)

    if mode.startswith("radius_"):
        radius = max(0, int(round(resolve_condition_number(params.get("radius", params.get("sampling_radius", 1)), 1, cell, engine))))
        samples = _radius_field_samples(field, cell, engine, radius)
        return _aggregate_samples(samples, mode.split("_", 1)[1])

    if mode.startswith("contact_boundary_"):
        target_type = params.get("target_type") or params.get("contact_target_type") or params.get("sampling_target_type")
        target_type_id = _cell_type_id(engine, target_type)
        if target_type_id is None:
            print(f"[Environment Error] contact_boundary mode needs a valid target_type, got: {target_type}")
            return 0.0
        get_contact_ratio = getattr(engine, "get_contact_ratio", None)
        if callable(get_contact_ratio) and get_contact_ratio(cell, target_type) <= 0:
            return 0.0
        pixels = _cell_pixels(engine, cell)
        if not pixels:
            _debug_environment(engine, params, f"sampling_mode={mode} requires cell pixels; falling back to COM")
            return _sample_field_at(field, cell.xCOM, cell.yCOM, cell.zCOM, engine)
        samples = [
            _sample_field_at(field, x, y, z, engine)
            for x, y, z in pixels
            if _has_neighbor_type(engine, x, y, z, target_type_id)
        ]
        return _aggregate_samples(samples, mode.rsplit("_", 1)[1])

    pixels = _cell_pixels(engine, cell)
    if not pixels:
        _debug_environment(engine, params, f"sampling_mode={mode} requires cell pixels; falling back to COM")
        return _sample_field_at(field, cell.xCOM, cell.yCOM, cell.zCOM, engine)

    if mode.startswith("cell_"):
        samples = [_sample_field_at(field, x, y, z, engine) for x, y, z in pixels]
        return _aggregate_samples(samples, mode.split("_", 1)[1])

    if mode.startswith("boundary_"):
        samples = [
            _sample_field_at(field, x, y, z, engine)
            for x, y, z in pixels
            if _is_boundary_pixel(engine, cell, x, y, z)
        ]
        return _aggregate_samples(samples, mode.split("_", 1)[1])

    return _sample_field_at(field, cell.xCOM, cell.yCOM, cell.zCOM, engine)


def _environment_sampling_mode(raw_mode):
    return ENVIRONMENT_SAMPLING_ALIASES.get(str(raw_mode or "com").strip().lower(), "com")


def _sample_field_at(field, x, y, z, engine):
    xi = _clamp_index(x, getattr(getattr(engine, "dim", None), "x", None))
    yi = _clamp_index(y, getattr(getattr(engine, "dim", None), "y", None))
    zi = _clamp_index(z, getattr(getattr(engine, "dim", None), "z", None))
    try:
        return float(field[xi, yi, zi])
    except Exception:
        return 0.0


def _radius_field_samples(field, cell, engine, radius):
    cx = _clamp_index(cell.xCOM, getattr(getattr(engine, "dim", None), "x", None))
    cy = _clamp_index(cell.yCOM, getattr(getattr(engine, "dim", None), "y", None))
    cz = _clamp_index(cell.zCOM, getattr(getattr(engine, "dim", None), "z", None))

    x_max = getattr(getattr(engine, "dim", None), "x", cx + radius + 1)
    y_max = getattr(getattr(engine, "dim", None), "y", cy + radius + 1)
    z_max = getattr(getattr(engine, "dim", None), "z", 1)
    radius_sq = radius * radius
    z_values = [cz] if z_max <= 1 else range(max(0, cz - radius), min(z_max - 1, cz + radius) + 1)

    samples = []
    for x in range(max(0, cx - radius), min(x_max - 1, cx + radius) + 1):
        for y in range(max(0, cy - radius), min(y_max - 1, cy + radius) + 1):
            for z in z_values:
                if (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 <= radius_sq:
                    samples.append(_sample_field_at(field, x, y, z, engine))
    return samples


def _aggregate_samples(samples, method):
    if not samples:
        return 0.0
    if method == "max":
        return max(samples)
    if method == "min":
        return min(samples)
    return sum(samples) / len(samples)


def _cell_pixels(engine, cell):
    for method_name in ("get_cell_pixel_list", "getCellPixelList"):
        method = getattr(engine, method_name, None)
        if method is None:
            continue
        try:
            return [_pixel_coords(item) for item in method(cell) if _pixel_coords(item) is not None]
        except Exception:
            continue
    return []


def _pixel_coords(item):
    pixel = getattr(item, "pixel", item)
    try:
        return int(pixel.x), int(pixel.y), int(pixel.z)
    except Exception:
        try:
            return int(pixel[0]), int(pixel[1]), int(pixel[2] if len(pixel) > 2 else 0)
        except Exception:
            return None


def _is_boundary_pixel(engine, cell, x, y, z):
    for nx, ny, nz in _neighbor_sites(engine, x, y, z):
        try:
            neighbor = engine.cell_field[nx, ny, nz]
        except Exception:
            return True
        if neighbor is None or getattr(neighbor, "id", None) != getattr(cell, "id", None):
            return True
    return False


def _has_neighbor_type(engine, x, y, z, target_type_id):
    for nx, ny, nz in _neighbor_sites(engine, x, y, z):
        try:
            neighbor = engine.cell_field[nx, ny, nz]
        except Exception:
            continue
        if neighbor is not None and getattr(neighbor, "type", None) == target_type_id:
            return True
    return False


def _neighbor_sites(engine, x, y, z):
    dim = getattr(engine, "dim", None)
    x_max = getattr(dim, "x", x + 2)
    y_max = getattr(dim, "y", y + 2)
    z_max = getattr(dim, "z", 1)
    offsets = [(-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0)]
    if z_max > 1:
        offsets.extend([(0, 0, -1), (0, 0, 1)])

    for dx, dy, dz in offsets:
        nx, ny, nz = x + dx, y + dy, z + dz
        if 0 <= nx < x_max and 0 <= ny < y_max and 0 <= nz < z_max:
            yield nx, ny, nz


def _cell_type_id(engine, type_name):
    if not type_name:
        return None
    return getattr(engine, str(type_name).strip().upper(), None)


def _clamp_index(value, upper):
    try:
        idx = int(round(float(value)))
    except (TypeError, ValueError):
        idx = 0
    if upper is None or upper <= 1:
        return 0
    return max(0, min(int(upper) - 1, idx))


def _state_value(cell, engine, key):
    if hasattr(engine, "_frequency_state_value"):
        return engine._frequency_state_value(cell, key)
    if key == "mcs":
        return float(getattr(engine, "current_mcs", 0))
    if cell is None:
        return 0.0
    try:
        return float(cell.dict.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _condition_context(cell, engine):
    if hasattr(engine, "_frequency_context"):
        return engine._frequency_context(cell, "state", 0.0)

    context = {"math": math, "mcs": float(getattr(engine, "current_mcs", 0))}
    if cell is not None:
        for key, value in getattr(cell, "dict", {}).items():
            if isinstance(value, (int, float, bool)):
                context[key] = float(value)
    return context


def _debug_environment(engine, params, message):
    if params.get("debug") or getattr(engine, "debug_conditions", False) or getattr(engine, "debug", False):
        print(f"[Environment] {message}")

def evaluate_condition(block, cell, engine):
    full_type = block.get("condition_type", "")

    if full_type.startswith("Logic_"):
        actual_logic = full_type.split("_")[1].upper()
        conditions = block.get("params", {}).get("conditions", [])

        if actual_logic == "AND":
            for cond in conditions:
                if not evaluate_condition(cond, cell, engine):
                    return False
            return True
        if actual_logic == "OR":
            for cond in conditions:
                if evaluate_condition(cond, cell, engine):
                    return True
            return False
        if actual_logic == "NOT":
            return not evaluate_condition(conditions[0], cell, engine) if conditions else False
    return evaluate_single_condition(block, cell, engine)
