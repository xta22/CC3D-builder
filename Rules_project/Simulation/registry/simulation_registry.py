import json
import os

class SimulationRegistry:

    def __init__(self, project_path):

        self.project_path = project_path

        self.rules_path = os.path.join(
            project_path,
            "Simulation",
            "config", 
            "rules.json"
        )
        self.xml_path = os.path.join(
            project_path,
            "Simulation",
            "Rules_project.xml"
        )

        self.rules = []

        self.cell_index = {}
        self.behaviour_index = {}
        self.celltype_params = {}

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

        if not os.path.exists(self.rules_path):
            self.rules = []
            self.celltype_params = {}
            return

        with open(self.rules_path, "r") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise Exception("Invalid rules.json format: expected dict")

        self.rules = data.get("rules", [])
        self.celltype_params = data.get("celltype_params", {})

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

        self.rules.append(rule)

        self._build_index()
        self.save()

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
    # MODIFY
    # ============================================================

    def update_rule(self, rule_id, new_rule):

        for i, r in enumerate(self.rules):
            if r["id"] == rule_id:
                self.rules[i] = new_rule
                break

        self._build_index()
        self.save()

    # ============================================================
    # SAVE JSON
    # ============================================================

    def save(self):
        with open(self.rules_path, "w") as f:
            json.dump({
                "rules": self.rules,
                "celltype_params": self.celltype_params
            }, f, indent=2)

    # ============================================================
    # ============================================================

    def export_to_xml(self):
            from core.structure_manager import StructureManager
            sm = StructureManager(self.project_path)

            for name in self.celltype_params.keys():
                sm.ensure_celltype(name)

            active_inits = {}
            for name, params in self.celltype_params.items():
                if params.get("should_initialize", True): # 默认初始化
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
                return True
        return False
    
    '''
    def export_to_internal_json(self):
        """Silently save current rules state in json."""
        internal_json_path = os.path.join(self.project_path,"Simulation", "config", "rules.json")
        
        # make sure config folder exists
        os.makedirs(os.path.dirname(internal_json_path), exist_ok=True)
        
        with open(internal_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.rules, f, indent=4, ensure_ascii=False)
    '''
    
    def load_from_internal_json(self):
        """When the software starts or a project is loaded, restore the rules from the internal JSON."""
        internal_json_path = os.path.join(self.project_path, "Simulation", "config", "rules.json")
        
        if os.path.exists(internal_json_path):
            with open(internal_json_path, 'r', encoding='utf-8') as f:
                self.rules = json.load(f)  
            return True
        return False