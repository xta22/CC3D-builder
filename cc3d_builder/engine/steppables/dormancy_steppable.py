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
    Execute dormancy state-transition requests and track persistent dormancy.

    RuleEngine handles rule matching and calls execute directly. This steppable
    mutates cell state and records continuing dormancy during step().
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
            if cell.dict.get("dormant", False) and cell.dict.get("_dormancy_executed_mcs") != mcs:
                record_active_step(cell, "dormancy", mcs)

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
