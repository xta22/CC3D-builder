# dormancy_plugin.py
from .base_plugin import BaseBehaviourPlugin
from cc3d_builder.core.rule_schema import case_payload

class DormancyPlugin(BaseBehaviourPlugin):
    """
    Build dormancy state-transition requests.
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
            return None

        request = {
            "action": action,
            "debug": bool(rule.get("debug") or payload.get("debug", False)),
        }

        if request["debug"]:
            print(f"[DormancyPlugin] built {action} for cell {cell.id}")

        return request
