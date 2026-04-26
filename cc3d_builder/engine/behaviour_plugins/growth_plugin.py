from .base_plugin import BaseBehaviourPlugin


class GrowthPlugin(BaseBehaviourPlugin):

    def apply(self, rule, case, cell):

        apply_block = case.get("apply")
        if not apply_block:
            return

        if "requests" not in cell.dict:
            cell.dict["requests"] = {}

        cell.dict["requests"]["growth"] = apply_block
        print(f"📝 [DEBUG 4] Request Written: Cell:{cell.id} dict['requests']['growth'] = {growth_val}")
        print(f"   Current Dict State: {cell.dict['requests']}")