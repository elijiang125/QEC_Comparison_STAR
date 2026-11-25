"""These require Stim (already a dependency in the upstream pyproject)."""
import pytest
stim = pytest.importorskip("stim")
from qec_star.hardware.models import NoiseProfile
from qec_star.hardware.noise import decorate_stim_memory


def test_channels_and_idle():
    clean = stim.Circuit("R 0 1 2\nTICK\nCX 0 1\nTICK\nM 0 1 2\nDETECTOR rec[-1]")
    noisy = decorate_stim_memory(clean, NoiseProfile(.01,.02,.03,.04,.05), active_qubits=range(3))
    expected = stim.Circuit("R 0 1 2\nDEPOLARIZE1(0.01) 0 1 2\nTICK\nCX 0 1\nDEPOLARIZE2(0.03) 0 1\nDEPOLARIZE1(0.05) 2\nTICK\nM(0.04) 0 1 2\nDETECTOR rec[-1]")
    assert noisy == expected
    assert noisy.num_measurements == clean.num_measurements
    assert noisy.num_detectors == clean.num_detectors


def test_zero_noise_and_measure_reset():
    c = stim.Circuit("RX 0\nTICK\nH 0\nTICK\nMRX 0")
    z = decorate_stim_memory(c, NoiseProfile.paper(0), active_qubits=[0])
    assert z == c
    n = decorate_stim_memory(c, NoiseProfile.paper(), active_qubits=[0])
    assert "MRX(0.001) 0" in str(n)
    assert n.num_measurements == c.num_measurements


def test_reject_existing_noise():
    c = stim.Circuit("R 0\nX_ERROR(0.1) 0")
    with pytest.raises(ValueError, match="unsupported or already noisy"):
        decorate_stim_memory(c, NoiseProfile.paper(), active_qubits=[0])


@pytest.mark.parametrize("basis", ["X", "Z"])
def test_upstream_memory_smoke(basis):
    from qec_star.circuits import memory_experiment
    c = memory_experiment(3, 7, 18, basis=basis)
    z = decorate_stim_memory(c, NoiseProfile.paper(0), active_qubits=range(c.num_qubits))
    assert z == c
    n = decorate_stim_memory(c, NoiseProfile.paper(), active_qubits=range(c.num_qubits))
    assert n.num_detectors == c.num_detectors
    assert n.num_observables == c.num_observables
    n.detector_error_model(decompose_errors=False)


def test_flattened_surface_smoke():
    c = stim.Circuit.generated("surface_code:rotated_memory_z", distance=3, rounds=9).flattened()
    # Some generated IDs have holes: use actual allocated qubit coordinates.
    qs = sorted(c.get_final_qubit_coordinates())
    n = decorate_stim_memory(c, NoiseProfile.paper(), active_qubits=qs)
    assert n.num_measurements == c.num_measurements
    n.detector_error_model(decompose_errors=False)
