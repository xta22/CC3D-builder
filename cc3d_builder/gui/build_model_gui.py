from PyQt5.QtWidgets import QInputDialog, QLineEdit, QVBoxLayout, QDialog, QDialogButtonBox, QLabel, QFormLayout

def build_model_gui(behaviour, parent=None):
    models = ["hill", "linear", "expression"]
    model_type, ok = QInputDialog.getItem(parent, "Select Model", "Choose model type:", models, 0, False)
    
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
        
        layout.addRow("Regulator(s):", reg_input)
        layout.addRow("y_max:", ymax_input)
        layout.addRow("y_min:", ymin_input)
        layout.addRow("K:", k_input)
        layout.addRow("n:", n_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            regs = [r.strip() for r in reg_input.text().split(",")]
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
        reg, ok1 = QInputDialog.getText(parent, "Linear Model", "Regulator field:")
        alpha, ok2 = QInputDialog.getDouble(parent, "Linear Model", "Alpha:", 0.1, -100, 100, 4)
        if ok1 and ok2:
            return {"model": "linear", "regulator": reg, "parameters": {"alpha": alpha}}

    elif model_type == "expression":
        reg, ok1 = QInputDialog.getText(parent, "Expression Model", "Regulator field:")
        expr, ok2 = QInputDialog.getText(parent, "Expression Model", "Expression (e.g. 0.02 * Oxygen):")
        if ok1 and ok2:
            return {
                "model": "expression", 
                "regulator": reg, 
                "parameters": {   
                    "expression": expr
                }
            }
    return None