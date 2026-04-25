# simulation_registry.py
import json
from pathlib import Path
from cc3d_builder.core.structure_manager import StructureManager

class SimulationRegistry:

    def __init__(self, project_path,structure_manager=None):
        # here it is sandbox_dir from main.py and main_editor.py
        self.project_path = Path(project_path)
        self.sm = structure_manager

        self.rules_path = self.project_path / "Simulation" /"rules.json"
        self.xml_path = self.project_path / "Simulation" /"Rules_project.xml"
        self.py_path    = self.project_path / "Simulation" /"Rules_project_Steppables.py"
        # 暂时没用但是还是写着了
        self.rules = []
        self.cell_index = {}
        self.behaviour_index = {}
        self.celltype_params = {}
        self.field_params = {}

    def add_celltype_params(self, name, target, lam):
        self.celltype_params[name] = {
            "targetVolume": target,
            "lambdaVolume": lam
        }
        self.save()

    # ============================================================
    # LOAD
    # ============================================================

    def load(self):
        if not self.rules_path.exists():
            self.rules = []
            self.celltype_params = {}
            return

        with self.rules_path.open("r", encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise Exception("Invalid rules.json format: expected dict")

        self.rules = data.get("rules", [])
        self.celltype_params = data.get("celltype_params", {})
        
        if self.sm:
            self.sync_with_xml()
        
        self._build_index()

    # ============================================================
    # BUILD INDEX
    # ============================================================

    def _build_index(self):

        self.cell_index = {}
        self.behaviour_index = {}

        for rule in self.rules:
            cell = rule.get("target")
            behaviour = rule.get("behaviour")
            self.cell_index.setdefault(cell, []).append(rule)
            self.behaviour_index.setdefault(behaviour, []).append(rule)

    # ============================================================
    # ADD / UPDATE
    # ============================================================

    def add_rule(self, rule):
        print("before append:", len(self.rules), rule.get("id"), id(rule))
        self.rules.append(rule)
        print("after append:", len(self.rules))
        self._build_index()
        # self.save()

    # ============================================================
    # DELETE
    # ============================================================

    def delete_rule(self, rule_id):

        self.rules = [r for r in self.rules if r.get("id") != rule_id]
        self._build_index()
        self.save()

    # ============================================================
    # QUERY API
    # ============================================================

    def get_rule(self, rule_id):

        for r in self.rules:
            if r["id"] == rule_id:
                return r

        return None

    def get_rules_for_cell(self, cell_type):
        return self.cell_index.get(cell_type, [])

    def get_rules_for_behaviour(self, behaviour):
        return self.behaviour_index.get(behaviour, [])

    def list_all_rules(self):
        return self.rules

    # ============================================================
    # SAVE JSON
    # ============================================================

    def save(self):
        with open(self.rules_path, "w") as f:
            json.dump({
                "rules": self.rules,
                "celltype_params": self.celltype_params,
                "field_params": self.field_params
            }, f, indent=2)

    # ============================================================
    # ============================================================

    def export_to_xml(self):
            sm = StructureManager(self.project_path)

            for name in self.celltype_params.keys():
                sm.ensure_celltype(name)

            active_inits = {}
            for name, params in self.celltype_params.items():
                if params.get("should_initialize", True): # initialize by default
                    count = params.get("initial_count", 5)
                    active_inits[name] = count

            sm.update_initializers(active_inits)

            sm.save()
            print(f"✅ XML Updated: Initialized {list(active_inits.keys())}")

    def get_rule_by_id(self, rule_id):
        for rule in self.rules:
            if str(rule.get("id")) == str(rule_id):
                return rule
        return None
    
    def update_rule(self, rule_id, new_rule):
        for i, rule in enumerate(self.rules):
            if str(rule.get("id")) == str(rule_id):
                self.rules[i] = new_rule
                self._build_index() 
                self.save()
                print(f"✅ Rule {rule_id} updated and saved.")
                return True
        print(f"⚠️ Rule {rule_id} not found for update.")    
        return False
    
    def load_from_internal_json(self):
        """When the software starts or a project is loaded, restore the rules from the internal JSON."""
        if self.rules_path.exists():
            with self.rules_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
                self.rules = data.get("rules", []) if isinstance(data, dict) else data
            return True
        return False

    def sync_with_xml(self):
        """
        Syncronize the celltypes in XML to registry,
        if there didn't exist then initialize them 
        """
        if self.sm is None:
            print("⚠️ [Sync] StructureManager not provided, skipping sync.")
            return

        xml_names = self.sm.get_xml_cell_types()
        xml_fields = self.sm.get_all_fields_from_xml()
        modified = False
        for name in xml_names:
            if name not in self.celltype_params:
                print(f"🔗 [Sync] Adding XML cell type to registry: {name}")
                self.celltype_params[name] = {
                    "should_initialize": True,
                    "initial_count": 5,   
                    "targetVolume": 50.0,
                    "lambdaVolume": 2.0
                }
                modified = True

        for f_name, params in xml_fields.items():
        # 如果 registry 内存里还没这个场，或者你想以 XML 为准
            self.field_params[f_name] = params
        
        if modified:
            self.save() 


    def add_field_params(self, field_name, params):
        # 统一转换函数：不管传进来是大写还是小写，都存成小写
        def get_val(keys, default):
            for k in keys:
                if k in params: return params[k]
            return default

        # 强制归一化存储
        normalized = {
            "solver": get_val(["solver", "Solver"], "DiffusionSolverFE"),
            "diffusion_constant": get_val(["diffusion_constant", "GlobalDiffusionConstant"], 0.1),
            "decay_constant": get_val(["decay_constant", "GlobalDecayConstant"], 0.001),
            "initial_expression": get_val(["initial_expression", "InitialConcentrationExpression"], "0.0"),
            "boundary_conditions": get_val(["boundary_conditions", "BoundaryConditions"], {}),
            "chemotaxis": get_val(["chemotaxis", "Chemotaxis"], [])
        }

        # 🛡️ 关键防线：如果新 params 里没 BC（比如是空的），但 Registry 里旧的有，一定要保留！
        if not normalized["boundary_conditions"] and field_name in self.field_params:
            normalized["boundary_conditions"] = self.field_params[field_name].get("boundary_conditions", {})

        self.field_params[field_name] = normalized
        self.save()

    # 在 SimulationRegistry 类内部添加：

    def get_all_fields(self):
        """返回所有场的字典 {field_name: params_dict}"""
        # 假设你的 Registry 里存储场数据的变量名是 self.field_params
        print(f"DEBUG: Current field_params in registry: {self.field_params}")
        return self.field_params

    def get_field_params(self, field_name):
        """根据名称获取单个场的配置参数"""
        return self.field_params.get(field_name, {})

    def update_field(self, field_name, new_data):
        """更新某个场的配置数据"""
        if field_name in self.field_params:
            self.field_params[field_name].update(new_data)
        else:
            self.field_params[field_name] = new_data
        self.save() # 别忘了更新完存一下 JSON