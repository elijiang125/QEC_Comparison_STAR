"""Noise adapter: placement, record preservation, and exact location counts.

Expected counts are derived by hand from the circuit structure, not taken
from the implementation.
"""
import numpy as np
import pytest
import stim

from qec_star.circuits import memory_experiment
from qec_star.hardware.models import NoiseProfile
from qec_star.hardware.noise import (decorate_stim_memory, expected_faults, noise_census,
                                     operated_qubits)

DISTINCT = NoiseProfile(.01, .02, .03, .04, .05, "distinct", .06)


def surface(d, rounds, basis="z"):
    return stim.Circuit.generated(f"surface_code:rotated_memory_{basis}", distance=d, rounds=rounds)


# ---------- placement on a hand-written circuit ----------

def test_channels_and_idle_placement():
    clean = stim.Circuit("R 0 1 2\nTICK\nH 0\nTICK\nCX 0 1\nTICK\nM 0 1\nDETECTOR rec[-1]")
    noisy = decorate_stim_memory(clean, DISTINCT)
    assert noisy == stim.Circuit("""
        R 0 1 2
        DEPOLARIZE1[prep](0.01) 0 1 2
        TICK
        H 0
        DEPOLARIZE1[one_qubit](0.02) 0
        TICK
        CX 0 1
        DEPOLARIZE2[two_qubit](0.03) 0 1
        DEPOLARIZE1[idle](0.05) 2
        TICK
        M(0.04) 0 1
        DETECTOR rec[-1]
        DEPOLARIZE1[cycle_idle](0.06) 2
    """)


def test_idle_is_charged_only_in_entangling_layers():
    # Qubit 1 idles through a single-qubit layer: the paper charges nothing there.
    noisy = decorate_stim_memory(stim.Circuit("R 0 1\nTICK\nH 0\nTICK\nM 0 1"), NoiseProfile.paper())
    assert noise_census(noisy)["idle"] == 0


def test_unallocated_qubits_never_idle():
    # Qubit index 1 is skipped by the circuit, like the gaps in Stim's surface codes.
    clean = stim.Circuit("R 0 2 3\nTICK\nCX 0 2\nTICK\nM 0 2 3")
    assert operated_qubits(clean) == {0, 2, 3}
    noisy = decorate_stim_memory(clean, DISTINCT)
    assert "DEPOLARIZE1[idle](0.05) 3\n" in str(noisy)
    # An explicit allocation can add a spectator atom that no gate touches.
    spectator = decorate_stim_memory(clean, DISTINCT, active_qubits=[0, 1, 2, 3])
    assert "DEPOLARIZE1[idle](0.05) 1 3\n" in str(spectator)


def test_measure_reset_gets_flip_and_reset_noise():
    noisy = decorate_stim_memory(stim.Circuit("RX 0\nTICK\nMRX 0"), DISTINCT)
    assert noisy == stim.Circuit("RX 0\nDEPOLARIZE1[prep](0.01) 0\nTICK\nMRX(0.04) 0\nDEPOLARIZE1[prep](0.01) 0")


def test_multi_pair_gate_is_one_layer():
    noisy = decorate_stim_memory(stim.Circuit("R 0 1 2 3 4\nTICK\nCX 0 1 2 3"), DISTINCT)
    assert "DEPOLARIZE2[two_qubit](0.03) 0 1 2 3\nDEPOLARIZE1[idle](0.05) 4" in str(noisy)
    assert noise_census(noisy)["two_qubit"] == 2


# ---------- explicit failures ----------

@pytest.mark.parametrize("text,match", [
    ("R 0\nX_ERROR(0.1) 0", "unsupported or already noisy"),
    ("R 0\nDEPOLARIZE1(0.1) 0", "unsupported or already noisy"),
    ("M(0.01) 0", "already parameterized"),
    ("MPP X0*X1", "unsupported"),
    ("R 0 1\nM 0\nCX rec[-1] 1", "direct, non-inverted"),
    ("M !0", "direct, non-inverted"),
    ("R 0 1 2\nCX 0 1 1 2", "overlapping"),
    ("R 0 1\nTICK\nCX 0 1\nH 0", "overlapping"),
    ("R 0 1 2\nTICK\nCX 0 1\nM 2", "mixes two-qubit gates and measurements"),
])
def test_rejects_unsupported_input(text, match):
    with pytest.raises(ValueError, match=match):
        decorate_stim_memory(stim.Circuit(text), NoiseProfile.paper())


def test_rejects_decorating_twice():
    once = decorate_stim_memory(surface(3, 2), NoiseProfile.paper())
    with pytest.raises(ValueError):
        decorate_stim_memory(once, NoiseProfile.paper())


@pytest.mark.parametrize("active", [[0, 0], [-1], [0, 9], [], [0.0]])
def test_rejects_bad_allocation(active):
    with pytest.raises(ValueError):
        decorate_stim_memory(stim.Circuit("R 0\nM 0"), NoiseProfile.paper(), active_qubits=active)


def test_rejects_gate_on_unallocated_qubit():
    with pytest.raises(ValueError, match="unallocated"):
        decorate_stim_memory(stim.Circuit("R 0 1\nM 0 1"), NoiseProfile.paper(), active_qubits=[0])


# ---------- the real memory circuits ----------

CIRCUITS = [(lambda b: memory_experiment(3, 7, 18, basis=b)),
            (lambda b: memory_experiment(4, 7, 6, basis=b)),
            (lambda b: surface(3, 9, b.lower())),
            (lambda b: surface(5, 15, b.lower()))]


@pytest.mark.parametrize("basis", ["X", "Z"])
@pytest.mark.parametrize("make", CIRCUITS)
def test_zero_noise_is_the_original_circuit(make, basis):
    clean = make(basis)
    assert decorate_stim_memory(clean, NoiseProfile.paper(0)) == clean.flattened()


@pytest.mark.parametrize("basis", ["X", "Z"])
@pytest.mark.parametrize("make", CIRCUITS)
def test_records_detectors_and_observables_are_preserved(make, basis):
    clean = make(basis)
    noisy = decorate_stim_memory(clean, NoiseProfile.paper())
    assert noisy.num_measurements == clean.num_measurements
    assert noisy.num_detectors == clean.num_detectors
    assert noisy.num_observables == clean.num_observables
    # Stripping the noise gives back exactly the clean circuit, record for record.
    assert noisy.without_noise() == clean.flattened()
    # Detectors stay deterministic, so the detector error model exists.
    dem = noisy.detector_error_model(decompose_errors=False)
    assert dem.num_detectors == clean.num_detectors


@pytest.mark.parametrize("make", CIRCUITS)
def test_noiseless_decorated_circuit_fires_nothing(make):
    quiet = decorate_stim_memory(make("Z"), NoiseProfile.paper(0))
    dets, obs = quiet.compile_detector_sampler(seed=1).sample(20, separate_observables=True)
    assert not dets.any() and not obs.any()


def test_repeat_blocks_are_unrolled_exactly():
    looped = surface(3, 5)
    assert any(isinstance(op, stim.CircuitRepeatBlock) for op in looped)
    assert decorate_stim_memory(looped, DISTINCT) == decorate_stim_memory(looped.flattened(), DISTINCT)


@pytest.mark.parametrize("l,rounds", [(3, 18), (4, 5)])
def test_bicycle_noise_location_counts(l, rounds):
    """Per round: 2lm ancilla resets and measurements, 8 layers x 2lm CNOTs.

    Every CNOT layer uses all 4lm qubits, so no qubit ever idles in an
    entangling layer: the paper's idle channel contributes nothing here.
    """
    n = 2 * l * 7                                   # data qubits = ancillas = 2lm
    census = noise_census(decorate_stim_memory(memory_experiment(l, 7, rounds), DISTINCT))
    assert census == {
        "prep": n + rounds * n,                      # data once, ancillas every round
        "two_qubit": rounds * 8 * n,
        "measurement": rounds * n + n,               # ancillas every round, data at the end
        "cycle_idle": rounds * n + n,                # data wait each round; ancillas at final readout
    }
    assert census["idle"] == 0 and census["one_qubit"] == 0


@pytest.mark.parametrize("d,rounds", [(3, 9), (5, 4), (9, 27)])
def test_surface_noise_location_counts(d, rounds):
    """Rotated patch: (d-1)^2 weight-4 and 2(d-1) weight-2 checks, half of each type X."""
    data, anc = d * d, d * d - 1
    cx = 4 * (d - 1) ** 2 + 2 * 2 * (d - 1)          # CNOTs per round = sum of check weights
    census = noise_census(decorate_stim_memory(surface(d, rounds), DISTINCT))
    assert census == {
        "prep": data + anc + rounds * anc,           # initial reset, then MR every round
        "one_qubit": rounds * 2 * (anc // 2),        # H before and after on each X ancilla
        "two_qubit": rounds * cx,
        "idle": rounds * (4 * (data + anc) - 2 * cx),
        "measurement": rounds * anc + data,
        "cycle_idle": (rounds - 1) * data,           # final data readout shares the last moment
    }


def test_expected_faults_scale_with_the_profile():
    clean = memory_experiment(3, 7, 2)
    p = NoiseProfile.paper(1e-3)
    base = expected_faults(decorate_stim_memory(clean, p), p)
    assert base == pytest.approx({"prep": 0.126, "two_qubit": 0.672, "measurement": 0.126})
    double = NoiseProfile(1e-3, 1e-3, 2e-3, 1e-3, 1e-3)
    assert expected_faults(decorate_stim_memory(clean, double), double)["two_qubit"] == pytest.approx(1.344)


def test_sampled_detection_rate_matches_first_order_prediction():
    """A lone measurement flip fires its detector at exactly the flip rate."""
    noisy = decorate_stim_memory(stim.Circuit("R 0\nTICK\nM 0\nDETECTOR rec[-1]"),
                                 NoiseProfile(0, 0, 0, 0.25, 0))
    fired = noisy.compile_detector_sampler(seed=7).sample(40_000).mean()
    assert abs(fired - 0.25) < 5 * np.sqrt(0.25 * 0.75 / 40_000)


def test_reset_depolarization_flips_z_basis_with_two_thirds_p():
    """After R, only X and Y of the depolarizing channel flip the outcome: 2p/3."""
    noisy = decorate_stim_memory(stim.Circuit("R 0\nTICK\nM 0\nDETECTOR rec[-1]"),
                                 NoiseProfile(0.3, 0, 0, 0, 0))
    fired = noisy.compile_detector_sampler(seed=7).sample(40_000).mean()
    assert abs(fired - 0.2) < 5 * np.sqrt(0.2 * 0.8 / 40_000)
