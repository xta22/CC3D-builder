from cc3d.core.PySteppables import *
from cc3d_builder.engine.core.model_registry import MODEL_REGISTRY
import math

# 🧬 Generated High-Performance Steppable
class CompiledRuleSteppable(SteppableBasePy):
    def step(self, mcs):

        # --- Compiled Rule 1 (growth) ---
        for cell in self.cell_list_by_type(self.CELLA):
            if evaluate_condition({"condition_type": "Environment", "params": {"operator": ">", "threshold": 3.0, "field_name": "Substrate"}}, cell, self):
                apply_params = {"model": "hill", "regulator": "Oxygen", "parameters": {"y_max": 1.0, "y_min": 0.0, "K": 0.5, "n": 2.0}}
                delta = MODEL_REGISTRY['hill'](apply_params, cell, self)
                cell.targetVolume += delta

        # --- Compiled Rule 2 (growth) ---
        for cell in self.cell_list_by_type(self.CELL):
            if evaluate_condition({"condition_type": "Environment", "params": {"operator": ">", "threshold": 3.0, "field_name": "Oxygen"}}, cell, self):
                apply_params = {"model": "linear", "regulator": "Substrate", "parameters": {"alpha": 0.1}}
                delta = MODEL_REGISTRY['linear'](apply_params, cell, self)
                cell.targetVolume += delta