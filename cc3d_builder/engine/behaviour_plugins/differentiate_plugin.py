from .base_plugin import BaseBehaviourPlugin


class DifferentiationPlugin(BaseBehaviourPlugin):

    behaviour_name = "differentiate"

    def apply(self, rule, case, cell):

        apply_block = case.get("apply")
        if not apply_block:
            return

        mode = apply_block.get("mode")

        # =========================
        # 1️⃣ TYPE SWITCH
        # =========================
        if mode == "type_switch":

            self.push_request(cell, "type_switch", apply_block)

            if rule.get("debug"):
                print(f"[Plugin] type_switch requested for cell {cell.id}")

        # =========================
        # 2️⃣ DIVISION
        # =========================
        elif mode == "division":

            self.push_request(cell, "division", apply_block)

            if rule.get("debug"):
                print(f"[Plugin] division requested for cell {cell.id}")

        else:
            print(f"[Plugin] Unknown differentiate mode: {mode}")