from cc3d.core.PySteppables import *
import numpy as np
import math
import random

class SimulationSteppable(SteppableBasePy):
    def __init__(self, frequency=1):
        SteppableBasePy.__init__(self, frequency)

    def step(self, mcs):

        # --- Compiled Rule 1 (growth) ---
        for cell in self.cell_list_by_type(self.CELLA):

        # --- Compiled Rule 2 (growth) ---
        for cell in self.cell_list_by_type(self.CELLB):

        # --- Compiled Rule 3 (growth) ---
        for cell in self.cell_list_by_type(self.CELLA):

        # --- Compiled Rule 1 (growth) ---
        for cell in self.cell_list_by_type(self.CELLA):

        # --- Compiled Rule 1 (growth) ---
        for cell in self.cell_list_by_type(self.CELLA):