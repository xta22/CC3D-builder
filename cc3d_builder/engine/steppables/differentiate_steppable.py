# differentiate_steppable.py
import math
from cc3d.core.PySteppables import MitosisSteppableBase


class DifferentiateSteppable(MitosisSteppableBase):

    def __init__(self, frequency=1, engine=None):
        MitosisSteppableBase.__init__(self, frequency)
        self.engine = engine

    def step(self, mcs):
        if self.cell_list is None: 
            return
        
        if self.engine is None:
            return
        
        cells_to_divide = []

        for cell in self.cell_list:
            
            # =========================
            # 1️⃣ TYPE SWITCH
            # =========================
            ts = cell.dict.get("requests", {}).get("type_switch")

            if ts:
                new_type = ts.get("new_type")

                if new_type:
                    cell.type = getattr(self, new_type.upper())
                    params = self.engine.celltype_params.get(new_type, {})

                    cell.targetVolume = params.get("targetVolume", 50)
                    cell.lambdaVolume = params.get("lambdaVolume", 10)
                cell.dict["requests"]["type_switch"] = None

            # =========================
            # 2️⃣ DIVISION REQUEST
            # =========================
            request = cell.dict.get("requests", {}).get("division")

            if request:
                cells_to_divide.append((cell, request))


                cell.dict["_internal"]["division_in_progress"] = True

        # =========================
        # =========================
        for cell, request in cells_to_divide:

            cell.dict["_internal"]["division_request"] = request

            placement = request.get("placement", {"type": "random"})

            if placement["type"] == "random":
                self.divide_cell_random_orientation(cell)

            elif placement["type"] == "angle":
                theta = math.radians(placement.get("angle_deg", 0))
                nx = math.cos(theta)
                ny = math.sin(theta)
                self.divide_cell_orientation_vector_based(cell, nx, ny, 0)

            elif placement["type"] == "vector":
                dx = placement.get("dx", 1)
                dy = placement.get("dy", 0)
                self.divide_cell_orientation_vector_based(cell, dx, dy, 0)


    # =========================
    # =========================
    def update_attributes(self):
        
        parent = self.parent_cell
        child = self.child_cell

        if parent is None or child is None:
            return
        
        request = parent.dict.get("_internal", {}).get("division_request")

        if not request:
            return

        # =========================
        # =========================
        parent_type = request.get("parent_type")
        child_type = request.get("child_type")

        if parent_type:
            parent.type = getattr(self, parent_type.upper())

        if child_type:
            child.type = getattr(self, child_type.upper())

        # =========================
        # =========================
        ratio = request.get("volume_ratio", 0.5)

        V_total = parent.volume + child.volume

        parent.targetVolume = V_total * ratio
        child.targetVolume  = V_total * (1 - ratio)

        parent.lambdaVolume = 20
        child.lambdaVolume  = 20

        # =========================
        # =========================
        parent.dict["requests"]["division"] = None

        parent.dict["_internal"]["division_request"] = None
        parent.dict["_internal"]["division_in_progress"] = False