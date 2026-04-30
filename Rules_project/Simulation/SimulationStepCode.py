from cc3d.core.PySteppables import *
import numpy as np

class SimulationSteppable(MitosisSteppableBase):
    def __init__(self, frequency=1, engine=None):
        MitosisSteppableBase.__init__(self, frequency)
        self.engine = engine

    def step(self, mcs):
        if not self.engine: return

        # --- [ZONE: CELL-BASED] ---
        for cell in self.cell_list_by_type(self.CELL):
            if (cell.ecc) >= 1.5:
                cell.dict['mitosis_intent'] = {'parent_type': 'CellB', 'child_type': 'CellB', 'volume_ratio': 0.5}
                self.divide_cell_random_orientation(cell)

    def update_attributes(self):
        parent = self.parent_cell
        child = self.child_cell
        
        # Basic attribute cloning
        self.clone_parent_2_child()
        
        # Handle type transitions based on pre-division markers
        # Users need to mark parent.dict before division in the step function
        intent = parent.dict.get('mitosis_intent')
        if intent:
            p_type = intent.get('parent_type')
            c_type = intent.get('child_type')
            ratio = intent.get('volume_ratio', 0.5)
            
            if p_type: parent.type = getattr(self, p_type.upper())
            if c_type: child.type = getattr(self, c_type.upper())
            
            # Volume redistribution
            total_v = parent.targetVolume
            parent.targetVolume = total_v * ratio
            child.targetVolume = total_v * (1.0 - ratio)
            
            # Clean the mark
            parent.dict['mitosis_intent'] = None