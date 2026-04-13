BEHAVIOUR_SCHEMA = {
    "growth": {
        "fields": [
            {"name": "target", "type": "str"},
            {"name": "model", "type": "choice", "options": ["linear", "hill", "expression"]}
        ],
        "subfields": {
            "linear": [
                {"name": "regulator", "type": "str"},
                {"name": "alpha", "type": "float"}
            ],
            "hill": [
                {"name": "regulator", "type": "str"},
                {"name": "y_min", "type": "float"},
                {"name": "y_max", "type": "float"},
                {"name": "K", "type": "float"},
                {"name": "n", "type": "float"}
            ],
            "expression": [
                {"name": "regulator", "type": "str"},
                {"name": "expression", "type": "str"}
            ]
        }
    },

    "create": {
        "fields": [
            {"name": "cell_type", "type": "str"},
            {"name": "count", "type": "int"},
            {"name": "distribution", "type": "choice", "options": ["stripe", "cluster", "random"]}
        ],
        "subfields": {
            "stripe": [
                {"name": "x", "type": "int"},
                {"name": "y_start", "type": "int"},
                {"name": "gap", "type": "int"},
                {"name": "y_end", "type": "int"},
            ],
            "cluster": [
                {"name": "center_x", "type": "int"},
                {"name": "center_y", "type": "int"},
                {"name": "radius", "type": "int"}
            ],
            "random": []
        }
    },

    "differentiate": {
        "fields": [
            {"name": "mode", "type": "choice", "options": ["type_switch", "division"]}
        ],
        "subfields": {
            "type_switch": [
                {"name": "new_type", "type": "str"}
            ],
            "division": [
                {"name": "parent_type", "type": "str"},
                {"name": "child_type", "type": "str"},
                {"name": "volume_ratio", "type": "float"}
            ]
        }
    }
}