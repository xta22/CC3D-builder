class BaseBehaviourPlugin:

    behaviour_name = None
    frequency = 1

    def __init__(self, engine):
        self.engine = engine

    def push_request(self, cell, key, value):

        if "requests" not in cell.dict:
            cell.dict["requests"] = {}

        cell.dict["requests"][key] = value

    def required_steppable(self):
        return None

    def apply(self, rule, case, cell):
        raise NotImplementedError