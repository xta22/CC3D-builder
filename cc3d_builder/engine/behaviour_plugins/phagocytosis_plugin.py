# phagocytosis_plugin.py
from .base_plugin import BaseBehaviourPlugin
from cc3d_builder.core.rule_schema import case_payload


class PhagocytosisPlugin(BaseBehaviourPlugin):
    behaviour_name = "phagocytosis"

    def apply(self, rule, case, cell):
        payload = case_payload(case)
        phago_mode = payload.get("phago_mode", "engulfment")
        target_type_name = payload.get("target_cell_type")

        valid_modes = {"absorption", "engulfment", "frustrated"}
        if phago_mode not in valid_modes:
            print(f"[PhagocytosisPlugin] Unknown phagocytosis mode: {phago_mode}")
            return None

        if phago_mode != "frustrated" and not target_type_name:
            print("[PhagocytosisPlugin] target_cell_type is required for absorption/engulfment")
            return None

        request = dict(payload)
        request["debug"] = bool(rule.get("debug") or payload.get("debug", False))

        if request["debug"]:
            print(f"[PhagocytosisPlugin] Built phagocytosis request for cell {cell.id}: {request}")

        return request
