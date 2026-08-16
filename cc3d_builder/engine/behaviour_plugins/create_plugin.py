# create_plugin.py
from .base_plugin import BaseBehaviourPlugin
from cc3d_builder.core.rule_schema import case_payload


class CreatePlugin(BaseBehaviourPlugin):

    behaviour_name = "create"

    def apply(self, rule, case, cell):

        payload = dict(case_payload(case))

        if not payload:
            return None

        payload["debug"] = bool(rule.get("debug") or payload.get("debug", False))
        return payload
