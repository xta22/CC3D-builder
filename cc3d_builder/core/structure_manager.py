# structure_manager.py
import xml.etree.ElementTree as ET
import random
from pathlib import Path 
from cc3d_builder.core.rule_schema import case_payload
# import os # only for compatibility of ElementTree.write


def _collect_regulators(value, target):
    if isinstance(value, dict):
        reg = value.get("regulator")
        if isinstance(reg, list):
            target.extend(str(item).lower() for item in reg)
        elif reg:
            target.append(str(reg).lower())
        for item in value.values():
            _collect_regulators(item, target)
    elif isinstance(value, list):
        for item in value:
            _collect_regulators(item, target)

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
        uses_rule_compartmentalize = False
        
        SHAPE_KEYWORDS = ["elongation", "eccentricity", "sphericity", "morphology"]

        for rule in rules_json_data.get("rules", []):
            regulators = []
            condition_types = []
            behaviour = rule.get("behaviour")

            if behaviour == "force":
                required_plugins.add("ExternalPotential")

            if behaviour == "compartmentalize":
                required_plugins.add("ContactInternal")
                uses_rule_compartmentalize = True

            if behaviour == "fpp_link":
                required_plugins.add("FocalPointPlasticity")

            if behaviour == "secrete/uptake":
                required_plugins.add("Secretion")

            for case in rule.get("cases", []):
                when_config = case.get("when", {})
                condition_type = str(when_config.get("condition_type", "")).lower()
                condition_types.append(condition_type)
                when_params = when_config.get("params", {}) if isinstance(when_config, dict) else {}

                if condition_type == "environment":
                    sampling_mode = str(
                        when_params.get("sampling_mode", when_params.get("environment_mode", "com"))
                    ).strip().lower()
                    if sampling_mode.startswith(("cell_", "boundary_", "contact_boundary_")):
                        required_plugins.add("PixelTracker")
                    _collect_regulators(when_params, regulators)

                payload = case_payload(case)
                _collect_regulators(payload, regulators)

                if behaviour == "compartmentalize" and (
                    str(payload.get("use_fpp_link", "")).lower() in {"1", "true", "yes", "y", "on"}
                    or str(payload.get("visualize_fpp_link", "")).lower() in {"1", "true", "yes", "y", "on"}
                ):
                    required_plugins.add("FocalPointPlasticity")

                if when_config.get("type") == "custom_condition":
                    script = when_config.get("script_path", "")
                    if script in self.DEPENDENCY_MAP:
                        required_plugins.update(self.DEPENDENCY_MAP[script])

                if behaviour == "custom_script":
                    script = payload.get("script_path", "")
                    if script in self.DEPENDENCY_MAP:
                        required_plugins.update(self.DEPENDENCY_MAP[script])

            if any(any(kw in cond for kw in SHAPE_KEYWORDS) for cond in condition_types) or \
               any(any(kw in r for kw in SHAPE_KEYWORDS) for r in regulators):
                required_plugins.add("MomentOfInertia")

            # if "contact" in cond_type or any("contact" in r for r in regulators):
            #     required_plugins.add("Contact")

            if any("neighbor" in cond for cond in condition_types) or any("neighbor" in r for r in regulators):
                required_plugins.add("NeighborTracker")

        modified = False
        if uses_rule_compartmentalize:
            for plugin in list(self.root.findall(".//Plugin[@Name='ContactCompartment']")):
                self.root.remove(plugin)
                modified = True

        for plugin_name in required_plugins:
            if self._ensure_plugin_exists(plugin_name):
                modified = True

        if self.ensure_contact_internal_from_rules(rules_json_data):
            modified = True

        if self.ensure_fpp_from_rules(rules_json_data):
            modified = True

        if self.normalize_core_plugin_order():
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

    def normalize_core_plugin_order(self):
        """
        Keep CellType before plugins that resolve type names during native init.
        """
        celltype = self.root.find("./Plugin[@Name='CellType']")
        if celltype is None:
            return False

        children = list(self.root)
        current_index = children.index(celltype)

        insert_index = 0
        for idx, child in enumerate(children):
            if child.tag in {"Metadata", "Potts"}:
                insert_index = idx + 1

        if current_index == insert_index:
            return False

        self.root.remove(celltype)
        self.root.insert(insert_index, celltype)
        return True

    def ensure_contact_internal_from_rules(self, rules_json_data):
        """
        Populate ContactInternal parameters implied by compartmentalize rules.

        Dependency scanning adds the plugin shell. This method fills the shell with
        the internal contact pairs needed to keep tip/segment compartment chains
        coherent without requiring manual XML edits.
        """
        specs, neighbor_order, managed_pairs = self._contact_internal_specs_from_rules(rules_json_data)
        if not specs and not managed_pairs:
            return False

        plugin = self.root.find(".//Plugin[@Name='ContactInternal']")
        if plugin is None:
            if not specs:
                return False
            self._ensure_plugin_exists("ContactInternal")
            plugin = self.root.find(".//Plugin[@Name='ContactInternal']")
            if plugin is None:
                return False

        modified = False
        existing_pairs = {}
        for energy in plugin.findall("Energy"):
            t1 = energy.attrib.get("Type1")
            t2 = energy.attrib.get("Type2")
            if t1 and t2:
                existing_pairs[tuple(sorted([t1, t2]))] = energy

        if self._remove_stale_contact_internal_nodes(plugin, specs, managed_pairs):
            modified = True

        for pair, spec in specs.items():
            t1, t2 = pair
            if not t1 or not t2:
                continue

            energy_value = spec["energy"]
            explicit_energy = spec["explicit_energy"]
            energy_node = existing_pairs.get(pair)

            if energy_node is None:
                energy_node = ET.SubElement(plugin, "Energy")
                energy_node.set("Type1", t1)
                energy_node.set("Type2", t2)
                energy_node.text = self._xml_number(energy_value)
                existing_pairs[pair] = energy_node
                modified = True
            elif explicit_energy:
                new_text = self._xml_number(energy_value)
                if (energy_node.text or "").strip() != new_text:
                    energy_node.text = new_text
                    modified = True

        neighbor_node = plugin.find("NeighborOrder")
        neighbor_text = str(int(neighbor_order))
        if neighbor_node is None:
            ET.SubElement(plugin, "NeighborOrder").text = neighbor_text
            modified = True
        elif not (neighbor_node.text or "").strip():
            neighbor_node.text = neighbor_text
            modified = True

        return modified

    def ensure_fpp_from_rules(self, rules_json_data):
        """
        Populate FocalPointPlasticity parameters implied by compartmentalize and fpp_link rules.

        Internal compartment chains use InternalParameters plus runtime
        new_fpp_internal_link(...). Optional visualize_fpp_link adds ordinary
        Parameters plus runtime new_fpp_link(...) so Player can display FPP links.
        Independent fpp_link rules always use ordinary Parameters plus
        runtime new_fpp_link(...).
        """
        (
            internal_specs,
            visual_specs,
            neighbor_order,
            managed_internal_pairs,
            managed_visual_pairs,
        ) = self._fpp_specs_from_rules(rules_json_data)
        if not internal_specs and not visual_specs and not managed_internal_pairs and not managed_visual_pairs:
            return False

        plugin = self.root.find(".//Plugin[@Name='FocalPointPlasticity']")
        if plugin is None:
            if not internal_specs and not visual_specs:
                return False
            self._ensure_plugin_exists("FocalPointPlasticity")
            plugin = self.root.find(".//Plugin[@Name='FocalPointPlasticity']")
            if plugin is None:
                return False

        modified = False

        if plugin.find("Local") is None:
            plugin.insert(0, ET.Element("Local"))
            modified = True

        if self._remove_stale_fpp_parameter_nodes(plugin, "InternalParameters", internal_specs, managed_internal_pairs):
            modified = True

        if self._ensure_fpp_parameter_nodes(plugin, "InternalParameters", internal_specs):
            modified = True

        if self._remove_stale_fpp_parameter_nodes(plugin, "Parameters", visual_specs, managed_visual_pairs):
            modified = True

        if self._ensure_fpp_parameter_nodes(plugin, "Parameters", visual_specs):
            modified = True

        neighbor_node = plugin.find("NeighborOrder")
        neighbor_text = str(int(neighbor_order))
        if neighbor_node is None:
            ET.SubElement(plugin, "NeighborOrder").text = neighbor_text
            modified = True
        elif (neighbor_node.text or "").strip() != neighbor_text:
            neighbor_node.text = neighbor_text
            modified = True

        return modified

    def apply_fpp_parameters(self, parameters, neighbor_order=1):
        """
        Apply explicit ordinary FocalPointPlasticity parameters from project settings.

        This is for runtime steppables that create selected local links without
        exposing the link creation itself as a rule-engine behaviour.
        """
        if not parameters:
            return False

        specs = {}
        for item in parameters:
            if not isinstance(item, dict):
                continue
            type1 = item.get("type1")
            type2 = item.get("type2")
            self._add_fpp_spec(
                specs,
                type1,
                type2,
                {
                    "lambda": self._safe_float(
                        item.get("lambda", item.get("lambda_distance", item.get("link_lambda", 10.0))),
                        10.0,
                    ),
                    "activation_energy": self._safe_float(
                        item.get("activation_energy", item.get("fpp_activation_energy", -50.0)),
                        -50.0,
                    ),
                    "target_distance": self._safe_float(item.get("target_distance", 0.0), 0.0),
                    "max_distance": self._safe_float(item.get("max_distance", 0.0), 0.0),
                    "max_junctions": self._safe_int(
                        item.get("max_junctions", item.get("max_number_of_junctions", 1)),
                        1,
                    ),
                },
            )

        if not specs:
            return False

        self._ensure_plugin_exists("FocalPointPlasticity")
        plugin = self.root.find(".//Plugin[@Name='FocalPointPlasticity']")
        if plugin is None:
            return False

        modified = False
        if plugin.find("Local") is None:
            plugin.insert(0, ET.Element("Local"))
            modified = True

        if self._ensure_fpp_parameter_nodes(plugin, "Parameters", specs):
            modified = True

        neighbor_node = plugin.find("NeighborOrder")
        neighbor_text = str(int(neighbor_order or 1))
        if neighbor_node is None:
            ET.SubElement(plugin, "NeighborOrder").text = neighbor_text
            modified = True
        elif (neighbor_node.text or "").strip() != neighbor_text:
            neighbor_node.text = neighbor_text
            modified = True

        return modified

    def ensure_external_potential_plugin(self):
        """Ensure the ExternalPotential plugin exists for lambdaVec-driven runtime forces."""
        if self.root.find(".//Plugin[@Name='ExternalPotential']") is not None:
            return False
        self._ensure_plugin_exists("ExternalPotential")
        return self.root.find(".//Plugin[@Name='ExternalPotential']") is not None

    def _remove_stale_contact_internal_nodes(self, plugin, specs, managed_pairs):
        modified = False
        active_pairs = set(specs)
        managed_pairs = managed_pairs or set()
        for node in list(plugin.findall("Energy")):
            t1 = node.attrib.get("Type1")
            t2 = node.attrib.get("Type2")
            if not t1 or not t2:
                continue
            pair = tuple(sorted([t1, t2]))
            if pair in active_pairs:
                continue
            if pair not in managed_pairs:
                continue
            plugin.remove(node)
            modified = True
        return modified

    def _remove_stale_fpp_parameter_nodes(self, plugin, tag_name, specs, managed_pairs=None):
        managed_pairs = managed_pairs or set()
        modified = False
        active_pairs = set(specs)
        for node in list(plugin.findall(tag_name)):
            t1 = node.attrib.get("Type1")
            t2 = node.attrib.get("Type2")
            if not t1 or not t2:
                continue
            pair = tuple(sorted([t1, t2]))
            if pair in active_pairs:
                continue
            if managed_pairs and pair not in managed_pairs:
                continue
            plugin.remove(node)
            modified = True
        return modified

    def _ensure_fpp_parameter_nodes(self, plugin, tag_name, specs):
        modified = False
        existing = {}
        for node in plugin.findall(tag_name):
            t1 = node.attrib.get("Type1")
            t2 = node.attrib.get("Type2")
            if t1 and t2:
                existing[tuple(sorted([t1, t2]))] = node

        for pair, spec in specs.items():
            t1, t2 = pair
            node = existing.get(pair)
            if node is None:
                node = ET.SubElement(plugin, tag_name)
                node.set("Type1", t1)
                node.set("Type2", t2)
                existing[pair] = node
                modified = True
            else:
                if node.attrib.get("Type1") != t1:
                    node.set("Type1", t1)
                    modified = True
                if node.attrib.get("Type2") != t2:
                    node.set("Type2", t2)
                    modified = True

            for tag, value in (
                ("Lambda", spec["lambda"]),
                ("ActivationEnergy", spec["activation_energy"]),
                ("TargetDistance", spec["target_distance"]),
                ("MaxDistance", spec["max_distance"]),
                ("MaxNumberOfJunctions", spec["max_junctions"]),
            ):
                child = node.find(tag)
                text = self._xml_number(value)
                if child is None:
                    ET.SubElement(node, tag).text = text
                    modified = True
                elif (child.text or "").strip() != text:
                    child.text = text
                    modified = True

        return modified

    def _fpp_specs_from_rules(self, rules_json_data):
        internal_specs = {}
        visual_specs = {}
        managed_internal_pairs = set()
        managed_visual_pairs = set()
        neighbor_order = 1

        for rule in rules_json_data.get("rules", []):
            behaviour = rule.get("behaviour")

            for case in rule.get("cases", []):
                payload = case_payload(case)
                if behaviour == "fpp_link":
                    source_type = self._clean_type_name(rule.get("target"))
                    partner_type = self._clean_type_name(
                        payload.get("partner_type") or payload.get("target_type") or payload.get("cell_type")
                    )
                    if not source_type or not partner_type:
                        continue

                    lambda_distance = self._safe_float(
                        payload.get("link_lambda", payload.get("lambda_distance", 10.0)),
                        10.0,
                    )
                    target_distance = self._safe_float(payload.get("target_distance", 0.0), 0.0)
                    max_distance = self._safe_float(payload.get("max_distance", 0.0), 0.0)
                    activation_energy = self._safe_float(
                        payload.get("activation_energy", payload.get("fpp_activation_energy", -50.0)),
                        -50.0,
                    )
                    max_junctions = self._safe_int(
                        payload.get("max_junctions", payload.get("max_number_of_junctions", 1)),
                        1,
                    )
                    if "fpp_neighbor_order" in payload:
                        neighbor_order = self._safe_int(payload.get("fpp_neighbor_order"), neighbor_order)

                    pair = self._pair_key(source_type, partner_type)
                    if pair:
                        managed_visual_pairs.add(pair)
                    self._add_fpp_spec(
                        visual_specs,
                        source_type,
                        partner_type,
                        {
                            "lambda": lambda_distance,
                            "activation_energy": activation_energy,
                            "target_distance": target_distance,
                            "max_distance": max_distance,
                            "max_junctions": max_junctions,
                        },
                    )
                    continue

                if behaviour != "compartmentalize":
                    continue

                use_internal = self._safe_bool(payload.get("use_fpp_link"), False)
                use_visual = self._safe_bool(payload.get("visualize_fpp_link"), False)

                segment_type = self._clean_type_name(
                    payload.get("segment_type") or payload.get("cell_type")
                )
                tip_type = self._clean_type_name(
                    payload.get("tip_type") or segment_type
                )
                root_type = self._clean_type_name(payload.get("root_type"))
                if not segment_type or not tip_type:
                    continue

                lambda_distance = self._safe_float(
                    payload.get("link_lambda", payload.get("lambda_distance", 50.0)),
                    50.0,
                )
                target_distance = self._safe_float(
                    payload.get("target_distance", payload.get("step_length", 4.0)),
                    4.0,
                )
                if target_distance <= 0:
                    target_distance = self._safe_float(payload.get("step_length", 4.0), 4.0)

                max_distance = self._safe_float(payload.get("max_distance", target_distance * 2.0), target_distance * 2.0)
                if max_distance <= 0:
                    max_distance = target_distance * 2.0

                activation_energy = self._safe_float(
                    payload.get("activation_energy", payload.get("fpp_activation_energy", -50.0)),
                    -50.0,
                )
                max_junctions = self._safe_int(
                    payload.get("max_junctions", payload.get("max_number_of_junctions", 2)),
                    2,
                )
                if "fpp_neighbor_order" in payload:
                    neighbor_order = self._safe_int(payload.get("fpp_neighbor_order"), neighbor_order)

                spec = {
                    "lambda": lambda_distance,
                    "activation_energy": activation_energy,
                    "target_distance": target_distance,
                    "max_distance": max_distance,
                    "max_junctions": max_junctions,
                }
                allow_same_type_internal = self._safe_bool(
                    payload.get("allow_same_type_internal_link", payload.get("allow_same_type_internal", True)),
                    True,
                )
                for type_a, type_b in ((segment_type, tip_type), (segment_type, segment_type)):
                    pair = self._pair_key(type_a, type_b)
                    if pair:
                        managed_internal_pairs.add(pair)
                        managed_visual_pairs.add(pair)
                if use_internal:
                    self._add_fpp_spec(internal_specs, segment_type, tip_type, spec)
                    if allow_same_type_internal:
                        self._add_fpp_spec(internal_specs, segment_type, segment_type, spec)
                    if root_type and root_type != segment_type:
                        root_spec = dict(spec)
                        root_spec["max_junctions"] = self._safe_int(
                            payload.get("root_link_max_junctions", 1),
                            1,
                        )
                        self._add_fpp_spec(internal_specs, root_type, segment_type, root_spec)
                if use_visual:
                    self._add_fpp_spec(visual_specs, segment_type, tip_type, spec)
                    if allow_same_type_internal:
                        self._add_fpp_spec(visual_specs, segment_type, segment_type, spec)
                    if root_type and root_type != segment_type:
                        root_spec = dict(spec)
                        root_spec["max_junctions"] = self._safe_int(
                            payload.get("root_link_max_junctions", 1),
                            1,
                        )
                        self._add_fpp_spec(visual_specs, root_type, segment_type, root_spec)

        return internal_specs, visual_specs, neighbor_order, managed_internal_pairs, managed_visual_pairs

    def _add_fpp_spec(self, specs, type_a, type_b, spec):
        type_a = self._clean_type_name(type_a)
        type_b = self._clean_type_name(type_b)
        if not type_a or not type_b:
            return
        if type_a.lower() in {"none", "global", "medium"} or type_b.lower() in {"none", "global", "medium"}:
            return

        pair = tuple(sorted([type_a, type_b]))
        specs[pair] = dict(spec)

    def _contact_internal_specs_from_rules(self, rules_json_data):
        specs = {}
        tip_types = set()
        managed_pairs = set()
        default_energy = 2.0
        neighbor_order = 4

        for rule in rules_json_data.get("rules", []):
            if rule.get("behaviour") != "compartmentalize":
                continue

            for case in rule.get("cases", []):
                payload = case_payload(case)
                segment_type = self._clean_type_name(
                    payload.get("segment_type") or payload.get("cell_type")
                )
                tip_type = self._clean_type_name(
                    payload.get("tip_type") or segment_type
                )
                root_type = self._clean_type_name(payload.get("root_type"))
                if not segment_type and not tip_type:
                    continue

                energy_raw = (
                    payload.get("internal_contact_energy")
                    if "internal_contact_energy" in payload
                    else payload.get("contact_internal_energy", payload.get("internal_energy", default_energy))
                )
                explicit_energy = any(
                    key in payload
                    for key in ("internal_contact_energy", "contact_internal_energy", "internal_energy")
                )
                energy = self._safe_float(energy_raw, default_energy)
                default_energy = energy

                if "internal_neighbor_order" in payload:
                    neighbor_order = self._safe_int(payload.get("internal_neighbor_order"), neighbor_order)
                elif "contact_internal_neighbor_order" in payload:
                    neighbor_order = self._safe_int(payload.get("contact_internal_neighbor_order"), neighbor_order)

                if tip_type:
                    tip_types.add(tip_type)
                allow_same_type_internal = self._safe_bool(
                    payload.get("allow_same_type_internal_link", payload.get("allow_same_type_internal", True)),
                    True,
                )
                for type_a, type_b in ((segment_type, tip_type), (segment_type, segment_type)):
                    pair = self._pair_key(type_a, type_b)
                    if pair:
                        managed_pairs.add(pair)
                self._add_contact_internal_spec(specs, segment_type, tip_type, energy, explicit_energy)
                if allow_same_type_internal:
                    self._add_contact_internal_spec(specs, segment_type, segment_type, energy, explicit_energy)
                if root_type and segment_type and root_type != segment_type:
                    self._add_contact_internal_spec(specs, root_type, segment_type, energy, explicit_energy)

        # If a type-switch creates a hypha tip seed, keep its internal relation
        # available for compartment-based chains that begin at the conversion site.
        for rule in rules_json_data.get("rules", []):
            if rule.get("behaviour") != "differentiate":
                continue

            source_type = self._clean_type_name(rule.get("target"))
            if not source_type:
                continue

            for case in rule.get("cases", []):
                payload = case_payload(case)
                if payload.get("mode") != "type_switch":
                    continue
                new_type = self._clean_type_name(payload.get("new_type"))
                if new_type in tip_types:
                    pair = self._pair_key(source_type, new_type)
                    if pair:
                        managed_pairs.add(pair)
                    self._add_contact_internal_spec(specs, source_type, new_type, default_energy, False)

        return specs, neighbor_order, managed_pairs

    def _add_contact_internal_spec(self, specs, type_a, type_b, energy, explicit_energy):
        type_a = self._clean_type_name(type_a)
        type_b = self._clean_type_name(type_b)
        if not type_a or not type_b:
            return
        if type_a.lower() in {"none", "global", "medium"} or type_b.lower() in {"none", "global", "medium"}:
            return

        pair = tuple(sorted([type_a, type_b]))
        previous = specs.get(pair)
        if previous is None or explicit_energy:
            specs[pair] = {
                "energy": energy,
                "explicit_energy": explicit_energy,
            }

    def _pair_key(self, type_a, type_b):
        type_a = self._clean_type_name(type_a)
        type_b = self._clean_type_name(type_b)
        if not type_a or not type_b:
            return None
        if type_a.lower() in {"none", "global", "medium"} or type_b.lower() in {"none", "global", "medium"}:
            return None
        return tuple(sorted([type_a, type_b]))

    @staticmethod
    def _clean_type_name(value):
        if value is None:
            return ""
        text = str(value).strip()
        return "" if not text or text.lower() == "nan" else text

    @staticmethod
    def _safe_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _safe_bool(value, default=False):
        if value is None:
            return bool(default)
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return bool(default)

    @staticmethod
    def _xml_number(value):
        numeric = float(value)
        return str(int(numeric)) if numeric.is_integer() else str(numeric)
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

    def ensure_volume_plugin_empty(self, save=True, quiet=False):

        # current volume plugin
        plugin = self.root.find(".//Plugin[@Name='Volume']")
        
        if plugin is not None:
            # clean<VolumeEnergyParameters ... />)
            for child in list(plugin):
                plugin.remove(child)
            if not quiet:
                print("[StructureManager] Volume plugin cleared for Python control.")
        else:
            plugin = ET.SubElement(self.root, "Plugin")
            plugin.set("Name", "Volume")
            if not quiet:
                print("[StructureManager] Empty Volume plugin added for Python control.")
            
        if save:
            self.save()
        
    # ============================================================
    # CELLTYPE
    # ============================================================

    def ensure_celltype(self, name, create_initializer=True):
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
        if create_initializer:
            self._ensure_initializer(name)

        return True

    def ensure_celltypes_from_registry(self, celltype_params):
        """
        Register all rule-known cell types in XML without creating initializer regions.

        Runtime-only types such as HyphaTip, HyphaSegment, DamagedHostCell, and
        InterstitialSpace must exist in the CellType plugin before FPP/contact
        parameters can reference them, but they should not be initialized as
        starting cells unless the initializer config explicitly asks for it.
        """
        if not isinstance(celltype_params, dict):
            return False

        modified = False
        for name in celltype_params.keys():
            clean_name = self._clean_type_name(name)
            if not clean_name or clean_name.lower() == "medium":
                continue
            if self.ensure_celltype(clean_name, create_initializer=False):
                modified = True

        return modified

    def remove_celltype(self, name):
        if not name or str(name).lower() == "medium":
            return False

        removed = False

        plugin = self.root.find(".//Plugin[@Name='CellType']")
        if plugin is not None:
            for ct in list(plugin.findall("CellType")):
                if ct.attrib.get("TypeName") == name:
                    plugin.remove(ct)
                    removed = True

        for plugin_name in ("Contact", "ContactInternal"):
            contact_plugin = self.root.find(f".//Plugin[@Name='{plugin_name}']")
            if contact_plugin is not None:
                for energy in list(contact_plugin.findall("Energy")):
                    if energy.attrib.get("Type1") == name or energy.attrib.get("Type2") == name:
                        contact_plugin.remove(energy)
                        removed = True

        volume_plugin = self.root.find(".//Plugin[@Name='Volume']")
        if volume_plugin is not None:
            for param in list(volume_plugin.findall("VolumeEnergyParameters")):
                if param.attrib.get("CellType") == name:
                    volume_plugin.remove(param)
                    removed = True

        initializer = self.root.find(".//Steppable[@Type='UniformInitializer']")
        if initializer is not None:
            for region in list(initializer.findall("Region")):
                types_node = region.find("Types")
                types = [part.strip() for part in (types_node.text or "").split(",")] if types_node is not None else []
                if name in types:
                    initializer.remove(region)
                    removed = True

        chem_plugin = self.root.find(".//Plugin[@Name='Chemotaxis']")
        if chem_plugin is not None:
            for chemical_field in list(chem_plugin.findall("ChemicalField")):
                for entry in list(chemical_field.findall("ChemotaxisByType")):
                    if entry.attrib.get("Type") == name:
                        chemical_field.remove(entry)
                        removed = True
                if len(chemical_field.findall("ChemotaxisByType")) == 0:
                    chem_plugin.remove(chemical_field)

        if removed:
            self._seen_celltypes.discard(name)
            print(f"[StructureManager] Removed CellType and related XML entries: {name}")
        return removed
    
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
            solver = ET.SubElement(self.root, "Steppable", attrib={"Type": "DiffusionSolverFE"})

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

    def apply_contact_overrides(self, overrides):
        """
        Apply explicit contact-energy overrides to the Contact plugin.

        Accepted formats:
        - [{"type1": "A", "type2": "B", "energy": 20.0}, ...]
        - {"A|B": 20.0, "A,B": 20.0, "A-B": 20.0}
        """
        if not overrides:
            return False

        contact_plugin = self.root.find(".//Plugin[@Name='Contact']")
        if contact_plugin is None:
            self._ensure_plugin_exists("Contact")
            contact_plugin = self.root.find(".//Plugin[@Name='Contact']")
            if contact_plugin is None:
                return False

        normalized = []
        if isinstance(overrides, dict):
            for pair_text, energy in overrides.items():
                parts = None
                for sep in ("|", ",", "-"):
                    if sep in str(pair_text):
                        parts = [part.strip() for part in str(pair_text).split(sep, 1)]
                        break
                if parts and len(parts) == 2:
                    normalized.append({"type1": parts[0], "type2": parts[1], "energy": energy})
        elif isinstance(overrides, list):
            normalized = [item for item in overrides if isinstance(item, dict)]
        else:
            return False

        existing = {}
        for energy_node in contact_plugin.findall("Energy"):
            t1 = energy_node.attrib.get("Type1")
            t2 = energy_node.attrib.get("Type2")
            if t1 and t2:
                existing[tuple(sorted([t1, t2]))] = energy_node

        modified = False
        for item in normalized:
            t1 = self._clean_type_name(item.get("type1") or item.get("Type1"))
            t2 = self._clean_type_name(item.get("type2") or item.get("Type2"))
            if not t1 or not t2:
                continue
            try:
                energy = float(item.get("energy", item.get("Energy")))
            except (TypeError, ValueError):
                continue

            pair = tuple(sorted([t1, t2]))
            text = self._xml_number(energy)
            energy_node = existing.get(pair)
            if energy_node is None:
                energy_node = ET.SubElement(contact_plugin, "Energy")
                energy_node.set("Type1", pair[0])
                energy_node.set("Type2", pair[1])
                existing[pair] = energy_node
                modified = True
            if (energy_node.text or "").strip() != text:
                energy_node.text = text
                modified = True

        if modified:
            self._indent(self.root)
        return modified

    def ensure_connectivity_global(self, cell_types, fast_algorithm=True, penalty=None):
        """
        Enable connectivity protection for selected cell types.

        This prevents individual CellG objects from fragmenting while avoiding a
        global connectivity constraint on host/interstitial tissue.
        """
        normalized_types = []
        for cell_type in cell_types or []:
            name = self._clean_type_name(cell_type)
            if name and name.lower() != "medium" and name not in normalized_types:
                normalized_types.append(name)

        if not normalized_types:
            return False

        plugin = self.root.find("./Plugin[@Name='ConnectivityGlobal']")
        modified = False
        if plugin is None:
            plugin = ET.Element("Plugin", {"Name": "ConnectivityGlobal"})
            celltype_plugin = self.root.find("./Plugin[@Name='CellType']")
            children = list(self.root)
            insert_index = children.index(celltype_plugin) + 1 if celltype_plugin in children else 2
            self.root.insert(insert_index, plugin)
            modified = True

        if fast_algorithm:
            if plugin.find("FastAlgorithm") is None:
                plugin.insert(0, ET.Element("FastAlgorithm"))
                modified = True

            existing = {
                (node.get("Type") or "").strip()
                for node in plugin.findall("ConnectivityOn")
            }
            for name in normalized_types:
                if name not in existing:
                    ET.SubElement(plugin, "ConnectivityOn", {"Type": name})
                    modified = True
        else:
            try:
                penalty_text = self._xml_number(float(penalty if penalty is not None else 1000000))
            except (TypeError, ValueError):
                penalty_text = "1000000"

            existing = {
                (node.get("Type") or "").strip(): node
                for node in plugin.findall("Penalty")
            }
            for name in normalized_types:
                node = existing.get(name)
                if node is None:
                    node = ET.SubElement(plugin, "Penalty", {"Type": name})
                    node.text = penalty_text
                    modified = True
                elif (node.text or "").strip() != penalty_text:
                    node.text = penalty_text
                    modified = True

        if modified:
            self._indent(self.root)
        return modified

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

    def update_initializers(self, active_cells_config, layout_regions=None):
        initializer = self.root.find(".//Steppable[@Type='UniformInitializer']")
        if initializer is None:
            initializer = ET.SubElement(self.root, "Steppable", {"Type": "UniformInitializer"})
        else:
            # clear the old, unticked cell types
            for region in list(initializer.findall("Region")):
                initializer.remove(region)

        if layout_regions:
            for layout_region in layout_regions:
                self._add_initializer_region(initializer, layout_region)
            self._indent(self.root)
            return

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

    def _add_initializer_region(self, initializer, layout_region):
        region = ET.SubElement(initializer, "Region")

        box_min = layout_region.get("box_min") or layout_region.get("BoxMin") or {}
        box_max = layout_region.get("box_max") or layout_region.get("BoxMax") or {}

        boxmin = ET.SubElement(region, "BoxMin")
        boxmin.set("x", str(box_min.get("x", 0)))
        boxmin.set("y", str(box_min.get("y", 0)))
        boxmin.set("z", str(box_min.get("z", 0)))

        boxmax = ET.SubElement(region, "BoxMax")
        boxmax.set("x", str(box_max.get("x", 1)))
        boxmax.set("y", str(box_max.get("y", 1)))
        boxmax.set("z", str(box_max.get("z", 1)))

        ET.SubElement(region, "Gap").text = str(layout_region.get("gap", layout_region.get("Gap", 0)))
        ET.SubElement(region, "Width").text = str(layout_region.get("width", layout_region.get("Width", 5)))

        raw_types = layout_region.get("types", layout_region.get("type", layout_region.get("Types", "")))
        if isinstance(raw_types, (list, tuple)):
            raw_types = ",".join(str(item).strip() for item in raw_types if str(item).strip())

        types = ET.SubElement(region, "Types")
        types.text = str(raw_types).strip()

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
                    cf_node.set("Source", "DiffusionSolverFE")
                
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
                                nodes = plane.findall(val_type)
                                if nodes:
                                    min_val = 0.0
                                    max_val = 0.0
                                    for node in nodes:
                                        position = node.get('PlanePosition')
                                        value = float(node.get('Value') or 0.0)
                                        if position == 'Min':
                                            min_val = value
                                        elif position == 'Max':
                                            max_val = value
                                    fields_data[f_name]["boundary_conditions"][axis] = {
                                        "type": val_type,
                                        "min_val": min_val,
                                        "max_val": max_val,
                                    }
                                    break

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
                   
                    secretion_plugin = self.root.find(".//Plugin[@Name='Secretion']")
                    has_pure_secretion = (secretion_plugin is not None) and (len(secretion_plugin.findall('Field')) == 0)
                    
                    # Initialize params dict
                    params = {
                        'solver': solver_type,
                        'diffusion_constant': 0.01,
                        'decay_constant': 0.0001,
                        'initial_expression': '0.0',
                        'python_secretion': has_pure_secretion,
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


    def ensure_field_xml_from_registry(self, field_params, verbose=True):
        """
        Regenerate clean XML nodes from scratch based on the field_params dictionary in the Registry.
        """
        if verbose:
            print("🚨 BUILD XML CALLED")

        for steppable in self.root.findall("Steppable[@Type='DiffusionSolverFE']"):
            self.root.remove(steppable)

        # Locate the Secretion plugin and clear it (keep the plugin shell, remove its contents)
        for plugin in self.root.findall("Plugin[@Name='Secretion']"):
            self.root.remove(plugin)

        # Rebuild Chemotaxis only when at least one field has real chemotaxis data.
        chemo_plugin = self.root.find(".//Plugin[@Name='Chemotaxis']")
        if chemo_plugin is not None:
            self.root.remove(chemo_plugin)

        if not field_params:
            self.sync_secretion_plugin_capsule(field_params)
            return

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
            # print(f"DEBUG: Params for {field_name}: {params}")
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
            if py_sec and verbose:
                print(f"[SM] {field_name} uses Python secretion. Skipping XML SecretionData.")
            if not py_sec:
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
                    if verbose:
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

                chem_field_node = ET.SubElement(chemo_plugin, 'ChemicalField', attrib={
                    'Name': field_name,
                    'Source': params.get('solver', 'DiffusionSolverFE'),
                })

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
        self.sync_secretion_plugin_capsule(field_params)

    # ==========================================
    # 3. Secretion
    # ==========================================
    def remove_plugin_by_name(self, plugin_name):
        """
        scan the XML tree and safely remove Plugin nodes with the target name
        """
        if self.root is None:
            return
            
        plugins_to_remove = self.root.findall(f".//Plugin[@Name='{plugin_name}']")
        for plugin in plugins_to_remove:
            try:
                self.root.remove(plugin)
                print(f"🧹 [StructureManager] Removed existing <Plugin Name='{plugin_name}'/>")
            except ValueError:
                pass

    def sync_secretion_plugin_capsule(self, field_params):
        """
        Independently manage the clean lifecycle of the Python secretion plugin switch
        """
        self.remove_plugin_by_name("Secretion")

        any_py_sec = any(p.get('python_secretion', False) for p in field_params.values())
        
        if any_py_sec:
            ET.SubElement(self.root, 'Plugin', attrib={'Name': 'Secretion'})
            print("🚀 [StructureManager] Successfully injected PURE <Plugin Name='Secretion'/> capsule for Python.")
