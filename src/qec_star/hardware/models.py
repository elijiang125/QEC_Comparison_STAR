"""Paper baseline and explicit, uncalibrated hardware sensitivity parameters."""
from dataclasses import dataclass
from math import isfinite

# Ismail et al., arXiv:2606.25011v1, Sec. III.2, Table IV.
SURFACE_CYCLE_MS = 1.0
BICYCLE_CYCLE_MS = 2.0


def probability(value: float, name: str) -> None:
    if isinstance(value, bool) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a finite probability in [0, 1]")


def nonnegative(value: float, name: str) -> None:
    if isinstance(value, bool) or not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True)
class NoiseProfile:
    """Total Pauli-channel probabilities; measurement is a classical bit flip.

    idle is charged only on unused qubits during an entangling layer. It is
    NOT a rate per second. Motion/loss are deliberately not hidden in these
    parameters. A real device profile needs independently sourced estimates.
    """
    prep: float
    one_qubit: float
    two_qubit: float
    measurement: float
    idle: float
    label: str = "user-specified Pauli sensitivity scenario"

    def __post_init__(self):
        for field in ("prep", "one_qubit", "two_qubit", "measurement", "idle"):
            probability(getattr(self, field), field)
        if not self.label.strip():
            raise ValueError("label must not be empty")

    @classmethod
    def paper(cls, p: float = 0.001):
        """Circuit-level depolarizing baseline, Sec. III; no atom loss."""
        return cls(p, p, p, p, p, "Ismail et al. v1 Sec. III (loss-free)")


@dataclass(frozen=True)
class CycleTiming:
    """Illustrative serialized layer budget, not a calibrated scheduler.

    Durations are wall-clock microseconds for a full parallel layer, NOT
    per-atom sums. Fixed overhead is counted once per syndrome round.
    Parallel overlap must be encoded in the effective input durations.
    """
    entangling_layers: int
    entangling_layer_us: float
    movement_layer_us: float
    fixed_overhead_us: float

    def __post_init__(self):
        if type(self.entangling_layers) is not int or self.entangling_layers < 1:
            raise ValueError("entangling_layers must be a positive integer")
        for field in ("entangling_layer_us", "movement_layer_us", "fixed_overhead_us"):
            nonnegative(getattr(self, field), field)

    @property
    def cycle_ms(self) -> float:
        return (self.entangling_layers * (self.entangling_layer_us + self.movement_layer_us)
                + self.fixed_overhead_us) / 1000
