# topology/contact_ratio.py
import operator
import sys

sys.path.append("/Users/xiaoyue/src/bioinfo/project/Rules_project/simulation")
from core.rule_engine import RuleEngine

OPS = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne
}

def evaluate(cell, engine:'RuleEngine', params):

    target_type = params.get("target_type")
    threshold = params.get("threshold", 0.5)
    
    op_str = params.get("operator", ">") 
    
    compare_func = OPS.get(op_str, operator.gt) 
    
    current_ratio = engine.get_contact_ratio(cell, target_type)
    
    return compare_func(current_ratio, threshold)