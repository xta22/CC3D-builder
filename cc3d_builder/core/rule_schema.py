# rule_schema.py
from collections.abc import Mapping


CASE_META_KEYS = {"when"}
FORBIDDEN_CASE_KEYS = {"apply", "parameters"}


def validate_case_schema(case, rule_id=None, case_index=None):
    """Raise ValueError if a case still uses a deprecated wrapper."""
    if not isinstance(case, Mapping):
        raise ValueError(_schema_error("Rule case must be a dict", rule_id, case_index))

    forbidden = sorted(key for key in FORBIDDEN_CASE_KEYS if key in case)
    if forbidden:
        keys = ", ".join(forbidden)
        raise ValueError(
            _schema_error(
                f"Deprecated case-level wrapper key(s) found: {keys}",
                rule_id,
                case_index,
            )
        )


def validate_rule_schema(rule):
    """Validate strict flat case schema for one rule."""
    if not isinstance(rule, Mapping):
        raise ValueError("Rule must be a dict")

    cases = rule.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(_schema_error("Rule must contain a non-empty cases list", rule.get("id")))

    for idx, case in enumerate(cases):
        validate_case_schema(case, rule.get("id"), idx)


def validate_rules_schema(rules):
    """Validate strict flat case schema for a list of rules."""
    for rule in rules:
        validate_rule_schema(rule)


def case_payload(case):
    """
    Return the executable payload from a flat rule case.

    Standard schema:
        {"when": {...}, "model": "linear", "alpha": 0.5}
    """
    if not isinstance(case, Mapping):
        return {}

    validate_case_schema(case)

    return {
        key: value
        for key, value in case.items()
        if key not in CASE_META_KEYS
    }


def first_case(rule):
    """Return the first case from a rule, or an empty dict if unavailable."""
    if not isinstance(rule, Mapping):
        return {}

    cases = rule.get("cases")
    if not isinstance(cases, list) or not cases:
        return {}

    case = cases[0]
    return dict(case) if isinstance(case, Mapping) else {}


def first_case_payload(rule):
    """Return case_payload(first_case(rule))."""
    return case_payload(first_case(rule))


def _schema_error(message, rule_id=None, case_index=None):
    details = []
    if rule_id is not None:
        details.append(f"rule_id={rule_id}")
    if case_index is not None:
        details.append(f"case_index={case_index}")

    if details:
        return f"{message} ({', '.join(details)})"
    return message
