from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QPushButton,
    QInputDialog, QApplication, QMessageBox, QFileDialog
)
import sys
import os
from core.rule_builder import build_rule
from core.csv_importer import import_rules_from_csv
from utils_extensions.utils import extract_celltypes_from_rule
from core.structure_manager import StructureManager
from injector.steppable_injector import SteppableInjector
from injector.inject import process_and_inject_rule

current_file_path = os.path.abspath(__file__) 

gui_dir = os.path.dirname(current_file_path)
builder_root = os.path.dirname(gui_dir) 
if builder_root not in sys.path:
    sys.path.insert(0, builder_root)
    print(f"✅ Dynamic Builder Root: {builder_root}")

class MainWindow(QWidget):

    def __init__(self, registry=None):
        
        super().__init__()
        print(">>> ENTER MAIN WINDOW INIT <<<")
        self.registry = registry

        layout = QVBoxLayout()

        self.rule_list = QListWidget()

        self.add_btn = QPushButton("Add Rule")
        self.save_btn = QPushButton("Save")
        self.exit_btn = QPushButton("Exit")
        self.manage_rules_btn = QPushButton("Manage Rules (Table View)")
        self.manage_rules_btn.clicked.connect(self.open_manage_rules)


        self.add_btn.clicked.connect(self.add_rule)
        self.save_btn.clicked.connect(self.save)
        self.import_btn = QPushButton("Import Rules CSV")
        self.exit_btn.clicked.connect(self.close)  
        self.import_btn.clicked.connect(self.clicked_import_csv)
        

        layout.addWidget(self.manage_rules_btn)
        layout.addWidget(self.rule_list)
        layout.addWidget(self.add_btn)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.exit_btn)
        layout.addWidget(self.import_btn)

        self.setLayout(layout)

        if self.registry:
            self.refresh_list()

    # ============================================================
    # RULE LIST
    # ============================================================

    def refresh_list(self):
        if not self.registry:
            return

        self.rule_list.clear()

        for r in self.registry.rules:
            rid = r.get("id", "?")
            behaviour = r.get("behaviour", "?")
            target = r.get("target", "global")

            self.rule_list.addItem(f"{rid} | {behaviour} | {target}")

    def generate_rule_id(self):
        if not self.registry or not self.registry.rules:
            return "1"

        ids = [int(r.get("id", 0)) for r in self.registry.rules if r.get("id", "").isdigit()]
        return str(max(ids) + 1 if ids else 1)

    def ask_celltype_params_gui(self, name):

        target, ok = QInputDialog.getDouble(
            self,
            f"New CellType: {name}",
            "targetVolume:",
            50
        )
        if not ok:
            return None

        lam, ok = QInputDialog.getDouble(
            self,
            f"New CellType: {name}",
            "lambdaVolume:",
            10
        )
        if not ok:
            return None

        return {
            "targetVolume": target,
            "lambdaVolume": lam
        }
    
    def confirm_rule(self, rule, new_types):
        """show rules for users to confirm"""
        rule_id = rule.get("id", "?")
        behaviour = rule.get("behaviour", "?")
        
        message = f"📋 Rule Summary\n\n"
        message += f"ID: {rule_id}\n"
        message += f"Behaviour: {behaviour}\n"
        message += f"Target: {rule.get('target', 'global')}\n"
        
    
        if rule.get('when'):
   
            when = rule.get('when', {})
            if when.get('type') == 'time_window':
                message += f"Condition: time {when.get('start')} - {when.get('end')}\n"
            else:
                message += f"Condition: always true\n"
        elif rule.get('cases') and len(rule['cases']) > 0:
      
            when = rule['cases'][0].get('when', {})
            if when.get('type') == 'time_window':
                message += f"Condition: time {when.get('start')} - {when.get('end')}\n"
            else:
                message += f"Condition: always true\n"
        else:
            message += f"Condition: unknown\n"
        
        
        message += f"\n📝 Rule Details:\n"
        
    
        apply_block = None
        if 'apply' in rule:
           
            apply_block = rule['apply']
        elif 'cases' in rule and len(rule['cases']) > 0 and 'apply' in rule['cases'][0]:
       
            apply_block = rule['cases'][0]['apply']
       
        if behaviour == "growth":
            if apply_block:
                message += f"  • Regulator: {apply_block.get('regulator', '?')}\n"
                message += f"  • Model: {apply_block.get('model', '?')}\n"
                
                parameters = apply_block.get('parameters', {})
                model_type = apply_block.get('model', '')
                
                if model_type == "linear":
                    message += f"  • Alpha: {parameters.get('alpha', '?')}\n"
                elif model_type == "hill":
                    message += f"  • Ymin: {parameters.get('y_min', '?')}\n"
                    message += f"  • Ymax: {parameters.get('y_max', '?')}\n"
                    message += f"  • K: {parameters.get('K', '?')}\n"
                    message += f"  • n: {parameters.get('n', '?')}\n"
                elif model_type == "expression":
                    params = apply_block.get('parameters', {})
                    expr_val = params.get('expression', apply_block.get('expression', '?')) 
                    message += f"  • Expression: {expr_val}\n"
            else:
                message += f"  • No apply block found\n"
                
        elif behaviour == "differentiate":
            if apply_block:
                mode = apply_block.get('mode', '?')
                message += f"  • Mode: {mode}\n"
                
                if mode == 'type_switch':
                    message += f"  • New Type: {apply_block.get('new_type', '?')}\n"
                else:  # division
                    p_type = apply_block.get('parent_type', '?')
                    c_type = apply_block.get('child_type', '?')
                    if p_type == c_type:
                        message += f"  • Division: Symmetric ({p_type})\n"
                    else:
                        message += f"  • Division: Asymmetric ({p_type} and {c_type})\n"
                    
                    message += f"  • Volume Ratio: {apply_block.get('volume_ratio', '?')}\n"
                    
                    placement = apply_block.get('placement', {})
                    place_type = placement.get('type', 'random')
                    message += f"  • Placement: {place_type}\n"
            else:
                message += "  • Error: No Differentiate data found\n"

        elif behaviour == "create":
            if apply_block:
                message += f"  • Cell Type: {apply_block.get('cell_type', '?')}\n"
                message += f"  • Count: {apply_block.get('count', '?')}\n"
                dist = apply_block.get('distribution', {})
                message += f"  • Distribution: {dist.get('type', '?')}\n"
        
        if new_types:
            message += f"\n✨ New Cell Types:\n"
            for ct in new_types:
                if ct not in self.registry.celltype_params:
                    message += f"  • {ct} (will be created)\n"
                else:
                    message += f"  • {ct} (already exists)\n"
        else:
            message += f"\n✓ No new cell types needed\n"
        
      
        message += f"\n⚙️ Options:\n"
        message += f"  • Trigger once: {'Yes' if rule.get('once') else 'No'}\n"
        message += f"  • Debug: {'Yes' if rule.get('debug') else 'No'}\n"
        
        reply = QMessageBox.question(
            self,
            "Confirm Rule",
            message + "\n\nProceed with adding this rule?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        return reply == QMessageBox.Yes
    
    def add_rule(self):
        if not self.registry:
            return
        
        result = self.collect_params()
        if not result:
            return

        behaviour, params = result
        rule = build_rule(behaviour, params)
        
        from utils_extensions.utils import extract_celltypes_from_rule, handle_new_rule_registration
        new_types = extract_celltypes_from_rule(rule)
        
        if not self.confirm_rule(rule, new_types):
            return

        existing_ids = {r["id"] for r in self.registry.rules}
        if params["id"] in existing_ids:
            reply = QMessageBox.question(
                self, "Overwrite?",
                f"Rule ID {params['id']} already exists.\nOverwrite?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            self.registry.rules = [r for r in self.registry.rules if r["id"] != params["id"]]

        try:
            handle_new_rule_registration(
                self.registry, 
                rule, 
                self.ask_celltype_params_gui 
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Registration failed:\n{str(e)}")
            return
    
        self.refresh_list()
        QMessageBox.information(
            self, "Success",
            f"Rule {params['id']} added and injected successfully!"
        )

    # ============================================================
    # SAVE
    # ============================================================

    def save(self):
        if not self.registry:
            print("No registry loaded")
            return

        self.registry.save()

        try:
            self.registry.export_to_xml()   # 🔥 加这一行
        except Exception as e:
            print("❌ Export failed:", e)

        print("Saved")

    '''
    def ask_field(self, field):

        name = field["name"]
        ftype = field["type"]

        if ftype == "str":
            val, ok = QInputDialog.getText(self, name, name)
        elif ftype == "int":
            val, ok = QInputDialog.getInt(self, name, name)
        elif ftype == "float":
            val, ok = QInputDialog.getDouble(self, name, name)
        elif ftype == "choice":
            val, ok = QInputDialog.getItem(
                self, name, name, field["options"], 0, False
            )
        else:
            return None

        if not ok:
            return None

        return val
    '''

    def ask_placement_strategy(self):
        
        # orientaion
        orient_type, ok = QInputDialog.getItem(
            self,
            "Placement Strategy",
            "Select orientation strategy:",
            ["random", "angle", "vector"],
            0,
            False
        )
        if not ok:
            return None
        
        if orient_type == "random":
            return {"type": "random"}
            
        elif orient_type == "angle":
            angle, ok = QInputDialog.getDouble(
                self,
                "Angle",
                "Angle (degrees, 0=right, 90=up):",
                0.0, -360.0, 360.0, 1
            )
            if not ok:
                return None
            return {
                "type": "angle",
                "angle_deg": angle
            }
            
        elif orient_type == "vector":
            dx, ok = QInputDialog.getDouble(
                self,
                "Direction Vector",
                "dx (x-component):",
                1.0, -100.0, 100.0, 2
            )
            if not ok:
                return None
                
            dy, ok = QInputDialog.getDouble(
                self,
                "Direction Vector",
                "dy (y-component):",
                0.0, -100.0, 100.0, 2
            )
            if not ok:
                return None
                
            return {
                "type": "vector",
                "dx": dx,
                "dy": dy
            }
        
        return None
    
    def collect_params(self):
        # 1️get the “Behaviour”
        behaviours = ["growth", "differentiate", "create", "death"]
        beh, ok = QInputDialog.getItem(self, "Step 1", "Select Behaviour:", behaviours, 0, False)
        if not ok: return None

        # get the universal parameters (ID, Target, Condition, Flags)
        params = {}
        
        # ID 
        default_id = self.generate_rule_id()
        rule_id, ok = QInputDialog.getText(self, "Rule ID", "Rule ID:", text=str(default_id))
        if not ok: return None
        params["id"] = rule_id.strip() or str(default_id)

        # Target 
        target, ok = QInputDialog.getText(self, "Target", "Target cell type (or None):")
        if not ok: return None
        params["target"] = None if target.lower() == "none" else target

        # Condition 
        params["when"] = self.build_condition_gui()
        if params["when"] is None: return None

        # Flags (Once/Debug)
        once_reply = QMessageBox.question(self, "Trigger Once", "Trigger once?", QMessageBox.Yes | QMessageBox.No)
        params["once"] = (once_reply == QMessageBox.Yes)
        
        debug_reply = QMessageBox.question(self, "Debug", "Enable debug?", QMessageBox.Yes | QMessageBox.No)
        params["debug"] = (debug_reply == QMessageBox.Yes)

        # dispatch behavior‑specific parameter collection
        # These functions return only business‑level parameters and do not interfere with the generic parameters above
        if beh == "growth":
            from gui.build_model_gui import build_model_gui
            apply_data = build_model_gui(beh)
            if not apply_data: return None
            params["apply"] = apply_data # growth would be packed

        elif beh == "differentiate":
            specific = self.collect_diff_params_wizard()
            if not specific: return None
            params.update(specific) # Differentiate  unfold

        elif beh == "create":
            specific = self.collect_create_params_wizard()
            if not specific: return None
            params.update(specific)

        return beh, params


    def collect_diff_params_wizard(self):
        """Parameter collection wizard dedicated to differentiation/division"""
        # --- mode ---
        mode, ok = QInputDialog.getItem(
            self, "Differentiate Mode", "Select mode:", ["type_switch", "division"], 0, False
        )
        if not ok: return None

        res = {"mode": mode}

        if mode == "type_switch":
            # --- mode A ---
            new_type, ok = QInputDialog.getText(self, "Type Switch", "New Cell Type:")
            if not ok: return None
            res["new_type"] = new_type.strip()

        else:
            # --- mode B (Division) ---
            parent_type, ok1 = QInputDialog.getText(self, "Division", "Parent Cell Type:")
            child_type, ok2 = QInputDialog.getText(self, "Division", "Child Cell Type:")
            ratio, ok3 = QInputDialog.getDouble(self, "Division", "Volume Ratio (0.0-1.0):", 0.5, 0, 1, 2)
            
            if not (ok1 and ok2 and ok3): return None
            
            res.update({
                "parent_type": parent_type.strip(),
                "child_type": child_type.strip(),
                "volume_ratio": ratio
            })

            placement = self.ask_placement_strategy()
            if placement:
                res["placement"] = placement
            else:
                return None 

        return res
    
    def collect_create_params_wizard(self):
        """
        Parameter collection wizard dedicated to Create
        """
        res = {}

        cell_type, ok = QInputDialog.getText(self, "Create Cells", "Cell Type:")
        if not ok: return None
        res["cell_type"] = cell_type.strip()

        count, ok = QInputDialog.getInt(self, "Create Cells", "Count:", 10, 1, 10000)
        if not ok: return None
        res["count"] = count

        dist_type, ok = QInputDialog.getItem(
            self, "Distribution", "Select Mode:", ["random", "cluster", "stripe"], 0, False
        )
        if not ok: return None

        dist = {"type": dist_type}

        # --- mode A cluster ---
        if dist_type == "cluster":
            cx, _ = QInputDialog.getInt(self, "Center", "Center X:")
            cy, _ = QInputDialog.getInt(self, "Center", "Center Y:")
            r, _ = QInputDialog.getInt(self, "Radius", "Radius:")
            dist.update({"center": [cx, cy], "radius": r})

        # --- mode B strope ---
        elif dist_type == "stripe":
            direction, _ = QInputDialog.getItem(
                self, "Stripe Direction", "Direction:", ["vertical", "horizontal"], 0, False
            )
            dist["direction"] = direction

            mode, _ = QInputDialog.getItem(
                self, "Stripe Mode", "End Mode:", ["gap", "end"], 0, False
            )

            if direction == "vertical":
                x, _ = QInputDialog.getInt(self, "Vertical Stripe", "X coordinate:")
                y_start, _ = QInputDialog.getInt(self, "Vertical Stripe", "Y start:")
                dist.update({"x": x, "y_start": y_start})

                if mode == "gap":
                    dist["y_gap"] = QInputDialog.getInt(self, "Vertical Stripe", "Y gap:")[0]
                else:
                    dist["y_end"] = QInputDialog.getInt(self, "Vertical Stripe", "Y end:")[0]
            else:
                y, _ = QInputDialog.getInt(self, "Horizontal Stripe", "Y coordinate:")
                x_start, _ = QInputDialog.getInt(self, "Horizontal Stripe", "X start:")
                dist.update({"y": y, "x_start": x_start})

                if mode == "gap":
                    dist["x_gap"] = QInputDialog.getInt(self, "Horizontal Stripe", "X gap:")[0]
                else:
                    dist["x_end"] = QInputDialog.getInt(self, "Horizontal Stripe", "X end:")[0]

        res["distribution"] = dist
        return res

    '''
    def collect_params(self):

        params = {}

        # =========================
        # 1️⃣ behaviour
        # =========================
        behaviour, ok = QInputDialog.getItem(
            self,
            "Behaviour",
            "Select behaviour:",
            ["growth", "differentiate", "create"],
            0,
            False
        )
        if not ok:
            return None

        # =========================
        # 2️⃣ id
        # =========================
        default_id = self.generate_rule_id()

        rule_id, ok = QInputDialog.getText(
            self,
            "Rule ID",
            "Rule ID (leave blank for auto):",
            text=str(default_id)
        )
        if not ok:
            return None

        rule_id = rule_id.strip()
        if not rule_id:
            rule_id = str(default_id)

        params["id"] = rule_id

        # =========================
        # 3️⃣ target
        # =========================
        target, ok = QInputDialog.getText(self, "Target", "Target (or None):")
        if not ok:
            return None

        params["target"] = None if target.lower() == "none" else target

        # =========================
        # 4️⃣ condition（GUI ver）
        # =========================
        params["when"] = self.build_condition_gui() # 

        if params["when"] is None:
            return None

        # ============================================================
        # GROWTH
        # ============================================================
        if behaviour == "growth":
            
            # model
            model, ok = QInputDialog.getItem(
                self, 
                "Growth Model", 
                "Select model:", 
                ["linear", "hill", "expression"],  # 添加 expression
                0, 
                False
            )
            if not ok:
                return None
            
            regulator, ok = QInputDialog.getText(self, "Regulator", "Regulator (field name):")
            if not ok:
                return None
            
            # model
            if model == "linear":
                # Linear: y = alpha * x
                alpha, ok = QInputDialog.getDouble(
                    self, 
                    "Alpha", 
                    "Alpha (growth rate):", 
                    0.01, 0.001, 10.0, 3
                )
                if not ok:
                    return None
                parameters = {"alpha": alpha}
                
            elif model == "hill":
                # Hill: y = ymin + (ymax - ymin) * x^n / (k^n + x^n)
                ymin, ok = QInputDialog.getDouble(
                    self, 
                    "Ymin", 
                    "Minimum value (ymin):", 
                    0.0, 0.0, 100.0, 3
                )
                if not ok:
                    return None
                    
                ymax, ok = QInputDialog.getDouble(
                    self, 
                    "Ymax", 
                    "Maximum value (ymax):", 
                    1.0, 0.0, 100.0, 3
                )
                if not ok:
                    return None
                    
                k, ok = QInputDialog.getDouble(
                    self, 
                    "K", 
                    "Half-maximum concentration (k):", 
                    0.5, 0.001, 100.0, 3
                )
                if not ok:
                    return None
                    
                n, ok = QInputDialog.getDouble(
                    self, 
                    "n", 
                    "Hill coefficient (n):", 
                    2.0, 0.1, 10.0, 2
                )
                if not ok:
                    return None
                    
                parameters = {
                    "ymin": ymin,
                    "ymax": ymax,
                    "k": k,
                    "n": n
                }
                
            elif model == "expression":
                expression, ok = QInputDialog.getText(
                    self, 
                    "Expression", 
                    "Mathematical expression (e.g., '2*x + 1'):"
                )
                if not ok:
                    return None
                parameters = {"expression": expression}
            
            params["apply"] = {
                "model": model,
                "regulator": regulator,
                "parameters": parameters
            }

        # ============================================================
        # DIFFERENTIATE
        # ============================================================
        elif behaviour == "differentiate":
            
            # mode
            mode, ok = QInputDialog.getItem(
                self,
                "Differentiate Mode",
                "Select mode:",
                ["type_switch", "division"],
                0,
                False
            )
            if not ok:
                return None
            
            params["mode"] = mode
            
            if mode == "type_switch":
                new_type, ok = QInputDialog.getText(self, "New Type", "New cell type:")
                if not ok:
                    return None
                params["new_type"] = new_type
                
            else:  # mode == "division"
                
                # 1. type
                div_type, ok = QInputDialog.getItem(
                    self,
                    "Division Type",
                    "Select division type:",
                    ["symmetric", "asymmetric"],
                    0,
                    False
                )
                if not ok:
                    return None
                
                if div_type == "symmetric":
                    daughter_type, ok = QInputDialog.getText(
                        self, 
                        "Daughter Type", 
                        "Daughter cell type:"
                    )
                    if not ok:
                        return None
                    parent_type = daughter_type
                    child_type = daughter_type
                    
                else:  # asymmetric
                    parent_type, ok = QInputDialog.getText(
                        self, 
                        "Mother Type", 
                        "Mother cell new type:"
                    )
                    if not ok:
                        return None
                        
                    child_type, ok = QInputDialog.getText(
                        self, 
                        "Child Type", 
                        "Daughter cell type:"
                    )
                    if not ok:
                        return None
                
                params["parent_type"] = parent_type
                params["child_type"] = child_type
                
                # 2. volume ratio
                ratio, ok = QInputDialog.getDouble(
                    self,
                    "Volume Ratio",
                    "Mother volume ratio (0-1, default 0.5):",
                    0.5, 0.0, 1.0, 2
                )
                if not ok:
                    return None
                params["volume_ratio"] = ratio
                
                # division orientation
                placement = self.ask_placement_strategy()
                if placement is None:
                    return None
                params["placement"] = placement
        


        # ============================================================
        # CREATE
        # ============================================================
        elif behaviour == "create":

            cell_type, ok = QInputDialog.getText(self, "Cell Type", "Cell Type:")
            if not ok:
                return

            count, ok = QInputDialog.getInt(self, "Count", "Count:", 10)
            if not ok:
                return

            params["cell_type"] = cell_type
            params["count"] = count

            dist_type, ok = QInputDialog.getItem(
                self,
                "Distribution",
                "Type:",
                ["random", "cluster", "stripe"],
                0,
                False
            )
            if not ok:
                return

            dist = {"type": dist_type}

            if dist_type == "cluster":
                cx, _ = QInputDialog.getInt(self, "center_x", "center_x:")
                cy, _ = QInputDialog.getInt(self, "center_y", "center_y:")
                r, _ = QInputDialog.getInt(self, "radius", "radius:")
                dist.update({"center": [cx, cy], "radius": r})

            elif dist_type == "stripe":

                direction, _ = QInputDialog.getItem(
                    self, "Direction", "Direction:",
                    ["vertical", "horizontal"], 0, False
                )
                dist["direction"] = direction

                mode, _ = QInputDialog.getItem(
                    self, "Mode", "Mode:",
                    ["gap", "end"], 0, False
                )

                if direction == "vertical":
                    x, _ = QInputDialog.getInt(self, "x", "x:")
                    y_start, _ = QInputDialog.getInt(self, "y_start", "y_start:")
                    dist.update({"x": x, "y_start": y_start})

                    if mode == "gap":
                        dist["y_gap"] = QInputDialog.getInt(self, "y_gap", "y_gap:")[0]
                    else:
                        dist["y_end"] = QInputDialog.getInt(self, "y_end", "y_end:")[0]

                else:
                    y, _ = QInputDialog.getInt(self, "y", "y:")
                    x_start, _ = QInputDialog.getInt(self, "x_start", "x_start:")
                    dist.update({"y": y, "x_start": x_start})

                    if mode == "gap":
                        dist["x_gap"] = QInputDialog.getInt(self, "x_gap", "x_gap:")[0]
                    else:
                        dist["x_end"] = QInputDialog.getInt(self, "x_end", "x_end:")[0]

            params["distribution"] = dist
        # =========================
        # flags
        # =========================
        once_reply = QMessageBox.question(
            self, "Trigger Once", "Trigger once?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        params["once"] = (once_reply == QMessageBox.Yes)

        debug_reply = QMessageBox.question(
            self, "Debug", "Enable debug?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        params["debug"] = (debug_reply == QMessageBox.Yes)

        return behaviour, params
    '''
    def clicked_import_csv(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "open CSV",
            "",
            "CSV Files (*.csv)"
        )

        if not path:
            return

        try:
            rules_data = import_rules_from_csv(path)  

            for behaviour, params in rules_data:
                rule = build_rule(behaviour, params)

                new_types = extract_celltypes_from_rule(rule)

                for ct in new_types:
                    if ct not in self.registry.celltype_params:
                        params_ct = self.ask_celltype_params_gui(ct)

                        if params_ct is None:
                            return
                        self.registry.add_celltype_params(
                            ct,
                            params_ct['targetVolume'],
                            params_ct['lambdaVolume']
                        )
                self.registry.add_rule(rule)
                process_and_inject_rule(self.registry.project_path, self.registry, rule)

            self.refresh_list()

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
    
    def open_manage_rules(self):
        if not self.registry:
            QMessageBox.warning(self, "Warning", "Please Load/Create a Project first!")
            return
        # “Pass in self so that ManageRulesWindow can access all the methods of the main window.”
        from gui.ManageRuleWindow import ManageRulesWindow
        self.manage_win = ManageRulesWindow(self.registry, main_editor=self)
        self.manage_win.show()

    def build_condition_gui(self):
        # explicityly import
        from gui.build_condition_gui import build_condition_gui as real_builder
        return real_builder(self)













 