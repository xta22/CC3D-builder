"""Catalog of stable helpers available to RuleParser custom scripts.

These helpers are provided by both runtime contexts:

- custom condition scripts receive them on ``engine``
- full custom rule scripts receive them on ``context``

Keep this file limited to documented, stable custom-script APIs. Internal
methods should not be added here just because they exist on a runtime class.
"""

CUSTOM_RUNTIME_HELPERS = {
    "available_helpers": {
        "signature": "available_helpers()",
        "returns": "dict",
        "description": "Return the documented custom-script helper catalog for this runtime context.",
        "condition_usage": "helpers = engine.available_helpers()",
        "script_usage": "helpers = context.available_helpers()",
    },
    "ensure_cell_state": {
        "signature": "ensure_cell_state(cell)",
        "returns": "dict",
        "description": "Return the mutable per-cell state dictionary, creating it if needed.",
        "condition_usage": "state = engine.ensure_cell_state(cell)",
        "script_usage": "state = context.ensure_cell_state(cell)",
    },
    "get_current_mcs": {
        "signature": "get_current_mcs()",
        "returns": "int",
        "description": "Return the current Monte Carlo Step tracked by the rule runtime.",
        "condition_usage": "mcs = engine.get_current_mcs()",
        "script_usage": "mcs = context.get_current_mcs()",
    },
    "resolve_numeric": {
        "signature": "resolve_numeric(value, cell=None, default=0.0)",
        "returns": "float",
        "description": "Resolve a constant, {state/native} expression, or physical-model dict into a numeric value.",
        "condition_usage": "threshold = engine.resolve_numeric(params.get('threshold', 1.0), cell, 1.0)",
        "script_usage": "amount = context.resolve_numeric(params.get('amount', '{volume} * 0.01'), cell, 0.0)",
    },
    "target_cells": {
        "signature": "target_cells(target)",
        "returns": "list[cell]",
        "description": "Return cells matching a CC3D type name; use 'all', '*', or 'global' for all cells.",
        "condition_usage": "cells = engine.target_cells('CellA')",
        "script_usage": "cells = context.target_cells('CellA')",
    },
    "get_cell_type_id": {
        "signature": "get_cell_type_id(type_name)",
        "returns": "int | None",
        "description": "Return the CC3D numeric type id for a cell type name, or None when unknown.",
        "condition_usage": "type_id = engine.get_cell_type_id('CellA')",
        "script_usage": "type_id = context.get_cell_type_id('CellA')",
    },
    "get_cell_type_name": {
        "signature": "get_cell_type_name(cell)",
        "returns": "str",
        "description": "Return the registered CC3D type name for a cell when available.",
        "condition_usage": "type_name = engine.get_cell_type_name(cell)",
        "script_usage": "type_name = context.get_cell_type_name(cell)",
    },
    "get_field_value": {
        "signature": "get_field_value(field_name, cell)",
        "returns": "float",
        "description": "Return the field value at the cell center of mass; returns 0.0 if unavailable.",
        "condition_usage": "oxygen = engine.get_field_value('Oxygen', cell)",
        "script_usage": "oxygen = context.get_field_value('Oxygen', cell)",
    },
    "get_neighbor_data": {
        "signature": "get_neighbor_data(cell, include_medium=False)",
        "returns": "list[tuple[cell | None, float]]",
        "description": "Return neighboring cells with contact areas; medium contacts are omitted unless requested.",
        "condition_usage": "neighbors = engine.get_neighbor_data(cell)",
        "script_usage": "neighbors = context.get_neighbor_data(cell)",
    },
    "get_neighbor_cells": {
        "signature": "get_neighbor_cells(cell)",
        "returns": "list[cell]",
        "description": "Return neighboring non-medium cells around the given cell.",
        "condition_usage": "neighbors = engine.get_neighbor_cells(cell)",
        "script_usage": "neighbors = context.get_neighbor_cells(cell)",
    },
    "get_contact_ratio": {
        "signature": "get_contact_ratio(cell, target_type_name)",
        "returns": "float",
        "description": "Return the fraction of the cell contact area touching the requested cell type.",
        "condition_usage": "ratio = engine.get_contact_ratio(cell, 'CellB')",
        "script_usage": "ratio = context.get_contact_ratio(cell, 'CellB')",
    },
    "get_min_distance_to_type": {
        "signature": "get_min_distance_to_type(cell, target_type_name)",
        "returns": "float",
        "description": "Return the minimum COM distance from this cell to another cell type; returns inf if unavailable.",
        "condition_usage": "distance = engine.get_min_distance_to_type(cell, 'CellB')",
        "script_usage": "distance = context.get_min_distance_to_type(cell, 'CellB')",
    },
    "get_specific_surface_area": {
        "signature": "get_specific_surface_area(cell)",
        "returns": "float",
        "description": "Return cell surface divided by volume; returns 0.0 if unavailable.",
        "condition_usage": "ssa = engine.get_specific_surface_area(cell)",
        "script_usage": "ssa = context.get_specific_surface_area(cell)",
    },
    "get_elongation_ratio": {
        "signature": "get_elongation_ratio(cell)",
        "returns": "float",
        "description": "Return an aspect-ratio-like elongation value derived from eccentricity.",
        "condition_usage": "elongation = engine.get_elongation_ratio(cell)",
        "script_usage": "elongation = context.get_elongation_ratio(cell)",
    },
    "get_intracellular_value": {
        "signature": "get_intracellular_value(cell, model_name, variable, default=0.0)",
        "returns": "Any",
        "description": "Return a cached or live intracellular model variable value.",
        "condition_usage": "value = engine.get_intracellular_value(cell, 'model1', 'x')",
        "script_usage": "value = context.get_intracellular_value(cell, 'model1', 'x')",
    },
    "get_subcellular_value": {
        "signature": "get_subcellular_value(cell, system, variable='stage', default=0.0)",
        "returns": "Any",
        "description": "Return a subcellular state value such as stage, components.X, or localization.X.",
        "condition_usage": "stage = engine.get_subcellular_value(cell, 'cycle', 'stage')",
        "script_usage": "stage = context.get_subcellular_value(cell, 'cycle', 'stage')",
    },
}


CUSTOM_TEMPLATE_LOCAL_HELPERS = {
    "_to_float": {
        "signature": "_to_float(value, default=0.0)",
        "returns": "float",
        "description": "Convert an interactive string parameter to float with a fallback default.",
    },
    "_to_int": {
        "signature": "_to_int(value, default=0)",
        "returns": "int",
        "description": "Convert an interactive string parameter to int through float parsing with a fallback default.",
    },
}


def format_helper_catalog(catalog=None):
    """Return a compact text summary suitable for CLI/GUI help output."""
    catalog = CUSTOM_RUNTIME_HELPERS if catalog is None else catalog
    lines = []
    for name, spec in catalog.items():
        lines.append(f"{name}: {spec['signature']} -> {spec['returns']}")
        lines.append(f"  {spec['description']}")
    return "\n".join(lines)
