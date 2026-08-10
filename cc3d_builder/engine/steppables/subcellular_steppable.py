# subcellular_steppable.py
from __future__ import annotations

import random
import re
from collections.abc import Mapping
from typing import Any

from cc3d.core.PySteppables import SteppableBasePy

from cc3d_builder.engine.core.behaviour_stats import record_active_step, set_metric
from cc3d_builder.engine.core.subcellular_state import (
    clean_subcellular_text,
    component_count,
    ensure_subcellular_system,
    localization_value,
    read_subcellular_value,
    set_component_count,
    set_localization_value,
    write_subcellular_value,
)


class SubcellularSteppable(SteppableBasePy):
    """Execute coarse-grained subcellular component/stage updates."""

    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        self._visualization_fields = {}
        if self.engine is not None:
            self.engine.register_executor("subcellular", self)

    def start(self):
        self._initialize_registered_systems(0)
        self._create_visualization_fields()
        self._update_visualization_fields(0)

    def step(self, mcs):
        if self.cell_list is None:
            return

        self._initialize_registered_systems(mcs)

        if self.engine is not None and self.engine.ordered_dispatch_enabled():
            self._update_visualization_fields(mcs)
            return

        for cell in list(self.cell_list):
            requests = cell.dict.setdefault("requests", {})
            queue = requests.get("subcellular", [])
            if not isinstance(queue, list) or not queue:
                continue
            try:
                for request in list(queue):
                    self.execute(cell, request, mcs)
            finally:
                requests["subcellular"] = []
        self._update_visualization_fields(mcs)

    def execute(self, cell, request, mcs):
        if cell is None:
            return False

        system = self._request_system(request)
        if not system:
            if request.get("debug"):
                print("[Subcellular] request missing system/subsystem")
            return False

        spec = self._system_spec(system)
        state = ensure_subcellular_system(cell, spec or system, mcs=mcs)
        action = str(request.get("action", "set_stage")).strip().lower()

        if action in {"initialize", "init"}:
            ok = True
        elif action == "set_stage":
            ok = self._set_stage(cell, system, request, mcs)
        elif action == "advance_stage":
            ok = self._advance_stage(cell, system, request, mcs)
        elif action in {"set_component", "set_count"}:
            ok = self._set_component(cell, system, request, mcs)
        elif action in {"increase_component", "add_component"}:
            ok = self._change_component(cell, system, request, mcs, sign=1)
        elif action in {"consume_component", "decrease_component"}:
            ok = self._change_component(cell, system, request, mcs, sign=-1)
        elif action == "set_localization":
            ok = self._set_localization(cell, system, request, mcs)
        elif action == "translocate":
            ok = self._translocate(cell, system, request, mcs)
        elif action == "set_value":
            ok = self._set_value(cell, system, request, mcs)
        elif action == "assemble":
            ok = self._assemble(cell, system, request, mcs)
        else:
            if request.get("debug"):
                print(f"[Subcellular] unknown action: {action}")
            return False

        if ok:
            state["last_action"] = action
            state["last_update_mcs"] = mcs
            record_active_step(cell, "subcellular", mcs)
            set_metric(cell, "subcellular", "system", system)
            set_metric(cell, "subcellular", "action", action)
        return bool(ok)

    def _initialize_registered_systems(self, mcs):
        if self.cell_list is None:
            return
        for spec in self._system_specs():
            attach = spec.get("attach_to", {}) if isinstance(spec.get("attach_to"), dict) else {}
            cell_types = attach.get("cell_types") or spec.get("cell_types") or []
            if isinstance(cell_types, str):
                cell_types = [part.strip() for part in cell_types.split(",") if part.strip()]
            if not cell_types:
                continue
            for cell_type in cell_types:
                type_id = getattr(self, str(cell_type).strip().upper(), None)
                if type_id is None:
                    continue
                for cell in self.cell_list_by_type(type_id):
                    ensure_subcellular_system(cell, spec, mcs=mcs)

    def _system_specs(self):
        if self.engine is None:
            return []
        return list(getattr(self.engine, "subcellular_systems", []) or [])

    def _create_visualization_fields(self):
        for system, metric, field_name in self._visualization_specs():
            if field_name in self._visualization_fields:
                continue
            try:
                self.create_scalar_field_cell_level_py(field_name)
                self._visualization_fields[field_name] = (system, metric)
            except Exception as exc:
                print(f"[Subcellular] could not create visualization field {field_name}: {exc}")

    def _update_visualization_fields(self, mcs):
        if self.cell_list is None:
            return
        if not self._visualization_fields:
            self._create_visualization_fields()
        if not self._visualization_fields:
            return

        stage_maps = {
            clean_subcellular_text(spec.get("id") or spec.get("name") or spec.get("system")): {
                clean_subcellular_text(stage): index
                for index, stage in enumerate(spec.get("stages", []) or [])
            }
            for spec in self._system_specs()
            if isinstance(spec, Mapping)
        }

        for field_name, (system, metric) in self._visualization_fields.items():
            field = getattr(self.field, field_name, None)
            if field is None:
                continue
            for cell in self.cell_list:
                state = cell.dict.get("subcellular", {}).get(system, {})
                value = 0.0
                if isinstance(state, dict):
                    metric_type, metric_key = metric
                    if metric_type == "stage":
                        stage = clean_subcellular_text(state.get("stage", ""))
                        value = float(stage_maps.get(system, {}).get(stage, 0))
                    elif metric_type == "active":
                        value = 1.0 if state.get("last_update_mcs") == mcs else 0.0
                    elif metric_type == "component":
                        value = self._to_float(state.get("components", {}).get(metric_key, 0.0), 0.0)
                    elif metric_type == "localization":
                        value = self._to_float(state.get("localization", {}).get(metric_key, 0.0), 0.0)
                try:
                    field[cell] = value
                except Exception:
                    pass

    def _visualization_specs(self):
        specs = []
        for spec in self._system_specs():
            if not isinstance(spec, Mapping):
                continue
            system = clean_subcellular_text(spec.get("id") or spec.get("name") or spec.get("system"))
            if not system:
                continue
            specs.append((system, ("stage", "stage"), self._field_name("SubcellularStage", system)))
            specs.append((system, ("active", "active"), self._field_name("SubcellularActive", system)))

            for component in self._component_names(spec):
                specs.append((system, ("component", component), self._field_name("SubcellularCount", system, component)))
            for location in self._localization_names(spec):
                specs.append((system, ("localization", location), self._field_name("SubcellularLoc", system, location)))
        return specs

    def _component_names(self, spec):
        values = spec.get("default_counts") or spec.get("components") or {}
        if isinstance(values, Mapping):
            return [clean_subcellular_text(key) for key in values.keys() if clean_subcellular_text(key)]
        if isinstance(values, list):
            names = []
            for item in values:
                if isinstance(item, Mapping):
                    name = item.get("id") or item.get("name") or item.get("component")
                else:
                    name = item
                name = clean_subcellular_text(name)
                if name:
                    names.append(name)
            return names
        return []

    def _localization_names(self, spec):
        values = spec.get("default_localization") or spec.get("localization") or {}
        if isinstance(values, Mapping):
            return [clean_subcellular_text(key) for key in values.keys() if clean_subcellular_text(key)]
        return []

    def _field_name(self, prefix, system, key=None):
        parts = [prefix, system]
        if key:
            parts.append(key)
        text = "_".join(clean_subcellular_text(part) for part in parts if clean_subcellular_text(part))
        text = re.sub(r"\W+", "_", text).strip("_")
        if not text or text[0].isdigit():
            text = f"Subcellular_{text}"
        return text[:64]

    def _system_spec(self, requested_name):
        requested = clean_subcellular_text(requested_name)
        for spec in self._system_specs():
            aliases = {
                clean_subcellular_text(spec.get("id", "")),
                clean_subcellular_text(spec.get("name", "")),
                clean_subcellular_text(spec.get("system", "")),
            }
            aliases.discard("")
            if requested in aliases:
                return spec
        return None

    def _request_system(self, request):
        return clean_subcellular_text(request.get("system") or request.get("subsystem") or request.get("id"))

    def _set_stage(self, cell, system, request, mcs):
        stage = request.get("stage", request.get("to_stage", request.get("value")))
        if stage is None:
            return False
        write_subcellular_value(cell, system, "stage", clean_subcellular_text(stage), mcs=mcs)
        return True

    def _advance_stage(self, cell, system, request, mcs):
        current = clean_subcellular_text(read_subcellular_value(cell, system, "stage", default="none"))
        from_stage = clean_subcellular_text(request.get("from_stage")) if request.get("from_stage") not in (None, "") else None
        if from_stage not in (None, "") and str(current) != str(from_stage):
            return False

        probability = self._to_float(request.get("probability", request.get("rate", 1.0)), 1.0)
        if probability < 1.0 and random.random() > max(0.0, probability):
            return False

        to_stage = clean_subcellular_text(request.get("to_stage") or request.get("stage") or self._next_stage(system, current))
        if not to_stage:
            return False
        write_subcellular_value(cell, system, "stage", to_stage, mcs=mcs)
        return True

    def _next_stage(self, system, current):
        spec = self._system_spec(system)
        stages = [clean_subcellular_text(item) for item in spec.get("stages", [])] if isinstance(spec, Mapping) else []
        current = clean_subcellular_text(current)
        if not isinstance(stages, list) or current not in stages:
            return None
        index = stages.index(current)
        if index + 1 >= len(stages):
            return current
        return stages[index + 1]

    def _set_component(self, cell, system, request, mcs):
        component = clean_subcellular_text(request.get("component") or request.get("variable"))
        if not component:
            return False
        value = request.get("value", request.get("count", 0))
        set_component_count(cell, system, component, self._to_float(value, 0.0), mcs=mcs)
        return True

    def _change_component(self, cell, system, request, mcs, sign):
        component = clean_subcellular_text(request.get("component") or request.get("variable"))
        if not component:
            return False
        amount = self._to_float(request.get("amount", request.get("delta", 1.0)), 1.0)
        current = self._to_float(component_count(cell, system, component, default=0.0), 0.0)
        next_value = current + sign * amount
        if request.get("floor_zero", True):
            next_value = max(0.0, next_value)
        set_component_count(cell, system, component, next_value, mcs=mcs)
        return True

    def _set_localization(self, cell, system, request, mcs):
        location = clean_subcellular_text(request.get("location") or request.get("to_location") or request.get("variable"))
        if not location:
            return False
        value = request.get("value", request.get("fraction", 0.0))
        set_localization_value(cell, system, location, self._to_float(value, 0.0), mcs=mcs)
        return True

    def _translocate(self, cell, system, request, mcs):
        from_location = clean_subcellular_text(request.get("from_location")) if request.get("from_location") else None
        to_location = clean_subcellular_text(request.get("to_location") or request.get("location"))
        if not to_location:
            return False
        amount = self._to_float(request.get("amount", request.get("fraction", 0.1)), 0.1)
        if from_location:
            source = self._to_float(localization_value(cell, system, from_location, 0.0), 0.0)
            moved = min(source, amount)
            set_localization_value(cell, system, from_location, source - moved, mcs=mcs)
        else:
            moved = amount
        target = self._to_float(localization_value(cell, system, to_location, 0.0), 0.0)
        set_localization_value(cell, system, to_location, target + moved, mcs=mcs)
        return True

    def _set_value(self, cell, system, request, mcs):
        variable = clean_subcellular_text(request.get("variable") or request.get("path") or request.get("key"))
        if not variable:
            return False
        write_subcellular_value(cell, system, variable, request.get("value", 0.0), mcs=mcs)
        return True

    def _assemble(self, cell, system, request, mcs):
        requirements = request.get("requires") or request.get("required_components") or {}
        if isinstance(requirements, str):
            requirements = {}
        for raw_component, amount in requirements.items():
            component = clean_subcellular_text(raw_component)
            if self._to_float(component_count(cell, system, component, 0.0), 0.0) < self._to_float(amount, 0.0):
                return False

        for raw_component, amount in requirements.items():
            component = clean_subcellular_text(raw_component)
            current = self._to_float(component_count(cell, system, component, 0.0), 0.0)
            set_component_count(cell, system, component, current - self._to_float(amount, 0.0), mcs=mcs)

        product = clean_subcellular_text(request.get("product") or request.get("component"))
        if product:
            current = self._to_float(component_count(cell, system, product, 0.0), 0.0)
            set_component_count(cell, system, product, current + self._to_float(request.get("amount", 1.0), 1.0), mcs=mcs)

        if request.get("to_stage") or request.get("stage"):
            self._set_stage(cell, system, request, mcs)
        return True

    def _to_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)
