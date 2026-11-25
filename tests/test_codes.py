"""Tests for the bicycle-chain code from the STAR paper (arXiv:2606.25011).

Findings are written up in notes/02-bicycle-chain-findings.md.
"""

import itertools

import numpy as np
import pytest

from qec_star import codes, gf2


def mod2(a):
    return (np.asarray(a, dtype=np.int64) % 2).astype(np.uint8)


def is_nontrivial_logical(H, v):
    """Self-dual code: v is a logical iff H v = 0 and v is not a stabilizer."""
    return not mod2(H.astype(int) @ v).any() and not gf2.in_rowspace(H, v)


# --- Basic parameters -------------------------------------------------------

def test_bicycle_chain_3x7_basics():
    Hx, Hz = codes.bicycle_chain(3, 7)
    H = Hx
    assert H.shape == (21, 42)
    np.testing.assert_array_equal(Hx, Hz)  # self-dual: B = A^T gives Hx = Hz
    assert not mod2(H.astype(int) @ H.T).any()  # checks commute: H H^T = 0
    assert set(H.sum(axis=1)) == {8}  # every check has weight 8
    assert gf2.rank(H) == 18  # 3 of the 21 checks are redundant
    assert gf2.css_k(Hx, Hz) == 6


@pytest.mark.parametrize(
    "l, m, n, rank, k",
    [
        (3, 7, 42, 18, 6),  # [[42, 6, 6]]
        (4, 7, 56, 24, 8),  # [[14l, 2l, 6]] with l = 4
        (3, 11, 66, 30, 6),  # [[66, 6, 8]]
        (3, 13, 78, 36, 6),  # [[78, 6, 10]]
    ],
)
def test_bicycle_chain_n_rank_k(l, m, n, rank, k):
    Hx, Hz = codes.bicycle_chain(l, m)
    assert Hx.shape[1] == n
    assert gf2.rank(Hx) == rank
    assert gf2.css_k(Hx, Hz) == k


@pytest.mark.parametrize("l", [2, 3, 4, 5])
def test_m7_family_has_k_equal_2l(l):
    Hx, Hz = codes.bicycle_chain(l, 7)
    assert gf2.css_k(Hx, Hz) == 2 * l  # [[14l, 2l, 6]]


def test_find_logicals_on_bicycle_chain():
    Hx, Hz = codes.bicycle_chain(3, 7)
    Lx, Lz = gf2.find_logicals(Hx, Hz)
    assert Lx.shape == Lz.shape == (6, 42)
    np.testing.assert_array_equal(mod2(Lx.astype(int) @ Lz.T), np.eye(6, dtype=np.uint8))


# --- Investigation 1: which slices hold logicals? ---------------------------

def slice_logicals(H, qubits):
    """Brute force: all non-empty subsets of `qubits` that are non-trivial logicals."""
    n = H.shape[1]
    found = []
    for r in range(1, len(qubits) + 1):
        for S in itertools.combinations(qubits, r):
            v = np.zeros(n, dtype=np.uint8)
            v[list(S)] = 1
            if is_nontrivial_logical(H, v):
                found.append(S)
    return found


@pytest.mark.parametrize("l", [3, 4])
def test_row_slices_hold_exactly_one_logical_each(l):
    """Fixed row i (m = 7 qubits): the only logical is the whole row (weight 7)."""
    m = 7
    H = codes.bicycle_chain_matrix(l, m)
    for side in ("L", "R"):
        for i in range(l):
            qs = codes.slice_qubits(l, m, side, row=i)
            assert slice_logicals(H, qs) == [tuple(qs)], (side, i)


@pytest.mark.parametrize("l", [3, 4])
def test_column_slices_hold_no_logicals(l):
    """Fixed column j (l qubits): no subset is a logical, so slices are rows."""
    m = 7
    H = codes.bicycle_chain_matrix(l, m)
    for side in ("L", "R"):
        for j in range(m):
            qs = codes.slice_qubits(l, m, side, col=j)
            assert slice_logicals(H, qs) == [], (side, j)


@pytest.mark.parametrize("l, m", [(3, 7), (4, 7), (3, 11), (3, 13)])
def test_row_slice_logicals_form_symplectic_basis(l, m):
    H = codes.bicycle_chain_matrix(l, m)
    Ls = codes.row_slice_logicals(l, m)
    assert Ls.shape[0] == 2 * l == gf2.css_k(H, H)
    # Odd weight (= m) and pairwise disjoint supports.
    assert set(Ls.sum(axis=1)) == {m}
    assert (Ls.sum(axis=0) <= 1).all()
    # Each is a logical (commutes with all checks).
    assert not mod2(H.astype(int) @ Ls.T).any()
    # Overlap parity: X-version of L_a vs Z-version of L_b. Disjoint + odd weight
    # => identity, so X_a and Z_a anticommute and everything else commutes.
    np.testing.assert_array_equal(mod2(Ls.astype(int) @ Ls.T), np.eye(2 * l, dtype=np.uint8))
    # Independent modulo stabilizers: they span all 2l logical directions.
    assert gf2.rank(np.vstack([H, Ls])) == gf2.rank(H) + 2 * l


# --- Investigation 2: the shift automorphism --------------------------------

@pytest.mark.parametrize("l, m", [(3, 7), (4, 7)])
def test_shift_preserves_stabilizer_group(l, m):
    """(i, j) -> (i+1, j) on both halves maps rowspace(H) onto itself."""
    H = codes.bicycle_chain_matrix(l, m)
    perm = codes.torus_shift_permutation(l, m, di=1)
    H_shifted = codes.apply_permutation(H, perm)
    for row in H_shifted:
        assert gf2.in_rowspace(H, row)
    assert gf2.rank(np.vstack([H, H_shifted])) == gf2.rank(H)


@pytest.mark.parametrize("l, m", [(3, 7), (4, 7)])
def test_shift_cycles_left_and_right_logicals_separately(l, m):
    """Shift sends L_i -> L_{i+1 mod l} and R_i -> R_{i+1 mod l}: two l-cycles."""
    Ls = codes.row_slice_logicals(l, m)
    perm = codes.torus_shift_permutation(l, m, di=1)
    shifted = codes.apply_permutation(Ls, perm)
    for i in range(l):
        np.testing.assert_array_equal(shifted[i], Ls[(i + 1) % l])  # left half
        np.testing.assert_array_equal(shifted[l + i], Ls[l + (i + 1) % l])  # right half


def test_j_shift_fixes_each_row_logical():
    """For contrast: (i, j) -> (i, j+1) is also an automorphism but fixes every row logical."""
    l, m = 3, 7
    H = codes.bicycle_chain_matrix(l, m)
    perm = codes.torus_shift_permutation(l, m, dj=1)
    assert gf2.rank(np.vstack([H, codes.apply_permutation(H, perm)])) == gf2.rank(H)
    Ls = codes.row_slice_logicals(l, m)
    np.testing.assert_array_equal(codes.apply_permutation(Ls, perm), Ls)


# --- Investigation 3: distance of [[42, 6, 6]] -----------------------------

@pytest.mark.slow
def test_distance_42_6_6():
    """No logical of weight <= 5 (~1M supports checked), and one of weight 6 exists.

    The code is self-dual (Hx = Hz), so X- and Z-distance are equal and it is
    enough to search for Z-type logicals: H v = 0 and v anticommutes with some
    X-logical.
    """
    H = codes.bicycle_chain_matrix(3, 7)
    Lx, _ = gf2.find_logicals(H, H)
    for w in range(1, 6):
        assert gf2.low_weight_logicals(H, Lx, w) == [], f"found a weight-{w} logical"
    (support,) = gf2.low_weight_logicals(H, Lx, 6, stop_at_first=True)
    v = np.zeros(42, dtype=np.uint8)
    v[list(support)] = 1
    # Double-check with the direct definition (independent of Lx).
    assert is_nontrivial_logical(H, v)
