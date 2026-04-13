import os
import xml.etree.ElementTree as ET
import random


class StructureManager:
    DEPENDENCY_MAP = {
        "topology/contact_ratio.py": ["NeighborTracker"],
        "topology/distance.py": ["CenterOfMass"],
        "morphology/is_elongated.py": ["Surface", "Volume"],
        "morphology/specific_surface.py": ["Surface", "Volume"],
        "morphology/elongation.py": ["MomentOfInertia"],
        # future registered new conditions would be added here.
    }
    def __init__(self, project_path):
        self.project_path = project_path
        self.xml_path = os.path.join(
            project_path,
            "Simulation",
            os.path.basename(project_path) + ".xml"
        )

        self.tree = ET.parse(self.xml_path)
        self.root = self.tree.getroot()

        self._seen_celltypes = set()

    def check_and_inject_dependencies(self, rules_json_data):
        """
        screen JSON dictionaries and inject lacking plugins to xmls
        """
        required_plugins = set()

        for rule in rules_json_data.get("rules", []):
            when_config = rule.get("when", {})
            if when_config.get("type") == "custom_condition":
                script = when_config.get("script_path", "")
                if script in self.DEPENDENCY_MAP:
                    required_plugins.update(self.DEPENDENCY_MAP[script])
            
            if rule.get("behaviour") == "custom":
                script = rule.get("script_path", "")
                if script in self.DEPENDENCY_MAP:
                    required_plugins.update(self.DEPENDENCY_MAP[script])

        modified = False
        for plugin_name in required_plugins:
            if self._ensure_plugin_exists(plugin_name):
                modified = True
                
        if modified:
            self.save()


    def _ensure_plugin_exists(self, plugin_name):
        """
        """
        for plugin_element in self.root.findall('Plugin'):
            if plugin_element.get('Name') == plugin_name:
                return False 

        print(f"🧩 [Structure Manager] inject lacking plugins: <Plugin Name=\"{plugin_name}\"/>")
        new_plugin = ET.Element('Plugin', Name=plugin_name)
        
        self.root.append(new_plugin)
        return True # DOM tree is modified
    # ============================================================
    # ENTRY POINT inject rule
    # ============================================================

    def ensure_from_rule(self, rule):
        self._scan_all(rule)
        self.save()
        print("[StructureManager] XML updated safely.")

    def _scan_all(self, rule):

        stack = [rule]

        while stack:
            current = stack.pop()

            if isinstance(current, dict):
                for k, v in current.items():
                                   
                    if k == "target" and isinstance(v, str):
                        if v.lower() not in ["none", ""]:
                            self.ensure_celltype(v)

                    elif k.endswith("_type") and k != "condition_type" and isinstance(v, str):
                        if v.lower() not in ["field", "celltype"]: 
                            self.ensure_celltype(v)

                    stack.append(v)

            elif isinstance(current, list):
                for item in current:
                    stack.append(item)


    # ============================================================
    # VOLUME PLUGIN MANAGEMENT
    # ============================================================

    def ensure_volume_plugin_empty(self):
        
        # current volume plugin
        plugin = self.root.find(".//Plugin[@Name='Volume']")
        
        if plugin is not None:
            # clean<VolumeEnergyParameters ... />)
            for child in list(plugin):
                plugin.remove(child)
            print("[StructureManager] Volume plugin cleared for Python control.")
        else:
            plugin = ET.SubElement(self.root, "Plugin")
            plugin.set("Name", "Volume")
            print("[StructureManager] Empty Volume plugin added for Python control.")
            
        self.save()
    # ============================================================
    # CELLTYPE
    # ============================================================

    def ensure_celltype(self, name):
        if not name:
            return False

        if name in self._seen_celltypes:
            return False
        self._seen_celltypes.add(name)

        plugin = self.root.find(".//Plugin[@Name='CellType']")
        if plugin is None:
            return False

        for ct in plugin.findall("CellType"):
            if ct.attrib.get("TypeName") == name:
                return False

        ids = [
            int(ct.attrib.get("TypeId", "0"))
            for ct in plugin.findall("CellType")
        ]

        new_id = max(ids) + 1 if ids else 1

        new_cell = ET.SubElement(plugin, "CellType")
        new_cell.set("TypeName", name)
        new_cell.set("TypeId", str(new_id))

        print(f"[StructureManager] Added CellType: {name}")

        self._ensure_contact(name)
        self._ensure_initializer(name)

        return True

    # ============================================================
    # CONTACT
    # ============================================================

    def _ensure_contact(self, name):

        contact_plugin = self.root.find(".//Plugin[@Name='Contact']")
        if contact_plugin is None:
            return

        celltype_plugin = self.root.find(".//Plugin[@Name='CellType']")
        all_types = [
            ct.attrib["TypeName"]
            for ct in celltype_plugin.findall("CellType")
        ]

        existing_pairs = set()

        for energy in contact_plugin.findall("Energy"):
            t1 = energy.attrib["Type1"]
            t2 = energy.attrib["Type2"]
            existing_pairs.add(tuple(sorted([t1, t2])))

        for t in all_types:

            key = tuple(sorted([name, t]))

            if key not in existing_pairs:

                e = ET.SubElement(contact_plugin, "Energy")
                e.set("Type1", key[0])
                e.set("Type2", key[1])
                e.text = "10.0"

    # ============================================================
    # INITIALIZER
    # ============================================================

    def _ensure_initializer(self, name):

        init = self.root.find(".//Steppable[@Type='UniformInitializer']")
        if init is None:
            return

        potts = self.root.find(".//Potts")
        dims = potts.find("Dimensions")

        max_x = int(dims.attrib["x"])
        max_y = int(dims.attrib["y"])
        max_z = int(dims.attrib["z"])

        PATCH_SIZE = 5
        MARGIN = 5

        x_min = random.randint(MARGIN, max_x - PATCH_SIZE - MARGIN)
        y_min = random.randint(MARGIN, max_y - PATCH_SIZE - MARGIN)

        x_max = x_min + PATCH_SIZE
        y_max = y_min + PATCH_SIZE

        region = ET.SubElement(init, "Region")

        boxmin = ET.SubElement(region, "BoxMin")
        boxmin.set("x", str(x_min))
        boxmin.set("y", str(y_min))
        boxmin.set("z", "0")

        boxmax = ET.SubElement(region, "BoxMax")
        boxmax.set("x", str(x_max))
        boxmax.set("y", str(y_max))
        boxmax.set("z", str(max_z))

        ET.SubElement(region, "Gap").text = "0"
        ET.SubElement(region, "Width").text = str(PATCH_SIZE)

        types = ET.SubElement(region, "Types")
        types.text = name

    # ============================================================
    # SAVE to XML
    # ============================================================

    def save(self):
        print("SAVING TO:", self.xml_path)

        try:
            ET.indent(self.tree, space="    ", level=0)
        except AttributeError:
            self._indent(self.root, 0)

        self.tree.write(
            self.xml_path,
            encoding="utf-8",
            xml_declaration=False,
            short_empty_elements=False
        )

        print("SAVE DONE")

    def _indent(self, elem, level=0):
        indent_str = "\n" + level * "    "

        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent_str + "    "

            for child in elem:
                self._indent(child, level + 1)

            if not elem.tail or not elem.tail.strip():
                elem.tail = indent_str
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent_str

    # structure_manager.py

    def migrate_volume_data(self):
        """
        read all old data before clean
        return: { "OldCellType": {"targetVolume": 50, "lambdaVolume": 2}, ... }
        """
        old_volumes = {}
        plugin = self.root.find(".//Plugin[@Name='Volume']")
        
        if plugin is not None:
            # find all<VolumeEnergyParameters ... />
            for param in plugin.findall("VolumeEnergyParameters"):
                ct_name = param.attrib.get("CellType")
                target = param.attrib.get("TargetVolume")
                lam = param.attrib.get("LambdaVolume")
                
                if ct_name and target and lam:
                    old_volumes[ct_name] = {
                        "targetVolume": float(target),
                        "lambdaVolume": float(lam)
                    }
        return old_volumes

    def update_initializers(self, active_cells_config):
        initializer = self.root.find(".//Steppable[@Type='UniformInitializer']")
        if initializer is None:
            initializer = ET.SubElement(self.root, "Steppable", {"Type": "UniformInitializer"})
        else:
            # clear the old, unticked cell types
            for region in list(initializer.findall("Region")):
                initializer.remove(region)

        # retrieve the map size
        potts = self.root.find(".//Potts")
        dims = potts.find("Dimensions")
        max_x = int(dims.attrib["x"])
        max_y = int(dims.attrib["y"])
        max_z = int(dims.attrib["z"])

        PATCH_SIZE = 5
        MARGIN = 10 # incase out of boundary 

        for name, count in active_cells_config.items():
            region = ET.SubElement(initializer, "Region")

            current_count = int(count)
            side_length = int((current_count ** 0.5) * PATCH_SIZE) + 2 
            
            x_min = random.randint(10, max_x - side_length - 10)
            y_min = random.randint(10, max_y - side_length - 10)
            x_max = x_min + side_length
            y_max = y_min + side_length

            # 写入 XML
            boxmin = ET.SubElement(region, "BoxMin")
            boxmin.set("x", str(x_min)); boxmin.set("y", str(y_min)); boxmin.set("z", "0")

            boxmax = ET.SubElement(region, "BoxMax")
            boxmax.set("x", str(x_max)); boxmax.set("y", str(y_max)); boxmax.set("z", "1")

            ET.SubElement(region, "Gap").text = "0"
            ET.SubElement(region, "Width").text = str(PATCH_SIZE)
            
            types = ET.SubElement(region, "Types")
            types.text = str(name).strip()

        self._indent(self.root)