import operator
import sys


## 这里不能写死 better change
sys.path.append("/Users/xiaoyue/src/bioinfo/project/Rules_project/simulation")

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.rule_engine import RuleEngine

OPS = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne
}

def evaluate(cell, engine: 'RuleEngine', params: dict):

    target_type = params.get("target_type")
    threshold = params.get("threshold", 10.0)
    
    op_str = params.get("operator", "<") 
    compare_func = OPS.get(op_str, operator.lt)
    
    min_dist = engine.get_min_distance_to_type(cell, target_type)
    
    return compare_func(min_dist, threshold)