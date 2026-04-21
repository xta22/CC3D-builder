# scripts/check_stiffness.py

def call(cell, custom_data, **kwargs):
    """
    CC3D Rule Engine would pass the cell object
    We leverage cell.dict to store the state counter
    """

    current_pressure = getattr(cell, 'pressure', 0)
    threshold = 0.5
    required_duration = 10

    # set a timer in cell dict
    if "pressure_timer" not in cell.dict:
        cell.dict["pressure_timer"] = 0

    if current_pressure > threshold:
        cell.dict["pressure_timer"] += 1
    else:
        cell.dict["pressure_timer"] = 0 # reset

    print(f"PRESSURE: {cell.pressure}")
    # return boolean value: whether the lasting duration meets requirements.
    return cell.dict["pressure_timer"] >= required_duration
   