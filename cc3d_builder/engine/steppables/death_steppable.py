# death_steppable.py
from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.behaviour_stats import (
    record_active_step,
    record_activation,
    record_event,
    set_metric,
)


class DeathSteppable(SteppableBasePy):
    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        # Initialize a scalar field used to control cell display colors in the Player
        # 0.0 = healthy
        # 1.0 = apoptotic
        # 2.0 = necrotic swelling
        # 3.0 = post-rupture necrotic shrinking
        self.create_scalar_field_cell_level_py("DeathStatus")
        if self.engine is not None:
            self.engine.register_executor("death", self)

    def step(self, mcs):
        if self.cell_list is None:
            return

        field = self.field.DeathStatus

        for cell in self.cell_list:
            if cell.dict.get("is_dead"):
                self._clear_non_death_state(cell)

            # ========================================================
            # Continuous state of dead cells.
            # ========================================================
            state = cell.dict.get("death_state")
            if not state:
                field[cell] = 0.0
                continue

            record_active_step(cell, "death", mcs)
            set_metric(cell, "death", "state", state)
            params = cell.dict.get("death_params", {})

            # ------- The apoptotic cell continues shrinking -------
            if state == "apoptosis":
                shrink_rate = self._to_float(params.get("shrink_rate", 0.95), 0.95)
                terminal_volume = self._to_float(params.get("terminal_volume", 0.0), 0.0)
                stop_threshold = max(terminal_volume, 1.0)
                cell.targetVolume *= shrink_rate

                if cell.targetVolume <= stop_threshold:
                    if self._as_bool(params.get("delete_on_terminal", False)):
                        self.delete_cell(cell)
                        continue
                    cell.targetVolume = terminal_volume
                    cell.lambdaVolume = 100.0

            # ------- The necrotic cell continues swelling -------
            elif state == "necrosis_swelling":
                swell_rate = self._to_float(params.get("swell_rate", 1.05), 1.05)
                cell.targetVolume *= swell_rate

                max_vol = self._to_float(params.get("max_target_volume", 150.0), 150.0)
                if cell.targetVolume >= max_vol:
                    # Instantly trigger chemical release.
                    release_fields = params.get("fields", [])
                    for f_info in release_fields:
                        self._release_field(cell, f_info)

                    cell.dict["death_state"] = "necrosis_shrinking"
                    field[cell] = 3.0

            # ------- Switch to shrinking after rupture -------
            elif state == "necrosis_shrinking":
                post_shrink = self._to_float(params.get("post_burst_shrink_rate", 0.8), 0.8)
                cell.targetVolume *= post_shrink

                if cell.targetVolume < 1.0:
                    if self._as_bool(params.get("delete_on_terminal", False)):
                        self.delete_cell(cell)
                        continue
                    cell.targetVolume = 0.0
                    cell.lambdaVolume = 100.0

    def execute(self, cell, req, mcs):
        self._start_death_program(cell, req, self.field.DeathStatus, mcs)

    def _start_death_program(self, cell, req, field, mcs):
        mode = req.get("mode")
        params = req.get("params", {})

        if mode == "apoptosis":
            cell.dict["death_state"] = "apoptosis"
            field[cell] = 1.0
        elif mode == "necrosis":
            cell.dict["death_state"] = "necrosis_swelling"
            field[cell] = 2.0
        else:
            print(f"[DeathSteppable] Unknown death mode: {mode}")
            return

        cell.dict["is_dead"] = True
        cell.dict["death_params"] = params
        record_event(cell, "death", mcs)
        record_activation(cell, "death", mcs)
        set_metric(cell, "death", "mode", mode)
        set_metric(cell, "death", "state", cell.dict["death_state"])
        self._clear_non_death_state(cell)

        if req.get("debug"):
            print(f"[DeathSteppable] Cell {cell.id} entered {mode} program")

    def _clear_non_death_state(self, cell):
        cell.dict.pop("active_force", None)

    def _release_field(self, cell, field_info):
        if not isinstance(field_info, dict):
            return

        field_name = field_info.get("field_name")
        if not field_name or not hasattr(self.field, field_name):
            return

        amount = self._to_float(field_info.get("amount", 0.0), 0.0)
        if amount == 0:
            return

        field = getattr(self.field, field_name)
        field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)] += amount

    def _to_float(self, value, default):
        if value in (None, ""):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _as_bool(self, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
