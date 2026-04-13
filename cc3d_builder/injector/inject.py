# inject.py

import os
import sys
from core.structure_manager import StructureManager
from injector.steppable_injector import SteppableInjector

def process_and_inject_rule(project_path, registry, rule):

    sim_path = os.path.join(project_path, "Simulation")
    if sim_path not in sys.path:
        sys.path.append(sim_path)
    
    sm = StructureManager(project_path)
    injector = SteppableInjector(project_path)
    # ==========================================
    # ==========================================
    sm.ensure_from_rule(rule)

    from utils_extensions.utils import extract_celltypes_from_rule
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