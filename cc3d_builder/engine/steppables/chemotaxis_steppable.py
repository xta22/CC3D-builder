# chemotaxis_steppable.py
import math
from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.behaviour_stats import record_active_step, set_metric

class ChemotaxisSteppable(SteppableBasePy):
    def __init__(self, frequency=1, engine=None):
        # Inherit from the CC3D stepper base class.**
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        if self.engine is not None:
            self.engine.register_executor("chemotaxis", self)

    def step(self, mcs):
        if self.cell_list is None:
            return

        for cell in self.cell_list:
            requests = cell.dict.setdefault("requests", {})
            request = None if self.engine is not None and self.engine.ordered_dispatch_enabled() else requests.get("chemotaxis")
            stats = cell.dict.get("behaviour_stats", {}).get("chemotaxis", {})

            if not request:
                # No new command means the previously written ChemotaxisData
                # remains active until another rule explicitly overwrites it.
                if stats.get("active") and cell.dict.get("_chemotaxis_executed_mcs") != mcs:
                    record_active_step(cell, "chemotaxis", mcs)
                continue

            try:
                self.execute(cell, request, mcs)
            finally:
                requests["chemotaxis"] = None

            # ChemotaxisData itself remains active after this one-shot request is cleared.

    def execute(self, cell, request, mcs):
        plugin = self.chemotaxisPlugin
        if not plugin:
            return

        stats = cell.dict.get("behaviour_stats", {}).get("chemotaxis", {})

        # Filtering based on UI strategy.
        field_name = request.get("field_name", "ATTR")
        strategy = request.get("target_strategy", "break")

        is_target = False

        if strategy == "break":
            is_target = True
        elif strategy == "id" and cell.id == request.get("target_cell_id"):
            is_target = True
        elif strategy == "coord":
            tx = request.get("target_x", 0)
            ty = request.get("target_y", 0)
            if math.sqrt((cell.xCOM - tx)**2 + (cell.yCOM - ty)**2) <= 3.0:
                is_target = True

        if is_target:
            cd = plugin.getChemotaxisData(cell, field_name)
            if not cd:
                cd = plugin.addChemotaxisData(cell, field_name)

            actual_lambda = float(request.get("lambda", 20.0))
            cd.setLambda(actual_lambda)

            formula_name = request.get("formula", "Standard")
            if formula_name != "Standard":
                cd.setChemotaxisFormulaByName(formula_name)

                coef_val = request.get("coef")
                if coef_val is not None:
                    if formula_name == "Saturation":
                        cd.setSaturationCoef(float(coef_val))
                    elif formula_name == "SaturationLinear":
                        cd.setSaturationLinearCoef(float(coef_val))
                    elif formula_name == "LogScaled":
                        cd.setLogScaledCoef(float(coef_val))

            record_active_step(cell, "chemotaxis", mcs)
            set_metric(cell, "chemotaxis", "field_name", field_name)
            set_metric(cell, "chemotaxis", "lambda", actual_lambda)
            set_metric(cell, "chemotaxis", "formula", formula_name)

            if request.get("debug"):
                print(
                    f"[Chemotaxis Executive] Cell ID {cell.id} overridden! "
                    f"Field: {field_name}, Lambda: {actual_lambda}, Formula: {formula_name}"
                )
        elif stats.get("active"):
            record_active_step(cell, "chemotaxis", mcs)

        cell.dict["_chemotaxis_executed_mcs"] = mcs
