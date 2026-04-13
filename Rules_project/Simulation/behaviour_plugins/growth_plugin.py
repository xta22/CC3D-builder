from .base_plugin import BaseBehaviourPlugin


class GrowthPlugin(BaseBehaviourPlugin):

    def apply(self, rule, case, cell):

        apply_block = case.get("apply")
        if not apply_block:
            return

        if "requests" not in cell.dict:
            cell.dict["requests"] = {}

        cell.dict["requests"]["growth"] = apply_block