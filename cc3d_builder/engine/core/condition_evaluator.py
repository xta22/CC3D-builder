import json
import random
from pathlib import Path
import importlib.util

def evaluate_single_condition(cond, cell, engine):
    cond_type = cond.get("condition_type", cond.get("type"))
    p = cond.get("params", cond)

    if cond_type == "TRUE":
        return True

    # --- Environment Condition ---
    elif cond_type == "Environment":
        field_name = p.get("field_name")
        operator = p.get("operator", ">")
        threshold = float(p.get("threshold", 0.0))

        if not field_name:
            print("[Environment Error] field_name missing")
            return False

        # get field value from enging
        try:
            field = getattr(engine.field, field_name)
            val = field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]
        except AttributeError:
            print(f"[Environment Error] Field {field_name} not found in engine.field")
            return False

        # logic comparison
        if operator == ">": return val > threshold
        elif operator == ">=": return val >= threshold
        elif operator == "<": return val < threshold
        elif operator == "<=": return val <= threshold
        elif operator == "==": return val == threshold
        return False
    # ---------------------------

    elif cond_type in ["time_window", "TimeWindow"]:
        start = p.get("start", p.get("start_mcs", 0))
        end = p.get("end", p.get("end_mcs", float("inf")))
        return start <= engine.current_mcs < end

    elif cond_type in ["probability", "Probability"]:
        prob = p.get("p", 0)
        return random.random() < prob

    elif cond_type in ["contact", "Contact"]:
        target_type = p.get("target_type")
        operator = p.get("operator", ">")
        threshold = p.get("threshold", 0.0)

        value = engine.get_contact_ratio(cell, target_type)

        if operator == ">":
            return value > threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<":
            return value < threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        return False

    elif cond_type in ["duration", "Duration"]:
        threshold_mcs = p.get("threshold_mcs", 0)
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
        thr = p.get("threshold", 0.0)
        
        ops = {">": lambda a,b: a>b, "<": lambda a,b: a<b, "==": lambda a,b: a==b, 
            ">=": lambda a,b: a>=b, "<=": lambda a,b: a<=b}
        return ops.get(op, lambda a,b: False)(val, thr)

    
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
        
    return False

def evaluate_condition(block, cell, engine):
    full_type = block.get("condition_type", "")
    
    if full_type.startswith("Logic_"):
        actual_logic = full_type.split("_")[1].upper() 
        conditions = block.get("params", {}).get("conditions", [])
        
        results = [evaluate_condition(cond, cell, engine) for cond in conditions]
        
        if actual_logic == "AND": return all(results)
        if actual_logic == "OR":  return any(results)
        if actual_logic == "NOT": return not results[0] if results else False
    return evaluate_single_condition(block, cell, engine)