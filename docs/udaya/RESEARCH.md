# Research notes: hardware-aware STAR comparison

## Question

Does the bicycle-chain qLDPC STAR architecture keep its space-time advantage over surface-code STAR
when hardware operational overhead and non-uniform physical noise are taken into account?

This is an investigation, not a defense of the paper. Faithful reproduction of the paper's model and
exploratory extensions are kept apart throughout: the registry marks each scenario `reference` or
`exploratory`, and RESULTS.md reports them in separate sections.

## The primary paper

Ismail, Kornjača, Hu, Maskara, Wang, Zhou, Zhao, *Fast and Parallel High-Rate STAR Architecture for
Megaquop Quantum Simulation*, [arXiv:2606.25011v1](https://arxiv.org/html/2606.25011v1) (23 June 2026).
Read in full from the arXiv HTML. Parameter-level provenance is in ASSUMPTIONS.md; this section
records what the paper claims and what it leaves open.

**Codes.** Bicycle chain [[2lm, 2l, d ≤ m]] from a(x,y) = 1 + y³ + xy² + xy⁴ on an l × m torus,
self-dual with weight-8 checks. Main instances [[14l, 2l, 6]] (m = 7); l = 3 gives [[42,6,6]], and
l = 4 gives the k = 8 block used for the rotation gadget. The surface baseline is the rotated d = 9
code from the earlier transversal paper.

**Syndrome extraction.** Depth-8 CNOT schedule (Table 2), one ancilla per check. Of 212 valid
schedules for d = 6, 192 have fault distance 4 and 20 have fault distance 5; the paper uses one of
the 20. So the circuit-level distance is 5, not 6.

**Noise.** Uniform depolarizing, p = 1e-3, no loss in the headline numbers. Loss enters only as a
heralded erasure fraction f of each error budget, handled by discarding shots (f = 0.7 in the
abstract's numbers, f = 0 in Fig. 5).

**Timing.** Cycle times 1 ms (surface), 1.5 ms (BB/GB) and 2 ms (bicycle chain), justified only by
stabilizer weight. No gate, movement, readout or reset duration appears anywhere in the paper.
One cyclic shift needs two moves with one AOD array, or one move with two.

**Resource model (App. D.5).**

    Q_phys = 2 (Q_data + Q_magic)                              (32)
    t_run  = (V_RZ / Q_magic + V_Cliff / Q_data) × t_cycle     (33)
    Q_data = n_logical × n/k,   Q_magic = n_factories × n_factory

The bicycle architecture runs two instances side by side: twice the atoms, per-shot time t_run/2.

**Headline claims.** For an 8×8 transverse-field Ising simulation: 1,904 to 3,584 qubits and 8 to
116 s per shot at f = 0 (the arXiv HTML doubles some digits, see item 5 below; check the PDF); "surface STAR achieves ε_gate = 0.46 (TFIM) and 0.84 (FH) at 5.5× and 5.7×
the qubit count". The abstract's 2,240 qubits and ~200 s per shot are at f = 0.7 and a longer
simulated time. Reported logical error scales: transversal CNOT ~1e-7 per logical (bicycle, k = 8)
against ~4e-6 (surface d = 9).

**Open problems the paper names (Sec. IV).** Structured, biased hardware noise; syndrome extraction
under atom loss; real-time decoding (their MLE decoder does not scale); simulation methods that
combine non-Clifford gates with loss.

### Things we noticed while reading

1. **The two codes are not at equal reliability.** The comparison pairs a d = 6 bicycle code decoded
   with relay-BP/MLE against a d = 9 surface code decoded with MWPF, which the paper itself calls
   suboptimal. The 5.5× is a ratio at the paper's chosen operating points, not at matched logical error.
2. **Internal inconsistency.** The Fig. 5 caption lists the surface-STAR accumulated gate error as
   0.32 / 0.31; the Sec. III.2 text gives 0.46 / 0.84. We could not resolve this from the HTML.
3. **Factor of two.** Eq. (32) doubles for ancillas; the two-instance doubling is described separately.
   Whether the quoted qubit counts include one or both is not explicit.
4. **A consistency check we can do.** 1,904 = 34 × 56, 3,584 = 64 × 56 and 2,240 = 40 × 56, where 56
   is the data-qubit count of one [[56,8,6]] block. A 64-qubit simulation needs 8 such blocks (448
   data qubits), so the rest is magic-state space: at the smallest point, data storage is under half
   of the footprint. This is our inference from the numbers, not a statement in the paper.
5. **Rendering artifact.** Sec. III.1 of the HTML shows "88 versus 44" for the entangling depths;
   this is 8 versus 4 (Sec. II.3 states depth 8).
6. **No public code.** App. D refers to an accompanying open-source package, but the paper gives no link.

## Supporting literature

Each entry was checked against Crossref or arXiv metadata, and numbers against the full text
(arXiv versions for the 2025-2026 papers). Corrections to the starter notes are marked.

| Source | What it gives us | Limits |
|---|---|---|
| Ismail et al., *Transversal Architecture for Megaquop-Scale Quantum Simulation with Neutral Atoms*, PRX Quantum 7, 020343 (2026), arXiv:2509.18294. **Corrected**: the published title has no "STAR" | The surface-code STAR baseline: rotated code, d = 3-7 simulated and d = 9 extrapolated, MWPF decoder, and a Z-biased hardware-derived Pauli model (CZ ZZ error 1.3e-3, measurement flip 4e-3, per-move Pauli about 2.8e-4) with loss folded into a Pauli-Y channel | A different noise model from the primary paper. It states no physical cycle time, only clock cycles and a uniform ~200 µs transport. All values are model inputs |
| Evered et al., *High-fidelity parallel entangling gates on a neutral-atom quantum computer*, Nature 622, 268 (2023) | CZ fidelity 99.52(4)% and 99.54(2)% on up to 60 atoms in parallel; global 1-qubit 99.97% | Loss was not measured separately; no gate duration in the text we read |
| Evered, Xu, Li et al., *High-fidelity entangling gates and nonlocal circuits with neutral atoms*, Science 394, 197 (2026), arXiv:2604.25987 | CZ 99.854(4)% raw and 99.941(3)% when neither atom is lost; loss 0.054(2)% per atom per CZ, about 60% of the error | Post-selection happens at the end of the sequence, not mid-circuit. Numbers from arXiv v1 |
| Bluvstein et al., *A fault-tolerant neutral-atom architecture for universal quantum computation*, Nature 649, 39 (2026), arXiv:2506.20661. **Corrected**: volume and year | Up to 448 atoms; measured QEC round of 4.45 ms; 270 ns CZ; coherence 1-2 s; non-destructive readout with 0.3% loss; "roughly half of our errors being loss" | Timings are explicitly not optimized for speed. No single loss-per-round number |
| Bluvstein et al., Nature 604, 451 (2022) and Nature 626, 58 (2024) | Transport physics (constant-jerk moves, time ∝ √distance, 55 µm in 200 µs before loss), 500 µs mid-circuit imaging, T2 = 1.5 s | Earlier machines; per-move fidelity is not reported cleanly |
| Xu et al., *Constant-Overhead Fault-Tolerant Quantum Computation with Reconfigurable Atom Arrays*, arXiv:2308.08648 | A worked timing model for qLDPC codes with atom rearrangement: 24 ms per stabilizer round for a 10⁴-qubit hypergraph-product code | Assumed parameters; a different code family with long-range moves |
| Zhou et al., arXiv:2505.15907 | Source of the common 1 ms cycle assumption (500 µs move pipelined with 500 µs measurement) | Assumed |
| Perrin, Jandura, Pupillo, *Quantum Error Correction resilient against Atom Loss*, Quantum 9, 1884 (2025) | Loss-aware decoding of the surface code; loss threshold about 2.6% | Surface code only; independent loss per CZ. Does not transfer to the bicycle chain without new work |
| Müller et al., arXiv:2506.01779 (relay-BP); Wu et al., arXiv:2508.04969 (MWPF) | The decoders the paper relies on | Neither is in this repository's dependencies; see VALIDATION.md for availability |
| Beni, Higgott, Shutty, *Tesseract: A Search-Based Decoder for Quantum Error Correction*, arXiv:2503.10988 | The decoder we used: a search for the most likely error, exact with an unbounded search and a heuristic otherwise; reported one to two orders of magnitude below BP+OSD on bicycle-code memories | Published as development builds only; we used its default finite beam |
| Gidney, *Stim*, Quantum 5, 497 (2021) | Exact semantics of `DEPOLARIZE1/2` and `M(p)` | Clifford only: cannot simulate the arbitrary-angle rotation gadget |
| Wu et al., Nat. Commun. 13, 4657 (2022); Ma et al., Nature 622, 279 (2023); Scholl et al., Nature 622, 273 (2023) | Erasure conversion: what fraction of errors can be heralded | Yb and Sr platforms, not the Rb-87 platform assumed here |

## What the literature implies for our question

- **Timing.** The paper's cycle times are proportional to stabilizer weight with no fixed term. On
  real hardware a round is dominated by transport and readout (2.57 ms of the measured 4.45 ms is
  moving ancillas). Any time that does not scale with the number of entangling layers moves the
  bicycle/surface cycle ratio below 2, which favors the bicycle chain. Longer moves per layer for the
  bicycle chain (its checks reach up to 4 sites away) would push the other way. Neither is in the paper.
- **Noise composition.** Measured errors are Z-biased and more than half loss. A uniform depolarizing
  p is a summary, not a description. The bicycle circuit is dominated by two-qubit gate noise more
  strongly than the surface circuit (see RESULTS.md), so it is the more exposed of the two to the CZ error.
- **Idle error.** With T2 between 1 and 2 s, waiting 1 ms costs a Z error of 2.5e-4 to 5e-4, the same
  order as the gate error itself at p = 1e-3. The paper charges nothing for it, and the bicycle cycle
  is twice as long.

## Experiment matrix

| ID | What varies | What is held | Output | Status |
|---|---|---|---|---|
| E1 | nothing (paper baseline) | p = 1e-3, r = 3d, both bases | failure per shot | sampled with Tesseract on both team circuits: bounds, or coarse estimates at surface d ≤ 5 |
| E2 | uniform p | everything else | failure vs p | one point (2e-3, Z basis) sampled |
| E3 | two-qubit error × {0.5, 2, 4} | other channels at 1e-3 | fault budget; relative failure | fault budget done (exact); sampling not run |
| E4 | measurement, idle × {0.5, 2, 4}; literature-anchored profile | other channels at 1e-3 | fault budget; relative failure | fault budget done (exact); sampling not run |
| E5 | cycle ratio; T2-derived per-round idle | paper noise | break-even curves; fault budget | done (analytic); sampling not run |
| E6 | logical qubit count, block size | exact counting | physical qubits | done (analytic) |
| E7 | heralded loss | | | not started; needs loss-aware circuits and a decoder |

Sampling for E3-E5 needs 10⁵ to 10⁶ shots per cell at roughly 1 to 5 worker-seconds per shot and is handed to
the surface-code and simulation owner (HANDOFF.md), with recommended configurations.

Rules applied to every sampled experiment: one sample per shot (failure = any observable wrong);
a shot count fixed before sampling; 95% Wilson intervals; seeds derived from the circuit hash; the
full configuration and code revision stored with each result. Raw detector rates are never reported
as logical error rates.
