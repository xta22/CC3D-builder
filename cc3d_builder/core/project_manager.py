# projecy_manager.py
import shutil
from pathlib import Path
from cc3d_builder.utils_extensions.rule_parsing import extract_celltypes_from_rule, extract_fields_from_rule
class ProjectManager: 
    def __init__(self, sandbox_path: Path):
        self.sandbox = sandbox_path

    def import_user_project(self, source_path):
            src = Path(source_path).resolve()
            # 确定沙盒内的 Simulation 目录
            dst_sim = self.sandbox / "Simulation"
            
            # 1. 清理旧沙盒
            if self.sandbox.exists():
                shutil.rmtree(self.sandbox)
            self.sandbox.mkdir(parents=True)
            dst_sim.mkdir()

            # 2. 精准提取
            # A. 拷贝 .cc3d 文件到 Rules_project 根目录
            cc3d_files = list(src.glob("*.cc3d"))
            for f in cc3d_files:
                shutil.copy2(f, self.sandbox / f.name)

            # B. 拷贝 Simulation 内部的 xml 和 python 文件
            src_sim = src / "Simulation"
            if src_sim.exists():
                for item in src_sim.iterdir():
                    if item.is_file() and item.suffix in ['.xml', '.py', '.json']:
                        shutil.copy2(item, dst_sim)
                    elif item.is_dir():
                        # 如果有子目录（如 config），也考过去
                        shutil.copytree(item, dst_sim / item.name)
            
            print(f"✅ 精准提取完成：{self.sandbox}")