# subcellular_plugin.py
from __future__ import annotations

from typing import Any

from cc3d_builder.core.rule_schema import case_payload


class SubcellularPlugin:
    behaviour_name = "subcellular"

    def __init__(self, engine: Any):
        self.engine = engine

    def apply(self, rule: dict[str, Any], case: Any, cell: Any) -> dict[str, Any] | None:
        if cell is None:
            return None

        payload = case_payload(case)
        request = dict(payload)
        request.setdefault("action", "set_stage")
        request["debug"] = bool(rule.get("debug") or request.get("debug", False))
        return request
