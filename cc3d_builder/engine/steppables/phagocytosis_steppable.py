# phagocytosis_steppable.py
from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.behaviour_stats import (
    record_active_step,
    set_metric,
    sync_event_count,
)


class PhagocytosisSteppable(SteppableBasePy):
    """
    Execute phagocytosis requests.

    RuleEngine handles rule matching and calls execute directly. This
    steppable owns the CC3D side effects: neighbor scan, volume transfer,
    and optional field leakage.
    """

    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        if self.engine is not None:
            self.engine.register_executor("phagocytosis", self)

    def step(self, mcs):
        return

    def execute(self, cell, request, mcs):
        self._execute_request(cell, request, mcs)

    def _execute_request(self, cell, request, mcs):
        phago_mode = request.get("phago_mode", "engulfment")
        eating_rate = self._to_float(request.get("eating_rate", 2.0), 2.0)
        leak_field = request.get("leak_field", "None")
        leak_amount = self._to_float(request.get("leak_amount", 0.0), 0.0)
        debug = request.get("debug", False)

        if phago_mode == "frustrated":
            self._execute_frustrated(cell, leak_field, leak_amount, debug, mcs)
            return

        target_type_id = self._cell_type_id(request.get("target_cell_type"))
        if target_type_id is None:
            print(f"[PhagocytosisSteppable] Unknown target cell type: {request.get('target_cell_type')}")
            return

        if phago_mode == "absorption":
            self._execute_absorption(cell, target_type_id, eating_rate, leak_field, leak_amount, debug, mcs)
        elif phago_mode == "engulfment":
            self._execute_engulfment(cell, target_type_id, eating_rate, leak_field, leak_amount, debug, mcs)
        else:
            print(f"[PhagocytosisSteppable] Unknown phagocytosis mode: {phago_mode}")

    def _execute_absorption(self, cell, target_type_id, eating_rate, leak_field, leak_amount, debug, mcs):
        for neighbor, _common_surface_area in self.getCellNeighborDataList(cell):
            if not neighbor or neighbor.type != target_type_id:
                continue

            completed, actual_eat = self._eat_neighbor(cell, neighbor, eating_rate)
            if actual_eat > 0:
                record_active_step(cell, "phagocytosis", mcs, actual_eat)
                set_metric(cell, "phagocytosis", "mode", "absorption")
                set_metric(cell, "phagocytosis", "last_target_type_id", target_type_id)

            self._leak_inside_cell(cell, leak_field, leak_amount)

            if completed:
                self._increment_phago_count(cell, debug, mcs)

    def _execute_engulfment(self, cell, target_type_id, eating_rate, leak_field, leak_amount, debug, mcs):
        for neighbor, _common_surface_area in self.getCellNeighborDataList(cell):
            if not neighbor or neighbor.type != target_type_id:
                continue

            completed, actual_eat = self._eat_neighbor(cell, neighbor, eating_rate)
            if actual_eat > 0:
                record_active_step(cell, "phagocytosis", mcs, actual_eat)
                set_metric(cell, "phagocytosis", "mode", "engulfment")
                set_metric(cell, "phagocytosis", "last_target_type_id", target_type_id)

            self._leak_at_com(cell, leak_field, leak_amount)

            if completed:
                self._increment_phago_count(cell, debug, mcs)

            break

    def _execute_frustrated(self, cell, leak_field, leak_amount, debug, mcs):
        for neighbor, _common_surface_area in self.getCellNeighborDataList(cell):
            if not neighbor:
                continue

            acted = False
            if neighbor.type == cell.type:
                self._move_cell_pixels(neighbor, cell)
                acted = True
                if debug:
                    print(f"[PhagocytosisSteppable] Cell {cell.id} merged pixels from cell {neighbor.id}")

            leak_delta = leak_amount * 2.0
            if self._should_leak(leak_field, leak_delta):
                self._leak_inside_cell(cell, leak_field, leak_delta)
                acted = True

            if acted:
                record_active_step(cell, "phagocytosis", mcs)
                set_metric(cell, "phagocytosis", "mode", "frustrated")
                set_metric(cell, "phagocytosis", "last_leak_field", leak_field)
                set_metric(cell, "phagocytosis", "last_leak_amount", leak_delta)

    def _eat_neighbor(self, cell, neighbor, eating_rate):
        actual_eat = min(eating_rate, neighbor.volume)
        if actual_eat <= 0:
            return False, 0.0

        neighbor.targetVolume = max(0.0, neighbor.targetVolume - actual_eat)
        cell.targetVolume += actual_eat

        if neighbor.volume <= 1:
            neighbor.targetVolume = 0.0
            return True, actual_eat

        return False, actual_eat

    def _cell_type_id(self, type_name):
        if not type_name:
            return None
        type_attr = str(type_name).upper()
        return getattr(self, type_attr, getattr(self.engine, type_attr, None))

    def _leak_inside_cell(self, cell, field_name, amount):
        if not self._should_leak(field_name, amount):
            return

        secretor = self._field_secretor(field_name)
        if not secretor:
            return

        secretor.secreteInsideCell(cell, amount)

    def _leak_at_com(self, cell, field_name, amount):
        if not self._should_leak(field_name, amount):
            return

        secretor = self._field_secretor(field_name)
        if not secretor:
            return

        secretor.secreteInsideCellAtCOM(cell, amount)

    def _field_secretor(self, field_name):
        try:
            getter = getattr(self, "get_field_secretor", None)
            if not getter and self.engine:
                getter = getattr(self.engine, "get_field_secretor", None)
            if not getter:
                print(f"[PhagocytosisSteppable] Secretor API is unavailable for field '{field_name}'")
                return None
            return getter(field_name)
        except Exception as exc:
            print(f"[PhagocytosisSteppable] Secretor for field '{field_name}' not found: {exc}")
            return None

    def _should_leak(self, field_name, amount):
        return bool(field_name and str(field_name).strip().lower() != "none" and amount != 0)

    def _move_cell_pixels(self, source_cell, target_cell):
        mover = getattr(self, "move_cell_pixels", None)
        if not mover and self.engine:
            mover = getattr(self.engine, "move_cell_pixels", None)

        if not mover:
            print("[PhagocytosisSteppable] move_cell_pixels API is unavailable")
            return

        mover(source_cell, target_cell)

    def _increment_phago_count(self, cell, debug, mcs):
        state_key = "phago_count"
        cell.dict[state_key] = cell.dict.get(state_key, 0) + 1
        sync_event_count(cell, "phagocytosis", mcs, cell.dict[state_key])
        set_metric(cell, "phagocytosis", "state_key", state_key)

        if debug:
            print(
                f"[PhagocytosisSteppable] Cell {cell.id} completed phagocytosis; "
                f"count={cell.dict[state_key]}"
            )

    def _to_float(self, value, default):
        if value in (None, ""):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
