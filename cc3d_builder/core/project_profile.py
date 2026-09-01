# project_profile.py
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROFILE_DIR_NAME = ".ruleparser"
PROFILE_RULES_NAME = "rules.json"
PROFILE_METADATA_NAME = "metadata.json"
ACTIVE_PROJECT_NAME = "active_project.json"
ORIGINAL_DIR_NAME = "original"


def profile_dir(source_path):
    source = project_root(source_path)
    return source / PROFILE_DIR_NAME


def project_root(source_path):
    source = Path(source_path).expanduser().resolve()
    return source.parent if source.is_file() else source


def profile_rules_path(source_path):
    return profile_dir(source_path) / PROFILE_RULES_NAME


def profile_metadata_path(source_path):
    return profile_dir(source_path) / PROFILE_METADATA_NAME


def original_simulation_dir(source_path):
    return profile_dir(source_path) / ORIGINAL_DIR_NAME / "Simulation"


def original_cc3d_path(source_path):
    return profile_dir(source_path) / ORIGINAL_DIR_NAME / "original.cc3d"


def original_xml_path(source_path):
    return original_simulation_dir(source_path) / "original.xml"


def original_steppables_path(source_path):
    return original_simulation_dir(source_path) / "original_Steppables.py"


def original_main_path(source_path):
    return original_simulation_dir(source_path) / "original_main.py"


def original_settings_path(source_path):
    return original_simulation_dir(source_path) / "original_settings.sqlite"


def sandbox_profile_dir(sandbox_path):
    return Path(sandbox_path).expanduser().resolve() / PROFILE_DIR_NAME


def active_project_path(sandbox_path):
    return sandbox_profile_dir(sandbox_path) / ACTIVE_PROJECT_NAME


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def has_project_profile(source_path):
    return profile_rules_path(source_path).exists()


def has_original_snapshot(source_path):
    return (
        original_cc3d_path(source_path).exists()
        or original_xml_path(source_path).exists()
        or original_steppables_path(source_path).exists()
        or original_main_path(source_path).exists()
        or original_settings_path(source_path).exists()
    )


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"⚠️ Could not read JSON file {path}: {exc}")
        return default

    if not text.strip():
        print(f"⚠️ Empty JSON file ignored: {path}")
        return default

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"⚠️ Invalid JSON file ignored: {path}: {exc}")
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_active_project(sandbox_path, source_path, mode):
    source = project_root(source_path)
    data = {
        "source_project_path": str(source),
        "profile_dir": str(profile_dir(source)),
        "profile_rules_path": str(profile_rules_path(source)),
        "mode": mode,
        "updated_at": utc_timestamp(),
    }
    write_json(active_project_path(sandbox_path), data)
    return data


def read_active_project(sandbox_path):
    return load_json(active_project_path(sandbox_path), {}) or {}


def restore_profile_to_sandbox(source_path, sandbox_path):
    source_rules = profile_rules_path(source_path)
    if not source_rules.exists():
        return False

    sandbox_rules = Path(sandbox_path).expanduser().resolve() / "Simulation" / PROFILE_RULES_NAME
    sandbox_rules.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_rules, sandbox_rules)
    return True


def _first_project_xml(source_path):
    source = project_root(source_path)
    candidates = [
        path for path in source.rglob("*.xml")
        if PROFILE_DIR_NAME not in path.parts
    ]
    return sorted(candidates)[0] if candidates else None


def _first_project_steppables(source_path):
    source = project_root(source_path)
    candidates = [
        path for path in source.rglob("*Steppables.py")
        if PROFILE_DIR_NAME not in path.parts
    ]
    return sorted(candidates)[0] if candidates else None


def _first_project_cc3d(source_path):
    source = project_root(source_path)
    candidates = [
        path for path in source.glob("*.cc3d")
        if PROFILE_DIR_NAME not in path.parts
    ]
    return sorted(candidates)[0] if candidates else None


def _first_project_main(source_path):
    source = project_root(source_path)
    candidates = [
        path for path in source.rglob("*main.py")
        if PROFILE_DIR_NAME not in path.parts
        and path.name not in {"wrapper_main.py", "gen_code_main.py", "generated_main.py"}
    ]
    return sorted(candidates)[0] if candidates else None


def _first_project_settings(source_path):
    source = project_root(source_path)
    candidates = [
        path for path in source.rglob("_settings.sqlite")
        if PROFILE_DIR_NAME not in path.parts
    ]
    return sorted(candidates)[0] if candidates else None


def ensure_original_snapshot(source_path):
    """
    Save immutable original XML/Steppables copies on first import.

    Existing snapshot files are never overwritten here.
    """
    snapshot_dir = original_simulation_dir(source_path)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    cc3d_source = _first_project_cc3d(source_path)
    cc3d_target = original_cc3d_path(source_path)
    if cc3d_source and not cc3d_target.exists():
        cc3d_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cc3d_source, cc3d_target)
        copied.append(str(cc3d_target))

    xml_source = _first_project_xml(source_path)
    xml_target = original_xml_path(source_path)
    if xml_source and not xml_target.exists():
        shutil.copy2(xml_source, xml_target)
        copied.append(str(xml_target))

    steppables_source = _first_project_steppables(source_path)
    steppables_target = original_steppables_path(source_path)
    if steppables_source and not steppables_target.exists():
        shutil.copy2(steppables_source, steppables_target)
        copied.append(str(steppables_target))

    main_source = _first_project_main(source_path)
    main_target = original_main_path(source_path)
    if main_source and not main_target.exists():
        shutil.copy2(main_source, main_target)
        copied.append(str(main_target))

    settings_source = _first_project_settings(source_path)
    settings_target = original_settings_path(source_path)
    if settings_source and not settings_target.exists():
        shutil.copy2(settings_source, settings_target)
        copied.append(str(settings_target))

    return copied


def restore_original_snapshot_to_sandbox(source_path, sandbox_path):
    """
    Restore original XML/Steppables snapshot into sandbox.

    Returns True if at least one original artifact was restored.
    """
    sandbox_sim = Path(sandbox_path).expanduser().resolve() / "Simulation"
    sandbox_sim.mkdir(parents=True, exist_ok=True)

    restored = False
    cc3d_source = original_cc3d_path(source_path)
    if cc3d_source.exists():
        shutil.copy2(cc3d_source, Path(sandbox_path).expanduser().resolve() / "Rules_project.cc3d")
        restored = True

    xml_source = original_xml_path(source_path)
    if xml_source.exists():
        shutil.copy2(xml_source, sandbox_sim / "Rules_project.xml")
        restored = True

    steppables_source = original_steppables_path(source_path)
    if steppables_source.exists():
        shutil.copy2(steppables_source, sandbox_sim / "Rules_project_Steppables.py")
        restored = True

    main_source = original_main_path(source_path)
    if main_source.exists():
        shutil.copy2(main_source, sandbox_sim / "original_main.py")
        restored = True

    settings_source = original_settings_path(source_path)
    if settings_source.exists():
        shutil.copy2(settings_source, sandbox_sim / "_settings.sqlite")
        restored = True

    return restored


def write_dynamic_cc3d(project_path, cc3d_path=None):
    project = project_root(project_path)
    target = Path(cc3d_path).expanduser().resolve() if cc3d_path else project / "Rules_project.cc3d"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        """<Simulation version="4.7.0">
   <XMLScript Type="XMLScript">Simulation/Rules_project.xml</XMLScript>
   <PythonScript Type="PythonScript">Simulation/wrapper_main.py</PythonScript>
   <Resource Type="Python">Simulation/Rules_project_Steppables.py</Resource>
   <Resource Type="Python">Simulation/SimulationStepCode.py</Resource>
</Simulation>
""",
        encoding="utf-8",
    )
    return target


def write_generated_cc3d(project_path, cc3d_path=None):
    project = project_root(project_path)
    target = Path(cc3d_path).expanduser().resolve() if cc3d_path else project / "Rules_project.cc3d"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        """<Simulation version="4.7.0">
   <XMLScript Type="XMLScript">Simulation/Rules_project.xml</XMLScript>
   <PythonScript Type="PythonScript">Simulation/gen_code_main.py</PythonScript>
   <Resource Type="Python">Simulation/Rules_project_Steppables.py</Resource>
   <Resource Type="Python">Simulation/SimulationStepCode.py</Resource>
</Simulation>
""",
        encoding="utf-8",
    )
    return target


def write_generated_main(project_path):
    project = project_root(project_path)
    sim_dir = project / "Simulation"
    sim_dir.mkdir(parents=True, exist_ok=True)
    main_path = sim_dir / "gen_code_main.py"
    main_path.write_text(
        """from cc3d import CompuCellSetup
from SimulationStepCode import SimulationSteppable

CompuCellSetup.register_steppable(SimulationSteppable(frequency=1))
CompuCellSetup.run()
""",
        encoding="utf-8",
    )
    return main_path


def write_dynamic_wrapper(project_path, development_root=None):
    project = project_root(project_path)
    sim_dir = project / "Simulation"
    sim_dir.mkdir(parents=True, exist_ok=True)
    if development_root is None:
        development_root = Path(__file__).resolve().parents[2]
    development_root = Path(development_root).expanduser().resolve()
    wrapper_path = sim_dir / "wrapper_main.py"
    wrapper_path.write_text(
        f'''print(">>> WRAPPER LOADED <<<")

import sys
import importlib
from pathlib import Path

DEVELOPMENT_ROOT = {str(development_root)!r}

def _detect_project_sim_dir(_sys=sys, _Path=Path):
    candidates = []
    for entry in _sys.path:
        if entry:
            candidates.append(_Path(entry))
    candidates.extend([_Path.cwd(), _Path.cwd() / "Simulation"])
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            continue
        if (resolved / "rules.json").exists() and (
            (resolved / "wrapper_main.py").exists()
            or (resolved / "Rules_project_Steppables.py").exists()
        ):
            return resolved
    return _Path(__file__).resolve().parent

PROJECT_SIM_DIR = _detect_project_sim_dir()

def _prepend_sys_path(path, _sys=sys):
    text = str(path)
    while text in _sys.path:
        _sys.path.remove(text)
    _sys.path.insert(0, text)

_prepend_sys_path(DEVELOPMENT_ROOT)
_prepend_sys_path(PROJECT_SIM_DIR)

print(f"DEBUG: wrapper file: {{Path(__file__).resolve()}}")
print(f"DEBUG: project sim dir: {{PROJECT_SIM_DIR}}")
print(f"DEBUG: sys.path[:5]: {{sys.path[:5]}}")

from cc3d import CompuCellSetup
from cc3d.core.PySteppables import SteppableBasePy

try:
    original_steppables = importlib.import_module("Rules_project_Steppables")
except Exception as exc:
    original_steppables = None
    print(f"[Wrapper] Could not import Rules_project_Steppables: {{exc}}")

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
from cc3d_builder.engine.steppables.pif_snapshot_steppable import RuleParserPIFDumperSteppable
from cc3d_builder.engine.steppables.subcellular_steppable import SubcellularSteppable
import cc3d_builder

print(f"DEBUG: cc3d_builder loaded from: {{Path(cc3d_builder.__file__).resolve()}}")


def _iter_project_steppable_classes(module, steppable_base=SteppableBasePy):
    if module is None:
        return
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
CompuCellSetup.register_steppable(SubcellularSteppable(frequency=1, engine=rule_engine))
CompuCellSetup.register_steppable(
    RuleParserPIFDumperSteppable(frequency=1, settings_path=PROJECT_SIM_DIR / "rules.json")
)

CompuCellSetup.run()
''',
        encoding="utf-8",
    )
    return wrapper_path


def _copy_if_exists(source, target):
    source = Path(source)
    target = Path(target)
    if not source.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source.resolve() == target.resolve():
            return None
    except OSError:
        pass
    shutil.copy2(source, target)
    return str(target)


def _remove_if_exists(path):
    path = Path(path)
    if not path.exists():
        return None
    if not path.is_file():
        return None
    path.unlink()
    return str(path)


def sync_sandbox_artifacts_to_source(sandbox_path, source_path=None, include_generated_code=True):
    sandbox = Path(sandbox_path).expanduser().resolve()
    if source_path is None:
        active = read_active_project(sandbox)
        source_path = active.get("source_project_path")
    if not source_path:
        return {"synced": False, "copied": [], "reason": "no active source project"}

    source = project_root(source_path)
    sandbox_sim = sandbox / "Simulation"
    source_sim = source / "Simulation"
    source_sim.mkdir(parents=True, exist_ok=True)

    ensure_original_snapshot(source)
    write_dynamic_wrapper(sandbox)
    write_dynamic_cc3d(sandbox)
    write_generated_main(sandbox)

    cc3d_target = _first_project_cc3d(source) or source / "Rules_project.cc3d"
    generated_cc3d_path = write_generated_cc3d(source, cc3d_target)
    mappings = [
        (sandbox_sim / "Rules_project.xml", source_sim / "Rules_project.xml"),
        (sandbox_sim / "Rules_project_Steppables.py", source_sim / "Rules_project_Steppables.py"),
        (sandbox_sim / "gen_code_main.py", source_sim / "gen_code_main.py"),
        (sandbox_sim / PROFILE_RULES_NAME, source_sim / PROFILE_RULES_NAME),
        (sandbox_sim / "_settings.sqlite", source_sim / "_settings.sqlite"),
    ]
    if include_generated_code:
        mappings.append((sandbox_sim / "SimulationStepCode.py", source_sim / "SimulationStepCode.py"))

    copied = [str(generated_cc3d_path)]
    for src, dst in mappings:
        copied_path = _copy_if_exists(src, dst)
        if copied_path:
            copied.append(copied_path)
    removed = []
    removed_path = _remove_if_exists(source_sim / "wrapper_main.py")
    if removed_path:
        removed.append(removed_path)

    metadata = load_json(profile_metadata_path(source), {}) or {}
    metadata.update({
        "source_project_path": str(source),
        "sandbox_project_path": str(sandbox),
        "artifacts_synced_at": utc_timestamp(),
        "synced_artifacts": copied,
        "removed_artifacts": removed,
    })
    write_json(profile_metadata_path(source), metadata)
    write_active_project(sandbox, source, mode="synced")
    return {
        "synced": bool(copied),
        "copied": copied,
        "removed": removed,
        "source_project_path": str(source),
    }


def _rule_count_from_file(path):
    try:
        data = load_json(path, {}) or {}
        rules = data.get("rules", [])
        return len(rules) if isinstance(rules, list) else 0
    except Exception:
        return None


def sync_sandbox_rules_to_profile(sandbox_path, source_path=None):
    sandbox = Path(sandbox_path).expanduser().resolve()
    if source_path is None:
        active = read_active_project(sandbox)
        source_path = active.get("source_project_path")
    if not source_path:
        return False

    source = project_root(source_path)
    sandbox_rules = sandbox / "Simulation" / PROFILE_RULES_NAME
    if not sandbox_rules.exists():
        return False

    target_rules = profile_rules_path(source)
    target_rules.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sandbox_rules, target_rules)

    metadata = {
        "source_project_path": str(source),
        "sandbox_project_path": str(sandbox),
        "rules_path": str(target_rules),
        "rule_count": _rule_count_from_file(target_rules),
        "updated_at": utc_timestamp(),
    }
    cc3d_files = sorted(source.glob("*.cc3d"))
    if cc3d_files:
        metadata["cc3d_file"] = str(cc3d_files[0])
    write_json(profile_metadata_path(source), metadata)
    write_active_project(sandbox, source, mode="synced")
    return True
