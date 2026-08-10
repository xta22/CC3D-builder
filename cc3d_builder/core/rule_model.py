# rule_model.py

class Rule:

    def __init__(self, id, target, behaviour, cases,
                 once=False, debug=False):
        self.id = id
        self.target = target
        self.behaviour = behaviour
        self.cases = cases
        self.once = once
        self.debug = debug
        self.triggered = False

    def to_dict(self):

        return {
            "id": self.id,
            "target": self.target,
            "behaviour": self.behaviour,
            "cases": self.cases,
            "once": self.once,
            "debug": self.debug,
            "triggered": self.triggered
        }