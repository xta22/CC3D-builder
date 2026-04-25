from cc3d.core.PySteppables import *
import numpy as np
import math
import random

class SimulationSteppable(SteppableBasePy):
    def __init__(self, frequency=1):
        SteppableBasePy.__init__(self, frequency)

    def step(self, mcs):

        # --- Rule 1: growth ---
        for cell in self.cell_list_by_type(self.CELL):
            if self.field.Oxygen[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)] > 1.0:
                # Applied hill growth model
                cell.targetVolume += 1.0 * ((self.field.Oxygen[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]**2.0) / (0.5**2.0 + self.field.Oxygen[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]**2.0))