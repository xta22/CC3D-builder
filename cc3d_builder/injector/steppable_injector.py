# steppable_injector.py
from pathlib import Path

class SteppableInjector:

    def __init__(self, project_path):
        self.project_path = Path(project_path).resolve()
        sim_dir = self.project_path
        if not sim_dir.exists():
            raise Exception(f"Simulation directory not found at: {sim_dir}")
        steppable_files = list(sim_dir.glob("*Steppables.py"))
        if steppable_files:
            self.steppable_path = steppable_files[0]
        else:
            raise Exception(f"No Steppables.py file found in {sim_dir}")

    # =============================
    # FILE IO
    # =============================

    def _read_file(self):
        return self.steppable_path.read_text(encoding="utf-8")

    def _write_file(self, content):
        self.steppable_path.write_text(content, encoding="utf-8")

    # =============================
    # INSERT INTO start()
    # =============================

    def _insert_into_start(self, content, block_lines, marker):

        full_marker_start = f"# === {marker} START ==="
        if full_marker_start in content:
            print(f"[Injector] {marker} already exists")
            return content
        
        lines = content.splitlines()
        new_lines = []
        inserted = False

        for line in lines:

            new_lines.append(line)

            if line.strip().startswith("def start") and not inserted:

                base_indent = len(line) - len(line.lstrip())
                indent = " " * (base_indent + 4)

                new_lines.append(f"{indent}# === {marker} START ===")

                for bl in block_lines:
                    new_lines.append(indent + bl)

                new_lines.append(f"{indent}# === {marker} END ===")

                inserted = True

        if not inserted:
            print(f"⚠️ [Warning] Could not find start() function in {self.steppable_path.name}")
            return content
            
        return "\n".join(new_lines)

    # =============================
    # 1️⃣ initialize cell.dict
    # =============================

    def ensure_dict_init(self):

        content = self._read_file()
        block = [
            "for cell in self.cell_list:",
            "    if \"state\" not in cell.dict:",
            "        cell.dict[\"state\"] = {}",
            "        cell.dict[\"requests\"] = {}",
            "        cell.dict[\"_internal\"] = {}",
        ]

        new_content = self._insert_into_start(
            content,
            block,
            marker="CC3D_DICT_INIT"
        )

        self._write_file(new_content)

        print("[Injector] dict init ensured")

    # =============================
    # volume intialized
    # =============================

    def ensure_volume_start_code(self,
                                celltype_name,
                                target_volume,
                                lambda_volume):

        """
        Set initial volume constraint for "NewCell"
        """
        content = self._read_file()
        upper = celltype_name.upper()
        marker = f"CC3D_VOLUME_{upper}"

        block = [
            f"for cell in self.cell_list_by_type(self.{upper}):",
            f"    cell.targetVolume = {target_volume}",
            f"    cell.lambdaVolume = {lambda_volume}",
        ]

        new_content = self._insert_into_start(
            content,
            block,
            marker=marker
        )

        self._write_file(new_content)

        print(f"[Injector] Volume init ensured for {celltype_name}")

