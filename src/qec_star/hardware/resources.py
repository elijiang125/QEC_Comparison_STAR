"""Exact memory-block accounting and the paper's approximate STAR formulas.

Two different kinds of number live here and must not be mixed:
  * exact counts of atoms in whole code blocks (BlockFootprint, allocate);
  * the paper's Appendix D.5 estimate, Eqs. (32)-(33) (star_resources),
    which approximates ancillas by a factor 2 and ignores block rounding.
Nothing here estimates a logical error rate. A resource ratio is a fair
architecture comparison only at matched workload and reliability target.
"""
from dataclasses import dataclass

from ..codes import bicycle_chain
from ..gf2 import css_k
from .models import nonnegative


def positive_int(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class BlockFootprint:
    """Atoms in one code block: data qubits plus one ancilla per check."""
    data: int
    ancillas: int
    logical: int

    def __post_init__(self):
        positive_int(self.data, "data")
        positive_int(self.logical, "logical")
        if type(self.ancillas) is not int or self.ancillas < 0 or self.logical > self.data:
            raise ValueError("invalid ancilla or logical count")

    @property
    def physical(self) -> int:
        return self.data + self.ancillas

    @property
    def encoding_rate(self) -> float:
        """k/n, counting data qubits only (the usual code rate)."""
        return self.logical / self.data

    @property
    def physical_per_logical(self) -> float:
        """Data plus ancillas per logical qubit, for a full block."""
        return self.physical / self.logical


def surface_block(d: int) -> BlockFootprint:
    """Rotated surface-code patch [[d^2, 1, d]]: d^2 data, d^2 - 1 ancillas."""
    positive_int(d, "distance")
    if d < 3 or d % 2 == 0:
        raise ValueError("use an odd rotated-surface-code distance >= 3")
    return BlockFootprint(d*d, d*d-1, 1)


def bicycle_block(l: int, m: int = 7) -> BlockFootprint:
    """Bicycle-chain block on an l x m torus: 2lm data, 2lm check ancillas.

    k is computed from the team's parity-check matrices rather than assumed
    (k = 2l for the paper's instances). The code distance is not computed
    here; the paper's values are d = 6, 8, 10 for m = 7, 11, 13 at l = 3.
    Spare atoms, reservoirs and transport lanes are not included.
    """
    positive_int(l, "l")
    positive_int(m, "m")
    k = css_k(*bicycle_chain(l, m))
    if k < 1:
        raise ValueError(f"bicycle chain with l={l}, m={m} encodes no logical qubits")
    return BlockFootprint(2*l*m, 2*l*m, k)


@dataclass(frozen=True)
class Allocation:
    """Whole blocks needed to hold a number of logical qubits."""
    logical_count: int
    block: BlockFootprint
    blocks: int

    @property
    def physical(self) -> int:
        return self.blocks * self.block.physical

    @property
    def capacity(self) -> int:
        return self.blocks * self.block.logical

    @property
    def unused_logical(self) -> int:
        """Encoded logical qubits the workload does not use (block rounding)."""
        return self.capacity - self.logical_count

    @property
    def physical_per_used_logical(self) -> float:
        return self.physical / self.logical_count


def allocate(logical_count: int, block: BlockFootprint) -> Allocation:
    """Memory only: no magic-state factories, spares or routing space."""
    positive_int(logical_count, "logical_count")
    return Allocation(logical_count, block, -(-logical_count // block.logical))


def memory_footprint(logical_count: int, block: BlockFootprint) -> int:
    """Physical qubits (data + ancillas) in the whole blocks that are needed."""
    return allocate(logical_count, block).physical


def memory_spacetime_ratio(logical_count: int, surface: BlockFootprint, bicycle: BlockFootprint,
                           surface_cycle_ms: float, bicycle_cycle_ms: float) -> float:
    """Surface / bicycle qubit-seconds per syndrome round, memory only.

    Above 1 the bicycle chain is cheaper. This compares one round of each
    code as built; it does NOT equalize logical error rates (the paper pairs
    d=9 surface with d=6 bicycle), so it is a footprint statement, not an
    end-to-end advantage.
    """
    for name, value in (("surface_cycle_ms", surface_cycle_ms), ("bicycle_cycle_ms", bicycle_cycle_ms)):
        nonnegative(value, name)
        if value == 0:
            raise ValueError(f"{name} must be positive")
    return (memory_footprint(logical_count, surface) * surface_cycle_ms) / (
        memory_footprint(logical_count, bicycle) * bicycle_cycle_ms)


def break_even_cycle_ratio(logical_count: int, surface: BlockFootprint, bicycle: BlockFootprint) -> float:
    """Bicycle/surface cycle-time ratio at which memory qubit-seconds are equal.

    Equal to the footprint ratio: a slower bicycle cycle erases the space
    saving only once it is this many times slower than the surface cycle.
    """
    return memory_footprint(logical_count, surface) / memory_footprint(logical_count, bicycle)


@dataclass(frozen=True)
class StarResources:
    physical_qubits: int
    wall_seconds: float
    parallel_shots: int

    @property
    def seconds_per_shot(self) -> float:
        """Throughput-normalized time (wall time / shots run side by side)."""
        return self.wall_seconds / self.parallel_shots

    @property
    def qubit_seconds_per_shot(self) -> float:
        return self.physical_qubits * self.seconds_per_shot


def star_data_qubits(logical_count: int, block: BlockFootprint) -> float:
    """Paper D.5: Q_data = n_logical * n/k (data qubits, no block rounding)."""
    positive_int(logical_count, "logical_count")
    return logical_count / block.encoding_rate


def star_resources(*, q_data: float, q_magic: float, v_rz: float, v_cliff: float,
                   cycle_ms: float, parallel_shots: int = 1) -> StarResources:
    """Paper Appendix D.5, Eqs. (32)-(33).

        Q_phys = 2 (Q_data + Q_magic)                              (32)
        t_run  = (V_RZ / Q_magic + V_Cliff / Q_data) * t_cycle     (33)

    q_data, q_magic: data-qubit counts for one algorithm instance, before
    the factor 2 that stands in for syndrome ancillas (Q_magic =
    n_factories * n_factory). v_rz, v_cliff: rotation and Clifford volumes in
    qubit-cycles, supplied by the algorithm owner. parallel_shots=2 is the
    paper's bicycle convention of running two instances side by side: twice
    the atoms, the same wall-clock latency, half the time per shot.
    TMR acceptance, repeat-until-success and logical error are not computed.
    """
    for field, value in (("q_data", q_data), ("q_magic", q_magic), ("cycle_ms", cycle_ms)):
        nonnegative(value, field)
        if value == 0:
            raise ValueError(f"{field} must be positive")
    if type(parallel_shots) is not int or parallel_shots not in (1, 2):
        raise ValueError("parallel_shots must be 1 or 2")
    nonnegative(v_rz, "v_rz")
    nonnegative(v_cliff, "v_cliff")
    return StarResources(round(2 * (q_data + q_magic) * parallel_shots),
                         (v_rz/q_magic + v_cliff/q_data) * cycle_ms/1000,
                         parallel_shots)
