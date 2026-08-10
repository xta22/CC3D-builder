# fpp_link_plugin.py
from typing import Any

from cc3d_builder.core.rule_schema import case_payload


class FPPLinkPlugin:
    def __init__(self, engine: Any):
        self.engine = engine

    def apply(self, rule: dict[str, Any], case: Any, cell: Any) -> None:
        if cell is None:
            return

        payload = case_payload(case)
        request = dict(payload)
        request.setdefault("mode", "nearest_type")
        request["debug"] = bool(rule.get("debug") or request.get("debug", False))

        requests = cell.dict.setdefault("requests", {})
        queue = requests.get("fpp_link")
        if not isinstance(queue, list):
            queue = []
            requests["fpp_link"] = queue

        queue.append(request)
