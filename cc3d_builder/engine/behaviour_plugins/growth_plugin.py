# growth_plugin.py
from .base_plugin import BaseBehaviourPlugin
from cc3d_builder.core.rule_schema import case_payload


class GrowthPlugin(BaseBehaviourPlugin):

    def apply(self, rule, case, cell):

        payload = case_payload(case)
        if not payload:
            return None

        request = dict(payload)
        request["debug"] = bool(rule.get("debug") or request.get("debug", False))
        return request
