# intracellular_model_plugin.py
from __future__ import annotations

from typing import Any

from cc3d_builder.core.rule_schema import case_payload


class IntracellularModelPlugin:
    behaviour_name = "intracellular_model"

    def __init__(self, engine: Any):
        self.engine = engine

    def apply(self, rule: dict[str, Any], case: Any, cell: Any) -> dict[str, Any] | None:
        payload = case_payload(case)
        if not payload:
            return None

        request = dict(payload)
        request.setdefault("action", "advance")
        request["debug"] = bool(rule.get("debug") or request.get("debug", False))
        return request
