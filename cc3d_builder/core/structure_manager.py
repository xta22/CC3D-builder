# structure_manager.py
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
        Scan JSON rules and automatically inject any missing XML plugins.
        """
        required_plugins = set()
        
        SHAPE_KEYWORDS = ["elongation", "eccentricity", "sphericity", "morphology"]

        for rule in rules_json_data.get("rules", []):
            when_config = rule.get("when", {})
            cond_type = str(when_config.get("condition_type", "")).lower()
       
            regulators = []
            cases = rule.get("cases", [])
            if cases:
                for case in cases:
                    reg = case.get("apply", {}).get("regulator")
                    if reg: regulators.append(str(reg).lower())
            else:
                reg = rule.get("apply", {}).get("regulator")
                if reg: regulators.append(str(reg).lower())

            if any(kw in cond_type for kw in SHAPE_KEYWORDS) or \
               any(any(kw in r for kw in SHAPE_KEYWORDS) for r in regulators):
                required_plugins.add("MomentOfInertia")

            # if "contact" in cond_type or any("contact" in r for r in regulators):
            #     required_plugins.add("Contact")

            if "neighbor" in cond_type or any("neighbor" in r for r in regulators):
                required_plugins.add("NeighborTracker")

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
            print(f"🧩 [Structure Manager] Logic scanned. Injected: {required_plugins}")

    def _ensure_plugin_exists(self, plugin_name):
        """
        Ensure that the plugin exists in the XML tree.
        """
        # avoid repeating
        for plugin_element in self.root.findall('Plugin'):
            if plugin_element.get('Name') == plugin_name:
                return False 

        print(f"✨ [Structure Manager] Adding lacking plugin to XML: <Plugin Name=\"{plugin_name}\"/>")
        new_plugin = ET.Element('Plugin', Name=plugin_name)
        
        # if plugin_name == "MomentOfInertia": pass

        self.root.insert(2, new_plugin)
        return True
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
        sync date between registry and xml
        """
        fields_data = {}

        # 1. Scan all DiffusionSolverFE nodes and handle duplicate node issues
        for solver in self.root.findall('.//Steppable[@Type="DiffusionSolverFE"]'):
            for d_field in solver.findall('DiffusionField'):
                f_name = d_field.get('Name')
                if not f_name: continue
                
                if f_name not in fields_data:
                    # initialize standard structure
                    fields_data[f_name] = {
                        "solver": "DiffusionSolverFE",
                        "diffusion_constant": 0.1,
                        "decay_constant": 0.0,
                        "initial_expression": "0.0",
                        "boundary_conditions": {},
                        "chemotaxis": [],
                        "python_secretion": False
                    }
                
                # extract PDE parameters
                d_data = d_field.find('DiffusionData')
                if d_data is not None:
                    fields_data[f_name]["diffusion_constant"] = float(d_data.findtext('GlobalDiffusionConstant') or 0.1)
                    fields_data[f_name]["decay_constant"] = float(d_data.findtext('GlobalDecayConstant') or 0.0)
                    fields_data[f_name]["initial_expression"] = d_data.findtext('InitialConcentrationExpression') or "0.0"

                # extract Boundary Conditions
                bc_node = d_field.find('BoundaryConditions')
                if bc_node is not None:
                    for plane in bc_node.findall('Plane'):
                        axis = plane.get('Axis')
                        # Periodic
                        if plane.find('Periodic') is not None:
                            fields_data[f_name]["boundary_conditions"][axis] = {"type": "Periodic"}
                        # ConstantValue / ConstantDerivative
                        else:
                            for val_type in ['ConstantValue', 'ConstantDerivative']:
                                node = plane.find(val_type)
                                if node is not None:
                                    fields_data[f_name]["boundary_conditions"][axis] = {
                                        "type": val_type,
                                        "min_val": float(node.get('Value') or 0.0),
                                        "max_val": float(node.get('Value') or 0.0) 
                                    }

        # 2. Extract Chemotaxis (output in list format)
        chem_plugin = self.root.find('.//Plugin[@Name="Chemotaxis"]')
        if chem_plugin is not None:
            for c_field in chem_plugin.findall('ChemicalField'):
                f_name = c_field.get('Name')
                if f_name in fields_data:
                    if not isinstance(fields_data[f_name]["chemotaxis"], list):
                        fields_data[f_name]["chemotaxis"] = []

                    for c_type in c_field.findall('ChemotaxisByType'):
                        mode = "simple"
                        sat_val = 0.0
                        
                        s_coef = c_type.get("SaturationCoef")
                        sl_coef = c_type.get("SaturationLinearCoef")
                        
                        if s_coef is not None:
                            mode = "saturation"
                            sat_val = float(s_coef)
                        elif sl_coef is not None:
                            mode = "saturation linear"
                            sat_val = float(sl_coef)

                        fields_data[f_name]["chemotaxis"].append({
                            "cell_type": c_type.get('Type', 'Unknown'),
                            "lambda": float(c_type.get('Lambda') or 0.0),
                            "mode": mode,
                            "sat_coef": sat_val
                        })

        return fields_data

    
    def clear_field_and_related_plugins(self):
        """
        Clear the DiffusionSolverFE, Chemotaxis, and Secretion nodes in the XML.
        """
        cc3d_root = self.root  # self.root is the root node of <CompuCell3D> 

        # Identify and remove all DiffusionSolverFE nodes.
        for solver in cc3d_root.findall('.//Steppable[@Type="DiffusionSolverFE"]'):
            cc3d_root.remove(solver)

        # Identify and remove all Chemotaxis plugins
        for plugin in cc3d_root.findall('.//Plugin[@Name="Chemotaxis"]'):
            cc3d_root.remove(plugin)

        # 3. Identify and remove all Secretion plugins(not added yet)
        for plugin in cc3d_root.findall('.//Plugin[@Name="Secretion"]'):
            cc3d_root.remove(plugin)
            
        # Save after regenerating the XML nodes later. No need to save here.

    def get_all_fields_from_xml(self):
        """
        Parse Rules_project.xml and extract all field parameters.
        """
        fields_data = {}
        
        # Use .// to ensure Steppables nested at any level can be found.
        steppables = self.root.findall('.//Steppable')
        
        for steppable in steppables:
            solver_type = steppable.get('Type')
            if solver_type and 'DiffusionSolver' in solver_type:
                fields = steppable.findall('DiffusionField')
                
                for field in fields:
                    f_name = field.get('Name')
                    if not f_name: continue
                    
                    # Initialize params dict
                    params = {
                        'solver': solver_type,
                        'diffusion_constant': 0.01,
                        'decay_constant': 0.0001,
                        'initial_expression': '0.0',
                        'python_secretion': False,
                        'boundary_conditions': {}
                    }
                    
                    # 1. Parse DiffusionData
                    diff_data = field.find('DiffusionData')
                    if diff_data is not None:
                        d_const = diff_data.find('DiffusionConstant') or diff_data.find('GlobalDiffusionConstant')
                        dy_const = diff_data.find('DecayConstant') or diff_data.find('GlobalDecayConstant')
                        init_expr = diff_data.find('InitialConcentrationExpression')
                        
                        if d_const is not None: params['diffusion_constant'] = float(d_const.text or 0.01)
                        if dy_const is not None: params['decay_constant'] = float(dy_const.text or 0.0001)
                        if init_expr is not None: params['initial_expression'] = init_expr.text or "0.0"

                    # 2. Parse BoundaryConditions 
                    bc_tag = field.find("BoundaryConditions")
                    if bc_tag is not None:
                        # address <Plane Axis="X"> 
                        planes = bc_tag.findall("Plane")
                        for p in planes:
                            axis_name = p.get("Axis") # get "X", "Y", or "Z"
                            if not axis_name: continue
                            
                            # initialize default data
                            axis_info = {'type': 'Periodic', 'min_val': 0.0, 'max_val': 0.0}
                            
                            # check the sub label <ConstantValue>, <ConstantDerivative>, <Periodic>
                            periodic = p.find("Periodic")
                            c_val = p.find("ConstantValue")
                            c_der = p.find("ConstantDerivative")
                            
                            if c_val is not None:
                                axis_info['type'] = 'ConstantValue'
                                axis_info['min_val'] = float(c_val.get('Value', 0.0)) if c_val.get('PlanePosition') == "Min" else axis_info['min_val']
                                
                                for cv in p.findall("ConstantValue"):
                                    if cv.get('PlanePosition') == "Min": axis_info['min_val'] = float(cv.get('Value', 0.0))
                                    if cv.get('PlanePosition') == "Max": axis_info['max_val'] = float(cv.get('Value', 0.0))
                            
                            elif c_der is not None:
                                axis_info['type'] = 'ConstantDerivative'
                                for cd in p.findall("ConstantDerivative"):
                                    if cd.get('PlanePosition') == "Min": axis_info['min_val'] = float(cd.get('Value', 0.0))
                                    if cd.get('PlanePosition') == "Max": axis_info['max_val'] = float(cd.get('Value', 0.0))
                            
                            elif periodic is not None:
                                axis_info['type'] = 'Periodic'

                            params['boundary_conditions'][axis_name] = axis_info
                    
                    params['chemotaxis'] = []
                    # Find the ChemicalField corresponding to the given field_name under the Plugin Chemotaxis.
                    chem_plugin = self.root.find(".//Plugin[@Name='Chemotaxis']")
                    if chem_plugin is not None:
                        cf_node = chem_plugin.find(f"ChemicalField[@Name='{f_name}']")
                        if cf_node is not None:
                            for entry in cf_node.findall("ChemotaxisByType"):
                                e_mode = "simple"
                                e_sat = "0.0"
                                
                                if "SaturationCoef" in entry.attrib:
                                    e_mode = "saturation"
                                    e_sat = entry.get("SaturationCoef")
                                elif "SaturationLinearCoef" in entry.attrib:
                                    e_mode = "saturation linear"
                                    e_sat = entry.get("SaturationLinearCoef")
                                    
                                params['chemotaxis'].append({
                                    "cell_type": entry.get("Type"),
                                    "lambda": entry.get("Lambda"),
                                    "mode": e_mode,
                                    "sat_coef": e_sat
                                })

                    fields_data[f_name] = params
                    print(f"📖 [XML Parser] Successfully recovered field: {f_name} (BC: {list(params['boundary_conditions'].keys())})")

        return fields_data


    def ensure_field_xml_from_registry(self, field_params):
        """
        Regenerate clean XML nodes from scratch based on the field_params dictionary in the Registry.
        """
        print("🚨 BUILD XML CALLED")
        if not field_params:
            return  
        for steppable in self.root.findall("Steppable[@Type='DiffusionSolverFE']"):
            self.root.remove(steppable)
        
        # # Locate the Chemotaxis plugin and clear it (keep the plugin shell, remove its contents)
        chemo_plugin = self.root.find(".//Plugin[@Name='Chemotaxis']")
        if chemo_plugin is not None:
            for child in list(chemo_plugin):
                chemo_plugin.remove(child)
        else:
            chemo_plugin = ET.SubElement(self.root, "Plugin", Name="Chemotaxis")

        # ==========================================
        # 1. Reconstruct DiffusionSolverFE Node
        # ==========================================
        # Construct <Steppable Type="DiffusionSolverFE">
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
            
            if 'diffusion_constant' in params:
                ET.SubElement(data_node, 'GlobalDiffusionConstant').text = str(params['diffusion_constant'])
                
            if 'decay_constant' in params:
                ET.SubElement(data_node, 'GlobalDecayConstant').text = str(params['decay_constant'])
                
            if 'initial_expression' in params:
                ET.SubElement(data_node, 'InitialConcentrationExpression').text = str(params['initial_expression'])

            # Secretion through python?
            py_sec = params.get('python_secretion', False)
            if py_sec:
                print(f"[SM] {field_name} uses Python secretion. Skipping XML SecretionData.")
            else:
                # If not controlled by Python, write SecretionData into the XML as-is
                if 'SecretionData' in params:
                    sec_data_node = ET.SubElement(field_node, 'SecretionData')
                    for ct_name, rate in params['SecretionData'].items():
                        sec_node = ET.SubElement(sec_data_node, 'Secretion', attrib={'Type': ct_name})
                        sec_node.text = str(rate)

            #  BoundaryConditions
            if 'boundary_conditions' in params and params['boundary_conditions']:
                bc_node = ET.SubElement(field_node, 'BoundaryConditions')
                
                for axis, config in params['boundary_conditions'].items():
                    plane_node = ET.SubElement(bc_node, 'Plane', attrib={'Axis': axis})
                    bc_type = config.get('type', 'ConstantValue')
                    print(f"DEBUG: Axis {axis} config: {config}")

                    if bc_type == "Periodic":
                        ET.SubElement(plane_node, 'Periodic')
                    
                    elif bc_type == "ConstantValue":
                        ET.SubElement(plane_node, 'ConstantValue', attrib={
                            'PlanePosition': 'Min', 'Value': str(config.get('min_val', 0.0))
                        })
                        ET.SubElement(plane_node, 'ConstantValue', attrib={
                            'PlanePosition': 'Max', 'Value': str(config.get('max_val', 0.0))
                        })
                        
                    elif bc_type == "ConstantDerivative":
                        ET.SubElement(plane_node, 'ConstantDerivative', attrib={
                            'PlanePosition': 'Min', 'Value': str(config.get('min_val', 0.0))
                        })
                        ET.SubElement(plane_node, 'ConstantDerivative', attrib={
                            'PlanePosition': 'Max', 'Value': str(config.get('max_val', 0.0))
                        })

        # Reconstrutct Chemotaxis plugin node
        if has_chemotaxis:
            chemo_plugin = self.root.find(".//Plugin[@Name='Chemotaxis']")
            if chemo_plugin is not None:
                for child in list(chemo_plugin):
                    chemo_plugin.remove(child)
            else:
                chemo_plugin = ET.SubElement(self.root, 'Plugin', attrib={'Name': 'Chemotaxis'})

            for field_name, params in field_params.items():
                chemo_data = params.get('chemotaxis', [])
                if not chemo_data: 
                    continue

                chem_field_node = ET.SubElement(chemo_plugin, 'ChemicalField', attrib={'Name': field_name})

                for entry in chemo_data:
                    if not isinstance(entry, dict):
                        print(f"⚠️ [SM] Skipping invalid chemotaxis entry: {entry} (type: {type(entry)})")
                        continue
                    c_type = entry.get('cell_type') or entry.get('CellType', 'Unknown')
                    
                    raw_lambda = entry.get('lambda') or entry.get('Lambda', '0.0')
                    l_val = str(float(raw_lambda)) if raw_lambda is not None else "0.0"
                    
                    mode = str(entry.get('mode') or entry.get('Mode', 'simple')).lower()
                    
                    raw_sat = entry.get('sat_coef') or entry.get('SatCoef', '0.0')
                    s_coef = str(float(raw_sat)) if raw_sat is not None else "0.0"

                    attribs = {
                        'Type': str(c_type),
                        'Lambda': l_val
                    }

                    # 2. Determine the tag based on the mode.
                    if mode == "saturation":
                        attribs['SaturationCoef'] = s_coef
                    elif mode == "saturation linear":
                        attribs['SaturationLinearCoef'] = s_coef

                    ET.SubElement(chem_field_node, 'ChemotaxisByType', attrib=attribs)

        # If any field has Python-based secretion enabled, this plugin must be present.
        any_py_sec = any(p.get('python_secretion') for p in field_params.values())
        if any_py_sec:
            if self.root.find(".//Plugin[@Name='Secretion']") is None:
                ET.SubElement(self.root, 'Plugin', attrib={'Name': 'Secretion'})
                print("[SM] Added Secretion Plugin for Python support.")


        # ==========================================
        # 3. Secretion
        # ==========================================
                