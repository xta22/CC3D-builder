# scripts/state_lasting.py

def validate(cell, **kwargs):
    """
    Sub-condition logic：decide whether a state lasts long enough
    UI parameters passed in eg: "limit=15" or "limit=5"
    """
    # 1. parse the parameters from UI
    args_str = kwargs.get('script_args', "")
    limit = 10 
    
    if "limit=" in args_str:
        try:
            # parse the number after 
            limit = int(args_str.split("limit=")[1].split(",")[0])
        except:
            pass

    # 2. state lasting
    if "lasting_timer" not in cell.dict:
        cell.dict["lasting_timer"] = 0

    # self_defined condition
    is_condition_met = cell.volume > 50 

    if is_condition_met:
        cell.dict["lasting_timer"] += 1
    else:
        cell.dict["lasting_timer"] = 0 

    # 3. return boolean
    reached = cell.dict["lasting_timer"] >= limit
    
    if reached:
        print(f" Rule Triggered! Cell {cell.id} state lasted for {limit} steps.")
        
    return reached