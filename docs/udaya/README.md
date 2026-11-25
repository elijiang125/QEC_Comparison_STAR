# Udaya workstream — STAR hardware and noise modeling

**Status:** initial implementation and research plan, not a completed replication.
**Integration base:** `epa-branch` at `0dc22d9aabac2016ca9f0040136c2aacecb3ddb8` (observed Nov 25, 2026).
**Primary paper:** [Ismail et al., arXiv:2606.25011v1](https://arxiv.org/html/2606.25011v1).

## Scope and ownership

Own hardware assumptions, noise channels, cycle and footprint accounting, and hardware sensitivity analysis. The simulation/decoder teammate owns sampling, decoder selection and logical failure estimates; the QEC team owns parity-check matrices, logical operators, syndrome schedules and circuits; the Hamiltonian teammate owns problem compilation and algorithm-level volumes. Coordinate interfaces and share paper writing. This allocation is proposed pending team confirmation. The shared project Google Doc was permission-blocked during preparation; do not treat these notes as its replacement.

## Start here

From the repository root, with Python >=3.12 (existing project requirement):

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q tests/test_udaya_hardware.py tests/test_udaya_noise.py
python -m pytest -q
python -m qec_star.hardware --logical-count 64
```

The command-line report prints an idealized memory allocation and loss-free reference parameters. It is not Fig. 5 replication or a logical-error benchmark. Stim adapter tests require the existing Stim dependency. The starter was checked locally with Python 3.13: 16 pure-Python tests passed; the Stim test module was skipped (Stim unavailable). Upstream suites and actual hardware were not tested in that environment. Re-run all tests in a fully installed checkout before merging.

## Files

- `docs/udaya/ROADMAP.md`: research question, milestones and acceptance gates.
- `docs/udaya/RESEARCH.md`: literature, baseline parameters, limitations and experimental design.
- `src/qec_star/hardware/models.py`: immutable noise and timing parameters.
- `src/qec_star/hardware/noise.py`: strict Stim decorator for flat, noiseless memory circuits.
- `src/qec_star/hardware/resources.py`: idealized block and Appendix D.5 resource bookkeeping.
- `src/qec_star/hardware/__main__.py`: JSON memory-footprint example.
- `tests/test_udaya_hardware.py`, `tests/test_udaya_noise.py`: pure arithmetic and Stim-dependent tests.

## Integration contract

```python
from qec_star.circuits import memory_experiment
from qec_star.hardware.models import NoiseProfile
from qec_star.hardware.noise import decorate_stim_memory

clean = memory_experiment(3, 7, rounds=18, basis="Z")
noisy = decorate_stim_memory(clean, NoiseProfile.paper(),
                             active_qubits=range(clean.num_qubits))
# Simulator teammate consumes this circuit and its detector error model.
dem = noisy.detector_error_model(decompose_errors=False)
```

For surface memory, pass a *noiseless* flattened Stim circuit and an explicit set of actually allocated qubit IDs. `num_qubits` can include gaps in generated surface-code IDs. Do not add noise twice. No decoder is bundled. Do not use Stim for exact non-Clifford TMR state simulation. Unsupported instructions fail loudly. The initial decorator intentionally requires TICK-delimited, non-overlapping entangling moments and does not simulate transport, leakage or atom loss. Agree on any changes with circuit owners.

## Working rules

- Keep additions under this namespace and `docs/udaya/`; do not rewrite the QEC modules or teammates' tests.
- Keep the paper baseline unchanged. Add separately labeled sensitivity scenarios.
- Preserve raw counts, seeds, configuration, code commit and decoder/version; never fabricate logical errors or results.
- Keep physical data qubits, ancillas, factories, spare atoms and number of concurrent shots separate.
- Present null/negative findings and uncertainty; a simulated hardware scenario is not a device calibration.
- Open a scoped PR only after the team agrees on a merge target and all required tests are green.
