print(">>> WRAPPER LOADED <<<")

import sys
import json
import importlib
from pathlib import Path

DEVELOPMENT_ROOT = "/Users/xiaoyue/src/RuleParser"
PROJECT_SIM_DIR = "/Users/xiaoyue/src/RuleParser/Rules_project/Simulation"
RULES_PATH = Path(PROJECT_SIM_DIR) / "rules.json"

if DEVELOPMENT_ROOT not in sys.path:
    sys.path.insert(0, DEVELOPMENT_ROOT)
if PROJECT_SIM_DIR not in sys.path:
    sys.path.insert(0, PROJECT_SIM_DIR)

print(f"DEBUG: sys.path[0] is now: {sys.path[0]}")

from cc3d import CompuCellSetup
from cc3d.core.PySteppables import SteppableBasePy

original_steppables = importlib.import_module(
    "Rules_project.Simulation.Rules_project_Steppables"
)

from cc3d_builder.engine.core.rule_engine import RuleEngineSteppable
from cc3d_builder.engine.steppables.growth_steppable import GrowthSteppable
from cc3d_builder.engine.steppables.differentiate_steppable import DifferentiateSteppable
from cc3d_builder.engine.steppables.create_steppable import CreateSteppable
from cc3d_builder.engine.steppables.death_steppable import DeathSteppable
from cc3d_builder.engine.steppables.dormancy_steppable import DormancySteppable
from cc3d_builder.engine.steppables.phagocytosis_steppable import PhagocytosisSteppable
from cc3d_builder.engine.steppables.secrete_uptake_steppable import SecretionSteppable
from cc3d_builder.engine.steppables.chemotaxis_steppable import ChemotaxisSteppable
from cc3d_builder.engine.steppables.force_steppable import ForceSteppable
from cc3d_builder.engine.steppables.compartmentalize_steppable import CompartmentalizeSteppable
from cc3d_builder.engine.steppables.fpp_link_steppable import FPPLinkSteppable
from cc3d_builder.engine.steppables.intracellular_model_steppable import IntracellularModelSteppable


def _iter_project_steppable_classes(module, steppable_base=SteppableBasePy):
    for name, obj in vars(module).items():
        if not isinstance(obj, type):
            continue
        if obj.__module__ != module.__name__:
            continue
        try:
            if issubclass(obj, steppable_base):
                yield name, obj
        except TypeError:
            continue


registered_original = False
for class_name, steppable_cls in _iter_project_steppable_classes(original_steppables):
    try:
        steppable = steppable_cls(frequency=1)
    except TypeError:
        steppable = steppable_cls()
    CompuCellSetup.register_steppable(steppable)
    registered_original = True
    print(f"[Wrapper] Registered original steppable: {class_name}")

if not registered_original:
    print("[Wrapper] No original project steppable class found in Rules_project_Steppables.py")

rule_engine = RuleEngineSteppable(frequency=1)
try:
    with RULES_PATH.open(encoding="utf-8") as handle:
        rule_config = json.load(handle)
except Exception as exc:
    print(f"[Wrapper] Could not load rules.json for optional steppables: {exc}")
    rule_config = dict()

if not isinstance(rule_config, dict):
    rule_config = dict()

optional_rules = rule_config.get("rules") if isinstance(rule_config, dict) else []
optional_subcellular_systems = rule_config.get("subcellular_systems") if isinstance(rule_config, dict) else []
optional_settings = rule_config.get("settings") if isinstance(rule_config, dict) else {}
if not isinstance(optional_rules, list):
    optional_rules = []
if not isinstance(optional_subcellular_systems, list):
    optional_subcellular_systems = []
if not isinstance(optional_settings, dict):
    optional_settings = {}

has_subcellular_config = bool(optional_subcellular_systems) or any(
    isinstance(rule, dict) and str(rule.get("behaviour", "")).lower() == "subcellular"
    for rule in optional_rules
)

CompuCellSetup.register_steppable(rule_engine)
CompuCellSetup.register_steppable(DeathSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(GrowthSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(DormancySteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(PhagocytosisSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(SecretionSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(DifferentiateSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(CreateSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(ChemotaxisSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(ForceSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(CompartmentalizeSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(FPPLinkSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(IntracellularModelSteppable(frequency=1, engine=rule_engine))

if has_subcellular_config:
    from cc3d_builder.engine.steppables.subcellular_steppable import SubcellularSteppable
    CompuCellSetup.register_steppable(SubcellularSteppable(frequency=1, engine=rule_engine))

CompuCellSetup.run()
