# scripts/state_lasting.py

def validate(cell, engine, p, **kwargs):
    # Read v_threshold from params p, default to 50 if not provided
    # Note: p is the "params" dictionary defined in your JSON
    # here we list self-defined parameters in advance so we could modify them in GUI
    threshold = p.get("v_threshold", 50) 
    limit = p.get("limit", 10)

    # State duration tracking logic
    if "lasting_timer" not in cell.dict:
        cell.dict["lasting_timer"] = 0

    is_condition_met = cell.volume > threshold 

    if is_condition_met:
        cell.dict["lasting_timer"] += 1
    else:
        cell.dict["lasting_timer"] = 0 

    #Check if the target duration is reached
    reached = cell.dict["lasting_timer"] >= limit
    
    # if reached:
        # print(f"Rule Triggered! Cell {cell.id} volume > {threshold} for {limit} steps.")
    # in this context only when the target cell we specified     
    return reached