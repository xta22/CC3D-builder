import operator
import sys
from pathlib import Path
from cc3d_builder.utils_extensions.paths import ROOT, SIMULATION_DIR
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Rules_project.Simulation.core.rule_engine import RuleEngineSteppable

from typing import TYPE_CHECKING

OPS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}

def evaluate(cell, engine: 'RuleEngineSteppable', params: dict):

    threshold = params.get("threshold", 2.0)
    compare_func = OPS.get(params.get("operator", ">"), operator.gt)
    
    aspect_ratio = engine.get_elongation_ratio(cell)
    
    return compare_func(aspect_ratio, threshold)