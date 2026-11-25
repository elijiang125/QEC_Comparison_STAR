"""Stim circuits for the bicycle-chain code (plan steps 3 and 4).

Step 3: one noiseless round of syndrome extraction, using the depth-8 CNOT
schedule of Table II in the paper.
Step 4: a memory experiment, which repeats that round and adds detectors
and logical observables.

How one check is measured
-------------------------
- X-check: ancilla starts in |+>, does CNOT(ancilla -> data) onto its 8 data
  qubits, then is measured in the X basis.
- Z-check: ancilla starts in |0>, receives CNOT(data -> ancilla) from its 8
  data qubits, then is measured in the Z basis.

How Table II reads
------------------
The polynomial a(x, y) = 1 + y^3 + x y^2 + x y^4 has four monomials, which the
paper labels A1 = x y^4, A2 = x y^2, A3 = y^3, A4 = 1. The monomials of
b = a^T are their inverses, B_k = A_k^(-1). In layer t:

- every X-ancilla (i, j) does a CNOT onto the data qubit at (i, j) slid by the
  listed monomial, in the listed half;
- every Z-ancilla (i, j) receives a CNOT from the other half, at (i, j) slid by
  the *transposed* (inverted) monomial.

Because each slide is a permutation of the torus, a layer touches every data
qubit of a half exactly once, and the X and Z ancillas always work on opposite
halves. So all 2*l*m ancillas run in parallel with no qubit used twice.

Sign rule this produces (it matches H = [A | A^T] from codes.py):
    X-check:  A_k -> slide by +A_k        B_k  -> slide by -A_k
    Z-check:  A_k^T -> slide by -A_k      B_k^T -> slide by +A_k
"""

import stim

from .codes import bicycle_chain_matrix, row_slice_logicals
from .layout import Layout

# Table II's dictionary: A_k as exponent pairs (p, q) of x^p y^q.
A_MONOS = {1: (1, 4), 2: (1, 2), 3: (0, 3), 4: (0, 0)}

# Table II, one entry per CNOT layer:
#   ((X-check half, letter, k), (Z-check half, letter, k))
# The Z-check entry is the transposed monomial, e.g. ("R", "A", 4) means A4^T on the right half.
TABLE_II = [
    (("L", "A", 1), ("R", "A", 4)),
    (("R", "B", 1), ("L", "B", 4)),
    (("L", "A", 2), ("R", "A", 3)),
    (("R", "B", 2), ("L", "B", 2)),
    (("R", "B", 3), ("L", "B", 3)),
    (("L", "A", 3), ("R", "A", 2)),
    (("R", "B", 4), ("L", "B", 1)),
    (("L", "A", 4), ("R", "A", 1)),
]


def _sign(letter, transposed):
    """+1 to slide by A_k, -1 to slide by A_k^(-1) (see the sign rule above)."""
    s = 1 if letter == "A" else -1
    return -s if transposed else s


def layer_pairs(layout, t):
    """The CNOT (control, target) pairs of Table II layer t (0-based)."""
    (xh, xl, xk), (zh, zl, zk) = TABLE_II[t]
    pairs = []
    for i, j in layout.cells():
        di, dj = layout.slide(i, j, A_MONOS[xk], _sign(xl, transposed=False))
        pairs.append((layout.x_anc(i, j), layout.data(xh, di, dj)))   # ancilla controls data
        di, dj = layout.slide(i, j, A_MONOS[zk], _sign(zl, transposed=True))
        pairs.append((layout.data(zh, di, dj), layout.z_anc(i, j)))   # data controls ancilla
    return pairs


def ancilla_supports(layout):
    """Which data qubits each X- and Z-ancilla touches over the 8 layers."""
    x_sup = {c: set() for c in range(layout.n_half)}
    z_sup = {c: set() for c in range(layout.n_half)}
    for t in range(len(TABLE_II)):
        for ctrl, targ in layer_pairs(layout, t):
            if ctrl >= 2 * layout.n_half:            # X-ancilla is the control
                x_sup[ctrl - 2 * layout.n_half].add(targ)
            else:                                    # Z-ancilla is the target
                z_sup[targ - 3 * layout.n_half].add(ctrl)
    return x_sup, z_sup


class _Recorder:
    """Keeps a running count of measurements, so we can refer to old results with rec[-k]."""

    def __init__(self):
        self.count = 0

    def measure(self, n):
        first = self.count
        self.count += n
        return list(range(first, first + n))

    def rec(self, idx):
        return stim.target_rec(idx - self.count)


def syndrome_round(circuit, layout, recorder):
    """Append one full round: reset ancillas, 8 CNOT layers, measure ancillas.

    Returns (x_meas, z_meas): absolute measurement indices, one per check, in cell order.
    """
    xs = [layout.x_anc(i, j) for i, j in layout.cells()]
    zs = [layout.z_anc(i, j) for i, j in layout.cells()]
    circuit.append("RX", xs)
    circuit.append("R", zs)
    circuit.append("TICK")
    for t in range(len(TABLE_II)):
        circuit.append("CX", [q for pair in layer_pairs(layout, t) for q in pair])
        circuit.append("TICK")
    circuit.append("MX", xs)
    x_meas = recorder.measure(len(xs))
    circuit.append("M", zs)
    z_meas = recorder.measure(len(zs))
    return x_meas, z_meas


def single_round_circuit(l, m):
    """Just one syndrome round, with nothing before or after (used to test step 3)."""
    layout = Layout(l, m)
    c = stim.Circuit()
    syndrome_round(c, layout, _Recorder())
    return c


def memory_experiment(l, m, rounds, basis="Z", x_errors_after_round=None):
    """A noiseless memory experiment (plan step 4).

    1. Prepare every data qubit in |0> (basis "Z") or |+> (basis "X"). That puts
       the block in a logical all-|0> (or all-|+>) state once checks are measured.
    2. Repeat the syndrome round `rounds` times.
    3. Measure every data qubit in the same basis.

    Detectors (parities that must be 0 when nothing goes wrong):
    - first round: the checks of the prepared basis already have known value +1;
    - every later round: each check must match its own value from the round before;
    - at the end: each check of the prepared basis, rebuilt from the data
      measurements, must match its last ancilla measurement.

    Observables: the 2l row logicals (L1..Ll, R1..Rl), read from the data.

    `x_errors_after_round` lets a test inject X errors by hand,
    e.g. {1: [5]} flips data qubit 5 after round 1.
    """
    if basis not in ("Z", "X"):
        raise ValueError("basis must be 'Z' or 'X'")
    layout = Layout(l, m)
    H = bicycle_chain_matrix(l, m)          # self-dual: X- and Z-check supports are both rows of H
    logicals = row_slice_logicals(l, m)
    data = list(range(2 * layout.n_half))
    rec = _Recorder()
    c = stim.Circuit()

    for q in range(layout.num_qubits):
        c.append("QUBIT_COORDS", [q], layout.coords(q))
    c.append("R" if basis == "Z" else "RX", data)
    c.append("TICK")

    history = []                            # per round: (x_meas, z_meas)
    for r in range(rounds):
        x_meas, z_meas = syndrome_round(c, layout, rec)
        same = z_meas if basis == "Z" else x_meas
        for idx, (i, j) in enumerate(layout.cells()):
            if r == 0:
                c.append("DETECTOR", [rec.rec(same[idx])], (i, j, r))
            else:
                prev_x, prev_z = history[-1]
                c.append("DETECTOR", [rec.rec(x_meas[idx]), rec.rec(prev_x[idx])], (i, j, r))
                c.append("DETECTOR", [rec.rec(z_meas[idx]), rec.rec(prev_z[idx])], (i, j, r))
        history.append((x_meas, z_meas))
        # Injected errors must be noise (X_ERROR with probability 1), not a plain X gate:
        # Stim reports detectors relative to the noiseless circuit, so a plain X would
        # count as "intended" and never fire anything.
        for q in (x_errors_after_round or {}).get(r, []):
            c.append("X_ERROR", [q], 1.0)
        c.append("TICK")

    c.append("M" if basis == "Z" else "MX", data)
    data_meas = rec.measure(len(data))
    last = history[-1][1] if basis == "Z" else history[-1][0]
    for idx, (i, j) in enumerate(layout.cells()):
        support = [data_meas[q] for q in H[idx].nonzero()[0]]
        c.append("DETECTOR", [rec.rec(k) for k in support] + [rec.rec(last[idx])], (i, j, rounds))
    for a, row in enumerate(logicals):
        c.append("OBSERVABLE_INCLUDE", [rec.rec(data_meas[q]) for q in row.nonzero()[0]], a)
    return c
