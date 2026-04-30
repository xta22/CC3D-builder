# code_generator.py
from pathlib import Path
import pandas as pd
class CC3DDecompiledGenerator:

    def __init__(self, registry):
        self.registry = registry
        self.rules = getattr(registry, 'rules', [])

    def generate(self):
        # If "Differentiate" is present, the base class must be MitosisSteppableBase
        # But for pure "Create", SteppableBasePy is sufficient
        
        rules_with_mitosis = [
            r for r in self.rules 
            if r.get('behaviour') == 'differentiate' and 
            (r.get('cases', [{}])[0].get('apply', {}).get('do_division') or 
             r.get('cases', [{}])[0].get('apply', {}).get('parent_type'))
        ]

        has_mitosis = any(r.get('behaviour') == 'differentiate' for r in self.rules)
        base_class = "MitosisSteppableBase" if has_mitosis else "SteppableBasePy"

        code = [
            "from cc3d.core.PySteppables import *",
            "import numpy as np",
            "",
            f"class SimulationSteppable({base_class}):",
            "    def __init__(self, frequency=1, engine=None):",
            f"        {base_class}.__init__(self, frequency)",
            "        self.engine = engine",
            "",
            "    def step(self, mcs):",
            "        if not self.engine: return"
        ]

        # -----------------------------------------------------------
        # Global triggering logic (for Create)
        # -----------------------------------------------------------
        create_rules = [r for r in self.rules if r.get('behaviour') == 'create']
        if create_rules:
            code.append("\n        # --- [ZONE: CREATE] --- ")
            for rule in create_rules:
                code.extend(self._compile_create_logic(rule))

        # -----------------------------------------------------------
        # Other Cell Actions (create/differentiate | 4.29.2026)
        # -----------------------------------------------------------
        cell_rules = [r for r in self.rules if r.get('behaviour') in ['growth', 'differentiate', 'death']]
        if cell_rules:
            code.append("\n        # --- [ZONE: CELL-BASED] ---")
            targets = set(r.get('target', 'ALL') for r in cell_rules)
            for t in targets:
                t_str = str(t).upper()
                iterator = "self.cell_list" if t_str in ["ALL", "NONE"] else f"self.cell_list_by_type(self.{t_str})"
                
                code.append(f"        for cell in {iterator}:")
                for rule in cell_rules:
                    if str(rule.get('target', 'ALL')).upper() == t_str:
                        code.extend(self._compile_cell_action_body(rule))
        if has_mitosis:
            code.extend(self._generate_update_attributes_logic(rules_with_mitosis))

        return "\n".join(code)

    def _generate_update_attributes_logic(self, mitosis_rules):
        """
        Generate the native update_attributes callback function.
        It is responsible for handling post-division parent/child cell type transitions and volume allocation.
        """
        lines = [
            "",
            "    def update_attributes(self):",
            "        parent = self.parent_cell",
            "        child = self.child_cell",
            "        ",
            "        # Basic attribute cloning",
            "        self.clone_parent_2_child()",
            "        ",
            "        # Handle type transitions based on pre-division markers",
            "        # Users need to mark parent.dict before division in the step function"
        ]
        
    # Since division is asynchronous, before calling divide in step,
    # we store the “division intent” in parent.dict,
    # and then read it here.
        
        lines.extend([
            "        intent = parent.dict.get('mitosis_intent')",
            "        if intent:",
            "            p_type = intent.get('parent_type')",
            "            c_type = intent.get('child_type')",
            "            ratio = intent.get('volume_ratio', 0.5)",
            "            ",
            "            if p_type: parent.type = getattr(self, p_type.upper())",
            "            if c_type: child.type = getattr(self, c_type.upper())",
            "            ",
            "            # Volume redistribution",
            "            total_v = parent.targetVolume",
            "            parent.targetVolume = total_v * ratio",
            "            child.targetVolume = total_v * (1.0 - ratio)",
            "            ",
            "            # Clean the mark",
            "            parent.dict['mitosis_intent'] = None"
        ])
        return lines

    def _compile_create_logic(self, rule):
        lines = []
        rid = rule.get('id', 'N/A')
        
        for idx, case in enumerate(rule.get('cases', [])):
            cond = self._parse_condition(case.get('when', {}), rid, idx)
            apply = case.get('apply', {})
            dist = apply.get("distribution", {})
            dist_type = dist.get("type", "random")
            count = apply.get("count", 1)
            cell_type = apply.get("cell_type", "CellA").upper()

            lines.append(f"\n        # --- [Native Create] Rule {rid} ---")
            lines.append(f"        if {cond['expr']}:")
            
            if dist_type == "random":
                x_s = dist.get("x_start", 0)
                x_e = dist.get("x_end", "self.dim.x")
                y_s = dist.get("y_start", 0)
                y_e = dist.get("y_end", "self.dim.y")
                
                lines.append(f"            created = 0")
                lines.append(f"            attempts = 0")
                lines.append(f"            while created < {count} and attempts < {count * 20}:")
                lines.append(f"                x = random.randint({x_s}, {x_e} - 1)")
                lines.append(f"                y = random.randint({y_s}, {y_e} - 1)")
                lines.append(f"                if not self.cell_field[x, y, 0]:")
                lines.append(f"                    self.cell_field[x, y, 0] = self.new_cell(self.{cell_type})")
                lines.append(f"                    created += 1")
                lines.append(f"                attempts += 1")

            elif dist_type == "cluster":
                cx, cy = dist.get("center", [32, 32])
                r = dist.get("radius", 10)
                lines.append(f"            created = 0")
                lines.append(f"            attempts = 0")
                lines.append(f"            while created < {count} and attempts < {count * 20}:")
                lines.append(f"                angle = random.uniform(0, 2 * np.pi)")
                lines.append(f"                d = random.uniform(0, {r})")
                lines.append(f"                x, y = int({cx} + d * np.cos(angle)), int({cy} + d * np.sin(angle))")
                lines.append(f"                if 0 <= x < self.dim.x and 0 <= y < self.dim.y:")
                lines.append(f"                    if not self.cell_field[x, y, 0]:")
                lines.append(f"                        self.cell_field[x, y, 0] = self.new_cell(self.{cell_type})")
                lines.append(f"                        created += 1")
                lines.append(f"                attempts += 1")
       
            elif dist_type == "stripe":
                lines.extend(self._generate_native_stripe(dist, count, cell_type))

        return lines

    def _generate_native_stripe(self, dist, count, cell_type):
        """Generate Stripe layout"""
        res = []
        direction = dist.get("direction", "vertical")
        if direction == "vertical":
            x_pos = dist.get("x", 0)
            y_s = dist.get("y_start", 0)
            if "y_gap" in dist:
                res.append(f"            coords = [({x_pos}, {y_s} + i * {dist['y_gap']}) for i in range({count})]")
            else:
                y_e = dist.get("y_end", 100)
                res.append(f"            step = ({y_e} - {y_s}) / ({count} - 1) if {count} > 1 else 0")
                res.append(f"            coords = [({x_pos}, int({y_s} + i * step)) for i in range({count})]")
        else: # horizontal
            y_pos = dist.get("y", 0)
            x_s = dist.get("x_start", 0)
            if "x_gap" in dist:
                res.append(f"            coords = [( {x_s} + i * {dist['x_gap']}, {y_pos}) for i in range({count})]")
            else:
                x_e = dist.get("x_end", 100)
                res.append(f"            step = ({x_e} - {x_s}) / ({count} - 1) if {count} > 1 else 0")
                res.append(f"            coords = [(int({x_s} + i * step), {y_pos}) for i in range({count})]")
        
        res.append(f"            for nx, ny in coords:")
        res.append(f"                if 0 <= nx < self.dim.x and 0 <= ny < self.dim.y:")
        res.append(f"                    new_cell = self.new_cell(self.{cell_type.upper()})")
        res.append(f"                    self.cell_field[nx, ny, 0] = new_cell")
        return res

    def _compile_cell_action_body(self, rule):
        """
        Directly generate native CC3D behavior
        """
        lines = []
        rid = rule.get('id')
        beh = rule.get('behaviour')
        
        for idx, case in enumerate(rule.get('cases', [])):
            cond = self._parse_condition(case.get('when', {}), rid, idx)
            apply = case.get('apply', {})
            
            # 1. 
            if cond['mode'] == 'nested':
                lines.extend([f"            {l}" for l in cond['lines']])
                act_indent = "                "
            else:
                lines.append(f"            if {cond['expr']}:")
                act_indent = "                "

            if beh == "growth":
                math = self._decompile_growth(apply)
                lines.append(f"{act_indent}cell.targetVolume += {math}")

            elif beh == "differentiate":
                if apply.get("new_type"):
                    new_t = apply.get("new_type").upper()
                    lines.append(f"{act_indent}cell.type = self.{new_t}")
                
                if apply.get("do_division") or apply.get("parent_type"):
                    intent = {
                        "parent_type": apply.get("parent_type"),
                        "child_type": apply.get("child_type"),
                        "volume_ratio": apply.get("volume_ratio", 0.5)
                    }
                    lines.append(f"{act_indent}cell.dict['mitosis_intent'] = {intent}")

                    placement = apply.get("placement", {"type": "random"})
                    if placement["type"] == "random":
                        lines.append(f"{act_indent}self.divide_cell_random_orientation(cell)")
                    
                    elif placement["type"] == "angle":
                        angle_rad = f"np.radians({placement.get('angle_deg', 0)})"
                        lines.append(f"{act_indent}nx, ny = np.cos({angle_rad}), np.sin({angle_rad})")
                        lines.append(f"{act_indent}self.divide_cell_orientation_vector_based(cell, nx, ny, 0)")
                    
                # Note: After native division, attribute assignment (e.g., parent_type, child_type)
                # must be handled inside the generated update_attributes(self) function, not here.
                # This section should only trigger the division action.

            elif beh == "death":
                # death: pending ... Targetvolume change
                lines.append(f"{act_indent}cell.targetVolume = 0")
                lines.append(f"{act_indent}cell.lambdaVolume = 100")

        return lines
    
    def _decompile_growth(self, apply):
        """
        Translate the growth model into a native mathematical expression string.
        """
        model = apply.get('model', 'linear')
        p = apply.get('parameters', {})
        reg = apply.get('regulator')
        # Define regulator sampling: if a field exists, sample from it; 
        # otherwise raise an error—unless the regulator is explicitly unspecified, 
        # in which case default to a constant value of 1.0.
            # simulate: self.field.FieldName[...]

        if pd.isna(reg) or str(reg).lower().strip() in ["nan", "none", ""]:
            reg_val = "1.0"
        else: 
            reg_val = f"self.field.{reg}[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]"

        if model == "linear":
            alpha = p.get('alpha', 0.1)
            # e.g. return "0.5 * self.field.Oxygen[...]"
            return f"{alpha} * {reg_val}"
        
        elif model == "hill":
            y_max = p.get('y_max', 1.0)
            K = p.get('K', 0.5)
            n = p.get('n', 2.0)
            return f"{y_max} * (({reg_val}**{n}) / ({K}**{n} + {reg_val}**{n}))"
        
        return "0.1" # default growth rate is 0.1
    
    def _parse_condition(self, when, rid, c_idx):
        c_type = when.get('condition_type', 'TRUE')
        p = when.get('params', {})

        if c_type == "TimeWindow":
            start = p.get('start_mcs', 0)
            end = p.get('end_mcs', 9999999)
            return {"mode": "simple", "expr": f"{start} <= mcs <= {end}"}

        elif c_type == "Probability":
            prob = p.get('p', 0.5)
            return {"mode": "simple", "expr": f"random.random() < {prob}"}
        
        elif c_type == "Environment":
            f, op, thr = p.get('field_name'), p.get('operator'), p.get('threshold')
            return {"mode": "simple", "expr": f"self.field.{f}[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)] {op} {thr}"}

        elif c_type.startswith("Morphology"):
            op, thr = p.get('operator'), p.get('threshold')
            if "Elongation" in c_type:
                expr = f"(cell.ecc) {op} {thr}"
            else:
                expr = f"cell.volume {op} {thr}"
            return {"mode": "simple", "expr": expr}

        return {"mode": "simple", "expr": "True"}
    
    def save_to_file(self, project_path, filename="SimulationStepCode.py"):
        """
        Save the generated native Python code to the CC3D project directory.
        """

        try:
            full_code = self.generate()
            
            base_path = Path(project_path)
            
            base_path.mkdir(parents=True, exist_ok=True)
            
            file_path = base_path / filename
            file_path.write_text(full_code, encoding="utf-8")
            
            print(f"✅ [Generator] Native code saved to: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ [Generator] Failed to save code: {e}")
            return False