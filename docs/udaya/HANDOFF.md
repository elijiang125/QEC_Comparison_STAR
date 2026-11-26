# Technical handoff

What each teammate can use from the hardware workstream today, and what the hardware workstream
needs from them. Interfaces are specified in [INTEGRATION.md](INTEGRATION.md); evidence for the
statements below is in [VALIDATION.md](VALIDATION.md) and [RESULTS.md](RESULTS.md).

## For the QEC and surface-code owners

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

1. **A noiseless surface-code memory circuit** (surface-code owner) with the same conventions: `TICK` between
   layers, both bases, detectors and observables included. Please say whether X ancillas are prepared
   and measured directly (`RX`/`MX`) or through H gates; it changes the noise count by 80 locations
   per round at d = 9. Until then I use Stim's generated circuit, labeled `surface_reference`.
2. **Transversal-gate and magic-state circuits** when they exist. The noise layer will accept them
   if they follow the rules in INTEGRATION.md; `CZ` and `SWAP` are already supported.
3. If atom moves become explicit in the circuit, tell me how they are marked, so transport time and
   transport error can be attached to them.

## For the simulation owner

**Use `decorate_stim_memory(circuit, SCENARIOS[id].noise)` to get a noisy circuit, then decode it
however you like.** Store the scenario id and `REGISTRY_VERSION` with each result.

Two things to do before trusting any logical error rate:

1. Run `low_weight_fault_failures(noisy_circuit, weight, samples, decoder=...)` for weights 1 and 2
   and compare decoders on it. It is a diagnostic, not a pass/fail proof: a most-likely-error decoder
   can legitimately mis-correct a rare single fault. On our circuit BP+OSD-0 from `ldpc`
   mis-corrected 8 of 300 double faults; Tesseract mis-corrected none, and neither did BP+OSD with
   literature settings (10,000 iterations, OSD-CS order 10) on 100 double faults, at about 2 s per
   decode. The sampled failure rates differ by about 100 times in the same direction.
2. Check `dem_logical_collisions(dem) == 0` if your decoder merges error mechanisms by detector pattern.

What we measured about cost, so you can plan compute: on the 18-round [[42,6,6]] memory, the
validation run spent 1.1 to 1.3 worker-seconds per shot at p = 1e-3 and 5.2 at p = 2e-3 with
Tesseract (recorded wall time × 12 workers on a 14-core laptop). At the failure rates it
gives (0 and 1 failures in 6,000 shots at p = 1e-3), resolving the paper baseline needs on the order
of 10⁵ to 10⁶ shots per cell. That is a cluster job, not a laptop job.

I used Tesseract's default beam of 5. Its authors recommend a beam of 15 with beam climbing for
bicycle codes, and it is an exact most-likely-error decoder only with an unbounded search. Record its
low-confidence flag in production runs; my runner does not.

What I need:

1. **A production decoder** for the bicycle chain: relay-BP (IBM's `relay-bp`), or Tesseract on a
   cluster. `relay-bp` did not build on my machine for a local reason (C toolchain license), not
   because of the package.
2. **Decoder-backed runs of the sweeps I could not afford**: one channel at a time (`asym/*`), the
   T2-derived idle scenarios (`idle/*`) and the literature-anchored profile (`lit/rb87_mixed`), on
   both architectures and both bases, with a fixed shot count per cell.
3. **Logical error rates at matched conditions**, so that the surface distance can be chosen to match
   the bicycle code's reliability before space-time costs are compared.

The runner in `experiments.py` is small on purpose. Replace it with your pipeline; keep the record
fields if you can, so the figures regenerate.

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

- Nothing outside `src/qec_star/hardware/`, `tests/test_udaya_*.py`, `docs/udaya/` and
  `results/udaya/` was changed. `pyproject.toml` is untouched.
- Optional packages I used that are not in `pyproject.toml`: `tesseract-decoder` (the decoder used for the validation run)
  and `jupyter` (to run the notebook). If the team wants Tesseract as a declared dependency, it is a
  one-line addition for whoever owns `pyproject.toml`.
- Please confirm the integration branch before I open a pull request. `udaya` is based on
  `epa-branch` at `0dc22d9` and has not been merged anywhere.
