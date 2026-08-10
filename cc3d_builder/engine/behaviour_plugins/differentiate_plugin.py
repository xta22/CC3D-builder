# differentiate_plugin.py
from .base_plugin import BaseBehaviourPlugin
from cc3d_builder.core.rule_schema import case_payload


class DifferentiationPlugin(BaseBehaviourPlugin):

    behaviour_name = "differentiate"

    def apply(self, rule, case, cell):

        payload = case_payload(case)
        if not payload:
            return

        mode = payload.get("mode")

        # =========================
        # 1️⃣ TYPE SWITCH
        # =========================
        if mode == "type_switch":

            self.push_request(cell, "type_switch", payload)

            if rule.get("debug"):
                print(f"[Plugin] type_switch requested for cell {cell.id}")

        # =========================
        # 2️⃣ DIVISION
        # =========================
        elif mode == "division":

            self.push_request(cell, "division", payload)

            if rule.get("debug"):
                print(f"[Plugin] division requested for cell {cell.id}")

        else:
            print(f"[Plugin] Unknown differentiate mode: {mode}")
