# chemotaxis_plugin.py
# Behaviours/ChemotaxisPlugin.py
from typing import Any
from cc3d_builder.core.rule_schema import case_payload

class ChemotaxisPlugin:
    def __init__(self, engine: Any):
        self.engine = engine

    def apply(self, rule: dict[str, Any], case: Any, cell: Any) -> dict[str, Any] | None:
        """
        When the conditions of the main engine's judgment are met, this action is automatically triggered.
        """
        payload = dict(case_payload(case))
        
        if "mode" not in payload:
            payload["mode"] = "chemotaxis"
        payload["debug"] = bool(rule.get("debug") or payload.get("debug", False))

        if rule.get("debug") or payload.get("debug"):
            print(f"[Plugin] Chemotaxis request built for cell {cell.id} on field {payload.get('field_name')}")

        return payload
