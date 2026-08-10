# dormancy_steppable.py
from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.behaviour_stats import (
    record_active_step,
    record_deactivation,
    record_event,
    set_metric,
)


class DormancySteppable(SteppableBasePy):
    """
    Execute queued dormancy state-transition requests.

    RuleEngine handles rule matching and DormancyPlugin queues requests. This
    steppable only mutates cell state and clears the queue.
    """

    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        if self.engine is not None:
            self.engine.register_executor("dormancy", self)

    def step(self, mcs):
        if self.cell_list is None:
            return

        for cell in self.cell_list:
            request_dict = cell.dict.setdefault("requests", {})
            requests = request_dict.get("dormancy", [])

            if cell.dict.get("dormant", False) and cell.dict.get("_dormancy_executed_mcs") != mcs:
                record_active_step(cell, "dormancy", mcs)

            if self.engine is not None and self.engine.ordered_dispatch_enabled():
                continue

            if not requests:
                continue

            try:
                if "dormant" not in cell.dict:
                    cell.dict["dormant"] = False

                for request in list(requests):
                    self._execute_request(cell, request, mcs)
            finally:
                request_dict["dormancy"] = []

    def execute(self, cell, request, mcs):
        self._execute_request(cell, request, mcs)
        cell.dict["_dormancy_executed_mcs"] = mcs

    def _execute_request(self, cell, request, mcs):
        action = request.get("action", "dormant")
        debug = request.get("debug", False)

        if action == "dormant":
            if not cell.dict.get("dormant", False):
                cell.dict["dormant"] = True
                record_event(cell, "dormancy", mcs)
                record_active_step(cell, "dormancy", mcs)
                set_metric(cell, "dormancy", "last_action", "dormant")
                if debug:
                    print(f"[DormancySteppable] Cell {cell.id} entered dormancy")

        elif action == "reactivate":
            if cell.dict.get("dormant", False):
                cell.dict["dormant"] = False
                record_event(cell, "dormancy", mcs)
                record_deactivation(cell, "dormancy", mcs)
                set_metric(cell, "dormancy", "last_action", "reactivate")
                if debug:
                    print(f"[DormancySteppable] Cell {cell.id} reactivated")

        else:
            print(f"[DormancySteppable] Unknown dormancy action: {action}")
