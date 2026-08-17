# ManageRuleWindow.py
import copy
import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QAbstractItemView, QPushButton, QInputDialog,
    QGroupBox, QFormLayout, QScrollArea, QDialog, QLineEdit,
    QDialogButtonBox, QScrollArea, QFileDialog, QTextEdit, QApplication,
    QSizePolicy, QLabel
)
from PyQt5.QtCore import Qt
from pathlib import Path
from cc3d_builder.gui.main_editor import MainWindow
from cc3d_builder.core.rule_builder import build_rule
from cc3d_builder.core.rule_schema import case_payload
from cc3d_builder.core.state_key_catalog import format_state_key_catalog
from cc3d_builder.gui.build_model_gui import build_model_gui
from cc3d_builder.gui.field_setup_dialog import FieldSetupDialog
from cc3d_builder.utils_extensions.rule_parsing import extract_celltypes_from_rule, extract_fields_from_rule
import importlib.util
from cc3d_builder.utils_extensions.utils import collect_custom_params_gui, process_custom_script, extract_params
from typing import TYPE_CHECKING, Any, List, Dict
if TYPE_CHECKING:
    from cc3d_builder.engine.registry.simulation_registry import SimulationRegistry


class ManageRulesWindow(QWidget):
    def __init__(self, registry: 'SimulationRegistry', sm, injector, ask_func=None, main_editor=None):
        super().__init__()
        self.registry = registry
        self.sm = sm
        self.structure_manager = sm
        self.injector = injector
        self.main_editor = main_editor
        self.ask_params_gui = ask_func

        self._set_quarter_screen_default_size()

        self.main_h_layout = QHBoxLayout(self)
        self.main_h_layout.setContentsMargins(12, 10, 12, 10)
        self.main_h_layout.setSpacing(12)

        self.left_container = QWidget()
        self.main_layout = QVBoxLayout(self.left_container)
        self.left_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setup_toolbar()
        self.table = QTableWidget()
        self.setup_table_config()
        self.main_layout.addWidget(self.table)
        self.main_h_layout.addWidget(self.left_container, stretch=1)

        self.right_container = QWidget()
        self.right_container.setMinimumWidth(260)
        self.right_container.setMaximumWidth(340)
        self.right_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.right_layout = QVBoxLayout(self.right_container)

        self.cell_manager = CellInventoryWidget(self.registry, on_changed_callback=self.save_and_sync, main_editor=self.main_editor)
        self.right_layout.addWidget(self.cell_manager)

        self.field_manager = FieldManagerWidget(
            registry=self.registry,
            structure_manager=self.structure_manager,
            available_celltypes=self.get_current_celltypes(),
            parent=self
        )
        self.right_layout.addWidget(self.field_manager)

        self.xml_config_hint = QLabel("Cell/field deletion and spatial initialization are managed in XML Config Editor.")
        self.xml_config_hint.setWordWrap(True)
        self.right_layout.addWidget(self.xml_config_hint)
        self.btn_xml_config = QPushButton("Open XML Config Editor")
        self.btn_xml_config.clicked.connect(self.open_xml_config_editor)
        self.right_layout.addWidget(self.btn_xml_config)
        self.btn_intracellular_models = QPushButton("Intracellular Models")
        self.btn_intracellular_models.clicked.connect(self.open_intracellular_model_manager)
        self.right_layout.addWidget(self.btn_intracellular_models)
        self.btn_subcellular_systems = QPushButton("Subcellular Systems")
        self.btn_subcellular_systems.clicked.connect(self.open_subcellular_system_manager)
        self.right_layout.addWidget(self.btn_subcellular_systems)

        self.main_h_layout.addWidget(self.right_container)

        self.refresh_table()
        self.field_manager.refresh_table()

    def _set_quarter_screen_default_size(self):
        """Use roughly 1/4 of the available screen area by default."""
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(800, 520)
            return

        geometry = screen.availableGeometry()
        width = max(720, int(geometry.width() * 0.5))
        height = max(480, int(geometry.height() * 0.5))

        self.resize(width, height)
        self.move(
            geometry.x() + max(0, (geometry.width() - width) // 2),
            geometry.y() + max(0, (geometry.height() - height) // 2),
        )

    def _ask_parameter_gui_fallback(self, title, label, default_val=1) -> Any:
        """
        Advanced parameter/model dispatcher specifically for the window manager.
        Prevents integer casting crashes when cloning rules that contain advanced physical models.
        """
        items = [
            "1 - Fixed Constant (number only)",
            "2 - State / Native Expression ({state_key}, e.g., {volume} * 0.01)",
            "3 - Field Physical Model (diffusion fields only)",
        ]
        choice, ok = QInputDialog.getItem(
            self,
            title,
            f"{label}\nFixed = number only.\nState/native = {{state_key}} expressions.\nPhysical model = diffusion-field regulators only.",
            items,
            0,
            False,
        )
        if not ok:
            return default_val

        if choice.startswith("3"):
            model = build_model_gui("dynamic_parameter", self)
            return model if model is not None else default_val
        elif choice.startswith("2"):
            val, ok = QInputDialog.getText(
                self,
                title,
                f"{label}\nEnter a state/native expression using {{state_key}} names.\nExamples: {{volume}} * 0.01, {{division_count}} + 1",
                text="{volume} * 0.01",
            )
            if not ok or not val.strip():
                return default_val
            return val.strip()
        else:
            d_str = "1" if isinstance(default_val, dict) else str(default_val)
            while True:
                val, ok = QInputDialog.getText(self, title, f"{label}\nPlease enter a numeric constant:", text=d_str)
                if not ok or not val.strip():
                    return default_val
                try:
                    return float(val.strip()) if '.' in val.strip() else int(val.strip())
                except ValueError:
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "Invalid Constant", "Fixed Constant accepts numbers only. Use State / Native Expression for {state_key} formulas.")

    def _case_payload(self, rule):
        cases = rule.get("cases") or []
        if not cases:
            return {}
        return case_payload(cases[0])

    def _first_case_ref(self, rule):
        cases = rule.setdefault("cases", [])
        if not cases:
            cases.append({"when": {"condition_type": "TRUE", "params": {}}})
        return cases[0]

    # Helper function to retrieve all current cell types.
    def get_current_celltypes(self) -> List[str]:
        return list(self.registry.celltype_params.keys())

    # XML reconstruction function for use by `FieldManagerWidget`.
    def trigger_xml_rebuild(self):
        print("🛠️ Triggering XML Rebuild from Field Manager...")
        self.save_and_sync()

    def open_xml_config_editor(self):
        if self.main_editor and hasattr(self.main_editor, "open_xml_config_editor"):
            self.main_editor.open_xml_config_editor()
            return

        from cc3d_builder.gui.xml_config_editor import XMLConfigEditor

        self.xml_config_win = XMLConfigEditor(
            registry=self.registry,
            structure_manager=self.structure_manager,
            injector=self.injector,
            parent=self,
        )
        self.xml_config_win.show()

    def open_intracellular_model_manager(self):
        if self.main_editor and hasattr(self.main_editor, "open_intracellular_model_manager"):
            self.main_editor.open_intracellular_model_manager()
            return

        from cc3d_builder.gui.intracellular_model_dialog import IntracellularModelManagerDialog

        dialog = IntracellularModelManagerDialog(self.registry, parent=self)
        dialog.exec_()

    def open_subcellular_system_manager(self):
        if self.main_editor and hasattr(self.main_editor, "open_subcellular_system_manager"):
            self.main_editor.open_subcellular_system_manager()
            return

        from cc3d_builder.gui.subcellular_system_dialog import SubcellularSystemManagerDialog

        dialog = SubcellularSystemManagerDialog(self.registry, parent=self)
        dialog.exec_()

    def setup_toolbar(self):
        toolbar_layout = QVBoxLayout()
        top_row = QHBoxLayout()
        bottom_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add Rule (Wizard)")
        self.btn_state_keys = QPushButton("State Key Reference")
        self.btn_duplicate = QPushButton("Duplicate Selected")
        self.btn_up = QPushButton("Move Up ↑")
        self.btn_down = QPushButton("Move Down ↓")
        self.btn_delete = QPushButton("Delete Selected")

        self.btn_add.clicked.connect(self.handle_add_new)
        self.btn_state_keys.clicked.connect(self.show_state_key_reference)
        self.btn_duplicate.clicked.connect(self.handle_duplicate)
        self.btn_up.clicked.connect(lambda: self.handle_move(-1))
        self.btn_down.clicked.connect(lambda: self.handle_move(1))
        self.btn_delete.clicked.connect(self.handle_delete)
        self.btn_back = QPushButton("✅ Finish & Return to Main")
        self.btn_back.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_back.clicked.connect(self.handle_back)

        top_row.addWidget(self.btn_add)
        top_row.addWidget(self.btn_state_keys)
        top_row.addStretch()
        top_row.addWidget(self.btn_back)

        bottom_row.addWidget(self.btn_up)
        bottom_row.addWidget(self.btn_down)
        bottom_row.addWidget(self.btn_duplicate)
        bottom_row.addWidget(self.btn_delete)
        bottom_row.addStretch()

        toolbar_layout.addLayout(top_row)
        toolbar_layout.addLayout(bottom_row)
        self.main_layout.addLayout(toolbar_layout) # type: ignore

    def show_state_key_reference(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("State Key Reference")
        dialog.resize(780, 620)

        text = QTextEdit(dialog)
        text.setReadOnly(True)
        text.setPlainText(format_state_key_catalog())

        close_btn = QPushButton("Close", dialog)
        close_btn.clicked.connect(dialog.accept)

        layout = QVBoxLayout(dialog)
        layout.addWidget(text)
        layout.addWidget(close_btn)

        dialog.exec_()

    def setup_table_config(self):
        self.columns = ["ID", "Behaviour", "Target Cell", "Frequency", "Condition", "Apply Params", "Once", "Custom Script"]
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive) # type: ignore
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._apply_rule_table_column_widths()
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

    def _apply_rule_table_column_widths(self):
        widths = [46, 120, 105, 76, 150, 160, 58, 92]
        for idx, width in enumerate(widths):
            self.table.setColumnWidth(idx, width)

    def refresh_table(self):
        self.is_updating_table = True
        self.table.setRowCount(0)
        for rule in self.registry.rules:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, self._read_only_item(rule.get("id")))
            self.table.setItem(row, 1, self._read_only_item(rule.get("behaviour")))
            self.table.setItem(row, 2, QTableWidgetItem(str(rule.get("target", "None"))))

            cases = rule.get("cases", [])

            if cases:
                first_case = cases[0]

                frequency_val = first_case.get("frequency") or rule.get("frequency", 1)

                cond_type = first_case.get("when", {}).get("condition_type", "TRUE")

                payload = self._case_payload(rule)
                model_info = (
                    payload.get("model")
                    or payload.get("system")
                    or payload.get("mode")
                    or payload.get("action")
                    or payload.get("secret_mode")
                    or "Params"
                )
            else:
                frequency_val = rule.get("frequency", 1)

                cond_type = rule.get("when", {}).get("condition_type", "TRUE")

                payload = self._case_payload(rule)
                model_info = (
                    payload.get("model")
                    or payload.get("system")
                    or payload.get("mode")
                    or payload.get("action")
                    or payload.get("secret_mode")
                    or "Params"
                )

            self.table.setItem(row, 3, QTableWidgetItem(str(frequency_val)))
            self.table.setItem(row, 4, self._read_only_item(f"[{cond_type}] Edit..."))
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
            if self.main_editor:
                editor = self.main_editor
                try:
                    handle_new_rule_registration(
                        registry=self.registry,
                        rule=rule,
                        input_handler=lambda m, n, p: editor.ask_params_gui(m, n, editor),
                        sm=self.sm,
                        injector=self.injector
                    )
                    self.refresh_table()
                    self.field_manager.refresh_table()
                    self.save_and_sync()
                    QMessageBox.information(self, "Success", f"Rule {rule['id']} added successfully!")
                except Exception as e:
                    import traceback
                    traceback.print_exc()

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
            self.registry.save_state(quiet=True)
            self.refresh_table()
            self.save_and_sync()
            print(f" Rule {rule_id} has been deleted and JSON sync completed.")

    def handle_duplicate(self):
        curr_row = self.table.currentRow()
        if curr_row == -1:
            QMessageBox.information(self, "Duplicate Rule", "Please select a rule to duplicate.")
            return

        item = self.table.item(curr_row, 0)
        if item is None:
            return

        source_id = item.text()
        source_rule = self.registry.get_rule_by_id(source_id)
        if not source_rule:
            QMessageBox.warning(self, "Duplicate Rule", f"Rule {source_id} was not found.")
            return

        new_rule = copy.deepcopy(source_rule)
        new_rule["id"] = self._next_duplicate_rule_id(source_id)
        new_rule.pop("triggered", None)

        insert_at = curr_row + 1
        self.registry.rules.insert(insert_at, new_rule)
        self.registry._build_index()
        self.registry.save_state(quiet=True)
        self.save_and_sync()
        self.refresh_table()
        self.table.selectRow(insert_at)
        QMessageBox.information(
            self,
            "Duplicate Rule",
            f"Rule {source_id} duplicated as {new_rule['id']}.\nEdit the target cell or parameters as needed.",
        )

    def _next_duplicate_rule_id(self, source_id):
        existing = {str(rule.get("id")) for rule in self.registry.rules}
        base = f"{source_id}_copy"
        if base not in existing:
            return base

        idx = 2
        while f"{base}{idx}" in existing:
            idx += 1
        return f"{base}{idx}"

    # ==========================================
    # order and swap
    # ==========================================
    def handle_move(self, direction):
        curr_row = self.table.currentRow()
        target_row = curr_row + direction
        if 0 <= target_row < len(self.registry.rules):
            self.registry.rules[curr_row], self.registry.rules[target_row] = \
                self.registry.rules[target_row], self.registry.rules[curr_row]
            self.registry.save_state(quiet=True)
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
                if self.main_editor:
                    editor = self.main_editor
                    handle_new_rule_registration(
                        registry=self.registry,
                        rule=rule,
                        input_handler=lambda m, n, p: editor.ask_params_gui(m, n, editor),
                        sm = self.sm,
                        injector = self.injector,
                    )

            elif col == 3:

                raw_freq = item.text().strip()
                try:
                    rule["frequency"] = int(raw_freq)
                except ValueError:
                    rule["frequency"] = raw_freq

            elif col == 6:
                rule["once"] = (item.checkState() == Qt.Checked)

            elif col == 7: # Custom Script Path
                raw_path = item.text().strip()
                rule["custom_script"] = Path(raw_path).as_posix() if raw_path != "None" else "None"

            self.registry.update_rule(rule_id, rule)
            self.field_manager.refresh_table()
            self.save_and_sync()
            self.refresh_table()
            print(f"✅ Auto-saved inline edit for Rule {rule_id}")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save edit: {str(e)}")
            self.refresh_table()


    def on_cell_double_clicked(self, row, col):

        item = self.table.item(row, 0)
        if item is None: return

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
            if beh == "custom_script":
                mode = "params"
            else:
                mode = self._choose_block_edit_mode(
                    "Edit Condition",
                    "Edit existing condition parameters only",
                    "Rebuild condition logic from wizard",
                )
            if mode == "params":
                case = self._first_case_ref(rule)
                current_cond = copy.deepcopy(case.get("when", rule.get("when", {"condition_type": "TRUE", "params": {}})))
                cond_type = str(current_cond.get("condition_type", "")).strip().lower()
                if cond_type == "custom":
                    params = current_cond.get("params", {}) if isinstance(current_cond.get("params"), dict) else {}
                    script_path = current_cond.get("script_path") or params.get("script_path")
                    if not script_path:
                        QMessageBox.warning(self, "Custom Condition", "This custom condition has no script_path.")
                        return
                    resolved_path = self._resolve_existing_script_path(script_path)
                    if not resolved_path:
                        QMessageBox.warning(self, "Custom Condition", f"Script not found:\n{script_path}")
                        return
                    final_params = collect_custom_params_gui(resolved_path, existing_params=params)
                    if final_params is not None:
                        current_cond["script_path"] = Path(resolved_path).expanduser().as_posix()
                        current_cond["params"] = final_params
                        case["when"] = current_cond
                        updated = True
                else:
                    dialog = RuleBlockReviewDialog(
                        title=f"Condition Parameters - Rule {rule_id}",
                        block=current_cond,
                        locked_keys={"condition_type"},
                        parent=self,
                    )
                    if dialog.exec_() == QDialog.Accepted:
                        case["when"] = dialog.get_updated_block()
                        updated = True
            elif mode == "rebuild":
                new_cond = self.main_editor.build_condition_gui()
                if new_cond:
                    case = self._first_case_ref(rule)
                    case["when"] = new_cond
                    updated = True

        # --- col5 Parameters ---
        elif col == 5:
            if beh == "custom_script":
                mode = "params"
            else:
                mode = self._choose_block_edit_mode(
                    "Edit Behaviour Parameters",
                    "Edit existing parameters only",
                    "Rebuild behaviour parameters from wizard",
                )
            if mode == "params":
                updated = self._edit_apply_params_only(rule, rule_id)
            elif mode == "rebuild":
                new_data = self._collect_rebuilt_apply_params(rule, beh)
                if new_data and beh != "custom_script":
                    self._update_rule_content(rule, new_data)
                    updated = True

        if updated:
            self.registry.update_rule(rule_id, rule)

            mentioned_types = extract_celltypes_from_rule(rule)
            for ct in mentioned_types:
                if ct and ct not in self.registry.celltype_params:
                    params_ct = self.main_editor.ask_params_gui("celltype", ct, self.main_editor)
                    if params_ct:
                        self.registry.add_celltype_params(ct, params_ct["targetVolume"], params_ct["lambdaVolume"])

            mentioned_fields = extract_fields_from_rule(rule)
            for f_name in mentioned_fields:
                if beh == "secrete/uptake" and f_name in self.registry.field_params:
                    self.registry.field_params[f_name]["python_secretion"] = True

                if f_name and f_name not in self.registry.field_params:
                    params_f = self.main_editor.ask_params_gui("field", f_name, self.main_editor)
                    if params_f:
                        if beh == "secrete/uptake":
                            params_f["python_secretion"] = True

                        self.registry.add_field_params(f_name, params_f)
                        self.sm.ensure_field(f_name)
                        self.sm.sync_secretion_plugin_capsule(self.registry.field_params)

            self.registry.save_state(quiet=True)
            self.save_and_sync()
            self.refresh_table()

    def _choose_block_edit_mode(self, title, params_label, rebuild_label):
        choices = [params_label, rebuild_label]
        choice, ok = QInputDialog.getItem(self, title, "What do you want to edit?", choices, 0, False)
        if not ok:
            return None
        return "params" if choice == params_label else "rebuild"

    def _resolve_existing_script_path(self, script_path):
        raw_path = Path(str(script_path)).expanduser()
        candidates = [raw_path]
        if not raw_path.is_absolute():
            candidates.extend([
                Path.cwd() / raw_path,
                self.registry.project_path / raw_path,
                self.registry.project_path / "Simulation" / raw_path,
            ])
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _edit_apply_params_only(self, rule, rule_id):
        beh = rule.get("behaviour", "").lower()

        if beh == "custom_script":
            case = self._first_case_ref(rule)
            payload = case_payload(case)
            script_path = payload.get("script_path") or rule.get("custom_script")
            if script_path and script_path != "None":
                resolved_path = self._resolve_existing_script_path(script_path)
                if not resolved_path:
                    QMessageBox.warning(self, "Custom Script", f"Script not found:\n{script_path}")
                    return False
                saved_params = payload.get("apply_params", rule.get("apply_params", {}))
                final_params = collect_custom_params_gui(resolved_path, existing_params=saved_params)
                if final_params is not None:
                    case["script_path"] = Path(resolved_path).expanduser().as_posix()
                    case["apply_params"] = final_params
                    return True
            return False

        case = self._first_case_ref(rule)
        payload = {
            key: copy.deepcopy(value)
            for key, value in case.items()
            if key != "when"
        }
        dialog = RuleBlockReviewDialog(
            title=f"Apply Parameters - Rule {rule_id}",
            block=payload,
            locked_keys={"action", "mode", "model", "secret_mode"},
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return False

        updated_payload = dialog.get_updated_block()
        when = case.get("when", {"condition_type": "TRUE", "params": {}})
        case.clear()
        case["when"] = when
        case.update(updated_payload)
        return True

    def _collect_rebuilt_apply_params(self, rule, beh):
        if beh == "custom_script":
            return None

        new_data = None
        if beh == "growth":
            from cc3d_builder.gui.build_model_gui import build_model_gui
            res = build_model_gui(beh)
            if res: new_data = res
        elif beh == "differentiate":
            new_data = self.main_editor.collect_diff_params_wizard()

        elif beh == "create":
            new_data = self.main_editor.collect_create_params_wizard()

        elif beh == "death":
            new_data = self.main_editor.collect_death_params_wizard()

        elif beh == "secrete/uptake":
            new_data = self.main_editor.collect_secrete_uptake_params_wizard()

        elif beh == "dormancy":
            res = self.main_editor.collect_dormancy_params_wizard()
            if res:
                new_data = res
                if "frequency" in res:
                    rule["frequency"] = res["frequency"]

        elif beh == "phagocytosis":
            res = self.main_editor.collect_phagocytosis_params_wizard()
            if res:
                new_data = res

        elif beh == "chemotaxis":
            res = self.main_editor.collect_chemotaxis_params_wizard()
            if res: new_data = res

        elif beh == "force":
            res = self.main_editor.collect_force_params_wizard()
            if res: new_data = res

        elif beh == "compartmentalize":
            res = self.main_editor.collect_compartmentalize_params_wizard()
            if res: new_data = res

        elif beh == "fpp_link":
            res = self.main_editor.collect_fpp_link_params_wizard()
            if res: new_data = res

        elif beh == "intracellular_model":
            res = self.main_editor.collect_intracellular_model_params_wizard()
            if res: new_data = res

        elif beh == "subcellular":
            res = self.main_editor.collect_subcellular_params_wizard()
            if res: new_data = res

        return new_data

    def _update_rule_content(self, rule, new_data):
        cases = rule.get("cases") or []
        case = cases[0] if cases else {}
        params = {
            "id": rule.get("id"),
            "target": rule.get("target"),
            "when": case.get("when", rule.get("when", {"condition_type": "TRUE", "params": {}})),
            "frequency": rule.get("frequency", 1),
            "order": rule.get("order"),
            "once": rule.get("once", False),
            "debug": rule.get("debug", False),
        }
        params.update(new_data)

        rebuilt = build_rule(rule.get("behaviour"), params)
        rule["target"] = rebuilt["target"]
        rule["behaviour"] = rebuilt["behaviour"]
        rule["cases"] = rebuilt["cases"]
        rule["frequency"] = rebuilt["frequency"]
        if "order" in rebuilt:
            rule["order"] = rebuilt["order"]
        else:
            rule.pop("order", None)
        rule["once"] = rebuilt["once"]
        rule["debug"] = rebuilt["debug"]

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
        """
        Synchronizes the UI Registry data with the physical simulation files (XML and Python).
        This acts as the bridge between the GUI memory and the CC3D source code.
        """
        try:
            self.registry.commit_artifacts(quiet=True)
            print("✅ [Sync Success] Registry, XML, Python source, and generated code updated.")

        except Exception as e:
            # Log any errors during the file writing process
            print(f"❌ [Sync Error] Failed to rebuild simulation files: {e}")

        # 5. Refresh the Main Editor UI list to reflect any internal changes
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
        from cc3d_builder.gui.build_condition_gui import build_condition_gui as real_builder
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
            editor = self.main_editor
            final_params = process_custom_script(
                file_path = file_path,
                registry = self.registry,
                ask_params_func = lambda m, n, p: editor.ask_params_gui(m, n, editor),
                extract_params_func = extract_params,
                existing_params =rule.get("apply_params", {})
            )
            if final_params:
                rule["apply_params"] = final_params
                rule["custom_script"] = file_path

                self.registry.update_rule(rule_id, rule)
                self.save_and_sync()
                self.refresh_table()

    def open_field_setup(self, field_name):
        # Retrieve the complete data from the Registry,
        # either from the wizard or previously stored data.
        current_params = self.registry.get_field_params(field_name)

        # Instantiate the configuration window you’ve already implemented.
        dialog = FieldSetupDialog(
            field_name=field_name,
            available_celltypes=self.get_current_celltypes(),
            initial_data=current_params,
            parent=self
        )

        # if user hit Confirm
        if dialog.exec_() == QDialog.Accepted:
            updated_data = dialog.get_data()

            # update Registry
            self.registry.update_field(field_name, updated_data)

            # regenerate XML
            self.structure_manager.ensure_field_xml_from_registry(self.registry.get_all_fields())

            # refresh the managewindow
            self.refresh_table()

            print(f"✅ Field {field_name} updated and XML rebuilt.")

class CellInventoryWidget(QGroupBox):
    def __init__(self, registry: 'SimulationRegistry', on_changed_callback=None, ask_cell_func=None, main_editor = None):
        super().__init__("🧬 Cell Initialization Manager")
        self.registry = registry
        self.ask_cell_func = ask_cell_func
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
            if item and item.widget():
                item.widget().deleteLater()

        initializer_summary = self._xml_initializer_summary_by_type()

        # 2. iterate celltypes
        for name, params in self.registry.celltype_params.items():
            name_label = QPushButton(f" {name}")
            name_label.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    font-weight: bold;
                    color: #2196F3;
                    border: none;
                    text-decoration: underline;
                    background: transparent;
                    padding: 0px;
                }
                QPushButton:hover { color: #0b7dda; }
            """)
            name_label.setCursor(Qt.PointingHandCursor)

            # Bind a click event to call the popup function.
            name_label.clicked.connect(lambda _, n=name: self.open_cell_params_dialog(n))

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            summary = initializer_summary.get(name, {"regions": 0, "cells": 0, "unknown": False})
            init_label = QLabel("XML init: yes" if summary["regions"] else "XML init: no")
            if not summary["regions"]:
                count_text = "0 cells"
            elif summary.get("unknown") and not summary.get("cells"):
                count_text = "unknown cells"
            elif summary.get("unknown"):
                count_text = f"~{summary['cells']}+ cells"
            else:
                count_text = f"~{summary['cells']} cells"
            count_label = QLabel(count_text)

            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda _, n=name: self.delete_celltype(n))

            row_layout.addWidget(init_label)
            row_layout.addWidget(count_label)
            row_layout.addWidget(delete_btn)

            # --- add the name_label button as the left column of the form ---
            self.form_layout.addRow(name_label, row_widget)

    def _xml_initializer_summary_by_type(self):
        summary = {}
        structure_manager = self._structure_manager()
        xml_path = getattr(structure_manager, "xml_path", None)
        if not xml_path:
            return summary
        try:
            root = ET.parse(str(xml_path)).getroot()
        except Exception:
            return summary

        for steppable in root.findall(".//Steppable"):
            if not self._is_region_initializer_steppable(steppable):
                continue
            for region in steppable.findall("Region"):
                types = self._split_initializer_types(region.findtext("Types", ""))
                if not types:
                    continue
                count = self._estimate_initializer_region_cells(region)
                for cell_type in types:
                    entry = summary.setdefault(cell_type, {"regions": 0, "cells": 0, "unknown": False})
                    entry["regions"] += 1
                    if count is None:
                        entry["unknown"] = True
                    else:
                        entry["cells"] += max(1, count // len(types))
        return summary

    def _structure_manager(self):
        owner = self.window()
        if owner and hasattr(owner, "structure_manager"):
            return owner.structure_manager
        if self.main_editor and hasattr(self.main_editor, "sm"):
            return self.main_editor.sm
        return None

    def _split_initializer_types(self, raw_types):
        return [item.strip() for item in str(raw_types or "").split(",") if item.strip()]

    @staticmethod
    def _is_region_initializer_steppable(steppable):
        if steppable.tag != "Steppable":
            return False
        kind = f"{steppable.get('Type', '')} {steppable.get('Name', '')}".lower()
        if "initializer" not in kind:
            return False
        return steppable.get("Type") == "UniformInitializer" or bool(steppable.findall("Region"))

    def _estimate_initializer_region_cells(self, region):
        box_min = region.find("BoxMin")
        box_max = region.find("BoxMax")
        if box_min is None or box_max is None:
            return None
        try:
            width = max(1, int(float(region.findtext("Width", "1"))))
            gap = max(0, int(float(region.findtext("Gap", "0"))))
            pitch = max(1, width + gap)
            dx = max(0, int(float(box_max.get("x", 0))) - int(float(box_min.get("x", 0))))
            dy = max(0, int(float(box_max.get("y", 0))) - int(float(box_min.get("y", 0))))
            dz = max(1, int(float(box_max.get("z", 1))) - int(float(box_min.get("z", 0))))
        except (TypeError, ValueError):
            return None
        return max(1, dx // pitch) * max(1, dy // pitch) * max(1, dz)

    def _sync(self):
        self.registry.save()
        if self.on_changed_callback:
            self.on_changed_callback()

    def open_cell_params_dialog(self, cell_name):
        """Pop up the same parameter configuration interface that you used when creating a new cell."""
        editor = self.main_editor

        if not editor:
            parent_win = self.window()
            if hasattr(parent_win, 'main_editor') and parent_win.main_editor:
                editor = parent_win.main_editor
                self.main_editor = editor

        if not self.main_editor or not hasattr(self.main_editor, 'ask_params_gui'):
            print("❌ Error: main_editor or ask_params_gui reference missing!")
            return

        # apply the ask_params functions
        new_params = self.main_editor.ask_params_gui("celltype", cell_name, self.main_editor)

        if new_params:
            # update the parameters in registry
            self.registry.celltype_params[cell_name].update({
                "targetVolume": new_params.get("targetVolume", 50.0),
                "lambdaVolume": new_params.get("lambdaVolume", 2.0)
            })

            self._sync()
            QMessageBox.information(self, "Success", f"Parameters for {cell_name} updated!")

    def delete_celltype(self, cell_name):
        if self._celltype_used_by_rules(cell_name):
            return

        reply = QMessageBox.question(
            self,
            "Delete Cell Type",
            f"Delete cell type '{cell_name}' from registry and XML?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        parent_win = self.window()
        if hasattr(parent_win, "structure_manager") and parent_win.structure_manager:
            parent_win.structure_manager.remove_celltype(cell_name)

        if hasattr(parent_win, "injector") and parent_win.injector:
            parent_win.injector.remove_volume_start_code(cell_name)

        self.registry.delete_celltype(cell_name)

        if parent_win and hasattr(parent_win, "save_and_sync"):
            parent_win.save_and_sync()
        else:
            self._sync()

        self.refresh_list()
        if parent_win and hasattr(parent_win, "field_manager"):
            parent_win.field_manager.available_celltypes = list(self.registry.celltype_params.keys())
            parent_win.field_manager.refresh_table()

        QMessageBox.information(self, "Deleted", f"Cell type '{cell_name}' deleted.")

    def _celltype_used_by_rules(self, cell_name):
        used_by = []
        for rule in self.registry.rules:
            try:
                if cell_name in extract_celltypes_from_rule(rule):
                    used_by.append(str(rule.get("id", "?")))
            except Exception:
                continue

        if used_by:
            QMessageBox.warning(
                self,
                "Cell Type In Use",
                f"Cell type '{cell_name}' is referenced by rule(s): {', '.join(used_by)}.\n"
                "Delete or edit those rules first.",
            )
            return True
        return False

#  for custom scripts parameter modification in MainRuleWindow
class RuleBlockReviewDialog(QDialog):
    def __init__(self, title, block, locked_keys=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(680, 620)
        self.block = copy.deepcopy(block or {})
        self.locked_keys = set(locked_keys or set())
        self.inputs = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Edit parameter values only. Structural keys are read-only; use rebuild mode to change logic/model/action."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.form_layout = QFormLayout(container)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        rows = list(self._iter_leaf_paths(self.block))
        if not rows:
            self.form_layout.addRow(QLabel("No editable parameters found."), QLabel(""))

        for path, value in rows:
            label = self._path_label(path)
            line_edit = QLineEdit(self._value_to_text(value))
            line_edit.setToolTip(f"Original type: {type(value).__name__}")
            if self._path_is_locked(path):
                line_edit.setReadOnly(True)
                line_edit.setStyleSheet("color: #666; background: #f1f1f1;")
            self.inputs[path] = (line_edit, value)
            self.form_layout.addRow(f"{label}:", line_edit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_if_valid)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _iter_leaf_paths(self, value, prefix=()):
        if isinstance(value, dict):
            if not value:
                yield prefix, value
                return
            for key, child in value.items():
                yield from self._iter_leaf_paths(child, prefix + (key,))
            return

        if isinstance(value, list):
            if not value or all(not isinstance(item, (dict, list)) for item in value):
                yield prefix, value
                return
            for index, child in enumerate(value):
                yield from self._iter_leaf_paths(child, prefix + (index,))
            return

        yield prefix, value

    def _path_is_locked(self, path):
        return any(str(part) in self.locked_keys for part in path)

    def _path_label(self, path):
        if not path:
            return "<root>"
        label = ""
        for part in path:
            if isinstance(part, int):
                label += f"[{part}]"
            else:
                label += ("" if not label else ".") + str(part)
        return label

    def _value_to_text(self, value):
        if isinstance(value, (dict, list)):
            import json
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    def _accept_if_valid(self):
        try:
            self.get_updated_block()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Parameter Value", str(exc))
            return
        self.accept()

    def get_updated_block(self):
        updated = copy.deepcopy(self.block)
        for path, (line_edit, original_value) in self.inputs.items():
            if self._path_is_locked(path):
                continue
            parsed = self._parse_text_value(line_edit.text(), original_value, self._path_label(path))
            self._set_path(updated, path, parsed)
        return updated

    def _parse_text_value(self, text, original_value, label):
        raw = text.strip()
        if isinstance(original_value, bool):
            lowered = raw.lower()
            if lowered in {"true", "1", "yes", "y", "on"}:
                return True
            if lowered in {"false", "0", "no", "n", "off"}:
                return False
            raise ValueError(f"{label}: expected boolean true/false.")

        if isinstance(original_value, int) and not isinstance(original_value, bool):
            try:
                return int(float(raw))
            except ValueError as exc:
                raise ValueError(f"{label}: expected integer.") from exc

        if isinstance(original_value, float):
            try:
                return float(raw)
            except ValueError as exc:
                raise ValueError(f"{label}: expected float.") from exc

        if isinstance(original_value, list):
            import json
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [part.strip() for part in raw.split(",") if part.strip()]

        if isinstance(original_value, dict):
            import json
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{label}: expected JSON object.") from exc
            if not isinstance(parsed, dict):
                raise ValueError(f"{label}: expected JSON object.")
            return parsed

        if original_value is None:
            if raw.lower() == "null":
                return None
            return self._parse_json_scalar_or_string(raw)

        return self._parse_json_scalar_or_string(raw)

    def _parse_json_scalar_or_string(self, raw):
        if raw == "":
            return ""
        import json
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, (str, int, float, bool)) or parsed is None:
                return parsed
        except json.JSONDecodeError:
            pass
        return raw

    def _set_path(self, root, path, value):
        target = root
        for part in path[:-1]:
            target = target[part]
        if path:
            target[path[-1]] = value


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

class FieldManagerWidget(QWidget):
    def __init__(self, registry: 'SimulationRegistry', structure_manager, available_celltypes, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.structure_manager = structure_manager
        self.available_celltypes = available_celltypes or list(self.registry.celltype_params.keys())
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Field Name",
            "Solver",
            "Diffusion Constant",
            "Decay Constant",
            "Configure",
            "Delete",
        ])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        for idx, width in enumerate([110, 120, 88, 88, 82, 62]):
            self.table.setColumnWidth(idx, width)

        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)

        layout.addWidget(self.table)
        self.refresh_table()

    def refresh_table(self):
        """Synchronize the latest data from the Registry to the UI list."""
        all_fields = self.registry.get_all_fields()
        # print(f"DEBUG22: FieldManager is refreshing. Found fields: {list(all_fields.keys())}")
        self.table.setRowCount(len(all_fields))

        for row, (name, params) in enumerate(all_fields.items()):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(params.get('solver', 'DiffusionSolverFE')))
            self.table.setItem(row, 2, QTableWidgetItem(str(params.get('diffusion_constant', '0.0'))))
            self.table.setItem(row, 3, QTableWidgetItem(str(params.get('decay_constant', '0.00001'))))

            edit_btn = QPushButton("⚙️ Configure")
            edit_btn.clicked.connect(lambda _, n=name: self.open_field_setup(n))
            self.table.setCellWidget(row, 4, edit_btn)

            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda _, n=name: self.delete_field(n))
            self.table.setCellWidget(row, 5, delete_btn)

    def _owner_window(self):
        owner = self.window()
        if owner is self:
            owner = self.parent()
        return owner

    def open_field_setup(self, field_name):
        owner = self._owner_window()
        if owner and hasattr(owner, "open_field_setup"):
            owner.open_field_setup(field_name)

    def on_item_double_clicked(self, item):
        row = item.row()
        field_name = self.table.item(row, 0).text()
        current_data = self.registry.get_field_params(field_name)

        live_celltypes = list(self.registry.celltype_params.keys())
        # Import the Dialog class and pass in the parent.
        from cc3d_builder.gui.field_setup_dialog import FieldSetupDialog
        dialog = FieldSetupDialog(
            field_name=field_name,
            available_celltypes=live_celltypes,
            initial_data=current_data,
            parent=self
        )

        if dialog.exec_() == QDialog.Accepted:
            new_data = dialog.get_data()
            self.registry.update_field(field_name, new_data)

            owner = self._owner_window()
            if owner and hasattr(owner, 'structure_manager'):
                self.structure_manager.ensure_field_xml_from_registry(self.registry.get_all_fields())

            self.refresh_table()
            if owner and hasattr(owner, "refresh_table"):
                owner.refresh_table()

    def delete_field(self, field_name):
        if self._field_used_by_rules(field_name):
            return

        reply = QMessageBox.question(
            self,
            "Delete Field",
            f"Delete field '{field_name}' from registry and XML?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.registry.delete_field(field_name)

        if self.structure_manager:
            self.structure_manager.ensure_field_xml_from_registry(self.registry.get_all_fields())
            self.structure_manager.save()

        self.refresh_table()
        owner = self._owner_window()
        if owner and hasattr(owner, "refresh_table"):
            owner.refresh_table()
        if owner and hasattr(owner, "save_and_sync"):
            owner.save_and_sync()

        QMessageBox.information(self, "Deleted", f"Field '{field_name}' deleted.")

    def _field_used_by_rules(self, field_name):
        used_by = []
        for rule in self.registry.rules:
            try:
                if field_name in extract_fields_from_rule(rule):
                    used_by.append(str(rule.get("id", "?")))
            except Exception:
                continue

        if used_by:
            QMessageBox.warning(
                self,
                "Field In Use",
                f"Field '{field_name}' is referenced by rule(s): {', '.join(used_by)}.\n"
                "Delete or edit those rules first.",
            )
            return True
        return False
