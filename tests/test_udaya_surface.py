"""The team's surface-code circuit (qec_star.surface) under the hardware noise layer.

Covers d = 3, 5, 7, 9 in both bases. Expected counts are derived by hand from
the code's structure: a rotated distance-d patch has d^2 data qubits and
d^2 - 1 checks, (d-1)^2 of weight 4 and 2(d-1) of weight 2, half X and half Z.
"""
import pytest
import stim

from qec_star import surface as sc
from qec_star.hardware import SCENARIOS, NoiseProfile, surface_block
from qec_star.hardware.experiments import (DECODERS, Cell, SamplingPlan, dem_logical_collisions,
                                           low_weight_fault_failures, run_cell,
                                           surface_integration_cells, surface_integration_shots)
from qec_star.hardware.models import SURFACE_ENTANGLING_LAYERS
from qec_star.hardware.noise import decorate_stim_memory, noise_census, operated_qubits

DISTANCES = [3, 5, 7, 9]
BASES = ["X", "Z"]
DISTINCT = NoiseProfile(.01, .02, .03, .04, .05, "distinct", .06)
pytestmark = pytest.mark.parametrize("d", DISTANCES)


def cnots_per_round(d):
    return 4 * (d - 1) ** 2 + 2 * 2 * (d - 1)          # sum of check weights


# ---------- the noiseless circuit ----------

@pytest.mark.parametrize("basis", BASES)
def test_structure(d, basis):
    rounds = 3
    c = sc.memory_experiment(d, rounds, basis)
    names = [op.name for op in c]
    assert c.num_qubits == len(operated_qubits(c)) == 2 * d * d - 1     # dense indices, no gaps
    assert c.num_observables == 1
    assert c.num_detectors == rounds * (d * d - 1)
    assert c.num_measurements == rounds * (d * d - 1) + d * d
    # X ancillas are prepared and measured directly: no Hadamard (or any 1-qubit gate).
    assert set(names) == {"QUBIT_COORDS", "R", "RX", "TICK", "CX", "MX", "M", "DETECTOR", "OBSERVABLE_INCLUDE"}
    assert names.count("CX") == rounds * SURFACE_ENTANGLING_LAYERS == rounds * 4


@pytest.mark.parametrize("basis", BASES)
def test_noiseless_circuit_is_deterministic_after_decoration(d, basis):
    clean = sc.memory_experiment(d, 3, basis)
    quiet = decorate_stim_memory(clean, NoiseProfile.paper(0))
    assert quiet == clean.flattened()
    dets, obs = quiet.compile_detector_sampler(seed=3).sample(50, separate_observables=True)
    assert not dets.any() and not obs.any()


# ---------- noise placement ----------

@pytest.mark.parametrize("basis", BASES)
def test_noise_location_counts(d, basis):
    rounds = 3 * d
    data, anc, cx = d * d, d * d - 1, cnots_per_round(d)
    census = noise_census(decorate_stim_memory(sc.memory_experiment(d, rounds, basis), DISTINCT))
    assert census == {
        "prep": data + rounds * anc,                       # data once, ancillas every round
        "two_qubit": rounds * cx,
        "idle": rounds * (4 * (data + anc) - 2 * cx),      # atoms a CNOT layer leaves untouched
        "measurement": rounds * anc + data,                # ancillas every round, data at the end
        "cycle_idle": (rounds - 1) * data,                 # data wait between rounds
    }
    assert census["one_qubit"] == 0


def test_idle_noise_lands_on_exactly_the_untouched_atoms(d):
    """First CNOT layer of the first round, checked against the code's own layer definition."""
    noisy = decorate_stim_memory(sc.memory_experiment(d, 1, "Z"), NoiseProfile(0, 0, 0, 0, .05))
    idle = [op for op in noisy if op.name == "DEPOLARIZE1"]
    assert len(idle) == 4
    for layer, op in enumerate(idle):
        used = {q for pair in sc.layer_pairs(d, layer) for q in pair}
        assert {t.value for t in op.targets_copy()} == set(range(2 * d * d - 1)) - used


@pytest.mark.parametrize("basis", BASES)
def test_records_detectors_and_observables_are_preserved(d, basis):
    clean = sc.memory_experiment(d, d, basis)
    noisy = decorate_stim_memory(clean, NoiseProfile.paper())
    assert noisy.without_noise() == clean.flattened()
    assert (noisy.num_measurements, noisy.num_detectors, noisy.num_observables) == (
        clean.num_measurements, clean.num_detectors, clean.num_observables)
    dem = noisy.detector_error_model(decompose_errors=False)
    assert dem.num_detectors == clean.num_detectors
    assert dem_logical_collisions(dem) == 0


def test_measurement_and_preparation_errors_reach_every_ancilla(d):
    noisy = decorate_stim_memory(sc.memory_experiment(d, 2, "Z"), NoiseProfile(.01, 0, 0, .04, 0))
    text = str(noisy)
    x_anc = (d * d - 1) // 2
    assert text.count("MX(0.04)") == 2 and text.count("M(0.04)") == 3      # 2 rounds, then the data
    measured = sum(len(op.targets_copy()) for op in noisy if op.name in ("M", "MX"))
    assert measured == 2 * (2 * x_anc) + d * d
    assert noise_census(noisy)["prep"] == d * d + 2 * (d * d - 1)


@pytest.mark.parametrize("basis", BASES)
def test_full_noise_model_keeps_the_code_distance(d, basis):
    noisy = decorate_stim_memory(sc.memory_experiment(d, d, basis), NoiseProfile.paper())
    assert len(noisy.shortest_graphlike_error()) == d


# ---------- against the Stim reference it replaces ----------

def test_differs_from_stim_reference_only_as_expected(d):
    """Same code and CNOT count; Stim adds Hadamards and one extra ancilla reset."""
    rounds, anc = 3 * d, d * d - 1
    team = noise_census(decorate_stim_memory(sc.memory_experiment(d, rounds), DISTINCT))
    ref_clean = sc.stim_reference(d, rounds)
    ref = noise_census(decorate_stim_memory(ref_clean, DISTINCT))
    assert ref_clean == stim.Circuit.generated("surface_code:rotated_memory_z", distance=d, rounds=rounds)
    for channel in ("two_qubit", "idle", "measurement", "cycle_idle"):
        assert team[channel] == ref[channel]
    assert team["one_qubit"] == 0 and ref["one_qubit"] == rounds * 2 * (anc // 2)   # H before and after
    assert ref["prep"] - team["prep"] == anc                                        # ancillas reset at start too


# ---------- hardware layer integration ----------

def test_block_footprint_uses_the_team_counts(d):
    block = surface_block(d)
    assert (block.data, block.ancillas, block.logical) == (sc.num_data(d), sc.num_ancilla(d), 1)
    assert block.physical == sc.atoms_per_logical(d) == 2 * d * d - 1


def test_every_registry_scenario_applies(d):
    clean = sc.memory_experiment(d, 2, "Z")
    for sid, scenario in SCENARIOS.items():
        noisy = decorate_stim_memory(clean, scenario.noise)
        assert noisy.num_detectors == clean.num_detectors, sid
        assert scenario.timing["surface"].entangling_layers == 4


def test_cells_and_decoders_accept_the_team_circuit(d):
    cell = Cell("T", "surface", (d,), "Z", d, NoiseProfile.paper())
    assert cell.circuit() == sc.memory_experiment(d, d, "Z")
    for decoder in DECODERS.values():
        record = run_cell(cell, SamplingPlan(shots=100, chunk_shots=50, workers=2), decoder=decoder)
        assert (record["architecture"], record["shots"], record["num_observables"]) == ("surface", 100, 1)
        assert record["noise_locations"].get("one_qubit", 0) == 0
    assert low_weight_fault_failures(cell.noisy_circuit(), weight=1, samples=40) == 0


def test_integration_grid(d):
    cells = surface_integration_cells()
    mine = [c for c in cells if c.architecture == "surface" and c.code == (d,)]
    assert len(cells) == len(set(cells)) == 15
    assert {(c.scenario_id, c.basis) for c in mine} == {
        ("paper/p1e-3", "Z"), ("paper/p1e-3", "X"), ("uniform/p0.002", "Z")}
    assert all(c.rounds == 3 * d for c in mine)
    assert all(surface_integration_shots(c) == (200_000 if d <= 5 else 40_000) for c in mine)
