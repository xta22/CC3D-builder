# main.py
import sys
from pathlib import Path
from cc3d_builder.utils_extensions.paths import RULES_JSON, SIMULATION_DIR, SANDBOX_DIR
from cc3d_builder.cli.cli_interface import cli_add_rule
from Rules_project.Simulation.registry.simulation_registry import SimulationRegistry
from cc3d_builder.utils_extensions.utils import ask_celltype_params, handle_new_rule_registration
from cc3d_builder.core.structure_manager import StructureManager
from cc3d_builder.core.project_manager import ProjectManager


def main():    
    user_input = input("Project path: ").strip()
    user_project_path = Path(user_input)

    if not user_project_path.exists():
        print(f"❌ Project path does not exist: {user_project_path}")
        return
    
    pm = ProjectManager(SANDBOX_DIR)
    pm.import_user_project(user_project_path)

    sm = StructureManager(SANDBOX_DIR)
    registry = SimulationRegistry(SANDBOX_DIR, structure_manager=sm)
    print(f"🔄 Loading registry from sandbox: {SANDBOX_DIR}")
    registry.load()

    rule = cli_add_rule()

    if not rule:
        print("Operation cancelled.")
        return

    try:
        handle_new_rule_registration(
            registry, 
            rule, 
            ask_celltype_params 
        )

        registry.add_rule(rule)
        registry.save() # Rules_project/Simulation/config/rules.json
        registry.export_to_xml() # Rules_project/Simulation/Rules_project.xml
        print("✅ Rule successfully added and injected ✔")
        print(f"📍 Modified files are at: {SANDBOX_DIR}")
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ Error during rule registration: {e}")


if __name__ == "__main__":
    main()