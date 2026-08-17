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
    write_dynamic_cc3d,
    write_dynamic_wrapper,
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
        write_dynamic_wrapper(self.sandbox, development_root=development_root)
        write_dynamic_cc3d(self.sandbox)

    def _reset_rules_json(self):
        """ clean JSON """
        json_path = self.sandbox / "Simulation" / "rules.json"
        json_path.write_text(
            '{"rules": [], "celltype_params": {}, "field_params": {}, "intracellular_models": [], '
            '"subcellular_systems": [], '
            '"settings": {"execution_semantics": "snapshot"}}'
        )
