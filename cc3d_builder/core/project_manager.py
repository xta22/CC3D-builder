# projecy_manager.py
import shutil
from pathlib import Path
from cc3d_builder.utils_extensions.rule_parsing import extract_celltypes_from_rule, extract_fields_from_rule
class ProjectManager: 
    def __init__(self, sandbox_path: Path):
        self.sandbox = sandbox_path

    def import_user_project(self, source_path):
        src = Path(source_path).resolve()
        
        # 1. 清理旧沙盒
        if self.sandbox.exists():
            shutil.rmtree(self.sandbox)
        self.sandbox.mkdir(parents=True)

        # 1. 提取 XML 并重命名到根目录
        xml_file = list(src.rglob("*.xml"))[0] # 使用 rglob 自动深搜
        shutil.copy2(xml_file, self.sandbox/ "Rules_project.xml")

        # 2. 提取 Python Steppable 并重命名到根目录
        py_file = list(src.rglob("*Steppables.py"))[0]
        shutil.copy2(py_file, self.sandbox / "Rules_project_Steppables.py")

        # 3. 提取或初始化 JSON 到根目录
        src_json = list(src.rglob("rules.json"))
        if src_json:
            shutil.copy2(src_json[0], self.sandbox / "rules.json")
        else:
            # 如果用户项目没这个文件，创建一个空的
            (self.sandbox / "rules.json").write_text('{"rules": [], "celltype_params": {}}')