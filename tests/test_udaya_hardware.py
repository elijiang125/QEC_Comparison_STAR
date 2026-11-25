import math
import pytest
from qec_star.hardware import (NoiseProfile, CycleTiming, surface_block, bicycle_block,
                               memory_footprint, star_resources)


def test_paper_noise_and_zero():
    p = NoiseProfile.paper()
    assert (p.prep, p.one_qubit, p.two_qubit, p.measurement, p.idle) == (0.001,)*5
    assert NoiseProfile.paper(0).idle == 0


@pytest.mark.parametrize("p", [-0.1, 1.1, math.nan, math.inf, True])
def test_invalid_p(p):
    with pytest.raises(ValueError):
        NoiseProfile.paper(p)


def test_cycle_units():
    assert CycleTiming(8, 20, 100, 1040).cycle_ms == 2.0
    assert CycleTiming(4, 20, 100, 520).cycle_ms == 1.0


@pytest.mark.parametrize("args", [(0, 1, 1, 1), (4, -1, 1, 1), (4, 1, math.inf, 1)])
def test_invalid_timing(args):
    with pytest.raises(ValueError):
        CycleTiming(*args)


def test_footprint_and_rounding():
    s = surface_block(9)
    b = bicycle_block(3)
    assert (s.data, s.ancillas, s.physical, s.logical) == (81, 80, 161, 1)
    assert (b.data, b.ancillas, b.physical, b.logical) == (42, 42, 84, 6)
    assert b.encoding_rate == pytest.approx(1/7)
    assert memory_footprint(7, b) == 168
    assert memory_footprint(64, bicycle_block(4)) == 896
    assert memory_footprint(64, s) == 10304


@pytest.mark.parametrize("args", [(1, 7), (4, 11)])
def test_unvalidated_bicycle_family(args):
    with pytest.raises(ValueError):
        bicycle_block(*args)


def test_surface_distance_validation():
    with pytest.raises(ValueError):
        surface_block(4)


def test_star_throughput_not_latency():
    args = dict(q_data=100, q_magic=50, v_rz=500, v_cliff=200, cycle_ms=2)
    one = star_resources(**args)
    two = star_resources(**args, parallel_shots=2)
    assert one.physical_qubits == 300
    assert one.wall_seconds == pytest.approx(0.024)
    assert two.physical_qubits == 600
    assert two.wall_seconds == one.wall_seconds
    assert two.seconds_per_shot == one.seconds_per_shot / 2
    assert two.qubit_seconds_per_shot == one.qubit_seconds_per_shot


def test_resource_validation():
    with pytest.raises(ValueError):
        star_resources(q_data=1, q_magic=0, v_rz=0, v_cliff=0, cycle_ms=1)
    with pytest.raises(ValueError):
        star_resources(q_data=1, q_magic=1, v_rz=0, v_cliff=0, cycle_ms=1, parallel_shots=3)
