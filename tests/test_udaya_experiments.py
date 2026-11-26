"""Experiment runner: statistics helpers, determinism, provenance and decoder guards."""
import pytest
import stim

from qec_star.hardware.experiments import (DECODERS, Cell, SamplingPlan, code_revision,
                                           dem_logical_collisions, load_records,
                                           low_weight_fault_failures, per_round_rate, predictor,
                                           run_cell, run_grid, validation_cells, validation_shots,
                                           wilson_interval)
from qec_star.hardware.models import NoiseProfile
from qec_star.hardware.noise import decorate_stim_memory

SMALL = SamplingPlan(shots=350, chunk_shots=100, workers=2, seed=5)
BPOSD = DECODERS["bposd0"]


def test_wilson_interval_known_values():
    low, high = wilson_interval(0, 100)
    assert low == 0 and high == pytest.approx(0.0370, abs=5e-4)     # the "rule of three" scale
    low, high = wilson_interval(50, 100)
    assert (low, high) == pytest.approx((0.4038, 0.5962), abs=5e-4)
    assert wilson_interval(100, 100)[1] == 1
    for bad in [(1, 0), (-1, 5), (6, 5)]:
        with pytest.raises(ValueError):
            wilson_interval(*bad)


def test_per_round_rate_inverts_the_parity_formula():
    r, rounds = 0.01, 18
    shot = (1 - (1 - 2*r) ** rounds) / 2
    assert per_round_rate(shot, rounds) == pytest.approx(r)
    assert per_round_rate(0, 5) == 0
    with pytest.raises(ValueError):
        per_round_rate(0.5, 5)


@pytest.mark.parametrize("arch,code,rounds", [("bicycle", (3, 7), 2), ("surface_reference", (3,), 3)])
@pytest.mark.parametrize("basis", ["X", "Z"])
def test_cells_build_both_architectures_and_bases(arch, code, rounds, basis):
    cell = Cell("T", arch, code, basis, rounds, NoiseProfile.paper())
    noisy = cell.noisy_circuit()
    assert noisy.num_detectors == cell.circuit().num_detectors > 0
    noisy.detector_error_model(decompose_errors=False)


def test_invalid_cell():
    with pytest.raises(ValueError):
        Cell("T", "toric", (3,), "Z", 1, NoiseProfile.paper()).circuit()
    with pytest.raises(ValueError):
        Cell("T", "bicycle", (3, 7), "Y", 1, NoiseProfile.paper()).circuit()


def test_noiseless_run_never_fails_and_records_provenance():
    record = run_cell(Cell("T", "surface_reference", (3,), "Z", 3, NoiseProfile.paper(0)), SMALL,
                      decoder=BPOSD)
    assert (record["shots"], record["failures"], record["design"]) == (350, 0, "fixed_shots")
    assert record["wilson95"][0] == 0 and record["wilson95"][1] < 0.011
    for key in ("circuit_sha256", "decoder", "sampling_plan", "chunks", "runtime_seconds",
                "code_revision", "versions", "noise", "per_observable_failures", "noise_locations"):
        assert key in record
    # Exactly the planned shots: three full chunks and one of 50.
    assert [c["shots"] for c in record["chunks"]] == [100, 100, 100, 50]
    assert len({c["seed"] for c in record["chunks"]}) == 4
    assert set(record["code_revision"]) == {"commit", "source_tree", "dirty"}
    assert record["versions"]["stim"] and "tesseract-decoder" in record["versions"]


def test_shot_count_never_depends_on_outcomes():
    for p in (0.0, 0.03):
        record = run_cell(Cell("T", "surface_reference", (3,), "Z", 3, NoiseProfile.paper(p)), SMALL,
                          decoder=BPOSD)
        assert record["shots"] == 350


@pytest.mark.parametrize("bad", [dict(shots=0), dict(chunk_shots=0), dict(workers=0), dict(shots=1.5)])
def test_invalid_sampling_plan(bad):
    with pytest.raises(ValueError):
        SamplingPlan(**bad)


def test_runs_are_reproducible_and_seeds_differ_between_circuits(tmp_path):
    noisy = Cell("T", "surface_reference", (3,), "Z", 3, NoiseProfile.paper(0.01))
    first, second = run_cell(noisy, SMALL, decoder=BPOSD), run_cell(noisy, SMALL, decoder=BPOSD)
    assert first["chunks"] == second["chunks"] and first["failures"] == second["failures"] > 0
    # The worker count does not change the result.
    one_worker = run_cell(noisy, SamplingPlan(350, 100, 1, 5), decoder=BPOSD)
    assert one_worker["chunks"] == first["chunks"]
    other = run_cell(Cell("T", "surface_reference", (3,), "X", 3, NoiseProfile.paper(0.01)), SMALL,
                     decoder=BPOSD)
    assert {c["seed"] for c in other["chunks"]}.isdisjoint(c["seed"] for c in first["chunks"])
    # Failures across chunks add up, and no observable fails more often than the shot does.
    assert sum(c["failures"] for c in first["chunks"]) == first["failures"]
    assert max(first["per_observable_failures"]) <= first["failures"]
    path = tmp_path / "out.jsonl"
    run_grid([noisy], path, SMALL, decoder=BPOSD)
    assert load_records(path)[0]["failures"] == first["failures"]


def test_code_revision_ignores_documentation(monkeypatch):
    """source_tree is the tree hash of src/qec_star, so docs-only commits leave it unchanged."""
    from qec_star.hardware import experiments
    calls = []
    monkeypatch.setattr(experiments, "_git", lambda *a: calls.append(a) or "src/qec_star/hardware/"
                        if a[1:] == ("--show-prefix",) else (calls.append(a) or ""))
    revision = code_revision()
    assert ("rev-parse", "HEAD:src/qec_star") in calls
    assert revision["dirty"] is False


# ---------- decoder guards and the acceptance check ----------

def test_merged_logical_effects_are_detected_and_refused():
    """Two mechanisms with the same detector but different observables must not be merged."""
    clash = stim.Circuit("R 0 1\nX_ERROR(0.01) 0\nX_ERROR(0.1) 1\nM 0 1\n"
                         "DETECTOR rec[-2] rec[-1]\nOBSERVABLE_INCLUDE(0) rec[-1]")
    assert dem_logical_collisions(clash.detector_error_model()) == 1
    for decoder in DECODERS.values():
        with pytest.raises(ValueError, match="different observables"):
            predictor(clash, decoder)


@pytest.mark.parametrize("arch,code,rounds", [("bicycle", (3, 7), 3), ("surface_reference", (3,), 3)])
def test_production_circuits_have_no_merged_logical_effects(arch, code, rounds):
    for basis in "XZ":
        circuit = Cell("T", arch, code, basis, rounds, NoiseProfile.paper()).noisy_circuit()
        assert dem_logical_collisions(circuit.detector_error_model(decompose_errors=False)) == 0


def test_unknown_decoder():
    circuit = Cell("T", "surface_reference", (3,), "Z", 1, NoiseProfile.paper()).noisy_circuit()
    with pytest.raises(ValueError, match="unknown decoder"):
        predictor(circuit, {"name": "magic"})


def test_low_weight_fault_check_on_a_repetition_code():
    """The acceptance check itself, on a circuit every decoder handles."""
    noisy = decorate_stim_memory(stim.Circuit.generated("repetition_code:memory", distance=5, rounds=3),
                                 NoiseProfile.paper())
    for decoder in DECODERS.values():
        assert low_weight_fault_failures(noisy, weight=1, samples=100, decoder=decoder) == 0
    assert (low_weight_fault_failures(noisy, weight=3, samples=50, seed=3, decoder=BPOSD)
            == low_weight_fault_failures(noisy, weight=3, samples=50, seed=3, decoder=BPOSD))


def test_tesseract_passes_the_acceptance_check_on_the_bicycle_circuit():
    """Fault distance 5 means every pair of faults is correctable; Tesseract does so.

    (BP+OSD-0 does not: see docs/udaya/VALIDATION.md. That is a property of
    a third-party decoder, so it is recorded there rather than asserted.)
    """
    circuit = Cell("T", "bicycle", (3, 7), "Z", 3, NoiseProfile.paper()).noisy_circuit()
    assert low_weight_fault_failures(circuit, weight=1, samples=40) == 0
    assert low_weight_fault_failures(circuit, weight=2, samples=40) == 0


def test_validation_grid_is_well_formed():
    cells = validation_cells()
    assert len(cells) == len(set(cells)) == 12
    assert all(c.rounds == 3 * (6 if c.architecture == "bicycle" else c.code[0]) for c in cells)
    assert {(c.architecture, c.basis) for c in cells if c.experiment == "E1"} == {
        ("bicycle", "X"), ("bicycle", "Z"), ("surface_reference", "X"), ("surface_reference", "Z")}
    assert all(validation_shots(c) >= 2_400 for c in cells)
