from cc3d.core.PySteppables import *
import numpy as np

# mechanisms have to be standardized somehow
# should the HF modulate a base parameter, or should the parameters of the hill function have the units of the parameter
# where do we instantiate the rules? In XML? In Python? Inside a class?
# Rule 1: Oxygen -> promotes growth_rate
# r1_min = 0; r1_max = 0; r1_hm = 0.5; r1_n = 10
# Rule 2: xCOM -> inhibits lambdaVolume
# r2_min = 2; r2_max = 2; r2_hm = 50; r2_n = 4 # problem with knowing the lattice size here

# other rules we should try: with SBML variables back and forth

class ConstraintInitializerSteppable(SteppableBasePy):
    def __init__(self,frequency=1):
        SteppableBasePy.__init__(self,frequency)

    def start(self):
        # === CC3D_VOLUME_CELLA START ===
        for cell in self.cell_list_by_type(self.CELLA):
            cell.targetVolume = 50.0
            cell.lambdaVolume = 10.0
        # === CC3D_VOLUME_CELLA END ===
        # === CC3D_VOLUME_CELL START ===
        for cell in self.cell_list_by_type(self.CELL):
            cell.targetVolume = 50.0
            cell.lambdaVolume = 2.0
        # === CC3D_VOLUME_CELL END ===
        # === CC3D_DICT_INIT START ===
        for cell in self.cell_list:
            if "state" not in cell.dict:
                cell.dict["state"] = {}
                cell.dict["requests"] = {}
                cell.dict["_internal"] = {}
        # === CC3D_DICT_INIT END ===

    def step(self, mcs):
        return