"""Experiment runner: statistics helpers, determinism and record contents."""
import pytest

from qec_star.hardware.experiments import (Cell, StopRule, load_records, low_weight_fault_failures,
                                           per_round_rate, pilot_cells, run_cell, run_grid,
                                           wilson_interval)
from qec_star.hardware.models import NoiseProfile

SMALL = StopRule(max_shots=400, max_failures=10**9, chunk_shots=100, workers=2, seed=5)


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
    record = run_cell(Cell("T", "surface_reference", (3,), "Z", 3, NoiseProfile.paper(0)), SMALL)
    assert (record["shots"], record["failures"]) == (400, 0)
    assert record["wilson95"][0] == 0 and record["wilson95"][1] < 0.01
    for key in ("circuit_sha256", "decoder", "stop_rule", "chunks", "runtime_seconds",
                "source_commit", "versions", "noise", "per_observable_failures", "noise_locations"):
        assert key in record
    assert sum(c["shots"] for c in record["chunks"]) == record["shots"]
    assert len({c["seed"] for c in record["chunks"]}) == len(record["chunks"])


def test_runs_are_reproducible_and_seeds_differ_between_circuits(tmp_path):
    noisy = Cell("T", "surface_reference", (3,), "Z", 3, NoiseProfile.paper(0.01))
    first, second = run_cell(noisy, SMALL), run_cell(noisy, SMALL)
    assert first["chunks"] == second["chunks"] and first["failures"] == second["failures"] > 0
    other = run_cell(Cell("T", "surface_reference", (3,), "X", 3, NoiseProfile.paper(0.01)), SMALL)
    assert {c["seed"] for c in other["chunks"]}.isdisjoint(c["seed"] for c in first["chunks"])
    # Failures across chunks add up, and no observable fails more often than the shot does.
    assert sum(c["failures"] for c in first["chunks"]) == first["failures"]
    assert max(first["per_observable_failures"]) <= first["failures"]
    path = tmp_path / "out.jsonl"
    run_grid([noisy], path, SMALL)
    assert load_records(path)[0]["failures"] == first["failures"]


def test_stop_rule_stops_on_failures():
    rule = StopRule(max_shots=100_000, max_failures=5, chunk_shots=100, workers=2, seed=5)
    record = run_cell(Cell("T", "surface_reference", (3,), "Z", 3, NoiseProfile.paper(0.02)), rule)
    assert record["failures"] >= 5 and record["shots"] < 100_000


def test_low_weight_fault_check_on_a_repetition_code():
    """The acceptance check itself: BP+OSD handles single faults on a repetition code.

    (On the surface and bicycle circuits BP+OSD does NOT pass this check; see
    docs/udaya/VALIDATION.md. That is a statement about the decoder, so it is
    recorded there rather than asserted here.)
    """
    import stim
    from qec_star.hardware.noise import decorate_stim_memory
    clean = stim.Circuit.generated("repetition_code:memory", distance=5, rounds=3)
    noisy = decorate_stim_memory(clean, NoiseProfile.paper())
    assert low_weight_fault_failures(noisy, weight=1, samples=200) == 0
    assert (low_weight_fault_failures(noisy, weight=3, samples=50, seed=3)
            == low_weight_fault_failures(noisy, weight=3, samples=50, seed=3))


def test_pilot_grid_is_well_formed():
    cells = pilot_cells()
    assert len(cells) == len(set(cells))
    assert {c.experiment for c in cells} == {"E1", "E2", "E3", "E4", "E5"}
    assert all(c.rounds == 3 * (6 if c.architecture == "bicycle" else c.code[0]) for c in cells)
    # The paper baseline is run in both bases on both architectures.
    assert {(c.architecture, c.basis) for c in cells if c.experiment == "E1"} == {
        ("bicycle", "X"), ("bicycle", "Z"), ("surface_reference", "X"), ("surface_reference", "Z")}
