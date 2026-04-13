import operator
import sys

sys.path.append("/Users/xiaoyue/src/bioinfo/project/Rules_project/simulation")

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.rule_engine import RuleEngine

OPS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}

def evaluate(cell, engine: 'RuleEngine', params: dict):

    threshold = params.get("threshold", 1.0)
    compare_func = OPS.get(params.get("operator", ">"), operator.gt)
    
    ssa = engine.get_specific_surface_area(cell)
    
    return compare_func(ssa, threshold)