# project_manager.py
import shutil
from pathlib import Path
from cc3d_builder.core.project_profile import (
    ensure_original_snapshot,
    has_project_profile,
    PROFILE_DIR_NAME,
    read_active_project,
    restore_original_snapshot_to_sandbox,
    restore_profile_to_sandbox,
    write_active_project,
)

class ProjectManager: 
    def __init__(self, sandbox_path: Path):
        self.sandbox = sandbox_path
    
    def initialize_project(self, source_path: Path, is_import: bool = False):
        """
        called by CLI or GUI 
        """
        src = source_path.expanduser().resolve()
        if src.is_file():
            src = src.parent
        json_path = self.sandbox / "Simulation" / "rules.json"

        if is_import:
            # Import new projects 
            print(f"🚀 Importing new project from: {src}")
            copied = ensure_original_snapshot(src)
            if copied:
                print(f"📦 Original project snapshot saved: {len(copied)} file(s)")
            if restore_original_snapshot_to_sandbox(src, self.sandbox):
                self._ensure_sandbox_packages()
                self._write_dynamic_wrapper()
                print("♻️ Restored XML/Steppables from original snapshot.")
            else:
                self._clear_and_copy_assets(src)
            # empty or reset json
            self._reset_rules_json()
            write_active_project(self.sandbox, src, mode="import_new")

        else:
            # Resume the selected source project, not whichever rules are
            # currently left in the shared sandbox from a previous project.
            print(f"♻️ Resuming project from: {src}")
            self._clear_and_copy_assets(src)

            if restore_profile_to_sandbox(src, self.sandbox):
                print(f"✅ Restored project rules from: {src / '.ruleparser' / 'rules.json'}")
            else:
                active = read_active_project(self.sandbox)
                active_source = Path(active.get("source_project_path", "")).expanduser() if active.get("source_project_path") else None
                same_active_project = active_source is not None and active_source.resolve() == src
                if json_path.exists() and same_active_project:
                    print("♻️ No project profile found; keeping current sandbox rules for the same active project.")
                else:
                    print("🐣 No project profile found; initializing empty rules for this project.")
                    self._reset_rules_json()

            write_active_project(self.sandbox, src, mode="resume")

            if not json_path.exists():
                self._reset_rules_json()
            if (self.sandbox / "Simulation" / "Rules_project_Steppables.py").exists():
                self._write_dynamic_wrapper()


    def _clear_and_copy_assets(self, src: Path):
        """ move and reset XML and Steppable """
        sim_dir = self._ensure_sandbox_packages()

        # 1. XML 
        xml_files = sorted(
            path for path in src.rglob("*.xml")
            if PROFILE_DIR_NAME not in path.parts
        )
        if xml_files:
            shutil.copy2(xml_files[0], sim_dir / "Rules_project.xml")

        # 2. Steppables
        py_files = sorted(
            path for path in src.rglob("*Steppables.py")
            if PROFILE_DIR_NAME not in path.parts
        )
        if py_files:
            shutil.copy2(py_files[0], sim_dir / "Rules_project_Steppables.py")

        self._write_dynamic_wrapper()

    def _ensure_sandbox_packages(self):
        sim_dir = self.sandbox / "Simulation"
        sim_dir.mkdir(parents=True, exist_ok=True)
        (self.sandbox / "__init__.py").touch()
        (sim_dir / "__init__.py").touch()
        return sim_dir

    def _write_dynamic_wrapper(self):
        development_root = self.sandbox.resolve().parent
        project_sim_dir = (self.sandbox / "Simulation").resolve()
        wrapper_path = project_sim_dir / "wrapper_main.py"

        wrapper_path.write_text(f'''print(">>> WRAPPER LOADED <<<")

import sys
import json
import importlib
from pathlib import Path

DEVELOPMENT_ROOT = "{development_root}"
PROJECT_SIM_DIR = "{project_sim_dir}"
RULES_PATH = Path(PROJECT_SIM_DIR) / "rules.json"

if DEVELOPMENT_ROOT not in sys.path:
    sys.path.insert(0, DEVELOPMENT_ROOT)
if PROJECT_SIM_DIR not in sys.path:
    sys.path.insert(0, PROJECT_SIM_DIR)

print(f"DEBUG: sys.path[0] is now: {{sys.path[0]}}")

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
    print(f"[Wrapper] Registered original steppable: {{class_name}}")

if not registered_original:
    print("[Wrapper] No original project steppable class found in Rules_project_Steppables.py")

rule_engine = RuleEngineSteppable(frequency=1)
try:
    with RULES_PATH.open(encoding="utf-8") as handle:
        rule_config = json.load(handle)
except Exception as exc:
    print(f"[Wrapper] Could not load rules.json for optional steppables: {{exc}}")
    rule_config = dict()

if not isinstance(rule_config, dict):
    rule_config = dict()

optional_rules = rule_config.get("rules") if isinstance(rule_config, dict) else []
optional_subcellular_systems = rule_config.get("subcellular_systems") if isinstance(rule_config, dict) else []
optional_settings = rule_config.get("settings") if isinstance(rule_config, dict) else {{}}
if not isinstance(optional_rules, list):
    optional_rules = []
if not isinstance(optional_subcellular_systems, list):
    optional_subcellular_systems = []
if not isinstance(optional_settings, dict):
    optional_settings = {{}}

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
''', encoding="utf-8")

    def _reset_rules_json(self):
        """ clean JSON """
        json_path = self.sandbox / "Simulation" / "rules.json"
        json_path.write_text(
            '{"rules": [], "celltype_params": {}, "field_params": {}, "intracellular_models": [], '
            '"subcellular_systems": [], '
            '"settings": {"execution_semantics": "snapshot"}}'
        )
