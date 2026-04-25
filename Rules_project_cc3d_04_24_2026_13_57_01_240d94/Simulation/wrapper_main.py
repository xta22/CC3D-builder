print(">>> WRAPPER LOADED <<<")

import sys
from pathlib import Path

DEVELOPMENT_ROOT = "/Users/xiaoyue/src/RuleParser"
PROJECT_SIM_DIR = "/Users/xiaoyue/src/RuleParser/Rules_project/Simulation"

# 2. 注入路径
if DEVELOPMENT_ROOT not in sys.path:
    sys.path.insert(0, DEVELOPMENT_ROOT)
if PROJECT_SIM_DIR not in sys.path:
    sys.path.insert(0, PROJECT_SIM_DIR)

# 打印出来确认，这次应该显示 /Users/xiaoyue/src/RuleParser
print(f"DEBUG: sys.path[0] is now: {sys.path[0]}")


from cc3d import CompuCellSetup
print("1")
from Rules_project.Simulation.Rules_project_Steppables import ConstraintInitializerSteppable
print("2")
from cc3d_builder.engine.core.rule_engine import RuleEngineSteppable
print("3")
from cc3d_builder.engine.steppables.growth_steppable import GrowthSteppable
print("4")
from cc3d_builder.engine.steppables.differentiate_steppable import DifferentiateSteppable
print("5")
from cc3d_builder.engine.steppables.create_steppable import CreateSteppable
print("6")

CompuCellSetup.register_steppable(
    ConstraintInitializerSteppable(frequency=1)
)

print("7")

rule_engine = RuleEngineSteppable(frequency=1)
print("8")
CompuCellSetup.register_steppable(rule_engine)
print("9")
CompuCellSetup.register_steppable(GrowthSteppable(frequency=1))
print("10")
CompuCellSetup.register_steppable(DifferentiateSteppable(frequency=1, engine = rule_engine))
print("11")
CompuCellSetup.register_steppable(CreateSteppable(frequency=1, engine=rule_engine))
print("12")

CompuCellSetup.run()
print("13")