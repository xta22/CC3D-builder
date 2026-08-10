# chemotaxis_plugin.py
# Behaviours/ChemotaxisPlugin.py
from typing import Any
from cc3d_builder.core.rule_schema import case_payload

class ChemotaxisPlugin:
    def __init__(self, engine: Any):
        self.engine = engine

    def push_request(self, cell: Any, key: str, value: Any) -> None:
        """Reuse your native distributed distribution hub."""
        if "requests" not in cell.dict:
            cell.dict["requests"] = {}
        cell.dict["requests"][key] = value

    def apply(self, rule: dict[str, Any], case: Any, cell: Any) -> None:
        """
        When the conditions of the main engine's judgment are met, this action is automatically triggered.
        """
        payload = case_payload(case)
        
        if "mode" not in payload:
            payload["mode"] = "chemotaxis"

        self.push_request(cell, "chemotaxis", payload)

        if rule.get("debug") or payload.get("debug"):
            print(f"[Plugin] Chemotaxis request pushed for cell {cell.id} on field {payload.get('field_name')}")
