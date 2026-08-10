# subcellular_system_dialog.py
from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _clean_user_label(value):
    text = str(value or "").strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


class SubcellularSystemManagerDialog(QDialog):
    """Project-level editor for coarse-grained subcellular systems."""

    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.setWindowTitle("Subcellular Systems")
        self.resize(900, 520)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Default Stage", "Stages", "Components", "Attach Cell Types"])

        self.add_btn = QPushButton("Add")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.import_btn = QPushButton("Import CSV")
        self.close_btn = QPushButton("Close")

        self.add_btn.clicked.connect(self.add_system)
        self.edit_btn.clicked.connect(self.edit_system)
        self.delete_btn.clicked.connect(self.delete_system)
        self.import_btn.clicked.connect(self.import_csv)
        self.close_btn.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(self.add_btn)
        buttons.addWidget(self.edit_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addWidget(self.import_btn)
        buttons.addStretch()
        buttons.addWidget(self.close_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self.refresh_table()

    def refresh_table(self):
        systems = list(getattr(self.registry, "subcellular_systems", []) or [])
        self.table.setRowCount(0)
        for spec in systems:
            row = self.table.rowCount()
            self.table.insertRow(row)
            attach = spec.get("attach_to", {}) if isinstance(spec.get("attach_to"), dict) else {}
            cell_types = attach.get("cell_types") or spec.get("cell_types") or []
            if isinstance(cell_types, list):
                cell_types = ", ".join(str(item) for item in cell_types)
            components = spec.get("default_counts") or spec.get("components") or {}
            if isinstance(components, dict):
                component_text = ", ".join(f"{key}:{value}" for key, value in components.items())
            elif isinstance(components, list):
                component_text = ", ".join(str(item) for item in components)
            else:
                component_text = ""
            stages = spec.get("stages") or []
            if isinstance(stages, list):
                stages = ", ".join(str(item) for item in stages)
            values = [
                spec.get("id", ""),
                spec.get("default_stage", ""),
                stages,
                component_text,
                cell_types,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def add_system(self):
        dialog = SubcellularSystemEditDialog(parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        systems = list(getattr(self.registry, "subcellular_systems", []) or [])
        spec = dialog.system_spec()
        if any(str(item.get("id")) == str(spec.get("id")) for item in systems):
            QMessageBox.warning(self, "Duplicate System", f"Subcellular system id already exists: {spec.get('id')}")
            return
        systems.append(spec)
        self.registry.subcellular_systems = systems
        self.registry.save()
        self.refresh_table()

    def edit_system(self):
        row = self.table.currentRow()
        if row < 0:
            return
        systems = list(getattr(self.registry, "subcellular_systems", []) or [])
        if row >= len(systems):
            return
        dialog = SubcellularSystemEditDialog(systems[row], parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        systems[row] = dialog.system_spec()
        self.registry.subcellular_systems = systems
        self.registry.save()
        self.refresh_table()

    def delete_system(self):
        row = self.table.currentRow()
        if row < 0:
            return
        systems = list(getattr(self.registry, "subcellular_systems", []) or [])
        if row >= len(systems):
            return
        del systems[row]
        self.registry.subcellular_systems = systems
        self.registry.save()
        self.refresh_table()

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Subcellular Systems CSV",
            "",
            "CSV Files (*.csv)",
        )
        if not path:
            return

        try:
            from cc3d_builder.core.csv_importer import import_subcellular_systems_from_csv

            imported = import_subcellular_systems_from_csv(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))
            return

        existing = {
            str(item.get("id"))
            for item in getattr(self.registry, "subcellular_systems", []) or []
            if isinstance(item, dict)
        }
        systems = [
            item
            for item in getattr(self.registry, "subcellular_systems", []) or []
            if isinstance(item, dict)
        ]
        for spec in imported:
            spec_id = str(spec.get("id"))
            if spec_id in existing:
                systems = [spec if str(item.get("id")) == spec_id else item for item in systems]
            else:
                systems.append(spec)
                existing.add(spec_id)

        self.registry.subcellular_systems = systems
        self.registry.save()
        self.refresh_table()
        QMessageBox.information(self, "Import Complete", f"Imported {len(imported)} subcellular system(s).")


class SubcellularSystemEditDialog(QDialog):
    def __init__(self, spec: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Subcellular System")
        self.resize(760, 560)
        spec = spec or {}

        attach = spec.get("attach_to", {}) if isinstance(spec.get("attach_to"), dict) else {}
        cell_types = attach.get("cell_types") or spec.get("cell_types") or []

        self.id_input = QLineEdit(str(spec.get("id", "")))
        self.id_input.setPlaceholderText("Enter a unique system ID")
        self.stages_input = QLineEdit(", ".join(str(item) for item in spec.get("stages", [])))
        self.stages_input.setPlaceholderText("Enter comma-separated stage names")
        self.default_stage_input = QLineEdit(str(spec.get("default_stage", "")))
        self.default_stage_input.setPlaceholderText("Optional; uses the first stage if blank")
        self.attach_input = QLineEdit(", ".join(cell_types) if isinstance(cell_types, list) else str(cell_types))
        self.attach_input.setPlaceholderText("Enter attached cell types")

        self.components_table = QTableWidget(0, 2)
        self.components_table.setHorizontalHeaderLabels(["Component", "Default count"])
        self.components_table.setMaximumHeight(130)
        self.localization_table = QTableWidget(0, 2)
        self.localization_table.setHorizontalHeaderLabels(["Location", "Default value"])
        self.localization_table.setMaximumHeight(120)

        for component, value in self._component_defaults(spec).items():
            self._add_table_row(self.components_table, component, value)
        for location, value in self._localization_defaults(spec).items():
            self._add_table_row(self.localization_table, location, value)

        add_component_btn = QPushButton("Add Component")
        remove_component_btn = QPushButton("Remove Component")
        add_location_btn = QPushButton("Add Location")
        remove_location_btn = QPushButton("Remove Location")
        add_component_btn.clicked.connect(lambda: self._add_table_row(self.components_table, "", 0))
        remove_component_btn.clicked.connect(lambda: self._remove_selected(self.components_table))
        add_location_btn.clicked.connect(lambda: self._add_table_row(self.localization_table, "", 0.0))
        remove_location_btn.clicked.connect(lambda: self._remove_selected(self.localization_table))

        component_buttons = QHBoxLayout()
        component_buttons.addWidget(add_component_btn)
        component_buttons.addWidget(remove_component_btn)
        component_buttons.addStretch()

        location_buttons = QHBoxLayout()
        location_buttons.addWidget(add_location_btn)
        location_buttons.addWidget(remove_location_btn)
        location_buttons.addStretch()

        form = QFormLayout()
        form.addRow("System ID:", self.id_input)
        form.addRow("Stages:", self.stages_input)
        form.addRow("Default stage:", self.default_stage_input)
        form.addRow("Attach cell types:", self.attach_input)
        form.addRow("Components:", self.components_table)
        form.addRow("", self._wrap_layout(component_buttons))
        form.addRow("Localizations:", self.localization_table)
        form.addRow("", self._wrap_layout(location_buttons))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self):
        try:
            self.system_spec()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Subcellular System", str(exc))
            return
        super().accept()

    def system_spec(self):
        system_id = _clean_user_label(self.id_input.text())
        if not system_id:
            raise ValueError("System ID is required")
        stages = [_clean_user_label(part) for part in self.stages_input.text().split(",") if _clean_user_label(part)]
        default_stage = _clean_user_label(self.default_stage_input.text()) or (stages[0] if stages else "unassigned")
        if stages and default_stage not in stages:
            stages.insert(0, default_stage)
        return {
            "id": system_id,
            "scope": "cell",
            "stages": stages,
            "default_stage": default_stage,
            "attach_to": {"cell_types": [_clean_user_label(part) for part in self.attach_input.text().split(",") if _clean_user_label(part)]},
            "default_counts": self._table_dict(self.components_table),
            "default_localization": self._table_dict(self.localization_table),
        }

    def _component_defaults(self, spec):
        values = spec.get("default_counts") or spec.get("components") or {}
        if isinstance(values, dict):
            return values
        if isinstance(values, list):
            result = {}
            for item in values:
                if isinstance(item, dict):
                    name = item.get("id") or item.get("name") or item.get("component")
                    if name:
                        result[str(name)] = item.get("initial_count", item.get("count", 0))
                elif item:
                    result[str(item)] = 0
            return result
        return {}

    def _localization_defaults(self, spec):
        values = spec.get("default_localization") or spec.get("localization") or {}
        return values if isinstance(values, dict) else {}

    def _add_table_row(self, table, key, value):
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(str(key)))
        table.setItem(row, 1, QTableWidgetItem(str(value)))

    def _remove_selected(self, table):
        rows = sorted({item.row() for item in table.selectedItems()}, reverse=True)
        if not rows and table.rowCount():
            rows = [table.rowCount() - 1]
        for row in rows:
            table.removeRow(row)

    def _table_dict(self, table):
        values = {}
        for row in range(table.rowCount()):
            key_item = table.item(row, 0)
            value_item = table.item(row, 1)
            if key_item is None or not key_item.text().strip():
                continue
            values[_clean_user_label(key_item.text())] = self._parse_scalar(value_item.text().strip() if value_item else "0")
        return values

    def _parse_scalar(self, text):
        lowered = str(text).strip().lower()
        if lowered in {"true", "yes", "y", "on"}:
            return True
        if lowered in {"false", "no", "n", "off"}:
            return False
        try:
            return int(text)
        except (TypeError, ValueError):
            pass
        try:
            return float(text)
        except (TypeError, ValueError):
            return _clean_user_label(text)

    def _wrap_layout(self, source_layout):
        widget = QWidget(self)
        container = QHBoxLayout(widget)
        container.setContentsMargins(0, 0, 0, 0)
        while source_layout.count():
            item = source_layout.takeAt(0)
            if item.widget() is not None:
                container.addWidget(item.widget())
            elif item.spacerItem() is not None:
                container.addItem(item.spacerItem())
        return widget
