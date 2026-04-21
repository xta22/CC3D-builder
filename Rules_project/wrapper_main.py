print(">>> WRAPPER LOADED <<<")

from cc3d import CompuCellSetup

from Rules_project.Rules_projectSteppables import ConstraintInitializerSteppable
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