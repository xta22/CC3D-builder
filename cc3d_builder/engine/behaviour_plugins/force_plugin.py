# force_plugin.py
from typing import Any

from cc3d_builder.core.rule_schema import case_payload


class ForcePlugin:
    def __init__(self, engine: Any):
        self.engine = engine

    def apply(self, rule: dict[str, Any], case: Any, cell: Any) -> None:
        if cell is None:
            return

        payload = case_payload(case)
        request = dict(payload)
        request.setdefault("mode", "vector")
        request["debug"] = bool(rule.get("debug") or request.get("debug", False))

        requests = cell.dict.setdefault("requests", {})
        requests["force"] = request

        if request.get("debug"):
            print(f"[ForcePlugin] queued force request for cell {cell.id}: {request.get('mode')}")
