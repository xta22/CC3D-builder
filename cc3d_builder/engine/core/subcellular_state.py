# subcellular_state.py
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SUBCELLULAR_KEY = "subcellular"


def clean_subcellular_text(value: Any) -> str:
    """Normalize user-entered labels such as stages, systems, and component keys."""
    text = str(value or "").strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


def ensure_subcellular_container(cell: Any) -> dict[str, Any]:
    """Return the per-cell subcellular container, creating it if needed."""
    return cell.dict.setdefault(SUBCELLULAR_KEY, {})


def system_name(spec_or_name: Any) -> str:
    if isinstance(spec_or_name, Mapping):
        return clean_subcellular_text(spec_or_name.get("id") or spec_or_name.get("name") or spec_or_name.get("system"))
    return clean_subcellular_text(spec_or_name)


def ensure_subcellular_system(cell: Any, spec_or_name: Any, mcs: int | None = None) -> dict[str, Any]:
    """Return one subcellular system state, initializing defaults from a registry spec."""
    name = system_name(spec_or_name)
    container = ensure_subcellular_container(cell)
    system = container.setdefault(name, {})
    if not isinstance(system, dict):
        system = {}
        container[name] = system

    if isinstance(spec_or_name, Mapping):
        _apply_system_defaults(system, spec_or_name)

    if mcs is not None:
        system.setdefault("initialized_mcs", mcs)
    return system


def read_subcellular_value(cell: Any, system: str, variable: str = "stage", default: Any = 0.0) -> Any:
    """Read a value from cell.dict['subcellular'][system]."""
    if cell is None or not system:
        return default

    state = getattr(cell, "dict", {}).get(SUBCELLULAR_KEY, {}).get(str(system), {})
    if not isinstance(state, Mapping):
        return default

    variable = str(variable or "stage").strip()
    if not variable:
        return default

    aliases = {
        "stage": "stage",
        "assembly_stage": "stage",
    }
    variable = aliases.get(variable, variable)

    if variable in state:
        return _clean_read_value(state.get(variable, default))

    return _clean_read_value(get_nested(state, variable, default))


def write_subcellular_value(cell: Any, system: str, variable: str, value: Any, mcs: int | None = None) -> Any:
    state = ensure_subcellular_system(cell, system, mcs=mcs)
    value = _clean_write_value(value)
    set_nested(state, variable, value)
    if mcs is not None:
        state["last_update_mcs"] = mcs
    return value


def component_count(cell: Any, system: str, component: str, default: Any = 0.0) -> Any:
    return read_subcellular_value(cell, system, f"components.{clean_subcellular_text(component)}", default=default)


def set_component_count(cell: Any, system: str, component: str, value: Any, mcs: int | None = None) -> Any:
    return write_subcellular_value(cell, system, f"components.{clean_subcellular_text(component)}", value, mcs=mcs)


def localization_value(cell: Any, system: str, location: str, default: Any = 0.0) -> Any:
    return read_subcellular_value(cell, system, f"localization.{clean_subcellular_text(location)}", default=default)


def set_localization_value(cell: Any, system: str, location: str, value: Any, mcs: int | None = None) -> Any:
    return write_subcellular_value(cell, system, f"localization.{clean_subcellular_text(location)}", value, mcs=mcs)


def get_nested(mapping: Mapping[str, Any], path: str, default: Any = 0.0) -> Any:
    current: Any = mapping
    for part in str(path).split("."):
        if not part:
            continue
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def set_nested(mapping: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in str(path).split(".") if part]
    if not parts:
        return
    current = mapping
    for part in parts[:-1]:
        next_value = current.setdefault(part, {})
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _apply_system_defaults(system: dict[str, Any], spec: Mapping[str, Any]) -> None:
    system.setdefault("stage", clean_subcellular_text(spec.get("default_stage", spec.get("stage", "none"))))
    system.setdefault("components", {})
    system.setdefault("localization", {})
    system.setdefault("state", {})

    default_counts = spec.get("default_counts") or spec.get("components") or {}
    if isinstance(default_counts, Mapping):
        for component, value in default_counts.items():
            system["components"].setdefault(clean_subcellular_text(component), value)
    elif isinstance(default_counts, list):
        for item in default_counts:
            if isinstance(item, Mapping):
                component = item.get("id") or item.get("name") or item.get("component")
                if component:
                    system["components"].setdefault(clean_subcellular_text(component), item.get("initial_count", item.get("count", 0)))
            elif item:
                system["components"].setdefault(clean_subcellular_text(item), 0)

    default_localization = spec.get("default_localization") or spec.get("localization") or {}
    if isinstance(default_localization, Mapping):
        for location, value in default_localization.items():
            system["localization"].setdefault(clean_subcellular_text(location), value)


def _clean_read_value(value: Any) -> Any:
    return clean_subcellular_text(value) if isinstance(value, str) else value


def _clean_write_value(value: Any) -> Any:
    return clean_subcellular_text(value) if isinstance(value, str) else value
