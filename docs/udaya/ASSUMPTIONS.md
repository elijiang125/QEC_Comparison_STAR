# Assumptions and parameter provenance

Every number used by `qec_star.hardware` is listed here with its origin. Evidence classes:

- **assumed**: assumed by the paper we reproduce (Ismail et al., arXiv:2606.25011v1, "the paper").
- **measured**: reported from an experiment in the cited source.
- **derived**: computed by us from other entries with the stated formula.
- **synthetic**: chosen by us to probe sensitivity. No claim of realism.
- **unknown**: not available. We do not fill these in.

The paper was read from its arXiv HTML (v1, 23 June 2026). Numbers from the two most recent hardware
papers were read from their arXiv v1 preprints, because the publisher pages were not accessible; they
may differ slightly from the published versions.

## 1. Paper baseline (reproduction target)

| Parameter | Value | Class | Where in the paper |
|---|---|---|---|
| Noise family | uniform circuit-level depolarizing | assumed | Sec. III; Sec. III.2 "standard depolarizing error model without atom loss" |
| Physical error rate p | 1e-3 | assumed | Fig. 4 caption; App. C.3. App. C.3.5 sweeps 7e-4 to 5e-3 |
| Preparation of \|0> or \|+> | followed by 1-qubit depolarizing, strength p | assumed | Sec. III |
| Measurement (X or Z) | wrong outcome with probability p | assumed | Sec. III |
| 1- and 2-qubit gates | followed by 1- or 2-qubit depolarizing "of total strength p" | assumed | Sec. III |
| Idle | 1-qubit depolarizing p on "qubits that idle during entangling layers" | assumed | Sec. III |
| Idle during readout or reset | not stated | unknown | (we charge nothing in the baseline) |
| Atom loss | none in the baseline; otherwise post-selected heralded erasure fraction f | assumed | Sec. III.1, App. C.3.4 |
| Surface cycle time | 1.0 ms | assumed | Sec. III.2, Table 4, App. D.5 |
| Bicycle-chain cycle time | 2.0 ms | assumed | Sec. III.2, Table 4, App. D.5 |
| Reason given for cycle times | "reflecting their weight-four, weight-six, and weight-eight stabilizers" | assumed | Sec. III.2 |
| Gate, movement, readout, reset durations | not stated | unknown | |
| Surface code | rotated, d = 9, [[81,1,9]], 2d²−1 = 161 atoms per logical | assumed | Table 4, App. D.6 |
| Bicycle-chain code | [[14l, 2l, 6]] with m = 7; 14 atoms per logical | assumed | Table 1, Table 4 |
| Check ancillas, bicycle | n = 2lm, one per check | assumed | App. B.2 |
| Entangling depth, bicycle | 8 (Table 2 schedule, fault distance 5) | assumed | Sec. II.3, App. B.2 |
| Memory rounds | r = 3d (18 for the bicycle code) | assumed | Sec. III.1. The surface round count is not stated separately |
| Decoders | relay-BP and MLE (bicycle); MWPF (surface, from the earlier paper) | assumed | Sec. III.1, App. C.2 |

How we map this onto Stim (see `noise.py`):

| Paper statement | Stim instruction | Note |
|---|---|---|
| 1-qubit depolarizing, strength p | `DEPOLARIZE1(p)` | p is the total probability of X, Y or Z (p/3 each) |
| 2-qubit depolarizing, total strength p | `DEPOLARIZE2(p)` | p/15 for each of the 15 non-identity Paulis. The paper does not spell out the channel; "total strength p" matches this convention, but it is our reading |
| wrong outcome with probability p | `M(p)`, `MX(p)`, `MR(p)` | classical flip of the recorded bit; the state is not flipped |
| reset noise after `MR` | `DEPOLARIZE1(p)` after it | `MR(p)` alone does not make the reset noisy |

**derived**: after a reset to \|0>, only the X and Y parts of the depolarizing channel matter, so the
effective flip rate is 2p/3 (checked by sampling in `tests/test_udaya_noise.py`).

## 2. Quantities we derived

| Quantity | Value | Formula / check |
|---|---|---|
| Per-layer budget implied by the paper | 0.25 ms | 1.0/4 = 1.5/6 = 2.0/8. The paper's cycle time is exactly proportional to stabilizer weight, with no fixed term |
| Noise locations per round, surface d=9 | 288 two-qubit, 80 prep, 80 measurement, 68 idle = 516 | exact count on the team's surface circuit; hand count in the tests. Stim's generated circuit adds 80 one-qubit locations (596) |
| Noise locations per round, bicycle [[56,8,6]] | 448 two-qubit, 56 prep, 56 measurement, 0 idle = 560 | exact count on the team's circuit |
| Idle locations in the bicycle circuit | 0 | each of the 8 CNOT layers uses all 4lm atoms |
| Memory qubit ratio, 64 logical | 10,304 / 896 = 11.5 | exact block counting, d=9 vs [[56,8,6]] |
| Memory break-even cycle ratio | 11.5 (6.47 for 9 logical qubits) | qubit-seconds equal when t_bicycle/t_surface = footprint ratio |
| Fidelity to Pauli probability | p = (d+1)/d × (1 − F_avg) | F_avg = (d F_e + 1)/(d+1) (Nielsen, Phys. Lett. A 303, 249 (2002)) and F_e = 1 − p for a Pauli channel. 3/2 for one qubit, 5/4 for two |
| Idle dephasing | p_Z = (1 − exp(−t/T2))/2 | pure dephasing with exponential decay; an assumption about the decay shape |

## 3. Literature values (hardware, Rb-87 tweezer arrays)

Used only in the `lit/rb87_mixed` and `idle/t2_*` scenarios and in the discussion of timing.

| Quantity | Value | Class | Source |
|---|---|---|---|
| CZ fidelity | 99.52(4)% (Bell decay), 99.54(2)% (randomized benchmarking) | measured, no loss post-selection | Evered et al., Nature 622, 268 (2023) |
| CZ fidelity | 99.854(4)% raw; 99.941(3)% post-selected on neither atom lost | measured | Evered, Xu, Li et al., Science 394, 197 (2026); numbers from arXiv:2604.25987v1 |
| Loss per atom per CZ | 0.054(2)%; loss is about 60% of the CZ error | measured | same |
| CZ duration | 270 ns | stated for the gate in use | Bluvstein et al., Nature 649, 39 (2026), Methods (arXiv:2506.20661v1) |
| Global 1-qubit fidelity | 99.97% | measured | Evered et al. 2023, Methods |
| Mid-circuit readout | about 99.8% fidelity, 500 µs imaging | measured | Bluvstein et al., Nature 626, 58 (2024), Methods and Fig. 1c |
| Move between gates | about 200 µs; loss onset at 55 µm in 200 µs | measured / stated | Bluvstein et al., Nature 604, 451 (2022); Nature 626, 58 (2024) |
| Coherence T2 | 1.5 s with XY16 (128 π pulses); 1 to 2 s in circuits | measured | Bluvstein 2022 Methods; 2024 and 2026 Methods |
| Full QEC round | 4.45 ms (0.47 ms between gates, 2.57 ms moving ancillas). A 4 ms cycle is also reported, for repeated calibration, not for QEC | measured, "not optimized for speed" | Bluvstein et al. 2026, Methods |
| Assumed QEC cycle in architecture papers | 1 ms | assumed | Zhou et al., arXiv:2505.15907; origin is an outlook estimate in Bluvstein 2022 |

Not found in any source we opened (**unknown**): a measured fidelity per atom move, a measured idle
error per millisecond, a single atom-loss-per-round figure, and the CZ duration in the two Evered papers.

Three cautions when using these:

1. A randomized-benchmarking fidelity is not a depolarizing probability. The conversion in section 2
   is exact only if the error really is depolarizing. Measured errors are Z-biased and mostly loss.
2. The 99.941% figure is conditional on no loss. Using it together with a separate loss channel
   is correct; using the raw 99.854% together with a loss channel counts loss twice.
3. The measured 4.45 ms round is about 4.5 times the paper's assumed 1 ms. The paper's cycle times
   are projections, and so is every runtime we compute from them.

## 4. Synthetic scenarios

All `uniform/*`, `asym/*`, `timing/*` and `idle/t2_150ms/*` scenarios in `scenarios.py` are synthetic:
they scale one input of the paper baseline to see how results respond. `python -m qec_star.hardware
scenarios` prints every scenario with its per-parameter evidence class.

## 5. Modeling choices that are ours

- **`cycle_idle`**: a per-round depolarizing probability on qubits that wait through a measurement
  moment and are used again by a later entangling layer. Not in the paper; zero in the baseline. It
  is the only place where cycle duration enters the noise, so it is how a longer bicycle cycle can
  cost fidelity. An r-round memory gets it r − 1 times per data qubit in both architectures.
- **Dephasing applied as depolarizing**: the T2-derived probability p is a Z error, but we insert a
  depolarizing channel of the same total probability. Its Z component is p/3; the errors that act as
  phase flips (Z or Y) total 2p/3, one third less than p; and it adds bit-flip errors (X or Y, 2p/3)
  that pure dephasing would not cause.
- **Surface circuit**: results use the team's circuit (`qec_star.surface`), which prepares and
  measures X ancillas directly, as the paper describes. Stim's generated circuit, the stand-in used
  before, does it with H gates and so has 80 more noise locations per round at d = 9. It is kept as
  the `surface_reference` architecture for comparison and to keep earlier records reproducible.
- **One-qubit error**: neither team circuit contains a one-qubit gate, so `one_qubit` affects no
  current result. It will matter once transversal gates are simulated.
- **Atom counts in Eq. (32)**: the paper's 2 (Q_data + Q_magic) need not be an integer. We round one
  instance up to a whole atom and then multiply by the number of parallel instances.
