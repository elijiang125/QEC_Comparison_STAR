"""Tests for surface.py (rotated surface code baseline).

Uses the team's GF(2) tools from the repo (read-only) for the code checks.
"""

import numpy as np
import pytest
import stim

from qec_star import surface as sc
from qec_star import gf2

DS = [3, 5, 7]


def mod2(a):
    return (np.asarray(a, dtype=np.int64) % 2).astype(np.uint8)


def with_cnot_noise(circuit, p):
    """Copy of `circuit` with DEPOLARIZE2(p) after every CX layer.

    Test-only stand-in for the shared noise model (task 2), just enough to
    measure circuit-level distance.
    """
    out = stim.Circuit()
    for inst in circuit:
        out.append(inst)
        if inst.name == "CX":
            out.append("DEPOLARIZE2", inst.targets_copy(), p)
    return out


# ---------- counts ----------

@pytest.mark.parametrize("d", DS)
def test_qubit_counts(d):
    assert sc.num_data(d) == d * d
    assert sc.num_ancilla(d) == d * d - 1
    assert sc.num_qubits(d) == 2 * d * d - 1
    assert len(sc.faces(d)) == d * d - 1


def test_known_atom_counts():
    assert [sc.atoms_per_logical(d) for d in (3, 5, 7, 9, 11)] == [17, 49, 97, 161, 241]


def test_patches_for_budget():
    assert sc.patches_for_budget(84, 3) == 4    # 84 atoms = one [[42,6,6]] block
    assert sc.patches_for_budget(84, 5) == 1
    assert sc.patches_for_budget(156, 7) == 1   # 156 atoms = one [[78,6,10]] block


def test_even_distance_rejected():
    with pytest.raises(ValueError):
        sc.faces(4)


# ---------- code ----------

@pytest.mark.parametrize("d", DS)
def test_checks_commute_and_k_is_1(d):
    Hx, Hz = sc.rotated_surface_code(d)
    assert Hx.shape == Hz.shape == ((d * d - 1) // 2, d * d)
    assert set(Hx.sum(axis=1)) | set(Hz.sum(axis=1)) == {2, 4}
    assert gf2.css_k(Hx, Hz) == 1


@pytest.mark.parametrize("d", DS)
def test_logicals_are_valid(d):
    Hx, Hz = sc.rotated_surface_code(d)
    Lx, Lz = sc.logicals(d)
    assert not mod2(Hx.astype(int) @ Lz).any()   # Z-logical commutes with X-checks
    assert not mod2(Hz.astype(int) @ Lx).any()   # X-logical commutes with Z-checks
    assert int(Lx @ Lz) % 2 == 1                 # they anticommute
    assert not gf2.in_rowspace(Hz, Lz)
    assert not gf2.in_rowspace(Hx, Lx)


@pytest.mark.parametrize("d", [3, 5])
def test_code_distance_brute_force(d):
    Hx, Hz = sc.rotated_surface_code(d)
    Lx, Lz = gf2.find_logicals(Hx, Hz)
    for w in range(1, d):
        assert not gf2.low_weight_logicals(Hx, Lx, w, stop_at_first=True)
        assert not gf2.low_weight_logicals(Hz, Lz, w, stop_at_first=True)
    assert gf2.low_weight_logicals(Hx, Lx, d, stop_at_first=True)


# ---------- circuit ----------

@pytest.mark.parametrize("d", DS)
def test_each_layer_touches_each_qubit_at_most_once(d):
    for t in range(4):
        used = [q for pair in sc.layer_pairs(d, t) for q in pair]
        assert len(used) == len(set(used)), f"layer {t} reuses a qubit"


@pytest.mark.parametrize("d", DS)
def test_ancillas_touch_exactly_their_check(d):
    Hx, Hz = sc.rotated_surface_code(d)
    H = np.vstack([Hx, Hz])
    nd = sc.num_data(d)
    touched = {a: set() for a in range(len(H))}
    for t in range(4):
        for ctrl, targ in sc.layer_pairs(d, t):
            anc, dat = (ctrl, targ) if ctrl >= nd else (targ, ctrl)
            touched[anc - nd].add(dat)
    for a, row in enumerate(H):
        assert touched[a] == set(row.nonzero()[0].tolist())


@pytest.mark.parametrize("d", DS)
@pytest.mark.parametrize("basis", ["Z", "X"])
def test_noiseless_memory_is_deterministic(d, basis):
    c = sc.memory_experiment(d, rounds=3, basis=basis)
    assert c.num_qubits == sc.num_qubits(d)
    c.detector_error_model()  # raises if any detector or observable is non-deterministic
    dets, obs = c.compile_detector_sampler().sample(200, separate_observables=True)
    assert not dets.any() and not obs.any()


@pytest.mark.parametrize("d", DS)
def test_matches_stim_reference_size(d):
    ours = sc.memory_experiment(d, rounds=d)
    ref = sc.stim_reference(d, rounds=d)
    # Stim's reference indexes qubits sparsely, so count the qubits it places.
    assert ours.num_qubits == len(ref.get_final_qubit_coordinates())
    assert ours.num_detectors == ref.num_detectors
    assert ours.num_observables == ref.num_observables


@pytest.mark.parametrize("d", DS)
@pytest.mark.parametrize("basis", ["Z", "X"])
def test_circuit_keeps_full_distance(d, basis):
    """Hook errors must not shorten the distance: the smallest set of CNOT
    faults that flips the logical without tripping a detector has size d."""
    c = with_cnot_noise(sc.memory_experiment(d, rounds=d, basis=basis), 1e-3)
    err = c.shortest_graphlike_error()
    assert len(err) == d


def test_decodes_with_pymatching():
    """End-to-end: noisy d=5 memory decodes with matching, and d=5 beats d=3."""
    import pymatching

    rates = {}
    for d in (3, 5):
        c = with_cnot_noise(sc.memory_experiment(d, rounds=d), 2e-3)
        m = pymatching.Matching.from_detector_error_model(c.detector_error_model(decompose_errors=True))
        dets, obs = c.compile_detector_sampler(seed=1).sample(20_000, separate_observables=True)
        rates[d] = np.mean(m.decode_batch(dets)[:, 0] != obs[:, 0])
    assert rates[5] < rates[3] < 0.05
