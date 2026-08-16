# main_editor.py
import json
import os
import re
import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QPushButton, QDialog,
    QInputDialog, QApplication, QMessageBox, QFileDialog, QTextEdit
)
from cc3d_builder.core.rule_builder import build_rule
from cc3d_builder.core.rule_schema import case_payload
from cc3d_builder.core.state_key_catalog import format_state_key_catalog
from cc3d_builder.core.csv_importer import import_rules_from_csv
from cc3d_builder.utils_extensions.utils import  handle_new_rule_registration, ask_params_gui, process_custom_script, extract_params
from cc3d_builder.utils_extensions.rule_parsing import extract_celltypes_from_rule, extract_fields_from_rule
from cc3d_builder.utils_extensions.paths import ROOT, SANDBOX_DIR
from typing import Any
from cc3d_builder.gui.field_setup_dialog import FieldSetupDialog

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    print(f"✅ Framework Root Injected: {PROJECT_ROOT}")

class MainWindow(QWidget):

    def __init__(self, registry=None, sm=None, injector=None):

        super().__init__()
        print(">>> ENTER MAIN WINDOW INIT <<<")
        self.registry = registry
        self.sm = sm
        self.injector = injector
        self.ask_params_gui = ask_params_gui

        layout = QVBoxLayout()

        self.rule_list = QListWidget()

        self.add_btn = QPushButton("Add Rule")
        self.save_btn = QPushButton("Save")
        self.exit_btn = QPushButton("Exit")
        self.manage_rules_btn = QPushButton("Manage Rules (Table View)")
        self.xml_config_btn = QPushButton("XML Config Editor")
        self.intracellular_models_btn = QPushButton("Intracellular Models")
        self.subcellular_systems_btn = QPushButton("Subcellular Systems")
        self.state_keys_btn = QPushButton("State Key Reference")
        self.execution_semantics_btn = QPushButton("Execution Semantics")
        self.manage_rules_btn.clicked.connect(self.open_manage_rules)
        self.xml_config_btn.clicked.connect(self.open_xml_config_editor)
        self.intracellular_models_btn.clicked.connect(self.open_intracellular_model_manager)
        self.subcellular_systems_btn.clicked.connect(self.open_subcellular_system_manager)
        self.state_keys_btn.clicked.connect(self.show_state_key_reference)
        self.execution_semantics_btn.clicked.connect(self.set_execution_semantics)

        self.add_btn.clicked.connect(self.gui_add_rule)
        self.save_btn.clicked.connect(self.save)
        self.import_btn = QPushButton("Import Rules CSV")
        self.exit_btn.clicked.connect(self.close)
        self.import_btn.clicked.connect(self.clicked_import_csv)


        layout.addWidget(self.manage_rules_btn)
        layout.addWidget(self.xml_config_btn)
        layout.addWidget(self.intracellular_models_btn)
        layout.addWidget(self.subcellular_systems_btn)
        layout.addWidget(self.state_keys_btn)
        layout.addWidget(self.execution_semantics_btn)
        layout.addWidget(self.rule_list)
        layout.addWidget(self.add_btn)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.exit_btn)
        layout.addWidget(self.import_btn)

        self.setLayout(layout)

        if self.registry:
            self.refresh_list()

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

    def set_execution_semantics(self):
        if not self.registry:
            return

        options = ["snapshot", "asynchronous"]
        current = self.registry.settings.get("execution_semantics", "snapshot")
        index = options.index(current) if current in options else 0
        value, ok = QInputDialog.getItem(
            self,
            "Execution Semantics",
            "Choose how matched rules are committed within each MCS:",
            options,
            index,
            False,
        )
        if not ok:
            return

        self.registry.settings["execution_semantics"] = value
        self.registry.commit_artifacts(quiet=True)
        QMessageBox.information(self, "Execution Semantics", f"Execution semantics set to: {value}")

    def _ask_parameter_gui(self, title, label, default_val=1.0):
        """
        Allow users to choose a fixed numeric value, a state/native expression,
        or a field-regulated physical model.
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
            from cc3d_builder.gui.build_model_gui import build_model_gui
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
            while True:
                val, ok = QInputDialog.getText(self, title, f"{label}\nPlease enter a numeric constant:", text=str(default_val))
                if not ok or not val.strip():
                    return default_val
                try:
                    return float(val.strip())
                except ValueError:
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "Invalid Constant", "Fixed Constant accepts numbers only. Use State / Native Expression for {state_key} formulas.")

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

    def _format_dynamic_param(self, param_val) -> str:
        """
        Built-in helper: Advanced parameter/model visualization formatter.
        If the parameter is a plain number or pure formula text, return it as-is.
        If the parameter is a complex physical model dictionary produced by build_model,
        expand it elegantly into a human-readable topological description.
        """
        if not isinstance(param_val, dict):
            return str(param_val)

        model_type = param_val.get("model", "unknown").lower()
        regulator = param_val.get("regulator", "None")
        params = param_val.get("parameters", {})

        if model_type == "linear":
            return f"Live Model [Linear] (Driven by field '{regulator}') -> Alpha: {params.get('alpha', '?')}"
        elif model_type == "hill":
            return (f"Live Model [Hill Saturation Kinetics] (Regulated by field '{regulator}')\n"
                    f"      - Ymin: {params.get('y_min', '?')}, Ymax: {params.get('y_max', '?')}\n"
                    f"      - Half-saturation K: {params.get('K', '?')}, Hill coefficient n: {params.get('n', '?')}")
        elif model_type == "expression":
            expr = params.get("expression", param_val.get("expression", "?"))
            return f"Live Model [Custom Expression] -> {expr}"

        return f"[Model Asset Dict]: {str(param_val)}"

    def _case_payload(self, rule):
        cases = rule.get("cases") or []
        if not cases:
            return {}
        return case_payload(cases[0])

    def confirm_rule(self, rule, new_types):
        """Enhanced full-link physical model visualization rule confirmation dashboard"""
        if self.registry is None:
            return False

        rule_id = rule.get("id", "?")
        behaviour = rule.get("behaviour", "?")

        message = f"Rule Summary\n\n"
        message += f"ID: {rule_id}\n"
        message += f"Behaviour: {behaviour}\n"
        message += f"Target: {rule.get('target', 'global')}\n"

        when = {}
        if rule.get('when'):
            when = rule.get('when', {})
        elif rule.get('cases') and len(rule['cases']) > 0:
            when = rule['cases'][0].get('when', {})

        if when:
            cond_type = when.get('condition_type', when.get('type', 'TRUE'))
            params = when.get('params', {})

            if cond_type == 'TRUE':
                message += f"Condition: Always True\n"
            elif cond_type in ['time_window', 'TimeWindow']:
                start = params.get('start', params.get('start_mcs', 0))
                end = params.get('end', params.get('end_mcs', 'inf'))
                message += f"Condition: Time Window (MCS {start} - {end})\n"
            elif cond_type == 'Environment':
                sampling = params.get('sampling_mode', 'com')
                extra = ""
                if str(sampling).startswith("radius_"):
                    extra = f", radius={params.get('radius', '?')}"
                elif str(sampling).startswith("contact_boundary_"):
                    extra = f", target_type={params.get('target_type', '?')}"
                message += (
                    f"Condition: Field Environment "
                    f"({params.get('field_name', '?')} {params.get('operator', '?')} {params.get('threshold', '?')}; "
                    f"sampling={sampling}{extra})\n"
                )
            elif cond_type in ['probability', 'Probability']:
                message += f"Condition: Stochastic (Probability p={params.get('p', '?')})\n"
            elif cond_type in ['contact', 'Contact']:
                message += f"Condition: Topology Contact (Ratio with {params.get('target_type', '?')} {params.get('operator', '?')} {params.get('threshold', '?')})\n"
            elif cond_type in ['duration', 'Duration']:
                message += f"Condition: State Lasting (Maintain for >= {params.get('threshold_mcs', '?')} MCS)\n"
            elif cond_type.startswith('Logic_'):
                message += f"Condition: Compound Logical Block ({cond_type})\n"
            else:
                message += f"Condition: Custom / {cond_type}\n"
        else:
            message += f"Condition: Unknown\n"

        message += f"\nRule Details:\n"

        apply_block = self._case_payload(rule)

        if behaviour == "growth":
            if apply_block:
                message += f"  • Regulator: {apply_block.get('regulator', '?')}\n"
                message += f"  • Model: {apply_block.get('model', '?')}\n"

                parameters = apply_block.get('parameters', apply_block)
                model_type = apply_block.get('model', '')

                if model_type == "linear":
                    message += f"  • Alpha: {parameters.get('alpha', '?')}\n"
                elif model_type == "hill":
                    message += f"  • Ymin: {parameters.get('y_min', '?')}\n"
                    message += f"  • Ymax: {parameters.get('y_max', '?')}\n"
                    message += f"  • K: {parameters.get('K', '?')}\n"
                    message += f"  • n: {parameters.get('n', '?')}\n"
                elif model_type == "expression":
                    params_block = apply_block.get('parameters', apply_block)
                    expr_val = params_block.get('expression', apply_block.get('expression', '?'))
                    message += f"  • Expression: {expr_val}\n"
            else:
                message += f"  • No case payload found\n"

        elif behaviour == "differentiate":
            if apply_block:
                mode = apply_block.get('mode', '?')
                message += f"  • Mode: {mode}\n"

                if mode == 'type_switch':
                    message += f"  • New Type: {apply_block.get('new_type', '?')}\n"
                else:
                    p_type = apply_block.get('parent_type', '?')
                    c_type = apply_block.get('child_type', '?')
                    if p_type == c_type:
                        message += f"  • Division: Symmetric ({p_type})\n"
                    else:
                        message += f"  • Division: Asymmetric ({p_type} and {c_type})\n"

                    v_ratio = apply_block.get('volume_ratio', '?')
                    message += f"  • Volume Ratio: {self._format_dynamic_param(v_ratio)}\n"

                    strategy = apply_block.get('inheritance_strategy', 'total')
                    if strategy == 'reset':
                        message += f"  • Memory Inheritance: reset (Parent ages, Child starts brand new at 0)\n"
                    else:
                        message += f"  • Memory Inheritance: total (Both parent and child inherit the aging clock)\n"

                    placement = apply_block.get('placement', {})
                    place_type = placement.get('type', 'random')
                    message += f"  • Placement: {place_type}\n"
            else:
                message += "  • Error: No Differentiate data found\n"

        elif behaviour == "create":
            if apply_block:
                message += f"  • Cell Type: {apply_block.get('cell_type', '?')}\n"
                count_val = apply_block.get('count', '?')
                message += f"  • Count: {self._format_dynamic_param(count_val)}\n"
                dist = apply_block.get('distribution', {})
                message += f"  • Distribution: {dist.get('type', '?')}\n"

        elif behaviour == "death":
            if apply_block:
                mode = apply_block.get("mode", "?")
                message += f"  • Mode: {mode}\n"

                params_block = apply_block.get("parameters", apply_block)

                if mode == "apoptosis":
                    s_rate = params_block.get('shrink_rate', '?')
                    message += f"  • Shrink Rate: {self._format_dynamic_param(s_rate)}\n"
                    terminal_volume = params_block.get('terminal_volume', '?')
                    message += f"  • Terminal Volume: {self._format_dynamic_param(terminal_volume)}\n"
                    message += f"  • Color Change: {params_block.get('color_change', '?')}\n"

                elif mode == "necrosis":
                    sw_rate = params_block.get('swell_rate', '?')
                    m_vol = params_block.get('max_target_volume', '?')
                    pb_rate = params_block.get('post_burst_shrink_rate', '?')

                    message += f"  • Swell Rate: {self._format_dynamic_param(sw_rate)}\n"
                    message += f"  • Burst Threshold: {self._format_dynamic_param(m_vol)}\n"
                    message += f"  • Post-burst Shrink Rate: {self._format_dynamic_param(pb_rate)}\n"
                    message += f"  • Color Change: {params_block.get('color_change', '?')}\n"

                    fields = params_block.get("fields", [])
                    if fields:
                        message += "  • Release Fields:\n"
                        for f in fields:
                            f_amt = f.get('amount', '?')
                            message += f"    - {f.get('field_name', '?')}: {self._format_dynamic_param(f_amt)}\n"
                    else:
                        message += "  • Release Fields: none\n"
            else:
                message += "  • Error: No Death data found\n"

        elif behaviour == "secrete/uptake":
            if apply_block:
                message += f"  • Target Field: {apply_block.get('field_name', '?')}\n"
                message += f"  • Secretion Mode: {apply_block.get('secret_mode', '?')}\n"

                params_block = apply_block.get("parameters", apply_block)
                sec_amt = params_block.get('amount', '?')
                rel_uptake = params_block.get('relative_uptake', '?')

                message += f"  • Base Amount/Rate: {self._format_dynamic_param(sec_amt)}\n"
                message += f"  • Relative Uptake Rate: {self._format_dynamic_param(rel_uptake)}\n"

                contacts = params_block.get('contact_types', [])
                if contacts:
                    message += f"  • On Contact With: {', '.join(contacts)}\n"

                message += f"  • Scale By Total Count: {'Yes' if params_block.get('total_count') else 'No'}\n"
            else:
                message += "  • Error: No Secretion/Uptake data found\n"

        elif behaviour == "dormancy":
            if apply_block:
                action = apply_block.get('action', 'dormant')
                if action == "dormant":
                    message += f"  • Action: Entering Dormancy (Arrest growth/division)\n"
                elif action == "reactivate":
                    message += f"  • Action: Reactivating/Waking Up (Restore cell cycle)\n"
                else:
                    message += f"  • Action: Unknown mode ({action})\n"
            else:
                message += "  • Error: No Dormancy/Reactivate data found\n"

        elif behaviour == "phagocytosis":
            if apply_block:
                p_mode = apply_block.get("phago_mode", "engulfment").lower()
                if p_mode == "absorption":
                    mode_desc = "absorption (Concurrent Vacuum Cleaning)"
                elif p_mode == "frustrated":
                    mode_desc = "frustrated (Large Cargo Surface Adhesion & Cell Fusion)"
                else:
                    mode_desc = "engulfment (One-by-one Target Wrapping)"

                message += f"  • Phagocytosis Mode: {mode_desc}\n"
                message += f"  • Phagocytic Target: Will attack/eat [{apply_block.get('target_cell_type', '?')}]\n"

                params_block = apply_block.get('parameters', apply_block)
                eating_rate = apply_block.get('eating_rate', params_block.get('eating_rate', 2.0))
                leak_f = apply_block.get('leak_field', params_block.get('leak_field', 'None'))
                leak_amount = apply_block.get('leak_amount', params_block.get('leak_amount', 0.0))

                if p_mode != "frustrated":
                    message += f"  • Eating Speed Rate: {self._format_dynamic_param(eating_rate)} vol_pixels/MCS\n"
                else:
                    message += f"  • Eating Speed Rate: 0.0 (Volumetric growth disabled in Fusion mode)\n"

                if leak_f and leak_f != "None":
                    message += f"  • Metabolic Leakage: Releases {self._format_dynamic_param(leak_amount)} of '{leak_f}' field per MCS while eating\n"
                else:
                    message += f"  • Metabolic Leakage: Clean eating (No environmental field leakage)\n"
            else:
                message += "  • Error: No Phagocytosis data found\n"

        elif behaviour == "chemotaxis":
            if apply_block:
                message += f"  • Target Field: {apply_block.get('field_name', '?')}\n"
                message += f"  • Target Strategy: {apply_block.get('target_strategy', 'break')}\n"
                message += f"  • Formula Variant: {apply_block.get('formula', 'Standard')}\n"

                params_block = apply_block.get('parameters', apply_block)
                lam_val = apply_block.get('lambda', params_block.get('lambda', 20.0))
                message += f"  • Chemotaxis Force Lambda: {self._format_dynamic_param(lam_val)}\n"

                if apply_block.get('coef') is not None:
                    message += f"  • Modification Coef: {self._format_dynamic_param(apply_block.get('coef'))}\n"
            else:
                message += "  • Error: No Chemotaxis data found\n"

        elif behaviour == "force":
            if apply_block:
                message += f"  • Force Mode: {apply_block.get('mode', '?')}\n"
                message += f"  • Force Magnitude: {self._format_dynamic_param(apply_block.get('force', '?'))}\n"
                if apply_block.get('decay') is not None:
                    message += f"  • Decay: {self._format_dynamic_param(apply_block.get('decay'))}\n"
                message += f"  • Persist: {'Yes' if apply_block.get('persist') else 'No'}\n"
                if apply_block.get("field_name"):
                    message += f"  • Field: {apply_block.get('field_name')}\n"
                if apply_block.get("target_type"):
                    message += f"  • Target Type: {apply_block.get('target_type')}\n"
            else:
                message += "  • Error: No Force data found\n"

        elif behaviour == "fpp_link":
            if apply_block:
                message += f"  • Link Mode: {apply_block.get('mode', '?')}\n"
                message += f"  • Partner Type: {apply_block.get('partner_type', apply_block.get('target_type', '?'))}\n"
                if apply_block.get("target_cell_id") is not None:
                    message += f"  • Target Cell ID: {apply_block.get('target_cell_id')}\n"
                message += f"  • Lambda: {self._format_dynamic_param(apply_block.get('link_lambda', '?'))}\n"
                message += f"  • Target Distance: {self._format_dynamic_param(apply_block.get('target_distance', '?'))}\n"
                message += f"  • Max Distance: {self._format_dynamic_param(apply_block.get('max_distance', '?'))}\n"
                if apply_block.get("max_search_distance"):
                    message += f"  • Search Distance: {self._format_dynamic_param(apply_block.get('max_search_distance'))}\n"
                if apply_block.get("max_links"):
                    message += f"  • Max Links: {apply_block.get('max_links')}\n"
            else:
                message += "  • Error: No FPP Link data found\n"

        elif behaviour == "compartmentalize":
            if apply_block:
                message += f"  • Action: {apply_block.get('action', '?')}\n"
                message += f"  • Segment Type: {apply_block.get('segment_type', '?')}\n"
                message += f"  • Tip Type: {apply_block.get('tip_type', '?')}\n"
                message += f"  • Direction Mode: {apply_block.get('direction_mode', '?')}\n"
                message += f"  • Extension Interval: {self._format_dynamic_param(apply_block.get('extension_interval', '?'))}\n"
                message += f"  • Step Length: {self._format_dynamic_param(apply_block.get('step_length', '?'))}\n"
                message += f"  • Search Radius: {self._format_dynamic_param(apply_block.get('search_radius', '?'))}\n"
                if apply_block.get('branch_probability') is not None:
                    message += f"  • Branch Probability: {self._format_dynamic_param(apply_block.get('branch_probability'))}\n"
                message += f"  • FPP Internal Link: {'Yes' if apply_block.get('use_fpp_link') else 'No'}\n"
            else:
                message += "  • Error: No Compartmentalize data found\n"

        elif behaviour == "intracellular_model":
            if apply_block:
                message += f"  • Model: {apply_block.get('model', '?')}\n"
                message += f"  • Action: {apply_block.get('action', 'advance')}\n"
                message += f"  • Sync Inputs: {'Yes' if apply_block.get('sync_inputs', True) else 'No'}\n"
                message += f"  • Step Model: {'Yes' if apply_block.get('step_model', True) else 'No'}\n"
                message += f"  • Sync Outputs: {'Yes' if apply_block.get('sync_outputs', True) else 'No'}\n"
            else:
                message += "  • Error: No Intracellular Model data found\n"

        elif behaviour == "subcellular":
            if apply_block:
                message += f"  • System: {apply_block.get('system', '?')}\n"
                message += f"  • Action: {apply_block.get('action', '?')}\n"
                if apply_block.get("stage") or apply_block.get("to_stage"):
                    message += f"  • Stage: {apply_block.get('stage', apply_block.get('to_stage'))}\n"
                if apply_block.get("component") or apply_block.get("product"):
                    message += f"  • Component/Product: {apply_block.get('component', apply_block.get('product'))}\n"
                if apply_block.get("variable") or apply_block.get("path"):
                    message += f"  • Variable: {apply_block.get('variable', apply_block.get('path'))}\n"
            else:
                message += "  • Error: No Subcellular data found\n"

        if new_types:
            message += f"\nNew Cell Types:\n"
            for ct in new_types:
                if ct not in self.registry.celltype_params:
                    message += f"  • {ct} (will be created)\n"
                else:
                    message += f"  • {ct} (already exists)\n"
        else:
            message += f"\nNo new cell types needed\n"

        message += f"\nGlobal Controls:\n"
        freq_val = rule.get('frequency', 1)
        message += f"  • Execution Frequency: Every {self._format_dynamic_param(freq_val)} MCS\n"
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

    def gui_add_rule(self):
        if not self.registry:
            return

        result = self.collect_params()
        if not result:
            return

        behaviour, params = result
        standard_rule = build_rule(behaviour, params)

        try:
            handle_new_rule_registration(
                self.registry,
                standard_rule,
                lambda m, n, _: ask_params_gui(m, n, self),
                self.sm,
                self.injector
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Registration failed:\n{str(e)}")
            return

        self.registry.commit_artifacts(quiet=True)
        self.refresh_list()
        QMessageBox.information(
            self, "Success",
            f"Rule added and synced successfully!"
        )

    # ============================================================
    # SAVE
    # ============================================================

    def save(self):
        if not self.registry:
            print("No registry loaded")
            return

        self.registry.commit_artifacts(quiet=True)

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
        behaviours = [
            "growth",
            "differentiate",
            "create",
            "death",
            "secrete/uptake",
            "custom_script",
            "dormancy",
            "phagocytosis",
            "chemotaxis",
            "force",
            "compartmentalize",
            "fpp_link",
            "intracellular_model",
            "subcellular",
        ]
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
            specific = build_model_gui(beh)
            if not specific: return None
            params.update(specific)

        elif beh == "differentiate":
            specific = self.collect_diff_params_wizard()
            if not specific: return None
            params.update(specific) # Differentiate  unfold

        elif beh == "create":
            specific = self.collect_create_params_wizard()
            if not specific: return None
            params.update(specific)

        elif beh == "death":
            specific = self.collect_death_params_wizard()
            if not specific:
                return None
            params.update(specific)

        elif beh == "secrete/uptake":
            specific = self.collect_secrete_uptake_params_wizard()
            if not specific:
                return None
            params.update(specific)

        elif beh == "dormancy":
            specific = self.collect_dormancy_params_wizard()
            if not specific:
                return None
            params.update(specific)

        elif beh == "phagocytosis":
            specific = self.collect_phagocytosis_params_wizard()
            if not specific: return None
            params.update(specific)

        elif beh == "chemotaxis":
            specific = self.collect_chemotaxis_params_wizard()
            if not specific: return None
            params.update(specific)

        elif beh == "force":
            specific = self.collect_force_params_wizard()
            if not specific: return None
            params.update(specific)

        elif beh == "compartmentalize":
            specific = self.collect_compartmentalize_params_wizard()
            if not specific: return None
            params.update(specific)

        elif beh == "fpp_link":
            specific = self.collect_fpp_link_params_wizard()
            if not specific: return None
            params.update(specific)

        elif beh == "intracellular_model":
            specific = self.collect_intracellular_model_params_wizard()
            if not specific: return None
            params.update(specific)

        elif beh == "subcellular":
            specific = self.collect_subcellular_params_wizard()
            if not specific: return None
            params.update(specific)

        return beh, params

    def collect_intracellular_model_params_wizard(self):
        models = []
        if self.registry is not None:
            for spec in getattr(self.registry, "intracellular_models", []) or []:
                name = spec.get("model_name") or spec.get("alias") or spec.get("id")
                if name:
                    models.append(str(name))

        if models:
            model_name, ok = QInputDialog.getItem(
                self,
                "Intracellular Model",
                "Choose model registry name:",
                models,
                0,
                False,
            )
        else:
            model_name, ok = QInputDialog.getText(
                self,
                "Intracellular Model",
                "Model registry id or model_name:",
            )
        if not ok or not str(model_name).strip():
            return None

        actions = ["advance", "sync_inputs", "step", "sync_outputs", "reset", "set_variable"]
        action, ok = QInputDialog.getItem(
            self,
            "Intracellular Action",
            "Select action:",
            actions,
            0,
            False,
        )
        if not ok:
            return None

        params = {"model": str(model_name).strip(), "action": action}

        if action == "advance":
            params["sync_inputs"] = QMessageBox.question(
                self,
                "Sync Inputs",
                "Synchronize mapped CC3D values into model variables before stepping?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            ) == QMessageBox.Yes
            params["step_model"] = QMessageBox.question(
                self,
                "Step Model",
                "Advance the intracellular model in this rule?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            ) == QMessageBox.Yes
            params["sync_outputs"] = QMessageBox.question(
                self,
                "Sync Outputs",
                "Synchronize model variables back into cell state after stepping?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            ) == QMessageBox.Yes

        if action == "set_variable":
            variable, ok = QInputDialog.getText(self, "Model Variable", "Variable to set:")
            if not ok or not variable.strip():
                return None
            params["variable"] = variable.strip()
            value, ok = QInputDialog.getText(self, "Variable Value", "Value:", text="0.0")
            if not ok:
                return None
            try:
                params["value"] = float(value)
            except ValueError:
                params["value"] = value

        if action in {"advance", "sync_inputs"}:
            inputs = self._ask_intracellular_mappings_json(
                "Rule-specific input mappings",
                "Add rule-specific input mappings JSON? These are appended to model-level inputs.",
            )
            if inputs is None:
                return None
            if inputs:
                params["inputs"] = inputs

        if action in {"advance", "sync_outputs"}:
            outputs = self._ask_intracellular_mappings_json(
                "Rule-specific output mappings",
                "Add rule-specific output mappings JSON? These are appended to model-level outputs.",
            )
            if outputs is None:
                return None
            if outputs:
                params["outputs"] = outputs

        return params

    def _ask_intracellular_mappings_json(self, title, prompt):
        reply = QMessageBox.question(
            self,
            title,
            prompt,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return []

        text, ok = QInputDialog.getMultiLineText(
            self,
            title,
            "JSON array or object:",
            "[]",
        )
        if not ok:
            return None

        try:
            parsed = json.loads(text.strip() or "[]")
        except Exception as exc:
            QMessageBox.warning(self, title, f"Invalid JSON:\n{exc}")
            return None

        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return parsed

        QMessageBox.warning(self, title, "Mappings JSON must be an object or an array.")
        return None

    def collect_subcellular_params_wizard(self):
        systems = []
        if self.registry is not None:
            for spec in getattr(self.registry, "subcellular_systems", []) or []:
                if not isinstance(spec, dict):
                    continue
                name = spec.get("id") or spec.get("name") or spec.get("system")
                if name:
                    systems.append(str(name))

        if systems:
            system, ok = QInputDialog.getItem(
                self,
                "Subcellular System",
                "Choose registered subcellular system:",
                systems,
                0,
                False,
            )
        else:
            system, ok = QInputDialog.getText(
                self,
                "Subcellular System",
                "System ID:",
            )
        if not ok or not str(system).strip():
            return None

        actions = [
            "initialize",
            "set_stage",
            "advance_stage",
            "set_component",
            "increase_component",
            "consume_component",
            "set_localization",
            "translocate",
            "set_value",
            "assemble",
        ]
        action, ok = QInputDialog.getItem(
            self,
            "Subcellular Action",
            "Select action:",
            actions,
            1,
            False,
        )
        if not ok:
            return None

        params = {"system": self._clean_user_label(system), "action": action}

        if action == "set_stage":
            stage = self._ask_subcellular_stage(params["system"], "Set Stage", "Stage:")
            if stage is None:
                return None
            params["stage"] = stage

        elif action == "advance_stage":
            from_stage, ok = QInputDialog.getText(
                self,
                "Advance Stage",
                "Optional required current stage. Leave blank to allow any current stage:",
            )
            if not ok:
                return None
            if from_stage.strip():
                params["from_stage"] = from_stage.strip()
            to_stage = self._ask_subcellular_stage(params["system"], "Advance Stage", "Target stage. Leave blank to use the next registered stage:", allow_blank=True)
            if to_stage is None:
                return None
            if to_stage:
                params["to_stage"] = to_stage
            params["probability"] = self._ask_parameter_gui("Advance Stage", "Transition probability:", default_val=1.0)

        elif action in {"set_component", "increase_component", "consume_component"}:
            component, ok = QInputDialog.getText(self, "Component", "Component name:")
            if not ok or not component.strip():
                return None
            params["component"] = self._clean_user_label(component)
            label = "Component count:" if action == "set_component" else "Amount:"
            value = self._ask_parameter_gui("Component Value", label, default_val=1.0)
            if action == "set_component":
                params["count"] = value
            else:
                params["amount"] = value
                if action == "consume_component":
                    params["floor_zero"] = QMessageBox.question(
                        self,
                        "Floor at Zero",
                        "Prevent component count from going below zero?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes,
                    ) == QMessageBox.Yes

        elif action == "set_localization":
            location, ok = QInputDialog.getText(self, "Localization", "Location key:")
            if not ok or not location.strip():
                return None
            params["location"] = self._clean_user_label(location)
            params["value"] = self._ask_parameter_gui("Localization", "Value or fraction:", default_val=1.0)

        elif action == "translocate":
            from_location, ok = QInputDialog.getText(self, "Translocate", "Optional source location. Leave blank for external source:")
            if not ok:
                return None
            to_location, ok = QInputDialog.getText(self, "Translocate", "Target location:")
            if not ok or not to_location.strip():
                return None
            if from_location.strip():
                params["from_location"] = self._clean_user_label(from_location)
            params["to_location"] = self._clean_user_label(to_location)
            params["amount"] = self._ask_parameter_gui("Translocate", "Amount or fraction:", default_val=0.1)

        elif action == "set_value":
            variable, ok = QInputDialog.getText(
                self,
                "Set Subcellular Value",
                "Nested variable path:",
            )
            if not ok or not variable.strip():
                return None
            raw_value, ok = QInputDialog.getText(self, "Set Subcellular Value", "Value:")
            if not ok or not raw_value.strip():
                return None
            params["variable"] = self._clean_user_label(variable)
            params["value"] = self._parse_literal_value(raw_value)

        elif action == "assemble":
            product, ok = QInputDialog.getText(self, "Assemble", "Product component or assembled unit:")
            if not ok or not product.strip():
                return None
            params["product"] = self._clean_user_label(product)
            params["amount"] = self._ask_parameter_gui("Assemble", "Product amount:", default_val=1.0)
            requirements = self._ask_key_value_mapping(
                "Assemble Requirements",
                "Required component counts as key=value pairs. Leave blank if none:",
            )
            if requirements is None:
                return None
            if requirements:
                params["requires"] = requirements
            to_stage = self._ask_subcellular_stage(params["system"], "Assemble", "Optional stage after assembly:", allow_blank=True)
            if to_stage is None:
                return None
            if to_stage:
                params["to_stage"] = to_stage

        return params

    def _ask_subcellular_stage(self, system, title, prompt, allow_blank=False):
        stages = []
        if self.registry is not None:
            for spec in getattr(self.registry, "subcellular_systems", []) or []:
                if not isinstance(spec, dict):
                    continue
                aliases = {str(spec.get("id", "")), str(spec.get("name", "")), str(spec.get("system", ""))}
                aliases.discard("")
                if str(system) not in aliases:
                    continue
                stages = [str(item) for item in spec.get("stages", []) if str(item).strip()]
                break

        if stages and not allow_blank:
            stage, ok = QInputDialog.getItem(self, title, prompt, stages, 0, False)
            return self._clean_user_label(stage) if ok else None

        default_text = "" if allow_blank else (stages[0] if stages else "")
        stage, ok = QInputDialog.getText(self, title, prompt, text=default_text)
        if not ok:
            return None
        if not stage.strip() and not allow_blank:
            return None
        return self._clean_user_label(stage)

    def _ask_key_value_mapping(self, title, prompt):
        text, ok = QInputDialog.getText(self, title, prompt)
        if not ok:
            return None
        if not text.strip():
            return {}
        values = {}
        for part in text.split(","):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = self._clean_user_label(key)
            if key:
                values[key] = self._parse_literal_value(value)
        return values

    def _clean_user_label(self, value):
        text = str(value or "").strip()
        while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
            text = text[1:-1].strip()
        return text

    def _parse_literal_value(self, raw_value):
        text = str(raw_value).strip()
        if text.startswith(("{", "[")) and text.endswith(("}", "]")):
            try:
                return json.loads(text)
            except Exception:
                return text
        lowered = text.lower()
        if lowered in {"true", "yes", "y", "on"}:
            return True
        if lowered in {"false", "no", "n", "off"}:
            return False
        try:
            value = float(text)
            return int(value) if value.is_integer() else value
        except ValueError:
            return self._clean_user_label(text)

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
            ratio = self._ask_parameter_gui(
                "Division",
                "Volume ratio assigned to the child cell:",
                default_val=0.5,
            )

            if not (ok1 and ok2):
                return None

            res.update({
                "parent_type": parent_type.strip(),
                "child_type": child_type.strip(),
                "volume_ratio": ratio
            })

            strategies = ["total", "reset"]
            strategy, ok_strat = QInputDialog.getItem(
                self,
                "Memory Inheritance Strategy",
                "Choose how the division count memory is passed down:\n\n"
                " • total: Both parent & child inherit the full aging clock.\n"
                " • reset: Parent cell ages (+1 count), Child resets to 0.",
                strategies,
                0,
                False
            )
            if not ok_strat: return None

            res["inheritance_strategy"] = strategy
            res["state_key"] = "division_count"
            # ============================================================

            placement = self.ask_placement_strategy()
            if placement:
                res["placement"] = placement
            else:
                return None

        return res


    def collect_create_params_wizard(self) -> Any:
        res = {}
        cell_type, ok = QInputDialog.getText(self, "Create Wizard", "Enter Cell Type to create:")
        if not ok or not cell_type.strip(): return None
        res["cell_type"] = cell_type.strip()

        count = self._ask_parameter_gui("Create Wizard", "Configure cell creation count (Count):", default_val=1)
        res["count"] = count

        distributions = ["Random", "Cluster", "Stripe"]
        dist, ok = QInputDialog.getItem(self, "Create Wizard", "Select Distribution:", distributions, 0, False)
        if not ok: return None

        if dist == "Random":
            reg, ok = QInputDialog.getItem(self, "Random Distribution", "Specify bounding region?", ["No", "Yes"], 0, False)
            if ok and reg == "Yes":
                x_start, ok = QInputDialog.getInt(self, "Region", "x_start:", 0, 0, 9999)
                x_end, ok = QInputDialog.getInt(self, "Region", "x_end:", 100, 0, 9999)
                y_start, ok = QInputDialog.getInt(self, "Region", "y_start:", 0, 0, 9999)
                y_end, ok = QInputDialog.getInt(self, "Region", "y_end:", 100, 0, 9999)
                res["distribution"] = {"type": "random", "x_start": x_start, "x_end": x_end, "y_start": y_start, "y_end": y_end}
            else:
                res["distribution"] = {"type": "random"}
        elif dist == "Cluster":
            cx, ok = QInputDialog.getInt(self, "Cluster", "Center X:", 50, 0, 9999)
            cy, ok = QInputDialog.getInt(self, "Cluster", "Center Y:", 50, 0, 9999)
            r, ok = QInputDialog.getInt(self, "Cluster", "Radius:", 10, 0, 9999)
            res["distribution"] = {"type": "cluster", "center": [cx, cy], "radius": r}
        elif dist == "Stripe":
            sd, ok = QInputDialog.getItem(self, "Stripe", "Direction:", ["vertical", "horizontal"], 0, False)
            if sd == "vertical":
                x, ok = QInputDialog.getInt(self, "Stripe", "X position:", 50)
                ys, ok = QInputDialog.getInt(self, "Stripe", "y_start:", 0)
                m, ok = QInputDialog.getItem(self, "Stripe Mode", "Mode:", ["gap", "end"], 0, False)
                res["distribution"] = {"type": "stripe", "direction": "vertical", "x": x, "y_start": ys}
                if m == "gap":
                    g, ok = QInputDialog.getInt(self, "Stripe", "y_gap:", 5)
                    res["distribution"]["y_gap"] = g
                else:
                    e, ok = QInputDialog.getInt(self, "Stripe", "y_end:", 100)
                    res["distribution"]["y_end"] = e
            else:
                y, ok = QInputDialog.getInt(self, "Stripe", "Y position:", 50)
                xs, ok = QInputDialog.getInt(self, "Stripe", "x_start:", 0)
                m, ok = QInputDialog.getItem(self, "Stripe Mode", "Mode:", ["gap", "end"], 0, False)
                res["distribution"] = {"type": "stripe", "direction": "horizontal", "y": y, "x_start": xs}
                if m == "gap":
                    g, ok = QInputDialog.getInt(self, "Stripe", "x_gap:", 5)
                    res["distribution"]["x_gap"] = g
                else:
                    e, ok = QInputDialog.getInt(self, "Stripe", "x_end:", 100)
                    res["distribution"]["x_end"] = e
        return res

    def collect_custom_script_wizard(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Script", str(SANDBOX_DIR), "Python (*.py)")
        if not file_path: return None
        file_path = Path(file_path)

        final_params = process_custom_script(
            file_path = str(file_path),
            registry = self.registry,
            ask_params_func = lambda param_list: ask_params_gui("", param_list, self),
            extract_params_func = extract_params,
            existing_params = None
        )
        print(f"DEBUG: Detected Params -> {final_params}")
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
            # rules_data = import_rules_from_csv(path)

            # for behaviour, params in rules_data:
            #     rule = build_rule(behaviour, params)
            compiled_rules = import_rules_from_csv(path)

            for rule in compiled_rules:

                handle_new_rule_registration(
                    self.registry,
                    rule,
                    lambda m, n, _: ask_params_gui(m, n, self),
                    self.sm,
                    self.injector,
                )

            self.refresh_list()

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def open_manage_rules(self):
        if not self.registry:
            QMessageBox.warning(self, "Warning", "Please Load/Create a Project first!")
            return
        # “Pass in self so that ManageRulesWindow can access all the methods of the main window.”
        from cc3d_builder.gui.ManageRuleWindow import ManageRulesWindow

        self.manage_win = ManageRulesWindow(self.registry,
                                            self.sm,
                                            self.injector,
                                            ask_func=lambda m, n: ask_params_gui(m, n, self),
                                            main_editor=self
                                            )

        if hasattr(self.manage_win, 'field_manager'):
            self.manage_win.field_manager.refresh_table()
            print("✅ Force refreshed field manager from MainWindow")
        self.manage_win.show()

    def open_xml_config_editor(self):
        if not self.registry or not self.sm:
            QMessageBox.warning(self, "Warning", "Please Load/Create a Project first!")
            return

        from cc3d_builder.gui.xml_config_editor import XMLConfigEditor

        self.xml_config_win = XMLConfigEditor(
            registry=self.registry,
            structure_manager=self.sm,
            injector=self.injector,
            parent=self,
        )
        self.xml_config_win.show()

    def open_intracellular_model_manager(self):
        if not self.registry:
            QMessageBox.warning(self, "Warning", "Please Load/Create a Project first!")
            return

        from cc3d_builder.gui.intracellular_model_dialog import IntracellularModelManagerDialog

        self.intracellular_model_win = IntracellularModelManagerDialog(self.registry, parent=self)
        self.intracellular_model_win.exec_()

    def open_subcellular_system_manager(self):
        if not self.registry:
            QMessageBox.warning(self, "Warning", "Please Load/Create a Project first!")
            return

        from cc3d_builder.gui.subcellular_system_dialog import SubcellularSystemManagerDialog

        self.subcellular_system_win = SubcellularSystemManagerDialog(self.registry, parent=self)
        self.subcellular_system_win.exec_()

    def build_condition_gui(self):
        # explicityly import
        from cc3d_builder.gui.build_condition_gui import build_condition_gui as real_builder
        return real_builder(self)

    def collect_death_params_wizard(self):
        """
        Collect death behaviour params aligned with CLI structure.

        Returns
        -------
        dict | None
            Apoptosis:
            {
                "mode": "apoptosis",
                "shrink_rate": 0.95,
                "terminal_volume": 0.0,
                "color_change": "grey"
            }

            Necrosis:
            {
                "mode": "necrosis",
                "swell_rate": 1.05,
                "max_target_volume": 150.0,
                "post_burst_shrink_rate": 0.8,
                "fields": [
                    {"field_name": "TNF", "amount": 50.0},
                    {"field_name": "IL6", "amount": 30.0}
                ]
            }
        """
        params = {}

        behaviours = ["apoptosis", "necrosis"]
        mode, ok = QInputDialog.getItem(
            self,
            "Death Mode",
            "Select death mode:",
            behaviours,
            0,
            False
        )
        if not ok:
            return None

        params["mode"] = mode

        if mode == "apoptosis":
            params["shrink_rate"] = self._ask_parameter_gui(
                "Apoptosis",
                "Configure apoptosis shrink rate:",
                default_val=0.95,
            )

            params["terminal_volume"] = self._ask_parameter_gui(
                "Apoptosis",
                "Configure terminal volume after apoptosis:",
                default_val=0.0
            )

            color_change, ok = QInputDialog.getText(
                self,
                "Apoptosis",
                "Color change to:",
                text="grey"
            )
            if not ok:
                return None
            params["color_change"] = color_change.strip() or "grey"

        elif mode == "necrosis":
            params["swell_rate"] = self._ask_parameter_gui(
                "Necrosis",
                "Configure necrosis swell rate:",
                default_val=1.05,
            )
            params["max_target_volume"] = self._ask_parameter_gui(
                "Necrosis",
                "Configure swell limit / burst threshold:",
                default_val=150.0,
            )
            params["post_burst_shrink_rate"] = self._ask_parameter_gui(
                "Necrosis",
                "Configure post-burst shrink rate:",
                default_val=0.8,
            )

            fields = []
            while True:
                f_name, ok = QInputDialog.getText(
                    self,
                    "Release Field",
                    "Release field name (leave empty to finish):"
                )
                if not ok:
                    return None

                f_name = f_name.strip()
                if not f_name:
                    break

                amount_val = self._ask_parameter_gui(
                    "Release Amount",
                    f"Configure release amount for {f_name}:",
                    default_val=50.0,
                )

                fields.append({
                    "field_name": f_name,
                    "amount": amount_val
                })

            params["fields"] = fields

        return params

    def collect_secrete_uptake_params_wizard(self):
        """
        GUI Wizard: Collect raw parameters for secretion and uptake.
        Return a flat dictionary to be fed directly into build_rule.
        """
        params = {}

        # 1. confirm the field name
        field_name, ok = QInputDialog.getText(
            self, "Field Name", "Enter chemical field name (e.g., VEGF, Oxygen):"
        )
        if not ok or not field_name.strip():
            return None
        params["field_name"] = field_name.strip()

        # 2. choose physical mode
        modes = [
            "secreteInsideCell",
            "secreteInsideCellAtBoundary",
            "secreteOutsideCellAtBoundary",
            "secreteInsideCellAtCOM",
            "uptakeInsideCell",
            "uptakeInsideCellAtBoundary",
            "uptakeOutsideCellAtBoundary",
            "uptakeInsideCellAtCOM",
            "secreteInsideCellAtBoundaryOnContactWith",
            "secreteOutsideCellAtBoundaryOnContactWith",
            "uptakeInsideCellAtBoundaryOnContactWith",
            "uptakeOutsideCellAtBoundaryOnContactWith"
        ]

        mode, ok = QInputDialog.getItem(
            self, "Secretion/Uptake Mode", "Select physical mode:", modes, 0, False
        )
        if not ok:
            return None
        params["secret_mode"] = mode

        # 3. collect numerical parameters according
        if "uptake" in mode:
            params["amount"] = self._ask_parameter_gui(
                "Uptake Parameters",
                "Configure max uptake amount:",
                default_val=1.0,
            )
            params["relative_uptake"] = self._ask_parameter_gui(
                "Uptake Parameters",
                "Configure relative uptake rate:",
                default_val=0.1,
            )

        # if Secrete mode
        else:
            params["amount"] = self._ask_parameter_gui(
                "Secretion Parameters",
                "Configure secretion concentration:",
                default_val=1.0,
            )
            params["relative_uptake"] = 0.0 # secretion doesnt need this

        # 4. contact
        if "OnContactWith" in mode:
            contact_types, ok = QInputDialog.getText(
                self, "Contact Types", "Enter cell types (comma separated, e.g., Tumor,Vessel):"
            )
            if not ok: return None
            params["contact_types"] = contact_types.strip()

        # 5. track total amount?
        track_total = QMessageBox.question(
            self, "Tracking", "Do you want to track the total amount secreted/uptaken?",
            QMessageBox.Yes | QMessageBox.No
        )
        params["total_count"] = (track_total == QMessageBox.Yes)

        return params

    def collect_dormancy_params_wizard(self):

        modes = ["dormant (Sleep)", "reactivate (Restore)"]
        selected_mode, ok = QInputDialog.getItem(
            self, "Dormancy Mode", "Select State Transition Action:", modes, 0, False
        )
        if not ok:
            return None

        action_mode = "reactivate" if "reactivate" in selected_mode else "dormant"

        # Collect parameter Frequency
        freq_str, ok = QInputDialog.getText(
            self, "Execution Control", "Check frequency (MCS interval, e.g., 1 or 5):", text="1"
        )
        if not ok:
            return None

        try:
            params["frequency"] = int(freq_str or 1)
        except ValueError:
            QMessageBox.warning(self, "Error", "Frequency must be an integer.")
            return None

        return {
            "action": action_mode,
            "frequency": int(freq_str or 1),
        }

    def collect_phagocytosis_params_wizard(self) -> Any:
        """
        1. Returns a flat parameter dictionary without legacy nesting.
        2. Upgrades plain float conversion to _ask_parameter_gui, enabling multi-factor physical models (Hill/Linear).
        """
        res = {}

        target_cell, ok = QInputDialog.getText(
            self, "Phagocytosis Target", "Enter the Target Cell Type to eat (e.g., ApoptoticCell):"
        )
        if not ok or not target_cell.strip(): return None
        res["target_cell_type"] = target_cell.strip()

        modes = ["engulfment", "absorption", "frustrated"]
        phago_mode, ok = QInputDialog.getItem(
            self,
            "Phagocytosis Mode",
            "Select Phagocytosis Mode based on cargo size:\n"
            " • engulfment: One-by-one cell wrapping\n"
            " • absorption: Concurrent small cargo intake\n"
            " • frustrated: Large cargo / Cell fusion",
            modes, 0, False
        )
        if not ok: return None
        res["phago_mode"] = phago_mode

        if phago_mode != "frustrated":
            eating_rate = self._ask_parameter_gui(
                "Eating Rate",
                f"Configure phagocytosis pixel rate for '{phago_mode}' mode (Eating Rate):",
                default_val=2.0
            )
            res["eating_rate"] = eating_rate
        else:
            res["eating_rate"] = 0.0

        leak_field, ok = QInputDialog.getText(
            self, "Field Leakage (Optional)", "Enter Field Name leaked during eating (Leave blank if none):"
        )

        if ok and leak_field.strip():
            res["leak_field"] = leak_field.strip()
            leak_amount = self._ask_parameter_gui(
                "Leakage Amount",
                f"Configure per-frame leak amount of '{leak_field.strip()}' during phagocytosis (Leak Amount):",
                default_val=10.0
            )
            res["leak_amount"] = leak_amount
        else:
            res["leak_field"] = "None"
            res["leak_amount"] = 0.0

        return res

    def collect_chemotaxis_params_wizard(self) -> Any:
        res = {}
        strategies = ["1 - break (Random Selection)", "2 - specify cell ID", "3 - specify position coordinates"]
        strat, ok = QInputDialog.getItem(self, "Chemotaxis Strategy", "Select Target Strategy:", strategies, 0, False)
        if not ok: return None

        if strat.startswith("1"):
            res["target_strategy"] = "break"
        elif strat.startswith("2"):
            res["target_strategy"] = "id"
            cid, ok = QInputDialog.getInt(self, "Chemotaxis Target", "Enter Target Cell ID:", 1)
            if ok: res["target_cell_id"] = cid
        elif strat.startswith("3"):
            res["target_strategy"] = "coordinate"
            tx, ok = QInputDialog.getInt(self, "Chemotaxis Target", "Target X:")
            ty, ok = QInputDialog.getInt(self, "Chemotaxis Target", "Target Y:")
            tz, ok = QInputDialog.getInt(self, "Chemotaxis Target", "Target Z (default 0):", 0)
            if ok:
                res["target_x"] = tx
                res["target_y"] = ty
                res["target_z"] = tz

        field_name, ok = QInputDialog.getText(self, "Chemotaxis Field", "Enter Chemical Field Name (e.g. ATTR):")
        if not ok: return None
        res["field_name"] = field_name.strip() if field_name.strip() else "ATTR"

        lam = self._ask_parameter_gui("Chemotaxis Lambda", "Configure chemotaxis driving force magnitude (Lambda, positive for attraction, negative for repulsion):", default_val=20.0)
        res["lambda"] = lam

        formulas = ["Standard (Regular)", "Saturation", "SaturationLinear", "LogScaled"]
        formula, ok = QInputDialog.getItem(self, "Chemotaxis Formula", "Select formula variant:", formulas, 0, False)
        if not ok: return None

        clean_formula = formula.split(" ")[0]
        res["formula"] = clean_formula

        if clean_formula == "Saturation":
            coef = self._ask_parameter_gui("Saturation", "Configure saturation coefficient:", default_val=200.0)
            if coef is not None:
                res["sat_coef"] = coef
                res["coef"] = coef
        elif clean_formula == "SaturationLinear":
            coef = self._ask_parameter_gui("Saturation Linear", "Configure saturation linear coefficient:", default_val=2.0)
            if coef is not None:
                res["sat_linear_coef"] = coef
                res["coef"] = coef
        elif clean_formula == "LogScaled":
            coef = self._ask_parameter_gui("Log Scaled", "Configure log scaled coefficient:", default_val=3.0)
            if coef is not None:
                res["log_scaled_coef"] = coef
                res["coef"] = coef

        if "coef" in res:
            coef_marker = "DYNAMIC" if isinstance(res["coef"], (dict, list)) else res["coef"]
            coef_part = f",coef={coef_marker}"
        else:
            coef_part = ""
        res["mode_param"] = f"field={res['field_name']},lambda=DYNAMIC,formula={res['formula']}{coef_part}"
        return res

    def collect_force_params_wizard(self) -> Any:
        res = {}
        modes = [
            "vector",
            "stored_vector",
            "toward_position",
            "away_from_position",
            "toward_cell_id",
            "toward_nearest_type",
            "away_from_nearest_type",
            "toward_field_gradient",
            "clear",
        ]
        mode, ok = QInputDialog.getItem(self, "Force Mode", "Select ExternalPotential force mode:", modes, 0, False)
        if not ok:
            return None

        res["mode"] = mode

        if mode != "clear":
            res["force"] = self._ask_parameter_gui(
                "ExternalPotential Force",
                "Force magnitude. CC3D sign is handled internally.",
                default_val=10.0
            )
            persist = QMessageBox.question(
                self, "Force Persistence", "Persist this force until clear/overwrite?",
                QMessageBox.Yes | QMessageBox.No
            )
            res["persist"] = persist == QMessageBox.Yes
            if res["persist"]:
                res["decay"] = self._ask_parameter_gui(
                    "Force Decay",
                    "Configure decay multiplier per step:",
                    default_val=1.0,
                )

        if mode == "vector":
            dx, ok = QInputDialog.getDouble(self, "Force Vector", "dx:", 1.0, -1000.0, 1000.0, 3)
            if not ok: return None
            dy, ok = QInputDialog.getDouble(self, "Force Vector", "dy:", 0.0, -1000.0, 1000.0, 3)
            if not ok: return None
            dz, ok = QInputDialog.getDouble(self, "Force Vector", "dz:", 0.0, -1000.0, 1000.0, 3)
            if not ok: return None
            res.update({"dx": dx, "dy": dy, "dz": dz})
        elif mode == "stored_vector":
            prefix, ok = QInputDialog.getText(self, "Stored Vector", "cell.dict vector prefix:", text="orientation")
            if not ok: return None
            res["vector_prefix"] = prefix.strip() or "orientation"
        elif mode in {"toward_position", "away_from_position"}:
            tx, ok = QInputDialog.getDouble(self, "Force Target", "target x:", 0.0)
            if not ok: return None
            ty, ok = QInputDialog.getDouble(self, "Force Target", "target y:", 0.0)
            if not ok: return None
            tz, ok = QInputDialog.getDouble(self, "Force Target", "target z:", 0.0)
            if not ok: return None
            res.update({"target_x": tx, "target_y": ty, "target_z": tz})
        elif mode == "toward_cell_id":
            cid, ok = QInputDialog.getInt(self, "Force Target", "Target cell ID:", 1)
            if not ok: return None
            res["target_cell_id"] = cid
        elif mode in {"toward_nearest_type", "away_from_nearest_type"}:
            target_type, ok = QInputDialog.getText(self, "Force Target", "Target cell type:")
            if not ok or not target_type.strip(): return None
            res["target_type"] = target_type.strip()
        elif mode == "toward_field_gradient":
            field_name, ok = QInputDialog.getText(self, "Force Field", "Field name:")
            if not ok or not field_name.strip(): return None
            step, ok = QInputDialog.getDouble(self, "Force Field", "Gradient finite-difference step:", 1.0, 1.0, 1000.0, 1)
            if not ok: return None
            res["field_name"] = field_name.strip()
            res["gradient_step"] = step

        return res

    def collect_compartmentalize_params_wizard(self) -> Any:
        res = {}
        actions = ["initialize_cluster", "extend_chain", "branch_chain"]
        action, ok = QInputDialog.getItem(self, "Compartmentalize Action", "Select structural action:", actions, 1, False)
        if not ok:
            return None
        res["action"] = action

        segment_type, ok = QInputDialog.getText(self, "Compartmentalize Type", "Segment/body cell type:")
        if not ok or not segment_type.strip():
            return None
        res["segment_type"] = segment_type.strip()

        tip_type, ok = QInputDialog.getText(self, "Compartmentalize Type", "Tip cell type:", text=segment_type.strip())
        if not ok:
            return None
        res["tip_type"] = tip_type.strip() or segment_type.strip()

        modes = ["stored_vector", "vector", "random_persistent", "toward_position", "toward_field_gradient", "inherit_force_vector"]
        direction_mode, ok = QInputDialog.getItem(self, "Compartmentalize Direction", "Select extension direction mode:", modes, 0, False)
        if not ok:
            return None
        res["direction_mode"] = direction_mode

        if direction_mode == "vector":
            dx, ok = QInputDialog.getDouble(self, "Compartmentalize Vector", "dx:", 1.0, -1000.0, 1000.0, 3)
            if not ok: return None
            dy, ok = QInputDialog.getDouble(self, "Compartmentalize Vector", "dy:", 0.0, -1000.0, 1000.0, 3)
            if not ok: return None
            dz, ok = QInputDialog.getDouble(self, "Compartmentalize Vector", "dz:", 0.0, -1000.0, 1000.0, 3)
            if not ok: return None
            res.update({"dx": dx, "dy": dy, "dz": dz})
        elif direction_mode == "toward_position":
            tx, ok = QInputDialog.getDouble(self, "Compartmentalize Target", "target x:", 0.0)
            if not ok: return None
            ty, ok = QInputDialog.getDouble(self, "Compartmentalize Target", "target y:", 0.0)
            if not ok: return None
            tz, ok = QInputDialog.getDouble(self, "Compartmentalize Target", "target z:", 0.0)
            if not ok: return None
            res.update({"target_x": tx, "target_y": ty, "target_z": tz})
        elif direction_mode == "toward_field_gradient":
            field_name, ok = QInputDialog.getText(self, "Compartmentalize Field", "Field name:")
            if not ok or not field_name.strip(): return None
            step, ok = QInputDialog.getDouble(self, "Compartmentalize Field", "Gradient finite-difference step:", 1.0, 1.0, 1000.0, 1)
            if not ok: return None
            res["field_name"] = field_name.strip()
            res["gradient_step"] = step

        interval = self._ask_parameter_gui(
            "Compartmentalize Timing",
            "Configure extension interval in MCS:",
            default_val=1.0,
        )
        step_length = self._ask_parameter_gui(
            "Compartmentalize Geometry",
            "Configure extension step length in pixels:",
            default_val=1.0,
        )
        max_length, ok = QInputDialog.getDouble(self, "Compartmentalize Geometry", "Max chain length, 0 means unlimited:", 0.0, 0.0, 100000.0, 1)
        if not ok: return None
        search_radius = self._ask_parameter_gui(
            "Compartmentalize Geometry",
            "Configure empty-site search radius:",
            default_val=3.0,
        )
        site_modes = ["empty_first", "occupied_first", "front_occupied_first"]
        site_selection_mode, ok = QInputDialog.getItem(
            self,
            "Compartmentalize Site Selection",
            "Choose how the next extension site is selected:",
            site_modes,
            0,
            False,
        )
        if not ok:
            return None
        allow_occupied = QMessageBox.question(
            self,
            "Compartmentalize Invasion",
            "Allow the new tip to replace selected occupied cell pixels?",
            QMessageBox.Yes | QMessageBox.No,
        )
        replace_target_types = ""
        if allow_occupied == QMessageBox.Yes:
            replace_target_types, ok = QInputDialog.getText(
                self,
                "Compartmentalize Invasion",
                "Replace target cell types, comma-separated:",
            )
            if not ok:
                return None
        direction_noise, ok = QInputDialog.getDouble(
            self,
            "Compartmentalize Direction",
            "Direction noise in radians per extension:",
            0.0,
            0.0,
            3.14159,
            3,
        )
        if not ok:
            return None
        internal_contact_energy, ok = QInputDialog.getDouble(
            self,
            "ContactInternal",
            "Internal contact energy between chain compartments:",
            2.0,
            0.0,
            100000.0,
            3,
        )
        if not ok:
            return None
        internal_neighbor_order, ok = QInputDialog.getInt(
            self,
            "ContactInternal",
            "Internal contact NeighborOrder:",
            4,
            1,
            100,
            1,
        )
        if not ok:
            return None
        res.update({
            "extension_interval": interval,
            "step_length": step_length,
            "max_length": max_length,
            "search_radius": search_radius,
            "site_selection_mode": site_selection_mode,
            "direction_noise": direction_noise,
            "allow_occupied_site": allow_occupied == QMessageBox.Yes,
            "replace_target_types": replace_target_types.strip(),
            "internal_contact_energy": internal_contact_energy,
            "internal_neighbor_order": internal_neighbor_order,
        })

        if action == "branch_chain":
            res["branch_probability"] = self._ask_parameter_gui(
                "Branching",
                "Configure branch probability per trigger:",
                default_val=1.0,
            )

        use_fpp = QMessageBox.question(
            self, "Internal FPP Link", "Create INTERNAL FocalPointPlasticity link between adjacent compartments?",
            QMessageBox.Yes | QMessageBox.No
        )
        res["use_fpp_link"] = use_fpp == QMessageBox.Yes
        if res["use_fpp_link"]:
            link_lambda, ok = QInputDialog.getDouble(self, "Internal FPP Link", "Lambda distance:", 10.0, 0.0, 100000.0, 3)
            if not ok: return None
            target_distance, ok = QInputDialog.getDouble(self, "Internal FPP Link", "Target distance:", 0.0, 0.0, 100000.0, 3)
            if not ok: return None
            max_distance, ok = QInputDialog.getDouble(self, "Internal FPP Link", "Max distance:", 0.0, 0.0, 100000.0, 3)
            if not ok: return None
            res.update({
                "link_lambda": link_lambda,
                "target_distance": target_distance,
                "max_distance": max_distance,
            })

        return res

    def collect_fpp_link_params_wizard(self) -> Any:
        res: dict[str, Any] = {}
        modes = ["nearest_type", "cell_id", "all_within_distance", "clear"]
        mode, ok = QInputDialog.getItem(
            self,
            "FPP Link Mode",
            "Select ordinary FocalPointPlasticity link mode:",
            modes,
            0,
            False,
        )
        if not ok:
            return None
        res["mode"] = mode

        if mode == "clear":
            return res

        partner_type, ok = QInputDialog.getText(
            self,
            "FPP Link Partner",
            "Partner cell type for XML pair and lookup:",
        )
        if not ok or not partner_type.strip():
            return None
        res["partner_type"] = partner_type.strip()

        if mode == "cell_id":
            target_cell_id, ok = QInputDialog.getInt(
                self,
                "FPP Link Partner",
                "Target/partner cell id:",
                0,
                0,
                100000000,
                1,
            )
            if not ok:
                return None
            res["target_cell_id"] = target_cell_id

        if mode in {"nearest_type", "all_within_distance"}:
            max_search_distance, ok = QInputDialog.getDouble(
                self,
                "FPP Link Search",
                "Max search distance, 0 means unlimited:",
                0.0,
                0.0,
                100000.0,
                3,
            )
            if not ok:
                return None
            res["max_search_distance"] = max_search_distance

        if mode == "all_within_distance":
            max_links, ok = QInputDialog.getInt(
                self,
                "FPP Link Search",
                "Maximum links to create per trigger:",
                1,
                1,
                100000,
                1,
            )
            if not ok:
                return None
            res["max_links"] = max_links

        link_lambda, ok = QInputDialog.getDouble(
            self,
            "FPP Link Parameters",
            "Lambda distance:",
            10.0,
            0.0,
            100000.0,
            3,
        )
        if not ok:
            return None
        target_distance, ok = QInputDialog.getDouble(
            self,
            "FPP Link Parameters",
            "Target distance:",
            0.0,
            0.0,
            100000.0,
            3,
        )
        if not ok:
            return None
        max_distance, ok = QInputDialog.getDouble(
            self,
            "FPP Link Parameters",
            "Max distance:",
            0.0,
            0.0,
            100000.0,
            3,
        )
        if not ok:
            return None
        res.update({
            "link_lambda": link_lambda,
            "target_distance": target_distance,
            "max_distance": max_distance,
        })

        return res
