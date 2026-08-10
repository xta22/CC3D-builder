# create_steppable.py
import random
from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.behaviour_stats import record_event, set_metric


class CreateSteppable(SteppableBasePy):

    def __init__(self, frequency=1, engine=None):
        super().__init__(frequency)
        self.engine = engine
        if self.engine is not None:
            self.engine.register_executor("create", self)

    def step(self, mcs):
        if self.engine is None:
            return
        if self.engine.ordered_dispatch_enabled():
            return

        queue = self.engine.create_queue

        for req in queue:
            self._execute_create(req, mcs)

        self.engine.create_queue = []

    def execute(self, cell, req, mcs):
        self._execute_create(req, mcs)

    def _place_cell(self, type_id, cell_type, x, y, mcs=None):
        if self.engine is None:
            return None

        if self.cell_field is None:
            print("[Create] cell_field is not initialized")
            return None

        new_cell = self.new_cell(type_id)
        params = self.engine.celltype_params.get(cell_type, {})

        new_cell.targetVolume = params.get("targetVolume", 50)
        new_cell.lambdaVolume = params.get("lambdaVolume", 50)

        self.cell_field[x, y, 0] = new_cell

        if mcs is not None:
            new_cell.dict["created_mcs"] = mcs
            record_event(new_cell, "create", mcs)
            set_metric(new_cell, "create", "cell_type", cell_type)

        return new_cell

    # ============================================================
    # CREATE LOGIC
    # ============================================================

    def _execute_create(self, req, mcs):

        cell_type = req.get("cell_type")
        count = self._to_count(req.get("count", 1))

        if not cell_type:
            return

        try:
            type_id = getattr(self, cell_type.upper())
        except AttributeError:
            print(f"[Create] Unknown cell type: {cell_type}")
            return

        dist = req.get("distribution", {"type": "random"})
        dist_type = dist.get("type", "random")

        if dist_type == "random":
            created = self._create_random(type_id, cell_type, count, dist, mcs)

        elif dist_type == "cluster":
            created = self._create_cluster(type_id, cell_type, count, dist, mcs)

        elif dist_type == "stripe":
            created = self._create_stripe(type_id, cell_type, count, dist, mcs)

        else:
            print(f"[Create] Unknown distribution: {dist_type}")
            return

        if req.get("debug", False):
            print(
                f"[Create] MCS={mcs} type={cell_type} distribution={dist_type} "
                f"requested={count} created={created}"
            )

    # ============================================================
    # DISTRIBUTIONS
    # ============================================================

    def _create_random(self, type_id, cell_type, count, dist, mcs):
        if self.cell_field is None:
            print("[Create] cell_field is not initialized")
            return 0

        x_start = dist.get("x_start", 0)
        x_end   = dist.get("x_end", self.dim.x)

        y_start = dist.get("y_start", 0)
        y_end   = dist.get("y_end", self.dim.y)

        created = 0
        attempts = 0
        max_attempts = count * 20

        while created < count and attempts < max_attempts:

            x = random.randint(x_start, x_end - 1)
            y = random.randint(y_start, y_end - 1)

            if self.cell_field[x, y, 0] is None:
                self._place_cell(type_id, cell_type, x, y, mcs)
                created += 1

            attempts += 1

        return created

    def _create_stripe(self, type_id, cell_type, count, dist, mcs):

        direction = dist["direction"]
        coords = []

        # =========================
        # vertical
        # =========================
        if direction == "vertical":

            x = dist["x"]
            y_start = dist["y_start"]

            # -------- mode 1 --------
            if "y_end" in dist:

                y_end = dist["y_end"]

                if count <= 1:
                    ys = [(y_start + y_end) // 2]
                else:
                    step = (y_end - y_start) / (count - 1)
                    ys = [int(y_start + i * step) for i in range(count)]

            # -------- mode 2 --------
            elif "y_gap" in dist:

                gap = dist["y_gap"]
                ys = [y_start + i * gap for i in range(count)]

            else:
                raise Exception("Need y_end or y_gap")

            coords = [(x, y) for y in ys]

        # =========================
        # horizontal
        # =========================
        elif direction == "horizontal":

            y = dist["y"]
            x_start = dist["x_start"]

            if "x_end" in dist:

                x_end = dist["x_end"]

                if count <= 1:
                    xs = [(x_start + x_end) // 2]
                else:
                    step = (x_end - x_start) / (count - 1)
                    xs = [int(x_start + i * step) for i in range(count)]

            elif "x_gap" in dist:

                gap = dist["x_gap"]
                xs = [x_start + i * gap for i in range(count)]

            else:
                raise Exception("Need x_end or x_gap")

            coords = [(x, y) for x in xs]

        # =========================
        # create
        # =========================
        created = 0
        for x, y in coords:
            if 0 <= x < self.dim.x and 0 <= y < self.dim.y:
                if self._place_cell(type_id, cell_type, x, y, mcs):
                    created += 1

        return created

    def _create_cluster(self, type_id, cell_type, count, dist, mcs):

        if self.cell_field is None:
            print("[Create] cell_field is not initialized")
            return 0

        cx, cy = dist.get("center", [self.dim.x // 2, self.dim.y // 2])
        radius = dist.get("radius", 20)

        created = 0
        attempts = 0
        max_attempts = count * 20

        while created < count and attempts < max_attempts:

            dx = random.uniform(-radius, radius)
            dy = random.uniform(-radius, radius)

            x = int(cx + dx)
            y = int(cy + dy)

            if 0 <= x < self.dim.x and 0 <= y < self.dim.y:

                if self.cell_field[x, y, 0] is None:
                    self._place_cell(type_id, cell_type, x, y, mcs)
                    created += 1

            attempts += 1

        return created

    def _to_count(self, value):
        try:
            return max(0, int(float(value)))
        except (TypeError, ValueError):
            print(f"[Create] Invalid count: {value}")
            return 0
