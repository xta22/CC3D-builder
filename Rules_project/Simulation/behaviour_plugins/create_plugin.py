from .base_plugin import BaseBehaviourPlugin


class CreatePlugin(BaseBehaviourPlugin):

    behaviour_name = "create"

    def apply(self, rule, case, cell):

        apply_block = case.get("apply")

        if not apply_block:
            return

        self.engine.create_queue.append(apply_block)