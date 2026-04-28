# main.py
import sys
from pathlib import Path
from cc3d_builder.utils_extensions.paths import RULES_JSON, SIMULATION_DIR, SANDBOX_DIR
from cc3d_builder.cli.cli_interface import cli_add_rule, cli_import_csv
from cc3d_builder.engine.registry.simulation_registry import SimulationRegistry
from cc3d_builder.utils_extensions.utils import ask_params_cli, handle_new_rule_registration
from cc3d_builder.core.structure_manager import StructureManager
from cc3d_builder.core.project_manager import ProjectManager
from cc3d_builder.injector.steppable_injector import SteppableInjector


def main():    
    user_input = input("👉 Enter CC3D Project path (containing .cc3d): ").strip()
    user_project_path = Path(user_input)
    
    if not user_project_path.exists():
        print(f"❌ Error: Project path does not exist: {user_project_path}")
        return
    
    # Initialize ProjectManager
    # SANDBOX_DIR: "Rules_project" 
    pm = ProjectManager(SANDBOX_DIR)
    
    json_exists = (SANDBOX_DIR / "Simulation" / "rules.json").exists()
    
    if json_exists:
        print("\n⚠️  Existing rules detected in the sandbox!")
        choice = input("Do you want to [I]mport new (clear rules) or [R]esume editing? (I/R): ").strip().upper()
        
        if choice == 'I':
            pm.initialize_project(user_project_path, is_import=True)
            print("✅ New project imported. Rules have been reset.")
        else:
            pm.initialize_project(user_project_path, is_import=False)
            print("✅ Resuming... Existing rules preserved.")
    else:
        print("🐣 Initializing workspace for the first time...")
        pm.initialize_project(user_project_path, is_import=True)

    sm = StructureManager(SANDBOX_DIR)
    injector = SteppableInjector(SANDBOX_DIR)
    registry = SimulationRegistry(SANDBOX_DIR, structure_manager=sm)
    print(f"🔄 Loading registry from sandbox: {SANDBOX_DIR}")
    registry.load()

    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
        cli_import_csv(csv_file, registry, sm, injector)
        sys.exit(0) #Exit after import.

    rule = cli_add_rule(registry, sm, injector)

    if not rule:
        print("Operation cancelled.")
        return
    
    try:
        '''
        handle_new_rule_registration(
            registry, 
            rule, 
            ask_params_cli,
            sm,
            injector 
        )
        '''
        # registry.add_rule(rule)
        registry.save() # Rules_project/rules.json
        registry.export_to_xml() # Rules_project/Rules_project.xml
        print("✅ Rule successfully added and injected ✔")
        print(f"📍 Modified files are at: {SANDBOX_DIR}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ Error during rule registration: {e}")


if __name__ == "__main__":
    main()