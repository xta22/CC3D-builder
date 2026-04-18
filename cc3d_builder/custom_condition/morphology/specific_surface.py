import operator
import sys
from pathlib import Path
from cc3d_builder.utils_extensions.paths import ROOT, SIMULATION_DIR
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Rules_project.Simulation.core.rule_engine import RuleEngineSteppable

OPS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}

def evaluate(cell, engine: 'RuleEngineSteppable', params: dict):

    threshold = params.get("threshold", 1.0)
    compare_func = OPS.get(params.get("operator", ">"), operator.gt)
    
    ssa = engine.get_specific_surface_area(cell)
    
    return compare_func(ssa, threshold)