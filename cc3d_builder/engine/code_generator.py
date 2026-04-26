import json
from pathlib import Path

class CC3DDecompiledGenerator:
    def __init__(self, registry):
        self.registry = registry
        # Ensure that the latest list of rules is retrieved from the registry.
        self.rules = getattr(registry, 'rules', [])

    def generate(self):
        # 1. Automatically determine the parent class and the base structure.
        has_create = any(r.get('behaviour') == 'create' for r in self.rules)
        base_class = "MitosisSteppableBase" if has_create else "SteppableBasePy"

        code = [
            "from cc3d.core.PySteppables import *",
            "import numpy as np",
            "import math",
            "import random",
            "",
            f"class SimulationSteppable({base_class}):",
            "    def __init__(self, frequency=1):",
            f"        {base_class}.__init__(self, frequency)",
            "",
            "    def step(self, mcs):"
        ]

        if has_create:
            code.append("        cells_to_divide = []")

        # 2. Compile each rule
        for rule in self.rules:
            try:
                code.extend(self._compile_rule_to_native(rule))
            except Exception as e:
                print(f"Warning: {rule.get('id')}，Failed: {e}")

        # 3. Post-processing after splitting (for create)
        if has_create:
            code.extend([
                "\n        # --- Execute Cell Divisions ---",
                "        for cell in cells_to_divide:",
                "            self.divide_cell_random_orientation(cell)",
                "",
                "    def update_attributes(self):",
                "        # Standard CC3D Mitosis handling",
                "        self.parent_cell.targetVolume /= 2.0",
                "        self.clone_parent_2_child()"
            ])

        return "\n".join(code)

    def _compile_rule_to_native(self, rule):
        # Fix error points: handle cases where the target is empty.
        target_raw = rule.get('target')
        target = str(target_raw).upper() if target_raw else "ALL"
        
        behaviour = rule.get('behaviour')
        indent = "        "
        
        lines = [f"\n{indent}# --- Compiled Rule {rule.get('id', 'N/A')} ({behaviour}) ---"]
        
        # Generate native CC3D loops.
        if target == "ALL" or target == "NONE":
            lines.append(f"{indent}for cell in self.cell_list:")
        else:
            # Automatically map type constants such as self.CELLA.
            lines.append(f"{indent}for cell in self.cell_list_by_type(self.{target}):")
        
        curr_indent = indent + "    "
        for case in rule.get('cases', []):
            # A. deconstruct evaluate_condition
            cond_expr = self._decompile_condition(case.get('when', {}))
            lines.append(f"{curr_indent}if {cond_expr}:")
            
            # B. deconstruct Plugin and Registry)
            exec_indent = curr_indent + "    "
            apply = case.get('apply', {})
            
            if behaviour == "growth":
                math_logic = self._decompile_growth(apply)
                lines.append(f"{exec_indent}# Pure math implementation")
                lines.append(f"{exec_indent}cell.targetVolume += {math_logic}")
            
            elif behaviour == "differentiate":
                to_type = str(apply.get('to_type', 'Medium')).upper()
                lines.append(f"{exec_indent}cell.type = self.{to_type}")
            
            elif behaviour == "create":
                lines.append(f"{exec_indent}cells_to_divide.append(cell)")
                
        return lines

    def _decompile_condition(self, when):
        """Expand JSON conditions into native expressions."""
        c_type = when.get('condition_type', "TRUE")
        p = when.get('params', {})
        
        if c_type == "Environment":
            field = p.get('field_name', 'Oxygen')
            op = p.get('operator', '>')
            thr = p.get('threshold', 0)
            return f"self.field.{field}[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)] {op} {thr}"
        
        if c_type.startswith("Morphology"):
            attr = c_type.split('_')[1].lower() if '_' in c_type else 'volume'
            op = p.get('operator', '>')
            thr = p.get('threshold', 0)
            return f"cell.{attr} {op} {thr}"

        return "True"

    def _decompile_growth(self, apply):
        """Expand the model logic into native mathematical expressions."""
        model = apply.get('model', 'linear')
        p = apply.get('parameters', {})
        reg = apply.get('regulator')
        
        # 场采样表达式
        if reg:
            reg_val = f"self.field.{reg}[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]"
        else:
            reg_val = "1.0"

        if model == "linear":
            alpha = p.get('alpha', 0.1)
            return f"{alpha} * {reg_val}"
        
        if model == "hill":
            y_max, K, n = p.get('y_max', 1.0), p.get('K', 0.5), p.get('n', 2.0)
            return f"{y_max} * (({reg_val}**{n}) / ({K}**{n} + {reg_val}**{n}))"
        
        return "0.1"

    def save_to_file(self, folder_path):
        p = Path(folder_path) / "CompiledStepCode.py"
        p.write_text(self.generate(), encoding='utf-8')