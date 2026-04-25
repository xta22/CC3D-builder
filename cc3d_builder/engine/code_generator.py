import json
from pathlib import Path

class CC3DDecompiledGenerator:
    def __init__(self, registry):
        self.registry = registry
        self.rules = registry.rules

    def generate(self):
        # Automatically determine the parent class.
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

        # Compile each rule into native code.
        for rule in self.rules:
            code.extend(self._compile_rule(rule))

        # Handle splitting logic
        if has_create:
            code.extend([
                "        for cell in cells_to_divide:",
                "            self.divide_cell_random_orientation(cell)",
                "",
                "    def update_attributes(self):",
                "        self.parent_cell.targetVolume /= 2.0",
                "        self.clone_parent_2_child()"
            ])

        return "\n".join(code)

    def _compile_rule(self, rule):
        target = rule.get('target', 'All').upper()
        behaviour = rule.get('behaviour')
        indent = "        "
        
        lines = [f"\n{indent}# --- Rule {rule.get('id')}: {behaviour} ---"]
        
        if target == 'ALL':
            lines.append(f"{indent}for cell in self.cell_list:")
        else:
            lines.append(f"{indent}for cell in self.cell_list_by_type(self.{target}):")
        
        curr_indent = indent + "    "
        for case in rule.get('cases', []):
            # Translate the Condition directly into an if statement.
            cond_expr = self._decompile_condition(case.get('when', {}))
            lines.append(f"{curr_indent}if {cond_expr}:")
            
            # Translate the Action directly into underlying API calls.
            exec_indent = curr_indent + "    "
            apply = case.get('apply', {})
            
            if behaviour == "growth":
                # Hardcode the model logic directly into the code, without referencing MODEL_REGISTRY
                math_logic = self._decompile_growth(apply)
                lines.append(f"{exec_indent}# Applied {apply.get('model')} growth model")
                lines.append(f"{exec_indent}cell.targetVolume += {math_logic}")
            
            elif behaviour == "differentiate":
                to_type = apply.get('to_type', 'Medium').upper()
                lines.append(f"{exec_indent}cell.type = self.{to_type}")
            
            elif behaviour == "create":
                lines.append(f"{exec_indent}cells_to_divide.append(cell)")
                
        return lines

    def _decompile_condition(self, when):
        """Expand the logic of condition_evaluator into native Python."""
        c_type = when.get('condition_type')
        p = when.get('params', {})
        
        if c_type == "Environment":
            field = p.get('field_name')
            op = p.get('operator', '>')
            thr = p.get('threshold', 0)
            # visit field through self.field
            return f"self.field.{field}[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)] {op} {thr}"
        
        if c_type.startswith("Morphology"):
            attr = c_type.split('_')[1].lower() if '_' in c_type else 'volume'
            op = p.get('operator', '>')
            thr = p.get('threshold', 0)
            return f"cell.{attr} {op} {thr}"

        if c_type == "Logic_AND":
            subs = [self._decompile_condition(c) for c in p.get('conditions', [])]
            return f"({' and '.join(subs)})"

        return "True"

    def _decompile_growth(self, apply):
        """Expand the logic of model_registry into mathematical expressions."""
        model = apply.get('model')
        p = apply.get('parameters', {})
        reg = apply.get('regulator')
        
        # 场采样表达式
        reg_val = f"self.field.{reg}[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]" if reg else "1.0"

        if model == "linear":
            return f"{p.get('alpha', 1.0)} * {reg_val}"
        
        if model == "hill":
            # 展开 Hill 公式：y_max * (S^n / (K^n + S^n))
            y_max = p.get('y_max', 1.0)
            K = p.get('K', 0.5)
            n = p.get('n', 2.0)
            return f"{y_max} * (({reg_val}**{n}) / ({K}**{n} + {reg_val}**{n}))"
        
        return "0.1"

    def save_to_file(self, folder_path):
        p = Path(folder_path) / "DecompiledSteppables.py"
        p.write_text(self.generate(), encoding='utf-8')