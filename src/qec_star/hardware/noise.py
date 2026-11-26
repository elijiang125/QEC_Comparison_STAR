"""Add circuit-level noise to a noiseless Stim memory circuit.

The QEC circuit is never rebuilt: instructions are copied in order and noise
channels are inserted next to them, so measurement records, detectors and
observables are unchanged. Works on the team's bicycle-chain memory circuit
and on Stim's generated surface-code circuits. Unsupported or already-noisy
instructions raise instead of being silently mis-modeled.

Convention (paper Sec. III; see docs/udaya/ASSUMPTIONS.md):
  reset            -> DEPOLARIZE1(prep) after the reset
  1-qubit gate     -> DEPOLARIZE1(one_qubit) after the gate
  2-qubit gate     -> DEPOLARIZE2(two_qubit) after the gate
  measurement      -> outcome flipped with probability `measurement`
  entangling layer -> DEPOLARIZE1(idle) on allocated qubits it leaves untouched
A "layer" (moment) is the run of instructions between two TICKs.
Each inserted channel carries a Stim tag naming its origin (prep, one_qubit,
two_qubit, idle, cycle_idle). Tags do not affect simulation; they make the
noise budget auditable with `noise_census`.
"""
from collections import Counter

from .models import NoiseProfile

_RESET = {"R", "RX", "RY"}
_MEASURE_RESET = {"MR", "MRX", "MRY"}
_MEASURE = {"M", "MX", "MY"} | _MEASURE_RESET
_SINGLE = {"H", "S", "S_DAG", "X", "Y", "Z", "H_XY", "H_YZ"}
_PAIR = {"CX", "CY", "CZ", "SWAP"}
_GATES = _RESET | _MEASURE | _SINGLE | _PAIR
_ANNOTATIONS = {"QUBIT_COORDS", "DETECTOR", "OBSERVABLE_INCLUDE", "SHIFT_COORDS"}
_NOISE = {"DEPOLARIZE1", "DEPOLARIZE2"}


def operated_qubits(circuit) -> set:
    """Qubits that some gate, reset or measurement actually acts on.

    Stim's generated surface-code circuits skip qubit indices, so
    `circuit.num_qubits` over-counts; idle noise must not be charged to
    indices that hold no atom.
    """
    return {t.value for op in circuit.flattened() if op.name in _GATES
            for t in op.targets_copy() if t.is_qubit_target}


def decorate_stim_memory(circuit, profile: NoiseProfile, *, active_qubits=None):
    """Return a new, flat Stim circuit with `profile`'s noise inserted.

    active_qubits: the allocated qubits (those that can idle). Defaults to
    `operated_qubits(circuit)`. Repeat blocks are unrolled first, which is
    exactly equivalent and keeps every measurement record index in place.
    With an all-zero profile the result equals `circuit.flattened()`.
    """
    import stim
    flat = circuit.flattened()
    allocated = operated_qubits(flat) if active_qubits is None else _checked(active_qubits, flat)
    out = stim.Circuit()
    touched = set()                 # qubits used so far in the current moment
    kinds = set()                   # which of "pair" / "measure" the moment contains

    def error(channel, targets):
        p = getattr(profile, channel)
        if targets and p:
            out.append("DEPOLARIZE2" if channel == "two_qubit" else "DEPOLARIZE1", targets, p, tag=channel)

    def finish_moment():
        untouched = sorted(allocated - touched)
        if "pair" in kinds:
            error("idle", untouched)
        if "measure" in kinds:
            error("cycle_idle", untouched)
        touched.clear()
        kinds.clear()

    for op in flat:
        name, targets, args = op.name, op.targets_copy(), op.gate_args_copy()
        if name == "TICK":
            finish_moment()
            out.append(op)
            continue
        if name in _ANNOTATIONS:
            out.append(op)
            continue
        if name not in _GATES:
            raise ValueError(f"unsupported or already noisy operation: {name}")
        if any(not t.is_qubit_target or t.is_inverted_result_target for t in targets):
            raise ValueError(f"only direct, non-inverted qubit targets supported: {name}")
        qs = [t.value for t in targets]
        if not set(qs) <= allocated:
            raise ValueError(f"operation touches unallocated qubit: {name}")
        if any(args):
            raise ValueError(f"already parameterized/noisy operation: {name}")
        kind = "pair" if name in _PAIR else "measure" if name in _MEASURE else None
        if kind:
            kinds.add(kind)
        if kinds == {"pair", "measure"}:
            raise ValueError("a moment mixes two-qubit gates and measurements; insert TICK")
        # In an entangling layer every qubit may be used once, otherwise
        # "idle during the layer" is not well defined.
        if "pair" in kinds and (len(set(qs)) != len(qs) or touched.intersection(qs)):
            raise ValueError("overlapping operations in entangling moment; insert TICK")
        touched.update(qs)

        if name in _MEASURE and profile.measurement:
            out.append(name, targets, profile.measurement)
        else:
            out.append(op)
        if name in _RESET or name in _MEASURE_RESET:
            error("prep", qs)
        elif name in _SINGLE:
            error("one_qubit", qs)
        elif name in _PAIR:
            if len(qs) % 2:
                raise ValueError("pair gate requires an even number of targets")
            error("two_qubit", qs)
    finish_moment()
    return out


def _checked(active_qubits, circuit) -> set:
    qs = tuple(active_qubits)
    if any(type(q) is not int or q < 0 for q in qs) or len(set(qs)) != len(qs):
        raise ValueError("active_qubits must be unique nonnegative integer indices")
    if not qs or any(q >= circuit.num_qubits for q in qs):
        raise ValueError("explicit allocation must refer to circuit qubits")
    return set(qs)


def noise_census(circuit) -> Counter:
    """Count noise locations per channel in a decorated circuit.

    Keys are the NoiseProfile channel names. A location is one qubit for
    prep, one_qubit, idle, cycle_idle and measurement, and one qubit pair for
    two_qubit. Multiplying by the channel probabilities gives the expected
    number of faults per shot, a decoder-independent exposure measure.
    """
    census = Counter()
    for op in circuit.flattened():
        n = len(op.targets_copy())
        if op.name in _NOISE:
            census[op.tag] += n // 2 if op.name == "DEPOLARIZE2" else n
        elif op.name in _MEASURE and any(op.gate_args_copy()):
            census["measurement"] += n
    return census


def expected_faults(circuit, profile: NoiseProfile) -> dict:
    """Expected number of faults per shot, by channel (locations x probability)."""
    return {channel: n * getattr(profile, channel) for channel, n in noise_census(circuit).items()}
