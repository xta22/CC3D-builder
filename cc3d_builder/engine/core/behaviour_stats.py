# behaviour_stats.py
def ensure_behaviour_stats(cell):
    return cell.dict.setdefault("behaviour_stats", {})


def behaviour_stats(cell, behaviour):
    stats = ensure_behaviour_stats(cell)
    return stats.setdefault(behaviour, {})


def field_behaviour_stats(cell, behaviour, field_name):
    parent = behaviour_stats(cell, behaviour)
    return parent.setdefault(str(field_name), {})


def record_event(cell, behaviour, mcs, amount=None):
    stats = behaviour_stats(cell, behaviour)
    previous_mcs = stats.get("last_mcs")

    stats["count"] = stats.get("count", 0) + 1
    stats.setdefault("first_mcs", mcs)
    stats["last_mcs"] = mcs
    stats["interval_since_last"] = None if previous_mcs is None else mcs - previous_mcs

    if amount is not None:
        stats["last_delta"] = amount
        stats["total_delta"] = stats.get("total_delta", 0.0) + amount

    return stats


def sync_event_count(cell, behaviour, mcs, count):
    stats = behaviour_stats(cell, behaviour)
    previous_mcs = stats.get("last_mcs")

    stats["count"] = count
    if count:
        stats.setdefault("first_mcs", mcs)
        stats["last_mcs"] = mcs
        stats["interval_since_last"] = None if previous_mcs is None else mcs - previous_mcs

    return stats


def record_activation(cell, behaviour, mcs):
    stats = behaviour_stats(cell, behaviour)

    if not stats.get("active", False):
        stats["active"] = True
        stats["active_since_mcs"] = mcs
        stats["activation_count"] = stats.get("activation_count", 0) + 1

    stats["last_active_mcs"] = mcs
    return stats


def record_active_step(cell, behaviour, mcs, delta=None):
    stats = behaviour_stats(cell, behaviour)
    counted_mcs = stats.get("_active_duration_counted_mcs")

    if not stats.get("active", False):
        stats["active"] = True
        stats["active_since_mcs"] = mcs
        stats["activation_count"] = stats.get("activation_count", 0) + 1

    stats["last_active_mcs"] = mcs
    if counted_mcs != mcs:
        stats["active_duration"] = stats.get("active_duration", 0) + 1
        stats["_active_duration_counted_mcs"] = mcs
    stats["inactive_duration"] = 0

    if delta is not None:
        stats["last_delta"] = delta
        stats["total_delta"] = stats.get("total_delta", 0.0) + delta

    return stats


def record_deactivation(cell, behaviour, mcs):
    stats = behaviour_stats(cell, behaviour)

    if stats.get("active", False):
        stats["active"] = False
        stats["deactivated_mcs"] = mcs
        last_active = stats.get("last_active_mcs", stats.get("active_since_mcs"))
        if last_active is not None:
            stats["inactive_duration"] = mcs - last_active

    return stats


def record_field_delta(cell, behaviour, field_name, mcs, delta):
    stats = field_behaviour_stats(cell, behaviour, field_name)
    previous_mcs = stats.get("last_active_mcs")
    counted_mcs = stats.get("_active_duration_counted_mcs")

    if not stats.get("active", False):
        stats["active"] = True
        stats["active_since_mcs"] = mcs
        stats["activation_count"] = stats.get("activation_count", 0) + 1

    stats["last_active_mcs"] = mcs
    stats["interval_since_last"] = None if previous_mcs is None else mcs - previous_mcs
    if counted_mcs != mcs:
        stats["active_duration"] = stats.get("active_duration", 0) + 1
        stats["_active_duration_counted_mcs"] = mcs
    stats["last_delta"] = delta
    stats["total_delta"] = stats.get("total_delta", 0.0) + delta
    return stats


def set_metric(cell, behaviour, key, value):
    stats = behaviour_stats(cell, behaviour)
    stats[key] = value
    return stats
