# main.py

import sys, os

if __name__ == "__main__":
    
    project_path = input("Project path: ").strip()

    sim_path = os.path.join(project_path, "Simulation")
    if sim_path not in sys.path:
        sys.path.append(sim_path)

    from cli.cli_interface import cli_add_rule
    from registry.simulation_registry import SimulationRegistry
    from utils_extensions.utils import ask_celltype_params, handle_new_rule_registration

    registry = SimulationRegistry(project_path)
    registry.load()

    rule = cli_add_rule()

    try:
        handle_new_rule_registration(
            registry, 
            rule, 
            ask_celltype_params 
        )
        print("\nRule successfully added and injected ✔")
    except Exception as e:
        print(f"\n❌ Error during rule registration: {e}")