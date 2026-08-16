# differentiate_plugin.py
from .base_plugin import BaseBehaviourPlugin
from cc3d_builder.core.rule_schema import case_payload


class DifferentiationPlugin(BaseBehaviourPlugin):

    behaviour_name = "differentiate"

    def apply(self, rule, case, cell):

        payload = case_payload(case)
        if not payload:
            return None

        mode = payload.get("mode")
        request = dict(payload)
        request["debug"] = bool(rule.get("debug") or request.get("debug", False))

        # =========================
        # 1️⃣ TYPE SWITCH
        # =========================
        if mode == "type_switch":
            if rule.get("debug"):
                print(f"[Plugin] type_switch requested for cell {cell.id}")
            return request

        # =========================
        # 2️⃣ DIVISION
        # =========================
        elif mode == "division":
            if rule.get("debug"):
                print(f"[Plugin] division requested for cell {cell.id}")
            return request

        else:
            print(f"[Plugin] Unknown differentiate mode: {mode}")
            return None
