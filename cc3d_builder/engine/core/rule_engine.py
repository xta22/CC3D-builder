# rule_engine.py
import copy
from pathlib import Path
import math
import importlib.util
import sys
import pandas as pd

current_file = Path(__file__).resolve()
sim_dir = current_file.parents[1] # /Simulation
if str(sim_dir) not in sys.path:
    sys.path.insert(0, str(sim_dir))

from cc3d.core.PySteppables import *  # cc3d has its own built-in python interpreter

from cc3d_builder.engine.behaviour_plugins.growth_plugin import GrowthPlugin
from cc3d_builder.engine.behaviour_plugins.differentiate_plugin import DifferentiationPlugin
from cc3d_builder.engine.core.condition_evaluator import evaluate_condition
from cc3d_builder.engine.behaviour_plugins.create_plugin import CreatePlugin
from cc3d_builder.engine.behaviour_plugins.death_plugin import DeathPlugin
from cc3d_builder.engine.behaviour_plugins.secrete_uptake_plugin import SecreteUptakePlugin
from cc3d_builder.engine.behaviour_plugins.dormancy_plugin import DormancyPlugin
from cc3d_builder.engine.behaviour_plugins.phagocytosis_plugin import PhagocytosisPlugin
from cc3d_builder.engine.behaviour_plugins.chemotaxis_plugin import ChemotaxisPlugin
from cc3d_builder.engine.behaviour_plugins.force_plugin import ForcePlugin
from cc3d_builder.engine.behaviour_plugins.compartmentalize_plugin import CompartmentalizePlugin
from cc3d_builder.engine.behaviour_plugins.fpp_link_plugin import FPPLinkPlugin
from cc3d_builder.engine.behaviour_plugins.intracellular_model_plugin import IntracellularModelPlugin
from cc3d_builder.engine.behaviour_plugins.subcellular_plugin import SubcellularPlugin
from cc3d_builder.engine.core.intracellular_state import read_intracellular_value
from cc3d_builder.engine.core.subcellular_state import read_subcellular_value
from cc3d_builder.core.project_profile import load_json
from cc3d_builder.core.rule_schema import case_payload, first_case_payload, validate_rules_schema


INTRACELLULAR_GLOBAL_ACTIONS = {"step", "step_all", "timestep", "timestep_all", "global_step"}

class RuleEngineSteppable(SteppableBasePy):

    def __init__(self, frequency=1):
        super().__init__(frequency)

        self.rules = []
        self.script_cache = {}
        self.executors = {}
        self.execution_semantics = "snapshot"
        self.settings = {"execution_semantics": self.execution_semantics}
        self.celltype_params = {}
        self.intracellular_models = []
        self.subcellular_systems = []
        self.behaviour_registry = {
            "growth": GrowthPlugin(self),
            "differentiate": DifferentiationPlugin(self),
            "create": CreatePlugin(self),
            "death": DeathPlugin(self),
            "secrete/uptake": SecreteUptakePlugin(self),
            "dormancy": DormancyPlugin(self),
            "phagocytosis": PhagocytosisPlugin(self),
            "chemotaxis": ChemotaxisPlugin(self),
            "force": ForcePlugin(self),
            "compartmentalize": CompartmentalizePlugin(self),
            "fpp_link": FPPLinkPlugin(self),
            "intracellular_model": IntracellularModelPlugin(self),
            "subcellular": SubcellularPlugin(self),
        }

        self.audit_output_dir = Path("simulation_time_series")
        self._audit_buffer = []
        self._audit_final_exported = False

    def register_executor(self, behaviour, executor):
        self.executors[behaviour] = executor

    # ============================================================
    # INIT
    # ============================================================

    def _flatten_cell_dict(self, d, parent_key='', sep='_'):
        """Recursively flatten the extremely complex nested structure of cell.dict for seamless storage into a two-dimensional DataFrame."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_cell_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def _audit_all_cells(self, mcs):
        """Instantly, automatically, and transparently capture all digital states of all cells in the current MCS"""
        if self.cell_list is None:
            return

        for cell in self.cell_list:
            snapshot = {
                "MCS": mcs,
                "Cell_ID": cell.id,
                "Cell_Type": cell.type,
                "Volume": cell.volume,
                "TargetVolume": cell.targetVolume,
                "X_COM": cell.xCOM,
                "Y_COM": cell.yCOM,
                "Z_COM": cell.zCOM,
            }

            if cell.dict:
                snapshot.update(self._flatten_cell_dict(cell.dict))

            self._audit_buffer.append(snapshot)

    def _configure_audit_output_dir(self):
        try:
            base_path = Path(self.simulator.getBasePath())
            if base_path.name == "Simulation":
                base_path = base_path.parent
            self.audit_output_dir = base_path / "simulation_time_series"
        except Exception:
            self.audit_output_dir = Path("simulation_time_series")
        self.audit_output_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        self.load_rules()
        self._configure_audit_output_dir()

        self.tracked_fields = set()
        for rule in self.rules:
            for case in rule.get("cases", []):
                payload = case_payload(case)
                if rule.get("behaviour") == "secrete/uptake" and payload.get("total_count"):
                    f_name = payload.get("field_name")
                    if f_name:
                        self.tracked_fields.add(f_name)
                        print(f"📋 [Engine Init] Identified tracking requirement for field: '{f_name}'")

        self._apply_initial_celltype_constraints()

        for cell in self.cell_list:
            self._ensure_cell_dict(cell)
            self.initialize_cell_tracking_dict(cell)

        self._audit_all_cells(0)

    def on_stop(self):
        self.finish()

    def _apply_initial_celltype_constraints(self):
        if self.cell_list is None or not isinstance(self.celltype_params, dict):
            return

        applied = 0
        for type_name, params in self.celltype_params.items():
            if not isinstance(params, dict):
                continue

            type_id = getattr(self, str(type_name).strip().upper(), None)
            if type_id is None:
                continue

            for cell in self.cell_list_by_type(type_id):
                for key, attr in (
                    ("targetVolume", "targetVolume"),
                    ("lambdaVolume", "lambdaVolume"),
                    ("targetSurface", "targetSurface"),
                    ("lambdaSurface", "lambdaSurface"),
                    ("fluctAmpl", "fluctAmpl"),
                ):
                    if key not in params:
                        continue
                    try:
                        setattr(cell, attr, params[key])
                    except Exception:
                        pass
                applied += 1

        if applied:
            print(f"[RuleEngine] Applied celltype_params to {applied} initial cells.")

    def load_rules(self):

        project_dir = Path(self.simulator.getBasePath())
        rules_path = project_dir / "Simulation" / "rules.json"

        if not rules_path.exists():
            print(f"ℹ️ [RuleEngine] No rules.json found at {rules_path}")
            return

        data = load_json(rules_path, None)
        if data is None:
            print(f"⚠️ [RuleEngine] Empty or invalid rules.json at {rules_path}; running with no rules.")
            return

        if isinstance(data, list):
            data = {"rules": data}
        if not isinstance(data, dict):
            print(f"⚠️ [RuleEngine] Invalid rules.json format at {rules_path}; running with no rules.")
            return

        self.rules = data.get("rules", [])
        if not isinstance(self.rules, list):
            print(f"⚠️ [RuleEngine] Invalid rules list at {rules_path}; running with no rules.")
            self.rules = []
        validate_rules_schema(self.rules)

        self.celltype_params = data.get("celltype_params", {})
        self.intracellular_models = data.get("intracellular_models", [])
        self.subcellular_systems = data.get("subcellular_systems", [])
        self.settings = data.get("settings", {"execution_semantics": "snapshot"})
        if not isinstance(self.celltype_params, dict):
            self.celltype_params = {}
        if not isinstance(self.intracellular_models, list):
            self.intracellular_models = []
        if not isinstance(self.subcellular_systems, list):
            self.subcellular_systems = []
        if not isinstance(self.settings, dict):
            self.settings = {"execution_semantics": "snapshot"}
        self.execution_semantics = self._normalize_execution_semantics(
            self.settings.get("execution_semantics", "snapshot")
        )

    # ============================================================
    # STEP
    # ============================================================
    def step(self, mcs):
        self.current_mcs = mcs

        self._prepare_cells()

        if self.execution_semantics == "asynchronous":
            self._step_asynchronous(mcs)
        else:
            self._step_snapshot(mcs)

        if self._audit_interval_matches(mcs):
            self._audit_all_cells(mcs)
            if self._live_audit_export_interval_matches(mcs):
                self._export_audit_data(final=False)

    def _audit_interval_matches(self, mcs):
        try:
            interval = int(float(self.settings.get("audit_interval", 50)))
        except (TypeError, ValueError):
            interval = 50
        return interval > 0 and mcs > 0 and mcs % interval == 0

    def _live_audit_export_interval_matches(self, mcs):
        try:
            interval = int(float(self.settings.get("audit_export_interval", 0)))
        except (TypeError, ValueError):
            interval = 0
        return interval > 0 and mcs > 0 and mcs % interval == 0

    def _prepare_cells(self):
        for cell in self.cell_list:
            self._ensure_cell_dict(cell)
            if "persistent_tracking" not in cell.dict:
                self.initialize_cell_tracking_dict(cell)

    def _step_snapshot(self, mcs):
        events = []
        seq = 0
        for original_index, rule in self._ordered_rules():
            new_events = self._events_for_rule(rule, original_index, mcs, seq)
            events.extend(new_events)
            seq += len(new_events)

        events.sort(key=lambda event: (event["order"], event["seq"]))
        executed_once_rules = set()
        for event in events:
            if not self._dispatch_event(event, mcs):
                continue
            rule = event["rule"]
            if self._cell_once_rule(rule):
                self._mark_cell_once_triggered(event["cell"], rule)
            elif rule.get("once"):
                executed_once_rules.add(id(rule))

        for rule in self.rules:
            if id(rule) in executed_once_rules:
                rule["triggered"] = True

    def _step_asynchronous(self, mcs):
        seq = 0
        for original_index, rule in self._ordered_rules():
            events = self._events_for_rule(rule, original_index, mcs, seq)
            executed = False
            for event in events:
                event_executed = self._dispatch_event(event, mcs)
                if event_executed and self._cell_once_rule(rule):
                    self._mark_cell_once_triggered(event["cell"], rule)
                executed = event_executed or executed
            if executed and rule.get("once") and not self._cell_once_rule(rule):
                rule["triggered"] = True
            seq += len(events)

    def _events_for_rule(self, rule, original_index, mcs, seq_start):
        if self._global_once_triggered(rule):
            return []

        raw_freq = rule.get("frequency", 1)
        is_static_freq = not isinstance(raw_freq, dict)
        if is_static_freq and not self._frequency_matches(raw_freq, mcs):
            return []

        behaviour = rule.get("behaviour")
        order = self._rule_order(rule, original_index)

        if behaviour == "custom_script":
            if not is_static_freq and not self._frequency_matches(raw_freq, mcs, None):
                return []
            event = self._event(rule, None, None, order, seq_start, original_index)
            return [event]

        if behaviour == "create" or self._intracellular_global_rule(rule):
            events = self._global_events_for_rule(rule, mcs, is_static_freq, raw_freq, order, seq_start, original_index)
        else:
            events = self._cell_events_for_rule(rule, mcs, is_static_freq, raw_freq, order, seq_start, original_index)

        return events

    def _global_events_for_rule(self, rule, mcs, is_static_freq, raw_freq, order, seq_start, original_index):
        if not is_static_freq and not self._frequency_matches(raw_freq, mcs, None):
            return []

        events = []
        for case in rule.get("cases", []):
            if not evaluate_condition(case.get("when", {}), None, self):
                continue
            resolved_case = self._resolve_case(case, None)
            events.append(self._event(rule, resolved_case, None, order, seq_start, original_index))
            break
        return events

    def _cell_events_for_rule(self, rule, mcs, is_static_freq, raw_freq, order, seq_start, original_index):
        target = rule.get("target")
        behaviour = rule.get("behaviour")

        if not target:
            print(f"[Warning] Missing target for rule {rule.get('id')}")
            return []

        cells_to_process = self._target_cells(target)
        events = []

        for cell in cells_to_process:
            if cell.dict.get("is_dead", False):
                continue

            if cell.dict.get("dormant", False) and behaviour not in {"dormancy", "death"}:
                continue

            if self._cell_once_triggered(cell, rule):
                continue

            if not is_static_freq and not self._frequency_matches(raw_freq, mcs, cell):
                continue

            for case in rule.get("cases", []):
                if not evaluate_condition(case.get("when", {}), cell, self):
                    continue

                resolved_case = self._resolve_case(case, cell)
                events.append(self._event(rule, resolved_case, cell, order, seq_start + len(events), original_index))
                break

        return events

    def _event(self, rule, resolved_case, cell, order, seq, original_index):
        payload = case_payload(resolved_case) if isinstance(resolved_case, dict) else {}
        return {
            "rule": rule,
            "rule_id": rule.get("id"),
            "behaviour": rule.get("behaviour"),
            "case": resolved_case,
            "payload": payload,
            "cell": cell,
            "order": order,
            "seq": seq,
            "original_index": original_index,
        }

    def _cell_once_rule(self, rule):
        if not rule.get("once"):
            return False
        if rule.get("behaviour") in {"create", "custom_script"} or self._intracellular_global_rule(rule):
            return False
        return bool(rule.get("target"))

    def _global_once_triggered(self, rule):
        return bool(rule.get("once") and not self._cell_once_rule(rule) and rule.get("triggered"))

    def _cell_once_key(self, rule):
        rule_id = rule.get("id")
        if rule_id is None or str(rule_id).strip() == "":
            return f"{rule.get('behaviour', 'rule')}:{id(rule)}"
        return str(rule_id)

    def _cell_once_triggered(self, cell, rule):
        if not self._cell_once_rule(rule) or cell is None:
            return False
        self._ensure_cell_dict(cell)
        once_rules = cell.dict["_internal"].setdefault("once_rules", {})
        return bool(once_rules.get(self._cell_once_key(rule), False))

    def _mark_cell_once_triggered(self, cell, rule):
        if not self._cell_once_rule(rule) or cell is None:
            return
        self._ensure_cell_dict(cell)
        once_rules = cell.dict["_internal"].setdefault("once_rules", {})
        once_rules[self._cell_once_key(rule)] = True

    def _dispatch_event(self, event, mcs):
        behaviour = event["behaviour"]
        rule = event["rule"]
        cell = event["cell"]

        if behaviour == "custom_script":
            self.handle_custom_script_rule(rule)
            return True

        if cell is not None:
            if cell.dict.get("is_dead", False) and behaviour != "death":
                return False
            if cell.dict.get("dormant", False) and behaviour not in {"dormancy", "death"}:
                return False

        plugin = self.behaviour_registry.get(behaviour)
        executor = self.executors.get(behaviour)
        if not plugin:
            print(f"[RuleEngine] No plugin registered for behaviour '{behaviour}'")
            return False
        if not executor:
            print(f"[RuleEngine] No steppable executor registered for behaviour '{behaviour}'")
            return False

        request = plugin.apply(rule, event["case"], cell)
        if request is None:
            return False

        executor.execute(cell, request, mcs)
        return True

    def _ordered_rules(self):
        return list(enumerate(self.rules))

    def _rule_order(self, rule, original_index):
        return float(original_index)

    def _intracellular_global_rule(self, rule):
        if rule.get("behaviour") != "intracellular_model":
            return False
        payload = first_case_payload(rule)
        action = str(payload.get("action", "advance")).strip().lower()
        return action in INTRACELLULAR_GLOBAL_ACTIONS

    def _target_cells(self, target):
        target_text = str(target).strip()
        if target_text.lower() in {"global", "all", "*"}:
            return list(self.cell_list)
        return list(self.cell_list_by_type(getattr(self, target_text.upper(), 0)))

    def _frequency_matches(self, raw_freq, mcs, cell=None):
        try:
            freq = self._solve_frequency(raw_freq, cell)
        except (ValueError, TypeError):
            freq = 1
        return mcs % freq == 0

    def _normalize_execution_semantics(self, value):
        text = str(value or "snapshot").strip().lower()
        aliases = {
            "sync": "snapshot",
            "synchronous": "snapshot",
            "ordered": "snapshot",
            "async": "asynchronous",
        }
        text = aliases.get(text, text)
        if text not in {"snapshot", "asynchronous"}:
            print(f"[RuleEngine] Unknown execution_semantics='{value}', falling back to snapshot")
            return "snapshot"
        return text

    # ============================================================
    # CELL DICT INIT（
    # ============================================================

    def _ensure_cell_dict(self, cell):

        if "state" not in cell.dict:
            cell.dict["state"] = {}

        if "_internal" not in cell.dict:
            cell.dict["_internal"] = {}
        cell.dict["_internal"].setdefault("once_rules", {})

        if "behaviour_stats" not in cell.dict:
            cell.dict["behaviour_stats"] = {}
        if "intracellular" not in cell.dict:
            cell.dict["intracellular"] = {}
        if "subcellular" not in cell.dict:
            cell.dict["subcellular"] = {}


    def get_contact_ratio(self, cell, target_type_name):
        if cell is None or not target_type_name:
            return 0.0

        target_type_id = getattr(self, target_type_name.upper(), None)

        if target_type_id is None:
            print(f"[Warning] Unknown cell type: {target_type_name}")
            return 0.0

        target_contact_area = 0.0
        total_contact_area = 0.0

        neighbor_list = self.getCellNeighborDataList(cell)
        if neighbor_list:
            for neighbor, common_surface_area in neighbor_list:
                total_contact_area += common_surface_area
                if neighbor and neighbor.type == target_type_id:
                    target_contact_area += common_surface_area

        if total_contact_area > 0:
            return target_contact_area / total_contact_area

        return 0.0

    def get_min_distance_to_type(self, cell, target_type_name):
        target_type_id = getattr(self, target_type_name.upper(), None)
        if target_type_id is None:
            print(f"[Warning] Unknown cell type for distance calculation: {target_type_name}")
            return float('inf')

        min_distance = float('inf')

        try:
            target_cells = self.cell_list_by_type(target_type_id)
        except AttributeError:
            print("[Error] unable to retrieve the cell list.")
            return min_distance

        for target_cell in target_cells:
            if cell.id == target_cell.id:
                continue

            try:
                dist = self.distance(
                    cell.xCOM, cell.yCOM, cell.zCOM,
                    target_cell.xCOM, target_cell.yCOM, target_cell.zCOM
                )
            except AttributeError:
                dist = math.sqrt(
                    (cell.xCOM - target_cell.xCOM) ** 2 +
                    (cell.yCOM - target_cell.yCOM) ** 2 +
                    (cell.zCOM - target_cell.zCOM) ** 2
                )

            if dist < min_distance:
                min_distance = dist

        return min_distance

    def get_specific_surface_area(self, cell):
        """
        Specific Surface Area.
        Formula: Surface / Volume
        """
        try:
            surface = cell.surface
            volume = cell.volume

            if volume == 0:
                return 0.0

            return surface / volume
        except AttributeError:
            print(f"[Warning] Unable to retrieve the surface area or volume of cell {cell.id}. Please check whether the Surface and Volume plugins are enabled.")
            return 0.0

    def get_elongation_ratio(self, cell):
        """
        Compute the cell elongation (aspect ratio).
        Convert it using the underlying CC3D eccentricity.
        A perfect sphere has a value of 1.0, and the value increases as the shape becomes more elongated.
        """
        try:
            ecc = getattr(cell, 'eccentricity', getattr(cell, 'ecc', 0.0))

            if ecc < 0.0001:
                return 1.0

            if ecc > 0.999:
                return 30.0 # extremely elongated

            # Derive the aspect ratio from the physical definition of eccentricity.
            aspect_ratio = 1.0 / math.sqrt(1.0 - ecc**2)

            return aspect_ratio

        except AttributeError:
            print(f"[Warning] can not get the eccentricity of {cell.id}. Please check if the MomentOfInertia plugin in xml is enabled.")
            return 1.0

    def get_field_value(self, field_name, cell):
        """
        get the value in field
        """
        f = getattr(self.field, field_name, None)
        if f: return f[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]
        return 0.0

    def get_intracellular_value(self, cell, model_name, variable, default=0.0):
        return read_intracellular_value(cell, model_name, variable, default=default)

    def get_subcellular_value(self, cell, system, variable="stage", default=0.0):
        return read_subcellular_value(cell, system, variable, default=default)

    def handle_custom_script_rule(self, rule):
        payload = first_case_payload(rule)
        script_path_str = payload.get("script_path")
        raw_params = payload.get("apply_params", {})  # retrieve the dict that you wrote in UI

        if not script_path_str:
            print(f"❌ [CustomScript] Path error: {script_path_str}")
            return

        script_path = Path(script_path_str)

        if not script_path.exists():
            print(f"❌ [CustomScript] Path error: {script_path}")
            return

        try:
            # check the cache in case repetitively write in
            if script_path not in self.script_cache:
                spec = importlib.util.spec_from_file_location("custom_rule_mod", script_path)
                if spec is None or spec.loader is None:
                    print(f"[Custom Error] Cannot load module from {script_path}")
                    return False
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.script_cache[script_path] = module

            module = self.script_cache[script_path]

            # execute the script
            if hasattr(module, "match") and module.match(self):
                if hasattr(module, "run"):
                    cleaned_params = {}
                    for k, v in raw_params.items():
                        try:
                            # convert parameters to float
                            cleaned_params[k] = float(v) if isinstance(v, str) else v
                        except (ValueError, TypeError):
                            # if cant then stay the same
                            cleaned_params[k] = v
                    # self pass in as context, scripts are then able to call other functions.
                    module.run(self, cleaned_params)

        except Exception as e:
            print(f"[RuleEngine] Error executing script {script_path}: {e}")


    def initialize_cell_tracking_dict(self, cell):
        """Ensure that any cell has a valid zero value for the Field float."""
        cell.dict["persistent_tracking"] = {}
        for f_name in self.tracked_fields:
            cell.dict["persistent_tracking"][f_name] = 0.0

    def _resolve_dynamic_parameters(self, data, cell):
        """
        Recursive scanning of the case payload.
        Strings containing {state_key} placeholders are evaluated against the
        same state/native-cell context used by dynamic frequency expressions.
        """
        if cell is None:
            return data

        if isinstance(data, dict):
            resolved = {}
            local_vars = self._dynamic_parameter_context(cell)
            local_vars.update({k: v for k, v in data.items() if isinstance(v, (int, float))})

            for k, v in data.items():
                if isinstance(v, str) and "{" in v and "}" in v:
                    try:
                        expr = v
                        for key, value in sorted(local_vars.items(), key=lambda item: len(str(item[0])), reverse=True):
                            expr = expr.replace("{" + str(key) + "}", str(value))

                        # If the string still contains residual curly braces, substitute 0 as a fallback.
                        import re
                        expr = re.sub(r"\{.*?}", "0", expr)

                        # Execute dynamic mathematical computation
                        resolved[k] = float(eval(expr, {"__builtins__": None}, {"math": math, **local_vars}))
                    except Exception as e:
                        print(f"⚠️ [Engine Math Error] Failed to resolve express '{v}': {e}")
                        resolved[k] = v # If evaluation fails, keep the original value as a fallback.
                else:
                    # Recursive deep nesting.
                    resolved[k] = self._resolve_dynamic_parameters(v, cell)
            return resolved

        elif isinstance(data, list):
            return [self._resolve_dynamic_parameters(item, cell) for item in data]

        return data

    def _dynamic_parameter_context(self, cell):
        context = {
            "mcs": float(getattr(self, "current_mcs", 0)),
        }

        if cell is None:
            return context

        for key, value in self._flatten_cell_dict(cell.dict).items():
            if isinstance(value, bool):
                context[key] = float(value)
            elif isinstance(value, (int, float)) and math.isfinite(float(value)):
                context[key] = float(value)

        context.update(self._native_cell_context(cell))
        return context

    def _resolve_case(self, case, cell):
        """
        Resolve dynamic values inside a strict flat case and return a flat case.
        """
        payload = case_payload(copy.deepcopy(case))
        payload = self._resolve_dynamic_parameters(payload, cell)
        self._resolve_physical_model_values(payload, cell)
        return {"when": copy.deepcopy(case.get("when", {})), **payload}

    def _resolve_physical_model_values(self, target_dict, cell):
        """
        Resolve nested physical model dictionaries inside a case payload.

        The root case payload may itself contain a behaviour model key, such as
        growth's {"model": "linear", ...}. Only nested values that still use
        build_model's {"model": ..., "parameters": ...} structure are solved.
        """
        if not isinstance(target_dict, dict):
            return

        for key, value in list(target_dict.items()):
            if isinstance(value, dict):
                if "model" in value and "parameters" in value:
                    target_dict[key] = self._solve_physical_model(value, cell)
                else:
                    self._resolve_physical_model_values(value, cell)
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, dict) and "model" in item and "parameters" in item:
                        value[idx] = self._solve_physical_model(item, cell)
                    else:
                        self._resolve_physical_model_values(item, cell)

    def _solve_frequency(self, frequency_spec, cell):
        if not isinstance(frequency_spec, dict):
            return self._coerce_frequency(frequency_spec)

        if frequency_spec.get("type") == "state_feedback_frequency":
            return self._solve_state_feedback_frequency(frequency_spec, cell)

        # Backward fallback for old rules that stored a generic physical model
        # in rule["frequency"]. New CLI rules should use state_feedback_frequency.
        return self._coerce_frequency(self._solve_physical_model(frequency_spec, cell))

    def _solve_state_feedback_frequency(self, spec, cell):
        state_key = spec.get("state_key", "division_count")
        state_val = self._frequency_state_value(cell, state_key)
        mode = spec.get("mode", "linear")

        try:
            if mode == "exponential":
                base = float(spec.get("base_frequency", 1.0))
                factor = float(spec.get("factor", 1.25))
                value = base * (factor ** state_val)
            elif mode == "expression":
                expr = spec.get("expression", "1")
                context = self._frequency_context(cell, state_key, state_val)
                value = float(eval(expr, {"__builtins__": None}, context))
            else:
                base = float(spec.get("base_frequency", 1.0))
                slope = float(spec.get("slope", 1.0))
                value = base + slope * state_val
        except Exception as exc:
            print(f"[RuleEngine] Frequency feedback evaluation failed: {exc}")
            value = spec.get("min_frequency", 1.0)

        value = self._clamp_frequency(
            value,
            spec.get("min_frequency", 1.0),
            spec.get("max_frequency", 1000.0),
        )
        return self._coerce_frequency(value)

    def _frequency_state_value(self, cell, state_key):
        state_key = str(state_key)
        if state_key == "mcs":
            return float(getattr(self, "current_mcs", 0))

        if cell is None:
            return 0.0

        native_values = self._native_cell_context(cell)
        value = native_values.get(state_key)
        if value is None and state_key.startswith("cell."):
            attr_name = state_key.split(".", 1)[1]
            value = self._numeric_attr(cell, attr_name)
        if value is None:
            value = cell.dict.get(state_key)
        if value is None:
            value = self._flatten_cell_dict(cell.dict).get(state_key, 0.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _frequency_context(self, cell, state_key, state_val):
        context = {
            "math": math,
            "mcs": float(getattr(self, "current_mcs", 0)),
            "state": state_val,
            state_key: state_val,
        }

        if cell is not None:
            for key, value in self._flatten_cell_dict(cell.dict).items():
                if isinstance(value, (int, float, bool)):
                    context[key] = float(value)
            context.update(self._native_cell_context(cell))

        return context

    def _native_cell_context(self, cell):
        native_specs = {
            "cell_id": "id",
            "cell_type": "type",
            "type_id": "type",
            "volume": "volume",
            "surface": "surface",
            "targetVolume": "targetVolume",
            "lambdaVolume": "lambdaVolume",
            "targetSurface": "targetSurface",
            "lambdaSurface": "lambdaSurface",
            "xCOM": "xCOM",
            "yCOM": "yCOM",
            "zCOM": "zCOM",
            "xCM": "xCM",
            "yCM": "yCM",
            "zCM": "zCM",
            "eccentricity": "eccentricity",
            "ecc": "ecc",
            "cluster_id": "clusterId",
            "lambdaVecX": "lambdaVecX",
            "lambdaVecY": "lambdaVecY",
            "lambdaVecZ": "lambdaVecZ",
        }
        context = {}

        for variable_name, attr_name in native_specs.items():
            value = self._numeric_attr(cell, attr_name)
            if value is not None:
                context[variable_name] = value
                context[f"cell.{variable_name}"] = value

        return context

    def _numeric_attr(self, obj, attr_name):
        try:
            value = getattr(obj, attr_name)
        except Exception:
            return None

        if isinstance(value, bool):
            return float(value)

        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)

        return None

    def _clamp_frequency(self, value, min_frequency, max_frequency):
        try:
            min_val = float(min_frequency)
        except (TypeError, ValueError):
            min_val = 1.0

        try:
            max_val = float(max_frequency)
        except (TypeError, ValueError):
            max_val = 1000.0

        if max_val < min_val:
            min_val, max_val = max_val, min_val

        return max(min_val, min(max_val, float(value)))

    def _coerce_frequency(self, value):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 1.0

        if not math.isfinite(numeric) or numeric <= 0:
            numeric = 1.0

        return max(1, int(math.ceil(numeric)))

    def _solve_physical_model(self, model_dict, cell):
        """
        Regardless of which behavior or which physical parameter it belongs to,
        as long as it conforms to the format defined in build_model, it is uniformly processed here — real-time physical values are computed based on the current environmental inputs!
        """
        if not isinstance(model_dict, dict) or "model" not in model_dict:
            return model_dict

        model_type = model_dict["model"]
        regulator = model_dict["regulator"]
        params = model_dict["parameters"]

        regulators_list = regulator if isinstance(regulator, list) else [regulator]
        reg_vals = {r: self.get_field_value(r, cell) for r in regulators_list}

        if model_type == "hill":
            y_max = params["y_max"]
            y_min = params["y_min"]
            K = params["K"]
            n = params["n"]

            product_term = 1.0
            for field_name, val in reg_vals.items():
                if val <= 0:
                    coef = 0.0
                else:
                    coef = (val**n) / (K**n + val**n)
                product_term *= coef

            return y_min + (y_max - y_min) * product_term

        elif model_type == "linear":
            alpha = params["alpha"]

            if isinstance(alpha, list):
                total_linear_sum = 0.0
                for idx, field_name in enumerate(regulators_list):
                    val = reg_vals[field_name]
                    a_val = alpha[idx]
                    total_linear_sum += a_val * val
                return total_linear_sum
            else:
                primary_val = list(reg_vals.values())[0]
                return alpha * primary_val

        elif model_type == "expression":
            expr_str = params["expression"]
            try:
                local_env = {k: v for k, v in reg_vals.items()}
                local_env["math"] = math

                return float(eval(expr_str, {"__builtins__": None}, local_env))
            except Exception as e:
                print(f"❌ [Multi-Variable Expression Error] Failed to evaluate '{expr_str}': {e}")
                return 0.0

        return 0.0

    def finish(self):
        """When the user clicks Stop on the CC3D interface, or when the simulation ends naturally, the C++ engine will automatically invoke the callback."""
        print("\n[Rule Engine Auditor] Simulation finished. Exporting time-series sequence...")
        self._export_audit_data(final=True)

    def _export_audit_data(self, final=False):
        if final and self._audit_final_exported:
            return
        if not self._audit_buffer:
            if final:
                print("[Rule Engine Auditor] No tracking data to export.")
            return

        master_df = pd.DataFrame(self._audit_buffer)

        master_df = master_df.dropna(how='all', axis=1)

        global_file = self.audit_output_dir / "global_simulation_history.csv"
        master_df.to_csv(global_file, index=False)
        if final:
            print(f"[Rule Engine Auditor] Global full dataset exported to: {global_file}")

        unique_ids = master_df["Cell_ID"].unique()
        exported_cell_sequences = 0
        try:
            cell_limit = int(float(self.settings.get("audit_cell_sequence_limit", 3)))
        except (TypeError, ValueError):
            cell_limit = 3
        for c_id in unique_ids:
            if exported_cell_sequences < max(0, cell_limit):
                specific_df = master_df[master_df["Cell_ID"] == c_id]
                specific_file = self.audit_output_dir / f"cell_id_{c_id}_sequence.csv"
                specific_df.to_csv(specific_file, index=False)
                exported_cell_sequences += 1

        if final:
            self._audit_final_exported = True
            print(f"[Rule Engine Auditor] Data logging completed successfully. Cell trajectories exported: {exported_cell_sequences}\n")
