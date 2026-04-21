import shutil
from pathlib import Path

class ProjectManager: 
    def __init__(self, sandbox_path: Path):
        self.sandbox = sandbox_path
    
    def initialize_project(self, source_path: Path, is_import: bool = False):
        """
        called by CLI or GUI 
        """
        src = source_path.resolve()
        json_path = self.sandbox / "rules.json"

        if is_import:
            # Import new projects 
            print(f"🚀 Importing new project from: {src}")
            self._clear_and_copy_assets(src)
            # empty or reset json
            self._reset_rules_json()

        else:
            # Continue working on current sandbox 
            if json_path.exists():
                print("♻️ Resuming: Existing project and rules detected.")
            else:
                # local workspace but still would like to reset
                print("🐣 Initializing empty workspace...")
                self._reset_rules_json()


    def _clear_and_copy_assets(self, src: Path):
        """ move and reset XML and Steppable """

        # 1. XML 
        xml_files = list(src.rglob("*.xml"))
        if xml_files:
            shutil.copy2(xml_files[0], self.sandbox / "Rules_project.xml")

        # 2. Steppables
        py_files = list(src.rglob("*Steppables.py"))
        if py_files:
            shutil.copy2(py_files[0], self.sandbox / "Rules_project_Steppables.py")

    def _reset_rules_json(self):
        """ clean JSON """
        json_path = self.sandbox / "rules.json"
        json_path.write_text('{"rules": [], "celltype_params": {}, "field_params": {}}')
