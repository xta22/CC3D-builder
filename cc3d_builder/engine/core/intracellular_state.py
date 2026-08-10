# intracellular_state.py
from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


INTRACELLULAR_KEY = "intracellular"


def ensure_intracellular_container(cell: Any) -> dict[str, Any]:
    """Return the per-cell intracellular cache, creating it if needed."""
    return cell.dict.setdefault(INTRACELLULAR_KEY, {})


def ensure_model_cache(cell: Any, model_name: str) -> dict[str, Any]:
    """Return the per-model cache inside cell.dict['intracellular']."""
    container = ensure_intracellular_container(cell)
    return container.setdefault(str(model_name), {})


def write_intracellular_value(cell: Any, model_name: str, variable: str, value: Any) -> Any:
    """Write one model variable to the RuleParser intracellular cache."""
    cache = ensure_model_cache(cell, model_name)
    cache[str(variable)] = _plain_value(value)
    return cache[str(variable)]


def read_intracellular_value(
    cell: Any,
    model_name: str,
    variable: str,
    *,
    prefer_live: bool = True,
    default: Any = 0.0,
) -> Any:
    """Read a model variable, preferring the live CC3D solver object when present."""
    if cell is None or not model_name or not variable:
        return default

    if prefer_live:
        live = read_live_model_value(cell, model_name, variable, default=None)
        if live is not None:
            return live

    cache = getattr(cell, "dict", {}).get(INTRACELLULAR_KEY, {}).get(str(model_name), {})
    if isinstance(cache, MutableMapping) and str(variable) in cache:
        return cache[str(variable)]
    return default


def read_live_model_value(cell: Any, model_name: str, variable: str, default: Any = 0.0) -> Any:
    """Read directly from cell.sbml.<model> or cell.maboss.<model> when available."""
    model = live_model(cell, model_name)
    if model is None:
        return default

    variable = str(variable)
    for getter in (
        lambda: model[variable],
        lambda: getattr(model, variable),
    ):
        try:
            value = getter()
            return _plain_value(value)
        except Exception:
            continue
    return default


def write_live_model_value(cell: Any, model_name: str, variable: str, value: Any) -> bool:
    """Write directly into a live solver model if the CC3D API exposes it."""
    model = live_model(cell, model_name)
    if model is None:
        return False

    variable = str(variable)
    for setter in (
        lambda: _set_mapping_value(model, variable, value),
        lambda: setattr(model, variable, value),
    ):
        try:
            setter()
            return True
        except Exception:
            continue
    return False


def live_model(cell: Any, model_name: str) -> Any:
    """Find a live SBML/Antimony/CellML/MaBoSS model attached to a CC3D cell."""
    for family in ("sbml", "maboss"):
        container = getattr(cell, family, None)
        if container is None:
            continue

        for getter in (
            lambda: getattr(container, str(model_name)),
            lambda: container[str(model_name)],
        ):
            try:
                return getter()
            except Exception:
                continue
    return None


def _set_mapping_value(model: Any, variable: str, value: Any) -> None:
    current = model[variable]
    if hasattr(current, "state"):
        current.state = bool(value)
        return
    model[variable] = value


def _plain_value(value: Any) -> Any:
    if hasattr(value, "state"):
        return bool(value.state)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    try:
        return float(value)
    except Exception:
        return value
