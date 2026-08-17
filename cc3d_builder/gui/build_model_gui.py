# build_model_gui.py
from PyQt5.QtWidgets import QInputDialog, QLineEdit, QVBoxLayout, QDialog, QDialogButtonBox, QLabel, QFormLayout, QMessageBox


def _parse_regulators(raw_text):
    regulators = [
        item.strip()
        for item in str(raw_text or "").split(",")
        if item.strip() and item.strip().lower() not in {"none", "null", "nan"}
    ]
    return regulators if regulators else None


def _warn_missing_regulator(parent):
    QMessageBox.warning(
        parent,
        "Missing Regulator Field",
        "Field-regulated physical models require at least one CC3D diffusion field, e.g. Oxygen.",
    )

def build_model_gui(behaviour, parent=None):
    models = ["hill", "linear", "expression"]
    model_type, ok = QInputDialog.getItem(
        parent,
        "Select Field-Regulated Model",
        "Choose model type.\nRegulators here are CC3D diffusion fields only.\nUse State / Native Expression for {volume}, {division_count}, or custom state keys.",
        models,
        0,
        False,
    )
    
    if not ok: return None

    if model_type == "hill":
        dialog = QDialog(parent)
        dialog.setWindowTitle("Hill Model Parameters")
        layout = QFormLayout(dialog)
        
        reg_input = QLineEdit("Oxygen")
        ymax_input = QLineEdit("1.0")
        ymin_input = QLineEdit("0.0")
        k_input = QLineEdit("0.5")
        n_input = QLineEdit("2.0")
        
        layout.addRow("Regulator diffusion field(s):", reg_input)
        layout.addRow("y_max:", ymax_input)
        layout.addRow("y_min:", ymin_input)
        layout.addRow("K:", k_input)
        layout.addRow("n:", n_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            regs = _parse_regulators(reg_input.text())
            if not regs:
                _warn_missing_regulator(parent)
                return None
            return {
                "model": "hill",
                "regulator": regs if len(regs) > 1 else regs[0],
                "parameters": {
                    "y_max": float(ymax_input.text()),
                    "y_min": float(ymin_input.text()),
                    "K": float(k_input.text()),
                    "n": float(n_input.text())
                }
            }

    elif model_type == "linear":
        reg, ok1 = QInputDialog.getText(parent, "Linear Model", "Regulator diffusion field(s), comma-separated:")
        alpha, ok2 = QInputDialog.getDouble(parent, "Linear Model", "Alpha:", 0.1, -100, 100, 4)
        if ok1 and ok2:
            regs = _parse_regulators(reg)
            if not regs:
                _warn_missing_regulator(parent)
                return None
            return {"model": "linear", "regulator": regs if len(regs) > 1 else regs[0], "parameters": {"alpha": alpha}}

    elif model_type == "expression":
        reg, ok1 = QInputDialog.getText(parent, "Expression Model", "Regulator diffusion field(s), comma-separated:")
        expr, ok2 = QInputDialog.getText(parent, "Expression Model", "Expression using field names (e.g. 0.02 * Oxygen):")
        if ok1 and ok2:
            regs = _parse_regulators(reg)
            if not regs:
                _warn_missing_regulator(parent)
                return None
            return {
                "model": "expression", 
                "regulator": regs if len(regs) > 1 else regs[0],
                "parameters": {   
                    "expression": expr
                }
            }
    return None
