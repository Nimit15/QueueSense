from queuesense.controllers import FixedTimeController, ActuatedController, QueuePressureController, QueueSenseController
def _make_queuesense(id_suffix, alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.30, max_wait=90.0):
    """Factory for per-junction independent QueueSenseController instances."""
    gate_enabled = (id_suffix == "D2")
    return QueueSenseController(
        alpha=alpha, beta=beta, gamma=gamma,
        spillback_threshold=spillback_threshold, max_wait=max_wait,
        spillback_gate_enabled=gate_enabled,
    )
def build_controllers():
    """Authoritative controller factory with proven isolation.

    Each junction (J1, J2, J3) receives its own controller instance
    (dictionary comprehension) rather than sharing one mutable object.
    D1 has spillback_gate_enabled=False; D2 has spillback_gate_enabled=True.
    """
    return {
        "A": {j: FixedTimeController() for j in ["J1", "J2", "J3"]},
        "B": {j: ActuatedController(gap_threshold=3.0) for j in ["J1", "J2", "J3"]},
        "C": {j: QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0) for j in ["J1", "J2", "J3"]},
        "D1": {j: _make_queuesense("D1") for j in ["J1", "J2", "J3"]},
        "D2": {j: _make_queuesense("D2") for j in ["J1", "J2", "J3"]},
    }