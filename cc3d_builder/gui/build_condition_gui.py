from PyQt5.QtWidgets import QInputDialog, QMessageBox

def build_condition_gui(self):
    """
    collect input from user and return a dict
    """
    cond_choices = [
        "Environment (Field Threshold)", 
        "Topology (Cell Contact)", 
        "Morphology (Shape/Size)", 
        "State-Lasting (Memory)",
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
        duration, ok = QInputDialog.getInt(
            self, "Duration", "How many MCS must this state last?", 50, 1, 100000
        )
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

        value, ok = QInputDialog.getDouble(self, "Threshold Value", "Value:", 0.0, -9999.0, 9999.0, 3)
        if not ok: return None
        params["threshold"] = value

        if cond_type.startswith("Environment"):
            field_name, ok = QInputDialog.getText(self, "Field Name", "Chemical field (e.g. Oxygen):")
            if not ok: return None
            params["field_name"] = field_name.strip()
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
        start, ok = QInputDialog.getInt(self, "Start", "Start MCS:")
        if not ok: return None
        end, ok = QInputDialog.getInt(self, "End", "End MCS:")
        if not ok: return None
        return {"condition_type": "TimeWindow", "params": {"start": start, "end": end}}

    # =========================
    # 5. Probability 
    # =========================
    elif cond_type.startswith("Probability"):
        p, ok = QInputDialog.getDouble(self, "Probability", "p:", 0.5, 0, 1)
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