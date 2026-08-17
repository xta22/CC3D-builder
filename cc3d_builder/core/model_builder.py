# model_builder.py
def _ask_regulators():
    while True:
        regulator = input("Regulator diffusion field(s), comma-separated (e.g., Oxygen, Lactate): ")
        regulators = [
            r.strip()
            for r in regulator.split(",")
            if r.strip() and r.strip().lower() not in {"none", "null", "nan"}
        ]
        if regulators:
            return regulators
        print("At least one diffusion field regulator is required for field-regulated physical models.")


def build_model():
    print("Select field-regulated physical model:")
    print("Regulators here are CC3D diffusion fields only (e.g., Oxygen, Lactate).")
    print("Use State/native expression instead for {volume}, {division_count}, or custom state keys.")
    print("1 - hill")
    print("2 - linear")
    print("3 - expression")

    choice = input("Choice: ").strip()

    if choice == "1":
        regulators = _ask_regulators()

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
        regulators = _ask_regulators()
        
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
        regulators = _ask_regulators()
        
        expr = input("Expression using field variable names (e.g., 0.02 * Oxygen - 0.01 * Lactate): ").strip()
        return {
            "model": "expression",
            "regulator": regulators if len(regulators) > 1 else regulators[0],
            "parameters": {            
                "expression": expr
            }
        }
