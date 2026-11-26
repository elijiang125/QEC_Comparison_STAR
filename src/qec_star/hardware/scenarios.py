"""Versioned registry of hardware/noise scenarios with explicit provenance.

Each scenario fixes a NoiseProfile and a CycleTiming per architecture and
says where every number comes from. Evidence classes:
  measured  - reported from an experiment (cite it);
  assumed   - assumed by the paper being reproduced;
  derived   - computed from other entries by a stated formula;
  synthetic - chosen by us to probe sensitivity, with no claim of realism.
Units: probabilities are per operation (dimensionless); times are in ms.
"""
from dataclasses import asdict, dataclass, replace
from types import MappingProxyType

from .models import (BICYCLE_ENTANGLING_LAYERS, SURFACE_ENTANGLING_LAYERS, CycleTiming, NoiseProfile,
                     dephasing_probability, pauli_error_from_average_infidelity)

REGISTRY_VERSION = "1.0"
PAPER = "Ismail et al., arXiv:2606.25011"
EVIDENCE = ("measured", "assumed", "derived", "synthetic")
ARCHITECTURES = ("surface", "bicycle")


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    kind: str                       # "reference" or "exploratory"
    source: str
    source_version: str
    noise: NoiseProfile
    timing: MappingProxyType        # architecture -> CycleTiming
    evidence: MappingProxyType      # parameter -> evidence class
    conditionality: str
    limitations: str

    def __post_init__(self):
        if self.kind not in ("reference", "exploratory"):
            raise ValueError("kind must be 'reference' or 'exploratory'")
        if set(self.timing) != set(ARCHITECTURES):
            raise ValueError(f"timing must cover exactly {ARCHITECTURES}")
        expected = set(NoiseProfile.CHANNELS) | {"cycle_time"}
        if set(self.evidence) != expected or not set(self.evidence.values()) <= set(EVIDENCE):
            raise ValueError(f"evidence must label exactly {sorted(expected)} with one of {EVIDENCE}")

    def cycle_ms(self, architecture: str) -> float:
        return self.timing[architecture].cycle_ms

    @property
    def cycle_ratio(self) -> float:
        """Bicycle / surface syndrome-cycle duration."""
        return self.cycle_ms("bicycle") / self.cycle_ms("surface")

    def to_dict(self) -> dict:
        """JSON-ready record, stored with every experiment result."""
        return {"registry_version": REGISTRY_VERSION, "id": self.id, "description": self.description,
                "kind": self.kind, "source": self.source, "source_version": self.source_version,
                "noise": asdict(self.noise),
                "timing": {a: {**asdict(t), "cycle_ms": t.cycle_ms} for a, t in self.timing.items()},
                "evidence": dict(self.evidence), "conditionality": self.conditionality,
                "limitations": self.limitations}


_PAPER_TIMING = {"surface": CycleTiming.paper_lumped(SURFACE_ENTANGLING_LAYERS),
                 "bicycle": CycleTiming.paper_lumped(BICYCLE_ENTANGLING_LAYERS)}
_PAPER_LIMITS = ("Uniform depolarizing model; no atom loss, leakage, transport error, "
                 "crosstalk or noise bias. Cycle times are assumed totals; the paper "
                 "gives no gate, movement or readout durations.")


def _scenario(id, description, kind, noise, *, timing=None, evidence=None,
              source=PAPER, source_version="v1 (2026-06-23), Sec. III, III.2, Table 4",
              conditionality="Loss-free (paper's f = 0 case).", limitations=_PAPER_LIMITS):
    base = "assumed" if kind == "reference" else "synthetic"
    labels = {**{c: "assumed" for c in NoiseProfile.CHANNELS}, "cycle_time": "assumed",
              "cycle_idle": base, **(evidence or {})}
    return Scenario(id, description, kind, source, source_version, noise,
                    MappingProxyType(dict(timing or _PAPER_TIMING)), MappingProxyType(labels),
                    conditionality, limitations)


def _build():
    paper = NoiseProfile.paper()
    out = [_scenario("paper/p1e-3", "Paper baseline: uniform p = 1e-3, cycles 1 ms / 2 ms.",
                     "reference", paper)]
    for p in (5e-4, 2e-3, 3e-3, 5e-3):
        out.append(_scenario(f"uniform/p{p:g}", f"Paper's model at uniform p = {p:g}.", "exploratory",
                             NoiseProfile.paper(p), evidence={c: "synthetic" for c in NoiseProfile.CHANNELS[:5]}))
    for channel in ("two_qubit", "measurement", "idle"):
        for mult in (0.5, 2.0, 4.0):
            noise = replace(paper, **{channel: mult * getattr(paper, channel)},
                            label=f"paper baseline with {channel} x{mult:g}")
            out.append(_scenario(f"asym/{channel}_x{mult:g}",
                                 f"Only the {channel} probability is scaled by {mult:g}; rest at 1e-3.",
                                 "exploratory", noise, evidence={channel: "synthetic"}))
    for ratio in (1.0, 1.5, 3.0, 4.0):
        timing = {**_PAPER_TIMING, "bicycle": CycleTiming(
            BICYCLE_ENTANGLING_LAYERS, 0.0, ratio * 1000 / BICYCLE_ENTANGLING_LAYERS, 0.0)}
        out.append(_scenario(f"timing/ratio_{ratio:g}",
                             f"Bicycle cycle = {ratio:g} x the 1 ms surface cycle; paper noise.",
                             "exploratory", paper, timing=timing, evidence={"cycle_time": "synthetic"}))
    out += cycle_idle_scenario(
        1500, source="Bluvstein et al., Nature 604, 451 (2022)",
        source_version="Methods: T2 = 1.5 s, Rb-87, XY16 with 128 pi pulses").values()
    out += cycle_idle_scenario(150, source="synthetic (10x shorter than the measured 1.5 s)",
                               source_version="n/a", t2_evidence="synthetic").values()
    out.append(_literature_anchored())
    return out


def _literature_anchored():
    """Non-uniform profile built from published Rb-87 numbers by stated formulas.

    The inputs come from different experiments and devices, so this is an
    illustration of a non-uniform error budget, NOT a calibration of any
    machine. Loss is counted as a Pauli error, which no decoder would do in
    practice (it could be heralded) and which the Science value includes.
    """
    noise = NoiseProfile(
        prep=1e-3,                                                   # no clean source: paper's value
        one_qubit=round(pauli_error_from_average_infidelity(1 - 0.9997, 1), 9),     # 4.5e-4
        two_qubit=round(pauli_error_from_average_infidelity(1 - 0.99854, 2), 9),    # 1.825e-3
        measurement=2e-3,                                            # 99.8% mid-circuit readout
        idle=1e-3,                                                   # no clean source: paper's value
        label="literature-anchored Rb-87 illustration (mixed sources)")
    return _scenario(
        "lit/rb87_mixed", "Non-uniform Pauli profile derived from published Rb-87 fidelities.",
        "exploratory", noise,
        source=("two_qubit: Evered et al., Science 394, 197 (2026), raw CZ fidelity 99.854(4)% "
                "(arXiv:2604.25987v1); one_qubit: Evered et al., Nature 622, 268 (2023), global "
                "Raman 99.97%; measurement: Bluvstein et al., Nature 626, 58 (2024), mid-circuit "
                "readout ~99.8%; prep, idle and cycle times: " + PAPER),
        source_version="see docs/udaya/ASSUMPTIONS.md, table 'Literature values'",
        evidence={"one_qubit": "derived", "two_qubit": "derived", "measurement": "measured"},
        conditionality="Raw (not loss-post-selected) CZ fidelity; loss treated as a Pauli error.",
        limitations=("Mixed devices and benchmarks; depolarizing conversion p = (d+1)/d (1-F) "
                     "assumed; real errors are Z-biased with ~60% loss. Not a device calibration."))


def cycle_idle_scenario(t2_ms: float, *, source: str, source_version: str,
                        t2_evidence: str = "measured"):
    """Paper noise plus per-round idle dephasing over each architecture's cycle.

    Returns {architecture: Scenario}: the two codes get different cycle_idle
    because their cycles differ in length. The Z-dephasing probability
    (1 - exp(-t_cycle/T2))/2 is applied as a depolarizing channel of the same
    total probability, which is an assumption, not a measured channel.
    """
    out = {}
    for arch in ARCHITECTURES:
        p = dephasing_probability(_PAPER_TIMING[arch].cycle_us, t2_ms * 1000)
        noise = replace(NoiseProfile.paper(), cycle_idle=p,
                        label=f"paper baseline + cycle idle, T2 = {t2_ms:g} ms ({arch})")
        out[arch] = _scenario(
            f"idle/t2_{t2_ms:g}ms/{arch}",
            f"Paper noise plus idle dephasing over one {arch} cycle with T2 = {t2_ms:g} ms.",
            "exploratory", noise, source=f"{PAPER}; T2 from {source}", source_version=source_version,
            evidence={"cycle_idle": "derived" if t2_evidence == "measured" else "synthetic"},
            limitations=_PAPER_LIMITS + " Exponential pure dephasing mapped to depolarizing noise.")
    return out


SCENARIOS = MappingProxyType({s.id: s for s in _build()})
PAPER_REFERENCE = SCENARIOS["paper/p1e-3"]


def get(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError:
        raise KeyError(f"unknown scenario {scenario_id!r}; known: {sorted(SCENARIOS)}") from None
