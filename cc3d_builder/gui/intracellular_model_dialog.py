# intracellular_model_dialog.py
from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cc3d_builder.core.csv_importer import import_intracellular_models_from_csv


MODEL_REGISTRY_CSV_EXAMPLE = """id,engine,model_name,source_kind,boolean_network_path,simulation_configuration_path,source_path,attach_cell_types,step_size,initial_conditions,inputs,outputs
DeltaNotch,maboss,DeltaNotch,file,models/delta_notch.bnd,models/delta_notch.cfg,,"Tip",1.0,"{""NICD"": false}","[{""model_var"": ""Delta_ext"", ""from"": ""neighbor_average"", ""source_model"": ""DeltaNotch"", ""source_var"": ""Delta"", ""target_type"": ""Tip"", ""default"": 0.0}]","[{""model_var"": ""NICD"", ""to"": ""state"", ""key"": ""notch_active""}]"
NotchSBML,sbml,NotchSBML,file,,,models/notch.xml,"Tip, Segment",1.0,"{}","[]","[{""model_var"": ""NICD"", ""to"": ""state"", ""key"": ""notch_active""}]"
"""


class IntracellularModelManagerDialog(QDialog):
    """Project-level editor for intracellular model registry entries."""

    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.setWindowTitle("Intracellular Models")
        self.resize(900, 520)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Engine", "Model Name", "Source", "Attach Cell Types"])

        self.add_btn = QPushButton("Add")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.import_btn = QPushButton("Import Registry CSV")
        self.example_btn = QPushButton("CSV Example")
        self.close_btn = QPushButton("Close")

        self.add_btn.clicked.connect(self.add_model)
        self.edit_btn.clicked.connect(self.edit_model)
        self.delete_btn.clicked.connect(self.delete_model)
        self.import_btn.clicked.connect(self.import_registry_csv)
        self.example_btn.clicked.connect(self.show_csv_example)
        self.close_btn.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(self.add_btn)
        buttons.addWidget(self.edit_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addWidget(self.import_btn)
        buttons.addWidget(self.example_btn)
        buttons.addStretch()
        buttons.addWidget(self.close_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.refresh_table()

    def refresh_table(self):
        models = list(getattr(self.registry, "intracellular_models", []) or [])
        self.table.setRowCount(0)
        for spec in models:
            row = self.table.rowCount()
            self.table.insertRow(row)
            source = spec.get("source", {}) if isinstance(spec.get("source"), dict) else {}
            attach = spec.get("attach_to", {}) if isinstance(spec.get("attach_to"), dict) else {}
            cell_types = attach.get("cell_types") or spec.get("cell_types") or []
            if isinstance(cell_types, list):
                cell_types = ", ".join(str(item) for item in cell_types)
            source_text = (
                source.get("path")
                or source.get("boolean_network_path")
                or source.get("bnd_path")
                or source.get("kind")
                or ""
            )

            values = [
                spec.get("id", ""),
                spec.get("engine", ""),
                spec.get("model_name", spec.get("alias", "")),
                source_text,
                cell_types,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def add_model(self):
        dialog = IntracellularModelEditDialog(parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        models = list(getattr(self.registry, "intracellular_models", []) or [])
        spec = dialog.model_spec()
        if any(str(item.get("id")) == str(spec.get("id")) for item in models):
            QMessageBox.warning(self, "Duplicate Model", f"Model id already exists: {spec.get('id')}")
            return
        models.append(spec)
        self.registry.intracellular_models = models
        self.registry.save()
        self.refresh_table()

    def import_registry_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Intracellular Model Registry CSV",
            "",
            "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            imported_models = import_intracellular_models_from_csv(path)
            added, updated = self._merge_imported_models(imported_models)
            self.registry.save()
            self.refresh_table()
            QMessageBox.information(
                self,
                "Model Registry Imported",
                f"Imported {len(imported_models)} model(s): {added} added, {updated} updated.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))

    def _merge_imported_models(self, imported_models):
        current_models = list(getattr(self.registry, "intracellular_models", []) or [])
        index_by_key = {}

        for index, spec in enumerate(current_models):
            if not isinstance(spec, dict):
                continue
            for key in (spec.get("id"), spec.get("model_name"), spec.get("alias")):
                if key:
                    index_by_key[str(key)] = index

        added = 0
        updated = 0
        for spec in imported_models:
            keys = [str(key) for key in (spec.get("id"), spec.get("model_name"), spec.get("alias")) if key]
            match_index = next((index_by_key[key] for key in keys if key in index_by_key), None)
            if match_index is None:
                current_models.append(spec)
                new_index = len(current_models) - 1
                for key in keys:
                    index_by_key[key] = new_index
                added += 1
            else:
                current_models[match_index] = spec
                for key in keys:
                    index_by_key[key] = match_index
                updated += 1

        self.registry.intracellular_models = current_models
        return added, updated

    def show_csv_example(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Intracellular Model Registry CSV Example")
        dialog.resize(980, 520)

        text = QTextEdit(dialog)
        text.setReadOnly(True)
        text.setPlainText(
            "This CSV imports model registry entries, not behaviour rules.\n"
            "Use behaviour=intracellular_model in the normal Rules CSV to execute a registered model.\n\n"
            "File-mode columns:\n"
            "- MaBoSS: boolean_network_path and simulation_configuration_path\n"
            "- SBML/Antimony/CellML: source_path\n"
            "- inputs/outputs/initial_conditions are CSV cells containing JSON.\n\n"
            + MODEL_REGISTRY_CSV_EXAMPLE
        )

        close_btn = QPushButton("Close", dialog)
        close_btn.clicked.connect(dialog.accept)

        layout = QVBoxLayout(dialog)
        layout.addWidget(text)
        layout.addWidget(close_btn)
        dialog.exec_()

    def edit_model(self):
        row = self.table.currentRow()
        if row < 0:
            return
        models = list(getattr(self.registry, "intracellular_models", []) or [])
        if row >= len(models):
            return
        dialog = IntracellularModelEditDialog(models[row], parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        models[row] = dialog.model_spec()
        self.registry.intracellular_models = models
        self.registry.save()
        self.refresh_table()

    def delete_model(self):
        row = self.table.currentRow()
        if row < 0:
            return
        models = list(getattr(self.registry, "intracellular_models", []) or [])
        if row >= len(models):
            return
        del models[row]
        self.registry.intracellular_models = models
        self.registry.save()
        self.refresh_table()


INPUT_SOURCE_MODES = [
    "constant",
    "time",
    "cell_attribute",
    "field",
    "contact_ratio",
    "neighbor_average",
    "cell_dict",
    "state",
    "model_variable",
]

OUTPUT_TARGET_MODES = [
    "intracellular",
    "state",
    "cell_dict",
    "cell_attribute",
]


def _combo(options, current):
    combo = QComboBox()
    combo.addItems(options)
    if current in options:
        combo.setCurrentText(current)
    return combo


def _table_text(table, row, col):
    item = table.item(row, col)
    return item.text().strip() if item is not None else ""


def _combo_text(table, row, col):
    widget = table.cellWidget(row, col)
    return widget.currentText().strip() if isinstance(widget, QComboBox) else ""


def _display_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parse_scalar(text):
    value = str(text).strip()
    lowered = value.lower()
    if lowered in {"true", "yes", "y", "on"}:
        return True
    if lowered in {"false", "no", "n", "off"}:
        return False
    if lowered in {"none", "null"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _mapping_list(value):
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _input_mode(value):
    aliases = {
        "value": "constant",
        "mcs": "time",
        "global_time": "time",
        "cell": "cell_attribute",
        "cell_attr": "cell_attribute",
        "field_sample": "field",
        "environment": "field",
        "contact": "contact_ratio",
        "neighbor_avg": "neighbor_average",
        "intracellular": "model_variable",
    }
    text = str(value or "constant").strip().lower()
    return aliases.get(text, text) if aliases.get(text, text) in INPUT_SOURCE_MODES else "constant"


def _output_mode(value):
    aliases = {
        "cache": "intracellular",
        "cell_attr": "cell_attribute",
    }
    text = str(value or "intracellular").strip().lower()
    return aliases.get(text, text) if aliases.get(text, text) in OUTPUT_TARGET_MODES else "intracellular"


def _input_source_key(mapping, from_mode):
    if from_mode == "field":
        return str(mapping.get("field_name") or mapping.get("field") or mapping.get("source_key") or "")
    if from_mode in {"cell_attribute", "cell_dict", "state"}:
        return str(mapping.get("key") or mapping.get("source_key") or mapping.get("attr") or "")
    if from_mode in {"neighbor_average", "model_variable"}:
        return str(mapping.get("source_var") or mapping.get("model_var") or mapping.get("variable") or "")
    if from_mode == "contact_ratio":
        return str(mapping.get("target_type") or mapping.get("cell_type") or mapping.get("source_key") or "")
    return ""


class InitialConditionTable(QWidget):
    """Small table editor for model initial variable values."""

    def __init__(self, values: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Variable", "Initial value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.add_btn = QPushButton("Add Initial Value")
        self.remove_btn = QPushButton("Remove Selected")
        self.add_btn.clicked.connect(lambda: self.add_row())
        self.remove_btn.clicked.connect(self.remove_selected)

        buttons = QHBoxLayout()
        buttons.addWidget(self.add_btn)
        buttons.addWidget(self.remove_btn)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        for variable, value in (values or {}).items():
            self.add_row(variable, value)

        self.setMinimumHeight(120)

    def add_row(self, variable="", value=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(variable)))
        self.table.setItem(row, 1, QTableWidgetItem(_display_value(value)))

    def remove_selected(self):
        rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for row in rows:
            self.table.removeRow(row)

    def values(self):
        values = {}
        for row in range(self.table.rowCount()):
            variable = _table_text(self.table, row, 0)
            if not variable:
                continue
            values[variable] = _parse_scalar(_table_text(self.table, row, 1))
        return values


class MappingTable(QWidget):
    """Table editor for intracellular input/output mappings."""

    def __init__(self, kind: str, mappings: list[dict[str, Any]] | None = None, parent=None):
        super().__init__(parent)
        self.kind = kind

        if kind == "input":
            self.headers = ["Model variable", "From", "Source key / variable", "Source model", "Target type", "Value/default"]
        else:
            self.headers = ["Model variable", "To", "Target key", "Default"]

        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        if kind == "input":
            for index, width in enumerate([140, 135, 185, 135, 115, 110]):
                self.table.setColumnWidth(index, width)
        else:
            for index, width in enumerate([160, 120, 220, 100]):
                self.table.setColumnWidth(index, width)

        self.add_btn = QPushButton("Add Mapping")
        self.remove_btn = QPushButton("Remove Selected")
        self.add_btn.clicked.connect(lambda: self.add_mapping())
        self.remove_btn.clicked.connect(self.remove_selected)

        buttons = QHBoxLayout()
        buttons.addWidget(self.add_btn)
        buttons.addWidget(self.remove_btn)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        for mapping in mappings or []:
            if isinstance(mapping, dict):
                self.add_mapping(mapping)

        self.setMinimumHeight(155)

    def add_mapping(self, mapping: dict[str, Any] | None = None):
        mapping = mapping or {}
        row = self.table.rowCount()
        self.table.insertRow(row)

        if self.kind == "input":
            from_mode = _input_mode(mapping.get("from") or mapping.get("source_kind") or mapping.get("source"))
            self.table.setItem(row, 0, QTableWidgetItem(str(mapping.get("model_var") or mapping.get("variable") or "")))
            self.table.setCellWidget(row, 1, _combo(INPUT_SOURCE_MODES, from_mode))
            self.table.setItem(row, 2, QTableWidgetItem(_input_source_key(mapping, from_mode)))
            self.table.setItem(row, 3, QTableWidgetItem(str(mapping.get("source_model") or "")))
            self.table.setItem(row, 4, QTableWidgetItem(str(mapping.get("target_type") or mapping.get("cell_type") or "")))
            self.table.setItem(row, 5, QTableWidgetItem(_display_value(mapping.get("value", mapping.get("default", "")))))
            return

        to_mode = _output_mode(mapping.get("to") or mapping.get("target_kind"))
        self.table.setItem(row, 0, QTableWidgetItem(str(mapping.get("model_var") or mapping.get("variable") or "")))
        self.table.setCellWidget(row, 1, _combo(OUTPUT_TARGET_MODES, to_mode))
        self.table.setItem(row, 2, QTableWidgetItem(str(mapping.get("key") or mapping.get("target_key") or "")))
        self.table.setItem(row, 3, QTableWidgetItem(_display_value(mapping.get("default", ""))))

    def remove_selected(self):
        rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for row in rows:
            self.table.removeRow(row)

    def mappings(self):
        if self.kind == "input":
            return self._input_mappings()
        return self._output_mappings()

    def _input_mappings(self):
        mappings = []
        for row in range(self.table.rowCount()):
            model_var = _table_text(self.table, row, 0)
            if not model_var:
                continue

            from_mode = _combo_text(self.table, row, 1) or "constant"
            source_key = _table_text(self.table, row, 2)
            source_model = _table_text(self.table, row, 3)
            target_type = _table_text(self.table, row, 4)
            value_text = _table_text(self.table, row, 5)

            mapping = {"model_var": model_var, "from": from_mode}

            if from_mode == "field":
                mapping["field_name"] = source_key
            elif from_mode in {"cell_attribute", "cell_dict", "state"}:
                mapping["key"] = source_key
            elif from_mode in {"neighbor_average", "model_variable"}:
                mapping["source_var"] = source_key
            elif from_mode == "contact_ratio":
                target_type = target_type or source_key

            if source_model:
                mapping["source_model"] = source_model
            if target_type:
                mapping["target_type"] = target_type
            if value_text:
                value = _parse_scalar(value_text)
                if from_mode == "constant":
                    mapping["value"] = value
                else:
                    mapping["default"] = value

            mappings.append(mapping)
        return mappings

    def _output_mappings(self):
        mappings = []
        for row in range(self.table.rowCount()):
            model_var = _table_text(self.table, row, 0)
            if not model_var:
                continue

            mapping = {
                "model_var": model_var,
                "to": _combo_text(self.table, row, 1) or "intracellular",
            }
            key = _table_text(self.table, row, 2)
            default_text = _table_text(self.table, row, 3)
            if key:
                mapping["key"] = key
            if default_text:
                mapping["default"] = _parse_scalar(default_text)
            mappings.append(mapping)
        return mappings


class IntracellularModelEditDialog(QDialog):
    def __init__(self, spec: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Intracellular Model")
        self.resize(980, 620)
        spec = spec or {}

        source = spec.get("source", {}) if isinstance(spec.get("source"), dict) else {}
        attach = spec.get("attach_to", {}) if isinstance(spec.get("attach_to"), dict) else {}
        solver = spec.get("solver", {}) if isinstance(spec.get("solver"), dict) else {}

        self.id_input = QLineEdit(str(spec.get("id", "")))
        self.id_input.setPlaceholderText("DeltaNotch")
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["sbml", "antimony", "cellml", "maboss"])
        engine = str(spec.get("engine", "sbml")).lower()
        self.engine_combo.setCurrentText(engine if engine in {"sbml", "antimony", "cellml", "maboss"} else "sbml")
        self.model_name_input = QLineEdit(str(spec.get("model_name", spec.get("alias", spec.get("id", "")))))
        self.model_name_input.setPlaceholderText("Defaults to ID")
        self.source_kind_combo = QComboBox()
        self.source_kind_combo.addItems(["file", "inline"])
        self.source_kind_combo.setCurrentText(str(source.get("kind", spec.get("source_kind", "file"))))
        self.source_path_input = QLineEdit(str(source.get("path", spec.get("path", ""))))
        self.source_path_input.setPlaceholderText("models/delta_notch.xml")
        self.bnd_path_input = QLineEdit(str(
            source.get("boolean_network_path")
            or spec.get("boolean_network_path")
            or source.get("bnd_path")
            or spec.get("bnd_path")
            or ""
        ))
        self.bnd_path_input.setPlaceholderText("models/delta_notch.bnd")
        self.cfg_path_input = QLineEdit(str(
            source.get("simulation_configuration_path")
            or spec.get("simulation_configuration_path")
            or source.get("cfg_path")
            or spec.get("cfg_path")
            or ""
        ))
        self.cfg_path_input.setPlaceholderText("models/delta_notch.cfg")
        self.attach_input = QLineEdit(", ".join(attach.get("cell_types", spec.get("cell_types", []))) if isinstance(attach.get("cell_types", spec.get("cell_types", [])), list) else str(attach.get("cell_types", spec.get("cell_types", ""))))
        self.attach_input.setPlaceholderText("Tip, Segment")
        self.step_size_input = QLineEdit(str(spec.get("step_size", solver.get("step_size", 1.0))))

        self.initial_table = InitialConditionTable(spec.get("initial_conditions", {}))
        self.inputs_table = MappingTable("input", _mapping_list(spec.get("inputs", [])))
        self.outputs_table = MappingTable("output", _mapping_list(spec.get("outputs", [])))
        self.inline_text = QTextEdit()
        self.inline_text.setPlainText(str(source.get("text", spec.get("model_string", ""))))
        self.bnd_text = QTextEdit()
        self.bnd_text.setPlainText(str(
            source.get("boolean_network_text")
            or spec.get("boolean_network_text")
            or source.get("bnd")
            or spec.get("bnd_str")
            or ""
        ))
        self.cfg_text = QTextEdit()
        self.cfg_text.setPlainText(str(
            source.get("simulation_configuration_text")
            or spec.get("simulation_configuration_text")
            or source.get("cfg")
            or spec.get("cfg_str")
            or ""
        ))

        for widget, height in (
            (self.inline_text, 300),
            (self.bnd_text, 220),
            (self.cfg_text, 220),
        ):
            widget.setMinimumHeight(height)
            widget.setMaximumHeight(height)

        model_tab = QWidget()
        form = QFormLayout(model_tab)
        self.form = form
        form.addRow("ID:", self.id_input)
        form.addRow("Engine:", self.engine_combo)
        form.addRow("Model name:", self.model_name_input)
        form.addRow("Source kind:", self.source_kind_combo)
        form.addRow("Source path:", self.source_path_input)
        form.addRow("Boolean network description path:", self.bnd_path_input)
        form.addRow("Simulation configuration path:", self.cfg_path_input)
        form.addRow("Attach cell types:", self.attach_input)
        form.addRow("Step size:", self.step_size_input)

        mapping_tab = QWidget()
        mapping_layout = QVBoxLayout(mapping_tab)
        mapping_layout.addWidget(self.initial_table)
        mapping_layout.addWidget(self.inputs_table)
        mapping_layout.addWidget(self.outputs_table)

        inline_tab = QWidget()
        inline_form = QFormLayout(inline_tab)
        self.inline_form = inline_form
        inline_form.addRow("Inline model text:", self.inline_text)
        inline_form.addRow("Inline Boolean network description:", self.bnd_text)
        inline_form.addRow("Inline Simulation configuration:", self.cfg_text)

        self.tabs = QTabWidget()
        self.tabs.addTab(model_tab, "Model")
        self.tabs.addTab(mapping_tab, "Mappings")
        self.tabs.addTab(inline_tab, "Inline Source")

        self._model_name_edited = bool(self.model_name_input.text().strip())
        self.model_name_input.textEdited.connect(self._mark_model_name_edited)
        self.id_input.textEdited.connect(self._sync_model_name_from_id)
        self.engine_combo.currentTextChanged.connect(self._update_visible_fields)
        self.source_kind_combo.currentTextChanged.connect(self._update_visible_fields)
        self._update_visible_fields()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    def _mark_model_name_edited(self, _text=None):
        self._model_name_edited = bool(self.model_name_input.text().strip())

    def _sync_model_name_from_id(self, text):
        if not self._model_name_edited:
            self.model_name_input.setText(text)

    def _set_form_row_visible(self, form, widget, visible):
        label = form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)
        widget.setVisible(visible)

    def _update_visible_fields(self):
        engine = self.engine_combo.currentText().strip().lower()
        source_kind = self.source_kind_combo.currentText().strip().lower()
        is_maboss = engine == "maboss"
        is_inline = source_kind == "inline"

        self._set_form_row_visible(self.form, self.source_path_input, not is_maboss and not is_inline)
        self._set_form_row_visible(self.form, self.bnd_path_input, is_maboss and not is_inline)
        self._set_form_row_visible(self.form, self.cfg_path_input, is_maboss and not is_inline)
        self._set_form_row_visible(self.inline_form, self.inline_text, not is_maboss and is_inline)
        self._set_form_row_visible(self.inline_form, self.bnd_text, is_maboss and is_inline)
        self._set_form_row_visible(self.inline_form, self.cfg_text, is_maboss and is_inline)
        self.tabs.setTabEnabled(2, is_inline)
        if not is_inline and self.tabs.currentIndex() == 2:
            self.tabs.setCurrentIndex(0)

    def accept(self):
        try:
            self.model_spec()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Model", str(exc))
            return
        super().accept()

    def model_spec(self):
        model_id = self.id_input.text().strip()
        if not model_id:
            raise ValueError("Model id is required")

        model_name = self.model_name_input.text().strip() or model_id
        engine = self.engine_combo.currentText().strip().lower()
        source_kind = self.source_kind_combo.currentText().strip().lower()
        cell_types = [part.strip() for part in self.attach_input.text().split(",") if part.strip()]

        spec = {
            "id": model_id,
            "engine": engine,
            "model_name": model_name,
            "source": {"kind": source_kind},
            "attach_to": {"cell_types": cell_types},
            "solver": {"step_size": float(self.step_size_input.text().strip() or 1.0)},
            "initial_conditions": self.initial_table.values(),
            "inputs": self.inputs_table.mappings(),
            "outputs": self.outputs_table.mappings(),
        }

        if engine == "maboss":
            if source_kind == "inline":
                spec["source"]["boolean_network_text"] = self.bnd_text.toPlainText()
                spec["source"]["simulation_configuration_text"] = self.cfg_text.toPlainText()
            else:
                spec["source"]["boolean_network_path"] = self.bnd_path_input.text().strip()
                spec["source"]["simulation_configuration_path"] = self.cfg_path_input.text().strip()
        elif source_kind == "inline":
            spec["source"]["text"] = self.inline_text.toPlainText()
        else:
            spec["source"]["path"] = self.source_path_input.text().strip()

        return spec
