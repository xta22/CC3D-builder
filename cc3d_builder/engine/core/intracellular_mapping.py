# intracellular_mapping.py
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cc3d_builder.engine.core.condition_evaluator import sample_environment_value
from cc3d_builder.engine.core.intracellular_state import (
    ensure_model_cache,
    read_intracellular_value,
    write_intracellular_value,
)


def model_alias(spec: Mapping[str, Any] | None, fallback: str | None = None) -> str:
    """Return the CC3D model alias used in cell.sbml/cell.maboss."""
    if not isinstance(spec, Mapping):
        return str(fallback or "").strip()
    return str(
        spec.get("model_name")
        or spec.get("alias")
        or spec.get("id")
        or fallback
        or ""
    ).strip()


def mapping_model_var(mapping: Mapping[str, Any]) -> str:
    return str(
        mapping.get("model_var")
        or mapping.get("variable")
        or mapping.get("var")
        or mapping.get("name")
        or ""
    ).strip()


def resolve_input_value(mapping: Mapping[str, Any], cell: Any, engine: Any, model_name: str, mcs: int) -> Any:
    """Resolve one input mapping value from CC3D state into a solver variable."""
    source_kind = str(
        mapping.get("from")
        or mapping.get("source_kind")
        or mapping.get("source")
        or "constant"
    ).strip().lower()

    if source_kind in {"constant", "value"}:
        return mapping.get("value", mapping.get("default", 0.0))

    if source_kind in {"time", "mcs", "global_time"}:
        return float(mcs)

    if source_kind in {"cell_attribute", "cell_attr", "cell"}:
        attr_name = str(mapping.get("attr") or mapping.get("key") or mapping.get("source_key") or "").strip()
        return _numeric_attr(cell, attr_name, mapping.get("default", 0.0))

    if source_kind in {"field", "field_sample", "environment"}:
        params = dict(mapping)
        field_name = params.get("field_name") or params.get("field") or params.get("source_key")
        params["field_name"] = field_name
        return sample_environment_value(params, cell, engine)

    if source_kind in {"contact", "contact_ratio"}:
        target_type = mapping.get("target_type") or mapping.get("cell_type") or mapping.get("source_key")
        getter = getattr(engine, "get_contact_ratio", None)
        return float(getter(cell, target_type)) if callable(getter) else 0.0

    if source_kind in {"neighbor_average", "neighbor_avg"}:
        return _neighbor_average(mapping, cell, engine, model_name)

    if source_kind in {"cell_dict", "state"}:
        key = str(mapping.get("key") or mapping.get("source_key") or "").strip()
        if source_kind == "state" and key and not key.startswith("state."):
            key = f"state.{key}"
        return get_cell_dict_path(cell, key, mapping.get("default", 0.0))

    if source_kind in {"model_variable", "intracellular"}:
        source_model = str(mapping.get("source_model") or model_name)
        source_var = str(mapping.get("source_var") or mapping_model_var(mapping))
        return read_intracellular_value(cell, source_model, source_var, default=mapping.get("default", 0.0))

    return mapping.get("default", 0.0)


def apply_output_mapping(mapping: Mapping[str, Any], cell: Any, engine: Any, model_name: str, mcs: int) -> Any:
    """Read a solver variable and write it to the requested CC3D/RuleParser target."""
    variable = mapping_model_var(mapping)
    if not variable:
        return None

    value = read_intracellular_value(cell, model_name, variable, default=mapping.get("default", 0.0))
    target_kind = str(mapping.get("to") or mapping.get("target_kind") or "intracellular").strip().lower()
    target_key = str(mapping.get("key") or mapping.get("target_key") or variable).strip()

    write_intracellular_value(cell, model_name, variable, value)

    if target_kind in {"intracellular", "cache"}:
        return value

    if target_kind == "state":
        cell.dict.setdefault("state", {})[target_key] = value
        return value

    if target_kind == "cell_dict":
        set_cell_dict_path(cell, target_key, value)
        return value

    if target_kind in {"cell_attribute", "cell_attr"}:
        if target_key:
            try:
                setattr(cell, target_key, value)
            except Exception:
                pass
        return value

    return value


def cache_outputs(cell: Any, model_name: str, outputs: list[Mapping[str, Any]], engine: Any, mcs: int) -> None:
    for mapping in outputs or []:
        apply_output_mapping(mapping, cell, engine, model_name, mcs)


def get_cell_dict_path(cell: Any, path: str, default: Any = 0.0) -> Any:
    if cell is None or not path:
        return default
    current = getattr(cell, "dict", {})
    for part in str(path).split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def set_cell_dict_path(cell: Any, path: str, value: Any) -> None:
    if cell is None or not path:
        return
    parts = [part for part in str(path).split(".") if part]
    if not parts:
        return
    current = cell.dict
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def ensure_default_model_cache(cell: Any, model_name: str, mcs: int) -> dict[str, Any]:
    cache = ensure_model_cache(cell, model_name)
    cache.setdefault("last_step_mcs", mcs)
    return cache


def _neighbor_average(mapping: Mapping[str, Any], cell: Any, engine: Any, model_name: str) -> float:
    source_model = str(mapping.get("source_model") or model_name)
    source_var = str(mapping.get("source_var") or mapping_model_var(mapping))
    target_type = mapping.get("target_type")
    target_type_id = getattr(engine, str(target_type).upper(), None) if target_type else None

    values = []
    try:
        neighbor_data = engine.getCellNeighborDataList(cell)
    except Exception:
        neighbor_data = []

    for neighbor, _area in neighbor_data:
        if neighbor is None:
            continue
        if target_type_id is not None and getattr(neighbor, "type", None) != target_type_id:
            continue
        value = read_intracellular_value(neighbor, source_model, source_var, default=None)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue

    if not values:
        return float(mapping.get("default", 0.0))
    return sum(values) / len(values)


def _numeric_attr(cell: Any, attr_name: str, default: Any = 0.0) -> Any:
    if cell is None or not attr_name:
        return default
    try:
        value = getattr(cell, attr_name)
    except Exception:
        return default
    return value
