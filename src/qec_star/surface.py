"""Rotated surface code: the baseline we compare the bicycle-chain code against.

Layout
------
A distance-d patch (d odd) has d x d data qubits on a grid, data (i, j) at
index i*d + j. Checks sit on the faces between data qubits. Face (i, j), with
i, j in -1..d-1, touches the up-to-four data qubits

    (i, j)    (i, j+1)        TL  TR
    (i+1, j)  (i+1, j+1)      BL  BR

and is an X-check when (i + j) is even, a Z-check when it is odd.
  * Bulk faces (fully inside the grid) are weight-4 checks of either type.
  * Faces on the top and bottom edges are kept only if they are X-checks,
    faces on the left and right edges only if they are Z-checks (weight 2).
  * Corner faces (weight 1) are dropped.
That gives (d-1)^2 + 2(d-1) = d^2 - 1 checks, so k = d^2 - (d^2 - 1) = 1.

Qubit count per patch: d^2 data + (d^2 - 1) ancillas = 2d^2 - 1 atoms.

Ancilla indices follow the data: ancilla number a (in check order) is qubit
d*d + a. Checks are ordered X-checks first, then Z-checks, each in row-major
face order, matching the rows of Hx and Hz.

CNOT schedule
-------------
Four layers. X-checks visit TL, TR, BL, BR; Z-checks visit TL, BL, TR, BR.
These two orders never use a data qubit twice in one layer, and they put the
"hook" error (an ancilla fault halfway through a check, which spreads to two
data qubits) perpendicular to the logical it could shorten, so the circuit
keeps the full distance d. Both properties are checked in tests/test_surface.py.
"""

import numpy as np
import stim

# Corner offsets of a face, in the order each check type visits them.
X_ORDER = [(0, 0), (0, 1), (1, 0), (1, 1)]  # TL, TR, BL, BR
Z_ORDER = [(0, 0), (1, 0), (0, 1), (1, 1)]  # TL, BL, TR, BR


# ---------------------------------------------------------------------------
# Qubit counts (used for both comparisons in the proposal)
# ---------------------------------------------------------------------------

def num_data(d):
    """Data qubits in one distance-d patch."""
    return d * d


def num_ancilla(d):
    """Measurement ancillas in one patch (one per check)."""
    return d * d - 1


def num_qubits(d):
    """All atoms in one patch: data plus ancillas, 2d^2 - 1."""
    return num_data(d) + num_ancilla(d)


def atoms_per_logical(d):
    """A patch stores one logical qubit, so this is just num_qubits(d)."""
    return num_qubits(d)


def patches_for_budget(n_atoms, d):
    """How many distance-d patches (= logical qubits) fit in n_atoms atoms."""
    return n_atoms // num_qubits(d)


# ---------------------------------------------------------------------------
# Checks and logicals
# ---------------------------------------------------------------------------

def _check_type(i, j):
    return "X" if (i + j) % 2 == 0 else "Z"


def faces(d):
    """The kept faces as (type, i, j), X-checks first, each in row-major order."""
    if d < 3 or d % 2 == 0:
        raise ValueError("d must be an odd integer >= 3")
    kept = {"X": [], "Z": []}
    for i in range(-1, d):
        for j in range(-1, d):
            t = _check_type(i, j)
            on_tb = i in (-1, d - 1)       # top or bottom edge
            on_lr = j in (-1, d - 1)       # left or right edge
            if on_tb and on_lr:
                continue                   # corner: weight 1, dropped
            if on_tb and t != "X":
                continue
            if on_lr and t != "Z":
                continue
            kept[t].append((t, i, j))
    return kept["X"] + kept["Z"]


def face_support(d, i, j, order):
    """Data qubits of face (i, j), in visiting order, skipping ones off the grid.

    Returns a list with one entry per CNOT layer: a data index, or None when
    that corner is off the grid (the ancilla idles in that layer).
    """
    out = []
    for di, dj in order:
        r, c = i + di, j + dj
        out.append(r * d + c if 0 <= r < d and 0 <= c < d else None)
    return out


def rotated_surface_code(d):
    """Parity-check matrices (Hx, Hz) of the distance-d rotated surface code.

    Same convention as codes.py: one row per check, one column per data qubit.
    """
    n = num_data(d)
    rows = {"X": [], "Z": []}
    for t, i, j in faces(d):
        v = np.zeros(n, dtype=np.uint8)
        for q in face_support(d, i, j, X_ORDER):
            if q is not None:
                v[q] = 1
        rows[t].append(v)
    return np.array(rows["X"], dtype=np.uint8), np.array(rows["Z"], dtype=np.uint8)


def logicals(d):
    """(Lx, Lz) as 0/1 vectors of length d^2.

    A Z string can only end on an edge with no X-checks, so it runs between
    the left and right (Z-check) edges: Z-logical = row 0. Likewise the
    X-logical runs between the top and bottom (X-check) edges: X-logical =
    column 0. They overlap on qubit 0 only, so they anticommute, as a logical
    pair must.
    """
    n = num_data(d)
    Lz = np.zeros(n, dtype=np.uint8)
    Lz[list(range(d))] = 1
    Lx = np.zeros(n, dtype=np.uint8)
    Lx[[r * d for r in range(d)]] = 1
    return Lx, Lz


# ---------------------------------------------------------------------------
# Circuits
# ---------------------------------------------------------------------------

def layer_pairs(d, t):
    """The CNOT (control, target) pairs of layer t (0..3).

    X-check: ancilla controls data. Z-check: data controls ancilla.
    """
    pairs = []
    for a, (typ, i, j) in enumerate(faces(d)):
        anc = num_data(d) + a
        order = X_ORDER if typ == "X" else Z_ORDER
        q = face_support(d, i, j, order)[t]
        if q is None:
            continue
        pairs.append((anc, q) if typ == "X" else (q, anc))
    return pairs


def memory_experiment(d, rounds, basis="Z"):
    """A noiseless distance-d memory experiment, structured like
    circuits.memory_experiment for the bicycle-chain code so both can be fed
    the same noise model and decoder pipeline later.

    1. Prepare every data qubit in |0> (basis "Z") or |+> (basis "X").
    2. Repeat `rounds` rounds of: reset ancillas, 4 CNOT layers, measure ancillas.
    3. Measure every data qubit in the prepared basis.

    Detectors:
      * first round: the checks of the prepared basis have known value +1;
      * later rounds: every check must match its value from the round before;
      * end: each prepared-basis check, rebuilt from the data, must match its
        last ancilla measurement.
    Observable 0: the logical of the prepared basis, read from the data.
    """
    if basis not in ("Z", "X"):
        raise ValueError("basis must be 'Z' or 'X'")
    if rounds < 1:
        raise ValueError("rounds must be >= 1")
    fs = faces(d)
    nd = num_data(d)
    data = list(range(nd))
    x_anc = [nd + a for a, f in enumerate(fs) if f[0] == "X"]
    z_anc = [nd + a for a, f in enumerate(fs) if f[0] == "Z"]
    Hx, Hz = rotated_surface_code(d)
    Lx, Lz = logicals(d)

    c = stim.Circuit()
    for q in data:
        r, col = divmod(q, d)
        c.append("QUBIT_COORDS", [q], (2 * col + 1, 2 * r + 1))
    for a, (_, i, j) in enumerate(fs):
        c.append("QUBIT_COORDS", [nd + a], (2 * j + 2, 2 * i + 2))

    c.append("R" if basis == "Z" else "RX", data)
    c.append("TICK")

    count = 0                                 # measurements so far

    def rec(idx):
        return stim.target_rec(idx - count)

    prev = None                               # (x_meas, z_meas) of last round
    for r in range(rounds):
        c.append("RX", x_anc)
        c.append("R", z_anc)
        c.append("TICK")
        for t in range(4):
            c.append("CX", [q for pair in layer_pairs(d, t) for q in pair])
            c.append("TICK")
        c.append("MX", x_anc)
        x_meas = list(range(count, count + len(x_anc)))
        count += len(x_anc)
        c.append("M", z_anc)
        z_meas = list(range(count, count + len(z_anc)))
        count += len(z_anc)

        same = z_meas if basis == "Z" else x_meas
        if r == 0:
            for k, m in enumerate(same):
                c.append("DETECTOR", [rec(m)], (k, r))
        else:
            for k, (m, pm) in enumerate(zip(x_meas, prev[0])):
                c.append("DETECTOR", [rec(m), rec(pm)], (k, r))
            for k, (m, pm) in enumerate(zip(z_meas, prev[1])):
                c.append("DETECTOR", [rec(m), rec(pm)], (len(x_meas) + k, r))
        prev = (x_meas, z_meas)
        c.append("TICK")

    c.append("M" if basis == "Z" else "MX", data)
    data_meas = list(range(count, count + nd))
    count += nd

    H, last, L = (Hz, prev[1], Lz) if basis == "Z" else (Hx, prev[0], Lx)
    for k, row in enumerate(H):
        support = [data_meas[q] for q in row.nonzero()[0]]
        c.append("DETECTOR", [rec(m) for m in support] + [rec(last[k])], (k, rounds))
    c.append("OBSERVABLE_INCLUDE", [rec(data_meas[q]) for q in L.nonzero()[0]], 0)
    return c


def stim_reference(d, rounds, basis="Z", p=0.0):
    """Stim's built-in rotated surface code memory circuit, as a cross-check.

    Not used for the comparison itself (its noise model is fixed by Stim), but
    handy for sanity-checking qubit counts and logical error rates.
    """
    kind = "surface_code:rotated_memory_" + basis.lower()
    return stim.Circuit.generated(
        kind, distance=d, rounds=rounds,
        after_clifford_depolarization=p,
        before_round_data_depolarization=p,
        before_measure_flip_probability=p,
        after_reset_flip_probability=p,
    )
