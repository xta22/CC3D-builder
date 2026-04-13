print(">>> WRAPPER LOADED <<<")

from cc3d import CompuCellSetup

from Rules_projectSteppables import ConstraintInitializerSteppable
from core.rule_engine import RuleEngineSteppable
from steppables.growth_steppable import GrowthSteppable
from steppables.differentiate_steppable import DifferentiateSteppable
from steppables.create_steppable import CreateSteppable

CompuCellSetup.register_steppable(
    ConstraintInitializerSteppable(frequency=1)
)

rule_engine = RuleEngineSteppable(frequency=1)

CompuCellSetup.register_steppable(rule_engine)
CompuCellSetup.register_steppable(GrowthSteppable(frequency=1))
CompuCellSetup.register_steppable(DifferentiateSteppable(frequency=1, engine = rule_engine))
CompuCellSetup.register_steppable(CreateSteppable(frequency=1, engine=rule_engine))

CompuCellSetup.run()