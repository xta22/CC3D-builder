# condition_builder.py
from cc3d_builder.core.dynamic_numeric import parse_dynamic_numeric


ENVIRONMENT_SAMPLING_MODES = {
    "1": "com",
    "2": "cell_average",
    "3": "cell_max",
    "4": "cell_min",
    "5": "boundary_average",
    "6": "boundary_max",
    "7": "boundary_min",
    "8": "contact_boundary_average",
    "9": "contact_boundary_max",
    "10": "contact_boundary_min",
    "11": "radius_average",
    "12": "radius_max",
    "13": "radius_min",
}


def _ask_dynamic_number(prompt, default=0.0):
    raw = input(f"{prompt} [default {default}]: ").strip()
    return parse_dynamic_numeric(raw if raw else default, default)


def _ask_environment_sampling_params():
    print("\nEnvironment sampling mode:")
    print("  1 - com: field value at cell center of mass (default)")
    print("  2 - cell_average: average across all cell pixels")
    print("  3 - cell_max: maximum across all cell pixels")
    print("  4 - cell_min: minimum across all cell pixels")
    print("  5 - boundary_average: average across cell boundary pixels")
    print("  6 - boundary_max: maximum across cell boundary pixels")
    print("  7 - boundary_min: minimum across cell boundary pixels")
    print("  8 - contact_boundary_average: average on boundary touching a target type")
    print("  9 - contact_boundary_max: maximum on boundary touching a target type")
    print("  10 - contact_boundary_min: minimum on boundary touching a target type")
    print("  11 - radius_average: average inside radius around COM")
    print("  12 - radius_max: maximum inside radius around COM")
    print("  13 - radius_min: minimum inside radius around COM")

    choice = input("Sampling mode [1]: ").strip() or "1"
    mode = ENVIRONMENT_SAMPLING_MODES.get(choice, "com")
    params = {"sampling_mode": mode}

    if mode.startswith("contact_boundary_"):
        params["target_type"] = input("Contact target cell type (e.g. FungusYeast): ").strip()

    if mode.startswith("radius_"):
        params["radius"] = _ask_dynamic_number("Sampling radius", 3)

    return params

def build_condition():

    print("\nSelect condition type:")
    print("1 - Environment (Field Threshold)")
    print("2 - Topology (Cell Contact)")
    print("3 - Morphology (Shape/Size)")
    print("4 - State-Lasting (Memory/Duration)")
    print("5 - Time Window (MCS based)")
    print("6 - Probability (Random)")
    print("7 - Logical block (AND/OR/NOT)")
    print("8 - Custom Script")
    print("9 - Always True")

    choice = input("Choice: ").strip()

    # =========================
    # 1. Environment
    # =========================
    if choice == "1":
        field_name = input("Field name (e.g. Oxygen): ").strip()
        operator = input("Operator (>, <, >=, <=, ==): ").strip()
        value = _ask_dynamic_number("Threshold Value", 0.0)
        params = {
            "field_name": field_name,
            "operator": operator,
            "threshold": value
        }
        params.update(_ask_environment_sampling_params())

        return {
            "condition_type": "Environment",
            "params": params
        }

    # =========================
    # 2. Topology
    # =========================
    elif choice == "2":
        target_type = input("Target cell type (e.g. ImmuneCell): ").strip()
        operator = input("Operator (>, <, >=, <=, ==): ").strip()
        value = _ask_dynamic_number("Threshold Value (Ratio/Distance)", 0.0)

        return {
            "condition_type": "Contact", # "Distance' could be considered to add here
            "params": {
                "target_type": target_type,
                "operator": operator,
                "threshold": value
            }
        }

    # =========================
    # 3. Morphology
    # =========================
    elif choice == "3":
        print("Indicators: 1 - Elongation, 2 - Specific_Surface")
        ind_choice = input("Indicator choice: ").strip()
        indicator = "Elongation" if ind_choice == "1" else "SpecificSurface"
        
        operator = input("Operator (>, <, >=, <=, ==): ").strip()
        value = _ask_dynamic_number("Threshold Value", 0.0)

        return {
            "condition_type": f"Morphology_{indicator}",
            "params": {
                "operator": operator,
                "threshold": value
            }
        }

    # =========================
    # 4. State-Lasting (Memory)
    # =========================
    elif choice == "4":
        duration = _ask_dynamic_number("How many MCS must this state last?", 50)
        
        print("\n>>> Now define the base condition that needs to be maintained:")
        sub_condition = build_condition() 

        return {
            "condition_type": "Duration",
            "params": {
                "threshold_mcs": duration,
                "sub_condition": sub_condition
            }
        }

    # =========================
    # 5. Time Window
    # =========================
    elif choice == "5":
        start = _ask_dynamic_number("Start MCS", 0)
        end = _ask_dynamic_number("End MCS", 1000)

        return {
            "condition_type": "TimeWindow",
            "params": {
                "start_mcs": start,
                "end_mcs": end
            }
        }

    # =========================
    # 6. Probability
    # =========================
    elif choice == "6":
        p = _ask_dynamic_number("Probability (0-1)", 0.5)

        return {
            "condition_type": "Probability",
            "params": {
                "p": p
            }
        }

    # =========================
    # 7. Logical Block
    # =========================
    elif choice == "7":
        logic = input("Logic type (AND/OR/NOT): ").strip().upper()

        if logic == "NOT":
            n = 1
        else:
            n = int(input("How many sub-conditions? "))

        conditions = []
        for i in range(n):
            print(f"\n--- Sub-condition {i+1} for {logic} ---")
            conditions.append(build_condition()) 

        return {
            "condition_type": f"Logic_{logic}",
            "params": {
                "conditions": conditions
            }
        }

    # =========================
    # 8. Custom Script
    # =========================
    elif choice == "8":
        script_path = input("Enter script path (e.g. custom/my_logic.py): ").strip()
        
        raw_params = input("Enter params (e.g. target_type=ImmuneCell, count=5) [Leave blank if none]: ").strip()
        
        custom_params = {}
        if raw_params:
            for pair in raw_params.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    try:
                        if "." in v:
                            v = float(v)
                        else:
                            v = int(v)
                    except ValueError:
                        pass 
                    
                    custom_params[k] = v

        return {
            "condition_type": "Custom",
            "script_path": script_path,
            "params": custom_params
        }

    # =========================
    # 9. Always True
    # =========================
    else:
        print("Set to default: Always True")
        return {
            "condition_type": "TRUE",
            "params": {}
        }
