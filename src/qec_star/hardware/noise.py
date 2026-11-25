"""Explicit Stim adapter for initially noiseless Clifford memory circuits.

Supports the upstream bicycle memory circuit and the usual flattened rotated
surface-memory instruction subset. Rejects unsupported/noisy inputs instead
of silently undercounting. No movement, leakage, correlated errors or erasures.
"""
from .models import NoiseProfile

_ANNOTATIONS = {"QUBIT_COORDS", "DETECTOR", "OBSERVABLE_INCLUDE", "SHIFT_COORDS"}
_RESET = {"R", "RX", "RY"}
_MEASURE = {"M", "MX", "MY", "MR", "MRX", "MRY"}
_MEASURE_RESET = {"MR", "MRX", "MRY"}
_SINGLE = {"H", "S", "S_DAG", "X", "Y", "Z", "H_XY", "H_YZ"}
_PAIR = {"CX", "CY", "CZ", "SWAP"}


def decorate_stim_memory(circuit, profile: NoiseProfile, *, active_qubits):
    """Return a new Stim circuit; require explicit allocation and flat moments.

    No new measurement records are added. Measurement gate args implement
    classical bit flips. Reset depolarization occurs after reset; MR does both.
    Idle depolarization is added once at the end of entangling TICK layers to
    allocated qubits not touched in that layer. Input may not contain faults,
    feed-forward gates, repeat blocks, or qubits reused in an entangling moment.
    Flatten a noiseless generated surface circuit explicitly before calling.
    """
    import stim
    allocated = tuple(active_qubits)
    if any(type(q) is not int or q < 0 for q in allocated) or len(set(allocated)) != len(allocated):
        raise ValueError("active_qubits must be unique nonnegative integer indices")
    allocated = set(allocated)
    if not allocated or any(q >= circuit.num_qubits for q in allocated):
        raise ValueError("explicit allocation must refer to circuit qubits")
    out = stim.Circuit()
    touched = set()
    entangling = False

    def error(name, targets, p):
        if targets and p:
            out.append(name, targets, p)

    def finish_moment():
        nonlocal entangling
        if entangling:
            error("DEPOLARIZE1", sorted(allocated - touched), profile.idle)
        touched.clear()
        entangling = False

    for op in circuit:
        if isinstance(op, stim.CircuitRepeatBlock):
            raise ValueError("flatten repeat blocks before adding noise")
        name, targets, args = op.name, op.targets_copy(), op.gate_args_copy()
        if name == "TICK":
            finish_moment()
            out.append(op)
            continue
        if name in _ANNOTATIONS:
            out.append(op)
            continue
        if name not in _RESET | _MEASURE | _SINGLE | _PAIR:
            raise ValueError(f"unsupported or already noisy operation: {name}")
        if any(not t.is_qubit_target or t.is_inverted_result_target for t in targets):
            raise ValueError(f"only direct, non-inverted qubit targets supported: {name}")
        qs = [t.value for t in targets]
        if not set(qs) <= allocated:
            raise ValueError(f"operation touches unallocated qubit: {name}")
        if args and (name not in _MEASURE or any(p != 0 for p in args)):
            raise ValueError(f"already parameterized/noisy operation: {name}")
        if (name in _PAIR or entangling) and (len(set(qs)) != len(qs) or touched.intersection(qs)):
            raise ValueError("overlapping operations in entangling moment; insert TICK")
        # A pair occurring after a repeated non-entangling target is ambiguous.
        # Existing memory circuits have separate reset/gate/readout moments.
        touched.update(qs)
        if name in _MEASURE:
            if profile.measurement:
                out.append(name, targets, profile.measurement)
            else:
                out.append(op)
            if name in _MEASURE_RESET:
                error("DEPOLARIZE1", qs, profile.prep)
        else:
            out.append(op)
            if name in _RESET:
                error("DEPOLARIZE1", qs, profile.prep)
            elif name in _SINGLE:
                error("DEPOLARIZE1", qs, profile.one_qubit)
            else:
                if len(qs) % 2:
                    raise ValueError("pair gate requires an even number of targets")
                entangling = True
                error("DEPOLARIZE2", qs, profile.two_qubit)
    finish_moment()
    return out
