# dormancy_inhibitor_plugin.py
from .base_plugin import BaseBehaviourPlugin


class DormancyInhibitorPlugin(BaseBehaviourPlugin):
    """
    Highest-priority interception plugin: checks whether the cell is in dormancy.
    """
    behaviour_name = "dormancy_filter"


    def should_inhibit(self, cell, behaviour_type):
        """
        A sentinel function that the Engine calls before executing any plugins in the pre-processing phase.
        """

        EXCLUDED_BEHAVIOURS = ["death", "dormancy"]
        
        if behaviour_type not in EXCLUDED_BEHAVIOURS:
            if cell.dict.get("dormant", False):
                return True
                
        return False