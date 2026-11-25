# Implementation roadmap

Target a roughly one-fifth contribution to a five-person team. The required work is a scoped hardware/noise package and a defensible sensitivity study, not a full independent replication. Estimates are planning ranges only; confirm deadline and scope with teammates.

| Phase | Deliverables | Acceptance gate | Focused effort |
|---|---|---|---:|
| 0. Scope and integration | confirm ownership, base branch and Python interfaces; source inventory | no overlap with QEC/algorithm work | 1–2 h |
| 1. Loss-free baseline | explicit profile, circuit adapter, exact block footprint, source table | p=0 equivalence; known-channel tests; detector/observable preservation on both memory circuits | 3–5 h |
| 2. Hardware timing | cycle model, parallel move accounting and timing scenarios | baseline 1/2 ms recovered; no double-counting idle/motion; clear assumption labels | 2–3 h |
| 3. Joint sensitivity | agreed profiles and reproducible input grid; collect decoder-backed logical results with simulation owner | same conventions, provenance, uncertainty and no fabricated data | 3–5 h |
| 4. Resources and paper | memory footprint, jointly computed cost sweep and figures; methods and limitations text | correct factory/ancilla counts, latency vs throughput, error-budget consistency | 3–5 h |
| Optional extension | explicit loss-aware noise and decoder experiment | validated known-loss toy tests and erasure flags; otherwise defer | separate agreement |

Required scope estimate: 12–20 focused hours (not including compute queue time or optional extension).

## Milestone checklist

- [x] Prepare initial isolated package, references, roadmap, and test files.
- [x] Verify dependency-free arithmetic, parameter validation and CLI in local starter tree (16 passed).
- [ ] Run Stim-dependent tests in a full repository checkout and fix adapter/API issues.
- [ ] Agree on base branch, noise decorator input format and work split with team.
- [ ] Verify noiseless equivalence on both memory circuits and manually inspect a noisy circuit/DEM.
- [ ] Add a source-provenanced hardware timing/noise scenario registry (do not claim calibration from a synthetic sweep).
- [ ] Share grid and code with simulation owner; lock seed and shot/stop policy before running.
- [ ] Run baseline and sensitivity cases with team; inspect error bars and failed/deferred cases.
- [ ] Obtain algorithm volumes and validated logical error rates before using Appendix D.5 for end-to-end resource estimates.
- [ ] Create figures and reproducible data tables, write methods and limitations; open scoped PR after team review.

## Handoff contracts

**QEC owners → hardware:** clean Stim circuit with correct measurement records, explicit physical qubit IDs, TICK-separated layers and code parameters; optionally movement metadata for every entangling layer. No injected faults unless a specific test.

**Hardware → simulation owner:** immutable profile, noise-decorated circuit, allocated qubit IDs, cycle milliseconds, profile/source/version and experiment grid. Simulator supplies decoder and per-shot/per-observable counts; hardware work does not replace decoder implementation.

**Algorithm owner → hardware:** logical qubit count, Trotter steps/time, gate counts, consistently defined Clifford/rotation qubit-cycle volumes, magic factory capacity/acceptance, target error budget. Hardware supplies exact memory allocation and explicitly parameterized D.5 footprint, latency, throughput and qubit-seconds. The starter does not infer algorithm volumes from code distance.

## Priorities if time is short

Finish exact loss-free noise + timing interface and a small joint comparison; write up methodology and report unresolved dependencies. Defer loss and detailed movement physics. Do not claim a complete reproduction when only a memory model or resource-accounting formula is tested. Negative outcomes are valid results.
