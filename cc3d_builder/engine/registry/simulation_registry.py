# simulation_registry.py
import ast
import contextlib
import io
import json
import re
import sqlite3
from pathlib import Path
from cc3d_builder.core.rule_schema import case_payload
from cc3d_builder.core.structure_manager import StructureManager
from cc3d_builder.core.project_profile import (
    load_json,
    read_active_project,
    sync_sandbox_artifacts_to_source,
    sync_sandbox_rules_to_profile,
)
from cc3d_builder.engine.code_generator import CC3DDecompiledGenerator
from cc3d_builder.injector.steppable_injector import SteppableInjector

class SimulationRegistry:

    def __init__(self, project_path,structure_manager=None):
        # here it is sandbox_dir from cli/main.py and main_editor.py
        self.project_path = Path(project_path)
        self.sm = structure_manager

        self.rules_path = self.project_path / "Simulation" /"rules.json"
        self.xml_path = self.project_path / "Simulation" /"Rules_project.xml"
        self.py_path    = self.project_path / "Simulation" /"Rules_project_Steppables.py"
        self.rules = []
        self.cell_index = {}
        self.behaviour_index = {}
        self.celltype_params = {}
        self.field_params = {}
        self.intracellular_models = []
        self.subcellular_systems = []
        self.settings = {"execution_semantics": "snapshot"}
        self.last_registration_summary = {}

    def _reset_state(self):
        self.rules = []
        self.celltype_params = {}
        self.field_params = {}
        self.intracellular_models = []
        self.subcellular_systems = []
        self.settings = {"execution_semantics": "snapshot"}
        self._build_index()

    def _apply_rules_data(self, data):
        if isinstance(data, list):
            data = {"rules": data}

        if not isinstance(data, dict):
            print(f"⚠️ Invalid rules.json format at {self.rules_path}; expected object. Using empty rules.")
            self._reset_state()
            return False

        self.rules = data.get("rules", [])
        self.celltype_params = data.get("celltype_params", {})
        self.field_params = data.get("field_params", {})
        self.intracellular_models = data.get("intracellular_models", [])
        self.subcellular_systems = data.get("subcellular_systems", [])
        self.settings = data.get("settings", {"execution_semantics": "snapshot"})

        if not isinstance(self.rules, list):
            print(f"⚠️ Invalid rules list in {self.rules_path}; using empty rules.")
            self.rules = []
        if not isinstance(self.celltype_params, dict):
            self.celltype_params = {}
        if not isinstance(self.field_params, dict):
            self.field_params = {}
        if not isinstance(self.intracellular_models, list):
            self.intracellular_models = []
        if not isinstance(self.subcellular_systems, list):
            self.subcellular_systems = []
        if not isinstance(self.settings, dict):
            self.settings = {"execution_semantics": "snapshot"}

        self._build_index()
        return True

    def add_celltype_params(
        self,
        name,
        target,
        lam,
        count=5,
        should_init=True,
        autosave=True,
        rebuild_artifacts=False,
    ):
        self.celltype_params[name] = {
            "targetVolume": target,
            "lambdaVolume": lam,
            "initial_count": count,          
             "should_initialize": should_init
        }
        if autosave:
            self.save(rebuild_artifacts=rebuild_artifacts, quiet=not rebuild_artifacts)

    # ============================================================
    # LOAD
    # ============================================================

    def load(self):
        if not self.rules_path.exists():
            self._reset_state()
        else:
            data = load_json(self.rules_path, None)
            if data is None:
                self._reset_state()
            else:
                self._apply_rules_data(data)
        
        if self.sm:
            self.sync_with_xml()
            self._apply_initial_layout_from_settings()
            self._apply_pif_io_from_settings()
        
        self._build_index()

    # ============================================================
    # BUILD INDEX
    # ============================================================

    def _build_index(self):

        self.cell_index = {}
        self.behaviour_index = {}

        for rule in self.rules:
            cell = rule.get("target")
            behaviour = rule.get("behaviour")
            self.cell_index.setdefault(cell, []).append(rule)
            self.behaviour_index.setdefault(behaviour, []).append(rule)

    # ============================================================
    # ADD / UPDATE
    # ============================================================

    def add_rule(self, rule):
        self.rules.append(rule)
        self._build_index()
        # self.save()

    # ============================================================
    # DELETE
    # ============================================================

    def delete_rule(self, rule_id):

        self.rules = [r for r in self.rules if r.get("id") != rule_id]
        self._build_index()
        self.save()

    def delete_field(self, field_name):
        if field_name not in self.field_params:
            return False
        del self.field_params[field_name]
        self.save()
        return True

    def delete_celltype(self, celltype_name):
        if celltype_name not in self.celltype_params:
            return False
        del self.celltype_params[celltype_name]
        self._build_index()
        self.save()
        return True

    # ============================================================
    # QUERY API
    # ============================================================

    def get_rule(self, rule_id):

        for r in self.rules:
            if r["id"] == rule_id:
                return r

        return None

    def get_rules_for_cell(self, cell_type):
        return self.cell_index.get(cell_type, [])

    def get_rules_for_behaviour(self, behaviour):
        return self.behaviour_index.get(behaviour, [])

    def list_all_rules(self):
        return self.rules

    # ============================================================
    # SAVE JSON
    # ============================================================

    def _rules_payload(self):
        return {
            "rules": self.rules,
            "celltype_params": self.celltype_params,
            "field_params": self.field_params,
            "intracellular_models": self.intracellular_models,
            "subcellular_systems": self.subcellular_systems,
            "settings": self.settings,
        }

    def save_state(self, sync_profile=True, quiet=False):
        self.sync_chemotaxis_placeholders_from_rules()
        self.sync_intracellular_field_placeholders_from_models()

        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.rules_path, "w") as f:
            json.dump(self._rules_payload(), f, indent=2)

        profile_synced = False
        try:
            if sync_profile and sync_sandbox_rules_to_profile(self.project_path):
                profile_synced = True
                if not quiet:
                    print("💾 [Profile] Project .ruleparser/rules.json synchronized.")
        except Exception as exc:
            if not quiet:
                print(f"⚠️ [Profile] Could not sync project .ruleparser/rules.json: {exc}")

        self._build_index()
        return {
            "rules_path": str(self.rules_path),
            "profile_synced": profile_synced,
        }

    def save(self, rebuild_artifacts=True, quiet=False):
        if rebuild_artifacts:
            return self.commit_artifacts(quiet=quiet)
        return self.save_state(quiet=quiet)

    def commit_artifacts(self, quiet=False):
        if quiet:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                return self._commit_artifacts_impl(quiet=True)
        return self._commit_artifacts_impl(quiet=False)

    def _commit_artifacts_impl(self, quiet=False):
        state_summary = self.save_state(quiet=True)

        xml_updated = False
        dependencies_checked = False
        volume_markers_synced = False
        code_generated = False
        generator_error = None
        source_artifact_summary = {"synced": False, "copied": []}
        source_artifact_error = None

        sm = self.sm
        if sm is None:
            try:
                sm = StructureManager(self.project_path)
                self.sm = sm
            except Exception:
                sm = None

        if sm:
            if sm.ensure_celltypes_from_registry(self.celltype_params):
                xml_updated = True
                sm.save()

            sm.ensure_volume_plugin_empty(save=True, quiet=quiet)
            xml_updated = True

            if self._sync_initializers_to_xml(sm):
                xml_updated = True
                sm.save()

            if self._sync_pif_io_to_xml(sm):
                xml_updated = True
                sm.save()

            if self._sync_contact_overrides_to_xml(sm):
                xml_updated = True
                sm.save()

            if self._sync_fpp_parameters_to_xml(sm):
                xml_updated = True
                sm.save()

            if self._sync_external_potential_to_xml(sm):
                xml_updated = True
                sm.save()

            if self._sync_connectivity_to_xml(sm):
                xml_updated = True
                sm.save()

            sm.ensure_field_xml_from_registry(self.field_params, verbose=not quiet)
            sm.save()
            xml_updated = True

            if not quiet:
                print("🔍 [Registry] Checking XML dependencies for all rules...")
            sm.check_and_inject_dependencies({"rules": self.rules})
            dependencies_checked = True

        self._sync_volume_markers_to_steppables()
        volume_markers_synced = True

        try:
            generator = CC3DDecompiledGenerator(self, steppable_class_name=self._project_steppable_class_name())
            generator.save_to_file(self.project_path / "Simulation")
            code_generated = True
            if not quiet:
                target_dir = self.project_path / "Simulation"
                print(f"🚀 [Generator] SimulationStepCode.py has been re-compiled in {target_dir}.")
        except Exception as e:
            generator_error = str(e)
            if not quiet:
                print(f"❌ [Generator] Failed to compile rules: {e}")

        self._enforce_player_display_defaults()

        try:
            source_artifact_summary = sync_sandbox_artifacts_to_source(
                self.project_path,
                include_generated_code=code_generated,
            )
        except Exception as exc:
            source_artifact_error = str(exc)
            if not quiet:
                print(f"⚠️ [Profile] Could not sync sandbox artifacts to source project: {exc}")

        return {
            **state_summary,
            "xml_updated": xml_updated,
            "dependencies_checked": dependencies_checked,
            "volume_markers_synced": volume_markers_synced,
            "code_generated": code_generated,
            "generator_error": generator_error,
            "source_artifacts_synced": bool(source_artifact_summary.get("synced")),
            "source_artifact_paths": source_artifact_summary.get("copied", []),
            "source_project_path": source_artifact_summary.get("source_project_path"),
            "source_artifact_error": source_artifact_error or source_artifact_summary.get("error"),
            "rule_count": len(self.rules),
            "celltypes": [
                str(name)
                for name in self.celltype_params.keys()
                if str(name).lower() != "medium"
            ],
            "fields": list(self.field_params.keys()),
        }

    def _project_steppable_class_name(self):
        inferred_from_project = self._active_project_steppable_class_name()
        if not self.py_path.exists():
            return inferred_from_project

        try:
            tree = ast.parse(self.py_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"⚠️ [Generator] Could not inspect project steppable class name: {exc}")
            return inferred_from_project

        fallback = None
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not self._is_cc3d_steppable_class(node):
                continue
            if node.name != "SimulationSteppable":
                return node.name
            fallback = fallback or node.name
        return inferred_from_project or fallback

    def _active_project_steppable_class_name(self):
        active = read_active_project(self.project_path)
        source_path = active.get("source_project_path")
        if not source_path:
            return None
        return f"{Path(source_path).expanduser().resolve().name}Steppable"

    def _is_cc3d_steppable_class(self, node):
        for base in node.bases:
            base_name = self._ast_name(base)
            if base_name in {"SteppableBasePy", "MitosisSteppableBase"}:
                return True
        return False

    def _ast_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _sync_volume_markers_to_steppables(self):
        """
        Keep the original project steppable volume markers aligned with
        registry.celltype_params.

        The rule engine and generated SimulationStepCode read celltype_params
        directly, but CC3D still runs the imported project Steppables.py start()
        method. If its CC3D_VOLUME_* markers are stale, they can override the
        intended type mechanics before rule execution starts.
        """
        if not self.py_path.exists():
            return

        try:
            injector = SteppableInjector(self.project_path)
        except Exception as exc:
            print(f"⚠️ [Registry] Could not sync steppable volume markers: {exc}")
            return

        current_markers = {
            f"CC3D_VOLUME_{str(name).upper()}"
            for name in self.celltype_params.keys()
            if str(name).lower() != "medium"
        }

        try:
            content = injector._read_file()
            stale_markers = []
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("# === CC3D_VOLUME_") and stripped.endswith(" START ==="):
                    marker = stripped.removeprefix("# === ").removesuffix(" START ===")
                    if marker not in current_markers:
                        stale_markers.append(marker)

            for marker in stale_markers:
                injector.remove_volume_start_code(marker.removeprefix("CC3D_VOLUME_"))

            for name, params in self.celltype_params.items():
                if str(name).lower() == "medium":
                    continue
                injector.ensure_volume_start_code(
                    name,
                    target_volume=float(params.get("targetVolume", 50.0)),
                    lambda_volume=float(params.get("lambdaVolume", 2.0)),
                )
        except Exception as exc:
            print(f"⚠️ [Registry] Could not sync steppable volume markers: {exc}")

    def _enforce_player_display_defaults(self):
        """
        Keep CC3D Player from displaying every singleton raw cluster as a cluster.

        CC3D gives every CellG a clusterId, even ordinary non-compartment cells.
        If ClusterBordersOn is enabled, Player outlines all of those singleton
        clusters and makes it look as if every normal cell is a compartment.
        """
        settings_path = self.project_path / "Simulation" / "_settings.sqlite"
        if not settings_path.exists():
            return

        desired = {
            "ClusterBordersOn": ("bool", "0"),
            "ClusterBorderColor": ("color", "#000000"),
            "CellGlyphsOn": ("bool", "0"),
        }

        try:
            with sqlite3.connect(settings_path) as conn:
                for name, (setting_type, value) in desired.items():
                    exists = conn.execute(
                        "select 1 from settings where name = ?",
                        (name,),
                    ).fetchone()
                    if exists:
                        conn.execute(
                            "update settings set type = ?, value = ? where name = ?",
                            (setting_type, value, name),
                        )
                    else:
                        conn.execute(
                            "insert into settings (name, type, value) values (?, ?, ?)",
                            (name, setting_type, value),
                        )
        except Exception as exc:
            print(f"⚠️ [Player Settings] Could not enforce cluster border defaults: {exc}")

    def _sync_initializers_to_xml(self, sm):
        active_inits = {}
        for name, params in self.celltype_params.items():
            if params.get("should_initialize", True):
                active_inits[name] = params.get("initial_count", 5)

        if not isinstance(self.settings, dict):
            initial_layout = {}
        else:
            initial_layout = self.settings.get("initial_layout", {})
        if not isinstance(initial_layout, dict):
            initial_layout = {}

        has_explicit_regions = "regions" in initial_layout
        layout_regions = list(initial_layout.get("regions") or [])
        for patch in initial_layout.get("interstitial_patches") or []:
            patch_region = self._interstitial_patch_to_region(patch)
            if patch_region:
                layout_regions.append(patch_region)

        if has_explicit_regions or layout_regions:
            sm.update_initializers(active_inits, layout_regions=layout_regions)
            return True

        modified = False
        for name, count in active_inits.items():
            if hasattr(sm, "ensure_initializer_region") and sm.ensure_initializer_region(name, count=count):
                modified = True
        return modified

    def _apply_initial_layout_from_settings(self):
        if self.sm is None or not isinstance(self.settings, dict):
            return False
        initial_layout = self.settings.get("initial_layout")
        if not isinstance(initial_layout, dict):
            return False
        if "regions" not in initial_layout and not initial_layout.get("interstitial_patches"):
            return False
        try:
            if self._sync_initializers_to_xml(self.sm):
                self.sm.save()
                return True
        except Exception as exc:
            print(f"⚠️ [Registry] Could not apply profile initializer layout: {exc}")
        return False

    def _sync_pif_io_to_xml(self, sm):
        if not isinstance(self.settings, dict):
            return False
        pif_config = (
            self.settings.get("piff")
            or self.settings.get("pif")
            or self.settings.get("pif_io")
        )
        if not isinstance(pif_config, dict):
            return False
        if not hasattr(sm, "update_pif_io"):
            return False
        return bool(sm.update_pif_io(pif_config))

    def _apply_pif_io_from_settings(self):
        if self.sm is None:
            return False
        try:
            if self._sync_pif_io_to_xml(self.sm):
                self.sm.save()
                return True
        except Exception as exc:
            print(f"⚠️ [Registry] Could not apply PIF settings: {exc}")
        return False

    @staticmethod
    def _interstitial_patch_to_region(patch):
        if not isinstance(patch, dict):
            return None

        try:
            x0 = int(patch.get("x0"))
            y0 = int(patch.get("y0"))
            x1 = int(patch.get("x1"))
            y1 = int(patch.get("y1"))
        except (TypeError, ValueError):
            return None

        width = int(patch.get("width") or max(1, min(abs(x1 - x0), abs(y1 - y0))))
        return {
            "type": patch.get("type", "InterstitialSpace"),
            "box_min": {"x": min(x0, x1), "y": min(y0, y1), "z": int(patch.get("z0", 0))},
            "box_max": {"x": max(x0, x1), "y": max(y0, y1), "z": int(patch.get("z1", 1))},
            "gap": int(patch.get("gap", 0)),
            "width": width,
        }

    def _sync_contact_overrides_to_xml(self, sm):
        if not isinstance(self.settings, dict):
            return False
        overrides = self.settings.get("contact_overrides")
        if not overrides:
            return False
        return sm.apply_contact_overrides(overrides)

    def _sync_fpp_parameters_to_xml(self, sm):
        if not isinstance(self.settings, dict):
            return False
        parameters = self.settings.get("fpp_parameters")
        if not parameters:
            return False
        neighbor_order = self.settings.get("fpp_neighbor_order", 1)
        return sm.apply_fpp_parameters(parameters, neighbor_order=neighbor_order)

    def _sync_external_potential_to_xml(self, sm):
        if not isinstance(self.settings, dict):
            return False
        external_config = self.settings.get("external_potential")
        enabled = (
            isinstance(external_config, dict)
            and bool(external_config.get("enabled"))
        )
        if not enabled:
            return False
        return sm.ensure_external_potential_plugin()

    def _sync_connectivity_to_xml(self, sm):
        if not isinstance(self.settings, dict):
            return False

        config = self.settings.get("connectivity")
        if not isinstance(config, dict):
            return False

        cell_types = config.get("cell_types") or config.get("types") or []
        if isinstance(cell_types, str):
            cell_types = [part.strip() for part in cell_types.split(",") if part.strip()]

        return sm.ensure_connectivity_global(
            cell_types,
            fast_algorithm=bool(config.get("fast_algorithm", True)),
            penalty=config.get("penalty"),
        )
    # ============================================================
    # ============================================================

    def sync_intracellular_field_placeholders_from_models(self):
        """
        Ensure intracellular input mappings that sample PDE fields have XML field
        placeholders before CC3D starts the simulation.
        """
        field_names = set()

        def collect_from_mappings(mappings):
            if isinstance(mappings, dict):
                mappings = [mappings]
            if not isinstance(mappings, list):
                return

            for mapping in mappings:
                if not isinstance(mapping, dict):
                    continue
                source_kind = str(
                    mapping.get("from")
                    or mapping.get("source_kind")
                    or mapping.get("source")
                    or ""
                ).strip().lower()
                if source_kind not in {"field", "field_sample", "environment"}:
                    continue
                field_name = str(
                    mapping.get("field_name")
                    or mapping.get("field")
                    or mapping.get("source_key")
                    or ""
                ).strip()
                if field_name:
                    field_names.add(field_name)

        for spec in self.intracellular_models or []:
            if not isinstance(spec, dict):
                continue
            collect_from_mappings(spec.get("inputs") or spec.get("input_mappings") or [])

        for rule in self.rules:
            if rule.get("behaviour") != "intracellular_model":
                continue
            for case in rule.get("cases", []):
                payload = case_payload(case)
                collect_from_mappings(payload.get("inputs") or payload.get("input_mappings") or [])

        for field_name in field_names:
            self.field_params.setdefault(
                field_name,
                {
                    "solver": "DiffusionSolverFE",
                    "diffusion_constant": 0.01,
                    "decay_constant": 0.0001,
                    "initial_expression": "0.0",
                    "python_secretion": False,
                    "boundary_conditions": {},
                    "chemotaxis": [],
                    "rule_managed": True,
                },
            )

    def sync_chemotaxis_placeholders_from_rules(self):
        """
        Ensure rule-driven chemotaxis also declares the required CC3D XML plugin data.

        Runtime chemotaxis rules write per-cell ChemotaxisData, but CC3D still needs
        the Chemotaxis plugin and ChemicalField/Type entries declared in XML first.
        These placeholders intentionally use Lambda=0.0 so global XML chemotaxis does
        not replace the rule-specific runtime lambda.
        """
        active_pairs = set()

        for rule in self.rules:
            if rule.get("behaviour") != "chemotaxis":
                continue

            target = str(rule.get("target") or "").strip()
            if not target or target.lower() == "none":
                continue

            for case in rule.get("cases", []):
                payload = case_payload(case)
                field_name = str(
                    payload.get("field_name")
                    or payload.get("field")
                    or payload.get("regulator")
                    or ""
                ).strip()

                if not field_name:
                    continue

                active_pairs.add((field_name, target))
                field_params = self.field_params.setdefault(
                    field_name,
                    {
                        "solver": "DiffusionSolverFE",
                        "diffusion_constant": 0.01,
                        "decay_constant": 0.0001,
                        "initial_expression": "0.0",
                        "python_secretion": False,
                        "boundary_conditions": {},
                        "chemotaxis": [],
                    },
                )
                entries = field_params.setdefault("chemotaxis", [])

                existing = None
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    entry_type = str(entry.get("cell_type") or entry.get("CellType") or "").strip()
                    if entry_type == target:
                        existing = entry
                        break

                if existing is None:
                    entries.append(
                        {
                            "cell_type": target,
                            "lambda": 0.0,
                            "mode": "regular",
                            "sat_coef": 0.0,
                            "rule_managed": True,
                        }
                    )
                elif self._is_zero_lambda_regular_chemotaxis(existing):
                    existing.setdefault("rule_managed", True)

        # Drop stale placeholders created by this helper while preserving user-authored entries.
        for field_name, params in list(self.field_params.items()):
            entries = params.get("chemotaxis")
            if not isinstance(entries, list):
                continue

            filtered_entries = []
            for entry in entries:
                if not isinstance(entry, dict):
                    filtered_entries.append(entry)
                    continue
                entry_type = str(entry.get("cell_type") or entry.get("CellType") or "").strip()
                if entry.get("rule_managed") and (field_name, entry_type) not in active_pairs:
                    continue
                filtered_entries.append(entry)

            params["chemotaxis"] = filtered_entries

    @staticmethod
    def _is_zero_lambda_regular_chemotaxis(entry):
        try:
            lambda_value = float(entry.get("lambda", entry.get("Lambda", 0.0)) or 0.0)
        except (TypeError, ValueError):
            return False

        mode = str(entry.get("mode", entry.get("Mode", "regular")) or "regular").strip().lower()
        return lambda_value == 0.0 and mode in {"regular", "simple", "standard"}

    def export_to_xml(self):
            sm = StructureManager(self.project_path)

            for name in self.celltype_params.keys():
                sm.ensure_celltype(name, create_initializer=False)

            active_inits = {}
            for name, params in self.celltype_params.items():
                if params.get("should_initialize", True): # initialize by default
                    count = params.get("initial_count", 5)
                    active_inits[name] = count

            initial_layout = self.settings.get("initial_layout", {}) if isinstance(self.settings, dict) else {}
            layout_regions = None
            if isinstance(initial_layout, dict) and "regions" in initial_layout:
                layout_regions = initial_layout.get("regions") or []
            sm.update_initializers(active_inits, layout_regions=layout_regions)

            self._sync_pif_io_to_xml(sm)

            sm.save()
            print(f"✅ XML Updated: Initialized {list(active_inits.keys())}")

    def get_rule_by_id(self, rule_id):
        for rule in self.rules:
            if str(rule.get("id")) == str(rule_id):
                return rule
        return None
    
    def update_rule(self, rule_id, new_rule):
        for i, rule in enumerate(self.rules):
            if str(rule.get("id")) == str(rule_id):
                self.rules[i] = new_rule
                self._build_index() 
                self.save()
                print(f"✅ Rule {rule_id} updated and saved.")
                return True
        print(f"⚠️ Rule {rule_id} not found for update.")    
        return False
    
    def load_from_internal_json(self):
        """When the software starts or a project is loaded, restore the rules from the internal JSON."""
        if self.rules_path.exists():
            data = load_json(self.rules_path, None)
            if data is None:
                self._reset_state()
                return True
            self._apply_rules_data(data)
            return True
        return False

    def sync_with_xml(self):
        """
        Syncronize the celltypes in XML to registry,
        if there didn't exist then initialize them 
        """
        if self.sm is None:
            print("⚠️ [Sync] StructureManager not provided, skipping sync.")
            return

        xml_names = self.sm.get_xml_cell_types()
        xml_fields = self.sm.get_all_fields_from_xml()
        marker_volume_params = self._volume_params_from_steppable_markers()
        xml_volume_params = {}
        if hasattr(self.sm, "migrate_volume_data"):
            try:
                xml_volume_params = self.sm.migrate_volume_data()
            except Exception as exc:
                print(f"⚠️ [Sync] Could not read XML VolumeEnergyParameters: {exc}")
        initializer_summary = {}
        if hasattr(self.sm, "initializer_summary_by_type"):
            try:
                initializer_summary = self.sm.initializer_summary_by_type()
            except Exception as exc:
                print(f"⚠️ [Sync] Could not read XML initializer regions: {exc}")
        modified = False
        for name in xml_names:
            volume_params = self._volume_params_for_celltype(
                name,
                marker_volume_params,
                xml_volume_params,
            )
            if name not in self.celltype_params:
                print(f"🔗 [Sync] Adding XML cell type to registry: {name}")
                init_entry = initializer_summary.get(name, {})
                should_initialize = bool(init_entry.get("regions"))
                self.celltype_params[name] = {
                    "should_initialize": should_initialize,
                    "initial_count": int(init_entry.get("cells") or (5 if should_initialize else 0)),
                    "targetVolume": volume_params.get("targetVolume", 50.0),
                    "lambdaVolume": volume_params.get("lambdaVolume", 2.0)
                }
                modified = True
            elif isinstance(self.celltype_params.get(name), dict):
                params = self.celltype_params[name]
                for key in ("targetVolume", "lambdaVolume"):
                    if key not in params and key in volume_params:
                        params[key] = volume_params[key]
                        modified = True

        for f_name, params in xml_fields.items():
            # Use XML as a fallback only. The profile JSON is the project-level
            # source of truth once RuleParser has saved field parameters.
            if f_name not in self.field_params:
                self.field_params[f_name] = params
                modified = True
        
        if modified:
            self.save(rebuild_artifacts=False, quiet=True)

    @staticmethod
    def _volume_params_for_celltype(celltype_name, marker_volume_params, xml_volume_params):
        name = str(celltype_name)
        marker_params = marker_volume_params.get(name.upper(), {})

        xml_params = xml_volume_params.get(name, {})
        if not xml_params:
            for xml_name, params in xml_volume_params.items():
                if str(xml_name).lower() == name.lower():
                    xml_params = params
                    break

        return {**xml_params, **marker_params}

    def _volume_params_from_steppable_markers(self):
        if not self.py_path.exists():
            return {}

        try:
            content = self.py_path.read_text(encoding="utf-8")
        except OSError:
            return {}

        marker_pattern = re.compile(
            r"# === CC3D_VOLUME_(?P<name>[A-Z0-9_]+) START ===(?P<body>.*?)"
            r"# === CC3D_VOLUME_(?P=name) END ===",
            re.DOTALL,
        )
        value_pattern = re.compile(
            r"cell\.(?P<key>targetVolume|lambdaVolume)\s*=\s*"
            r"(?P<value>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
        )

        params_by_type = {}
        for marker in marker_pattern.finditer(content):
            params = {}
            for value_match in value_pattern.finditer(marker.group("body")):
                try:
                    params[value_match.group("key")] = float(value_match.group("value"))
                except ValueError:
                    continue
            if params:
                params_by_type[marker.group("name")] = params

        return params_by_type


    def add_field_params(self, field_name, params, autosave=True, rebuild_artifacts=False):
        # Unified conversion function
        def get_val(keys, default):
            for k in keys:
                if k in params: return params[k]
            return default

        normalized = {
            "solver": get_val(["solver", "Solver"], "DiffusionSolverFE"),
            "diffusion_constant": get_val(["diffusion_constant", "GlobalDiffusionConstant"], 0.1),
            "decay_constant": get_val(["decay_constant", "GlobalDecayConstant"], 0.001),
            "initial_expression": get_val(["initial_expression", "InitialConcentrationExpression"], "0.0"),
            "boundary_conditions": get_val(["boundary_conditions", "BoundaryConditions"], {}),
            "chemotaxis": get_val(["chemotaxis", "Chemotaxis"], []),
            "python_secretion": get_val(["python_secretion"], False)
        }

        # If the new parameters don’t include BC but the Registry already has it, it must be preserved!
        if not normalized["boundary_conditions"] and field_name in self.field_params:
            normalized["boundary_conditions"] = self.field_params[field_name].get("boundary_conditions", {})

        self.field_params[field_name] = normalized
        if autosave:
            self.save(rebuild_artifacts=rebuild_artifacts, quiet=not rebuild_artifacts)

    def get_all_fields(self):
        """Return a dictionary of all fields {field_name: params_dict}"""
        print(f"DEBUG: Current field_params in registry: {self.field_params}")
        return self.field_params

    def get_field_params(self, field_name):
        """Retrieve the configuration parameters of a single field by name."""
        return self.field_params.get(field_name, {})

    def update_field(self, field_name, new_data):
        """Update the configuration data of a specific field."""
        if field_name in self.field_params:
            self.field_params[field_name].update(new_data)
        else:
            self.field_params[field_name] = new_data
        self.save()
