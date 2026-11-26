# Technical handoff

What each teammate can use from the hardware workstream today, and what the hardware workstream
needs from them. Interfaces are specified in [INTEGRATION.md](INTEGRATION.md); evidence for the
statements below is in [VALIDATION.md](VALIDATION.md) and [RESULTS.md](RESULTS.md).

## For the QEC owner

**Your bicycle-chain circuit works with the noise layer as it is.** `memory_experiment(l, m, rounds,
basis)` needs no changes. Checked for (3,7) and (4,7), both bases: measurement records, detectors and
observables are preserved, and the noise-location counts match hand counts.

Things I found in your circuit that you may want to know:

- Every CNOT layer of Table 2 uses all four atom arrays, so no atom idles during an entangling layer.
  The paper's idle-noise channel therefore never fires on this circuit.
- A bounded search for undetectable logical errors found weight 6 and nothing lighter, consistent
  with the paper's fault distance of 5. No sign of a hook-error problem in the schedule.
- No error mechanism shares its detectors with another that has a different logical effect, so
  decoders that merge mechanisms are safe on it.

What I need:

1. **Transversal-gate and magic-state circuits** when they exist. The noise layer will accept them
   if they follow the rules in INTEGRATION.md; `CZ` and `SWAP` are already supported.
2. If atom moves become explicit in the circuit, tell me how they are marked, so transport time and
   transport error can be attached to them.

## For the surface-code and simulation owner

**Your surface-code baseline is integrated on `udaya`** (merged from `origin/harman` at `f377d22`,
your commits and files unchanged). It is now the surface architecture everywhere in the hardware
layer; Stim's generated circuit is kept only as a named reference.

What I verified independently, at d = 3, 5, 7 and 9 in both bases (your tests stop at 7):

- 2d² − 1 atoms, one observable, r (d² − 1) detectors, 4 CNOT layers per round.
- Noise-location counts match hand formulas for every channel (VALIDATION.md has the table).
- Under the full noise model (preparation, measurement and idle errors included, not only CNOT
  errors) the shortest undetectable graph-like error has weight d at all four distances. Note that
  `shortest_graphlike_error`, which your test and mine both use, ignores error mechanisms that
  flip more than two detectors, so on its own it is not a proof of the circuit distance. A bounded
  search that includes them (`search_for_undetectable_logical_errors`) also found weight d and
  nothing lighter at d = 3 and 5, and the independent reviewer reached the same conclusion.
- Because you prepare and measure X ancillas directly, the circuit has no one-qubit gates: 516 noise
  locations per round at d = 9, against 596 for Stim's circuit. The analytic results were redone.

Two observations from a small fixed-shot run (RESULTS.md B2), neither established:

- At d = 5, p = 1e-3, Z basis, your circuit failed 8 times in 200,000 shots where Stim's failed 8
  times in 40,000 (Fisher exact p = 0.002). The X basis shows no such gap. It is one cell and is not
  explained; worth reproducing with more shots.
- In the same cell your Z-basis memory failed 8 times and your X-basis memory 21 times (p = 0.02,
  not significant once the number of comparisons is allowed for).
- Tesseract took five to seven times longer per shot on your d = 9 circuit than on Stim's. The circuits
  number qubits and detectors differently and Tesseract searches in detector order, so the detector
  ordering (or a matching decoder, which suits the surface code) is worth a look before large runs.

**How to run the hardware scenarios in your pipeline.**

```python
from qec_star import surface
from qec_star.hardware import SCENARIOS
from qec_star.hardware.noise import decorate_stim_memory

noisy = decorate_stim_memory(surface.memory_experiment(d, 3 * d, basis), SCENARIOS[scenario_id].noise)
```

`decorate_stim_memory` replaces the test-only `with_cnot_noise` helper in your tests: it adds the
paper's full model (preparation, gates, measurement, idle) or any registry scenario. Store the
scenario id and `REGISTRY_VERSION` with each result.

Recommended configurations, in priority order. Use r = 3d rounds, both bases, and a shot count fixed
before sampling.

| Priority | Scenario ids | Purpose | Codes |
|---|---|---|---|
| 1 | `paper/p1e-3` | the paper baseline | bicycle (3,7) and (4,7); surface d = 5, 7, 9 |
| 2 | `uniform/p0.0005`, `uniform/p0.002`, `uniform/p0.003` | error scaling with p; also where failures are frequent enough to measure | same |
| 3 | `asym/two_qubit_x2`, `asym/two_qubit_x4` | the channel that separates the two codes most (1.80 vs 1.56 in fault budget) | same |
| 4 | `lit/rb87_mixed` | a non-uniform budget from published fidelities | same |
| 5 | `asym/measurement_x2`, `asym/measurement_x4`, `asym/idle_x2`, `asym/idle_x4` | the idle scenarios are identical to the baseline for the bicycle circuit, so run them for the surface code only | as noted |
| 6 | `idle/t2_1500ms/surface` and `idle/t2_1500ms/bicycle` | idle error that grows with cycle length; use the id that matches the architecture | same |

Shot counts to plan for, from what we measured with Tesseract at p = 1e-3 (aim for at least 100
failures per cell):

| Code | Failure per shot seen | Shots for ~100 failures |
|---|---|---|
| surface d = 3 | 1.9e-3 | 6 × 10⁴ |
| surface d = 5 | 4e-5 to 1.1e-4 | 1 to 3 × 10⁶ |
| surface d = 7, 9 | none in 40,000 | more than 10⁶; unknown |
| bicycle [[42,6,6]] | 1 in 12,000 (both bases together) | of order 10⁶ |

At p = 2e-3 the Z-basis rates are 4 times higher at d = 3 (7.5e-3) and 25 times higher at d = 5
(1.0e-3), and failures become visible at d = 7 (1.5e-4), so the elevated-noise scenarios are the
practical place to measure sensitivities.

Decoder notes:

1. Before trusting a decoder on the bicycle circuit, compare it with Tesseract using
   `low_weight_fault_failures(noisy_circuit, weight, samples, decoder=...)` for weights 1 and 2. It
   is a diagnostic, not a proof: a most-likely-error decoder can legitimately mis-correct a rare
   single fault. On the bicycle circuit BP+OSD-0 from `ldpc` mis-corrected 8 of 300 double faults and
   gave failure rates about 100 times higher than Tesseract; Tesseract mis-corrected none, and
   neither did BP+OSD with literature settings (10,000 iterations, OSD-CS order 10) on 100 double
   faults, at about 2 s per decode.
2. Check `dem_logical_collisions(dem) == 0` if your decoder merges error mechanisms by detector
   pattern. It is 0 for both team circuits.
3. I used Tesseract's default beam of 5. Its authors recommend a beam of 15 with beam climbing for
   bicycle codes, and it is an exact most-likely-error decoder only with an unbounded search. Record
   its low-confidence flag in production runs; my runner does not.
4. Cost on the 18-round [[42,6,6]] memory was 1.1 to 1.3 worker-seconds per shot at p = 1e-3 and 5.2
   at p = 2e-3 (recorded wall time × 12 workers on a 14-core laptop). A million shots per bicycle
   cell is a few hundred core-hours: a cluster job.

What I need back:

1. **Failure counts and shot counts per cell** for the configurations above, in both bases, with the
   decoder settings. If you keep the record fields in INTEGRATION.md, the figures regenerate.
2. **Logical error rates at matched conditions**, so that the surface distance can be chosen to match
   the bicycle code's reliability before space-time costs are compared.

The runner in `experiments.py` is deliberately small and is not meant to replace your pipeline.

## For the Hamiltonian / algorithm owner

**`star_resources(q_data=, q_magic=, v_rz=, v_cliff=, cycle_ms=, parallel_shots=)` implements the
paper's Eqs. (32)-(33).** `star_data_qubits(n_logical, block)` gives Q_data = n_logical × n/k.

What I need, per workload (TFIM and Fermi-Hubbard) and per architecture:

| Input | Meaning |
|---|---|
| `n_logical` | logical qubits of the simulation |
| `v_rz`, `v_cliff` | rotation and Clifford volumes in qubit-cycles, in the paper's D.5 convention |
| `n_factories`, `n_factory` | magic-state space, giving Q_magic |
| error budget | ε_gate split into Clifford and rotation parts (paper Eqs. 29-30) |

With these I can reproduce the paper's footprint range (1,904 to 3,584 atoms for the 8×8 TFIM) or
explain the gap, and then vary the cycle time and noise. Without them the end-to-end comparison
cannot be done: I have only the memory part, which is exact.

One thing to keep in mind: in Eq. (33) the runtime is proportional to the cycle time, and the cycle
times are assumptions. A measured neutral-atom QEC round currently takes about 4.5 ms, against the
1 ms assumed for the surface code.

## For everyone

- I changed nothing outside `src/qec_star/hardware/`, `tests/test_udaya_*.py`, `docs/udaya/` and
  `results/udaya/`. `src/qec_star/surface.py` and `tests/test_surface.py` are on `udaya` exactly as
  they are on `origin/harman`. `pyproject.toml` is untouched.
- Optional packages I used that are not in `pyproject.toml`: `tesseract-decoder` (the decoder used for the validation run)
  and `jupyter` (to run the notebook). If the team wants Tesseract as a declared dependency, it is a
  one-line addition for whoever owns `pyproject.toml`.
- Please confirm the integration branch before I open a pull request. `udaya` is based on
  `epa-branch` at `0dc22d9`, contains `origin/harman` at `f377d22`, and has not been merged anywhere.
  Nothing was pushed to `harman` or `epa-branch`.
