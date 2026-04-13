
def build_model():

    print("Select model:")
    print("1 - hill")
    print("2 - linear")
    print("3 - expression")

    choice = input("Choice: ").strip()

    if choice == "1":
        regulator = input("Regulator (field name or list separated by comma): ")
        regulators = [r.strip() for r in regulator.split(",")]

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
        regulator = input("Regulator field: ")
        alpha = float(input("alpha: "))

        return {
            "model": "linear",
            "regulator": regulator,
            "parameters": {
                "alpha": alpha
            }
        }


    elif choice == "3":
        regulator = input("Regulator (field name): ").strip()
        expr = input("Expression (e.g. 0.02 * Oxygen): ").strip()
        return {
            "model": "expression",
            "regulator": regulator,
            "parameters": {            
                "expression": expr
            }
        }