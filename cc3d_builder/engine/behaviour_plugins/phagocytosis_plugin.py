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
            return

        if phago_mode != "frustrated" and not target_type_name:
            print("[PhagocytosisPlugin] target_cell_type is required for absorption/engulfment")
            return

        request = dict(payload)
        request["debug"] = bool(rule.get("debug") or payload.get("debug", False))

        request_dict = cell.dict.setdefault("requests", {})
        queue = request_dict.get("phagocytosis")
        if not isinstance(queue, list):
            queue = []
            request_dict["phagocytosis"] = queue

        queue.append(request)

        if request["debug"]:
            print(f"[PhagocytosisPlugin] Queued phagocytosis request for cell {cell.id}: {request}")
