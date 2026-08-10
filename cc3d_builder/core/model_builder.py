# model_builder.py
def build_model():
    print("Select model:")
    print("1 - hill")
    print("2 - linear")
    print("3 - expression")

    choice = input("Choice: ").strip()

    if choice == "1":
        regulator = input("Regulator (field name or list separated by comma): ")
        regulators = [r.strip() for r in regulator.split(",") if r.strip()]

        y_max = float(input("y_max: "))
        y_min = float(input("y_min: "))
        K = float(input("K: "))
        n = float(input("n: "))

        return {
            "model": "hill",
            "regulator": regulators if len(regulators) > 1 else regulators[0],
            "parameters": {
                "y_max": y_max,
                "y_min": y_min,
                "K": K,
                "n": n
            }
        }

    elif choice == "2":
        regulator = input("Regulator fields (separated by comma, e.g., Oxygen, Lactate): ")
        regulators = [r.strip() for r in regulator.split(",") if r.strip()]
        
        alphas = []
        if len(regulators) > 1:
            print(f"Detected {len(regulators)} fields. Please enter alpha for each field sequentially:")
            for r in regulators:
                alpha_val = float(input(f"  alpha for {r}: "))
                alphas.append(alpha_val)
        else:
            alphas = float(input("alpha: "))

        return {
            "model": "linear",
            "regulator": regulators if len(regulators) > 1 else regulators[0],
            "parameters": {
                "alpha": alphas 
            }
        }

    elif choice == "3":
        regulator = input("Regulator fields (separated by comma, e.g., Oxygen, Lactate): ")
        regulators = [r.strip() for r in regulator.split(",") if r.strip()]
        
        expr = input("Expression (e.g., 0.02 * Oxygen - 0.01 * Lactate): ").strip()
        return {
            "model": "expression",
            "regulator": regulators if len(regulators) > 1 else regulators[0],
            "parameters": {            
                "expression": expr
            }
        }