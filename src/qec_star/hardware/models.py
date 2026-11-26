"""Noise and timing parameters: the paper baseline plus labeled extensions.

Provenance of every number here is recorded in docs/udaya/ASSUMPTIONS.md.
Reference: Ismail et al., arXiv:2606.25011v1 (cited below as "the paper").
"""
from dataclasses import dataclass
from math import exp, isfinite

# Paper Sec. III.2 and Table 4: assumed syndrome-cycle durations (not measured).
SURFACE_CYCLE_MS = 1.0
BICYCLE_CYCLE_MS = 2.0
# Entangling (CNOT) layers per syndrome round: weight-4 and weight-8 checks.
SURFACE_ENTANGLING_LAYERS = 4
BICYCLE_ENTANGLING_LAYERS = 8
# Derived, not stated in the paper: its three cycle times (1.0, 1.5, 2.0 ms for
# weight 4, 6, 8) all equal 0.25 ms x stabilizer weight, with no fixed term.
PAPER_LUMPED_LAYER_US = 250.0


def probability(value: float, name: str) -> None:
    if isinstance(value, bool) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a finite probability in [0, 1]")


def nonnegative(value: float, name: str) -> None:
    if isinstance(value, bool) or not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")


def nonnegative_int(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True)
class NoiseProfile:
    """Per-operation error probabilities (not rates per second).

    prep, one_qubit, two_qubit, idle: total probability of a non-identity
    Pauli in a depolarizing channel (Stim DEPOLARIZE1/2 convention).
    measurement: probability that the reported outcome is flipped.
    idle: charged to allocated qubits left untouched by an entangling layer.

    cycle_idle is NOT part of the paper's model (must be 0 to reproduce it):
    a depolarizing probability charged, once per measurement moment, to every
    allocated qubit that is not measured or reset in that moment and is used
    by a later entangling layer. It stands in for data qubits waiting through
    mid-circuit readout (r-1 times in an r-round memory), and is the hook for
    duration-dependent idle error (see `dephasing_probability`).

    Atom loss, leakage, transport error and correlated errors are not modeled.
    """
    prep: float
    one_qubit: float
    two_qubit: float
    measurement: float
    idle: float
    label: str = "user-specified Pauli sensitivity scenario"
    cycle_idle: float = 0.0

    CHANNELS = ("prep", "one_qubit", "two_qubit", "measurement", "idle", "cycle_idle")

    def __post_init__(self):
        for field in self.CHANNELS:
            probability(getattr(self, field), field)
        if not self.label.strip():
            raise ValueError("label must not be empty")

    @classmethod
    def paper(cls, p: float = 0.001):
        """Uniform circuit-level depolarizing baseline, paper Sec. III; no loss."""
        return cls(p, p, p, p, p, "Ismail et al. v1 Sec. III (loss-free)")


def pauli_error_from_average_infidelity(infidelity: float, qubits: int) -> float:
    """Depolarizing Pauli-error probability matching an average gate infidelity.

    For a depolarizing channel on dimension d = 2**qubits with total
    non-identity Pauli probability p, the average gate fidelity is
    F = 1 - p*d/(d+1), so p = (d+1)/d * (1 - F): 1.5x for one qubit, 1.25x
    for two. This is exact only if the real error IS depolarizing; coherent
    errors, leakage and loss are not captured, and a fidelity conditioned on
    no atom loss must not be combined with a separate loss channel twice.
    """
    probability(infidelity, "infidelity")
    if qubits not in (1, 2):
        raise ValueError("qubits must be 1 or 2")
    d = 2 ** qubits
    p = (d + 1) / d * infidelity
    probability(p, "resulting Pauli probability")
    return p


def dephasing_probability(duration_us: float, t2_us: float) -> float:
    """Z-error probability after idling for duration_us with coherence time T2.

    Assumes pure dephasing with exponential coherence decay exp(-t/T2), which
    is a Z-flip channel with p_Z = (1 - exp(-t/T2)) / 2. Real decay under
    dynamical decoupling is often non-exponential; this is a modeling choice.
    """
    nonnegative(duration_us, "duration_us")
    nonnegative(t2_us, "t2_us")
    if t2_us == 0:
        raise ValueError("t2_us must be positive")
    return (1 - exp(-duration_us / t2_us)) / 2


@dataclass(frozen=True)
class CycleTiming:
    """Transparent wall-clock budget for one syndrome round (microseconds).

        cycle = entangling_layers * (entangling_layer_us + movement_layer_us)
              + single_qubit_layers * single_qubit_layer_us
              + measurement_us + reset_us + fixed_overhead_us

    Every duration is the wall-clock time of one parallel layer acting on the
    whole array, never a sum over atoms. movement_layer_us covers transport,
    settling and any other per-layer overhead between entangling pulses.
    This is an accounting model for sensitivity studies, not a scheduler.
    """
    entangling_layers: int
    entangling_layer_us: float
    movement_layer_us: float
    fixed_overhead_us: float
    single_qubit_layers: int = 0
    single_qubit_layer_us: float = 0.0
    measurement_us: float = 0.0
    reset_us: float = 0.0

    def __post_init__(self):
        if type(self.entangling_layers) is not int or self.entangling_layers < 1:
            raise ValueError("entangling_layers must be a positive integer")
        nonnegative_int(self.single_qubit_layers, "single_qubit_layers")
        for field in ("entangling_layer_us", "movement_layer_us", "fixed_overhead_us",
                      "single_qubit_layer_us", "measurement_us", "reset_us"):
            nonnegative(getattr(self, field), field)

    @classmethod
    def paper_lumped(cls, entangling_layers: int):
        """The paper's cycle time as layers x 0.25 ms, with no decomposition.

        The paper states only totals; the per-layer budget is a derived lump
        (gate + transport + amortized readout), not a measured duration.
        """
        return cls(entangling_layers, 0.0, PAPER_LUMPED_LAYER_US, 0.0)

    @property
    def per_layer_us(self) -> float:
        return self.entangling_layer_us + self.movement_layer_us

    @property
    def fixed_us(self) -> float:
        """Everything that does not scale with the number of entangling layers."""
        return (self.single_qubit_layers * self.single_qubit_layer_us
                + self.measurement_us + self.reset_us + self.fixed_overhead_us)

    @property
    def cycle_us(self) -> float:
        return self.entangling_layers * self.per_layer_us + self.fixed_us

    @property
    def cycle_ms(self) -> float:
        return self.cycle_us / 1000

    def breakdown_us(self) -> dict:
        """Where the cycle time goes; the values sum to cycle_us."""
        return {
            "entangling": self.entangling_layers * self.entangling_layer_us,
            "movement": self.entangling_layers * self.movement_layer_us,
            "single_qubit": self.single_qubit_layers * self.single_qubit_layer_us,
            "measurement": self.measurement_us,
            "reset": self.reset_us,
            "fixed_overhead": self.fixed_overhead_us,
        }
