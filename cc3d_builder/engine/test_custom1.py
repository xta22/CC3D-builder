def validate(cell, engine, params):
    # params is a string here，eg. "threshold=1.5, radius=50"
    # convert to dictionary
    thr = float(params.get("threshold", 1.2))

    oxygen_val = engine.get_field_value("Oxygen", cell)
    
    return oxygen_val > thr if oxygen_val else False