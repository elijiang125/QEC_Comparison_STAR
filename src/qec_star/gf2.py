"""Linear algebra over GF(2), the field with two elements {0, 1}.

Why we need this
----------------
A stabilizer code's parity-check matrix H is a 0/1 matrix, and "applying two
checks" means adding their rows mod 2. So every question we ask about a code
(how many independent checks? how many logical qubits? which errors are
undetectable?) is a linear-algebra question where 1 + 1 = 0.

Over GF(2):
  * addition is XOR  (1 + 1 = 0), and
  * the only non-zero scalar is 1, so Gaussian elimination never divides:
    to clear a 1 we just XOR the pivot row into the other row.

All matrices here are numpy arrays of dtype uint8 holding 0s and 1s.
Vectors are 1-D uint8 arrays.
"""

import itertools

import numpy as np


def _as_gf2(M):
    """Return a fresh uint8 copy of M reduced mod 2 (so callers' arrays are never mutated)."""
    return (np.array(M, dtype=np.int64) % 2).astype(np.uint8)


# ---------------------------------------------------------------------------
# Row reduction and the things it gives us for free
# ---------------------------------------------------------------------------

def rref(H):
    """Reduced row echelon form of H over GF(2).

    Returns
    -------
    R : uint8 array, same shape as H
        Every pivot column has a single 1 (in its pivot row); zero rows are
        at the bottom.
    pivot_cols : list[int]
        Column index of the pivot in row 0, 1, 2, ... (len == rank).

    Algorithm: plain Gauss-Jordan elimination. For each column, find a row
    (at or below the current one) with a 1 there, swap it up, then XOR it
    into every *other* row that also has a 1 in that column.
    """
    R = _as_gf2(H)
    if R.ndim != 2:
        raise ValueError("rref expects a 2-D matrix")
    n_rows, n_cols = R.shape
    pivot_cols = []
    r = 0  # next row that will receive a pivot
    for c in range(n_cols):
        if r == n_rows:
            break
        # Look for a 1 in column c at or below row r.
        candidates = np.nonzero(R[r:, c])[0]
        if len(candidates) == 0:
            continue  # no pivot in this column -> it is a "free" column
        p = r + candidates[0]
        R[[r, p]] = R[[p, r]]  # swap the pivot row into place
        # Clear column c everywhere else. Adding (XOR) the pivot row is the
        # only operation needed because there is nothing to divide by.
        others = np.nonzero(R[:, c])[0]
        others = others[others != r]
        R[others] ^= R[r]
        pivot_cols.append(c)
        r += 1
    return R, pivot_cols


def rank(H):
    """Number of linearly independent rows of H over GF(2).

    For a check matrix this is the number of *independent* stabilizer
    generators; redundant checks (products of others) do not count.
    """
    H = np.asarray(H)
    if H.size == 0:
        return 0
    return len(rref(H)[1])


def nullspace(H):
    """Basis of the kernel {v : H v = 0 mod 2}, returned as the rows of a matrix.

    If H is a check matrix, the kernel is exactly the set of error patterns
    that trigger *no* check (zero syndrome): stabilizers and logicals live here.

    Construction: in RREF, each non-pivot ("free") column f gives one basis
    vector: set v[f] = 1, and set each pivot variable to whatever makes its
    row sum to zero, i.e. v[pivot_r] = R[r, f].
    """
    H = np.asarray(H)
    n = H.shape[1]
    if H.shape[0] == 0:
        return np.eye(n, dtype=np.uint8)  # no constraints: everything is in the kernel
    R, pivots = rref(H)
    pivot_set = set(pivots)
    free = [c for c in range(n) if c not in pivot_set]
    basis = np.zeros((len(free), n), dtype=np.uint8)
    for i, f in enumerate(free):
        basis[i, f] = 1
        for r, pc in enumerate(pivots):
            basis[i, pc] = R[r, f]
    return basis


def in_rowspace(H, v):
    """True if v is a GF(2) sum of rows of H.

    Test: appending v as an extra row does not increase the rank.
    For a stabilizer matrix this asks "is v (up to phase) a stabilizer?".
    """
    H = _as_gf2(H)
    v = _as_gf2(v).reshape(1, -1)
    if H.shape[0] == 0:
        return not v.any()
    return rank(np.vstack([H, v])) == rank(H)


def inverse(M):
    """Inverse of a square invertible matrix over GF(2) (row-reduce [M | I])."""
    M = _as_gf2(M)
    k = M.shape[0]
    if M.shape != (k, k):
        raise ValueError("inverse expects a square matrix")
    R, pivots = rref(np.hstack([M, np.eye(k, dtype=np.uint8)]))
    if pivots[:k] != list(range(k)):
        raise ValueError("matrix is singular over GF(2)")
    return R[:, k:]


# ---------------------------------------------------------------------------
# CSS-code quantities
# ---------------------------------------------------------------------------

def check_css(Hx, Hz):
    """Raise ValueError unless every X-check commutes with every Z-check.

    An X-check and a Z-check commute iff their supports overlap on an even
    number of qubits, so the condition is Hx @ Hz.T == 0 (mod 2).
    """
    Hx, Hz = _as_gf2(Hx), _as_gf2(Hz)
    if Hx.shape[1] != Hz.shape[1]:
        raise ValueError("Hx and Hz must have the same number of columns (qubits)")
    if ((Hx.astype(np.int64) @ Hz.T.astype(np.int64)) % 2).any():
        raise ValueError("X- and Z-checks do not commute: Hx @ Hz.T != 0 mod 2")


def css_k(Hx, Hz):
    """Number of logical qubits k of the CSS code (Hx, Hz).

    Each independent check halves the code space, so
        k = n - rank(Hx) - rank(Hz).
    """
    check_css(Hx, Hz)
    n = np.asarray(Hx).shape[1]
    return n - rank(Hx) - rank(Hz)


def _quotient_basis(kernel, sub):
    """Pick rows of `kernel` that are independent modulo rowspace(sub).

    Greedy: walk through the kernel basis, keep a vector only if it is not
    already in span(sub + kept vectors). The kept vectors represent distinct
    non-trivial cosets kernel / rowspace(sub), i.e. distinct logical operators.
    """
    span = _as_gf2(sub)
    current_rank = rank(span)
    picked = []
    for v in kernel:
        trial = np.vstack([span, v]) if span.shape[0] else v.reshape(1, -1)
        r = rank(trial)
        if r > current_rank:
            picked.append(v)
            span, current_rank = trial, r
    n = kernel.shape[1]
    return np.array(picked, dtype=np.uint8).reshape(-1, n)


def find_logicals(Hx, Hz):
    """Return (Lx, Lz): k X-logicals and k Z-logicals with Lx @ Lz.T = I (mod 2).

    * A Z-logical must commute with all X-checks  -> in ker(Hx),
      but must not itself be a Z-stabilizer      -> not in rowspace(Hz).
    * An X-logical is the same with the roles of Hx and Hz swapped.

    The raw choices pair up in some invertible k x k pattern M = Lx Lz^T.
    Replacing Lx by M^{-1} Lx makes the pairing the identity, which means
    X_i anticommutes with Z_i only (the usual "symplectic basis": logical
    qubit i has its own X and Z, which commute with every other qubit's).
    """
    check_css(Hx, Hz)
    Hx, Hz = _as_gf2(Hx), _as_gf2(Hz)
    Lz = _quotient_basis(nullspace(Hx), Hz)
    Lx = _quotient_basis(nullspace(Hz), Hx)
    k = css_k(Hx, Hz)
    assert Lx.shape[0] == Lz.shape[0] == k, "logical count disagrees with k"
    if k == 0:
        return Lx, Lz
    M = (Lx.astype(np.int64) @ Lz.T.astype(np.int64)) % 2
    Lx = (inverse(M).astype(np.int64) @ Lx.astype(np.int64)) % 2
    return Lx.astype(np.uint8), Lz


# ---------------------------------------------------------------------------
# Brute-force search for low-weight logicals (used for distance checks)
# ---------------------------------------------------------------------------

def low_weight_logicals(H_check, L_other, weight, chunk=200_000, stop_at_first=False):
    """All supports of exactly `weight` qubits that are non-trivial logicals.

    Parameters
    ----------
    H_check : the checks the operator must commute with (e.g. Hx for a Z-logical).
    L_other : logicals of the *other* type (e.g. Lx for a Z-logical).
    weight  : number of qubits in the support.

    Why L_other is enough to test "not a stabilizer": a vector v in ker(H_check)
    is a stabilizer iff it commutes with every logical of the other type
    (stabilizers commute with everything in the normalizer). So v is a
    non-trivial logical iff  H_check v = 0  and  L_other v != 0.

    Vectorized: we enumerate index tuples in chunks and sum the relevant
    columns of H_check and L_other mod 2 (a syndrome is just the XOR of the
    columns of the qubits that are hit).

    Returns a list of sorted index tuples.
    """
    H_check, L_other = _as_gf2(H_check), _as_gf2(L_other)
    n = H_check.shape[1]
    Hcols = H_check.T  # Hcols[q] = column of qubit q = syndrome of a single error on q
    Lcols = L_other.T
    found = []
    combos = itertools.combinations(range(n), weight)
    while True:
        block = list(itertools.islice(combos, chunk))
        if not block:
            break
        idx = np.array(block, dtype=np.int64)  # shape (N, weight)
        syndrome = Hcols[idx].sum(axis=1, dtype=np.int64) % 2  # (N, n_checks)
        flips = Lcols[idx].sum(axis=1, dtype=np.int64) % 2  # (N, k)
        hits = np.nonzero(~syndrome.any(axis=1) & flips.any(axis=1))[0]
        found.extend(tuple(int(q) for q in idx[h]) for h in hits)
        if stop_at_first and found:
            return found[:1]
    return found
