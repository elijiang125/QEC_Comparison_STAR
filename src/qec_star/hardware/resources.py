"""Memory footprint bookkeeping and explicitly parameterized STAR costs.

Neither function estimates logical error rates. Compare only matched workloads
and error budgets; a memory footprint is not an end-to-end architecture result.
"""
from dataclasses import dataclass
from .models import nonnegative


def positive_int(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class BlockFootprint:
    data: int
    ancillas: int
    logical: int

    def __post_init__(self):
        positive_int(self.data, "data")
        positive_int(self.logical, "logical")
        if type(self.ancillas) is not int or self.ancillas < 0 or self.logical > self.data:
            raise ValueError("invalid ancilla or logical count")

    @property
    def physical(self):
        return self.data + self.ancillas

    @property
    def encoding_rate(self):
        return self.logical / self.data


def surface_block(d: int) -> BlockFootprint:
    """Odd-distance rotated planar patch, one logical and d²-1 ancillas."""
    positive_int(d, "distance")
    if d < 3 or d % 2 == 0:
        raise ValueError("use an odd rotated-surface-code distance >= 3")
    return BlockFootprint(d*d, d*d-1, 1)


def bicycle_block(l: int, m: int = 7) -> BlockFootprint:
    """Paper's m=7 family only, l>=2; other m require team validation.

    Two data arrays and two check-ancilla arrays, each l*m. This is the
    idealized code-block footprint (no spare atoms or transport zones).
    """
    positive_int(l, "l")
    if l < 2 or type(m) is not int or m != 7:
        raise ValueError("starter supports the paper's l>=2, m=7 family only")
    return BlockFootprint(2*l*m, 2*l*m, 2*l)


def memory_footprint(logical_count: int, block: BlockFootprint) -> int:
    """Whole-block rounding, no factories, no spares, one memory allocation."""
    positive_int(logical_count, "logical_count")
    return ((logical_count + block.logical - 1) // block.logical) * block.physical


@dataclass(frozen=True)
class StarResources:
    physical_qubits: int
    wall_seconds: float
    parallel_shots: int

    @property
    def seconds_per_shot(self):
        """Throughput-normalized time, not latency."""
        return self.wall_seconds / self.parallel_shots

    @property
    def qubit_seconds_per_shot(self):
        return self.physical_qubits * self.seconds_per_shot


def star_resources(*, q_data: int, q_magic: int, v_rz: float, v_cliff: float,
                   cycle_ms: float, parallel_shots: int = 1) -> StarResources:
    """Appendix D.5 Eqs. (32)-(33), caller supplies consistent volume units.

    q_data/q_magic are per algorithm instance, BEFORE the approximate factor
    two for syndrome ancillas in Eq. (32). Do not pass exact block footprints.
    v_rz/v_cliff use the same pre-ancilla qubit-cycle convention. The two-shot
    BB convention duplicates the per-instance footprint and divides wall
    time by two for throughput; wall-clock latency is unchanged.
    This does not compute TMR, RUS costs, or logical failure probabilities.
    """
    positive_int(q_data, "q_data")
    positive_int(q_magic, "q_magic")
    if type(parallel_shots) is not int or parallel_shots not in (1, 2):
        raise ValueError("parallel_shots must be 1 or 2")
    for field, value in (("v_rz", v_rz), ("v_cliff", v_cliff), ("cycle_ms", cycle_ms)):
        nonnegative(value, field)
    if cycle_ms == 0:
        raise ValueError("cycle_ms must be positive")
    return StarResources(2 * (q_data + q_magic) * parallel_shots,
                         (v_rz/q_magic + v_cliff/q_data) * cycle_ms/1000,
                         parallel_shots)
