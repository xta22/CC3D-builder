# rule_engine.py
import json
from pathlib import Path
import math
import importlib.util
import sys

current_file = Path(__file__).resolve()
sim_dir = current_file.parents[1] # /Simulation
if str(sim_dir) not in sys.path:
    sys.path.insert(0, str(sim_dir))

from cc3d.core.PySteppables import *  # cc3d has its own built-in python interpreter 

from cc3d_builder.engine.behaviour_plugins.growth_plugin import GrowthPlugin
from cc3d_builder.engine.behaviour_plugins.differentiate_plugin import DifferentiationPlugin
from cc3d_builder.engine.core.condition_evaluator import evaluate_condition
from cc3d_builder.engine.behaviour_plugins.create_plugin import CreatePlugin

class RuleEngineSteppable(SteppableBasePy):

    def __init__(self, frequency=1):
        super().__init__(frequency)

        self.rules = []
        self.create_queue = [] 
        self.script_cache = {}
        self.behaviour_registry = {
            "growth": GrowthPlugin(self),
            "differentiate": DifferentiationPlugin(self),
            "create": CreatePlugin(self), 
        }

    # ============================================================
    # INIT
    # ============================================================

    def start(self):
        self.load_rules()

    def load_rules(self):
        project_dir = Path(self.simulator.getBasePath())
        rules_path = project_dir / "Simulation" / "rules.json"
        
        if not rules_path.exists():
            print(f"ℹ️ [RuleEngine] No rules.json found at {rules_path}")
            return

        with rules_path.open('r', encoding='utf-8') as f:
            data = json.load(f)

        self.rules = data.get("rules", [])
        self.celltype_params = data.get("celltype_params", {})

    # ============================================================
    # STEP
    # ============================================================

    def step(self, mcs):
        print(f"DEBUG: MCS {mcs}, Number of rules: {len(self.rules)}")
        self.current_mcs = mcs

        for rule in self.rules:
            print(f"Rule ID: {rule.get('id')}, Triggered: {rule.get('triggered')}")
            freq = rule.get("frequency", 1)
            if mcs % freq != 0:
                continue
            # once logic
            if rule.get("once") and rule.get("triggered"):
                continue

            behaviour = rule["behaviour"]

            if behaviour == "custom_script":
                self.handle_custom_script_rule(rule)
                continue# skip the plugin logic

            # =========================
            # 🔵 GLOBAL （create） Create targets on cell doesn't exist yet, so it's exceptional.
            # =========================
            if behaviour == "create":

                if rule.get("once") and rule.get("triggered"):
                    continue

                for case in rule["cases"]:
                    print(f"DEBUG: Evaluating condition for case...")
                    if not evaluate_condition(case["when"], None, self):
                        continue

                    plugin = self.behaviour_registry.get(behaviour)
                    if not plugin:
                        continue

                    plugin.apply(rule, case, None)

                    if rule.get("once"):
                        rule["triggered"] = True

                    break

                continue

            # =========================
            # 🟢 CELL behaviour
            # =========================

            target = rule.get("target")

            # incase none corrupt
            if not target:
                print(f"[Warning] Missing target for rule {rule['id']}")
                continue

            try:
                target_id = getattr(self, target.upper())
            except AttributeError:
                print(f"[Warning] Unknown cell type: {target}")
                continue

            for cell in self.cell_list_by_type(target_id):

                for case in rule["cases"]:

                    if not evaluate_condition(case["when"], cell, self):
                        continue

                    plugin = self.behaviour_registry.get(behaviour)
                    if not plugin:
                        continue

                    plugin.apply(rule, case, cell)

                    if rule.get("once"):
                        rule["triggered"] = True

                    break

    # ============================================================
    # CELL DICT INIT（
    # ============================================================

    def _ensure_cell_dict(self, cell):

        if "state" not in cell.dict:
            cell.dict["state"] = {}

        if "requests" not in cell.dict:
            cell.dict["requests"] = {
                "growth": None,
                "type_switch": None,
                "division": None
            }

        if "_internal" not in cell.dict:
            cell.dict["_internal"] = {}


    def get_contact_ratio(self, cell, target_type_name):
        target_type_id = getattr(self, target_type_name.upper(), None)

        print(f"DEBUG: target={target_type_name}, id={target_type_id}")
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
            print(f"Cell {cell.id} contact ratio: {target_contact_area / total_contact_area}")
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
    
    def handle_custom_script_rule(self, rule):
        if "cases" in rule and len(rule["cases"]) > 0:
            case_apply = rule["cases"][0].get("apply", {})
            script_path_str = case_apply.get("script_path")
            raw_params = case_apply.get("apply_params", {})# retrieve the dict that you wrote in UI

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
