from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QMessageBox, QHeaderView, QAbstractItemView, QPushButton, QInputDialog, 
    QGroupBox, QCheckBox, QSpinBox, QFormLayout, QScrollArea, QDialog, QLineEdit,
    QDialogButtonBox, QScrollArea, QFileDialog
)
from PyQt5.QtCore import Qt
from cc3d_builder.gui.main_editor import MainWindow
from cc3d_builder.core.rule_builder import build_rule
from cc3d_builder.gui.build_model_gui import build_model_gui
from cc3d_builder.utils_extensions.rule_parsing import extract_celltypes_from_rule, extract_fields_from_rule
import importlib.util
from cc3d_builder.utils_extensions.utils import process_custom_script, extract_params
from typing import TYPE_CHECKING, Optional, List, Dict
if TYPE_CHECKING:
    from cc3d_builder.engine.registry.simulation_registry import SimulationRegistry


class ManageRulesWindow(QWidget):
    def __init__(self, registry: 'SimulationRegistry', sm, injector, ask_func=None, main_editor=None):
        super().__init__()
        self.registry = registry
        self.sm = sm
        self.injector = injector
        self.main_editor = main_editor
        self.ask_params_gui = ask_func

        self.resize(1600, 800) 
        
        self.main_h_layout = QHBoxLayout(self)
        
        self.left_container = QWidget()
        self.main_layout = QVBoxLayout(self.left_container)  # type: ignore

        self.main_h_layout.addWidget(self.left_container, stretch=4)
        
        self.setup_toolbar()
        self.table = QTableWidget()
        self.setup_table_config()
        self.main_layout.addWidget(self.table) # type: ignore
        
        self.cell_manager = CellInventoryWidget(self.registry, on_changed_callback=self.save_and_sync)
        self.main_h_layout.addWidget(self.cell_manager, stretch=1)
        
        self.refresh_table()

    def setup_toolbar(self):
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ Add Rule (Wizard)")
        self.btn_up = QPushButton("Move Up ↑")
        self.btn_down = QPushButton("Move Down ↓")
        self.btn_delete = QPushButton("Delete Selected")
        
        self.btn_add.clicked.connect(self.handle_add_new) 
        self.btn_up.clicked.connect(lambda: self.handle_move(-1))
        self.btn_down.clicked.connect(lambda: self.handle_move(1))
        self.btn_delete.clicked.connect(self.handle_delete)
        self.btn_back = QPushButton("✅ Finish & Return to Main")
        self.btn_back.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_back.clicked.connect(self.handle_back)

        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addStretch() 
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_back)
        self.main_layout.addLayout(btn_layout) # type: ignore
        

    def setup_table_config(self):
        self.columns = ["ID", "Behaviour", "Target Cell", "Frequency", "Condition", "Apply Params", "Once", "Custom Script"]
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # type: ignore
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

    def refresh_table(self):
        self.is_updating_table = True
        self.table.setRowCount(0)
        for rule in self.registry.rules:
            row = self.table.rowCount()
            self.table.insertRow(row)
                 
            self.table.setItem(row, 0, self._read_only_item(rule.get("id")))
            self.table.setItem(row, 1, self._read_only_item(rule.get("behaviour"))) 
            self.table.setItem(row, 2, QTableWidgetItem(str(rule.get("target", "None"))))
            self.table.setItem(row, 3, QTableWidgetItem(str(rule.get("frequency", 1))))
            
            cond_type = rule.get("when", {}).get("condition_type", "TRUE")
            self.table.setItem(row, 4, self._read_only_item(f"[{cond_type}] Edit..."))
            
            apply_data = rule.get("apply", {}) or (rule.get("cases", [{}])[0].get("apply", {}))
            model_info = apply_data.get("model", "Params")
            self.table.setItem(row, 5, self._read_only_item(f"[{model_info}] Edit..."))
            
            # Checkbox
            once_item = QTableWidgetItem()
            once_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            once_item.setCheckState(Qt.Checked if rule.get("once") else Qt.Unchecked)
            self.table.setItem(row, 6, once_item)

            # Custom Script 
            script_path = rule.get("custom_script", "None")
            self.table.setItem(row, 7, QTableWidgetItem(script_path))

        self.is_updating_table = False
        
        if hasattr(self, 'cell_manager'):
            self.cell_manager.refresh_list()

    def _read_only_item(self, text):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    # ==========================================
    # add and delete
    # ==========================================
    def handle_add_new(self):
        if not self.main_editor:
            QMessageBox.critical(self, "Error", "Main Editor reference missing!")
            return

        result = self.main_editor.collect_params() 
        
        if result:
            behaviour, params = result
            from cc3d_builder.core.rule_builder import build_rule
            rule = build_rule(behaviour, params)
           
            from cc3d_builder.utils_extensions.utils import handle_new_rule_registration
            try:
                handle_new_rule_registration(
                    registry=self.registry,
                    rule=rule,
                    input_handler=lambda m, n: self.main_editor.ask_params_gui(m, n, self.main_editor),
                    sm=self.sm,
                    injector=self.injector
                )
                self.refresh_table()
                self.save_and_sync()
                QMessageBox.information(self, "Success", f"Rule {rule['id']} added successfully!")
            except Exception as e:
                print(f"Registration/Injection failed: {e}") 
                QMessageBox.warning(self, "Error", f"Failed to register rule: {e}")
            
    def handle_delete(self):
        curr_row = self.table.currentRow()
        if curr_row == -1: return
        
        item = self.table.item(curr_row, 0)
        if item is None: return 
        
        rule_id = item.text()
        reply = QMessageBox.question(self, "Confirm", f"Delete Rule {rule_id}?", QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.registry.rules = [r for r in self.registry.rules if str(r['id']) != rule_id]
            self.registry.save()
            self.refresh_table()
            self.save_and_sync()
            print(f" Rule {rule_id} has been deleted and JSON sync completed.")

    # ==========================================
    # order and swap
    # ==========================================
    def handle_move(self, direction):
        curr_row = self.table.currentRow()
        target_row = curr_row + direction
        if 0 <= target_row < len(self.registry.rules):
            self.registry.rules[curr_row], self.registry.rules[target_row] = \
                self.registry.rules[target_row], self.registry.rules[curr_row]
            self.registry.save()
            self.refresh_table()
            self.table.selectRow(target_row)
            self.save_and_sync()

    def on_item_changed(self, item):
        if self.is_updating_table: return
            
        row = item.row()
        col = item.column()
        item_id = self.table.item(row, 0)
        if item_id is None: return 
        
        rule_id = item_id.text()
        rule = self.registry.get_rule_by_id(rule_id)
        if not rule: return

        try:
            if col == 2: 
                rule["target"] = item.text().strip()
                from cc3d_builder.utils_extensions.utils import handle_new_rule_registration
                handle_new_rule_registration(
                registry=self.registry,
                rule=rule,
                input_handler=lambda m, n: self.main_editor.ask_params_gui(m, n, self.main_editor),
                sm = self.sm,
                injector = self.injector,
            )
            elif col == 3: 
                rule["frequency"] = int(item.text().strip())
            elif col == 6: 
                rule["once"] = (item.checkState() == Qt.Checked)
                
            elif col == 7: # Custom Script Path
                from pathlib import Path
                raw_path = item.text().strip()
                rule["custom_script"] = Path(raw_path).as_posix() if raw_path != "None" else "None"
                
            self.registry.update_rule(rule_id, rule)
            self.save_and_sync() 
            print(f"✅ Auto-saved inline edit for Rule {rule_id}")

            # self.registry.save()
            
        except ValueError:
            QMessageBox.warning(self, "Error", "Frequency must be an integer!")
            self.refresh_table()

    # ==========================================
    # ==========================================

    def on_cell_double_clicked(self, row, col):
        item = self.table.item(row, 0)
        if item is None:
            return

        rule_id = item.text()
        rule = self.registry.get_rule_by_id(rule_id)
        if not rule: return
        beh = rule.get('behaviour', '').lower()
        updated = False

        if not self.main_editor:
            QMessageBox.warning(self, "Error", "Main Editor reference is missing!")
            return
        
        # --- col4 Condition ---
        if col == 4:
            new_cond = self.main_editor.build_condition_gui()
            if new_cond:
                if "cases" in rule and len(rule["cases"]) > 0:
                    rule["cases"][0]["when"] = new_cond
                else:
                    rule["when"] = new_cond
                updated = True

        # --- col5 Parameters ---
        elif col == 5:
            new_data = None
            if beh == "growth":
                from gui.build_model_gui import build_model_gui
                res = build_model_gui(beh)
                if res: new_data = res 
            elif beh == "differentiate":
                new_data = self.main_editor.collect_diff_params_wizard()
            
            elif beh == "create":
                new_data = self.main_editor.collect_create_params_wizard()

            elif beh == "custom_script":
                # Provide a dedicated parameter editor for custom scripts
                script_path = rule.get("custom_script")
                if script_path and script_path != "None":
                    # scan the script and get the new key
                    detected_keys = extract_params(script_path)
                    saved_params = rule.get("apply_params", {})
                    
                    dialog = ParamEditorDialog(detected_keys, saved_params)
                    if dialog.exec_() == QDialog.Accepted:
                        new_data = dialog.get_final_params()
                        rule["apply_params"] = new_data
                        updated = True

            if new_data:
                self._update_rule_content(rule, new_data)
                updated = True

        if updated:
            self.registry.update_rule(rule_id, rule) 
            mentioned_types = extract_celltypes_from_rule(rule)

            for ct in mentioned_types:
                if ct and ct not in self.registry.celltype_params:
                    params_ct = self.main_editor.ask_params_gui("celltype", ct, self.main_editor)
                    if params_ct:
                        self.registry.add_celltype_params(
                            ct, params_ct["targetVolume"], params_ct["lambdaVolume"]
                        )

            mentioned_fields = extract_fields_from_rule(rule)
            for f_name in mentioned_fields:
                if f_name and f_name not in self.registry.field_params:
                    params_f = self.main_editor.ask_params_gui("field", f_name, self.main_editor)
                    if params_f:
                        self.registry.add_field_params(f_name, params_f)
                        self.sm.ensure_field(f_name)
            self.registry.save()
            self.save_and_sync()
            self.refresh_table()

    def _update_rule_content(self, rule, new_data):
        # build apply block
        if "cases" in rule and len(rule["cases"]) > 0:
            rule["cases"][0]["apply"].update(new_data)
        else:
            rule["apply"] = new_data

    def setup_drag_drop_sync(self):
            original_drop_event = self.table.dropEvent

            def custom_drop_event(event):
                original_drop_event(event)
                
                self.sync_order_to_registry()
                self.refresh_table() 

            self.table.dropEvent = custom_drop_event

    def sync_order_to_registry(self):
            new_ordered_rules = []
            for row in range(self.table.rowCount()):
                id_item = self.table.item(row, 0)
                if id_item:
                    rule_id = id_item.text()
                    rule = self.registry.get_rule_by_id(rule_id)
                    if rule:
                        new_ordered_rules.append(rule)
            
            self.registry.rules = new_ordered_rules
            self.registry.save()


    def swap_rules(self, old_row, new_row):
        if 0 <= new_row < len(self.registry.rules):
            self.registry.rules[old_row], self.registry.rules[new_row] = \
                self.registry.rules[new_row], self.registry.rules[old_row]
            
            self.registry.save()
            
            self.refresh_table()
            
            self.table.selectRow(new_row)

    def save_and_sync(self):
            self.registry.save()
            
            try:
                self.registry.export_to_xml() 
            except Exception as e:
                print(f"Export XML Error: {e}")

            if self.main_editor and hasattr(self.main_editor, 'refresh_list'):
                self.main_editor.refresh_list()

    def handle_back(self):
        self.save_and_sync()
        
        print("Returning to Main Window...")
        
        self.close()
        
        if self.main_editor:
            self.main_editor.show()
            self.main_editor.raise_()

    def build_condition_gui(self):
        # explicitly import 
        from gui.build_condition_gui import build_condition_gui as real_builder
        return real_builder(self)
    
    def get_file_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Python Script", "", "Python Files (*.py)")
        return file_path
    
    def on_import_script(self):
        curr_row = self.table.currentRow()
        if curr_row == -1:
            QMessageBox.warning(self, "Warning", "Please select a rule first!")
            return
        
        item = rule_id = self.table.item(curr_row, 0)
        if item:
            rule_id = item.text()
            rule = self.registry.get_rule_by_id(rule_id)

        if not rule: return

        file_path = self.get_file_path() 
        if not file_path: return

        if self.main_editor:
            final_params = process_custom_script(
                file_path = file_path,
                registry = self.registry,
                ask_params_func = lambda m, n: self.main_editor.ask_params_gui(m, n, self.main_editor),
                extract_params_func = extract_params,
                existing_params =rule.get("apply_params", {}) 
            )
            if final_params:
                rule["apply_params"] = final_params
                rule["custom_script"] = file_path
                
                self.registry.update_rule(rule_id, rule)
                self.save_and_sync()
                self.refresh_table()

class CellInventoryWidget(QGroupBox):
    def __init__(self, registry: 'SimulationRegistry', on_changed_callback=None, ask_cell_func=None, main_editor = None):
        super().__init__("🧬 Cell Initialization Manager")
        self.registry = registry
        self.on_changed_callback = on_changed_callback
        self.main_layout = QVBoxLayout(self)
        self.main_editor = main_editor
        self.scroll: QScrollArea = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.form_layout = QFormLayout(self.container)
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)
        
        self.refresh_list()

    def refresh_list(self):
        while self.form_layout.count() > 0:
            item = self.form_layout.takeAt(0)
            if item: 
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        # for i in reversed(range(self.form_layout.count())): 
        #    self.form_layout.itemAt(i).widget().setParent(None)

        for name, params in self.registry.celltype_params.items():
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            cb = QCheckBox("Init")
            cb.setChecked(params.get("should_initialize", True))
            cb.stateChanged.connect(lambda state, n=name: self._update_init(n, state))
            
            sb = QSpinBox()
            sb.setRange(0, 1000)
            sb.setValue(params.get("initial_count", 5))
            sb.valueChanged.connect(lambda val, n=name: self._update_count(n, val))
            
            row_layout.addWidget(cb)
            row_layout.addWidget(sb)
            
            self.form_layout.addRow(f"<b>{name}</b>:", row_widget)

    def _update_init(self, name, state):
        self.registry.celltype_params[name]["should_initialize"] = (state == Qt.Checked)
        self._sync()

    def _update_count(self, name, val):
        self.registry.celltype_params[name]["initial_count"] = val
        self._sync()

    def _sync(self):
        self.registry.save()
        if self.on_changed_callback:
            self.on_changed_callback() 


#  for custom scripts parameter modification in MainRuleWindow 
class ParamEditorDialog(QDialog):
    def __init__(self, detected_keys, saved_params):
        super().__init__()

        self.setWindowTitle("Edit Script Parameters")
        self.setMinimumWidth(400)

        self.params_dict = saved_params or {} # saved {key: value}
        self.detected_keys = detected_keys   # scanning by regularization  [key1, key2]
        self.inputs = {} # dictionary for storing QLineEdit 
        self.init_ui()
        # UI layout:
        # 1. Iterate over detected_keys: automatically create input fields, and populate them with values if they exist in saved_params.
        # 2. Keep an "Add Custom Parameter" button at the bottom: used to manually add keys that were missed by the script.       

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        self.form_layout = QFormLayout()
        
        # merge keys 
        all_keys = sorted(list(set(self.detected_keys) | set(self.params_dict.keys())))
        
        for key in all_keys:
            self.add_param_row(key, self.params_dict.get(key, ""))
            
        self.main_layout.addLayout(self.form_layout)

        # 2. “Add Custom Parameter” buttom
        self.add_btn = QPushButton("+ Add Custom Parameter (Manual)")
        self.add_btn.clicked.connect(self.add_manual_param)
        self.main_layout.addWidget(self.add_btn)

        # 3. confirm/cancel button
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

    def add_param_row(self, key, value):
        """add a row of input frame in UI"""
        line_edit = QLineEdit(str(value))
        self.form_layout.addRow(f"<b>{key}</b>:", line_edit)
        self.inputs[key] = line_edit

    def add_manual_param(self):
        """manually add regular expression fail to catch"""
        key, ok = QInputDialog.getText(self, "Manual Add", "Enter Parameter Name:")
        if ok and key:
            if key not in self.inputs:
                self.add_param_row(key, "")
            else:
                QMessageBox.information(self, "Info", "Parameter already exists.")

    def get_final_params(self):
        # after users click confirmation, all the key/value pairs would be packed up as dict and returned 
        return {k: v.text() for k, v in self.inputs.items()}
