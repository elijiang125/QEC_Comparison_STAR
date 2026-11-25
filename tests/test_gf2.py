"""Tests for the GF(2) linear-algebra helpers, on small hand-checkable examples."""

import numpy as np
import pytest

from qec_star import codes, gf2


def mod2(a):
    return (np.asarray(a, dtype=np.int64) % 2).astype(np.uint8)


# --- rref / rank -----------------------------------------------------------

def test_rref_small_example():
    # Rows: r0 = 110, r1 = 011, r2 = 101 = r0 + r1, so rank is 2.
    H = np.array([[1, 1, 0], [0, 1, 1], [1, 0, 1]], dtype=np.uint8)
    R, pivots = gf2.rref(H)
    assert pivots == [0, 1]
    np.testing.assert_array_equal(R, [[1, 0, 1], [0, 1, 1], [0, 0, 0]])


def test_rref_does_not_mutate_input():
    H = np.array([[0, 1], [1, 1]], dtype=np.uint8)
    before = H.copy()
    gf2.rref(H)
    np.testing.assert_array_equal(H, before)


def test_rank_repetition_with_redundant_check():
    # 3-qubit repetition code with all three ZZ checks: Z0Z1, Z1Z2, Z0Z2.
    # The third is the product of the first two, so only 2 are independent.
    H = np.array([[1, 1, 0], [0, 1, 1], [1, 0, 1]], dtype=np.uint8)
    assert gf2.rank(H) == 2


def test_rank_identity_and_zero():
    assert gf2.rank(np.eye(5, dtype=np.uint8)) == 5
    assert gf2.rank(np.zeros((3, 4), dtype=np.uint8)) == 0
    assert gf2.rank(np.zeros((0, 4), dtype=np.uint8)) == 0


def test_rank_is_mod_2_not_real():
    # Over the reals these rows are independent; mod 2 the third is r0 + r1.
    H = np.array([[1, 1, 0, 0], [0, 1, 1, 0], [1, 2, 1, 0]])  # 2 == 0 mod 2
    assert gf2.rank(H) == 2


# --- nullspace / rowspace ---------------------------------------------------

def test_nullspace_is_kernel_and_has_right_dimension():
    H = codes.hamming_7_4()
    N = gf2.nullspace(H)
    assert N.shape == (7 - gf2.rank(H), 7)  # rank-nullity
    assert not mod2(H.astype(int) @ N.T).any()  # every basis vector is in ker(H)
    assert gf2.rank(N) == N.shape[0]  # and they are independent


def test_nullspace_of_empty_matrix_is_everything():
    N = gf2.nullspace(np.zeros((0, 3), dtype=np.uint8))
    np.testing.assert_array_equal(N, np.eye(3, dtype=np.uint8))


def test_in_rowspace():
    H = np.array([[1, 1, 0], [0, 1, 1]], dtype=np.uint8)
    assert gf2.in_rowspace(H, [1, 0, 1])  # r0 + r1
    assert gf2.in_rowspace(H, [0, 0, 0])  # empty sum
    assert not gf2.in_rowspace(H, [1, 0, 0])


def test_inverse():
    M = np.array([[1, 1], [0, 1]], dtype=np.uint8)
    Minv = gf2.inverse(M)
    np.testing.assert_array_equal(mod2(M.astype(int) @ Minv), np.eye(2))
    with pytest.raises(ValueError):
        gf2.inverse(np.array([[1, 1], [1, 1]]))


# --- css_k ------------------------------------------------------------------

@pytest.mark.parametrize(
    "name, Hx_Hz, k",
    [
        ("repetition(5)", codes.repetition(5), 1),
        ("[[4,2,2]]", codes.code_422(), 2),
        ("Steane", codes.steane(), 1),
        ("toric L=3", codes.toric(3), 2),
        ("toric L=4", codes.toric(4), 2),
    ],
)
def test_css_k_textbook_codes(name, Hx_Hz, k):
    Hx, Hz = Hx_Hz
    assert gf2.css_k(Hx, Hz) == k, name


def test_toric_size():
    Hx, Hz = codes.toric(3)
    assert Hx.shape == Hz.shape == (9, 18)  # n = 2 L^2
    assert set(Hx.sum(axis=1)) == set(Hz.sum(axis=1)) == {4}


def test_css_k_rejects_noncommuting_checks():
    # X0X1 and Z1Z2 overlap on one qubit -> they anticommute.
    Hx = np.array([[1, 1, 0]], dtype=np.uint8)
    Hz = np.array([[0, 1, 1]], dtype=np.uint8)
    with pytest.raises(ValueError):
        gf2.css_k(Hx, Hz)


# --- find_logicals ----------------------------------------------------------

@pytest.mark.parametrize(
    "Hx_Hz",
    [codes.repetition(3), codes.code_422(), codes.steane(), codes.toric(3), codes.toric(4)],
)
def test_find_logicals_are_valid_and_paired(Hx_Hz):
    Hx, Hz = Hx_Hz
    Lx, Lz = gf2.find_logicals(Hx, Hz)
    k = gf2.css_k(Hx, Hz)
    assert Lx.shape[0] == Lz.shape[0] == k
    # Logicals commute with the stabilizers of the other type ...
    assert not mod2(Hz.astype(int) @ Lx.T).any()
    assert not mod2(Hx.astype(int) @ Lz.T).any()
    # ... are not stabilizers themselves ...
    for v in Lx:
        assert not gf2.in_rowspace(Hx, v)
    for v in Lz:
        assert not gf2.in_rowspace(Hz, v)
    # ... and pair up as X_i <-> Z_i only (symplectic basis).
    np.testing.assert_array_equal(mod2(Lx.astype(int) @ Lz.T), np.eye(k, dtype=np.uint8))


def test_low_weight_logicals_steane_distance_3():
    Hx, Hz = codes.steane()
    Lx, _ = gf2.find_logicals(Hx, Hz)
    assert gf2.low_weight_logicals(Hx, Lx, 1) == []
    assert gf2.low_weight_logicals(Hx, Lx, 2) == []
    assert len(gf2.low_weight_logicals(Hx, Lx, 3)) > 0  # d = 3
