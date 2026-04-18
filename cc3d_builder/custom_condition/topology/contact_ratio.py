# topology/contact_ratio.py
import operator
import sys
from pathlib import Path
from cc3d_builder.utils_extensions.paths import ROOT, SIMULATION_DIR
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Rules_project.Simulation.core.rule_engine import RuleEngineSteppable

OPS = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne
}

def evaluate(cell, engine:'RuleEngineSteppable', params):

    target_type = params.get("target_type")
    threshold = params.get("threshold", 0.5)
    
    op_str = params.get("operator", ">") 
    
    compare_func = OPS.get(op_str, operator.gt) 
    
    current_ratio = engine.get_contact_ratio(cell, target_type)
    
    return compare_func(current_ratio, threshold)