# state_key_catalog.py
STATE_KEY_CATALOG = [
    {
        "category": "Global simulation",
        "source": "RuleEngine runtime context.",
        "items": [
            ("mcs", "Current Monte Carlo Step."),
        ],
    },
    {
        "category": "CC3D native cell attributes",
        "source": "Read from native cell attributes, e.g. cell.targetVolume. Use the variable name below in expressions.",
        "items": [
            ("cell_id", "cell.id", "Cell id."),
            ("cell_type", "cell.type", "Numeric CC3D cell type id."),
            ("type_id", "cell.type", "Alias of cell_type."),
            ("volume", "cell.volume", "Current cell volume."),
            ("surface", "cell.surface", "Current cell surface, if available."),
            ("targetVolume", "cell.targetVolume", "Current target volume."),
            ("lambdaVolume", "cell.lambdaVolume", "Current volume constraint lambda."),
            ("targetSurface", "cell.targetSurface", "Current target surface, if available."),
            ("lambdaSurface", "cell.lambdaSurface", "Current surface constraint lambda, if available."),
            ("xCOM", "cell.xCOM", "X coordinate of center of mass."),
            ("yCOM", "cell.yCOM", "Y coordinate of center of mass."),
            ("zCOM", "cell.zCOM", "Z coordinate of center of mass."),
            ("xCM", "cell.xCM", "Alternative CC3D X center coordinate, if available."),
            ("yCM", "cell.yCM", "Alternative CC3D Y center coordinate, if available."),
            ("zCM", "cell.zCM", "Alternative CC3D Z center coordinate, if available."),
            ("eccentricity", "cell.eccentricity", "Cell eccentricity, if MomentOfInertia data is available."),
            ("ecc", "cell.ecc", "Alternative eccentricity attribute, if available."),
            ("cluster_id", "cell.clusterId", "Cluster id, if available."),
            ("lambdaVecX", "cell.lambdaVecX", "Current ExternalPotential x component."),
            ("lambdaVecY", "cell.lambdaVecY", "Current ExternalPotential y component."),
            ("lambdaVecZ", "cell.lambdaVecZ", "Current ExternalPotential z component."),
        ],
    },
    {
        "category": "Cell built-in flags and counters",
        "source": "Read from top-level cell.dict keys, e.g. cell.dict['division_count'].",
        "items": [
            ("division_count", "Top-level division counter maintained by division rules."),
            ("phago_count", "Top-level completed phagocytosis counter."),
            ("dormant", "Boolean flag: 1 when the cell is dormant, otherwise 0."),
            ("is_dead", "Boolean flag: 1 after a death program starts, otherwise 0."),
            ("orientation_x", "Top-level persisted orientation vector x component."),
            ("orientation_y", "Top-level persisted orientation vector y component."),
            ("orientation_z", "Top-level persisted orientation vector z component."),
            ("compartment_enabled", "Boolean flag: 1 after a compartmentalize rule initializes/extends this cell."),
            ("is_compartment_tip", "Boolean flag: 1 when this cell is currently the active compartment tip."),
            ("is_hypha_tip", "Alias flag for fungal-tip use cases."),
            ("hypha_length", "Logical chain length copied to the current tip during compartment extension."),
            ("branch_count", "Number of branch attempts recorded on this compartment chain."),
            ("parent_segment_id", "Cell id of the previous segment that created this tip."),
        ],
    },
    {
        "category": "Creation stats",
        "source": "Read from cell.dict and flattened cell.dict['behaviour_stats']['create'].",
        "items": [
            ("created_mcs", "MCS when this cell was created by a create rule."),
            ("behaviour_stats_create_count", "Number of create events recorded on this cell."),
            ("behaviour_stats_create_first_mcs", "First MCS when create was recorded."),
            ("behaviour_stats_create_last_mcs", "Last MCS when create was recorded."),
        ],
    },
    {
        "category": "Division and type-switch stats",
        "source": "Read from flattened cell.dict['behaviour_stats']['division'] and ['type_switch'].",
        "items": [
            ("behaviour_stats_division_count", "Division count mirrored into the unified stats tree."),
            ("behaviour_stats_division_last_mcs", "Last MCS when division completed."),
            ("behaviour_stats_type_switch_count", "Number of completed type-switch events."),
            ("behaviour_stats_type_switch_last_mcs", "Last MCS when type-switch completed."),
        ],
    },
    {
        "category": "Growth stats",
        "source": "Read from flattened cell.dict['behaviour_stats']['growth'].",
        "items": [
            ("behaviour_stats_growth_active", "Boolean flag: 1 after growth has been activated."),
            ("behaviour_stats_growth_active_since_mcs", "First MCS of the current/last growth active period."),
            ("behaviour_stats_growth_last_active_mcs", "Last MCS when growth was applied."),
            ("behaviour_stats_growth_active_duration", "Number of MCS ticks where growth was applied."),
            ("behaviour_stats_growth_last_delta", "Most recent growth targetVolume increment."),
            ("behaviour_stats_growth_total_delta", "Accumulated growth targetVolume increment."),
        ],
    },
    {
        "category": "Dormancy stats",
        "source": "Read from flattened cell.dict['behaviour_stats']['dormancy'].",
        "items": [
            ("behaviour_stats_dormancy_count", "Number of dormancy/reactivation state-change events."),
            ("behaviour_stats_dormancy_active", "Boolean flag: 1 while the cell is dormant."),
            ("behaviour_stats_dormancy_active_since_mcs", "MCS when the cell entered the current/last dormant period."),
            ("behaviour_stats_dormancy_last_active_mcs", "Last MCS when the cell was observed dormant."),
            ("behaviour_stats_dormancy_active_duration", "Number of MCS ticks spent in dormancy."),
            ("behaviour_stats_dormancy_inactive_duration", "MCS gap since the latest dormancy active tick after reactivation."),
        ],
    },
    {
        "category": "Death stats",
        "source": "Read from flattened cell.dict['behaviour_stats']['death'].",
        "items": [
            ("behaviour_stats_death_count", "Number of times this cell entered a death program."),
            ("behaviour_stats_death_active", "Boolean flag: 1 after the death program starts."),
            ("behaviour_stats_death_active_since_mcs", "MCS when death program started."),
            ("behaviour_stats_death_last_active_mcs", "Last MCS when death state was updated."),
            ("behaviour_stats_death_active_duration", "Number of MCS ticks spent in death program."),
        ],
    },
    {
        "category": "Phagocytosis stats",
        "source": "Read from phago_count and flattened cell.dict['behaviour_stats']['phagocytosis'].",
        "items": [
            ("behaviour_stats_phagocytosis_count", "Completed phagocytosis events, synced with phago_count."),
            ("behaviour_stats_phagocytosis_active", "Boolean flag: 1 after phagocytosis has acted."),
            ("behaviour_stats_phagocytosis_active_duration", "Number of MCS ticks where phagocytosis acted."),
            ("behaviour_stats_phagocytosis_last_delta", "Most recent eaten volume amount."),
            ("behaviour_stats_phagocytosis_total_delta", "Accumulated eaten volume amount."),
        ],
    },
    {
        "category": "Secretion and uptake stats",
        "source": "Read from flattened cell.dict['behaviour_stats']['secrete_uptake']. When TotalCount mode is enabled, amounts come from CC3D Secretor result.tot_amount.",
        "items": [
            ("behaviour_stats_secrete_uptake_active", "Boolean flag: 1 after secretion/uptake has acted."),
            ("behaviour_stats_secrete_uptake_active_duration", "Number of MCS ticks where secretion/uptake acted."),
            ("behaviour_stats_secrete_uptake_last_delta", "Most recent absolute secreted/uptaken amount; uses CC3D result.tot_amount when TotalCount is active."),
            ("behaviour_stats_secrete_uptake_total_delta", "Accumulated absolute secreted/uptaken amount across fields."),
            ("behaviour_stats_secrete_uptake_<FIELD>_last_delta", "Most recent amount for one field, e.g. Oxygen; uses CC3D result.tot_amount when TotalCount is active."),
            ("behaviour_stats_secrete_uptake_<FIELD>_total_delta", "Accumulated amount for one field, e.g. Oxygen."),
        ],
    },
    {
        "category": "CC3D Secretor total-count return values",
        "source": "Returned by CC3D Secretor methods ending with TotalCount as result.tot_amount, then cached in cell.dict for later rule expressions.",
        "items": [
            ("persistent_tracking_<FIELD>", "cell.dict['persistent_tracking'][field_name]", "Cumulative CC3D result.tot_amount for one field, e.g. persistent_tracking_Oxygen."),
        ],
    },
    {
        "category": "CC3D field values",
        "source": "Read from the CC3D concentration field at the cell center through RuleEngine.get_field_value(field_name, cell).",
        "items": [
            ("<FIELD>", "self.field.<FIELD>[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)]", "Field value at the cell center, e.g. Oxygen or VEGF when used as a physical-model regulator."),
        ],
    },
    {
        "category": "Intracellular model state",
        "source": "Read from cell.dict['intracellular'][model_name][variable] after intracellular input/output synchronization.",
        "items": [
            ("intracellular_<MODEL>_<VAR>", "Flattened intracellular cache, e.g. intracellular_DN_NICD."),
            ("intracellular_<MODEL>_last_step_mcs", "Last MCS when the intracellular model was advanced or synchronized."),
            ("state_<KEY>", "Optional output mapping target for rule-readable state values."),
        ],
    },
    {
        "category": "Subcellular subsystem state",
        "source": "Read from cell.dict['subcellular'][system]. These values are coarse-grained internal cell states, not CC3D cell types or compartment clusters.",
        "items": [
            ("subcellular_<SYSTEM>_stage", "Current assembly or internal state label, e.g. subcellular_npc_stage."),
            ("subcellular_<SYSTEM>_components_<COMPONENT>", "Component count, e.g. subcellular_npc_components_nup107."),
            ("subcellular_<SYSTEM>_localization_<LOCATION>", "Localization amount/fraction, e.g. subcellular_npc_localization_nuclear_envelope."),
            ("behaviour_stats_subcellular_action", "Latest subcellular action executed on this cell."),
            ("behaviour_stats_subcellular_system", "Latest subcellular system updated on this cell."),
        ],
    },
    {
        "category": "Chemotaxis stats",
        "source": "Read from flattened cell.dict['behaviour_stats']['chemotaxis'].",
        "items": [
            ("behaviour_stats_chemotaxis_active", "Boolean flag: 1 after chemotaxis was configured."),
            ("behaviour_stats_chemotaxis_active_since_mcs", "MCS when chemotaxis was first configured."),
            ("behaviour_stats_chemotaxis_last_active_mcs", "Last MCS where chemotaxis remained active."),
            ("behaviour_stats_chemotaxis_active_duration", "Number of MCS ticks where chemotaxis remained active."),
            ("behaviour_stats_chemotaxis_lambda", "Latest chemotaxis lambda value."),
        ],
    },
    {
        "category": "Force stats",
        "source": "Read from native lambdaVec values and flattened cell.dict['behaviour_stats']['force'].",
        "items": [
            ("behaviour_stats_force_active", "Boolean flag: 1 after ExternalPotential force has been applied."),
            ("behaviour_stats_force_active_duration", "Number of MCS ticks where force was applied."),
            ("behaviour_stats_force_last_delta", "Most recent absolute force magnitude."),
            ("behaviour_stats_force_total_delta", "Accumulated absolute force magnitude over active ticks."),
            ("behaviour_stats_force_force", "Latest requested force magnitude."),
            ("behaviour_stats_force_dir_x", "Latest normalized force direction x component."),
            ("behaviour_stats_force_dir_y", "Latest normalized force direction y component."),
            ("behaviour_stats_force_dir_z", "Latest normalized force direction z component."),
        ],
    },
    {
        "category": "Compartmentalize stats",
        "source": "Read from top-level compartment metadata and flattened cell.dict['behaviour_stats']['compartmentalize'].",
        "items": [
            ("behaviour_stats_compartmentalize_count", "Number of compartment structural events recorded on this cell."),
            ("behaviour_stats_compartmentalize_last_mcs", "Last MCS when this cell was created/updated by a compartment action."),
            ("behaviour_stats_compartmentalize_interval_since_last", "MCS gap since the previous compartment event on this cell."),
            ("behaviour_stats_compartmentalize_action", "Latest compartment action name."),
            ("behaviour_stats_compartmentalize_length", "Latest logical chain length stored on the new tip."),
            ("behaviour_stats_compartmentalize_parent_segment_id", "Parent segment id for the latest created tip."),
        ],
    },
    {
        "category": "FPP link stats",
        "source": "Read from flattened cell.dict['behaviour_stats']['fpp_link'].",
        "items": [
            ("behaviour_stats_fpp_link_count", "Number of FPP link rule events recorded on this cell."),
            ("behaviour_stats_fpp_link_last_mcs", "Last MCS when an FPP link rule acted."),
            ("behaviour_stats_fpp_link_last_created", "Number of ordinary FPP links created by the latest trigger."),
            ("behaviour_stats_fpp_link_total_created", "Total ordinary FPP links created by this steppable instance."),
            ("behaviour_stats_fpp_link_mode", "Latest FPP link mode used by this cell."),
        ],
    },
]


DYNAMIC_NUMERIC_INPUTS = [
    {
        "category": "Dynamic numeric input locations",
        "source": "These rule fields may accept constants, state expressions, or physical-model dictionaries.",
        "items": [
            ("frequency", "Rule-level execution interval. Supports state-feedback frequency dictionaries."),
            ("behaviour parameters", "Examples: growth delta, secrete/uptake amount, chemotaxis lambda, force, compartmentalize search_radius."),
            ("Environment.threshold", "Right-hand numeric threshold for field concentration conditions."),
            ("Environment.sampling_mode", "Defines how field concentration is sampled: com, cell_average/max/min, boundary_average/max/min, contact_boundary_average/max/min, or radius_average/max/min."),
            ("Environment.radius", "Radius used by radius_* sampling modes. Supports dynamic numeric syntax."),
            ("Environment.target_type", "Target cell type used by contact_boundary_* sampling modes."),
            ("Contact.threshold", "Right-hand numeric threshold for contact-ratio conditions."),
            ("Morphology.threshold", "Right-hand numeric threshold for morphology conditions."),
            ("State.threshold", "Right-hand numeric threshold for cell state conditions, except boolean dormant comparisons."),
            ("SubcellularState.threshold", "Right-hand threshold for subcellular stage, component, localization, or nested-path conditions."),
            ("subcellular amount/count/fraction/probability", "Numeric fields used by subcellular component, localization, translocation, and assembly actions."),
            ("Duration.threshold_mcs", "Required MCS duration for state-lasting conditions."),
            ("Probability.p", "Random trigger probability. Runtime values should be clamped to the range 0..1."),
            ("TimeWindow.start_mcs", "MCS window start; GUI may store this as start."),
            ("TimeWindow.end_mcs", "MCS window end; GUI may store this as end."),
        ],
    },
    {
        "category": "Dynamic numeric syntax",
        "source": "Use state expressions for cell/native states; use physical-model dictionaries for field-regulated values.",
        "items": [
            ("constant", "0.2"),
            ("state expression", "{division_count} * 20 + 50"),
            ("native-cell expression", "{targetVolume} * 1.2"),
            ("behaviour-stat expression", "{behaviour_stats_growth_active_duration} * 0.5"),
            ("physical model JSON", '{"model":"linear","regulator":"FungalSignal","parameters":{"alpha":0.2}}'),
        ],
    },
    {
        "category": "Dynamic numeric fields that are not supported",
        "source": "These fields define rule structure or left-hand variables rather than numeric values.",
        "items": [
            ("field_name", "Chemical field selector; keep as a literal field name."),
            ("target_type", "Cell type selector; keep as a literal cell type name."),
            ("regulator", "Left-hand state/field selector; keep as a literal variable name."),
            ("operator", "Comparison operator; keep as one of >, >=, <, <=, ==, != when supported."),
            ("Custom.params.*", "Not automatically resolved by default, because custom scripts may need raw values."),
        ],
    },
]


def iter_state_key_catalog():
    for section in STATE_KEY_CATALOG:
        yield section["category"], section.get("source", ""), section["items"]


def iter_dynamic_numeric_inputs():
    for section in DYNAMIC_NUMERIC_INPUTS:
        yield section["category"], section.get("source", ""), section["items"]


def format_state_key_catalog():
    lines = [
        "Available state keys for rule expressions / dynamic numeric inputs",
        "",
        "Use these names directly as state_key values or inside expressions.",
        "The displayed key is the expression variable; the source tells where it is read from.",
        "Nested behaviour_stats values are flattened with underscores by RuleEngine.",
        "Field placeholders use the actual field name, e.g. <FIELD> -> Oxygen.",
        "",
    ]

    for category, source, items in iter_state_key_catalog():
        lines.append(category)
        if source:
            lines.append(f"  Source: {source}")
        for item in items:
            if len(item) == 3:
                key, source_expr, description = item
            else:
                key, description = item
                source_expr = ""
            lines.append(f"  {key}")
            if source_expr:
                lines.append(f"    Source path: {source_expr}")
            lines.append(f"    {description}")
        lines.append("")

    lines.extend(
        [
            "Dynamic numeric inputs",
            "  Use the state keys above inside {key} expressions where dynamic numeric fields are supported.",
            "  Physical-model JSON regulators are chemical fields sampled by the rule engine.",
            "  CSV cells containing JSON must escape quotes using doubled quotes.",
            "",
        ]
    )

    for category, source, items in iter_dynamic_numeric_inputs():
        lines.append(category)
        if source:
            lines.append(f"  Source: {source}")
        for key, description in items:
            lines.append(f"  {key}")
            lines.append(f"    {description}")
        lines.append("")

    return "\n".join(lines).rstrip()
