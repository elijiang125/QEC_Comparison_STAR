# Research brief: hardware-aware STAR comparison

## Question

For matched simulation workloads and logical error budgets, how sensitive is the high-rate bicycle-chain STAR advantage to hardware latency, asymmetric physical noise and (if feasible) heralded atom loss? Keep the original paper's reproduction and exploratory sensitivity experiments separate. A memory-only study is a useful intermediate result, not evidence of an end-to-end algorithm speedup.

## Primary baseline and definitions

[Ismail et al., Fast and Parallel High-Rate STAR Architecture for Megaquop Quantum Simulation, arXiv:2606.25011v1 (2026)](https://arxiv.org/html/2606.25011v1), especially Secs. II.3, III.1–III.2, App. B.2–B.3, C.3–C.4 and D.5/Table IV.

| Quantity | Surface STAR | Bicycle-chain STAR |
|---|---:|---:|
| Reference code | rotated d=9 | [[14l,2l,6]], m=7 |
| Data qubits per logical | 81 | 7 |
| Data + check ancillas per logical, idealized | 161 | 14 |
| Entangling syndrome layers | 4 | 8 |
| Nominal cycle duration | 1 ms | 2 ms |
| Baseline physical channel probability | 0.001 | 0.001 |
| Atom loss in reference resource estimate | none | none |
| Reference memory rounds | 3d | 3d |

Use code distance versus circuit distance carefully (App. B.2 reports circuit-level d−1 for the selected bicycle schedule). The `m=7` family is the initial scope; higher-distance code extensions must follow the QEC team's validated implementation.

Baseline channel semantics (Sec. III): preparation followed by one-qubit depolarization; measurement outcome flip; one- and two-qubit depolarization after respective gates; unused allocated qubits receive one-qubit depolarization during entangling layers. These are probabilities per operation/layer, not rates per unit time. The physical error parameter is not a directly interchangeable average gate infidelity. The baseline omits atom loss.

The architecture uses reconfigurable arrays: two data and two check-ancilla arrays for each bicycle block. Matching arrays can be brought together for parallel entanglement; uniform single-qubit pulses implement global H/S; cyclic permutations can be achieved with AOD transport. A one-site wraparound uses two moves with one AOD array or one with two arrays in the paper's abstraction. The actual movement schedule, transfer error, contention, spare atoms, readout and reloading latency are not measured here. Do not infer them from entangling depth alone.

The paper estimates ~2,240 physical qubits and ~200 s/shot for an 8×8 TFIM example and ~5.5× smaller space than its surface STAR comparator at comparable speed. These are projected end-to-end resources, not measured device outputs or the result of this starter. The independent two-shot convention is important: throughput-normalized seconds/shot is not wall latency. App. D.5 estimates physical footprint and runtime from rotation/Clifford volumes and factory allocation; keep its approximate ancilla factor distinct from exact block counting. Use identical Hamiltonian, Trotter schedule, simulation time and error budget before claiming a resource advantage.

## Secondary evidence and provenance

| Source | What it contributes | Limitation / how to use |
|---|---|---|
| [Ismail et al., PRX Quantum 7, 020343 (2026)](https://doi.org/10.1103/j2fw-ccmy) / [preprint](https://arxiv.org/abs/2509.18294) | Surface transversal STAR, logical gadget costs, neutral-atom implementation and direct analog rotations | Read full methods before borrowing a device-specific parameter. Do not conflate with the high-rate paper's uniform baseline. |
| [Evered et al., Nature 622, 268–272 (2023)](https://doi.org/10.1038/s41586-023-06481-y) | Experimental parallel CZ benchmarks near 99.5% | Fidelity is protocol/device dependent, not directly a Stim probability. |
| [Evered et al., Science 394, 197–201 (2026)](https://doi.org/10.1126/science.aei1312); [MIT-Harvard abstract](https://cua.mit.edu/publications/high-fidelity-entangling-gates-and-nonlocal-circuits-with-neutral-atoms) | 99.854(4)% CZ fidelity, 99.941(3)% conditional on loss postselection | Conditional and unconditional figures must not be mixed or double-counted with a separate loss channel. Not a full-system calibration. |
| [Bluvstein et al., Nature, doi:10.1038/s41586-025-09848-5](https://doi.org/10.1038/s41586-025-09848-5) / [NIST abstract](https://www.nist.gov/publications/fault-tolerant-neutral-atom-architecture-universal-quantum-computation) | Reconfigurable zones, repeated QEC, loss-resolved measurement and mid-circuit reuse on a system of up to 448 atoms | Device results justify modeling choices, not a claim that STAR's resource projections have been demonstrated. |
| [Quantum error correction resilient against atom loss, Quantum (2025)](https://quantum-journal.org/papers/q-2025-10-13-1884/) | Loss detection and adaptive decoding can change logical performance | Surface-code-specific mechanisms and thresholds cannot be transferred directly to bicycle chain. |
| [Stim gate/API documentation](https://github.com/quantumlib/Stim/wiki) | Clifford sampling, measurement errors, detectors and DEMs | Stim alone does not exactly simulate arbitrary-angle TMR, nor automatically provide a correct erasure-aware decoder. |

For every future numeric hardware parameter, record source identifier, version/date, section/table, measured vs assumed vs derived, device, units, denominator, uncertainty, conditionality and conversion method. If modeling an idealized d-dimensional depolarizing Pauli channel, average infidelity r maps to total nonidentity Pauli probability p=(d+1)r/d (d=2 for one qubit; d=4 for two). This is an explicit modeling assumption, not a general conversion for arbitrary real hardware noise. Do not apply it to conditional fidelity without separately accounting for survival.

## Proposed experiment matrix (not measured parameters)

1. **Baseline verification:** compare exact noise instructions and detector/observable counts in loss-free Stim circuits at p=0 and p=0.001. Use 3d rounds for each code to reproduce the paper's protocol; label different durations. Sample X and Z memories separately. Compare the same model under multiple seeds. Do not infer decoding performance from raw detector firing.
2. **Pauli sensitivity:** uniform p in {0.0005,0.001,0.002,0.003}; one-factor-at-a-time multipliers {0.5,1,2,4} on two-qubit, measurement and idle probabilities; leave all other rates at 0.001. These are synthetic sweeps, not a device error budget. Optional biased X/Z channels only after defining their total probability and decoder support.
3. **Timing sensitivity:** baseline cycle ratio r=t_bicycle/t_surface=2. Sweep r in {1,1.5,2,3,4}, preserving baseline and holding circuit assumptions explicit. An illustrative serialized timing model uses t_cycle=t_fixed+L*(t_gate_layer+t_move_layer), with duration per parallel layer. Never count a global parallel move once for every atom. For time-dependent noise, introduce separate per-duration models; do not silently vary the paper's per-layer p with latency.
4. **Loss-aware extension (optional):** define loss per operation, whether the flag is available immediately, behavior of subsequent gates on lost atoms, replacement schedule, and the decoder's use of erasure information. Start with a small circuit and known erasure checks. Do not treat a lost atom as an ordinary X error or a known erasure if the flag is unavailable. The paper's f is a fraction of physical errors modeled as heralded erasures, not a standalone per-gate loss probability. If decoder integration cannot be validated, report loss as future work, not a simulated logical rate.
5. **Resource sensitivity:** use validated logical failure rates to choose comparable error budgets; sweep factory counts, distinguish exact block versus D.5 estimated footprint, include both wall time and throughput. Inputs for rotations/Cliffords come from the algorithm team. Report the threshold at which advantage disappears, if observed; otherwise bound it within tested conditions. A normalized illustrative cost sweep is acceptable if inputs and missing calibration are stated.

## Scientific comparison checklist

- Report n/k/d, circuit distance where known, physical qubits including ancillas, both bases, memory rounds, cycle duration and decoder configuration.
- Use per-shot block failure (any observable) and per-observable failure with explicit denominators; correlations within one block prohibit pretending k outcomes are independent shots. Follow the source's exact per-round convention before comparing Fig. 4; if using parity-flip conversion, state independent symmetric flip assumptions. Do not use raw detector rate as logical error.
- For a common-time memory comparison, match physical horizon separately from 3d baseline tests. For a common-reliability resource comparison, select codes only once confidence intervals support the target.
- Pilot 1,000 shots per cell, then adaptive collection with predeclared stop rule (e.g. >=100 failures or >=1e6 shots); report 95% binomial intervals per independent shot and bounds for zero failures. Record seeds, shots, failures, runtime, package versions, source commit and circuit hash. No zero-failure claim of zero error.
- Use the same decoder where mathematically applicable; if decoders differ, disclose their effect and run a shared small reference (or near-optimal comparison). Relay-BP/MLE are paper references, not automatically implemented by using Stim. Avoid naive matching on non-graphlike hyperedges.
- No cherry-picking or postselection without acceptance probability and conditionality. Keep loss-free replication and extensions in separate tables/figures.

## Expected figures (not yet generated)

1. Architecture schematic and memory footprint versus logical capacity (include whole-block rounding).
2. Logical failure probability versus physical two-qubit/idle error, with confidence intervals (depends on simulator teammate).
3. Time/space sensitivity or break-even curve versus cycle ratio and factory count (depends on algorithm/decoder inputs).
4. Table of hardware assumptions with units and evidence labels.
