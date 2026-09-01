# xml_config_editor.py
import copy
import xml.etree.ElementTree as ET
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cc3d_builder.gui.field_setup_dialog import FieldSetupDialog
from cc3d_builder.utils_extensions.rule_parsing import extract_celltypes_from_rule, extract_fields_from_rule


class XMLConfigEditor(QDialog):
    """Small CC3D XML-aware editor for common model parameters."""

    def __init__(self, registry, structure_manager, injector=None, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.structure_manager = structure_manager
        self.injector = injector
        self.xml_path = Path(self.structure_manager.xml_path)
        self._reload_structure_manager_tree()
        self._xml_mtime_ns = self._current_xml_mtime_ns()

        self.celltype_params = copy.deepcopy(getattr(self.registry, "celltype_params", {}) or {})
        self.field_params = copy.deepcopy(getattr(self.registry, "field_params", {}) or {})
        self.initializer_regions = self._read_initializer_regions_from_xml()
        self.pif_config = self._read_pif_config()
        self._updating_initializer_table = False
        self._updating_initializer_mode = False
        self._deleted_celltypes = set()
        self._deleted_fields = set()

        self.setWindowTitle("CC3D XML Config Editor")
        self.resize(900, 620)
        self._build_ui()
        self.reload_from_memory()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        notice = QLabel(
            "Small XML editor: edit common CC3D parameters, then save once. "
            "If the XML changes in another window, saving is blocked until Reload."
        )
        notice.setWordWrap(True)
        main_layout.addWidget(notice)

        self.tabs = QTabWidget()
        self.cell_tab = QWidget()
        self.contact_tab = QWidget()
        self.field_tab = QWidget()
        self.initializer_tab = QWidget()
        self.tabs.addTab(self.cell_tab, "Cell Types / Volume")
        self.tabs.addTab(self.contact_tab, "Contact Matrix")
        self.tabs.addTab(self.field_tab, "Fields")
        self.tabs.addTab(self.initializer_tab, "Initializer")
        main_layout.addWidget(self.tabs)

        self._build_cell_tab()
        self._build_contact_tab()
        self._build_field_tab()
        self._build_initializer_tab()

        btn_row = QHBoxLayout()
        self.reload_btn = QPushButton("Reload")
        self.save_btn = QPushButton("Save XML Config")
        self.close_btn = QPushButton("Close")
        self.reload_btn.clicked.connect(self.reload_from_disk)
        self.save_btn.clicked.connect(self.save_changes)
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.reload_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.close_btn)
        main_layout.addLayout(btn_row)

    def _build_cell_tab(self):
        layout = QVBoxLayout(self.cell_tab)
        button_row = QHBoxLayout()
        add_btn = QPushButton("Add Cell Type")
        delete_btn = QPushButton("Delete Selected")
        add_btn.clicked.connect(self.add_celltype)
        delete_btn.clicked.connect(self.delete_selected_celltype)
        button_row.addWidget(add_btn)
        button_row.addWidget(delete_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.cell_table = QTableWidget(0, 6)
        self.cell_table.setHorizontalHeaderLabels([
            "Type Name", "TypeId", "TargetVolume", "LambdaVolume", "XML Init", "Est. XML Cells"
        ])
        self.cell_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cell_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.cell_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for idx, width in enumerate([180, 70, 120, 120, 90, 130]):
            self.cell_table.setColumnWidth(idx, width)
        layout.addWidget(self.cell_table)
        hint = QLabel("Spatial initialization is controlled by the Initializer tab. XML Init and Est. XML Cells are read-only summaries.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def _build_contact_tab(self):
        layout = QVBoxLayout(self.contact_tab)
        hint = QLabel("Edit Contact adhesion energy. Lower HostCell-AttachedFungus values make stronger attachment.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.contact_table = QTableWidget(0, 0)
        self.contact_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.contact_table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        layout.addWidget(self.contact_table)

    def _build_field_tab(self):
        layout = QVBoxLayout(self.field_tab)
        button_row = QHBoxLayout()
        add_btn = QPushButton("Add Field")
        configure_btn = QPushButton("Configure Selected")
        delete_btn = QPushButton("Delete Selected")
        add_btn.clicked.connect(self.add_field)
        configure_btn.clicked.connect(self.configure_selected_field)
        delete_btn.clicked.connect(self.delete_selected_field)
        button_row.addWidget(add_btn)
        button_row.addWidget(configure_btn)
        button_row.addWidget(delete_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.field_table = QTableWidget(0, 6)
        self.field_table.setHorizontalHeaderLabels([
            "Field Name", "Solver", "Diffusion", "Decay", "Initial Expression", "Python Secretion"
        ])
        self.field_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.field_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.field_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for idx, width in enumerate([160, 160, 100, 100, 260, 120]):
            self.field_table.setColumnWidth(idx, width)
        layout.addWidget(self.field_table)

    def _build_initializer_tab(self):
        layout = QVBoxLayout(self.initializer_tab)
        hint = QLabel(
            "Edit the real XML <Steppable Type=\"UniformInitializer\"> regions. "
            "Each enabled row writes one <Region>; estimated cells are approximate."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        pif_group = QGroupBox("PIF / PIFF Import and Export")
        pif_layout = QVBoxLayout(pif_group)
        pif_note = QLabel(
            "PIF import uses CC3D PIFInitializer. Export uses RuleParser's "
            "cluster-aware PIFF dumper, so compartment cluster ids are preserved."
        )
        pif_note.setWordWrap(True)
        pif_layout.addWidget(pif_note)

        self.pif_import_enabled = QCheckBox("Import initial lattice from PIF")
        self.pif_import_enabled.toggled.connect(self._on_pif_import_toggled)
        pif_layout.addWidget(self.pif_import_enabled)
        import_row = QHBoxLayout()
        self.pif_import_path = QLineEdit()
        self.pif_import_path.setPlaceholderText("Simulation/init.piff")
        import_browse_btn = QPushButton("Browse")
        import_browse_btn.clicked.connect(self._browse_pif_initializer)
        import_row.addWidget(self.pif_import_path)
        import_row.addWidget(import_browse_btn)
        pif_layout.addLayout(import_row)

        self.pif_dumper_enabled = QCheckBox("Export lattice snapshots to PIF")
        pif_layout.addWidget(self.pif_dumper_enabled)
        export_form = QFormLayout()
        export_row = QHBoxLayout()
        self.pif_dumper_path = QLineEdit()
        self.pif_dumper_path.setPlaceholderText("Simulation/snapshot")
        export_browse_btn = QPushButton("Browse")
        export_browse_btn.clicked.connect(self._browse_pif_dumper)
        export_row.addWidget(self.pif_dumper_path)
        export_row.addWidget(export_browse_btn)
        self.pif_dumper_frequency = QSpinBox()
        self.pif_dumper_frequency.setRange(1, 1000000000)
        self.pif_dumper_frequency.setValue(100)
        export_form.addRow("Export base name:", export_row)
        export_form.addRow("Frequency:", self.pif_dumper_frequency)
        pif_layout.addLayout(export_form)
        layout.addWidget(pif_group)

        button_row = QHBoxLayout()
        add_btn = QPushButton("Add Region")
        delete_btn = QPushButton("Delete Selected")
        refresh_btn = QPushButton("Refresh Estimates")
        add_btn.clicked.connect(self.add_initializer_region)
        delete_btn.clicked.connect(self.delete_selected_initializer_region)
        refresh_btn.clicked.connect(self.refresh_initializer_estimates)
        button_row.addWidget(add_btn)
        button_row.addWidget(delete_btn)
        button_row.addWidget(refresh_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.initializer_table = QTableWidget(0, 11)
        self.initializer_table.setHorizontalHeaderLabels([
            "Use", "Types", "Min X", "Min Y", "Min Z", "Max X", "Max Y", "Max Z", "Width", "Gap", "Est. Cells"
        ])
        self.initializer_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.initializer_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.initializer_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for idx, width in enumerate([50, 170, 70, 70, 60, 70, 70, 60, 80, 70, 90]):
            self.initializer_table.setColumnWidth(idx, width)
        self.initializer_table.itemChanged.connect(self._on_initializer_item_changed)
        layout.addWidget(self.initializer_table)

    def reload_from_memory(self):
        self._populate_cell_table()
        self._populate_contact_table()
        self._populate_field_table()
        self._populate_initializer_table()
        self._populate_pif_controls()

    def reload_from_disk(self):
        if self.registry:
            self.registry.load()
        self._reload_structure_manager_tree()
        self._xml_mtime_ns = self._current_xml_mtime_ns()
        self.celltype_params = copy.deepcopy(getattr(self.registry, "celltype_params", {}) or {})
        self.field_params = copy.deepcopy(getattr(self.registry, "field_params", {}) or {})
        self.initializer_regions = self._read_initializer_regions_from_xml()
        self.pif_config = self._read_pif_config()
        self._deleted_celltypes.clear()
        self._deleted_fields.clear()
        self.reload_from_memory()

    def _populate_cell_table(self):
        self.cell_table.setRowCount(0)
        xml_ids = self._xml_celltype_ids()
        initializer_summary = self._initializer_summary_by_type()
        for name, params in self.celltype_params.items():
            row = self.cell_table.rowCount()
            self.cell_table.insertRow(row)
            summary = initializer_summary.get(name, {"regions": 0, "cells": 0})
            self.cell_table.setItem(row, 0, self._readonly_item(name))
            self.cell_table.setItem(row, 1, self._readonly_item(xml_ids.get(name, "")))
            self.cell_table.setItem(row, 2, QTableWidgetItem(str(params.get("targetVolume", 50.0))))
            self.cell_table.setItem(row, 3, QTableWidgetItem(str(params.get("lambdaVolume", 2.0))))
            self.cell_table.setItem(row, 4, self._readonly_item("yes" if summary["regions"] else "no"))
            self.cell_table.setItem(row, 5, self._readonly_item(f"~{summary['cells']}" if summary["regions"] else "0"))

    def _populate_contact_table(self):
        types = self._all_xml_celltypes(include_medium=True)
        if not types:
            types = ["Medium"] + list(self.celltype_params.keys())
        matrix = self._read_contact_matrix(types)
        self.contact_table.setRowCount(len(types))
        self.contact_table.setColumnCount(len(types))
        self.contact_table.setHorizontalHeaderLabels(types)
        self.contact_table.setVerticalHeaderLabels(types)
        for row, t1 in enumerate(types):
            for col, t2 in enumerate(types):
                item = QTableWidgetItem(str(matrix.get(self._pair_key(t1, t2), "10.0")))
                self.contact_table.setItem(row, col, item)

    def _populate_field_table(self):
        self.field_table.setRowCount(0)
        for name, params in self.field_params.items():
            row = self.field_table.rowCount()
            self.field_table.insertRow(row)
            self.field_table.setItem(row, 0, self._readonly_item(name))
            self.field_table.setItem(row, 1, QTableWidgetItem(str(params.get("solver", "DiffusionSolverFE"))))
            self.field_table.setItem(row, 2, QTableWidgetItem(str(params.get("diffusion_constant", 0.01))))
            self.field_table.setItem(row, 3, QTableWidgetItem(str(params.get("decay_constant", 0.0001))))
            self.field_table.setItem(row, 4, QTableWidgetItem(str(params.get("initial_expression", "0.0"))))
            py_box = QCheckBox()
            py_box.setChecked(bool(params.get("python_secretion", False)))
            py_box.setStyleSheet("margin-left: 40px;")
            self.field_table.setCellWidget(row, 5, py_box)

    def _populate_initializer_table(self):
        self._updating_initializer_table = True
        try:
            self.initializer_table.setRowCount(0)
            for region in self.initializer_regions:
                self._insert_initializer_row(region)
        finally:
            self._updating_initializer_table = False
        self.refresh_initializer_estimates()

    def _insert_initializer_row(self, region):
        row = self.initializer_table.rowCount()
        self.initializer_table.insertRow(row)

        use_box = QCheckBox()
        use_box.setChecked(bool(region.get("enabled", True)))
        use_box.setStyleSheet("margin-left: 14px;")
        use_box.toggled.connect(self._on_initializer_use_toggled)
        self.initializer_table.setCellWidget(row, 0, use_box)

        self.initializer_table.setItem(row, 1, QTableWidgetItem(str(region.get("types", ""))))
        for col, key in enumerate(["min_x", "min_y", "min_z", "max_x", "max_y", "max_z", "width", "gap"], start=2):
            self.initializer_table.setItem(row, col, QTableWidgetItem(str(region.get(key, 0))))
        self.initializer_table.setItem(row, 10, self._readonly_item(self._estimate_initializer_cells(region)))

    def add_celltype(self):
        name, ok = QInputDialog.getText(self, "Add Cell Type", "New cell type name:")
        name = name.strip() if ok else ""
        if not name:
            return
        if name.lower() == "medium":
            QMessageBox.warning(self, "Invalid Cell Type", "Medium is the reserved CC3D background type.")
            return
        if name in self.celltype_params:
            QMessageBox.information(self, "Already Exists", f"Cell type '{name}' already exists.")
            return
        self.celltype_params[name] = {
            "targetVolume": 50.0,
            "lambdaVolume": 2.0,
            "should_initialize": True,
            "initial_count": 5,
        }
        self.initializer_regions.append(self._default_initializer_region(name, count=5))
        self._deleted_celltypes.discard(name)
        self.reload_from_memory()

    def delete_selected_celltype(self):
        row = self.cell_table.currentRow()
        if row < 0:
            return
        item = self.cell_table.item(row, 0)
        name = item.text() if item else ""
        if not name:
            return
        used_by = self._celltype_used_by_rules(name)
        if used_by:
            QMessageBox.warning(
                self,
                "Cell Type In Use",
                f"Cannot delete '{name}' because it is used by rule(s): {', '.join(used_by)}",
            )
            return
        reply = QMessageBox.question(
            self,
            "Delete Cell Type",
            f"Delete cell type '{name}' from registry and XML on save?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.celltype_params.pop(name, None)
        self._remove_initializer_type_from_local(name)
        self._deleted_celltypes.add(name)
        self.reload_from_memory()

    def _remove_initializer_type_from_local(self, name):
        updated_regions = []
        for region in self.initializer_regions:
            types = self._split_initializer_types(region.get("types", ""))
            if name not in types:
                updated_regions.append(region)
                continue
            remaining = [cell_type for cell_type in types if cell_type != name]
            if remaining:
                updated_region = copy.deepcopy(region)
                updated_region["types"] = ",".join(remaining)
                updated_regions.append(updated_region)
        self.initializer_regions = updated_regions

    def add_field(self):
        name, ok = QInputDialog.getText(self, "Add Field", "New chemical field name:")
        name = name.strip() if ok else ""
        if not name:
            return
        if name in self.field_params:
            QMessageBox.information(self, "Already Exists", f"Field '{name}' already exists.")
            return
        initial = {
            "solver": "DiffusionSolverFE",
            "diffusion_constant": 0.01,
            "decay_constant": 0.0001,
            "initial_expression": "0.0",
            "boundary_conditions": {},
            "chemotaxis": [],
            "python_secretion": False,
        }
        dialog = FieldSetupDialog(
            field_name=name,
            available_celltypes=list(self.celltype_params.keys()),
            initial_data=initial,
            parent=self,
        )
        if dialog.exec_() == QDialog.Accepted:
            self.field_params[name] = self._normalize_field_dialog_data(dialog.get_data())
            self._deleted_fields.discard(name)
            self.reload_from_memory()

    def configure_selected_field(self):
        row = self.field_table.currentRow()
        if row < 0:
            return
        name = self.field_table.item(row, 0).text()
        self._collect_field_table_into_local()
        dialog = FieldSetupDialog(
            field_name=name,
            available_celltypes=list(self.celltype_params.keys()),
            initial_data=self.field_params.get(name, {}),
            parent=self,
        )
        if dialog.exec_() == QDialog.Accepted:
            self.field_params[name] = self._normalize_field_dialog_data(dialog.get_data())
            self.reload_from_memory()

    def delete_selected_field(self):
        row = self.field_table.currentRow()
        if row < 0:
            return
        name = self.field_table.item(row, 0).text()
        used_by = self._field_used_by_rules(name)
        if used_by:
            QMessageBox.warning(
                self,
                "Field In Use",
                f"Cannot delete '{name}' because it is used by rule(s): {', '.join(used_by)}",
            )
            return
        reply = QMessageBox.question(
            self,
            "Delete Field",
            f"Delete field '{name}' from registry and XML on save?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.field_params.pop(name, None)
        self._deleted_fields.add(name)
        self.reload_from_memory()

    def add_initializer_region(self):
        self.pif_import_enabled.setChecked(False)
        available = [name for name in self.celltype_params.keys() if str(name).lower() != "medium"]
        default_type = available[0] if available else "Cell"
        self.initializer_regions.append(self._default_initializer_region(default_type))
        self._populate_initializer_table()

    def _default_initializer_region(self, cell_type, count=25):
        width = 5
        gap = 0
        side = int((max(1, int(count)) ** 0.5) * width) + 2
        offset = 20 + (len(self.initializer_regions) % 8) * 15
        return {
            "enabled": True,
            "types": cell_type,
            "min_x": offset,
            "min_y": offset,
            "min_z": 0,
            "max_x": offset + side,
            "max_y": offset + side,
            "max_z": 1,
            "width": width,
            "gap": gap,
        }

    def delete_selected_initializer_region(self):
        row = self.initializer_table.currentRow()
        if row < 0:
            return
        self.initializer_table.removeRow(row)
        try:
            self._collect_initializer_table_into_local()
        except ValueError:
            pass

    def refresh_initializer_estimates(self):
        if not hasattr(self, "initializer_table"):
            return
        self._updating_initializer_table = True
        try:
            for row in range(self.initializer_table.rowCount()):
                try:
                    region = self._initializer_region_from_row(row)
                    estimate = self._estimate_initializer_cells(region)
                except ValueError:
                    estimate = "invalid"
                self.initializer_table.setItem(row, 10, self._readonly_item(estimate))
        finally:
            self._updating_initializer_table = False

    def _on_initializer_item_changed(self, item):
        if self._updating_initializer_table:
            return
        if item and item.column() in {2, 3, 4, 5, 6, 7, 8, 9}:
            self.refresh_initializer_estimates()

    def save_changes(self):
        if self._xml_changed_on_disk():
            QMessageBox.warning(
                self,
                "XML Changed",
                "The XML file was changed after this editor opened. Click Reload before saving to avoid overwriting another window's changes.",
            )
            return

        try:
            self._collect_initializer_table_into_local()
            self._collect_pif_controls_into_local()
            self._collect_cell_table_into_local()
            self._collect_field_table_into_local()
            contact_types, contact_matrix = self._collect_contact_table()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Input", str(exc))
            return

        try:
            self._apply_celltypes_to_registry_and_xml()
            self._apply_fields_to_registry()
            self.structure_manager.ensure_field_xml_from_registry(self.registry.field_params)
            self._write_contact_matrix(contact_types, contact_matrix)
            self._write_initializer_regions()
            self._sync_initializer_layout_to_registry()
            self._write_pif_io()
            self._sync_pif_to_registry()
            self.structure_manager.save()
            self.registry.save()
            self._xml_mtime_ns = self._current_xml_mtime_ns()
            self.reload_from_memory()
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return

        parent = self.parent()
        if parent and hasattr(parent, "refresh_list"):
            parent.refresh_list()
        if parent and hasattr(parent, "manage_win"):
            manage_win = getattr(parent, "manage_win")
            if manage_win:
                if hasattr(manage_win, "refresh_table"):
                    manage_win.refresh_table()
                if hasattr(manage_win, "field_manager"):
                    manage_win.field_manager.available_celltypes = list(self.registry.celltype_params.keys())
                    manage_win.field_manager.refresh_table()
                if hasattr(manage_win, "cell_manager"):
                    manage_win.cell_manager.refresh_list()

        QMessageBox.information(self, "Saved", "XML config saved and synchronized.")

    def _collect_cell_table_into_local(self):
        updated = {}
        initializer_summary = self._initializer_summary_by_type()
        for row in range(self.cell_table.rowCount()):
            name = self.cell_table.item(row, 0).text().strip()
            if not name:
                continue
            target = self._float_cell(self.cell_table, row, 2, f"{name}.TargetVolume")
            lam = self._float_cell(self.cell_table, row, 3, f"{name}.LambdaVolume")
            summary = initializer_summary.get(name, {"regions": 0, "cells": 0})
            updated[name] = {
                "targetVolume": target,
                "lambdaVolume": lam,
                "should_initialize": bool(summary["regions"]),
                "initial_count": int(summary["cells"]),
            }
        self.celltype_params = updated

    def _collect_field_table_into_local(self):
        updated = {}
        for row in range(self.field_table.rowCount()):
            name = self.field_table.item(row, 0).text().strip()
            if not name:
                continue
            old = copy.deepcopy(self.field_params.get(name, {}))
            old["solver"] = self._text_cell(self.field_table, row, 1, "DiffusionSolverFE")
            old["diffusion_constant"] = self._float_cell(self.field_table, row, 2, f"{name}.diffusion")
            old["decay_constant"] = self._float_cell(self.field_table, row, 3, f"{name}.decay")
            old["initial_expression"] = self._text_cell(self.field_table, row, 4, "0.0")
            py_widget = self.field_table.cellWidget(row, 5)
            old["python_secretion"] = bool(py_widget.isChecked()) if isinstance(py_widget, QCheckBox) else False
            old.setdefault("boundary_conditions", {})
            old.setdefault("chemotaxis", [])
            updated[name] = old
        self.field_params = updated

    def _collect_initializer_table_into_local(self):
        updated = []
        for row in range(self.initializer_table.rowCount()):
            updated.append(self._initializer_region_from_row(row))
        self.initializer_regions = updated

    def _populate_pif_controls(self):
        if not hasattr(self, "pif_import_enabled"):
            return
        config = self._normalize_pif_config(self.pif_config)
        initializer = config["initializer"]
        dumper = config["dumper"]
        self.pif_import_enabled.setChecked(bool(initializer.get("enabled")))
        self.pif_import_path.setText(str(initializer.get("path", "")))
        self.pif_dumper_enabled.setChecked(bool(dumper.get("enabled")))
        self.pif_dumper_path.setText(str(dumper.get("path", "")))
        self.pif_dumper_frequency.setValue(max(1, int(dumper.get("frequency", 100))))
        self._apply_initializer_mode_exclusivity()

    def _collect_pif_controls_into_local(self):
        initializer_path = self.pif_import_path.text().strip()
        dumper_path = self._pif_dumper_base_name(self.pif_dumper_path.text().strip())
        if self.pif_import_enabled.isChecked() and not initializer_path:
            raise ValueError("PIF import path cannot be empty when PIF import is enabled.")
        if self.pif_dumper_enabled.isChecked() and not dumper_path:
            raise ValueError("PIF export base name cannot be empty when PIF export is enabled.")
        self.pif_config = {
            "initializer": {
                "enabled": bool(self.pif_import_enabled.isChecked()),
                "path": initializer_path,
            },
            "dumper": {
                "enabled": bool(self.pif_dumper_enabled.isChecked()),
                "path": dumper_path,
                "frequency": int(self.pif_dumper_frequency.value()),
            },
        }
        if self.pif_config["initializer"]["enabled"]:
            for region in self.initializer_regions:
                region["enabled"] = False

    def _write_pif_io(self):
        if hasattr(self.structure_manager, "update_pif_io"):
            self.structure_manager.update_pif_io(self.pif_config)

    def _sync_pif_to_registry(self):
        settings = self.registry.settings if isinstance(self.registry.settings, dict) else {}
        self.registry.settings = settings
        settings["piff"] = copy.deepcopy(self._normalize_pif_config(self.pif_config))

    def _on_pif_import_toggled(self, checked):
        if self._updating_initializer_mode or self._updating_initializer_table:
            return
        if checked:
            self._updating_initializer_mode = True
            try:
                for row in range(self.initializer_table.rowCount()):
                    widget = self.initializer_table.cellWidget(row, 0)
                    if isinstance(widget, QCheckBox):
                        widget.setChecked(False)
            finally:
                self._updating_initializer_mode = False
        self._apply_initializer_mode_exclusivity()

    def _on_initializer_use_toggled(self, checked):
        if self._updating_initializer_mode or self._updating_initializer_table:
            return
        if checked and self.pif_import_enabled.isChecked():
            self._updating_initializer_mode = True
            try:
                self.pif_import_enabled.setChecked(False)
            finally:
                self._updating_initializer_mode = False
        self._apply_initializer_mode_exclusivity()

    def _apply_initializer_mode_exclusivity(self):
        if not hasattr(self, "initializer_table") or not hasattr(self, "pif_import_enabled"):
            return
        pif_import_enabled = bool(self.pif_import_enabled.isChecked())
        self.initializer_table.setEnabled(not pif_import_enabled)

    def _read_pif_config(self):
        config = self._settings_pif_config()
        root = getattr(self.structure_manager, "root", None)
        if root is None:
            return config

        initializer = self._find_steppable_by_type("PIFInitializer")
        if initializer is not None:
            config["initializer"] = {
                "enabled": True,
                "path": self._child_text(initializer, "PIFName", ""),
            }

        dumper = self._find_steppable_by_type("PIFDumper")
        if dumper is not None and not config.get("dumper", {}).get("enabled"):
            config["dumper"] = {
                "enabled": True,
                "path": self._child_text(dumper, "PIFName", ""),
                "frequency": self._xml_int_attr(dumper, "Frequency", 100),
            }

        return self._normalize_pif_config(config)

    def _settings_pif_config(self):
        settings = getattr(self.registry, "settings", {}) or {}
        if not isinstance(settings, dict):
            return self._default_pif_config()
        raw = settings.get("piff") or settings.get("pif") or settings.get("pif_io")
        return self._normalize_pif_config(raw)

    @staticmethod
    def _default_pif_config():
        return {
            "initializer": {"enabled": False, "path": ""},
            "dumper": {"enabled": False, "path": "", "frequency": 100},
        }

    def _normalize_pif_config(self, raw):
        if not isinstance(raw, dict):
            raw = {}
        initializer = raw.get("initializer") or raw.get("import") or {}
        dumper = raw.get("dumper") or raw.get("export") or {}
        if not isinstance(initializer, dict):
            initializer = {}
        if not isinstance(dumper, dict):
            dumper = {}

        try:
            frequency = int(float(dumper.get("frequency", dumper.get("Frequency", 100))))
        except (TypeError, ValueError):
            frequency = 100

        return {
            "initializer": {
                "enabled": bool(initializer.get("enabled", initializer.get("use", False))),
                "path": str(
                    initializer.get("path")
                    or initializer.get("pif_name")
                    or initializer.get("PIFName")
                    or ""
                ).strip(),
            },
            "dumper": {
                "enabled": bool(dumper.get("enabled", dumper.get("use", False))),
                "path": str(
                    dumper.get("path")
                    or dumper.get("base_name")
                    or dumper.get("pif_name")
                    or dumper.get("PIFName")
                    or ""
                ).strip(),
                "frequency": max(1, frequency),
            },
        }

    def _find_steppable_by_type(self, type_name):
        wanted = str(type_name).strip().lower()
        root = getattr(self.structure_manager, "root", None)
        if root is None:
            return None
        for steppable in root.findall(".//Steppable"):
            current = str(steppable.get("Type", steppable.get("Name", ""))).strip().lower()
            if current == wanted:
                return steppable
        return None

    def _browse_pif_initializer(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select PIF / PIFF Initializer",
            self._dialog_start_path(self.pif_import_path.text()),
            "PIF files (*.pif *.piff);;All files (*)",
        )
        if filename:
            self.pif_import_path.setText(self._project_relative_or_absolute(filename))

    def _browse_pif_dumper(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Select PIF Export Base Name",
            self._dialog_start_path(self.pif_dumper_path.text() or "Simulation/snapshot"),
            "PIF files (*.pif *.piff);;All files (*)",
        )
        if filename:
            self.pif_dumper_path.setText(
                self._pif_dumper_base_name(self._project_relative_or_absolute(filename))
            )

    def _dialog_start_path(self, text):
        text = str(text or "").strip()
        if text:
            path = Path(text).expanduser()
            if not path.is_absolute():
                path = self._project_root() / path
            return str(path)
        return str(self._project_root() / "Simulation")

    def _project_root(self):
        return Path(getattr(self.structure_manager, "project_path", self.xml_path.parent.parent)).expanduser().resolve()

    def _project_relative_or_absolute(self, filename):
        path = Path(filename).expanduser()
        try:
            resolved = path.resolve()
            project_root = self._project_root()
            return str(resolved.relative_to(project_root))
        except ValueError:
            return str(path.resolve())
        except OSError:
            return str(path)

    @staticmethod
    def _pif_dumper_base_name(path_text):
        path_text = str(path_text or "").strip()
        lower = path_text.lower()
        for suffix in (".piff", ".pif"):
            if lower.endswith(suffix):
                return path_text[:-len(suffix)]
        return path_text

    def _initializer_region_from_row(self, row):
        use_widget = self.initializer_table.cellWidget(row, 0)
        enabled = bool(use_widget.isChecked()) if isinstance(use_widget, QCheckBox) else True
        types = self._text_cell(self.initializer_table, row, 1, "").strip()
        if not types:
            raise ValueError(f"Initializer row {row + 1}: Types cannot be empty.")
        return {
            "enabled": enabled,
            "types": types,
            "min_x": self._int_cell(self.initializer_table, row, 2, f"Initializer row {row + 1}.Min X"),
            "min_y": self._int_cell(self.initializer_table, row, 3, f"Initializer row {row + 1}.Min Y"),
            "min_z": self._int_cell(self.initializer_table, row, 4, f"Initializer row {row + 1}.Min Z"),
            "max_x": self._int_cell(self.initializer_table, row, 5, f"Initializer row {row + 1}.Max X"),
            "max_y": self._int_cell(self.initializer_table, row, 6, f"Initializer row {row + 1}.Max Y"),
            "max_z": self._int_cell(self.initializer_table, row, 7, f"Initializer row {row + 1}.Max Z"),
            "width": max(1, self._int_cell(self.initializer_table, row, 8, f"Initializer row {row + 1}.Width")),
            "gap": max(0, self._int_cell(self.initializer_table, row, 9, f"Initializer row {row + 1}.Gap")),
        }

    def _collect_contact_table(self):
        types = [self.contact_table.horizontalHeaderItem(col).text() for col in range(self.contact_table.columnCount())]
        matrix = {}
        for row, t1 in enumerate(types):
            for col, t2 in enumerate(types):
                if col < row:
                    continue
                item = self.contact_table.item(row, col)
                text = item.text().strip() if item else "10.0"
                try:
                    value = float(text)
                except ValueError as exc:
                    raise ValueError(f"Contact energy {t1}-{t2} must be numeric.") from exc
                matrix[self._pair_key(t1, t2)] = value
        return types, matrix

    def _apply_celltypes_to_registry_and_xml(self):
        current_names = set(self.registry.celltype_params.keys())
        new_names = set(self.celltype_params.keys())
        for name in sorted(current_names - new_names):
            self.registry.celltype_params.pop(name, None)
            self.structure_manager.remove_celltype(name)
            if self.injector and hasattr(self.injector, "remove_volume_start_code"):
                self.injector.remove_volume_start_code(name)

        if hasattr(self.structure_manager, "_seen_celltypes"):
            self.structure_manager._seen_celltypes = set()

        for name, params in self.celltype_params.items():
            self.registry.celltype_params[name] = params
            self.structure_manager.ensure_celltype(name, create_initializer=False)
            if self.injector and hasattr(self.injector, "ensure_volume_start_code"):
                self.injector.ensure_volume_start_code(
                    celltype_name=name,
                    target_volume=params.get("targetVolume", 50.0),
                    lambda_volume=params.get("lambdaVolume", 2.0),
                )

        self.registry._build_index()

    def _apply_fields_to_registry(self):
        self.registry.field_params = copy.deepcopy(self.field_params)

    def _write_contact_matrix(self, types, matrix):
        plugin = self.structure_manager.root.find(".//Plugin[@Name='Contact']")
        if plugin is None:
            plugin = ET.SubElement(self.structure_manager.root, "Plugin", {"Name": "Contact"})

        preserved_children = [child for child in list(plugin) if child.tag != "Energy"]
        for child in list(plugin):
            plugin.remove(child)

        for i, t1 in enumerate(types):
            for j in range(i, len(types)):
                t2 = types[j]
                value = matrix.get(self._pair_key(t1, t2), 10.0)
                energy = ET.SubElement(plugin, "Energy", {"Type1": t1, "Type2": t2})
                energy.text = str(value)

        for child in preserved_children:
            plugin.append(child)

    def _write_initializer_regions(self):
        for parent in self.structure_manager.root.iter():
            for steppable in list(parent):
                if self._is_uniform_initializer_steppable(steppable):
                    parent.remove(steppable)

        enabled_regions = [region for region in self.initializer_regions if region.get("enabled", True)]
        if not enabled_regions:
            return

        steppable = ET.Element("Steppable", {"Type": "UniformInitializer"})
        for region in enabled_regions:
            region_elem = ET.SubElement(steppable, "Region")
            ET.SubElement(region_elem, "BoxMin", {
                "x": str(region["min_x"]),
                "y": str(region["min_y"]),
                "z": str(region["min_z"]),
            })
            ET.SubElement(region_elem, "BoxMax", {
                "x": str(region["max_x"]),
                "y": str(region["max_y"]),
                "z": str(region["max_z"]),
            })
            gap = ET.SubElement(region_elem, "Gap")
            gap.text = str(region["gap"])
            width = ET.SubElement(region_elem, "Width")
            width.text = str(region["width"])
            types = ET.SubElement(region_elem, "Types")
            types.text = str(region["types"])

        self.structure_manager.root.append(steppable)

    def _sync_initializer_layout_to_registry(self):
        settings = self.registry.settings if isinstance(self.registry.settings, dict) else {}
        self.registry.settings = settings
        settings["initial_layout"] = {
            "regions": self._initializer_regions_for_registry(),
        }

    def _initializer_regions_for_registry(self):
        if self._pif_import_enabled():
            return []
        regions = []
        for region in self.initializer_regions:
            if not region.get("enabled", True):
                continue
            regions.append({
                "types": str(region.get("types", "")).strip(),
                "box_min": {
                    "x": int(region.get("min_x", 0)),
                    "y": int(region.get("min_y", 0)),
                    "z": int(region.get("min_z", 0)),
                },
                "box_max": {
                    "x": int(region.get("max_x", 1)),
                    "y": int(region.get("max_y", 1)),
                    "z": int(region.get("max_z", 1)),
                },
                "width": int(region.get("width", 5)),
                "gap": int(region.get("gap", 0)),
            })
        return regions

    def _read_initializer_regions_from_xml(self):
        regions = []
        root = getattr(self.structure_manager, "root", None)
        if root is None:
            return regions
        for steppable in root.findall(".//Steppable"):
            if not self._is_uniform_initializer_steppable(steppable):
                continue
            for region in steppable.findall("Region"):
                box_min = region.find("BoxMin")
                box_max = region.find("BoxMax")
                if box_min is None or box_max is None:
                    continue
                regions.append({
                    "enabled": True,
                    "types": self._child_text(region, "Types", "Cell"),
                    "min_x": self._xml_int_attr(box_min, "x", 0),
                    "min_y": self._xml_int_attr(box_min, "y", 0),
                    "min_z": self._xml_int_attr(box_min, "z", 0),
                    "max_x": self._xml_int_attr(box_max, "x", 0),
                    "max_y": self._xml_int_attr(box_max, "y", 0),
                    "max_z": self._xml_int_attr(box_max, "z", 1),
                    "gap": self._xml_int_text(region, "Gap", 0),
                    "width": max(1, self._xml_int_text(region, "Width", 10)),
                })
        return regions

    def _pif_import_enabled(self):
        if hasattr(self, "pif_import_enabled"):
            return bool(self.pif_import_enabled.isChecked())
        config = self._normalize_pif_config(getattr(self, "pif_config", {}))
        return bool(config.get("initializer", {}).get("enabled"))

    def _estimate_initializer_cells(self, region):
        count = self._estimate_initializer_cell_count(region)
        if count is None:
            return "invalid"
        return f"~{count}"

    def _estimate_initializer_cell_count(self, region):
        try:
            width = max(1, int(region.get("width", 1)))
            gap = max(0, int(region.get("gap", 0)))
            pitch = max(1, width + gap)
            dx = max(0, int(region.get("max_x", 0)) - int(region.get("min_x", 0)))
            dy = max(0, int(region.get("max_y", 0)) - int(region.get("min_y", 0)))
            dz = max(1, int(region.get("max_z", 1)) - int(region.get("min_z", 0)))
        except (TypeError, ValueError):
            return None

        nx = max(1, dx // pitch)
        ny = max(1, dy // pitch)
        nz = max(1, dz)
        return nx * ny * nz

    def _initializer_summary_by_type(self):
        summary = {}
        for region in self.initializer_regions:
            if not region.get("enabled", True):
                continue
            types = self._split_initializer_types(region.get("types", ""))
            if not types:
                continue
            total = self._estimate_initializer_cell_count(region)
            if total is None:
                continue
            per_type = max(1, total // len(types))
            for cell_type in types:
                entry = summary.setdefault(cell_type, {"regions": 0, "cells": 0})
                entry["regions"] += 1
                entry["cells"] += per_type
        return summary

    def _split_initializer_types(self, raw_types):
        return [item.strip() for item in str(raw_types or "").split(",") if item.strip()]

    @staticmethod
    def _is_uniform_initializer_steppable(steppable):
        if steppable.tag != "Steppable":
            return False
        return "uniforminitializer" in {
            str(steppable.get("Type", "")).lower(),
            str(steppable.get("Name", "")).lower(),
        }

    def _normalize_field_dialog_data(self, data):
        data = data or {}
        def get_val(*keys, default=None):
            for key in keys:
                if key in data:
                    return data[key]
            return default

        return {
            "solver": get_val("Solver", "solver", default="DiffusionSolverFE"),
            "diffusion_constant": get_val("GlobalDiffusionConstant", "diffusion_constant", default=0.01),
            "decay_constant": get_val("GlobalDecayConstant", "decay_constant", default=0.0001),
            "initial_expression": get_val("InitialConcentrationExpression", "initial_expression", default="0.0"),
            "boundary_conditions": get_val("BoundaryConditions", "boundary_conditions", default={}) or {},
            "chemotaxis": get_val("Chemotaxis", "chemotaxis", default=[]) or [],
            "python_secretion": bool(get_val("ControlSecretionPython", "python_secretion", default=False)),
        }

    def _read_contact_matrix(self, types):
        matrix = {}
        plugin = self.structure_manager.root.find(".//Plugin[@Name='Contact']")
        if plugin is not None:
            for energy in plugin.findall("Energy"):
                t1 = energy.get("Type1")
                t2 = energy.get("Type2")
                if not t1 or not t2:
                    continue
                matrix[self._pair_key(t1, t2)] = energy.text or "10.0"
        for t1 in types:
            for t2 in types:
                matrix.setdefault(self._pair_key(t1, t2), "10.0")
        return matrix

    def _all_xml_celltypes(self, include_medium=False):
        plugin = self.structure_manager.root.find(".//Plugin[@Name='CellType']")
        if plugin is None:
            return []
        names = []
        for ct in plugin.findall("CellType"):
            name = ct.get("TypeName")
            if not name:
                continue
            if not include_medium and name.lower() == "medium":
                continue
            names.append(name)
        for name in self.celltype_params:
            if name not in names:
                names.append(name)
        return names

    def _xml_celltype_ids(self):
        plugin = self.structure_manager.root.find(".//Plugin[@Name='CellType']")
        if plugin is None:
            return {}
        return {
            ct.get("TypeName"): ct.get("TypeId", "")
            for ct in plugin.findall("CellType")
            if ct.get("TypeName")
        }

    def _child_text(self, parent, tag, default=""):
        child = parent.find(tag)
        if child is None or child.text is None:
            return default
        return child.text.strip() or default

    def _xml_int_attr(self, elem, attr, default=0):
        try:
            return int(float(elem.get(attr, default)))
        except (TypeError, ValueError):
            return default

    def _xml_int_text(self, parent, tag, default=0):
        try:
            return int(float(self._child_text(parent, tag, str(default))))
        except (TypeError, ValueError):
            return default

    def _celltype_used_by_rules(self, name):
        used = []
        for rule in self.registry.rules:
            try:
                if name == rule.get("target") or name in extract_celltypes_from_rule(rule):
                    used.append(str(rule.get("id", "?")))
            except Exception:
                if name == rule.get("target"):
                    used.append(str(rule.get("id", "?")))
        return sorted(set(used))

    def _field_used_by_rules(self, name):
        used = []
        for rule in self.registry.rules:
            try:
                if name in extract_fields_from_rule(rule):
                    used.append(str(rule.get("id", "?")))
            except Exception:
                continue
        return sorted(set(used))

    def _reload_structure_manager_tree(self):
        self.structure_manager.tree = ET.parse(str(self.xml_path))
        self.structure_manager.root = self.structure_manager.tree.getroot()
        if hasattr(self.structure_manager, "_seen_celltypes"):
            self.structure_manager._seen_celltypes = set()

    def _xml_changed_on_disk(self):
        current = self._current_xml_mtime_ns()
        return self._xml_mtime_ns is not None and current is not None and current != self._xml_mtime_ns

    def _current_xml_mtime_ns(self):
        try:
            return self.xml_path.stat().st_mtime_ns
        except FileNotFoundError:
            return None

    def _readonly_item(self, value):
        item = QTableWidgetItem(str(value))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _text_cell(self, table, row, col, default=""):
        item = table.item(row, col)
        text = item.text().strip() if item else ""
        return text if text else default

    def _float_cell(self, table, row, col, label):
        item = table.item(row, col)
        text = item.text().strip() if item else ""
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{label} must be numeric.") from exc

    def _int_cell(self, table, row, col, label):
        item = table.item(row, col)
        text = item.text().strip() if item else ""
        try:
            return int(float(text))
        except ValueError as exc:
            raise ValueError(f"{label} must be an integer.") from exc

    def _pair_key(self, t1, t2):
        return tuple(sorted((str(t1), str(t2))))
