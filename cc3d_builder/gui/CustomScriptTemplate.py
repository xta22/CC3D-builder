# --- Custom Scripts Template ---

NEW_CELL_TYPES = ["Cell_42", ...]


def match(context):
    """
    # context: an object containing the current runtime environment (e.g., cell, state, etc.)
    # return: True (apply this rule) / False (skip)
    """
    return True 

def run(context, params):
    """
    context: same as above
    params: This is a Python dict，contents are from the MainRuleWindow window.
    """
    speed = params.get('speed', 1.0)
    context.move(speed)