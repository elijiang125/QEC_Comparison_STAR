"""Hardware and noise layer for the STAR comparison.

Independent of code construction and decoding: it takes the QEC team's
noiseless circuits and adds noise, timing and resource accounting.
See docs/udaya/INTEGRATION.md for the interface.
"""
from .models import (BICYCLE_CYCLE_MS, SURFACE_CYCLE_MS, CycleTiming, NoiseProfile,
                     dephasing_probability, pauli_error_from_average_infidelity)
from .resources import (Allocation, BlockFootprint, allocate, bicycle_block, break_even_cycle_ratio,
                        memory_footprint, memory_spacetime_ratio, star_data_qubits, star_resources,
                        surface_block)
from .scenarios import PAPER_REFERENCE, SCENARIOS, Scenario

__all__ = ["NoiseProfile", "CycleTiming", "SURFACE_CYCLE_MS", "BICYCLE_CYCLE_MS",
           "dephasing_probability", "pauli_error_from_average_infidelity",
           "BlockFootprint", "Allocation", "allocate", "surface_block", "bicycle_block",
           "memory_footprint", "memory_spacetime_ratio", "break_even_cycle_ratio",
           "star_data_qubits", "star_resources", "Scenario", "SCENARIOS", "PAPER_REFERENCE"]
