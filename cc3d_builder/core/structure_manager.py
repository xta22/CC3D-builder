import xml.etree.ElementTree as ET
import random
from pathlib import Path 
# import os # only for compatibility of ElementTree.write

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
        self.project_path = Path(project_path) # Rules_project
        self.xml_path = self.project_path / "Simulation" /"Rules_project.xml"
        
        if not self.xml_path.exists():
            raise FileNotFoundError(f"❌ XML file not found at: {self.xml_path}. "
                                    "Make sure ProjectManager.import_user_project() runs first!")
        
        self.tree = ET.parse(str(self.xml_path))
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
        ''' 
        if the "NewCell" isnt in XML then assign an ID for it
        '''
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
    # FIELD
    # ============================================================

    def ensure_field(self, field_name, diff_const=0.1, decay_const=0.001):
        """
        confirm that field exists in xml
        """
        if not field_name or field_name == "None":
            return False

        # 1. Check or Create DiffusionSolver in "Steppable" Plugin in XML
        solver = self.root.find(".//Steppable[@Type='DiffusionSolverFE']")
        if solver is None:
            # solver framework
            return False

        # 2. check whether field exists
        for df in solver.findall("DiffusionField"):
            if df.attrib.get("Name") == field_name:
                return False

        # 3. create new field node
        new_field = ET.SubElement(solver, "DiffusionField")
        new_field.set("Name", field_name)
        
        diff_data = ET.SubElement(new_field, "DiffusionData")
        ET.SubElement(diff_data, "FieldName").text = field_name
        ET.SubElement(diff_data, "DiffusionConstant").text = str(diff_const)
        ET.SubElement(diff_data, "DecayConstant").text = str(decay_const)

        print(f"[StructureManager] Added DiffusionField: {field_name}")
        
        # 4. automatically add Chemotaxis placeholders for all CellTypes
        self._ensure_field_chemotaxis_placeholders(field_name)
        
        return True

    # ============================================================
    # CONTACT
    # ============================================================

    def _ensure_contact(self, name):

        contact_plugin = self.root.find(".//Plugin[@Name='Contact']")
        if contact_plugin is None:
            return

        celltype_plugin = self.root.find(".//Plugin[@Name='CellType']")
        if celltype_plugin is not None:
            all_types = [
                ct.attrib["TypeName"]
                for ct in celltype_plugin.findall("CellType")
            ]
        else: 
            all_types = []

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
        if potts is not None:

            dims = potts.find("Dimensions")
            if dims is not None:
                max_x = int(dims.attrib.get("x", 256))
                max_y = int(dims.attrib.get("y", 256))
                max_z = int(dims.attrib.get("z", 1))
            else:
                max_x, max_y, max_z = 256, 256, 1
        else: max_x, max_y, max_z = 256, 256, 1
        
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
            str(self.xml_path),
            encoding="utf-8",
            xml_declaration=False,
            short_empty_elements=False
        )

        print("✅[StructureManager] SAVE DONE")

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
        if potts is not None:
            dims = potts.find("Dimensions")
            if dims is not None:

                max_x = int(dims.attrib.get("x", 256))
                max_y = int(dims.attrib.get("y", 256))
                max_z = int(dims.attrib["z"])

            else:  max_x, max_y, max_z = 256, 256, 1
        else: max_x, max_y, max_z = 256, 256, 1
        
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

            # write into XML
            boxmin = ET.SubElement(region, "BoxMin")
            boxmin.set("x", str(x_min)); boxmin.set("y", str(y_min)); boxmin.set("z", "0")

            boxmax = ET.SubElement(region, "BoxMax")
            boxmax.set("x", str(x_max)); boxmax.set("y", str(y_max)); boxmax.set("z", "1")

            ET.SubElement(region, "Gap").text = "0"
            ET.SubElement(region, "Width").text = str(PATCH_SIZE)
            
            types = ET.SubElement(region, "Types")
            types.text = str(name).strip()

        self._indent(self.root)

    def get_xml_cell_types(self):
        """extract all TypeName from CellType Plugin in XML"""
        plugin = self.root.find(".//Plugin[@Name='CellType']")
        if plugin is None:
            return []
        
        # exclude Medium
        names = [
            ct.attrib.get("TypeName") 
            for ct in plugin.findall("CellType") 
            if (name := ct.attrib.get("TypeName")) and name.lower() != "medium"
        ]
        return names

    def _ensure_field_chemotaxis_placeholders(self, field_name):
        """
        “When a new Field is created, add Chemotaxis placeholders for all existing CellTypes in the XML.”
        """
        # 1. check or create Chemotaxis plugin
        chemotaxis_plugin = self.root.find(".//Plugin[@Name='Chemotaxis']")
        if chemotaxis_plugin is None:
            chemotaxis_plugin = ET.SubElement(self.root, "Plugin")
            chemotaxis_plugin.set("Name", "Chemotaxis")

        # 2. get all CellType defined in XML
        cell_type_plugin = self.root.find(".//Plugin[@Name='CellType']")
        if cell_type_plugin is None:
            print("No Celltypes has been detected.")
            return # theoretically should not happen

        all_types = [ct.attrib['TypeName'] for ct in cell_type_plugin.findall("CellType") 
                    if ct.attrib['TypeName'] != 'Medium']

        # 3. check if the field has its Diffusion Solver
        for t_name in all_types:
            
            found = False
            for cf_node in chemotaxis_plugin.findall("ChemicalField"):
                if cf_node.attrib.get("Name") == field_name:
                    # celltype configuration
                    for c_type in cf_node.findall("ChemotaxisByType"):
                        if c_type.attrib.get("Type") == t_name:
                            found = True
                            break
            
            if not found:
                cf_node = None
                for node in chemotaxis_plugin.findall("ChemicalField"):
                    if node.attrib.get("Name") == field_name:
                        cf_node = node
                        break
                
                if cf_node is None:
                    cf_node = ET.SubElement(chemotaxis_plugin, "ChemicalField")
                    cf_node.set("Name", field_name)
                
                # chemotaxis parameters
                chemo_by_type = ET.SubElement(cf_node, "ChemotaxisByType")
                chemo_by_type.set("Lambda", "0.0")
                chemo_by_type.set("Type", t_name)
                
                print(f"[StructureManager] Added Chemotaxis placeholder for {t_name} on field {field_name}")




       
                # if cell_widget and type_widget:
                #     self.field_data["Chemotaxis"].append({
                #         "CellType": cell_widget.currentText(),
                #         "Lambda": float(self.table_chemo.item(row, 1).text()),
                #         "Type": type_widget.currentText(),
                #         "SatCoef": float(self.table_chemo.item(row, 3).text())
                #     })
                    

    def migrate_field_data(self):
        """
        Extract DiffusionSolverFE and Chemotaxis Configuration from original XML
        {
            "Oxygen": {
                "GlobalDiffusionConstant": 0.9,
                "GlobalDecayConstant": 1e-05,
                "InitialConcentrationExpression": "x/100",
                "Chemotaxis": {"Cell": 1000.0}
            }
        }
        """
        fields_data = {}

        # ==========================================
        # 1. 提取 DiffusionSolverFE 参数
        # ==========================================
        diffusion_solver = self.root.find('.//Steppable[@Type="DiffusionSolverFE"]')
        if diffusion_solver is not None:
            for d_field in diffusion_solver.findall('DiffusionField'):
                field_name = d_field.get('Name')
                diff_data = d_field.find('DiffusionData')
                
                if field_name not in fields_data:
                    fields_data[field_name] = {}
                if diff_data is not None:
        
                    # 提取核心参数
                    g_diff = diff_data.findtext('GlobalDiffusionConstant')
                    g_decay = diff_data.findtext('GlobalDecayConstant')
                    init_expr = diff_data.findtext('InitialConcentrationExpression')

                    if g_diff: fields_data[field_name]['GlobalDiffusionConstant'] = float(g_diff)
                    if g_decay: fields_data[field_name]['GlobalDecayConstant'] = float(g_decay)
                    if init_expr: fields_data[field_name]['InitialConcentrationExpression'] = init_expr
                    
                # ===You can also add logic here to parse BoundaryConditions and CellType-specific coefficients.

        # ==========================================
        # 2. Extract chemo parameters and merge
        # ==========================================
        chemotaxis_plugin = self.root.find('.//Plugin[@Name="Chemotaxis"]')
        if chemotaxis_plugin is not None:
            for c_field in chemotaxis_plugin.findall('ChemicalField'):
                field_name = c_field.get('Name')
                
                if field_name not in fields_data:
                    fields_data[field_name] = {}
                
                if 'Chemotaxis' not in fields_data[field_name]:
                    fields_data[field_name]['Chemotaxis'] = {}

                for c_type in c_field.findall('ChemotaxisByType'):
                    cell_type = c_type.get('Type')
                    lambda_val = c_type.get('Lambda')
                    if cell_type and lambda_val:
                        fields_data[field_name]['Chemotaxis'][cell_type] = float(lambda_val)

        # ==========================================
        # 3. (可选) 提取 Secretion 参数并合并
        # ==========================================
        secretion_plugin = self.root.find('.//Plugin[@Name="Secretion"]')
        # ... 仿照上面的逻辑，如果 XML 里有 Secretion 标签，也合并到 fields_data 中 ...

        return fields_data
    
    def clear_field_and_related_plugins(self):
        """
        清空 XML 中的 DiffusionSolverFE、Chemotaxis 和 Secretion 节点。
        就像在画布上重新作画前，先把这几块区域擦干净。
        """
        cc3d_root = self.root  # 假设 self.root 是 <CompuCell3D> 根节点

        # 1. 揪出并删除所有的 DiffusionSolverFE 节点
        for solver in cc3d_root.findall('.//Steppable[@Type="DiffusionSolverFE"]'):
            cc3d_root.remove(solver)

        # 2. 揪出并删除所有的 Chemotaxis 插件
        for plugin in cc3d_root.findall('.//Plugin[@Name="Chemotaxis"]'):
            cc3d_root.remove(plugin)

        # 3. 揪出并删除所有的 Secretion 插件 (如果有的话)
        for plugin in cc3d_root.findall('.//Plugin[@Name="Secretion"]'):
            cc3d_root.remove(plugin)
            
        # 注意：这里我们不需要调用 self.save()，
        # 因为清空只是中间步骤，等后续重新生成完 XML 节点后，再统一 save。

    def ensure_field_xml_from_registry(self, field_params):
        """
        根据 Registry 中的 field_params 字典，从头生成纯净的 XML 节点。
        """
        print("🚨 BUILD XML CALLED")
        if not field_params:
            return  # 如果没有任何场数据，直接返回

        # ==========================================
        # 1. 重建 DiffusionSolverFE 节点
        # ==========================================
        # 创建 <Steppable Type="DiffusionSolverFE">
        solver_node = ET.SubElement(self.root, 'Steppable', attrib={'Type': 'DiffusionSolverFE'})
        
        has_chemotaxis = any(
            'chemotaxis' in p and p['chemotaxis']
            for p in field_params.values()
        )

        for field_name, params in field_params.items():
            print(f"DEBUG: Params for {field_name}: {params}")
            field_node = ET.SubElement(solver_node, 'DiffusionField', attrib={'Name': field_name})
            data_node = ET.SubElement(field_node, 'DiffusionData')
            
            ET.SubElement(data_node, 'FieldName').text = field_name
            
            # 🟢 使用 Registry 里的实际 Key 名
            if 'diffusion_constant' in params:
                ET.SubElement(data_node, 'GlobalDiffusionConstant').text = str(params['diffusion_constant'])
                
            if 'decay_constant' in params:
                ET.SubElement(data_node, 'GlobalDecayConstant').text = str(params['decay_constant'])
                
            if 'initial_expression' in params:
                ET.SubElement(data_node, 'InitialConcentrationExpression').text = str(params['initial_expression'])

            # Secretion through python?
            py_sec = params.get('python_secretion', False)
            if py_sec:
            # 如果是 Python 控制，XML 里的 DiffusionField 内部不写 SecretionData
            # 这样就相当于你说的 "删掉/Comment out"
                print(f"[SM] {field_name} uses Python secretion. Skipping XML SecretionData.")
            else:
                # 如果不是 Python 控制，则按原样写入 XML SecretionData
                if 'SecretionData' in params:
                    sec_data_node = ET.SubElement(field_node, 'SecretionData')
                    for ct_name, rate in params['SecretionData'].items():
                        sec_node = ET.SubElement(sec_data_node, 'Secretion', attrib={'Type': ct_name})
                        sec_node.text = str(rate)

            # 🟢 新增：处理 BoundaryConditions
            if 'boundary_conditions' in params and params['boundary_conditions']:
                bc_node = ET.SubElement(field_node, 'BoundaryConditions')
                
                for axis, config in params['boundary_conditions'].items():
                    plane_node = ET.SubElement(bc_node, 'Plane', attrib={'Axis': axis})
                    bc_type = config.get('type', 'ConstantValue')
                    print(f"DEBUG: Axis {axis} config: {config}")

                    if bc_type == "Periodic":
                        # 周期性边界不需要指定 Min/Max
                        ET.SubElement(plane_node, 'Periodic')
                    
                    elif bc_type == "ConstantValue":
                        # 固定值边界
                        ET.SubElement(plane_node, 'ConstantValue', attrib={
                            'PlanePosition': 'Min', 'Value': str(config.get('min_val', 0.0))
                        })
                        ET.SubElement(plane_node, 'ConstantValue', attrib={
                            'PlanePosition': 'Max', 'Value': str(config.get('max_val', 0.0))
                        })
                        
                    elif bc_type == "ConstantDerivative":
                        # 固定导数（冯·诺依曼边界）
                        ET.SubElement(plane_node, 'ConstantDerivative', attrib={
                            'PlanePosition': 'Min', 'Value': str(config.get('min_val', 0.0))
                        })
                        ET.SubElement(plane_node, 'ConstantDerivative', attrib={
                            'PlanePosition': 'Max', 'Value': str(config.get('max_val', 0.0))
                        })

        # 重建 Chemotaxis 插件节点
        if has_chemotaxis:
            chemo_plugin = ET.SubElement(self.root, 'Plugin', attrib={'Name': 'Chemotaxis'})

            # =========================
            # 3. 再遍历 fields
            # =========================
            for field_name, params in field_params.items():
                if 'chemotaxis' in params and params['chemotaxis']:

                    chem_field_node = ET.SubElement(
                        chemo_plugin, 'ChemicalField', attrib={'Name': field_name}
                    )

                    data = params['chemotaxis']

                    if isinstance(data, list):
                        for entry in data:
                            ET.SubElement(chem_field_node, 'ChemotaxisByType', attrib={
                                'Type': entry.get('CellType', 'Unknown'),
                                'Lambda': str(entry.get('Lambda', '0.0'))
                            })

                    elif isinstance(data, dict):
                        for cell_type, lambda_val in data.items():
                            ET.SubElement(chem_field_node, 'ChemotaxisByType', attrib={
                                'Type': cell_type,
                                'Lambda': str(lambda_val)
                            })

        # 🟢 关键：确保 Secretion Plugin 存在（用于 Python Secretor 初始化）
        # 只要有任何一个场开启了 Python Secretion，就必须有这个插件
        any_py_sec = any(p.get('python_secretion') for p in field_params.values())
        if any_py_sec:
            if self.root.find(".//Plugin[@Name='Secretion']") is None:
                ET.SubElement(self.root, 'Plugin', attrib={'Name': 'Secretion'})
                print("[SM] Added Secretion Plugin for Python support.")


        # ==========================================
        # 3. Secretion
        # ==========================================
                