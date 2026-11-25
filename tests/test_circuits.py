"""Tests for plan steps 2-4: qubit layout, one syndrome round, memory experiment."""

import numpy as np
import pytest
import stim

from qec_star.circuits import (
    ancilla_supports, layer_pairs, memory_experiment, single_round_circuit, TABLE_II,
)
from qec_star.codes import bicycle_chain_matrix, row_slice_logicals
from qec_star.layout import Layout

SIZES = [(3, 7), (4, 7)]


# ---------- step 2: layout ----------

def test_layout_indices_are_distinct_and_cover_everything():
    lay = Layout(3, 7)
    qs = [lay.data(h, i, j) for h in "LR" for i, j in lay.cells()]
    qs += [lay.x_anc(i, j) for i, j in lay.cells()] + [lay.z_anc(i, j) for i, j in lay.cells()]
    assert sorted(qs) == list(range(lay.num_qubits)) == list(range(84))


def test_slide_by_one_stays_put():
    lay = Layout(3, 7)
    assert all(lay.slide(i, j, (0, 0)) == (i, j) for i, j in lay.cells())


def test_slide_by_x_moves_one_row_down_and_wraps():
    lay = Layout(3, 7)
    assert lay.slide(0, 5, (1, 0)) == (1, 5)
    assert lay.slide(2, 5, (1, 0)) == (0, 5)          # off the bottom, back at the top


def test_slide_by_inverse_undoes_slide():
    lay = Layout(3, 7)
    for i, j in lay.cells():
        assert lay.slide(*lay.slide(i, j, (1, 4)), (1, 4), sign=-1) == (i, j)


# ---------- step 3: one round of checks ----------

@pytest.mark.parametrize("l,m", SIZES)
def test_each_layer_touches_each_qubit_at_most_once(l, m):
    lay = Layout(l, m)
    for t in range(len(TABLE_II)):
        used = [q for pair in layer_pairs(lay, t) for q in pair]
        assert len(used) == len(set(used)), f"layer {t + 1} reuses a qubit"


@pytest.mark.parametrize("l,m", SIZES)
def test_ancillas_touch_exactly_their_check(l, m):
    """Over the 8 layers, ancilla (i, j) must touch exactly the 8 qubits of row i*m+j of H."""
    H = bicycle_chain_matrix(l, m)
    x_sup, z_sup = ancilla_supports(Layout(l, m))
    for c in range(l * m):
        want = set(H[c].nonzero()[0].tolist())
        assert x_sup[c] == want, f"X-check {c} touches the wrong qubits"
        assert z_sup[c] == want, f"Z-check {c} touches the wrong qubits"


def _pauli(kind, qubits):
    return "*".join(f"{kind}{q}" for q in qubits)


@pytest.mark.parametrize("l,m", SIZES)
def test_round_measures_each_check_and_leaves_data_alone(l, m):
    """Stim 'flows' prove what the noiseless circuit does, for every input state:

    - check -> rec:    the ancilla's result equals the check's value going in;
    - check -> check:  the check itself survives the round;
    - logical -> logical: the stored logical information is untouched.
    """
    H = bicycle_chain_matrix(l, m)
    circuit = single_round_circuit(l, m)
    n_meas = circuit.num_measurements                  # X results first, then Z results
    n_checks = l * m
    flows = []
    for c in range(n_checks):
        sup = H[c].nonzero()[0]
        x_rec = c - n_meas                             # rec index of X-check c
        z_rec = n_checks + c - n_meas                  # rec index of Z-check c
        flows.append(stim.Flow(f"{_pauli('X', sup)} -> rec[{x_rec}]"))
        flows.append(stim.Flow(f"{_pauli('Z', sup)} -> rec[{z_rec}]"))
        flows.append(stim.Flow(f"{_pauli('X', sup)} -> {_pauli('X', sup)}"))
        flows.append(stim.Flow(f"{_pauli('Z', sup)} -> {_pauli('Z', sup)}"))
    for row in row_slice_logicals(l, m):
        sup = row.nonzero()[0]
        flows.append(stim.Flow(f"{_pauli('X', sup)} -> {_pauli('X', sup)}"))
        flows.append(stim.Flow(f"{_pauli('Z', sup)} -> {_pauli('Z', sup)}"))
    ok = circuit.has_all_flows(flows)
    assert ok, "the round does not measure the intended checks cleanly"


def test_a_wrong_convention_is_caught():
    """Sanity check of the test itself: X-check 0 must NOT measure some other check's support."""
    H = bicycle_chain_matrix(3, 7)
    circuit = single_round_circuit(3, 7)
    other = H[1].nonzero()[0]
    assert not circuit.has_flow(stim.Flow(f"{_pauli('X', other)} -> rec[{-circuit.num_measurements}]"))


# ---------- step 4: memory experiment ----------

@pytest.mark.parametrize("l,m", SIZES)
@pytest.mark.parametrize("basis", ["Z", "X"])
def test_noiseless_memory_never_fires(l, m, basis):
    c = memory_experiment(l, m, rounds=6, basis=basis)
    dets, obs = c.compile_detector_sampler().sample(1000, separate_observables=True)
    assert not dets.any(), "a detector fired without any noise"
    assert not obs.any(), "a logical flipped without any noise"
    assert c.num_observables == 2 * l


def test_detector_count():
    l, m, r = 3, 7, 6
    c = memory_experiment(l, m, rounds=r, basis="Z")
    # first round: 21 Z-detectors; next r-1 rounds: 42 each; final data check: 21
    assert c.num_detectors == l * m + (r - 1) * 2 * l * m + l * m


def test_one_injected_error_fires_its_four_checks():
    """Flip left data qubit (0,0) after round 1: exactly checks 1, 5, 18, 20 notice in round 2,
    the same four the interactive code explorer shows."""
    l, m = 3, 7
    lay = Layout(l, m)
    c = memory_experiment(l, m, rounds=4, basis="Z", x_errors_after_round={1: [lay.data("L", 0, 0)]})
    dets = c.compile_detector_sampler().sample(1)[0]
    coords = c.get_detector_coordinates()
    fired = sorted(int(coords[d][0] * m + coords[d][1]) + 1 for d in np.nonzero(dets)[0])
    rounds_fired = {int(coords[d][2]) for d in np.nonzero(dets)[0]}
    assert fired == [1, 5, 18, 20]
    assert rounds_fired == {2}
