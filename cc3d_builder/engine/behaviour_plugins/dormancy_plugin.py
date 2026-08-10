# dormancy_plugin.py
from .base_plugin import BaseBehaviourPlugin
from cc3d_builder.core.rule_schema import case_payload

class DormancyPlugin(BaseBehaviourPlugin):
    """
    Queue dormancy state-transition requests.
    """
    behaviour_name = "dormancy"

    def apply(self, rule, case, cell):
        """
        RuleEngine has already matched the condition. This plugin only records
        intent; DormancySteppable performs the state mutation.
        """
        payload = case_payload(case)
        action = payload.get("action", "dormant")
        if action not in {"dormant", "reactivate"}:
            print(f"[DormancyPlugin] Unknown dormancy action: {action}")
            return

        request = {
            "action": action,
            "debug": bool(rule.get("debug") or payload.get("debug", False)),
        }

        request_dict = cell.dict.setdefault("requests", {})
        queue = request_dict.get("dormancy")
        if not isinstance(queue, list):
            queue = []
            request_dict["dormancy"] = queue

        queue.append(request)

        if request["debug"]:
            print(f"[DormancyPlugin] queued {action} for cell {cell.id}")
