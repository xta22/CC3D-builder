# model_registry.py

import math


def _normalize_regulators(regulator):
    if regulator is None:
        return []
    raw = regulator if isinstance(regulator, list) else [regulator]
    regulators = []
    for item in raw:
        text = str(item).strip()
        if not text or text.lower() in {"none", "null", "nan"}:
            continue
        regulators.append(text)
    return regulators

def get_local_fields(cell, engine):
    local_vars = {}
    # loop through engine.field (self.field in cc3d)
    for name in dir(engine.field):
        if name.startswith('_'): continue
        try:
            field = getattr(engine.field, name)
            if field is not None and hasattr(field, "__getitem__"):
                val = field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]
                local_vars[name] = val
        except:
            continue
    return local_vars

# ================================
# LINEAR
# ================================
def linear_model(request, cell, engine):
    regulator_name = request.get("regulator")
    alpha = request.get("alpha", 1.0)

    regulators = _normalize_regulators(regulator_name)
    if not regulators:
        return 0.0

    alphas = alpha if isinstance(alpha, list) else [alpha] * len(regulators)

    try:
        total = 0.0
        for reg, coef in zip(regulators, alphas):
            field = getattr(engine.field, str(reg), None)
            if field is not None:
                val = field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]
                total += float(coef) * float(val)
        return float(total)
    except Exception as e:
        print(f"Linear Model Error: {e} | Field: {regulators}")
        return 0.0

# ================================
# HILL
# ================================
def hill_model(request, cell, engine):
    regulators = request.get("regulator")
    regulators = _normalize_regulators(regulators)
    if not regulators:
        return 0.0

    y_max = request.get("y_max", 1.0)
    y_min = request.get("y_min", 0.0)
    K = request.get("K", 0.5)
    n = request.get("n", 2.0)
    product = 1.0

    for reg in regulators:
        try:
            field = getattr(engine.field, reg)
            val = field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]
        except Exception:
            val = 0.0

        hill = (val**n) / (K**n + val**n + 1e-12)
        product *= hill

    return float(y_min + (y_max - y_min) * product)

# ================================
# EXPRESSION
# ================================
import re
def expression_model(request, cell, engine):
    expr = request.get("expression")
    if not expr: return 0.0

    # 1. Identify all possible variable names in the expression (e.g., Oxygen)
    #    Use a regular expression to find all words that start with a letter

    potential_vars = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', expr)
    
    local_vars = {}
    x, y, z = int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)

    # 2. go to engine.field find these variables
    for var_name in set(potential_vars):
        if var_name in ["min", "max", "abs", "math"]: continue
        
        try:
            field = getattr(engine.field, var_name, None)
            if field is not None:
                val = field[x, y, z]
                local_vars[var_name] = float(val)
        except:
            # skip if it is not a field
            continue

    # 3. Computation
    SAFE = {"min": min, "max": max, "abs": abs, "math": math}
    try:
        # print(f"DEBUG EVAL: Expr={expr} Vars={local_vars}")
        return float(eval(expr, {"__builtins__": None}, {**SAFE, **local_vars}))
    except Exception as e:
        print(f"Expression Eval Error: {e} | Expr: {expr} | Vars: {local_vars.keys()}")
        return

# ================================
# REGISTRY
# ================================

MODEL_REGISTRY = {
    "linear": linear_model,
    "hill": hill_model,
    "expression": expression_model
}
