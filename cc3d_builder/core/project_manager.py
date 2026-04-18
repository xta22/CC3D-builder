import shutil
from pathlib import Path

class ProjectManager:
    def __init__(self, sandbox_path: Path):
        self.sandbox = sandbox_path

    def import_user_project(self, user_xml_path: Path):
        """
        Copy the Simulation folder related to XML that user chooses
        """
        user_project_dir = user_xml_path.parent
        
        # 1. location of sandbox
        target_dir = self.sandbox / "Simulation"
        
        # 2. backup or clean old sandbox in case of pollution
        if target_dir.exists():
            shutil.rmtree(target_dir)
            
        # 3. copy the source document of users to RuleParser/Rules_project 
        shutil.copytree(user_project_dir, target_dir)
        
        print(f"✅ Project has been copied to：{target_dir}")
        # Modifications afterwards all targets at target_dir 