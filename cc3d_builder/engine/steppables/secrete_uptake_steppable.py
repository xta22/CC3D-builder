# secrete_uptake_steppable.py
from cc3d.core.PySteppables import SteppableBasePy
from cc3d_builder.engine.core.behaviour_stats import (
    record_active_step,
    record_field_delta,
    set_metric,
)

class SecretionSteppable(SteppableBasePy):
    def __init__(self, frequency=1, engine=None):
        SteppableBasePy.__init__(self, frequency)
        self.engine = engine
        if self.engine is not None:
            self.engine.register_executor("secrete/uptake", self)

    def step(self, mcs):
        return

    def execute(self, cell, req_data, mcs):
        self._execute_request(cell, req_data, mcs)

    def _execute_request(self, cell, req_data, mcs):
        field_name = req_data.get("field_name")
        secret_mode = req_data.get("secret_mode")
        if not field_name or not secret_mode:
            return

        secretor = self.get_field_secretor(field_name)
        if not secretor:
            print(f"⚠️ [Secretion] Secretor for field '{field_name}' not found!")
            return

        actual_method_name = secret_mode
        if req_data.get("total_count") and not actual_method_name.endswith("TotalCount"):
            actual_method_name += "TotalCount"

        secretor_method = getattr(secretor, actual_method_name, None)
        if not secretor_method:
            print(f"⚠️ [Secretion] Method '{actual_method_name}' does not exist in CC3D!")
            return

        amount = self._to_float(req_data.get("amount", 1.0), 1.0)
        relative_uptake = self._to_float(req_data.get("relative_uptake", 0.1), 0.1)
        contact_type_ids = self._contact_type_ids(req_data.get("contact_types", []))

        result = None
        try:
            if "uptake" in secret_mode:
                if "OnContactWith" in secret_mode:
                    result = secretor_method(cell, amount, relative_uptake, contact_type_ids)
                else:
                    result = secretor_method(cell, amount, relative_uptake)
            else:
                if "OnContactWith" in secret_mode:
                    result = secretor_method(cell, amount, contact_type_ids)
                else:
                    result = secretor_method(cell, amount)

            actual_amount = getattr(result, "tot_amount", None)
            if actual_amount is None:
                actual_amount = amount
            actual_delta = abs(actual_amount)
            record_active_step(cell, "secrete_uptake", mcs, actual_delta)
            record_field_delta(cell, "secrete_uptake", field_name, mcs, actual_delta)
            set_metric(cell, "secrete_uptake", "last_field", field_name)
            set_metric(cell, "secrete_uptake", "last_mode", secret_mode)

            if req_data.get("total_count") and result:
                tracking = cell.dict.setdefault("persistent_tracking", {})
                tracking[field_name] = tracking.get(field_name, 0.0) + abs(result.tot_amount)

            if req_data.get("debug"):
                print(
                    f"[Secretion] MCS={mcs} cell={cell.id} field={field_name} "
                    f"mode={secret_mode} amount={actual_delta}"
                )

        except Exception as e:
            print(f"❌ [Secretion Error] Cell {cell.id} run {actual_method_name} failed: {e}")

    def _contact_type_ids(self, contact_types):
        if isinstance(contact_types, str):
            contact_types = [part.strip() for part in contact_types.split(",") if part.strip()]

        return [
            getattr(self, c_type.upper())
            for c_type in contact_types
            if hasattr(self, c_type.upper())
        ]

    def _to_float(self, value, default):
        if value in (None, ""):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
