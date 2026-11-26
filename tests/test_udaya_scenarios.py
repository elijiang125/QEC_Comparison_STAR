"""Scenario registry: provenance is complete and the reference is immutable."""
import dataclasses
import json

import pytest

from qec_star.hardware import PAPER_REFERENCE, SCENARIOS, NoiseProfile
from qec_star.hardware.scenarios import EVIDENCE, cycle_idle_scenario, get


def test_paper_reference_values():
    s = PAPER_REFERENCE
    assert s.kind == "reference" and s.noise == NoiseProfile.paper(1e-3)
    assert (s.cycle_ms("surface"), s.cycle_ms("bicycle"), s.cycle_ratio) == (1.0, 2.0, 2.0)
    assert set(s.evidence.values()) == {"assumed"}


def test_reference_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        PAPER_REFERENCE.noise = NoiseProfile.paper(0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        PAPER_REFERENCE.noise.two_qubit = 0.5
    with pytest.raises(TypeError):
        PAPER_REFERENCE.timing["bicycle"] = None
    with pytest.raises(TypeError):
        SCENARIOS["paper/p1e-3"] = None


def test_every_scenario_has_complete_provenance():
    assert len({s.id for s in SCENARIOS.values()}) == len(SCENARIOS)
    for sid, s in SCENARIOS.items():
        assert sid == s.id and s.description and s.source and s.source_version and s.limitations
        assert set(s.evidence) == set(NoiseProfile.CHANNELS) | {"cycle_time"}
        assert set(s.evidence.values()) <= set(EVIDENCE)
        json.dumps(s.to_dict())                      # serializable for result records


def test_only_one_reference_and_exploratory_ones_say_what_changed():
    assert [s.id for s in SCENARIOS.values() if s.kind == "reference"] == ["paper/p1e-3"]
    for s in SCENARIOS.values():
        if s.kind == "exploratory":
            assert set(s.evidence.values()) - {"assumed"}, f"{s.id} changes nothing?"


def test_one_factor_scenarios_change_exactly_one_channel():
    base = dataclasses.asdict(NoiseProfile.paper())
    for channel in ("two_qubit", "measurement", "idle"):
        changed = dataclasses.asdict(get(f"asym/{channel}_x4").noise)
        diff = {k for k in base if k != "label" and base[k] != changed[k]}
        assert diff == {channel} and changed[channel] == pytest.approx(0.004)


def test_timing_scenarios_change_only_the_bicycle_cycle():
    for ratio in (1.0, 1.5, 3.0, 4.0):
        s = get(f"timing/ratio_{ratio:g}")
        assert s.cycle_ms("surface") == 1.0 and s.cycle_ratio == pytest.approx(ratio)
        assert s.noise == NoiseProfile.paper()


def test_cycle_idle_grows_with_cycle_length():
    pair = cycle_idle_scenario(1500, source="test", source_version="test")
    surface, bicycle = pair["surface"].noise.cycle_idle, pair["bicycle"].noise.cycle_idle
    assert surface == pytest.approx(1 / 3000, rel=1e-3)       # 1 ms / (2 * 1.5 s)
    assert bicycle == pytest.approx(2 * surface, rel=1e-3)


def test_literature_scenario_follows_the_stated_conversion():
    n = get("lit/rb87_mixed").noise
    assert n.two_qubit == pytest.approx(1.25 * (1 - 0.99854))
    assert n.one_qubit == pytest.approx(1.5 * (1 - 0.9997))


def test_unknown_scenario():
    with pytest.raises(KeyError, match="unknown scenario"):
        get("nope")
