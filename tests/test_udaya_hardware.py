"""Noise parameters, timing and resource accounting, checked against hand calculations."""
import math

import pytest

from qec_star.hardware import (CycleTiming, NoiseProfile, allocate, bicycle_block,
                               break_even_cycle_ratio, dephasing_probability, memory_footprint,
                               memory_spacetime_ratio, pauli_error_from_average_infidelity,
                               star_data_qubits, star_resources, surface_block)
from qec_star.hardware.__main__ import main


# ---------- noise parameters ----------

def test_paper_noise_and_zero():
    p = NoiseProfile.paper()
    assert (p.prep, p.one_qubit, p.two_qubit, p.measurement, p.idle) == (0.001,)*5
    assert p.cycle_idle == 0                         # not part of the paper's model
    assert NoiseProfile.paper(0).idle == 0


@pytest.mark.parametrize("p", [-0.1, 1.1, math.nan, math.inf, True])
def test_invalid_probability(p):
    with pytest.raises(ValueError):
        NoiseProfile.paper(p)
    with pytest.raises(ValueError):
        NoiseProfile(0, 0, 0, 0, 0, cycle_idle=p)


def test_empty_label_rejected():
    with pytest.raises(ValueError):
        NoiseProfile(0, 0, 0, 0, 0, " ")


def test_fidelity_to_pauli_probability():
    # d=2: p = 3/2 r.  d=4: p = 5/4 r.  CZ at 99.5% -> 6.25e-3.
    assert pauli_error_from_average_infidelity(0.001, 1) == pytest.approx(0.0015)
    assert pauli_error_from_average_infidelity(0.005, 2) == pytest.approx(0.00625)
    # Fully depolarized: Pauli probability (d^2-1)/d^2 <-> infidelity (d-1)/d.
    assert pauli_error_from_average_infidelity(0.5, 1) == pytest.approx(0.75)
    assert pauli_error_from_average_infidelity(0.75, 2) == pytest.approx(0.9375)
    for bad in [(0.9, 2), (0.1, 3), (-0.1, 1)]:
        with pytest.raises(ValueError):
            pauli_error_from_average_infidelity(*bad)


def test_dephasing_probability():
    assert dephasing_probability(0, 1000) == 0
    assert dephasing_probability(1000, 1_000_000) == pytest.approx(0.0005, rel=1e-3)   # ~ t / 2T2
    assert dephasing_probability(1e12, 1) == pytest.approx(0.5)                        # saturates
    with pytest.raises(ValueError):
        dephasing_probability(1, 0)


# ---------- timing ----------

def test_paper_cycle_times_are_weight_times_quarter_ms():
    assert CycleTiming.paper_lumped(4).cycle_ms == 1.0
    assert CycleTiming.paper_lumped(6).cycle_ms == 1.5
    assert CycleTiming.paper_lumped(8).cycle_ms == 2.0


def test_cycle_formula_by_hand():
    t = CycleTiming(8, 0.27, 200, 10, single_qubit_layers=2, single_qubit_layer_us=1,
                    measurement_us=500, reset_us=100)
    # 8*(0.27+200) + 2*1 + 500 + 100 + 10 = 2214.16 us
    assert t.cycle_us == pytest.approx(2214.16)
    assert t.cycle_ms == pytest.approx(2.21416)
    assert t.fixed_us == pytest.approx(612)
    assert sum(t.breakdown_us().values()) == pytest.approx(t.cycle_us)
    assert t.breakdown_us()["movement"] == 1600


def test_parallel_layer_is_counted_once_not_per_atom():
    # The duration has no dependence on how many atoms a layer moves.
    assert CycleTiming(4, 1, 100, 0).cycle_us == 404


def test_fixed_overhead_pulls_cycle_ratio_below_two():
    def ratio(fixed):
        return CycleTiming(8, 0, 250, fixed).cycle_us / CycleTiming(4, 0, 250, fixed).cycle_us
    assert ratio(0) == 2
    assert ratio(1000) == pytest.approx(1.5)
    assert 1 < ratio(1e6) < 1.001


@pytest.mark.parametrize("kwargs", [
    dict(entangling_layers=0), dict(entangling_layers=4.0), dict(entangling_layer_us=-1),
    dict(movement_layer_us=math.inf), dict(fixed_overhead_us=math.nan),
    dict(single_qubit_layers=-1), dict(measurement_us=-5), dict(reset_us=True),
])
def test_invalid_timing(kwargs):
    base = dict(entangling_layers=4, entangling_layer_us=1, movement_layer_us=1, fixed_overhead_us=1)
    with pytest.raises(ValueError):
        CycleTiming(**{**base, **kwargs})


# ---------- exact memory accounting ----------

def test_block_footprints():
    s = surface_block(9)
    assert (s.data, s.ancillas, s.physical, s.logical) == (81, 80, 161, 1)
    assert s.encoding_rate == pytest.approx(1/81)
    b = bicycle_block(3)
    assert (b.data, b.ancillas, b.physical, b.logical) == (42, 42, 84, 6)
    assert b.encoding_rate == pytest.approx(1/7)
    assert b.physical_per_logical == 14              # paper Table 4
    assert s.physical_per_logical == 161             # paper Table 4: 2 d^2 - 1


@pytest.mark.parametrize("l,m,n,k", [(2, 7, 28, 4), (4, 7, 56, 8), (3, 11, 66, 6), (3, 13, 78, 6)])
def test_bicycle_family_matches_paper(l, m, n, k):
    b = bicycle_block(l, m)
    assert (b.data, b.logical) == (n, k)


@pytest.mark.parametrize("count,blocks,physical,unused", [
    (1, 1, 84, 5), (6, 1, 84, 0), (7, 2, 168, 5), (64, 11, 924, 2),
])
def test_whole_block_rounding(count, blocks, physical, unused):
    a = allocate(count, bicycle_block(3))
    assert (a.blocks, a.physical, a.unused_logical) == (blocks, physical, unused)
    assert a.capacity == count + unused


def test_memory_comparison_for_64_logical_qubits():
    s, b = surface_block(9), bicycle_block(4)
    assert memory_footprint(64, s) == 64 * 161 == 10304
    assert memory_footprint(64, b) == 8 * 112 == 896
    assert break_even_cycle_ratio(64, s, b) == 11.5
    # At the paper's 1 ms and 2 ms cycles the qubit-second ratio is half the qubit ratio.
    assert memory_spacetime_ratio(64, s, b, 1.0, 2.0) == 5.75
    assert memory_spacetime_ratio(64, s, b, 1.0, 11.5) == pytest.approx(1.0)


def test_rounding_can_shift_the_break_even():
    s, b = surface_block(9), bicycle_block(4)
    # 9 logical qubits need 2 bicycle blocks (224 atoms) vs 9 patches (1449).
    assert break_even_cycle_ratio(9, s, b) == pytest.approx(1449 / 224)


@pytest.mark.parametrize("bad", [0, -1, 1.5, True])
def test_invalid_logical_count(bad):
    with pytest.raises(ValueError):
        allocate(bad, surface_block(3))


@pytest.mark.parametrize("d", [1, 4, 0, 3.0])
def test_invalid_surface_distance(d):
    with pytest.raises(ValueError):
        surface_block(d)


def test_invalid_bicycle_and_cycle_inputs():
    with pytest.raises(ValueError):
        bicycle_block(0)
    with pytest.raises(ValueError):
        memory_spacetime_ratio(1, surface_block(3), bicycle_block(2), 0, 1)


# ---------- paper Appendix D.5 ----------

def test_star_data_qubits():
    assert star_data_qubits(64, bicycle_block(4)) == pytest.approx(448)   # 64 * 7
    assert star_data_qubits(64, surface_block(9)) == pytest.approx(5184)  # 64 * 81


def test_star_equations_by_hand():
    # Q = 2*(100+50) = 300.  t = (500/50 + 200/100) * 2 ms = 24 ms.
    one = star_resources(q_data=100, q_magic=50, v_rz=500, v_cliff=200, cycle_ms=2)
    assert one.physical_qubits == 300
    assert one.wall_seconds == pytest.approx(0.024)
    assert one.qubit_seconds_per_shot == pytest.approx(7.2)


def test_two_parallel_shots_change_throughput_not_latency():
    args = dict(q_data=100, q_magic=50, v_rz=500, v_cliff=200, cycle_ms=2)
    one, two = star_resources(**args), star_resources(**args, parallel_shots=2)
    assert two.physical_qubits == 2 * one.physical_qubits
    assert two.wall_seconds == one.wall_seconds
    assert two.seconds_per_shot == one.seconds_per_shot / 2
    assert two.qubit_seconds_per_shot == one.qubit_seconds_per_shot


def test_fractional_inputs_round_up_per_instance_then_double():
    # 2*(1.1+1.1) = 4.4 atoms -> 5 per instance; two instances are exactly twice one.
    one = star_resources(q_data=1.1, q_magic=1.1, v_rz=1, v_cliff=1, cycle_ms=1)
    two = star_resources(q_data=1.1, q_magic=1.1, v_rz=1, v_cliff=1, cycle_ms=1, parallel_shots=2)
    assert (one.physical_qubits, two.physical_qubits) == (5, 10)


def test_star_runtime_is_linear_in_cycle_time():
    args = dict(q_data=448, q_magic=504, v_rz=1e6, v_cliff=1e6)
    assert (star_resources(**args, cycle_ms=4).wall_seconds
            == pytest.approx(2 * star_resources(**args, cycle_ms=2).wall_seconds))


@pytest.mark.parametrize("kwargs", [
    dict(q_magic=0), dict(q_data=0), dict(cycle_ms=0), dict(v_rz=-1), dict(parallel_shots=3),
    dict(parallel_shots=True), dict(v_cliff=math.inf),
])
def test_star_validation(kwargs):
    base = dict(q_data=1, q_magic=1, v_rz=0, v_cliff=0, cycle_ms=1)
    with pytest.raises(ValueError):
        star_resources(**{**base, **kwargs})


# ---------- command line ----------

def test_cli_memory_report(capsys):
    main(["--logical-count", "64"])
    out = __import__("json").loads(capsys.readouterr().out)
    rows = {r["architecture"]: r for r in out["architectures"]}
    assert rows["surface"]["physical_memory_qubits"] == 10304
    assert rows["bicycle"]["physical_memory_qubits"] == 896
    assert out["surface_over_bicycle_qubits"] == 11.5
