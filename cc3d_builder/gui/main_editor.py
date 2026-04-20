from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QPushButton, QDialog,
    QInputDialog, QApplication, QMessageBox, QFileDialog
)
import sys
import os
from pathlib import Path
from cc3d_builder.core.rule_builder import build_rule
from cc3d_builder.core.csv_importer import import_rules_from_csv
from cc3d_builder.utils_extensions.utils import  handle_new_rule_registration, ask_params_gui, process_custom_script, extract_params
from cc3d_builder.utils_extensions.rule_parsing import extract_celltypes_from_rule, extract_fields_from_rule 
from cc3d_builder.core.structure_manager import StructureManager
from cc3d_builder.injector.steppable_injector import SteppableInjector
from cc3d_builder.injector.inject import process_and_inject_rule
from cc3d_builder.utils_extensions.paths import ROOT, SANDBOX_DIR
from Rules_project.Simulation.registry.simulation_registry import SimulationRegistry
import re
from typing import Any
from cc3d_builder.gui.field_setup_dialog import FieldSetupDialog

PROJECT_ROOT = Path(__file__).resolve().parents[2] 

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    print(f"✅ Framework Root Injected: {PROJECT_ROOT}")

class MainWindow(QWidget):

    def __init__(self, registry: SimulationRegistry | None = None):
        
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
    
    def confirm_rule(self, rule, new_types):
        """show rules for users to confirm"""
        if self.registry is None:
            return False
        
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

        new_fields = extract_fields_from_rule(rule)
        for field_name in new_fields:
            if field_name not in self.registry.field_params:
                
                # 拿到当前已经注册的细胞类型列表，传给弹窗，供趋化性下拉框使用
                available_cells = list(self.registry.celltype_params.keys())
                
                # 呼叫我们的终极弹窗！
                dialog = FieldSetupDialog(field_name, available_cells, self)
                
                if dialog.exec_() == QDialog.Accepted:
                    # 拿到组装好的终极字典
                    field_params = dialog.get_data()
                    
                    # 是否需要自动添加 Secretion Rule?
                    if field_params.pop("ControlSecretionPython", False):
                        # 自动生成联动规则
                        secrete_rule = {
                            "id": f"auto_secrete_{field_name}",
                            "behaviour": "secrete",
                            "target": "global",
                            "apply": {"field": field_name, "rate": 0.1}
                        }
                        self.registry.add_rule(secrete_rule)
                        print(f"✅ Auto-generated secretion rule for {field_name}")

                    # 写入 Registry (这样底层 ensure_xml 就能完美读取了)
                    self.registry.add_field_params(field_name, field_params)
                    
                else:
                    print(f"⚠️ User canceled field setup for {field_name}")
                    return # 如果必须要填物理参数而用户取消了，那就打断注入过程
        
        try:
            handle_new_rule_registration(
                self.registry, 
                rule, 
                self.ask_params_gui,
                self.sm,
                self.injector 
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
            self.registry.export_to_xml()  
        except Exception as e:
            print("❌ Export failed:", e)

        print("Saved")

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
        behaviours = ["growth", "differentiate", "create", "death", "custom_script"]
        beh, ok = QInputDialog.getItem(self, "Step 1", "Select Behaviour:", behaviours, 0, False)
        if not ok: return None

        # get the universal parameters (ID, Target, Condition, Flags)
        params = {}
        
        # ID 
        default_id = self.generate_rule_id()
        rule_id, ok = QInputDialog.getText(self, "Rule ID", "Rule ID:", text=str(default_id))
        if not ok: return None
        params["id"] = rule_id.strip() or str(default_id)

        if beh == "custom_script": 
            specific = self.collect_custom_script_wizard() 
            if not specific: return None
            params.update(specific)
            return beh, params
        
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
            from cc3d_builder.gui.build_model_gui import build_model_gui
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

        elif beh == "death":
            pass

        return beh, params


    def collect_diff_params_wizard(self):
        """Parameter collection wizard dedicated to differentiation/division"""
        # --- mode ---
        mode, ok = QInputDialog.getItem(
            self, "Differentiate Mode", "Select mode:", ["type_switch", "division"], 0, False
        )
        if not ok: return None

        res: dict[str, Any] = {"mode": mode}

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
            
            if not (ok1 and ok2 and ok3): 
                return None
            
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
        res: dict[str, Any] = {}

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

        dist: dict[str, Any] = {"type": dist_type}

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
    

    def collect_custom_script_wizard(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Script", str(SANDBOX_DIR), "Python (*.py)")
        if not file_path: return None
        file_path = Path(file_path)

        final_params = process_custom_script(
            file_path = str(file_path),
            registry = self.registry,
            ask_params_func = self.ask_params_gui,
            extract_params_func = extract_params,    
            existing_params = None
        )
        print(f"DEBUG: Detected Params -> {final_params}") # 👈 加这一
        if final_params:
            return {
                "script_path": file_path.as_posix(),
                "apply_params": final_params
            }
        return None

    def clicked_import_csv(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "open CSV",
            "",
            "CSV Files (*.csv)"
        )

        if not path:
            return
        
        if not self.registry:
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
        from cc3d_builder.gui.ManageRuleWindow import ManageRulesWindow
        self.manage_win = ManageRulesWindow(self.registry, ask_cell_func=self.ask_celltype_params_gui, main_editor=self)
        self.manage_win.show()

    def build_condition_gui(self):
        # explicityly import
        from gui.build_condition_gui import build_condition_gui as real_builder
        return real_builder(self)






 