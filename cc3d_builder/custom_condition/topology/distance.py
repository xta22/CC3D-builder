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

def evaluate(cell, engine: 'RuleEngineSteppable', params: dict):

    target_type = params.get("target_type")
    threshold = params.get("threshold", 10.0)
    
    op_str = params.get("operator", "<") 
    compare_func = OPS.get(op_str, operator.lt)
    
    min_dist = engine.get_min_distance_to_type(cell, target_type)
    
    return compare_func(min_dist, threshold)