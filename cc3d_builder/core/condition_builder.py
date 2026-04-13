# condition_builder.py

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
        value = float(input("Threshold Value: "))

        return {
            "condition_type": "Environment",
            "params": {
                "field_name": field_name,
                "operator": operator,
                "threshold": value
            }
        }

    # =========================
    # 2. Topology
    # =========================
    elif choice == "2":
        target_type = input("Target cell type (e.g. ImmuneCell): ").strip()
        operator = input("Operator (>, <, >=, <=, ==): ").strip()
        value = float(input("Threshold Value (Ratio/Distance): "))

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
        value = float(input("Threshold Value: "))

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
        duration = int(input("How many MCS must this state last? "))
        
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
        start = int(input("Start MCS: "))
        end = int(input("End MCS: "))

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
        p = float(input("Probability (0-1): "))

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