# secrete_uptake_plugin.py
# cc3d_builder/engine/behaviour_plugins/secrete_uptake_plugin.py
from cc3d_builder.core.rule_schema import case_payload

class SecreteUptakePlugin:
    def __init__(self, steppable_context):
        self.context = steppable_context

    def apply(self, rule, case, cell):
        payload = case_payload(case)

        field_name = payload.get("field_name")
        secret_mode = payload.get("secret_mode")
        if not field_name or not secret_mode:
            return

        request = dict(payload)

        if "requests" not in cell.dict:
            cell.dict["requests"] = {}

        cell.dict["requests"].setdefault("secretion", [])
        cell.dict["requests"]["secretion"].append(request)

        if rule.get("debug") or request.get("debug"):
            print(
                f"[Secrete/UptakePlugin] queued {secret_mode} "
                f"for cell {cell.id} on field {field_name}"
            )