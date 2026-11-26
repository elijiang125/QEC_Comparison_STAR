# Roadmap and status

Target: about one-fifth of a five-person project. Status as of 25 November 2026.

## Milestones

| # | Milestone | Status | Acceptance criterion | Met? |
|---|---|---|---|---|
| 1 | Branch and starter integrated | done | `udaya` pushed; patch and ZIP verified identical; teammates' tests pass | yes |
| 2 | Faithful loss-free noise model | done | every channel matches paper Sec. III; exact location counts match hand counts on both circuits; zero-noise identity; records preserved in X and Z bases | yes |
| 3 | Scenario registry with provenance | done | immutable reference; every parameter labeled measured / assumed / derived / synthetic | yes |
| 4 | Timing model | done | reproduces 1 ms and 2 ms; parallel layers counted once; fixed and per-layer time separated | yes |
| 5 | Resource accounting | done | Table 4 footprints reproduced; whole-block rounding; Eqs. (32)-(33) verified by hand | yes |
| 6 | Sensitivity experiments | pilot only | decoder passes the low-weight fault check; ≥ 100 failures or a stated bound per cell; both architectures on team circuits | **no**: decoder fails the check; surface circuit is a stand-in |
| 7 | Figures and analysis | partly | every figure regenerated from recorded data by one command | yes for 5 figures; pilot figures are labeled as such |
| 8 | Documentation | done | README, research notes, assumptions, validation, integration, results | yes |
| 9 | Atom loss (optional) | not started | loss-aware circuit semantics and a decoder validated on a toy case | no |

## What is finished

- Noise adapter for any TICK-delimited noiseless Stim circuit, with tagged channels and an audit count.
- Paper baseline scenario and 22 exploratory scenarios.
- Cycle-time model, memory break-even analysis, exact allocation.
- Deterministic pilot runner and a decoder acceptance test.
- Five figures and their underlying tables.
- 118 tests; the 68 pre-existing tests are untouched and pass.

## What remains, in priority order

1. **A decoder that passes the acceptance check** (simulation owner, or relay-BP if we can obtain an
   implementation). Until then no logical error rate from this repository should be quoted as a
   property of either code. *Done when:* `low_weight_fault_failures` returns 0 for weights 1 and 2 on
   the [[42,6,6]] circuit and the p-scaling of the failure rate is consistent with fault distance 5.
2. **The team's surface-code circuit** (Harman) in place of Stim's generated one. *Done when:* the
   noise-location test is updated to its structure and E1 is rerun.
3. **Rerun E1-E5 at production scale** with the two items above. *Done when:* each cell has ≥ 100
   failures or a stated upper bound, in both bases.
4. **Matched-reliability comparison.** Choose the surface distance whose logical error matches the
   bicycle code's, then compare space-time cost. *Done when:* the comparison quotes both error rates
   with intervals.
5. **End-to-end resources** from Eqs. (32)-(33) with the algorithm owner's volumes and factory
   counts. *Done when:* the paper's 1,904 to 3,584 qubit range is reproduced or the gap is explained.
6. **Timing with sourced durations.** Replace the lumped 0.25 ms per layer with gate, move, readout
   and reset times for a specific layout, including the longer moves of the bicycle schedule.
   *Done when:* each duration has an entry in ASSUMPTIONS.md.
7. **Biased and loss noise** (optional). Z-biased idle and CZ channels; heralded loss.

## Dependencies

See INTEGRATION.md for the full table. In short: a surface circuit (Harman), a decoder and production
sampling (simulation owner), algorithm volumes (Hamiltonian owner), transversal-gate and magic-state
circuits (QEC).

## Known limitations

- Memory experiments only. No transversal gates, no magic-state preparation, no rotations.
- Pauli noise only. No loss, leakage, crosstalk or coherent error.
- The surface results use Stim's circuit, which has H gates that a direct \|+> preparation would not.
- Cycle times are the paper's assumptions; measured rounds are currently about 4.5 times longer.
- The architectures are compared at the paper's code distances, not at equal logical error.

## Open questions

1. Is the paper's two-qubit channel the uniform 15-Pauli depolarizing channel? "Total strength p" suggests so; the paper does not say.
2. Does the paper's surface baseline at p = 1e-3 use the uniform model or the biased hardware model of the earlier paper?
3. Which of the two conflicting surface-STAR gate errors (Fig. 5 caption vs Sec. III.2) is right?
4. Do the quoted qubit counts include the two-instance doubling?
5. How long are the atom moves in the Table 2 schedule for a concrete trap layout?
