print(">>> WRAPPER LOADED <<<")

import sys
from pathlib import Path

DEVELOPMENT_ROOT = "/Users/xiaoyue/src/RuleParser"
PROJECT_SIM_DIR = "/Users/xiaoyue/src/RuleParser/Rules_project/Simulation"

if DEVELOPMENT_ROOT not in sys.path:
    sys.path.insert(0, DEVELOPMENT_ROOT)
if PROJECT_SIM_DIR not in sys.path:
    sys.path.insert(0, PROJECT_SIM_DIR)

# should be /Users/xiaoyue/src/RuleParser
print(f"DEBUG: sys.path[0] is now: {sys.path[0]}")


from cc3d import CompuCellSetup

from Rules_project.Simulation.Rules_project_Steppables import ConstraintInitializerSteppable

from cc3d_builder.engine.core.rule_engine import RuleEngineSteppable

from cc3d_builder.engine.steppables.growth_steppable import GrowthSteppable

from cc3d_builder.engine.steppables.differentiate_steppable import DifferentiateSteppable

from cc3d_builder.engine.steppables.create_steppable import CreateSteppable

CompuCellSetup.register_steppable(
    ConstraintInitializerSteppable(frequency=1)
)

rule_engine = RuleEngineSteppable(frequency=1)

CompuCellSetup.register_steppable(rule_engine)

CompuCellSetup.register_steppable(GrowthSteppable(frequency=1))

CompuCellSetup.register_steppable(DifferentiateSteppable(frequency=1, engine = rule_engine))

CompuCellSetup.register_steppable(CreateSteppable(frequency=1, engine=rule_engine))


CompuCellSetup.run()
