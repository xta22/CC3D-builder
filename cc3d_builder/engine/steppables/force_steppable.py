# force_steppable.py
import math

from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.behaviour_stats import record_active_step, record_deactivation, set_metric


class ForceSteppable(SteppableBasePy):
    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        if self.engine is not None:
            self.engine.register_executor("force", self)

    def step(self, mcs):
        if self.cell_list is None:
            return

        for cell in self.cell_list:
            requests = cell.dict.setdefault("requests", {})
            request = None if self.engine is not None and self.engine.ordered_dispatch_enabled() else requests.get("force")
            active_request = cell.dict.get("active_force")

            if cell.dict.get("is_dead"):
                self._clear_force(cell, mcs)
                requests["force"] = None
                cell.dict.pop("active_force", None)
                continue

            current = request or active_request
            if not current:
                continue
            if active_request is current and cell.dict.get("_force_executed_mcs") == mcs:
                continue

            try:
                self.execute(cell, current, mcs)
            finally:
                if request is not None:
                    requests["force"] = None

    def execute(self, cell, request, mcs):
        self._execute_request(cell, request, mcs)
        cell.dict["_force_executed_mcs"] = mcs
        if request.get("persist"):
            cell.dict["active_force"] = dict(request)
        elif request.get("mode") == "clear":
            cell.dict.pop("active_force", None)
        elif "force" in cell.dict.get("requests", {}):
            cell.dict.pop("active_force", None)

    def _execute_request(self, cell, request, mcs):
        mode = str(request.get("mode", "vector")).strip().lower()
        if mode == "clear":
            self._clear_force(cell, mcs)
            cell.dict.pop("active_force", None)
            return

        direction = self._direction(cell, request, mode)
        if direction is None:
            if request.get("debug"):
                print(f"[ForceSteppable] No valid direction for cell {cell.id}, mode={mode}")
            return

        force = self._to_float(request.get("force", request.get("magnitude", 1.0)), 1.0)
        decay = self._to_float(request.get("decay", 1.0), 1.0)
        if decay != 1.0 and cell.dict.get("active_force"):
            force *= decay
            request["force"] = force

        self._apply_external_potential(cell, direction, force)
        record_active_step(cell, "force", mcs, abs(force))
        set_metric(cell, "force", "mode", mode)
        set_metric(cell, "force", "force", force)
        set_metric(cell, "force", "dir_x", direction[0])
        set_metric(cell, "force", "dir_y", direction[1])
        set_metric(cell, "force", "dir_z", direction[2])

        if request.get("debug"):
            print(
                f"[ForceSteppable] cell={cell.id} mode={mode} "
                f"dir=({direction[0]:.3f},{direction[1]:.3f},{direction[2]:.3f}) force={force}"
            )

    def _direction(self, cell, request, mode):
        if mode == "vector":
            return self._normalize((
                self._to_float(request.get("dx", request.get("x", 0.0)), 0.0),
                self._to_float(request.get("dy", request.get("y", 0.0)), 0.0),
                self._to_float(request.get("dz", request.get("z", 0.0)), 0.0),
            ))

        if mode == "stored_vector":
            prefix = str(request.get("vector_prefix", "orientation")).strip() or "orientation"
            return self._normalize((
                self._dict_number(cell, f"{prefix}_x", 1.0),
                self._dict_number(cell, f"{prefix}_y", 0.0),
                self._dict_number(cell, f"{prefix}_z", 0.0),
            ))

        if mode in {"toward_position", "away_from_position"}:
            target = (
                self._to_float(request.get("target_x", request.get("x", cell.xCOM)), cell.xCOM),
                self._to_float(request.get("target_y", request.get("y", cell.yCOM)), cell.yCOM),
                self._to_float(request.get("target_z", request.get("z", cell.zCOM)), cell.zCOM),
            )
            vec = (target[0] - cell.xCOM, target[1] - cell.yCOM, target[2] - cell.zCOM)
            if mode == "away_from_position":
                vec = (-vec[0], -vec[1], -vec[2])
            return self._normalize(vec)

        if mode == "toward_cell_id":
            target = self._cell_by_id(request.get("target_cell_id"))
            if target is None:
                return None
            return self._normalize((target.xCOM - cell.xCOM, target.yCOM - cell.yCOM, target.zCOM - cell.zCOM))

        if mode in {"toward_nearest_type", "away_from_nearest_type"}:
            target_type = request.get("target_type") or request.get("cell_type") or request.get("target_cell_type")
            target = self._nearest_cell_by_type(cell, target_type)
            if target is None:
                return None
            vec = (target.xCOM - cell.xCOM, target.yCOM - cell.yCOM, target.zCOM - cell.zCOM)
            if mode == "away_from_nearest_type":
                vec = (-vec[0], -vec[1], -vec[2])
            return self._normalize(vec)

        if mode == "toward_field_gradient":
            return self._field_gradient_direction(cell, request)

        return None

    def _apply_external_potential(self, cell, direction, force):
        # CC3D ExternalPotential uses the opposite sign: negative lambda pushes along +direction.
        cell.lambdaVecX = -force * direction[0]
        cell.lambdaVecY = -force * direction[1]
        cell.lambdaVecZ = -force * direction[2]

    def _clear_force(self, cell, mcs=None):
        cell.lambdaVecX = 0.0
        cell.lambdaVecY = 0.0
        cell.lambdaVecZ = 0.0
        if mcs is not None:
            record_deactivation(cell, "force", mcs)
            set_metric(cell, "force", "force", 0.0)

    def _cell_by_id(self, target_cell_id):
        try:
            target_id = int(float(target_cell_id))
        except (TypeError, ValueError):
            return None

        for candidate in self.cell_list:
            if candidate.id == target_id:
                return candidate
        return None

    def _nearest_cell_by_type(self, cell, type_name):
        type_id = self._cell_type_id(type_name)
        if type_id is None:
            return None

        best = None
        best_dist = float("inf")
        for candidate in self.cell_list_by_type(type_id):
            if candidate.id == cell.id:
                continue
            dist = (candidate.xCOM - cell.xCOM) ** 2 + (candidate.yCOM - cell.yCOM) ** 2 + (candidate.zCOM - cell.zCOM) ** 2
            if dist < best_dist:
                best = candidate
                best_dist = dist
        return best

    def _field_gradient_direction(self, cell, request):
        field_name = request.get("field_name") or request.get("field")
        if not field_name:
            return None

        try:
            field = getattr(self.field, str(field_name))
        except Exception:
            if request.get("debug"):
                print(f"[ForceSteppable] Field '{field_name}' is unavailable for gradient force")
            return None

        step = max(1, int(self._to_float(request.get("gradient_step", request.get("step", 1)), 1)))
        x = self._clamp_index(cell.xCOM, self.dim.x)
        y = self._clamp_index(cell.yCOM, self.dim.y)
        z = self._clamp_index(cell.zCOM, self.dim.z)

        x0, x1 = max(0, x - step), min(self.dim.x - 1, x + step)
        y0, y1 = max(0, y - step), min(self.dim.y - 1, y + step)
        z0, z1 = max(0, z - step), min(self.dim.z - 1, z + step)

        try:
            gx = float(field[x1, y, z]) - float(field[x0, y, z])
            gy = float(field[x, y1, z]) - float(field[x, y0, z])
            gz = 0.0 if self.dim.z <= 1 else float(field[x, y, z1]) - float(field[x, y, z0])
        except Exception:
            return None

        return self._normalize((gx, gy, gz))

    def _cell_type_id(self, type_name):
        if not type_name:
            return None
        type_attr = str(type_name).strip().upper()
        return getattr(self, type_attr, getattr(self.engine, type_attr, None))

    def _dict_number(self, cell, key, default):
        if key in cell.dict:
            return self._to_float(cell.dict.get(key), default)
        state = cell.dict.get("state", {})
        if isinstance(state, dict) and key in state:
            return self._to_float(state.get(key), default)
        return default

    def _normalize(self, vec):
        x, y, z = vec
        norm = math.sqrt(x * x + y * y + z * z)
        if norm <= 0.0 or not math.isfinite(norm):
            return None
        return (x / norm, y / norm, z / norm)

    def _clamp_index(self, value, upper):
        if upper <= 1:
            return 0
        return max(0, min(upper - 1, int(round(value))))

    def _to_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)
