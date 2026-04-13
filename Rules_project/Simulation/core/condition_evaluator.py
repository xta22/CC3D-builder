import json
import random
import os
import importlib.util

'''
def evaluate_single_condition(cond, cell, engine):
    # 1. Unified extraction of types and parameter pools
    cond_type = cond.get("condition_type", cond.get("type"))
    params = cond.get("params", cond) 
    
    if cond_type == "TRUE":
        return True

    if cond_type == "threshold":
        regulator = params.get("regulator")
        operator = params.get("operator")
        value = params.get("value")
        reg_type = params.get("regulator_type", "field")

        if reg_type == "field":
            if cell is None:
                print(f"[Warning] 'field' threshold requires a cell instance. Skipping.")
                return False
            
            field = getattr(engine.field, regulator, None)
            if field is None:
                return False
            
            A = field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]

        elif reg_type == "celltype":
            reg_id = getattr(engine, regulator.upper(), None)
            if reg_id is None: return False
            A = len(engine.cell_list_by_type(reg_id))
        else:
            return False

        ops = {
            ">": lambda x, y: x > y,
            "<": lambda x, y: x < y,
            ">=": lambda x, y: x >= y,
            "<=": lambda x, y: x <= y,
            "==": lambda x, y: x == y
        }
        return ops.get(operator, lambda x, y: False)(A, value)

    elif cond_type in ["time_window", "TimeWindow"]:
        start = params.get("start_mcs", params.get("start", 0))
        end = params.get("end_mcs", params.get("end", float("inf")))
        
        res = start <= engine.current_mcs < end
        # print(f"MCS {engine.current_mcs} in [{start}, {end}]? {res}")
        return res

    elif cond_type == "probability":
        p = params.get("p", 0)
        return random.random() < p

    return False

'''

def evaluate_single_condition(cond, cell, engine):
    cond_type = cond.get("condition_type", cond.get("type"))
    p = cond.get("params", cond)

    if cond_type == "TRUE":
        return True

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
        script_path = cond.get("script_path")  
        if not script_path or not os.path.exists(script_path):
            print(f"[Custom Error] Script not found: {script_path}")
            return False
        
        try:
            spec = importlib.util.spec_from_file_location("custom_mod", script_path)
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