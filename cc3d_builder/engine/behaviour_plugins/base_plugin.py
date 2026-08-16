# base_plugin.py
class BaseBehaviourPlugin:

    behaviour_name = None
    frequency = 1

    def __init__(self, engine):
        self.engine = engine

    def required_steppable(self):
        return None

    def apply(self, rule, case, cell):
        raise NotImplementedError
