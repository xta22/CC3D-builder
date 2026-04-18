# cli_interface.py

from cc3d_builder.core.rule_builder import build_rule


def cli_add_rule():

    params = {}

    # =========================
    # basic information
    # =========================

    params["id"] = input("Rule ID: ").strip()

    target = input("Target cell type (or None): ").strip()
    params["target"] = None if target.lower() == "none" else target

    print("\nBehaviour:")
    print("1 - growth")
    print("2 - differentiate")
    print("3 - create")

    choice = input("Choice: ").strip()

    if choice == "1":
        behaviour = "growth"

    elif choice == "2":
        behaviour = "differentiate"

    elif choice == "3":
        behaviour = "create"

    else:
        raise Exception("Invalid behaviour")

    # =========================
    # CONDITION
    # =========================

    from cc3d_builder.cli.condition_builder import build_condition
    params["when"] = build_condition()

    # ============================================================
    # GROWTH
    # ============================================================

    if behaviour == "growth":

        from cc3d_builder.core.model_builder import build_model
        params["apply"] = build_model()

    # ============================================================
    # DIFFERENTIATE
    # ============================================================

    elif behaviour == "differentiate":

        print("\nDifferentiation mode:")
        print("1 - type_switch (A → B)")
        print("2 - division (A → X + Y)")

        mode_choice = input("Choice: ").strip()

        # -------- TYPE SWITCH --------
        if mode_choice == "1":

            params["mode"] = "type_switch"
            params["new_type"] = input("New type: ").strip()

        # -------- DIVISION --------
        elif mode_choice == "2":

            params["mode"] = "division"

            print("\nDivision type:")
            print("1 - symmetric (B + B)")
            print("2 - asymmetric (B + C)")

            div_type = input("Choice: ").strip()

            if div_type == "1":
                params["division_type"] = "symmetric"
                d_type = input("Daughter type: ").strip()
                params["parent_type"] = d_type
                params["child_type"] = d_type

            elif div_type == "2":

                params["division_type"] = "asymmetric"
                params["parent_type"] = input("Mother new type: ").strip()
                params["child_type"] = input("Daughter type: ").strip()

            else:
                raise Exception("Invalid division type")

            ratio = input("Mother volume ratio (0-1, default 0.5): ").strip()
            params["volume_ratio"] = float(ratio) if ratio else 0.5

            print("\nOrientation strategy:")
            print("1 - random")
            print("2 - specify angle")
            print("3 - specify direction vector")

            orient_choice = input("Choice: ").strip()

            if orient_choice == "1":
                params["placement"] = {"type": "random"}

            elif orient_choice == "2":
                angle = float(input("Angle (degrees): "))
                params["placement"] = {
                    "type": "angle",
                    "angle_deg": angle
                }

            elif orient_choice == "3":
                dx = float(input("dx: "))
                dy = float(input("dy: "))
                params["placement"] = {
                    "type": "vector",
                    "dx": dx,
                    "dy": dy
                }

            else:
                params["placement"] = {"type": "random"}

        else:
            raise Exception("Invalid differentiate mode")

    # ============================================================
    # CREATE
    # ============================================================

    elif behaviour == "create":

        params["cell_type"] = input("New cell type: ").strip()
        params["count"] = int(input("Count: "))

        print("\nDistribution:")
        print("1 - random")
        print("2 - cluster")
        print("3 - stripe")

        d = input("Choice: ").strip()

        # -------- RANDOM --------
        if d == "1":

            use_region = input("Specify region? (y/n): ").strip().lower()

            if use_region == "y":

                params["distribution"] = {
                    "type": "random",
                    "x_start": int(input("x_start: ")),
                    "x_end": int(input("x_end: ")),
                    "y_start": int(input("y_start: ")),
                    "y_end": int(input("y_end: "))
                }

            else:
                params["distribution"] = {"type": "random"}

        # -------- CLUSTER --------
        elif d == "2":

            params["distribution"] = {
                "type": "cluster",
                "center": [
                    int(input("center x: ")),
                    int(input("center y: "))
                ],
                "radius": int(input("radius: "))
            }

        # -------- STRIPE --------
        elif d == "3":

            print("\nStripe direction:")
            print("1 - vertical")
            print("2 - horizontal")

            dir_choice = input("Choice: ").strip()

            # =========================
            # vertical
            # =========================
            if dir_choice == "1":

                direction = "vertical"

                x = int(input("x position: "))
                y_start = int(input("y_start: "))

                print("\nMode:")
                print("1 - start + gap")
                print("2 - start + end")

                mode = input("Choice: ").strip()

                dist = {
                    "type": "stripe",
                    "direction": direction,
                    "x": x,
                    "y_start": y_start
                }

                if mode == "1":
                    y_gap = int(input("y_gap: "))
                    dist["y_gap"] = y_gap

                elif mode == "2":
                    y_end = int(input("y_end: "))
                    dist["y_end"] = y_end

                else:
                    raise Exception("Invalid mode")

                params["distribution"] = dist

            # =========================
            # horizontal
            # =========================
            elif dir_choice == "2":

                direction = "horizontal"

                y = int(input("y position: "))
                x_start = int(input("x_start: "))

                print("\nMode:")
                print("1 - start + gap")
                print("2 - start + end")

                mode = input("Choice: ").strip()

                dist = {
                    "type": "stripe",
                    "direction": direction,
                    "y": y,
                    "x_start": x_start
                }

                if mode == "1":
                    x_gap = int(input("x_gap: "))
                    dist["x_gap"] = x_gap

                elif mode == "2":
                    x_end = int(input("x_end: "))
                    dist["x_end"] = x_end

                else:
                    raise Exception("Invalid mode")

                params["distribution"] = dist

            else:
                raise Exception("Invalid direction")

        else:
            raise Exception("Invalid distribution")

    # ============================================================

    params["once"] = input("Trigger once? (y/n): ").strip().lower() == "y"
    params["debug"] = input("Debug mode? (y/n): ").strip().lower() == "y"

    # =========================
    # build rule
    # =========================

    rule = build_rule(behaviour, params)

    return rule

def ask_celltype_params(name):

    print(f"\n[New CellType Detected] {name}")

    target = float(input("targetVolume: "))
    lam = float(input("lambdaVolume: "))

    return {
        "targetVolume": target,
        "lambdaVolume": lam
    }