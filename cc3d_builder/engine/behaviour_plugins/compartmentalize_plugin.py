# compartmentalize_plugin.py
from typing import Any

from cc3d_builder.core.rule_schema import case_payload


class CompartmentalizePlugin:
    def __init__(self, engine: Any):
        self.engine = engine

    def apply(self, rule: dict[str, Any], case: Any, cell: Any) -> None:
        if cell is None:
            return

        payload = case_payload(case)
        request = dict(payload)
        request.setdefault("action", "extend_chain")
        request["debug"] = bool(rule.get("debug") or request.get("debug", False))

        requests = cell.dict.setdefault("requests", {})
        queue = requests.get("compartmentalize")
        if not isinstance(queue, list):
            queue = []
            requests["compartmentalize"] = queue

        queue.append(request)

        if request.get("debug_queue"):
            print(f"[CompartmentalizePlugin] queued compartmentalize request for cell {cell.id}: {request.get('action')}")
