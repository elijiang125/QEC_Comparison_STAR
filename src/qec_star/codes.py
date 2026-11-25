"""Parity-check matrices for a few CSS codes.

Convention: each function returns (Hx, Hz), two uint8 matrices with one row per
check and one column per physical qubit.
  * a row of Hx is an X-type stabilizer (detects Z errors),
  * a row of Hz is a Z-type stabilizer (detects X errors).
A code with no X-checks has Hx of shape (0, n), so formulas like
k = n - rank(Hx) - rank(Hz) still work without special cases.
"""

import numpy as np


# ---------------------------------------------------------------------------
# Textbook codes (sanity checks for the GF(2) tools)
# ---------------------------------------------------------------------------

def repetition(n):
    """Bit-flip repetition code on n qubits: [[n, 1, 1]] as a quantum code.

    Z_i Z_{i+1} checks catch single X errors (classical distance n), but there
    are no X-checks at all, so a single Z error is an undetectable logical:
    quantum distance 1. It is a "half" CSS code: Hx is empty.
    """
    Hz = np.zeros((n - 1, n), dtype=np.uint8)
    for i in range(n - 1):
        Hz[i, i] = Hz[i, i + 1] = 1
    Hx = np.zeros((0, n), dtype=np.uint8)
    return Hx, Hz


def code_422():
    """[[4, 2, 2]] code: stabilizers XXXX and ZZZZ.

    Smallest code that detects any single-qubit error; encodes 2 qubits.
    """
    H = np.ones((1, 4), dtype=np.uint8)
    return H.copy(), H.copy()


def hamming_7_4():
    """Check matrix of the classical [7, 4, 3] Hamming code.

    Column j (1-indexed) is the binary representation of j, so a single bit
    flip on bit j produces syndrome = j in binary.
    """
    return np.array([[(j >> b) & 1 for j in range(1, 8)] for b in range(3)], dtype=np.uint8)


def steane():
    """Steane [[7, 1, 3]] code: Hamming check matrix used for both X and Z.

    Works because the Hamming code contains its own dual (H H^T = 0), so the
    X- and Z-checks commute.
    """
    H = hamming_7_4()
    return H.copy(), H.copy()


def toric(L):
    """Kitaev toric code on an L x L torus: [[2 L^2, 2, L]].

    Qubits live on edges. Edge indexing:
      horizontal edge leaving vertex (i, j) to the right : i*L + j
      vertical   edge leaving vertex (i, j) downward     : L*L + i*L + j
    X-checks = vertices (star of 4 edges), Z-checks = plaquettes (4 edges).
    A star and a plaquette always share 0 or 2 edges, so they commute.
    """
    n = 2 * L * L

    def h(i, j):
        return (i % L) * L + (j % L)

    def v(i, j):
        return L * L + (i % L) * L + (j % L)

    Hx = np.zeros((L * L, n), dtype=np.uint8)
    Hz = np.zeros((L * L, n), dtype=np.uint8)
    for i in range(L):
        for j in range(L):
            r = i * L + j
            # Star at vertex (i, j): edges to the right, left, down and up.
            for q in (h(i, j), h(i, j - 1), v(i, j), v(i - 1, j)):
                Hx[r, q] = 1
            # Plaquette with top-left corner (i, j): top, bottom, left, right edges.
            for q in (h(i, j), h(i + 1, j), v(i, j), v(i, j + 1)):
                Hz[r, q] = 1
    return Hx, Hz


# ---------------------------------------------------------------------------
# The STAR paper's code
# ---------------------------------------------------------------------------

# a(x, y) = 1 + y^3 + x y^2 + x y^4, written as exponent pairs (p, q) for x^p y^q.
DEFAULT_A = ((0, 0), (0, 3), (1, 2), (1, 4))


def cell(i, j, m):
    """Index of torus cell (i, j) inside one half (row-major: i*m + j)."""
    return i * m + j


def shift_matrix(l, m, p, q):
    """Permutation matrix of the monomial x^p y^q on the l x m torus.

    Row (i, j) has its 1 in column ((i+p) mod l, (j+q) mod m). Over GF(2),
    a polynomial a(x, y) is then just the sum (XOR) of its monomials' matrices.
    """
    S = np.zeros((l * m, l * m), dtype=np.uint8)
    for i in range(l):
        for j in range(m):
            S[cell(i, j, m), cell((i + p) % l, (j + q) % m, m)] = 1
    return S


def poly_matrix(l, m, monomials):
    """Matrix of the polynomial sum_{(p,q)} x^p y^q, added mod 2."""
    A = np.zeros((l * m, l * m), dtype=np.uint8)
    for p, q in monomials:
        A ^= shift_matrix(l, m, p, q)
    return A


def bicycle_chain_matrix(l, m, a=DEFAULT_A):
    """The single check matrix H = [A | A^T] of the bicycle-chain code (l*m x 2*l*m)."""
    A = poly_matrix(l, m, a)
    return np.hstack([A, A.T])


def bicycle_chain(l, m, a=DEFAULT_A):
    """Bicycle-chain code from the STAR paper, returned as (Hx, Hz).

    Generalized-bicycle construction: with commuting matrices A and B,
    Hx = [A | B] and Hz = [B^T | A^T] commute because A B + B A = 0 mod 2.
    The paper picks B = A^T, which makes Hx = Hz = [A | A^T]: the code is
    *self-dual* (the same pattern serves as an X-check and a Z-check).

    Qubits: n = 2 l m, two "halves" (left = first l*m columns,
    right = last l*m) each laid out on an l x m torus with cell (i, j) at
    index i*m + j. Each check has weight 2 * (#monomials) = 8.
    """
    H = bicycle_chain_matrix(l, m, a)
    return H.copy(), H.copy()


def torus_shift_permutation(l, m, di=0, dj=0):
    """Qubit permutation for (i, j) -> (i+di, j+dj) applied to *both* halves.

    Returns perm with perm[q] = new index of qubit q. Applying it to a vector v
    (support moves along with the qubits) is  w[perm] = v.
    """
    half = l * m
    perm = np.empty(2 * half, dtype=np.int64)
    for i in range(l):
        for j in range(m):
            src = cell(i, j, m)
            dst = cell((i + di) % l, (j + dj) % m, m)
            perm[src] = dst
            perm[half + src] = half + dst
    return perm


def apply_permutation(v, perm):
    """Move the support of v (1-D, or rows of a 2-D array) along a qubit permutation."""
    v = np.asarray(v)
    w = np.zeros_like(v)
    w[..., perm] = v
    return w


# ---------------------------------------------------------------------------
# Slices of the torus and the paper's "disjoint" logical basis
# ---------------------------------------------------------------------------

def slice_qubits(l, m, side, row=None, col=None):
    """Qubit indices of one slice of one half of the bicycle-chain torus.

    side : "L" (first l*m qubits) or "R" (last l*m qubits).
    Give exactly one of
      row=i : the m qubits {(i, j) : j = 0..m-1}  (runs along the y / j direction)
      col=j : the l qubits {(i, j) : i = 0..l-1}  (runs along the x / i direction)
    """
    if (row is None) == (col is None):
        raise ValueError("give exactly one of row= or col=")
    offset = 0 if side == "L" else l * m
    if row is not None:
        return [offset + cell(row, j, m) for j in range(m)]
    return [offset + cell(i, col, m) for i in range(l)]


def row_slice_logicals(l, m):
    """The 2l disjoint logical representatives found by brute force (see notes/02).

    Row i of the left half, then row i of the right half, as 0/1 vectors:
    each is the all-ones vector on the m qubits {(i, j)} of that half.
    Because the code is self-dual, each support works as both an X- and a
    Z-logical. Order: [L0, L1, ..., L_{l-1}, R0, ..., R_{l-1}].
    """
    n = 2 * l * m
    rows = []
    for side in ("L", "R"):
        for i in range(l):
            v = np.zeros(n, dtype=np.uint8)
            v[slice_qubits(l, m, side, row=i)] = 1
            rows.append(v)
    return np.array(rows, dtype=np.uint8)
