# differentiate_steppable.py
import math
from cc3d.core.PySteppables import MitosisSteppableBase
from cc3d_builder.engine.core.behaviour_stats import record_event, set_metric, sync_event_count

class DifferentiateSteppable(MitosisSteppableBase):

    def __init__(self, frequency=1, engine=None):
        MitosisSteppableBase.__init__(self, frequency)
        self.engine = engine
        self.current_request = {}
        if self.engine is not None:
            self.engine.register_executor("differentiate", self)

    def step(self, mcs):
        self.current_mcs = mcs
        return

    def execute(self, cell, request, mcs):
        self.current_mcs = mcs
        mode = request.get("mode")

        if mode == "type_switch":
            self._execute_type_switch(cell, request, mcs)
        elif mode == "division":
            self._execute_division(cell, request, mcs)
        else:
            print(f"[DifferentiateSteppable] Unknown differentiate mode: {mode}")

    def _execute_type_switch(self, cell, request, mcs):
        new_type = request.get("new_type")

        if not new_type:
            return

        old_type = self.get_type_name_by_cell(cell)
        cell.type = getattr(self, new_type.upper())
        params = self.engine.celltype_params.get(new_type, {})

        cell.targetVolume = params.get("targetVolume", 50)
        cell.lambdaVolume = params.get("lambdaVolume", 10)
        record_event(cell, "type_switch", mcs)
        set_metric(cell, "type_switch", "from_type", old_type)
        set_metric(cell, "type_switch", "to_type", new_type)

    def _execute_division(self, cell, request, mcs):
        if "_internal" not in cell.dict:
            cell.dict["_internal"] = {}
        cell.dict["_internal"]["division_in_progress"] = True
        cell.dict["_internal"]["division_request"] = request

        self.current_request = request

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

    # ============================================================
    def update_attributes(self):
        """
        The official CC3D definition of the mitotic heart function: Precisely adjust the properties and state memory of mother and daughter cells here.
        """
        # ============================================================

        strategy = self.current_request.get("inheritance_strategy", "total")
        state_key = self.current_request.get("state_key", "division_count")
        mcs = getattr(self, "current_mcs", 0)
        parent_type = self.current_request.get("parent_type") or self.get_type_name_by_cell(self.parent_cell)
        child_type = self.current_request.get("child_type") or parent_type

        # The mother cell has successfully divided this time; its own count is first locked and then incremented.
        self.parent_cell.dict[state_key] = self.parent_cell.dict.get(state_key, 0) + 1

        # ============================================================
        if strategy == "total":
            # Mode 1: Full inheritance - multiple generations together, clock synchronized
            # Use the officially recommended clone_parent_2_child(), which performs a deep copy of all attributes including cell.dict to the daughter cells
            self.clone_parent_2_child()

            self.child_cell.dict[state_key] = self.parent_cell.dict[state_key]

        elif strategy == "reset":
            # Mode 2: Maternal inheritance, filial reset (asymmetric division / stem cell renewal)
            # Use clone_attributes with state_key excluded so daughter starts from a fresh count.
            self.clone_attributes(
                source_cell=self.parent_cell,
                target_cell=self.child_cell,
                no_clone_key_dict_list=[state_key]
            )

            self.child_cell.dict[state_key] = 0

        sync_event_count(self.parent_cell, "division", mcs, self.parent_cell.dict.get(state_key, 0))
        sync_event_count(self.child_cell, "division", mcs, self.child_cell.dict.get(state_key, 0))
        set_metric(self.parent_cell, "division", "state_key", state_key)
        set_metric(self.child_cell, "division", "state_key", state_key)

        self._apply_division_celltype(self.parent_cell, parent_type)
        self._apply_division_celltype(self.child_cell, child_type)

        auto_dilute_keys = ["phago_count", "absorbed_cargo", "internal_drug_concentration"]
        for k in auto_dilute_keys:

            if k in self.parent_cell.dict:
                old_val = self.parent_cell.dict[k]

                self.parent_cell.dict[k] = old_val / 2.0
                self.child_cell.dict[k] = old_val / 2.0
        # ============================================================
        # log
        # ============================================================
        if self.current_request.get("debug"):
            print(f"--- Mitosis Event Completed ---")
            print(f" Strategy Applied: {strategy}")
            print(f" Parent Cell (ID {self.parent_cell.id}) History Count: {self.parent_cell.dict.get(state_key)}")
            print(f" Child Cell  (ID {self.child_cell.id}) History Count: {self.child_cell.dict.get(state_key)}")

        for c in [self.parent_cell, self.child_cell]:
            if "_internal" in c.dict:
                c.dict["_internal"]["division_in_progress"] = False
                c.dict["_internal"]["division_request"] = None

    def _apply_division_celltype(self, cell, type_name):
        if not type_name:
            return

        try:
            cell.type = getattr(self, str(type_name).upper())
        except Exception:
            pass

        params = getattr(self.engine, "celltype_params", {}).get(str(type_name), {}) if self.engine else {}
        if "targetVolume" in params:
            cell.targetVolume = params["targetVolume"]
        if "lambdaVolume" in params:
            cell.lambdaVolume = params["lambdaVolume"]
