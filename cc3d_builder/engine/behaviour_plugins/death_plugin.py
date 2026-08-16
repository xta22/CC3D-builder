# death_plugin.py
from .base_plugin import BaseBehaviourPlugin
from cc3d_builder.core.rule_schema import case_payload

class DeathPlugin(BaseBehaviourPlugin):
    behaviour_name = "death"

    def apply(self, rule, case, cell):
        """
        Build the initial death request.

        Death state mutation is owned by DeathSteppable so the runtime path
        stays consistent with the plugin + steppable architecture.
        """
        payload = case_payload(case)
        mode = payload.get("mode")  # "apoptosis" or "necrosis"
        if mode not in {"apoptosis", "necrosis"}:
            print(f"[DeathPlugin] Unknown death mode: {mode}")
            return None

        if cell.dict.get("is_dead"):
            return None

        return {
            "mode": mode,
            "params": dict(payload),
            "debug": bool(rule.get("debug") or payload.get("debug", False)),
        }

    def required_steppable(self):
        """
        # Notify the Engine: once the Death plugin is loaded,
        # `DeathSteppable` must also be forcibly mounted in the background 
        # to handle subsequent physical evolution.

        """
        return "DeathSteppable"
