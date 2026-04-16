# rule_builder.py

from core.rule_model import Rule
from core.condition_builder import build_condition
from core.model_builder import build_model


def build_rule(behaviour, params):

    rule_id = params["id"]
    target = params.get("target")

    condition_block = params.get("when", {"condition_type": "TRUE", "params": {}})

    # =========================
    # GROWTH
    # =========================
    if behaviour == "growth":
        apply_block = params["apply"]

    # =========================
    # DIFFERENTIATE
    # =========================
    elif behaviour == "differentiate":

        mode = params["mode"]

        if mode == "type_switch":

            apply_block = {
                "mode": "type_switch",
                "new_type": params["new_type"]
            }

        elif mode == "division":

            apply_block = {
                "mode": "division",
                "parent_type": params["parent_type"],
                "child_type": params["child_type"],
                "volume_ratio": params.get("volume_ratio", 0.5),
                "placement": params.get("placement", {"type": "random"})
            }

        else:
            raise Exception("Invalid differentiate mode")

    # =========================
    # CREATE
    # =========================
    elif behaviour == "create":

        apply_block = {
            "cell_type": params["cell_type"],
            "count": params["count"],
            "distribution": params["distribution"]
        }

    elif behaviour == "custom_script":
        # we put parameters from UI into apply block
        # so Steppable could retrieve value from params
        apply_block = params.copy() 
        # delete the manual types value from params in case redundancy
        if "manual_types" in apply_block:
            del apply_block["manual_types"]
    else:
        raise Exception("Unsupported behaviour")

    rule = Rule(
        id=rule_id,
        target=target,
        behaviour=behaviour,
        cases=[{
            "when": condition_block,
            "apply": apply_block
        }],
        once=params.get("once", False),
        debug=params.get("debug", False)
    )

    return rule.to_dict()