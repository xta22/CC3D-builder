print(">>> WRAPPER LOADED <<<")

from cc3d import CompuCellSetup

from Rules_project.Simulation.Rules_projectSteppables import ConstraintInitializerSteppable
from Rules_project.Simulation.core.rule_engine import RuleEngineSteppable
from Rules_project.Simulation.steppables.growth_steppable import GrowthSteppable
from Rules_project.Simulation.steppables.differentiate_steppable import DifferentiateSteppable
from Rules_project.Simulation.steppables.create_steppable import CreateSteppable

CompuCellSetup.register_steppable(
    ConstraintInitializerSteppable(frequency=1)
)

rule_engine = RuleEngineSteppable(frequency=1)

CompuCellSetup.register_steppable(rule_engine)
CompuCellSetup.register_steppable(GrowthSteppable(frequency=1))
CompuCellSetup.register_steppable(DifferentiateSteppable(frequency=1, engine = rule_engine))
CompuCellSetup.register_steppable(CreateSteppable(frequency=1, engine=rule_engine))

CompuCellSetup.run()