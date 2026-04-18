from cc3d.core.PySteppables import *
from Rules_project.Simulation.core.model_registry import MODEL_REGISTRY


class GrowthSteppable(SteppableBasePy):

    def step(self, mcs):
        if self.cell_list is None: return
        
        for cell in self.cell_list:

            # -------------------------
            # get growth request
            # -------------------------
            req = cell.dict.get("requests", {}).get("growth")

            if not req:
                continue
            if req:
                print(f"DEBUG REQ: Cell {cell.id} - Request Content: {req}")
            model_name = req.get("model")
            model_fn = MODEL_REGISTRY.get(model_name)

            if not model_fn:
                continue

            # -------------------------
            # increase
            # -------------------------
            delta = model_fn(req, cell, self)
            print(f"MCS: {mcs} | Cell ID: {cell.id} | Type: {self.get_type_name_by_cell(cell)}")
            print(f"  > Growth Increment: +{delta:.4f} | New TargetVolume: {cell.targetVolume + delta:.2f}")
            # -------------------------
            # apply increase
            # -------------------------
            cell.targetVolume += delta

            # -------------------------
            # debug
            # -------------------------
            if req.get("debug", False):
                print(f"[Growth] Cell {cell.id} ΔV={delta}")

            # -------------------------
            # clean
            # -------------------------
            cell.dict["requests"]["growth"] = None