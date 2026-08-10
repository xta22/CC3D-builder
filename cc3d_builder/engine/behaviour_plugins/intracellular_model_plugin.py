# intracellular_model_plugin.py
from __future__ import annotations

from typing import Any

from cc3d_builder.core.rule_schema import case_payload


class IntracellularModelPlugin:
    behaviour_name = "intracellular_model"

    def __init__(self, engine: Any):
        self.engine = engine

    def apply(self, rule: dict[str, Any], case: Any, cell: Any) -> None:
        payload = case_payload(case)
        if not payload:
            return

        request = dict(payload)
        request.setdefault("action", "advance")
        request["debug"] = bool(rule.get("debug") or request.get("debug", False))

        if cell is None:
            queue = getattr(self.engine, "intracellular_global_queue", None)
            if not isinstance(queue, list):
                queue = []
                self.engine.intracellular_global_queue = queue
            queue.append(request)
            return

        requests = cell.dict.setdefault("requests", {})
        queue = requests.get("intracellular_model")
        if not isinstance(queue, list):
            queue = []
            requests["intracellular_model"] = queue
        queue.append(request)
