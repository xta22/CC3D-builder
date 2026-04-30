from cc3d.core.PySteppables import *
import numpy as np

class SimulationSteppable(SteppableBasePy):
    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine

    def step(self, mcs):
        if not self.engine: return

        # --- [ZONE: CELL-BASED] ---
        for cell in self.cell_list_by_type(self.CELLA):
        for cell in self.cell_list_by_type(self.CELLB):