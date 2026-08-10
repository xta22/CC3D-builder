# dynamic_numeric.py
import json
import math


def is_blank_value(value):
    if value is None:
        return True
    try:
        if value != value:
            return True
    except Exception:
        pass
    return str(value).strip() == ""


def parse_dynamic_numeric(value, default=0.0):
    """
    Parse a numeric rule parameter without destroying dynamic model dictionaries.

    Accepted forms:
    - plain numbers: 1, 0.5
    - JSON model dict strings: {"model":"linear",...}
    - state placeholder strings such as "{division_count} + 1"
    """
    if isinstance(value, (dict, list)):
        return value

    if is_blank_value(value):
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric) and numeric.is_integer():
            return int(numeric)
        return value

    text = str(value).strip()
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    try:
        numeric = float(text)
        return int(numeric) if numeric.is_integer() else numeric
    except ValueError:
        return text
