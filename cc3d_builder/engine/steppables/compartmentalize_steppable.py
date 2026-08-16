# compartmentalize_steppable.py
import math
import random

from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.behaviour_stats import record_event, set_metric


class CompartmentalizeSteppable(SteppableBasePy):
    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        self._warned_fpp = False
        self._warned_cluster = False
        self._reported_fpp_success = False
        self._reported_visual_fpp_success = False
        self._reported_cluster_success = False
        self._reported_loaded = False
        self._reported_request_seen = False
        self._fpp_links_created = 0
        self._visual_fpp_links_created = 0
        self._last_fpp_diag_mcs = -1
        self._warned_fpp_inventory = False
        self._cluster_tip_claim_mcs = None
        self._cluster_tip_claims = {}
        self._cluster_branch_claim_mcs = None
        self._cluster_branch_claims = {}
        self._internal_link_pairs = set()
        self._visual_link_pairs = set()
        self._last_hypha_summary_mcs = -1
        if self.engine is not None:
            self.engine.register_executor("compartmentalize", self)
        print("[CompartmentalizeSteppable] loaded and registered")

    def step(self, mcs):
        return

    def execute(self, cell, request, mcs):
        self._execute_request(cell, request, mcs)

    def _execute_request(self, cell, request, mcs):
        action = str(request.get("action", "extend_chain")).strip().lower()
        print(f"[DEBUG] _execute_request: cell={cell.id if cell else None}, action={action}")
        self._maybe_report_runtime_state(cell, request, mcs)
        self._maybe_report_hypha_summary(mcs)
        if not self._reported_request_seen:
            print(
                "[CompartmentalizeSteppable] first request received: "
                f"mcs={mcs} cell={cell.id if cell is not None else None} action={action}"
            )
            self._reported_request_seen = True

        if action in {"initialize", "initialize_cluster", "init_cluster"}:
            self._initialize_cluster(cell, request, mcs)
        elif action in {"extend", "extend_chain"}:
            self._extend_chain(cell, request, mcs)
        elif action in {"branch", "branch_chain"}:
            self._branch_chain(cell, request, mcs)
        else:
            print(f"[CompartmentalizeSteppable] Unknown compartmentalize action: {action}")

    def _initialize_cluster(self, cell, request, mcs):
        self._mark_as_compartment(cell, request, mcs, is_tip=True)
        cell.dict.setdefault("hypha_length", 1)
        cell.dict.setdefault("branch_count", 0)

        # Mark initializer cells as root-seeds for optional first-tip authorization
        cell.dict.setdefault("compartment_is_root_seed", True)
        cell.dict.setdefault("compartment_first_tip_emitted", False)

        # Optional: allow initializer to grant the compartment extend permit for this seed
        if self._as_bool(request.get("compartment_can_extend", request.get("grant_compartment_extend", False))):
            cell.dict["compartment_can_extend"] = True

        record_event(cell, "compartmentalize", mcs)
        set_metric(cell, "compartmentalize", "action", "initialize_cluster")

        if request.get("debug"):
            print(f"[CompartmentalizeSteppable] initialized compartment seed cell={cell.id} cluster={cell.clusterId}")

        # Optionally create the first tip immediately during initialization.
        # Use request key "start_with_tip" (default True for backward compatibility).
        try:
            if self._as_bool(request.get("start_with_tip", True)):
                # Build a local request for extending where the segment_type defaults to
                # the current cell's type (e.g., HyphaRoot) so the conversion keeps root semantics.
                local_req = dict(request)
                local_req.setdefault("segment_type", self.get_type_name_by_cell(cell))
                local_req.setdefault("tip_type", request.get("tip_type", "HyphaTip"))
                local_req.setdefault("action", "extend_chain")
                if request.get("debug"):
                    print(f"[CompartmentalizeSteppable] initializing and immediately extending seed cell={cell.id}")
                self._extend_chain(cell, local_req, mcs)
        except Exception as exc:
            if request.get("debug"):
                print(f"[CompartmentalizeSteppable] failed to auto-extend during initialize_cluster: {exc}")

    def _extend_chain(self, tip_cell, request, mcs, direction_override=None):
        interval = max(1, int(self._to_float(request.get("extension_interval", 1), 1)))
        if not tip_cell.dict.get("compartment_enabled"):
            self._mark_as_compartment(tip_cell, request, mcs, is_tip=True)
            tip_cell.dict.setdefault("hypha_length", 1)
            tip_cell.dict.setdefault("branch_count", 0)
            tip_cell.dict["tip_seed_mcs"] = mcs
            if self._as_bool(request.get("delay_first_extension", False)):
                delay = max(0, int(self._to_float(request.get("initial_extension_delay", interval), interval)))
                tip_cell.dict["last_extension_mcs"] = mcs - max(0, interval - delay)
                if request.get("debug"):
                    print(
                        "[CompartmentalizeSteppable] seeded tip before first extension: "
                        f"cell={tip_cell.id} delay={delay}"
                    )
                return

        last_mcs = tip_cell.dict.get("last_extension_mcs")
        if last_mcs is not None and (mcs - last_mcs) < interval:
            return

        # Optional enforcement: only allow extension if the parent segment is permitted
        # request key: "compartment_single_extend_per_branch" (bool)
        if self._as_bool(request.get("compartment_single_extend_per_branch", False)):
            parent_segment_id = tip_cell.dict.get("parent_segment_id")
            if parent_segment_id is not None:
                allowed = False
                if self.cell_list is not None:
                    for candidate in self.cell_list:
                        if getattr(candidate, "id", None) == parent_segment_id:
                            allowed = bool(candidate.dict.get("compartment_can_extend", False))
                            break
                if not allowed:
                    if request.get("debug"):
                        print(
                            f"[CompartmentalizeSteppable] extension blocked: parent segment {parent_segment_id} not permitted to extend (cell={tip_cell.id})"
                        )
                    return

        max_length = self._to_float(request.get("max_length", 0), 0)
        current_length = self._to_float(tip_cell.dict.get("hypha_length", 1), 1)
        if max_length > 0 and current_length >= max_length:
            return
        current_branch_length = self._to_float(tip_cell.dict.get("branch_length", current_length), current_length)
        max_branch_length = self._to_float(request.get("max_branch_length", 0), 0)
        if (
            max_branch_length > 0
            and current_branch_length >= max_branch_length
            and self._branch_length_limit_applies(tip_cell, request)
        ):
            return

        segment_type_id = self._cell_type_id(request.get("segment_type") or request.get("cell_type"))
        tip_type_id = self._cell_type_id(request.get("tip_type") or request.get("segment_type") or request.get("cell_type"))
        if segment_type_id is None or tip_type_id is None:
            print(
                "[CompartmentalizeSteppable] Missing or unknown segment_type/tip_type: "
                f"segment={request.get('segment_type')}, tip={request.get('tip_type')}"
            )
            return

        if (
            direction_override is None
            and self._cluster_tip_selection_enabled(request)
            and not self._claim_cluster_tip_extension(
                tip_cell,
                request,
                mcs,
                interval,
                max_length,
                max_branch_length,
                tip_type_id,
            )
        ):
            return

        direction = direction_override or self._direction(tip_cell, request)
        if direction is None:
            if request.get("debug"):
                print(f"[CompartmentalizeSteppable] No valid extension direction for cell {tip_cell.id}")
            return
        direction = self._apply_direction_noise(direction, request)

        step_length = max(1.0, self._to_float(request.get("step_length", 1.0), 1.0))
        site = self._front_extension_site(
            tip_cell,
            direction,
            step_length,
            int(self._to_float(request.get("search_radius", 3), 3)),
            request,
        )
        if site is None:
            if request.get("debug"):
                print(f"[CompartmentalizeSteppable] No usable lattice site near tip cell {tip_cell.id}")
            return

        parent_cluster_id = tip_cell.clusterId
        previous_tip_id = tip_cell.id
        # capture previous type name before converting tip to a segment
        previous_tip_type = self.get_type_name_by_cell(tip_cell)
        previous_parent_id = tip_cell.dict.get("parent_segment_id")
        previous_parent = self._cell_by_id(previous_parent_id)
        root_type_id = self._cell_type_id(request.get("root_type", "HyphaRoot"))
        previous_parent_is_root = (
            previous_parent is not None
            and root_type_id is not None
            and getattr(previous_parent, "type", None) == root_type_id
        )
        first_tip_from_root = bool(tip_cell.dict.get("compartment_is_first_tip_from_root", False)) or previous_parent_is_root
        tip_cell.type = segment_type_id
        self._apply_celltype_constraints(tip_cell, request.get("segment_type"))
        tip_cell.dict["is_hypha_tip"] = False
        tip_cell.dict["is_compartment_tip"] = False
        tip_cell.dict["is_root_child_segment"] = first_tip_from_root
        tip_cell.dict["last_extension_mcs"] = mcs

        # Manage single-extend-per-branch state (generic compartment key)
        # Mark the segment produced by this tip as permitted to extend next,
        # and clear the allow-extend flag on its parent segment (if present).
        try:
            # If this tip was the first tip emitted from a root-seed, grant the resulting
            # segment the extend permit and clear the marker.
            if bool(tip_cell.dict.get("compartment_is_first_tip_from_root", False)):
                tip_cell.dict["compartment_can_extend"] = True
                # clear the marker so it doesn't re-grant later
                tip_cell.dict.pop("compartment_is_first_tip_from_root", None)
            else:
                # Ensure default is False to avoid accidental grants
                tip_cell.dict.setdefault("compartment_can_extend", False)

            # Clear permit from the parent segment if present
            parent_seg_id = tip_cell.dict.get("parent_segment_id")
            if parent_seg_id is not None and self.cell_list is not None:
                for cand in self.cell_list:
                    if getattr(cand, "id", None) == parent_seg_id:
                        cand.dict["compartment_can_extend"] = False
                        break
        except Exception:
            pass

        new_tip = self.new_cell(tip_type_id)
        self._copy_cell_constraints(tip_cell, new_tip)
        self._apply_celltype_constraints(new_tip, request.get("tip_type"))
        replaced_cell = self.cell_field[site[0], site[1], site[2]]
        if replaced_cell is not None:
            new_tip.dict["replaced_cell_id"] = replaced_cell.id
            new_tip.dict["replaced_cell_type"] = self.get_type_name_by_cell(replaced_cell)
        self.cell_field[site[0], site[1], site[2]] = new_tip
        new_tip.dict["seed_pixels"] = self._seed_tip_patch(new_tip, site, request)
        new_tip.dict["bridge_pixels"] = self._bridge_parent_to_tip(tip_cell, new_tip, site, request)
        self._reassign_cluster(new_tip, parent_cluster_id, request)

        # If the parent (pre-conversion) was a root-seed and hasn't emitted its first tip,
        # mark this new tip as the 'first tip from root' so that when it later becomes a
        # segment it will receive the extend permit.
        try:
            parent_was_root = (previous_tip_type == "HyphaRoot") or bool(tip_cell.dict.get("compartment_is_root_seed", False))
            if parent_was_root and not bool(tip_cell.dict.get("compartment_first_tip_emitted", False)):
                new_tip.dict["compartment_is_first_tip_from_root"] = True
                tip_cell.dict["compartment_first_tip_emitted"] = True
        except Exception:
            pass

        self._mark_as_compartment(new_tip, request, mcs, is_tip=True)
        new_tip.dict["parent_segment_id"] = previous_tip_id
        new_tip.dict["hypha_length"] = current_length + 1
        if self._as_bool(request.get("start_new_branch", False)):
            new_tip.dict["branch_length"] = 1
            new_tip.dict["branch_root_id"] = previous_tip_id
            new_tip.dict["branch_id"] = new_tip.id
            new_tip.dict["branch_is_lateral"] = True
        else:
            new_tip.dict["branch_length"] = current_branch_length + 1
            new_tip.dict["branch_root_id"] = tip_cell.dict.get("branch_root_id", previous_tip_id)
            new_tip.dict["branch_id"] = tip_cell.dict.get("branch_id", previous_tip_id)
            new_tip.dict["branch_is_lateral"] = bool(tip_cell.dict.get("branch_is_lateral", False))
        new_tip.dict["last_extension_mcs"] = mcs
        # New tip should not be granted extend-permission until it becomes a segment
        new_tip.dict.setdefault("compartment_can_extend", False)
        new_tip.dict["orientation_x"] = direction[0]
        new_tip.dict["orientation_y"] = direction[1]
        new_tip.dict["orientation_z"] = direction[2]

        if self._as_bool(request.get("use_fpp_link", False)):
            self._link_internal(tip_cell, new_tip, request)
        if self._as_bool(request.get("visualize_fpp_link", False)):
            self._link_visual(tip_cell, new_tip, request)

        record_event(new_tip, "compartmentalize", mcs)
        set_metric(new_tip, "compartmentalize", "action", "extend_chain")
        set_metric(new_tip, "compartmentalize", "length", current_length + 1)
        set_metric(new_tip, "compartmentalize", "parent_segment_id", previous_tip_id)

        if request.get("debug"):
            print(
                f"[CompartmentalizeSteppable] extended cluster={parent_cluster_id}: "
                f"old_tip={previous_tip_id} new_tip={new_tip.id} site={site}"
            )

    def _branch_chain(self, segment_cell, request, mcs):
        max_branches = int(self._to_float(
            request.get("max_branches_per_segment", request.get("max_branch_tips_per_segment", 1)),
            1,
        ))
        current_branches = int(self._to_float(segment_cell.dict.get("branch_count", 0), 0))
        if max_branches > 0 and current_branches >= max_branches:
            return

        branch_interval = max(1, int(self._to_float(
            request.get("branch_interval", request.get("extension_interval", 1)),
            1,
        )))
        last_branch_mcs = segment_cell.dict.get("last_branch_mcs")
        if last_branch_mcs is not None and (mcs - last_branch_mcs) < branch_interval:
            return

        if not self._branch_source_allowed(segment_cell, request):
            return

        # If single-extend-per-branch enforcement is enabled, require the segment to have the permit
        if self._as_bool(request.get("compartment_single_extend_per_branch", False)):
            if not bool(segment_cell.dict.get("compartment_can_extend", False)):
                if request.get("debug"):
                    print(
                        f"[CompartmentalizeSteppable] branch blocked: segment {segment_cell.id} not permitted to extend (cluster={getattr(segment_cell, 'clusterId', None)})"
                    )
                return

        max_branch_length = self._to_float(request.get("max_branch_length", 0), 0)
        if max_branch_length > 0 and max_branch_length <= 1:
            return

        segment_type_id = self._cell_type_id(request.get("segment_type") or request.get("cell_type"))
        tip_type_id = self._cell_type_id(request.get("tip_type") or request.get("segment_type") or request.get("cell_type"))
        if segment_type_id is None or tip_type_id is None:
            print(
                "[CompartmentalizeSteppable] Missing or unknown segment_type/tip_type for branch: "
                f"segment={request.get('segment_type')}, tip={request.get('tip_type')}"
            )
            return

        cluster_id = getattr(segment_cell, "clusterId", None)
        if not self._claim_cluster_branch_event(cluster_id, request, mcs, segment_cell, segment_type_id, branch_interval):
            return

        probability = self._to_float(request.get("branch_probability", 1.0), 1.0)
        if random.random() > max(0.0, min(1.0, probability)):
            return

        max_active_tips = int(self._to_float(request.get("max_active_tips_per_cluster", 0), 0))
        max_length = self._to_float(request.get("max_length", 0), 0)
        if (
            max_active_tips > 0
            and self._active_tip_count(cluster_id, tip_type_id, max_length, max_branch_length) >= max_active_tips
        ):
            return

        base_direction = self._direction(segment_cell, request) or (1.0, 0.0, 0.0)
        branch_direction = self._branch_direction(base_direction, request)
        if branch_direction is None:
            branch_direction = base_direction

        step_length = max(1.0, self._to_float(
            request.get("branch_step_length", request.get("step_length", 1.0)),
            1.0,
        ))
        site = self._front_extension_site(
            segment_cell,
            branch_direction,
            step_length,
            int(self._to_float(request.get("branch_search_radius", request.get("search_radius", 3)), 3)),
            request,
        )
        if site is None:
            if request.get("debug"):
                print(f"[CompartmentalizeSteppable] No usable branch site near segment cell {segment_cell.id}")
            return

        parent_cluster_id = segment_cell.clusterId
        new_tip = self.new_cell(tip_type_id)
        self._copy_cell_constraints(segment_cell, new_tip)
        self._apply_celltype_constraints(new_tip, request.get("tip_type"))
        replaced_cell = self.cell_field[site[0], site[1], site[2]]
        if replaced_cell is not None:
            new_tip.dict["replaced_cell_id"] = replaced_cell.id
            new_tip.dict["replaced_cell_type"] = self.get_type_name_by_cell(replaced_cell)
        self.cell_field[site[0], site[1], site[2]] = new_tip
        new_tip.dict["seed_pixels"] = self._seed_tip_patch(new_tip, site, request)
        new_tip.dict["bridge_pixels"] = self._bridge_parent_to_tip(segment_cell, new_tip, site, request)
        self._reassign_cluster(new_tip, parent_cluster_id, request)

        self._mark_as_compartment(new_tip, request, mcs, is_tip=True)
        new_tip.dict["parent_segment_id"] = segment_cell.id
        new_tip.dict["branch_root_id"] = segment_cell.id
        new_tip.dict["branch_length"] = 1
        new_tip.dict["branch_id"] = new_tip.id
        new_tip.dict["branch_is_lateral"] = True
        new_tip.dict["hypha_length"] = self._to_float(segment_cell.dict.get("hypha_length", 1), 1) + 1
        new_tip.dict["last_extension_mcs"] = mcs
        new_tip.dict["orientation_x"] = branch_direction[0]
        new_tip.dict["orientation_y"] = branch_direction[1]
        new_tip.dict["orientation_z"] = branch_direction[2]

        segment_cell.dict["branch_count"] = current_branches + 1
        segment_cell.dict["last_branch_mcs"] = mcs

        # Do not automatically reassign compartment_can_extend here; permission flow
        # is managed when tips convert to segments (extend logic) or via initializer.
        if self._as_bool(request.get("use_fpp_link", False)):
            self._link_internal(segment_cell, new_tip, request)
        if self._as_bool(request.get("visualize_fpp_link", False)):
            self._link_visual(segment_cell, new_tip, request)

        record_event(new_tip, "compartmentalize", mcs)
        set_metric(new_tip, "compartmentalize", "action", "branch_chain")
        set_metric(new_tip, "compartmentalize", "parent_segment_id", segment_cell.id)
        set_metric(new_tip, "compartmentalize", "branch_length", 1)
        set_metric(segment_cell, "compartmentalize", "branch_count", segment_cell.dict["branch_count"])

        if request.get("debug"):
            print(
                f"[CompartmentalizeSteppable] branched cluster={parent_cluster_id}: "
                f"segment={segment_cell.id} new_tip={new_tip.id} site={site}"
            )

    def _cluster_tip_selection_enabled(self, request):
        mode = str(
            request.get("cluster_tip_selection", request.get("tip_selection", ""))
        ).strip().lower()
        return (
            mode in {"random_one_per_cluster", "one_per_cluster", "random"}
            or self._as_bool(request.get("single_tip_per_cluster", False))
        )

    def _claim_cluster_tip_extension(
        self,
        tip_cell,
        request,
        mcs,
        interval,
        max_length,
        max_branch_length,
        tip_type_id,
    ):
        cluster_id = getattr(tip_cell, "clusterId", None)
        if cluster_id is None:
            return True

        if self._cluster_tip_claim_mcs != mcs:
            self._cluster_tip_claims = {}
            self._cluster_tip_claim_mcs = mcs

        group = str(request.get("tip_selection_group", "extend_chain"))
        key = (cluster_id, group)
        if key not in self._cluster_tip_claims:
            candidates = self._eligible_tip_ids(
                cluster_id,
                tip_type_id,
                mcs,
                interval,
                max_length,
                max_branch_length,
            )
            if not candidates:
                return False
            self._cluster_tip_claims[key] = random.choice(candidates)

        return self._cluster_tip_claims.get(key) == tip_cell.id

    def _eligible_tip_ids(self, cluster_id, tip_type_id, mcs, interval, max_length, max_branch_length):
        candidates = []
        if self.cell_list is None:
            return candidates

        for candidate in list(self.cell_list):
            if getattr(candidate, "clusterId", None) != cluster_id:
                continue
            if getattr(candidate, "type", None) != tip_type_id:
                continue
            if candidate.dict.get("is_dead") or not candidate.dict.get("is_hypha_tip"):
                continue
            last_mcs = candidate.dict.get("last_extension_mcs")
            if last_mcs is not None and (mcs - last_mcs) < interval:
                continue
            current_length = self._to_float(candidate.dict.get("hypha_length", 1), 1)
            if max_length > 0 and current_length >= max_length:
                continue
            current_branch_length = self._to_float(candidate.dict.get("branch_length", current_length), current_length)
            if max_branch_length > 0 and current_branch_length >= max_branch_length:
                continue
            candidates.append(candidate.id)

        return candidates

    def _claim_cluster_branch_event(self, cluster_id, request, mcs, segment_cell=None, segment_type_id=None, branch_interval=1):
        if cluster_id is None:
            return True
        if not self._as_bool(request.get("single_branch_per_cluster", True)):
            return True

        if self._cluster_branch_claim_mcs != mcs:
            self._cluster_branch_claims = {}
            self._cluster_branch_claim_mcs = mcs

        group = str(request.get("branch_selection_group", "branch_chain"))
        key = (cluster_id, group)
        if key not in self._cluster_branch_claims:
            candidates = self._eligible_branch_segment_ids(
                cluster_id,
                segment_type_id,
                request,
                mcs,
                branch_interval,
            )
            if not candidates and segment_cell is not None:
                candidates = [segment_cell.id]
            if not candidates:
                return False
            self._cluster_branch_claims[key] = random.choice(candidates)

        return segment_cell is not None and self._cluster_branch_claims.get(key) == segment_cell.id

    def _eligible_branch_segment_ids(self, cluster_id, segment_type_id, request, mcs, branch_interval):
        candidates = []
        if self.cell_list is None:
            return candidates

        max_branches = int(self._to_float(
            request.get("max_branches_per_segment", request.get("max_branch_tips_per_segment", 1)),
            1,
        ))
        for candidate in list(self.cell_list):
            if getattr(candidate, "clusterId", None) != cluster_id:
                continue
            if segment_type_id is not None and getattr(candidate, "type", None) != segment_type_id:
                continue
            if candidate.dict.get("is_dead"):
                continue
            if not self._branch_source_allowed(candidate, request):
                continue
            current_branches = int(self._to_float(candidate.dict.get("branch_count", 0), 0))
            if max_branches > 0 and current_branches >= max_branches:
                continue
            last_branch_mcs = candidate.dict.get("last_branch_mcs")
            if last_branch_mcs is not None and (mcs - last_branch_mcs) < branch_interval:
                continue
            if (
                self._as_bool(request.get("compartment_single_extend_per_branch", False))
                and not bool(candidate.dict.get("compartment_can_extend", False))
            ):
                continue
            candidates.append(candidate.id)

        return candidates

    def _branch_source_allowed(self, segment_cell, request):
        mode = str(
            request.get("branch_source_filter", request.get("branch_source", ""))
        ).strip().lower()
        root_adjacent_only = (
            mode in {"root_child", "root_adjacent", "segment1", "first_segment"}
            or self._as_bool(request.get("root_adjacent_only", False))
            or self._as_bool(request.get("branch_from_root_child_only", False))
        )
        if not root_adjacent_only:
            return True
        if bool(segment_cell.dict.get("is_root_child_segment", False)):
            return True

        parent = self._cell_by_id(segment_cell.dict.get("parent_segment_id"))
        root_type_id = self._cell_type_id(request.get("root_type", "HyphaRoot"))
        return parent is not None and root_type_id is not None and getattr(parent, "type", None) == root_type_id

    def _branch_length_limit_applies(self, tip_cell, request):
        if self._as_bool(request.get("limit_primary_branch_length", False)):
            return True
        return bool(tip_cell.dict.get("branch_is_lateral", False))

    def _active_tip_count(self, cluster_id, tip_type_id, max_length=0, max_branch_length=0):
        if cluster_id is None or self.cell_list is None:
            return 0
        active = 0
        for candidate in self.cell_list:
            if getattr(candidate, "clusterId", None) != cluster_id:
                continue
            if getattr(candidate, "type", None) != tip_type_id:
                continue
            if candidate.dict.get("is_dead") or not candidate.dict.get("is_hypha_tip"):
                continue
            current_length = self._to_float(candidate.dict.get("hypha_length", 1), 1)
            if max_length > 0 and current_length >= max_length:
                continue
            current_branch_length = self._to_float(candidate.dict.get("branch_length", current_length), current_length)
            if max_branch_length > 0 and current_branch_length >= max_branch_length:
                continue
            active += 1
        return active

    def _mark_as_compartment(self, cell, request, mcs, is_tip):
        cell.dict["compartment_enabled"] = True
        cell.dict["compartment_cluster_id"] = getattr(cell, "clusterId", None)
        cell.dict["compartment_action_mcs"] = mcs
        cell.dict["is_compartment_tip"] = bool(is_tip)
        cell.dict["is_hypha_tip"] = bool(is_tip)
        cell.dict.setdefault("orientation_x", self._to_float(request.get("dx", 1.0), 1.0))
        cell.dict.setdefault("orientation_y", self._to_float(request.get("dy", 0.0), 0.0))
        cell.dict.setdefault("orientation_z", self._to_float(request.get("dz", 0.0), 0.0))

    def _direction(self, cell, request):
        mode = str(request.get("direction_mode", request.get("mode", "stored_vector"))).strip().lower()

        if mode in {"stored_vector", "inherit_orientation"}:
            return self._normalize((
                self._dict_number(cell, "orientation_x", self._to_float(request.get("dx", 1.0), 1.0)),
                self._dict_number(cell, "orientation_y", self._to_float(request.get("dy", 0.0), 0.0)),
                self._dict_number(cell, "orientation_z", self._to_float(request.get("dz", 0.0), 0.0)),
            ))

        if mode == "vector":
            return self._normalize((
                self._to_float(request.get("dx", 1.0), 1.0),
                self._to_float(request.get("dy", 0.0), 0.0),
                self._to_float(request.get("dz", 0.0), 0.0),
            ))

        if mode == "random_persistent":
            direction = self._normalize((
                self._dict_number(cell, "orientation_x", 0.0),
                self._dict_number(cell, "orientation_y", 0.0),
                self._dict_number(cell, "orientation_z", 0.0),
            ))
            if direction is None:
                angle = random.random() * 2.0 * math.pi
                direction = (math.cos(angle), math.sin(angle), 0.0)
                cell.dict["orientation_x"] = direction[0]
                cell.dict["orientation_y"] = direction[1]
                cell.dict["orientation_z"] = direction[2]
            return direction

        if mode == "toward_position":
            return self._normalize((
                self._to_float(request.get("target_x", request.get("x", cell.xCOM)), cell.xCOM) - cell.xCOM,
                self._to_float(request.get("target_y", request.get("y", cell.yCOM)), cell.yCOM) - cell.yCOM,
                self._to_float(request.get("target_z", request.get("z", cell.zCOM)), cell.zCOM) - cell.zCOM,
            ))

        if mode in {"toward_nearest_type", "toward_nearest_tissue", "into_tissue"}:
            direction = self._nearest_type_direction(cell, request)
            if direction is not None:
                return direction
            return self._normalize((
                self._to_float(request.get("dx", 1.0), 1.0),
                self._to_float(request.get("dy", 0.0), 0.0),
                self._to_float(request.get("dz", 0.0), 0.0),
            ))

        if mode == "toward_field_gradient":
            return self._field_gradient_direction(cell, request)

        if mode == "inherit_force_vector":
            return self._normalize((-cell.lambdaVecX, -cell.lambdaVecY, -cell.lambdaVecZ))

        return None

    def _front_empty_site(self, cell, direction, step_length, search_radius, request=None):
        return self._front_extension_site(cell, direction, step_length, search_radius, request)

    def _front_extension_site(self, cell, direction, step_length, search_radius, request=None):
        request = request or {}
        target = (
            self._clamp_index(cell.xCOM + direction[0] * step_length, self.dim.x),
            self._clamp_index(cell.yCOM + direction[1] * step_length, self.dim.y),
            self._clamp_index(cell.zCOM + direction[2] * step_length, self.dim.z),
        )
        mode = str(request.get("site_selection_mode", "empty_first")).strip().lower()
        if mode in {"directional_replace_first", "directional_occupied_first", "line_replace_first"}:
            site = self._find_directional_replace_site(cell, direction, step_length, search_radius, request)
            if site is not None:
                return site
            if self._as_bool(request.get("require_replace_site", False)):
                return None
            return self._find_empty_site(target, search_radius)

        if mode in {"occupied_first", "replace_first", "host_first"}:
            site = self._find_replace_site(target, search_radius, request)
            if site is not None:
                return site
            return self._find_empty_site(target, search_radius)

        if mode in {"front_occupied_first", "front_replace_first"}:
            site = self._find_replace_site(target, 0, request)
            if site is not None:
                return site
            site = self._find_empty_site(target, search_radius)
            return site if site is not None else self._find_replace_site(target, search_radius, request)

        site = self._find_empty_site(target, search_radius)
        return site if site is not None else self._find_replace_site(target, search_radius, request)

    def _find_empty_site(self, target, search_radius):
        if self.cell_field[target[0], target[1], target[2]] is None:
            return target

        for radius in range(1, max(1, search_radius) + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    for dz in ([0] if self.dim.z <= 1 else range(-radius, radius + 1)):
                        x = self._clamp_index(target[0] + dx, self.dim.x)
                        y = self._clamp_index(target[1] + dy, self.dim.y)
                        z = self._clamp_index(target[2] + dz, self.dim.z)
                        if self.cell_field[x, y, z] is None:
                            return (x, y, z)
        return None

    def _find_replace_site(self, target, search_radius, request):
        replace_type_ids = self._replace_target_type_ids(request or {})
        if replace_type_ids:
            for radius in range(0, max(1, search_radius) + 1):
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        for dz in ([0] if self.dim.z <= 1 else range(-radius, radius + 1)):
                            x = self._clamp_index(target[0] + dx, self.dim.x)
                            y = self._clamp_index(target[1] + dy, self.dim.y)
                            z = self._clamp_index(target[2] + dz, self.dim.z)
                            occupant = self.cell_field[x, y, z]
                            if occupant is not None and occupant.type in replace_type_ids:
                                return (x, y, z)
        return None

    def _find_directional_replace_site(self, cell, direction, step_length, search_radius, request):
        replace_type_ids = self._replace_target_type_ids(request or {})
        if not replace_type_ids:
            return None

        best_site = None
        best_score = None
        target = (
            self._clamp_index(cell.xCOM + direction[0] * step_length, self.dim.x),
            self._clamp_index(cell.yCOM + direction[1] * step_length, self.dim.y),
            self._clamp_index(cell.zCOM + direction[2] * step_length, self.dim.z),
        )

        for radius in range(0, max(1, search_radius) + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    for dz in ([0] if self.dim.z <= 1 else range(-radius, radius + 1)):
                        x = self._clamp_index(target[0] + dx, self.dim.x)
                        y = self._clamp_index(target[1] + dy, self.dim.y)
                        z = self._clamp_index(target[2] + dz, self.dim.z)
                        occupant = self.cell_field[x, y, z]
                        if occupant is None or occupant.type not in replace_type_ids:
                            continue

                        vx = x - cell.xCOM
                        vy = y - cell.yCOM
                        vz = z - cell.zCOM
                        projection = vx * direction[0] + vy * direction[1] + vz * direction[2]
                        if projection <= 0:
                            continue

                        total_sq = vx * vx + vy * vy + vz * vz
                        perp_sq = max(0.0, total_sq - projection * projection)
                        axial_error = abs(projection - step_length)
                        score = (perp_sq, axial_error, total_sq)
                        if best_score is None or score < best_score:
                            best_score = score
                            best_site = (x, y, z)

        return best_site

    def _seed_tip_patch(self, cell, site, request):
        radius = max(0, int(self._to_float(request.get("tip_seed_radius", request.get("seed_radius", 1)), 1)))
        if radius <= 0:
            return 1

        replace_type_ids = self._replace_target_type_ids(request or {})
        seeded = 0
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                for dz in ([0] if self.dim.z <= 1 else range(-radius, radius + 1)):
                    if self.dim.z > 1 and dx * dx + dy * dy + dz * dz > radius * radius:
                        continue
                    x = self._clamp_index(site[0] + dx, self.dim.x)
                    y = self._clamp_index(site[1] + dy, self.dim.y)
                    z = self._clamp_index(site[2] + dz, self.dim.z)
                    occupant = self.cell_field[x, y, z]
                    if occupant is None or occupant is cell or occupant.type in replace_type_ids:
                        self.cell_field[x, y, z] = cell
                        seeded += 1
        return max(1, seeded)

    def _bridge_parent_to_tip(self, parent_cell, child_cell, site, request):
        if not self._as_bool(request.get("bridge_to_tip", True)):
            return 0

        replace_type_ids = self._replace_target_type_ids(request or {})
        start = (float(parent_cell.xCOM), float(parent_cell.yCOM), float(parent_cell.zCOM))
        end = (float(site[0]), float(site[1]), float(site[2]))
        steps = int(max(abs(end[0] - start[0]), abs(end[1] - start[1]), abs(end[2] - start[2])))
        if steps <= 1:
            return 0

        bridged = 0
        for index in range(1, steps):
            fraction = index / float(steps)
            x = self._clamp_index(start[0] + (end[0] - start[0]) * fraction, self.dim.x)
            y = self._clamp_index(start[1] + (end[1] - start[1]) * fraction, self.dim.y)
            z = self._clamp_index(start[2] + (end[2] - start[2]) * fraction, self.dim.z)
            occupant = self.cell_field[x, y, z]
            if (
                occupant is None
                or occupant is parent_cell
                or occupant is child_cell
                or occupant.type in replace_type_ids
            ):
                self.cell_field[x, y, z] = parent_cell
                bridged += 1
        return bridged

    def _apply_direction_noise(self, direction, request):
        noise = self._to_float(request.get("direction_noise", request.get("angle_noise", 0.0)), 0.0)
        if noise <= 0.0:
            return direction

        angle = math.atan2(direction[1], direction[0])
        angle += random.uniform(-noise, noise)
        z = direction[2]
        noisy = self._normalize((math.cos(angle), math.sin(angle), z))
        return noisy or direction

    def _branch_direction(self, base_direction, request):
        base = self._normalize(base_direction)
        if base is None:
            return None

        mode = str(request.get("branch_direction_mode", "angle")).strip().lower()
        if mode in {"random", "random_persistent"}:
            angle = random.random() * 2.0 * math.pi
            return self._normalize((math.cos(angle), math.sin(angle), base[2]))

        min_angle = request.get("branch_angle_min_degrees", request.get("branch_min_angle_degrees"))
        max_angle = request.get("branch_angle_max_degrees", request.get("branch_max_angle_degrees"))
        if min_angle is not None or max_angle is not None:
            low = self._to_float(min_angle, 30.0)
            high = self._to_float(max_angle, 60.0)
            if high < low:
                low, high = high, low
            angle_degrees = random.uniform(low, high)
        else:
            angle_degrees = self._to_float(
                request.get("branch_angle_degrees", request.get("branch_angle", 45.0)),
                45.0,
            )
            jitter_degrees = self._to_float(
                request.get("branch_angle_jitter_degrees", request.get("branch_angle_jitter", 0.0)),
                0.0,
            )
            angle_degrees += random.uniform(-jitter_degrees, jitter_degrees)
        sign = -1.0 if random.random() < 0.5 else 1.0
        angle = math.atan2(base[1], base[0])
        branch_angle = math.radians(angle_degrees)
        angle += sign * branch_angle
        return self._normalize((math.cos(angle), math.sin(angle), base[2]))

    def _replace_target_type_ids(self, request):
        if not self._as_bool(request.get("allow_occupied_site", request.get("allow_replace", False))):
            return set()

        raw_types = (
            request.get("replace_target_types")
            or request.get("replace_types")
            or request.get("target_types")
            or request.get("target_type")
            or []
        )
        if isinstance(raw_types, str):
            raw_types = [part.strip() for part in raw_types.split(",") if part.strip()]

        type_ids = set()
        for type_name in raw_types:
            type_id = self._cell_type_id(type_name)
            if type_id is not None:
                type_ids.add(type_id)
        return type_ids

    def _field_gradient_direction(self, cell, request):
        field_name = request.get("field_name") or request.get("field")
        if not field_name:
            return None

        try:
            field = getattr(self.field, str(field_name))
        except Exception:
            return None

        step = max(1, int(self._to_float(request.get("gradient_step", 1), 1)))
        x = self._clamp_index(cell.xCOM, self.dim.x)
        y = self._clamp_index(cell.yCOM, self.dim.y)
        z = self._clamp_index(cell.zCOM, self.dim.z)
        x0, x1 = max(0, x - step), min(self.dim.x - 1, x + step)
        y0, y1 = max(0, y - step), min(self.dim.y - 1, y + step)
        z0, z1 = max(0, z - step), min(self.dim.z - 1, z + step)

        try:
            gx = float(field[x1, y, z]) - float(field[x0, y, z])
            gy = float(field[x, y1, z]) - float(field[x, y0, z])
            gz = 0.0 if self.dim.z <= 1 else float(field[x, y, z1]) - float(field[x, y, z0])
        except Exception:
            return None

        return self._normalize((gx, gy, gz))

    def _nearest_type_direction(self, cell, request):
        type_names = self._direction_target_type_names(request)
        if not type_names:
            return None

        max_distance = self._to_float(
            request.get("direction_search_radius", request.get("max_direction_distance", 0.0)),
            0.0,
        )
        max_dist_sq = max_distance * max_distance if max_distance > 0 else None
        best = None
        best_dist = float("inf")

        for type_name in type_names:
            type_id = self._cell_type_id(type_name)
            if type_id is None:
                continue
            for candidate in self.cell_list_by_type(type_id):
                if candidate.id == cell.id or candidate.dict.get("is_dead"):
                    continue
                dist = (
                    (candidate.xCOM - cell.xCOM) ** 2
                    + (candidate.yCOM - cell.yCOM) ** 2
                    + (candidate.zCOM - cell.zCOM) ** 2
                )
                if max_dist_sq is not None and dist > max_dist_sq:
                    continue
                if dist < best_dist:
                    best = candidate
                    best_dist = dist

        if best is None:
            return None
        return self._normalize((best.xCOM - cell.xCOM, best.yCOM - cell.yCOM, best.zCOM - cell.zCOM))

    def _direction_target_type_names(self, request):
        raw_types = (
            request.get("direction_target_types")
            or request.get("direction_target_type")
            or request.get("direction_type")
            or request.get("target_cell_type")
        )
        if raw_types is None:
            raw_types = request.get("target_type") if "direction_target_types" in request else None

        if raw_types is None:
            return []
        if isinstance(raw_types, str):
            return [part.strip() for part in raw_types.split(",") if part.strip()]
        if isinstance(raw_types, (list, tuple, set)):
            return [str(part).strip() for part in raw_types if str(part).strip()]
        return [str(raw_types).strip()]

    def _copy_cell_constraints(self, source_cell, new_cell):
        for attr in ("targetVolume", "lambdaVolume", "targetSurface", "lambdaSurface", "fluctAmpl"):
            try:
                setattr(new_cell, attr, getattr(source_cell, attr))
            except Exception:
                pass

    def _apply_celltype_constraints(self, cell, type_name):
        if self.engine is None or not type_name:
            return

        params = getattr(self.engine, "celltype_params", {}).get(str(type_name), {})
        if not params:
            return

        for param_key, attr_name in (
            ("targetVolume", "targetVolume"),
            ("lambdaVolume", "lambdaVolume"),
            ("targetSurface", "targetSurface"),
            ("lambdaSurface", "lambdaSurface"),
            ("fluctAmpl", "fluctAmpl"),
        ):
            if param_key in params:
                try:
                    setattr(cell, attr_name, params[param_key])
                except Exception:
                    pass

    def _reassign_cluster(self, cell, cluster_id, request):
        try:
            self.reassign_cluster_id(cell=cell, cluster_id=cluster_id)
            if not self._reported_cluster_success:
                print(
                    "[CompartmentalizeSteppable] cluster reassignment active: "
                    f"cell={cell.id} cluster={cell.clusterId}"
                )
                self._reported_cluster_success = True
        except Exception as exc:
            if request.get("debug") or not self._warned_cluster:
                print(f"[CompartmentalizeSteppable] Could not reassign cluster id; keeping logical chain only: {exc}")
                self._warned_cluster = True

    def _link_internal(self, cell_a, cell_b, request):
        lambda_distance = self._to_float(request.get("link_lambda", request.get("lambda_distance", 10.0)), 10.0)
        target_distance = self._to_float(request.get("target_distance", 0.0), 0.0)
        max_distance = self._to_float(request.get("max_distance", 0.0), 0.0)
        pair_key = self._link_pair_key(cell_a, cell_b)
        if pair_key in self._internal_link_pairs:
            return

        try:
            if self._internal_link_exists(cell_a, cell_b):
                self._internal_link_pairs.add(pair_key)
                return
            link = self.new_fpp_internal_link(cell_a, cell_b, lambda_distance, target_distance, max_distance)
            if link is None and not self._warned_fpp:
                print("[CompartmentalizeSteppable] FocalPointPlasticity plugin is not loaded; internal link skipped.")
                self._warned_fpp = True
            elif link is not None:
                self._internal_link_pairs.add(pair_key)
                self._fpp_links_created += 1
                if not self._reported_fpp_success:
                    print(
                        "[CompartmentalizeSteppable] FPP internal link active: "
                        f"created={self._fpp_links_created} "
                        f"cell_a={cell_a.id} cell_b={cell_b.id} "
                        f"lambda={lambda_distance} target={target_distance} max={max_distance}"
                    )
                    self._reported_fpp_success = True
        except Exception as exc:
            if request.get("debug") or not self._warned_fpp:
                print(f"[CompartmentalizeSteppable] Failed to create internal FPP link: {exc}")
                self._warned_fpp = True

    def _internal_link_exists(self, cell_a, cell_b):
        try:
            return self.get_fpp_internal_link_by_cells(cell_a, cell_b) is not None
        except Exception:
            return False

    def _link_visual(self, cell_a, cell_b, request):
        lambda_distance = self._to_float(
            request.get("visual_link_lambda", request.get("link_lambda", request.get("lambda_distance", 10.0))),
            10.0,
        )
        target_distance = self._to_float(
            request.get("visual_target_distance", request.get("target_distance", 0.0)),
            0.0,
        )
        max_distance = self._to_float(
            request.get("visual_max_distance", request.get("max_distance", 0.0)),
            0.0,
        )
        pair_key = self._link_pair_key(cell_a, cell_b)
        if pair_key in self._visual_link_pairs:
            return

        try:
            link = self.new_fpp_link(cell_a, cell_b, lambda_distance, target_distance, max_distance)
            if link is None and not self._warned_fpp:
                print("[CompartmentalizeSteppable] FocalPointPlasticity plugin is not loaded; visual link skipped.")
                self._warned_fpp = True
            elif link is not None:
                self._visual_link_pairs.add(pair_key)
                self._visual_fpp_links_created += 1
                if not self._reported_visual_fpp_success:
                    print(
                        "[CompartmentalizeSteppable] FPP visual link active: "
                        f"created={self._visual_fpp_links_created} "
                        f"cell_a={cell_a.id} cell_b={cell_b.id} "
                        f"lambda={lambda_distance} target={target_distance} max={max_distance}"
                    )
                    self._reported_visual_fpp_success = True
        except Exception as exc:
            if request.get("debug") or not self._warned_fpp:
                print(f"[CompartmentalizeSteppable] Failed to create visual FPP link: {exc}")
                self._warned_fpp = True

    def _link_pair_key(self, cell_a, cell_b):
        return tuple(sorted((int(cell_a.id), int(cell_b.id))))

    def _maybe_report_runtime_state(self, cell, request, mcs):
        if not (request.get("debug") or request.get("fpp_diagnostics")):
            return

        interval = max(1, int(self._to_float(request.get("fpp_diagnostic_interval", 100), 100)))
        if self._last_fpp_diag_mcs >= 0 and (mcs - self._last_fpp_diag_mcs) < interval:
            return

        self._last_fpp_diag_mcs = mcs
        cluster_id = getattr(cell, "clusterId", None)
        compartment_cells = self._compartment_cell_count(cluster_id)
        inventory_count = self._internal_fpp_inventory_count()
        # count of segments/segments permitted to extend (generic compartment key)
        try:
            extend_permit_count = sum(
                1 for candidate in (self.cell_list or []) if bool(getattr(candidate, 'dict', {}).get('compartment_can_extend'))
            )
        except Exception:
            extend_permit_count = 'unknown'

        print(
            "[CompartmentalizeSteppable] runtime state: "
            f"mcs={mcs} cell={getattr(cell, 'id', None)} cluster={cluster_id} "
            f"compartment_cells={compartment_cells} "
            f"internal_links_created={self._fpp_links_created} "
            f"internal_link_inventory={inventory_count} "
            f"visual_links_created={self._visual_fpp_links_created} "
            f"visual_link_inventory={self._visual_fpp_inventory_count()} "
            f"hypha_length={cell.dict.get('hypha_length') if cell is not None else None} "
            f"is_tip={cell.dict.get('is_hypha_tip') if cell is not None else None} "
            f"compartment_extend_permit_count={extend_permit_count}"
        )

    def _internal_fpp_inventory_count(self):
        try:
            links = self.get_focal_point_plasticity_internal_link_list()
            return len(links) if links is not None else 0
        except Exception as exc:
            if not self._warned_fpp_inventory:
                print(f"[CompartmentalizeSteppable] Could not inspect internal FPP inventory: {exc}")
                self._warned_fpp_inventory = True
            return "unavailable"

    def _visual_fpp_inventory_count(self):
        try:
            links = self.get_focal_point_plasticity_link_list()
            return len(links) if links is not None else 0
        except Exception as exc:
            if not self._warned_fpp_inventory:
                print(f"[CompartmentalizeSteppable] Could not inspect visual FPP inventory: {exc}")
                self._warned_fpp_inventory = True
            return "unavailable"

    def _compartment_cell_count(self, cluster_id):
        if cluster_id is None or self.cell_list is None:
            return "unknown"
        try:
            return sum(
                1
                for candidate in self.cell_list
                if getattr(candidate, "clusterId", None) == cluster_id
                and bool(getattr(candidate, "dict", {}).get("compartment_enabled"))
            )
        except Exception:
            return "unknown"

    def _maybe_report_hypha_summary(self, mcs):
        interval = 100
        try:
            settings = getattr(self.engine, "settings", {}) if self.engine is not None else {}
            interval = int(self._to_float(settings.get("hypha_summary_interval", interval), interval))
        except Exception:
            interval = 100

        if interval <= 0:
            return
        if self._last_hypha_summary_mcs >= 0 and (mcs - self._last_hypha_summary_mcs) < interval:
            return

        summary = self._hypha_summary_counts()
        hypha_total = summary["HyphaRoot"] + summary["HyphaSegment"] + summary["HyphaTip"]
        if hypha_total <= 0 and summary["AttachedFungus"] <= 0:
            return

        self._last_hypha_summary_mcs = mcs
        print(
            "[CompartmentalizeSteppable] hypha summary: "
            f"mcs={mcs} "
            f"attached={summary['AttachedFungus']} "
            f"root={summary['HyphaRoot']} "
            f"segment={summary['HyphaSegment']} "
            f"tip={summary['HyphaTip']} "
            f"active_tips={summary['active_tips']} "
            f"clusters={summary['clusters']} "
            f"expected_tree_links={summary['expected_tree_links']} "
            f"internal_links={self._internal_fpp_inventory_count()} "
            f"visual_links={self._visual_fpp_inventory_count()}"
        )

    def _hypha_summary_counts(self):
        names = ["AttachedFungus", "HyphaRoot", "HyphaSegment", "HyphaTip"]
        summary = {name: 0 for name in names}
        summary["active_tips"] = 0
        summary["clusters"] = 0
        summary["expected_tree_links"] = 0

        if self.cell_list is None:
            return summary

        type_ids = {name: self._cell_type_id(name) for name in names}
        type_id_to_name = {type_id: name for name, type_id in type_ids.items() if type_id is not None}
        hypha_type_ids = {
            type_ids.get("HyphaRoot"),
            type_ids.get("HyphaSegment"),
            type_ids.get("HyphaTip"),
        }
        hypha_type_ids.discard(None)

        clusters = set()
        for candidate in list(self.cell_list):
            name = type_id_to_name.get(getattr(candidate, "type", None))
            if not name:
                continue
            summary[name] += 1
            if getattr(candidate, "type", None) in hypha_type_ids:
                clusters.add(getattr(candidate, "clusterId", None))
            if name == "HyphaTip" and candidate.dict.get("is_hypha_tip") and not candidate.dict.get("is_dead"):
                summary["active_tips"] += 1

        clusters.discard(None)
        summary["clusters"] = len(clusters)
        hypha_total = summary["HyphaRoot"] + summary["HyphaSegment"] + summary["HyphaTip"]
        summary["expected_tree_links"] = max(0, hypha_total - summary["clusters"])
        return summary

    def _cell_type_id(self, type_name):
        if not type_name:
            return None
        type_attr = str(type_name).strip().upper()
        return getattr(self, type_attr, getattr(self.engine, type_attr, None))

    def _cell_by_id(self, cell_id):
        try:
            target_id = int(float(cell_id))
        except (TypeError, ValueError):
            return None
        if self.cell_list is None:
            return None
        for candidate in self.cell_list:
            if getattr(candidate, "id", None) == target_id:
                return candidate
        return None

    def _dict_number(self, cell, key, default):
        if key in cell.dict:
            return self._to_float(cell.dict.get(key), default)
        state = cell.dict.get("state", {})
        if isinstance(state, dict) and key in state:
            return self._to_float(state.get(key), default)
        return default

    def _normalize(self, vec):
        x, y, z = vec
        norm = math.sqrt(x * x + y * y + z * z)
        if norm <= 0.0 or not math.isfinite(norm):
            return None
        return (x / norm, y / norm, z / norm)

    def _clamp_index(self, value, upper):
        if upper <= 1:
            return 0
        return max(0, min(upper - 1, int(round(value))))

    def _to_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _as_bool(self, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "y"}
