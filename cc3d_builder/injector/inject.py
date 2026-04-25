# inject.py

import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
BUILDER_ROOT = CURRENT_FILE.parents[1]


from cc3d_builder.core.structure_manager import StructureManager
from cc3d_builder.injector.steppable_injector import SteppableInjector
from cc3d_builder.utils_extensions.rule_parsing import extract_celltypes_from_rule, extract_fields_from_rule


def process_and_inject_rule(project_path, registry, rule):
    print(f"\n--- 🕵️ DEBUG START: Processing Rule {rule.get('id')} ---")
    
    sub_params = registry.field_params.get('Substrate', {})
    print(f"STEP 1 [Pre-Inject Registry]: Substrate BC exists? {'YES' if sub_params.get('boundary_conditions') else 'NO'}")

    project_dir = Path(project_path).resolve()
    sm = StructureManager(str(project_dir))
    injector = SteppableInjector(str(project_dir))

    sm.ensure_from_rule(rule)

    # 1. Ensure all involved cell types are present in the Registry
    all_involved_types = extract_celltypes_from_rule(rule)
    for ct in all_involved_types:
        if ct not in registry.celltype_params:
            registry.add_celltype_params(ct, 50.0, 10.0)

    # ==========================================
    # 2. Extract Volume → generate (Python)
    # ==========================================
    legacy_volumes = sm.migrate_volume_data()

    for ct, params in legacy_volumes.items():
        if ct not in registry.celltype_params:
            registry.add_celltype_params(ct, params["targetVolume"], params["lambdaVolume"])

    sm.ensure_volume_plugin_empty()

    # ==========================================
    # 3. Extract Field → update → generate (XML)
    # ==========================================
    # Load the existing data from the XML into the Registry.
    legacy_fields = sm.migrate_field_data()

    legacy_sub = legacy_volumes.get('Substrate', {})
    print(f"STEP 2 [XML Migration]: Recovered Substrate BC from XML? {'YES' if legacy_sub.get('boundary_conditions') else 'NO'}")

    print(f"!!!!!  Legacy fields {legacy_fields}")
    for field_name, params in legacy_fields.items():
        registry.add_field_params(field_name, params)
    
    for k, v in legacy_fields.items():
        if k not in registry.field_params:
            registry.field_params[k] = v

    final_sub = registry.field_params.get('Substrate', {})
    print(f"STEP 3 [Pre-Write Registry]: Substrate BC still alive? {'YES' if final_sub.get('boundary_conditions') else 'NO'}")

    print(f"!!!!! After moving we got fields: {registry.field_params}")

    # Assume your rule includes chemotaxis or secretion logic; update registry.field_params here
    # For example:
    # if rule.get("behaviour") == "chemotaxis":
    #     field_name = rule["regulator"]
    #     target_cell = rule["target"]
    #     lambda_val = rule.get("lambda", 100.0)
    #     registry.add_chemotaxis_to_field(field_name, target_cell, lambda_val)

    sm.clear_field_and_related_plugins()
    # Regenerate the XML from the Registry after incorporating the newly added Rule data.
    sm.ensure_field_xml_from_registry(registry.field_params)

    print(f"--- 🕵️ DEBUG END ---\n")
    # ==========================================
    # 4. inject Python Steppables
    # ==========================================
    injector.ensure_dict_init()
    
    for ct, saved_params in registry.celltype_params.items():
        injector.ensure_volume_start_code(
            celltype_name=ct,
            target_volume=saved_params["targetVolume"],
            lambda_volume=saved_params["lambdaVolume"]
        )

    sm.save() 
    print(f"[Inject] Rule {rule.get('id', 'Unknown')} injected successfully.")

