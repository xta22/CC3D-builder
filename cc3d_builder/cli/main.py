# cli/main.py
import sys
from pathlib import Path
from cc3d_builder.core.state_key_catalog import (
    format_state_key_catalog,
    format_state_key_catalog_page,
    state_key_catalog_pages,
)


def _format_names(names):
    cleaned = [str(name) for name in names or [] if str(name)]
    return ", ".join(cleaned) if cleaned else "none"


def _print_registration_report(rule, registration_summary, artifact_summary, sandbox_dir):
    print("\n=== RuleParser Commit Summary ===")
    print(f"Rule: {rule.get('id')} ({rule.get('behaviour')})")
    print(f"Rules in project: {artifact_summary.get('rule_count', 0)}")
    print(f"Cell types added: {_format_names(registration_summary.get('new_celltypes'))}")
    print(f"Cell types reused: {_format_names(registration_summary.get('reused_celltypes'))}")
    print(f"Fields added: {_format_names(registration_summary.get('new_fields'))}")
    print(f"Fields reused: {_format_names(registration_summary.get('reused_fields'))}")
    print(f"XML updated: {'yes' if artifact_summary.get('xml_updated') else 'no'}")
    print(f"Steppable volume init synced: {'yes' if artifact_summary.get('volume_markers_synced') else 'no'}")
    print(f"Generated code: {'yes' if artifact_summary.get('code_generated') else 'no'}")
    print(f"Project profile synced: {'yes' if artifact_summary.get('profile_synced') else 'no'}")
    print(f"Source project artifacts synced: {'yes' if artifact_summary.get('source_artifacts_synced') else 'no'}")
    if artifact_summary.get("generator_error"):
        print(f"Generator error: {artifact_summary['generator_error']}")
    if artifact_summary.get("source_artifact_error"):
        print(f"Source artifact sync error: {artifact_summary['source_artifact_error']}")
    print(f"Modified files are at: {sandbox_dir}")


def _print_artifact_report(title, artifact_summary, sandbox_dir):
    print(f"\n=== {title} ===")
    print(f"Rules in project: {artifact_summary.get('rule_count', 0)}")
    print(f"XML updated: {'yes' if artifact_summary.get('xml_updated') else 'no'}")
    print(f"Steppable volume init synced: {'yes' if artifact_summary.get('volume_markers_synced') else 'no'}")
    print(f"Generated code: {'yes' if artifact_summary.get('code_generated') else 'no'}")
    print(f"Project profile synced: {'yes' if artifact_summary.get('profile_synced') else 'no'}")
    print(f"Source project artifacts synced: {'yes' if artifact_summary.get('source_artifacts_synced') else 'no'}")
    if artifact_summary.get("generator_error"):
        print(f"Generator error: {artifact_summary['generator_error']}")
    if artifact_summary.get("source_artifact_error"):
        print(f"Source artifact sync error: {artifact_summary['source_artifact_error']}")
    print(f"Modified files are at: {sandbox_dir}")


def _choose_cli_action():
    print("\nAction:")
    print("  1 - Add rule")
    print("  2 - Manage intracellular models")
    print("  3 - Manage subcellular systems")
    print("  4 - Rebuild/commit artifacts")
    print("  5 - Exit")
    return input("Choice [1]: ").strip() or "1"


def _browse_state_key_catalog():
    pages = state_key_catalog_pages()
    page_index = 0

    while True:
        print()
        print(format_state_key_catalog_page(page_index))
        print()
        command = input("[Enter/n] next, [p] previous, [page number] jump, [a] all, [q] quit: ").strip().lower()

        if command in {"q", "quit", "exit"}:
            return
        if command in {"a", "all"}:
            print()
            print(format_state_key_catalog())
            return
        if command in {"", "n", "next"}:
            if page_index < len(pages) - 1:
                page_index += 1
            else:
                print("Already at the last page.")
            continue
        if command in {"p", "prev", "previous"}:
            if page_index > 0:
                page_index -= 1
            else:
                print("Already at the first page.")
            continue
        if command.isdigit():
            requested = int(command)
            if 1 <= requested <= len(pages):
                page_index = requested - 1
            else:
                print(f"Page must be between 1 and {len(pages)}.")
            continue

        print("Unknown command.")


def main():
    args = sys.argv[1:]

    if args and args[0] in {"--state-keys", "state-keys", "--list-state-keys"}:
        if "--all" in args[1:] or not sys.stdin.isatty():
            print(format_state_key_catalog())
        else:
            _browse_state_key_catalog()
        return

    execution_semantics = None
    remaining_args = []
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg.startswith("--execution-semantics="):
            execution_semantics = arg.split("=", 1)[1]
        elif arg == "--execution-semantics":
            idx += 1
            if idx >= len(args):
                print("❌ --execution-semantics requires: snapshot or asynchronous")
                return
            execution_semantics = args[idx]
        else:
            remaining_args.append(arg)
        idx += 1

    from cc3d_builder.utils_extensions.paths import SANDBOX_DIR
    from cc3d_builder.cli.cli_interface import (
        cli_add_rule,
        cli_import_csv,
        cli_manage_intracellular_models,
        cli_manage_subcellular_systems,
    )
    from cc3d_builder.engine.registry.simulation_registry import SimulationRegistry
    from cc3d_builder.core.structure_manager import StructureManager
    from cc3d_builder.core.project_manager import ProjectManager
    from cc3d_builder.core.project_profile import has_project_profile
    from cc3d_builder.injector.steppable_injector import SteppableInjector

    while True:
        raw_input = input("👉 Enter CC3D Project path (containing .cc3d): ").strip()

        if not raw_input:
            print("⚠️  Input is empty. Please provide a valid path.")
            continue

        user_input = raw_input.replace('"', '').replace("'", "").replace('\\ ', ' ')

        user_project_path = Path(user_input).expanduser().resolve()

        if user_project_path.exists():
            has_cc3d = any(user_project_path.glob("*.cc3d"))
            if not has_cc3d:
                print(f"❓ Warning: No .cc3d file found in {user_project_path}")

            print(f"📂 Resolved path: '{user_project_path}'")
            break
        else:
            print(f"❌ Error: Path does not exist: {user_project_path}")
    # Initialize ProjectManager
    # SANDBOX_DIR: "Rules_project"
    pm = ProjectManager(SANDBOX_DIR)

    json_exists = (SANDBOX_DIR / "Simulation" / "rules.json").exists()
    profile_exists = has_project_profile(user_project_path)

    if json_exists or profile_exists:
        print("\n⚠️  Existing rules/profile detected!")
        if profile_exists:
            print(f"📌 Project profile found: {user_project_path / '.ruleparser' / 'rules.json'}")
        choice = input("Do you want to [I]mport new (clear project rules) or [R]esume project rules? (I/R): ").strip().upper()

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

    if execution_semantics:
        normalized = execution_semantics.strip().lower()
        aliases = {"async": "asynchronous"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"snapshot", "asynchronous"}:
            print(f"❌ Unknown execution semantics: {execution_semantics}")
            return
        registry.settings["execution_semantics"] = normalized
        registry.commit_artifacts(quiet=True)
        print(f"✅ Execution semantics set to: {normalized}")

    if remaining_args:
        csv_file = remaining_args[0]
        cli_import_csv(csv_file, registry, sm, injector)
        sys.exit(0) #Exit after import.

    while True:
        action = _choose_cli_action()

        if action == "1":
            rule = cli_add_rule(registry, sm, injector)

            if not rule:
                print("Operation cancelled.")
                return

            try:
                artifact_summary = registry.commit_artifacts(quiet=True)
                registration_summary = getattr(registry, "last_registration_summary", {}) or {}
                _print_registration_report(rule, registration_summary, artifact_summary, SANDBOX_DIR)
                return

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"\n❌ Error during rule registration: {e}")
                return

        if action == "2":
            changed = cli_manage_intracellular_models(registry)
            if changed:
                summary = registry.commit_artifacts(quiet=True)
                _print_artifact_report("Intracellular Model Registry Commit Summary", summary, SANDBOX_DIR)
            continue

        if action == "3":
            changed = cli_manage_subcellular_systems(registry)
            if changed:
                summary = registry.commit_artifacts(quiet=True)
                _print_artifact_report("Subcellular System Registry Commit Summary", summary, SANDBOX_DIR)
            continue

        if action == "4":
            summary = registry.commit_artifacts(quiet=True)
            _print_artifact_report("RuleParser Commit Summary", summary, SANDBOX_DIR)
            continue

        if action == "5":
            return

        print("Invalid action.")


if __name__ == "__main__":
    main()
