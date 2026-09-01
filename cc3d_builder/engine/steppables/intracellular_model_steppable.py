# intracellular_model_steppable.py
from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

from cc3d.core.PySteppables import SteppableBasePy

from cc3d_builder.engine.core.behaviour_stats import record_active_step, set_metric
from cc3d_builder.engine.core.intracellular_mapping import (
    apply_output_mapping,
    ensure_default_model_cache,
    model_alias,
    resolve_input_value,
)
from cc3d_builder.engine.core.intracellular_state import (
    live_model,
    read_intracellular_value,
    write_intracellular_value,
    write_live_model_value,
)


GLOBAL_STEP_ACTIONS = {"step", "step_all", "timestep", "timestep_all", "global_step"}


class IntracellularModelSteppable(SteppableBasePy):
    """Execute intracellular model requests emitted by RuleEngineSteppable."""

    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        self._initialized = False
        self._attached_cell_models: set[tuple[int, str]] = set()
        self._unavailable_model_specs: set[tuple[Any, ...]] = set()
        self._warned_model_issues: set[tuple[Any, ...]] = set()
        self._global_step_marks: set[tuple[int, str]] = set()
        self._visualization_fields: dict[str, tuple[str, str]] = {}
        if self.engine is not None:
            self.engine.register_executor("intracellular_model", self)

    def start(self):
        self._initialize_models()
        self._create_visualization_fields()
        self._update_visualization_fields(0)

    def step(self, mcs):
        if self.cell_list is None:
            return

        self._initialize_models()
        self._update_visualization_fields(mcs)

    def execute(self, cell, request, mcs):
        self._initialize_models()

        model_name = self._request_model_name(request)
        if not model_name:
            if request.get("debug"):
                print("[IntracellularModel] request missing model/model_name")
            return False

        spec = self._model_spec(model_name)
        if spec is None:
            if request.get("debug"):
                print(f"[IntracellularModel] model spec not found: {model_name}")
            return False

        action = str(request.get("action", "advance")).strip().lower()
        if action in GLOBAL_STEP_ACTIONS:
            return self._step_model_once(spec, request, mcs)

        if cell is None:
            if request.get("debug"):
                print(f"[IntracellularModel] action {action!r} needs a target cell")
            return False

        self._ensure_cell_model(cell, spec)

        if action == "sync_inputs":
            self._sync_inputs(cell, spec, request, mcs)
        elif action == "sync_outputs":
            self._sync_outputs(cell, spec, request, mcs)
        elif action == "reset":
            self._reset_model_cache(cell, spec, mcs)
        elif action == "set_variable":
            self._set_requested_variable(cell, spec, request, mcs)
        elif action == "advance":
            if request.get("sync_inputs", True):
                self._sync_inputs(cell, spec, request, mcs)
            if request.get("step_model", True):
                self._step_cell_or_global(cell, spec, request, mcs)
            if request.get("sync_outputs", True):
                self._sync_outputs(cell, spec, request, mcs)
        else:
            if request.get("debug"):
                print(f"[IntracellularModel] unknown action: {action}")
            return False

        record_active_step(cell, "intracellular_model", mcs)
        set_metric(cell, "intracellular_model", "model", model_alias(spec))
        set_metric(cell, "intracellular_model", "action", action)
        self._update_visualization_fields(mcs, cell)
        return True

    def _initialize_models(self):
        if self._initialized:
            return
        self._initialized = True
        for spec in self._model_specs():
            self._attach_to_configured_cells(spec)
        self._create_visualization_fields()

    def _model_specs(self):
        if self.engine is None:
            return []
        return list(getattr(self.engine, "intracellular_models", []) or [])

    def _model_spec(self, requested_name):
        requested = str(requested_name)
        for spec in self._model_specs():
            aliases = {
                str(spec.get("id", "")),
                str(spec.get("model_name", "")),
                str(spec.get("alias", "")),
            }
            aliases.discard("")
            if requested in aliases:
                return spec
        return None

    def _request_model_name(self, request):
        return str(request.get("model") or request.get("model_name") or request.get("id") or "").strip()

    def _attach_to_configured_cells(self, spec):
        attach = spec.get("attach_to", {}) if isinstance(spec.get("attach_to"), dict) else {}
        cell_types = (
            attach.get("cell_types")
            or spec.get("cell_types")
            or spec.get("attach_cell_types")
            or []
        )
        if isinstance(cell_types, str):
            cell_types = [part.strip() for part in cell_types.split(",") if part.strip()]

        for cell_type in cell_types:
            type_id = getattr(self, str(cell_type).strip().upper(), None)
            if type_id is None:
                print(f"[IntracellularModel] unknown attach cell type: {cell_type}")
                continue
            try:
                cells = list(self.cell_list_by_type(type_id))
            except Exception:
                cells = []
            for cell in cells:
                self._ensure_cell_model(cell, spec)

    def _ensure_cell_model(self, cell, spec):
        alias = model_alias(spec)
        if not alias:
            return False
        source_key = self._model_source_key(spec)
        if source_key in self._unavailable_model_specs:
            return False
        key = (int(getattr(cell, "id", -1)), alias)
        if key in self._attached_cell_models and live_model(cell, alias) is not None:
            return True

        attached = self._attach_model_to_cell(cell, spec)
        if attached:
            self._attached_cell_models.add(key)
            self._apply_initial_values(cell, spec)
            self._sync_outputs(cell, spec, {}, getattr(self.engine, "current_mcs", 0))
        return attached

    def _attach_model_to_cell(self, cell, spec):
        engine_name = str(spec.get("engine", "sbml")).strip().lower()
        alias = model_alias(spec)
        source = spec.get("source", {}) if isinstance(spec.get("source"), dict) else {}
        source_kind = str(source.get("kind") or spec.get("source_kind") or "file").strip().lower()

        method_name = self._attach_method_name(engine_name)
        method = getattr(self, method_name, None)
        if method is None:
            print(f"[IntracellularModel] CC3D API not available: {method_name}")
            return False

        kwargs = {
            "model_name": alias,
            "cell": cell,
            "step_size": spec.get("step_size", spec.get("solver", {}).get("step_size", 1.0) if isinstance(spec.get("solver"), dict) else 1.0),
        }

        if engine_name == "maboss":
            self._populate_maboss_source_kwargs(kwargs, spec, source, source_kind)
        else:
            self._populate_sbml_source_kwargs(kwargs, spec, source, source_kind)

        if not self._validate_attach_sources(kwargs, spec):
            return False

        return self._call_attach_method(method, kwargs, spec)

    def _attach_method_name(self, engine_name):
        if engine_name == "maboss":
            return "add_maboss_to_cell"
        if engine_name == "antimony":
            return "add_antimony_to_cell"
        if engine_name == "cellml":
            return "add_cellml_to_cell"
        return "add_sbml_to_cell"

    def _populate_sbml_source_kwargs(self, kwargs, spec, source, source_kind):
        if source_kind in {"inline", "string", "text"}:
            kwargs["model_string"] = source.get("text") or spec.get("model_string") or spec.get("source_text") or ""
        else:
            kwargs["model_file"] = self._resolve_model_path(source.get("path") or spec.get("path") or spec.get("model_file"))

    def _populate_maboss_source_kwargs(self, kwargs, spec, source, source_kind):
        if source_kind in {"inline", "string", "text"}:
            kwargs["bnd_str"] = (
                source.get("boolean_network_text")
                or spec.get("boolean_network_text")
                or source.get("bnd")
                or spec.get("bnd_str")
                or spec.get("bnd")
                or ""
            )
            kwargs["cfg_str"] = (
                source.get("simulation_configuration_text")
                or spec.get("simulation_configuration_text")
                or source.get("cfg")
                or spec.get("cfg_str")
                or spec.get("cfg")
                or ""
            )
        else:
            kwargs["bnd_file"] = self._resolve_model_path(
                source.get("boolean_network_path")
                or spec.get("boolean_network_path")
                or source.get("bnd_path")
                or spec.get("bnd_file")
                or spec.get("bnd_path")
            )
            kwargs["cfg_file"] = self._resolve_model_path(
                source.get("simulation_configuration_path")
                or spec.get("simulation_configuration_path")
                or source.get("configuration_path")
                or spec.get("configuration_path")
                or source.get("cfg_path")
                or spec.get("cfg_file")
                or spec.get("cfg_path")
            )

    def _resolve_model_path(self, raw_path):
        if not raw_path:
            return ""
        path = Path(str(raw_path)).expanduser()
        if path.is_absolute():
            return str(path)
        base = None
        try:
            base = Path(self.simulator.getBasePath()) / "Simulation"
        except Exception:
            pass
        if base is not None:
            candidate = base / path
            if candidate.exists():
                return str(candidate)
        return str(path)

    def _validate_attach_sources(self, kwargs, spec):
        source_key = self._model_source_key(spec)
        missing = []
        for key in ("model_file", "bnd_file", "cfg_file"):
            raw_path = kwargs.get(key)
            if not raw_path:
                continue
            path = Path(str(raw_path)).expanduser()
            if not path.exists():
                missing.append(str(path))

        if not missing:
            return True

        self._unavailable_model_specs.add(source_key)
        self._warn_once(
            ("missing_source", source_key),
            f"[IntracellularModel] source file not found for {model_alias(spec)}; skipping model attach: {', '.join(missing)}",
        )
        return False

    def _call_attach_method(self, method, kwargs, spec):
        kwargs = {key: value for key, value in kwargs.items() if value not in (None, "")}
        source_key = self._model_source_key(spec)
        if source_key in self._unavailable_model_specs:
            return False
        try:
            method(**self._supported_kwargs(method, kwargs))
            return True
        except Exception as exc:
            self._unavailable_model_specs.add(source_key)
            self._warn_once(
                ("attach_failed", source_key),
                f"[IntracellularModel] failed to attach {model_alias(spec)}; skipping further attempts: {exc}",
            )
            return False

    def _model_source_key(self, spec):
        source = spec.get("source", {}) if isinstance(spec.get("source"), dict) else {}
        source_kind = str(source.get("kind") or spec.get("source_kind") or "file").strip().lower()
        return (
            model_alias(spec),
            str(spec.get("engine", "sbml")).strip().lower(),
            source_kind,
            str(source.get("path") or spec.get("path") or spec.get("model_file") or ""),
            str(source.get("boolean_network_path") or spec.get("boolean_network_path") or spec.get("bnd_file") or ""),
            str(source.get("simulation_configuration_path") or spec.get("configuration_path") or spec.get("cfg_file") or ""),
        )

    def _warn_once(self, key, message):
        if key in self._warned_model_issues:
            return
        self._warned_model_issues.add(key)
        print(message)

    def _supported_kwargs(self, method, kwargs):
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            return kwargs
        if any(param.kind == param.VAR_KEYWORD for param in signature.parameters.values()):
            return kwargs
        return {key: value for key, value in kwargs.items() if key in signature.parameters}

    def _apply_initial_values(self, cell, spec):
        alias = model_alias(spec)
        values = spec.get("initial_conditions") or spec.get("initial_values") or {}
        if not isinstance(values, dict):
            return
        for variable, value in values.items():
            write_live_model_value(cell, alias, variable, value)
            write_intracellular_value(cell, alias, variable, value)

    def _sync_inputs(self, cell, spec, request, mcs):
        alias = model_alias(spec)
        for mapping in self._combined_mappings(spec, request, "inputs", "input_mappings"):
            variable = str(mapping.get("model_var") or mapping.get("variable") or "").strip()
            if not variable:
                continue
            value = resolve_input_value(mapping, cell, self.engine or self, alias, mcs)
            write_live_model_value(cell, alias, variable, value)
            write_intracellular_value(cell, alias, variable, value)

    def _sync_outputs(self, cell, spec, request, mcs):
        alias = model_alias(spec)
        outputs = self._combined_mappings(spec, request, "outputs", "output_mappings")
        for mapping in outputs:
            apply_output_mapping(mapping, cell, self.engine or self, alias, mcs)
        cache = ensure_default_model_cache(cell, alias, mcs)
        cache["last_sync_mcs"] = mcs

    def _create_visualization_fields(self):
        if not self._visualization_enabled():
            return
        for field_name, alias, variable in self._visualization_specs():
            if field_name in self._visualization_fields:
                continue
            try:
                self.create_scalar_field_cell_level_py(field_name)
                self._visualization_fields[field_name] = (alias, variable)
            except Exception as exc:
                print(f"[IntracellularModel] could not create visualization field {field_name}: {exc}")

    def _update_visualization_fields(self, mcs, single_cell=None):
        if not self._visualization_enabled():
            return
        if not self._visualization_fields:
            self._create_visualization_fields()
        if not self._visualization_fields or self.cell_list is None:
            return

        cells = [single_cell] if single_cell is not None else list(self.cell_list)
        for field_name, (alias, variable) in self._visualization_fields.items():
            field = getattr(self.field, field_name, None)
            if field is None:
                continue
            for cell in cells:
                if cell is None:
                    continue
                value = read_intracellular_value(cell, alias, variable, default=0.0)
                try:
                    field[cell] = self._to_float(value, 0.0)
                except Exception:
                    pass

    def _visualization_enabled(self):
        settings = getattr(self.engine, "settings", {}) if self.engine is not None else {}
        config = settings.get("intracellular_visualization", {}) if isinstance(settings, dict) else {}
        if isinstance(config, dict):
            return bool(config.get("enabled", True))
        return bool(config) if config not in (None, "") else True

    def _visualization_specs(self):
        specs = []
        seen = set()
        settings = getattr(self.engine, "settings", {}) if self.engine is not None else {}
        config = settings.get("intracellular_visualization", {}) if isinstance(settings, dict) else {}
        if not isinstance(config, dict):
            config = {}
        include_inputs = bool(config.get("include_inputs", False))
        include_initial_conditions = bool(config.get("include_initial_conditions", False))
        configured_variables = config.get("variables", {})

        for spec in self._model_specs():
            alias = model_alias(spec)
            if not alias:
                continue

            entries = []
            entries.extend(self._visualization_entries_from_mappings(spec.get("outputs") or spec.get("output_mappings") or []))
            entries.extend(self._visualization_entries_from_configured_variables(alias, configured_variables))
            if include_inputs:
                entries.extend(self._visualization_entries_from_mappings(spec.get("inputs") or spec.get("input_mappings") or []))
            if include_initial_conditions:
                entries.extend(
                    (str(variable), str(variable))
                    for variable in (spec.get("initial_conditions") or spec.get("initial_values") or {}).keys()
                )

            for variable, label in entries:
                if not variable:
                    continue
                key = (alias, variable, label)
                if key in seen:
                    continue
                seen.add(key)
                specs.append((self._field_name("Intracellular", alias, label or variable), alias, variable))
        return specs

    def _visualization_entries_from_mappings(self, mappings):
        if isinstance(mappings, dict):
            mappings = [mappings]
        entries = []
        for mapping in mappings or []:
            if not isinstance(mapping, dict):
                continue
            variable = str(mapping.get("model_var") or mapping.get("variable") or mapping.get("var") or "").strip()
            if not variable:
                continue
            label = str(mapping.get("target_key") or mapping.get("key") or variable).strip()
            entries.append((variable, label or variable))
        return entries

    def _visualization_entries_from_configured_variables(self, alias, configured_variables):
        if isinstance(configured_variables, dict):
            values = configured_variables.get(alias) or configured_variables.get("*") or []
        else:
            values = configured_variables
        if isinstance(values, str):
            values = [part.strip() for part in values.split(",") if part.strip()]
        entries = []
        for item in values or []:
            if isinstance(item, dict):
                variable = str(item.get("model_var") or item.get("variable") or item.get("name") or "").strip()
                label = str(item.get("label") or item.get("key") or variable).strip()
            else:
                variable = str(item).strip()
                label = variable
            if variable:
                entries.append((variable, label or variable))
        return entries

    def _field_name(self, prefix, model_name, variable):
        text = "_".join(str(part) for part in (prefix, model_name, variable) if str(part).strip())
        text = re.sub(r"\W+", "_", text).strip("_")
        if not text or text[0].isdigit():
            text = f"Intracellular_{text}"
        return text[:64]

    def _to_float(self, value, default=0.0):
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _combined_mappings(self, spec, request, primary_key, alternate_key):
        values = []
        for source in (spec, request):
            block = source.get(primary_key) or source.get(alternate_key) or []
            if isinstance(block, dict):
                block = [block]
            values.extend(item for item in block if isinstance(item, dict))
        return values

    def _step_cell_or_global(self, cell, spec, request, mcs):
        alias = model_alias(spec)
        local_model = live_model(cell, alias)
        if self._step_live_model(local_model):
            write_intracellular_value(cell, alias, "last_step_mcs", mcs)
            return True
        return self._step_model_once(spec, request, mcs)

    def _step_live_model(self, model):
        if model is None:
            return False
        for method_name in ("timestep", "step"):
            method = getattr(model, method_name, None)
            if not callable(method):
                continue
            try:
                method()
                return True
            except TypeError:
                try:
                    method(1)
                    return True
                except Exception:
                    continue
            except Exception:
                continue
        return False

    def _step_model_once(self, spec, request, mcs):
        alias = model_alias(spec)
        engine_name = str(spec.get("engine", "sbml")).strip().lower()
        current_mcs = int(mcs)
        self._global_step_marks = {
            mark for mark in self._global_step_marks if mark[0] == current_mcs
        }
        key = (current_mcs, engine_name)
        if key in self._global_step_marks:
            return True
        method_name = "timestep_maboss" if engine_name == "maboss" else "timestep_sbml"
        method = getattr(self, method_name, None)
        if method is None:
            print(f"[IntracellularModel] CC3D API not available: {method_name}")
            return False
        try:
            method()
            self._global_step_marks.add(key)
            if request.get("debug"):
                print(f"[IntracellularModel] global step completed for {alias} at MCS {mcs}")
            return True
        except Exception as exc:
            print(f"[IntracellularModel] global step failed for {alias}: {exc}")
            return False

    def _reset_model_cache(self, cell, spec, mcs):
        alias = model_alias(spec)
        cell.dict.setdefault("intracellular", {})[alias] = {"last_reset_mcs": mcs}
        self._apply_initial_values(cell, spec)

    def _set_requested_variable(self, cell, spec, request, mcs):
        alias = model_alias(spec)
        variable = request.get("model_var") or request.get("variable")
        if not variable:
            return
        value = request.get("value", 0.0)
        write_live_model_value(cell, alias, variable, value)
        write_intracellular_value(cell, alias, variable, value)
        write_intracellular_value(cell, alias, "last_set_mcs", mcs)

    def intracellular_value(self, cell, model_name, variable, default=0.0):
        return read_intracellular_value(cell, model_name, variable, default=default)
