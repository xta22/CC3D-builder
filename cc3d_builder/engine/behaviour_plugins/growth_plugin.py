# growth_plugin.py
from .base_plugin import BaseBehaviourPlugin
from cc3d_builder.core.rule_schema import case_payload


class GrowthPlugin(BaseBehaviourPlugin):

    def apply(self, rule, case, cell):

        payload = case_payload(case)
        if not payload:
            return

        requests = cell.dict.setdefault("requests", {})
        queue = requests.get("growth")
        if not isinstance(queue, list):
            queue = []
            requests["growth"] = queue

        request = dict(payload)
        request["debug"] = bool(rule.get("debug") or request.get("debug", False))
        queue.append(request)
