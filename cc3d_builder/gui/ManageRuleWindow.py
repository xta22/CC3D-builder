from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QMessageBox, QHeaderView, QAbstractItemView, QPushButton, QInputDialog, 
    QGroupBox, QCheckBox, QSpinBox, QFormLayout, QScrollArea
)
from PyQt5.QtCore import Qt
from core.rule_builder import build_rule
from gui.build_model_gui import build_model_gui

class ManageRulesWindow(QWidget):
    def __init__(self, registry, main_editor = None):
        super().__init__()
        self.registry = registry
        self.main_editor = main_editor
        self.resize(1600, 800) 
        
        self.main_h_layout = QHBoxLayout(self)
        
        self.left_container = QWidget()
        self.layout = QVBoxLayout(self.left_container) 

        self.main_h_layout.addWidget(self.left_container, stretch=4)
        
        self.setup_toolbar()
        self.table = QTableWidget()
        self.setup_table_config()
        self.layout.addWidget(self.table)
        
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
        self.layout.addLayout(btn_layout)
        

    def setup_table_config(self):
        self.columns = ["ID", "Behaviour", "Target Cell", "Frequency", "Condition", "Apply Params", "Once", "Custom Script"]
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
            from core.rule_builder import build_rule
            rule = build_rule(behaviour, params)
           
            from utils_extensions.utils import extract_celltypes_from_rule
            new_types = extract_celltypes_from_rule(rule)
            
            if self.main_editor.confirm_rule(rule, new_types):
                for ct in new_types:
                    if ct not in self.registry.celltype_params:
                        params_ct = self.main_editor.ask_celltype_params_gui(ct)
                        if params_ct:
                            self.registry.add_celltype_params(
                                ct, params_ct["targetVolume"], params_ct["lambdaVolume"]
                            )
                        else:
                            return 
                from injector.inject import process_and_inject_rule
                try:
                    self.registry.add_rule(rule)
                    process_and_inject_rule(self.registry.project_path, self.registry, rule)
                    
                    self.refresh_table()
                    self.save_and_sync()
                except Exception as e:
                    print(f"Injection failed: {e}") 
                    QMessageBox.warning(self, "Injection Error", f"Rules are saved but fail to inject  {e}")

    def handle_delete(self):
        curr_row = self.table.currentRow()
        if curr_row == -1: return
        
        rule_id = self.table.item(curr_row, 0).text()
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
        rule_id = self.table.item(row, 0).text()
        rule = self.registry.get_rule_by_id(rule_id)
        if not rule: return
        
        try:
            if col == 2: 
                rule["target"] = item.text().strip()
                from utils_extensions.utils import handle_new_rule_registration
                handle_new_rule_registration(
                    self.registry, 
                    rule, 
                    self.main_editor.ask_celltype_params_gui
                )
            elif col == 3: 
                rule["frequency"] = int(item.text().strip())
            elif col == 6: 
                rule["once"] = (item.checkState() == Qt.Checked)
                
            self.registry.update_rule(rule_id, rule)
            self.registry.save()
            print(f"✅ Auto-saved inline edit for Rule {rule_id}")
            
        except ValueError:
            QMessageBox.warning(self, "Error", "Frequency must be an integer!")
            self.refresh_table()

    # ==========================================
    # ==========================================
    def on_cell_double_clicked(self, row, col):
        rule_id = self.table.item(row, 0).text()
        rule = self.registry.get_rule_by_id(rule_id)
        if not rule: return
        beh = rule.get('behaviour', '').lower()
        updated = False

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

            if new_data:
                self._update_rule_content(rule, new_data)
                updated = True

        if updated:
            self.registry.update_rule(rule_id, rule) 
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
    

class CellInventoryWidget(QGroupBox):
    def __init__(self, registry, on_changed_callback=None):
        super().__init__("🧬 Cell Initialization Manager")
        self.registry = registry
        self.on_changed_callback = on_changed_callback
        self.layout = QVBoxLayout(self)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.form_layout = QFormLayout(self.container)
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)
        
        self.refresh_list()

    def refresh_list(self):
        while self.form_layout.count() > 0:
            item = self.form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        # for i in reversed(range(self.form_layout.count())): 
        #    self.form_layout.itemAt(i).widget().setParent(None)

        for name, params in self.registry.celltype_params.items():
            row_layout = QHBoxLayout()
            
            cb = QCheckBox("Init")
            cb.setChecked(params.get("should_initialize", True))
            cb.stateChanged.connect(lambda state, n=name: self._update_init(n, state))
            
            sb = QSpinBox()
            sb.setRange(0, 1000)
            sb.setValue(params.get("initial_count", 5))
            sb.valueChanged.connect(lambda val, n=name: self._update_count(n, val))
            
            row_layout.addWidget(cb)
            row_layout.addWidget(sb)
            
            self.form_layout.addRow(f"<b>{name}</b>:", row_layout)

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