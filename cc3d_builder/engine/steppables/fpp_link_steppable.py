# fpp_link_steppable.py
import math

from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.behaviour_stats import record_event, set_metric


class FPPLinkSteppable(SteppableBasePy):
    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        self._warned_fpp = False
        self._links_created = 0
        if self.engine is not None:
            self.engine.register_executor("fpp_link", self)

    def step(self, mcs):
        return

    def execute(self, cell, request, mcs):
        mode = str(request.get("mode", "nearest_type")).strip().lower()
        if mode in {"clear", "remove_all"}:
            self._clear_links(cell, request, mcs)
            return

        partners = self._resolve_partners(cell, request, mode)
        if not partners:
            if request.get("debug"):
                print(f"[FPPLinkSteppable] No partner found for cell={cell.id} mode={mode}")
            return

        created = 0
        for partner in partners:
            if partner is None or partner.id == cell.id:
                continue
            if self._link_exists(cell, partner):
                continue
            if self._create_link(cell, partner, request):
                created += 1

        if created:
            record_event(cell, "fpp_link", mcs, created)
            set_metric(cell, "fpp_link", "last_created", created)
            set_metric(cell, "fpp_link", "total_created", self._links_created)
            set_metric(cell, "fpp_link", "mode", mode)
            if request.get("debug"):
                print(
                    f"[FPPLinkSteppable] created={created} total={self._links_created} "
                    f"cell={cell.id} mode={mode}"
                )

    def _resolve_partners(self, cell, request, mode):
        if mode in {"cell_id", "target_cell_id", "by_id"}:
            target = self._cell_by_id(request.get("target_cell_id") or request.get("partner_cell_id"))
            return [target] if target is not None else []

        partner_type = request.get("partner_type") or request.get("target_type") or request.get("cell_type")
        if not partner_type:
            return []

        if mode in {"all_within_distance", "within_distance"}:
            return self._cells_by_type_within_distance(cell, partner_type, request)

        return [self._nearest_cell_by_type(cell, partner_type, request)]

    def _create_link(self, cell, partner, request):
        lambda_distance = self._to_float(request.get("link_lambda", request.get("lambda_distance", 10.0)), 10.0)
        target_distance = self._to_float(request.get("target_distance", 0.0), 0.0)
        max_distance = self._to_float(request.get("max_distance", 0.0), 0.0)
        try:
            link = self.new_fpp_link(cell, partner, lambda_distance, target_distance, max_distance)
            if link is None:
                if not self._warned_fpp:
                    print("[FPPLinkSteppable] FocalPointPlasticity plugin is not loaded; link skipped")
                    self._warned_fpp = True
                return False
            self._links_created += 1
            return True
        except Exception as exc:
            if request.get("debug") or not self._warned_fpp:
                print(f"[FPPLinkSteppable] Failed to create FPP link: {exc}")
                self._warned_fpp = True
            return False

    def _clear_links(self, cell, request, mcs):
        try:
            self.remove_all_cell_fpp_links(cell, links=True)
            record_event(cell, "fpp_link", mcs, 0)
            set_metric(cell, "fpp_link", "last_created", 0)
            set_metric(cell, "fpp_link", "mode", "clear")
        except Exception as exc:
            if request.get("debug"):
                print(f"[FPPLinkSteppable] Failed to clear FPP links for cell={cell.id}: {exc}")

    def _link_exists(self, cell, partner):
        try:
            return self.get_fpp_link_by_cells(cell, partner) is not None
        except Exception:
            return False

    def _cell_by_id(self, target_cell_id):
        try:
            target_id = int(float(target_cell_id))
        except (TypeError, ValueError):
            return None
        for candidate in self.cell_list:
            if candidate.id == target_id:
                return candidate
        return None

    def _nearest_cell_by_type(self, cell, type_name, request):
        type_id = self._cell_type_id(type_name)
        if type_id is None:
            return None

        max_distance = self._to_float(request.get("max_search_distance", request.get("search_radius", 0.0)), 0.0)
        max_dist_sq = max_distance * max_distance if max_distance > 0 else None
        best = None
        best_dist = float("inf")
        for candidate in self.cell_list_by_type(type_id):
            if candidate.id == cell.id or candidate.dict.get("is_dead"):
                continue
            dist = self._distance_sq(cell, candidate)
            if max_dist_sq is not None and dist > max_dist_sq:
                continue
            if dist < best_dist:
                best = candidate
                best_dist = dist
        return best

    def _cells_by_type_within_distance(self, cell, type_name, request):
        type_id = self._cell_type_id(type_name)
        if type_id is None:
            return []
        max_distance = self._to_float(request.get("max_search_distance", request.get("search_radius", 0.0)), 0.0)
        if max_distance <= 0:
            return []
        max_links = int(self._to_float(request.get("max_links", 1), 1))
        max_dist_sq = max_distance * max_distance
        candidates = []
        for candidate in self.cell_list_by_type(type_id):
            if candidate.id == cell.id or candidate.dict.get("is_dead"):
                continue
            dist = self._distance_sq(cell, candidate)
            if dist <= max_dist_sq:
                candidates.append((dist, candidate))
        candidates.sort(key=lambda item: item[0])
        return [candidate for _, candidate in candidates[:max_links]]

    def _distance_sq(self, cell_a, cell_b):
        return (
            (cell_a.xCOM - cell_b.xCOM) ** 2
            + (cell_a.yCOM - cell_b.yCOM) ** 2
            + (cell_a.zCOM - cell_b.zCOM) ** 2
        )

    def _cell_type_id(self, type_name):
        if not type_name:
            return None
        type_attr = str(type_name).strip().upper()
        return getattr(self, type_attr, getattr(self.engine, type_attr, None))

    def _to_float(self, value, default=0.0):
        if isinstance(value, dict):
            value = value.get("value", default)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default
