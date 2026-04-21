import operator
import sys
from pathlib import Path
from cc3d_builder.utils_extensions.paths import ROOT, SIMULATION_DIR
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cc3d_builder.engine.core.rule_engine import RuleEngineSteppable


def evaluate(cell, engine: 'RuleEngineSteppable', params: dict):
    """
    # Check whether a sub-condition has persisted for a specified number of MCS.
    # Example parameters: {"sub_condition_script": "environment/is_hypoxia.py", "threshold_mcs": 50}
    """
    threshold_mcs = params.get("threshold_mcs", 50)
    sub_script = params.get("sub_condition_script")
    
    current_mcs = engine.cc3d_steppable.mcs
    
    # Estimate whether the basic condition is True.
    is_state_active = engine.evaluate_single_condition(cell, sub_script, params.get("sub_params", {}))
    
    # store the data into cell.dict 
    dict_key = f"timer_start_{sub_script}"
    
    if is_state_active:
        # if status is activated，and it didnt record the time before，then take down the beginning MCS
        if dict_key not in cell.dict:
            cell.dict[dict_key] = current_mcs
        
        duration = current_mcs - cell.dict[dict_key]
        return duration > threshold_mcs
    else:
        # if status changed immediately reset to zero.
        if dict_key in cell.dict:
            del cell.dict[dict_key]
        return False