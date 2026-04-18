# inject.py

import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
BUILDER_ROOT = CURRENT_FILE.parents[1]


from cc3d_builder.core.structure_manager import StructureManager
from cc3d_builder.injector.steppable_injector import SteppableInjector
from cc3d_builder.utils_extensions.rule_parsing import extract_celltypes_from_rule


def process_and_inject_rule(project_path, registry, rule):

    project_dir = Path(project_path).resolve()
    sim_path = project_dir / "Simulation"

    if str(sim_path) not in sys.path:
        sys.path.append(str(sim_path))

    sm = StructureManager(str(project_dir))
    injector = SteppableInjector(str(project_dir))

    sm.ensure_from_rule(rule)

    all_involved_types = extract_celltypes_from_rule(rule)
    
    for ct in all_involved_types:
        if ct not in registry.celltype_params:
            registry.add_celltype_params(ct, 50.0, 10.0)

    # ==========================================
    # ==========================================
    legacy_volumes = sm.migrate_volume_data()
    for ct, params in legacy_volumes.items():
        if ct not in registry.celltype_params:
            registry.add_celltype_params(ct, params["targetVolume"], params["lambdaVolume"])

    sm.ensure_volume_plugin_empty()

    # ==========================================
    # 3. inject Python Steppables
    # ==========================================
    injector.ensure_dict_init()
    
    for ct, saved_params in registry.celltype_params.items():
        injector.ensure_volume_start_code(
            celltype_name=ct,
            target_volume=saved_params["targetVolume"],
            lambda_volume=saved_params["lambdaVolume"]
        )

    sm.save() 
    
    print(f"[Inject] Rule {rule.get('id', 'Unknown')} injected and legacy cells migrated successfully.")