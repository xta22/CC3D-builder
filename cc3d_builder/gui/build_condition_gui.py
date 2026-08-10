# build_condition_gui.py
from PyQt5.QtWidgets import QInputDialog, QMessageBox
from cc3d_builder.core.dynamic_numeric import parse_dynamic_numeric


ENVIRONMENT_SAMPLING_CHOICES = [
    ("COM concentration (current default)", "com"),
    ("Cell average", "cell_average"),
    ("Cell maximum", "cell_max"),
    ("Cell minimum", "cell_min"),
    ("Boundary average", "boundary_average"),
    ("Boundary maximum", "boundary_max"),
    ("Boundary minimum", "boundary_min"),
    ("Contact boundary average", "contact_boundary_average"),
    ("Contact boundary maximum", "contact_boundary_max"),
    ("Contact boundary minimum", "contact_boundary_min"),
    ("Radius average around COM", "radius_average"),
    ("Radius maximum around COM", "radius_max"),
    ("Radius minimum around COM", "radius_min"),
]


def _ask_dynamic_number(parent, title, label, default=0.0):
    raw, ok = QInputDialog.getText(
        parent,
        title,
        f"{label}\nSupports constants, {{state_key}} expressions, or JSON physical-model dictionaries:",
        text=str(default),
    )
    if not ok:
        return None, False
    return parse_dynamic_numeric(raw, default), True


def _ask_environment_sampling(parent, params):
    labels = [label for label, _mode in ENVIRONMENT_SAMPLING_CHOICES]
    selected, ok = QInputDialog.getItem(
        parent,
        "Environment Sampling",
        "How should field concentration be sampled for this cell?",
        labels,
        0,
        False,
    )
    if not ok:
        return False

    mode = dict(ENVIRONMENT_SAMPLING_CHOICES)[selected]
    params["sampling_mode"] = mode

    if mode.startswith("contact_boundary_"):
        target_type, ok = QInputDialog.getText(
            parent,
            "Contact Target Type",
            "Cell type that defines the contact boundary (e.g. FungusYeast):",
        )
        if not ok or not target_type.strip():
            return False
        params["target_type"] = target_type.strip()

    if mode.startswith("radius_"):
        radius, ok = _ask_dynamic_number(parent, "Sampling Radius", "Radius around cell COM:", 3)
        if not ok:
            return False
        params["radius"] = radius

    return True


def _clean_user_label(value):
    text = str(value or "").strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text

def build_condition_gui(self):
    """
    collect input from user and return a dict
    """
    cond_choices = [
        "Environment (Field Threshold)", 
        "Topology (Cell Contact)", 
        "Morphology (Shape/Size)", 
        "State-Lasting (Memory)",
        "Intracellular State",
        "Subcellular State",
        "Time Window (MCS based)", 
        "Probability (Random)", 
        "Logical (AND/OR/NOT)",
        "Custom Script",
        "Always True"
    ]

    cond_type, ok = QInputDialog.getItem(
        self, "Condition", "Select condition type:", cond_choices, 0, False
    )
    if not ok:
        return None

    # =========================
    # 0. Always True
    # =========================
    if cond_type == "Always True":
        return {"condition_type": "TRUE", "params": {}}

    # =========================
    # 1. Custom Script 
    # =========================
    elif cond_type == "Custom Script":
        script_name, ok = QInputDialog.getText(
            self, "Custom Script", 
            "Enter script path (e.g. custom/my_logic.py):"
        )
        if not ok or not script_name.strip(): 
            return None

        raw_params, ok = QInputDialog.getText(
            self, "Custom Parameters", 
            "Enter params (e.g. target_type=ImmuneCell, max_count=5)\nLeave blank if none:"
        )
        if not ok: 
            return None

        custom_params = {}
        if raw_params.strip():
            for pair in raw_params.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    try:
                        if "." in v:
                            v = float(v)
                        else:
                            v = int(v)
                    except ValueError:
                        pass
                    
                    custom_params[k] = v

        return {
            "condition_type": "Custom",
            "script_path": script_name.strip(),
            "params": custom_params
        }

    # =========================
    # 2. State-Lasting
    # =========================
    elif cond_type == "State-Lasting (Memory)":
        duration, ok = _ask_dynamic_number(self, "Duration", "How many MCS must this state last?", 50)
        if not ok: 
            return None

        QMessageBox.information(
            self, "Next Step", "Now, please define the base condition that needs to be maintained."
        )

        sub_condition = self.build_condition_gui()
        if not sub_condition: 
            return None

        return {
            "condition_type": "Duration",
            "params": {
                "threshold_mcs": duration,
                "sub_condition": sub_condition
            }
        }

    elif cond_type == "Intracellular State":
        params = {}
        models = []
        registry = getattr(self, "registry", None)
        if registry is not None:
            for spec in getattr(registry, "intracellular_models", []) or []:
                if not isinstance(spec, dict):
                    continue
                name = spec.get("model_name") or spec.get("id") or spec.get("alias")
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
        if not ok or not model_name.strip():
            return None
        params["model"] = model_name.strip()

        variable, ok = QInputDialog.getText(
            self,
            "Model Variable",
            "Model variable / species / MaBoSS node name, e.g. NICD:",
        )
        if not ok or not variable.strip():
            return None
        params["variable"] = variable.strip()

        operator, ok = QInputDialog.getItem(
            self, "Operator", "Operator:", [">", "<", ">=", "<=", "==", "!="], 0, False
        )
        if not ok:
            return None
        params["operator"] = operator

        threshold, ok = _ask_dynamic_number(self, "Threshold Value", "Value:", 0.0)
        if not ok:
            return None
        params["threshold"] = threshold

        return {"condition_type": "IntracellularState", "params": params}

    elif cond_type == "Subcellular State":
        params = {}
        systems = []
        registry = getattr(self, "registry", None)
        if registry is not None:
            for spec in getattr(registry, "subcellular_systems", []) or []:
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
        params["system"] = _clean_user_label(system)

        value_mode, ok = QInputDialog.getItem(
            self,
            "Subcellular Value",
            "Which subcellular value should be compared?",
            ["stage", "component count", "localization value", "nested path"],
            0,
            False,
        )
        if not ok:
            return None

        if value_mode == "stage":
            params["variable"] = "stage"
            default_threshold = ""
        elif value_mode == "component count":
            component, ok = QInputDialog.getText(self, "Component", "Component name:")
            if not ok or not component.strip():
                return None
            params["component"] = _clean_user_label(component)
            default_threshold = ""
        elif value_mode == "localization value":
            location, ok = QInputDialog.getText(self, "Localization", "Location key:")
            if not ok or not location.strip():
                return None
            params["location"] = _clean_user_label(location)
            default_threshold = ""
        else:
            variable, ok = QInputDialog.getText(self, "Nested Path", "Path under the system:")
            if not ok or not variable.strip():
                return None
            params["variable"] = _clean_user_label(variable)
            default_threshold = ""

        operator, ok = QInputDialog.getItem(
            self, "Operator", "Operator:", [">", "<", ">=", "<=", "==", "!="], 4 if value_mode == "stage" else 0, False
        )
        if not ok:
            return None
        params["operator"] = operator

        threshold, ok = QInputDialog.getText(self, "Threshold Value", "Value:", text=default_threshold)
        if not ok or not threshold.strip():
            return None
        params["threshold"] = parse_dynamic_numeric(threshold, threshold)
        if isinstance(params["threshold"], str):
            params["threshold"] = _clean_user_label(params["threshold"])

        return {"condition_type": "SubcellularState", "params": params}

    # =========================
    # 3. Environment / Topology / Morphology 
    # =========================
    elif cond_type.startswith(("Environment", "Topology", "Morphology")):
        params = {}

        operator, ok = QInputDialog.getItem(
            self, "Operator", "Operator:", [">", "<", ">=", "<=", "=="], 0, False
        )
        if not ok: return None
        params["operator"] = operator

        value, ok = _ask_dynamic_number(self, "Threshold Value", "Value:", 0.0)
        if not ok: return None
        params["threshold"] = value

        if cond_type.startswith("Environment"):
            field_name, ok = QInputDialog.getText(self, "Field Name", "Chemical field (e.g. Oxygen):")
            if not ok: return None
            params["field_name"] = field_name.strip()
            if not _ask_environment_sampling(self, params):
                return None
            return {"condition_type": "Environment", "params": params}

        elif cond_type.startswith("Topology"):
            target_type, ok = QInputDialog.getText(self, "Target Type", "Cell type (e.g. ImmuneCell):")
            if not ok: return None
            params["target_type"] = target_type.strip()
            return {"condition_type": "Contact", "params": params}

        elif cond_type.startswith("Morphology"):
            morph_type, ok = QInputDialog.getItem(
                self, "Indicator", "Morphology indicator:", ["Elongation", "Specific_Surface"], 0, False
            )
            if not ok: return None
            return {"condition_type": f"Morphology_{morph_type}", "params": params}

    # =========================
    # 4. Time Window
    # =========================
    elif cond_type.startswith("Time Window"):
        start, ok = _ask_dynamic_number(self, "Start", "Start MCS:", 0)
        if not ok: return None
        end, ok = _ask_dynamic_number(self, "End", "End MCS:", 1000)
        if not ok: return None
        return {"condition_type": "TimeWindow", "params": {"start": start, "end": end}}

    # =========================
    # 5. Probability 
    # =========================
    elif cond_type.startswith("Probability"):
        p, ok = _ask_dynamic_number(self, "Probability", "p:", 0.5)
        if not ok: return None
        return {"condition_type": "Probability", "params": {"p": p}}

    # =========================
    # 6. Logical Block 
    # =========================
    elif cond_type.startswith("Logical"):
        logic, ok = QInputDialog.getItem(self, "Logic", "Logic:", ["AND", "OR", "NOT"], 0, False)
        if not ok: return None

        n = 1 if logic == "NOT" else 2
        if logic != "NOT":
            n, ok = QInputDialog.getInt(self, "Count", "How many sub-conditions?", 2, 2, 10)
            if not ok: return None

        conditions = []
        for i in range(n):
            QMessageBox.information(self, "Logical Build", f"Please build sub-condition {i+1} for {logic}")
            cond = self.build_condition_gui()
            if cond is None: return None
            conditions.append(cond)

        return {"condition_type": f"Logic_{logic}", "params": {"conditions": conditions}}
