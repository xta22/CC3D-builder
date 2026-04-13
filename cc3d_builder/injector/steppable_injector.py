# steppable_injector.py

import os


class SteppableInjector:

    def __init__(self, project_path):
        self.project_path = project_path

        sim_dir = os.path.join(project_path, "Simulation")

        for fname in os.listdir(sim_dir):
            if fname.endswith("Steppables.py"):
                self.steppable_path = os.path.join(sim_dir, fname)
                break
        else:
            raise Exception("Steppables file not found")

    # =============================
    # FILE IO
    # =============================

    def _read_file(self):
        with open(self.steppable_path, "r") as f:
            return f.read()

    def _write_file(self, content):
        with open(self.steppable_path, "w") as f:
            f.write(content)

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
            raise Exception("Could not find start() function")

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