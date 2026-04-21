# model_registry.py

import math

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
def linear_model(apply, cell, engine):
    regulator_name = apply.get("regulator")
    params = apply.get("parameters", {})
    alpha = params.get("alpha", 1.0)  

    if not regulator_name:
        return 0.0

    try:
        field = getattr(engine.field, regulator_name, None)
        if field is not None:
            val = field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]
            return float(alpha * val)
    except Exception as e:
        print(f"Linear Model Error: {e} | Field: {regulator_name}")
        return 0.0
        
    return 0.0

# ================================
# HILL
# ================================
def hill_model(apply, cell, engine):
    params = apply.get("parameters", {})
    reg_name = apply.get("regulator")
    
    try:
        field = getattr(engine.field, reg_name)
        val = field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]
    except:
        val = 0.0

    y_max = params.get("y_max", 1.0)
    y_min = params.get("y_min", 0.0)
    K = params.get("K", 0.5)
    n = params.get("n", 2.0)

    growth = y_min + (y_max - y_min) * (val**n / (K**n + val**n + 1e-12))
    return float(growth)
'''
def hill_model(apply, cell, engine):

    regulators = apply["regulator"]
    if not isinstance(regulators, list):
        regulators = [regulators]

    params = apply["parameters"]

    y_max = params.get("y_max", 1.0)
    y_min = params.get("y_min", 0.0)
    K = params.get("K", 1.0)
    n = params.get("n", 1.0)

    product = 1.0

    for reg in regulators:
        field = getattr(engine.field, reg)
        A = field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]

        hill = (A**n) / (K**n + A**n + 1e-12)
        product *= hill

    return y_min + (y_max - y_min) * product
'''

# ================================
# EXPRESSION
# ================================
import re
def expression_model(apply, cell, engine):
    params = apply.get("parameters", {})
    expr = params.get("expression")
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