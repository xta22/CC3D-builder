# growth_steppable.py
from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.model_registry import MODEL_REGISTRY
from cc3d_builder.engine.core.behaviour_stats import record_active_step


class GrowthSteppable(SteppableBasePy):

    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        if self.engine is not None:
            self.engine.register_executor("growth", self)

    def step(self, mcs):
        if self.cell_list is None:
            return

        for cell in self.cell_list:
            requests = cell.dict.get("requests", {})
            growth_requests = requests.get("growth", [])

            if not growth_requests:
                continue

            try:
                if isinstance(growth_requests, dict):
                    growth_requests = [growth_requests]

                total_delta = 0.0
                applied_count = 0

                for req in list(growth_requests):
                    delta = self.execute(cell, req, mcs, record_stats=False)
                    total_delta += delta
                    applied_count += 1

                if applied_count:
                    record_active_step(cell, "growth", mcs, total_delta)
            finally:
                requests["growth"] = []

    def execute(self, cell, req, mcs, record_stats=True):
        model_name = req.get("model")
        model_fn = MODEL_REGISTRY.get(model_name)

        if not model_fn:
            print(f"[Growth] Unknown model '{model_name}' for cell {cell.id}")
            return 0.0

        delta = model_fn(req, cell, self)
        if delta is None:
            delta = 0.0

        cell.targetVolume += delta
        if record_stats:
            record_active_step(cell, "growth", mcs, delta)

        if req.get("debug", False):
            cell_type = self.get_type_name_by_cell(cell)
            print(
                f"[Growth] MCS={mcs} cell={cell.id} type={cell_type} "
                f"model={model_name} delta={delta:.4f} targetVolume={cell.targetVolume:.2f}"
            )

        return delta
