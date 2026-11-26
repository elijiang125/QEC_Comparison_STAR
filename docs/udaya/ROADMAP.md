# Roadmap and status

Target: about one-fifth of a five-person project. Status as of 25 November 2026. A milestone is
marked done only if its artifacts are committed on `udaya`.

## Milestones

| # | Milestone | Status | Acceptance criterion | Evidence |
|---|---|---|---|---|
| 1 | Branch and starter integrated | done | `udaya` pushed; patch and ZIP identical; teammates' tests pass | commit `e62ee2f` |
| 2 | Faithful loss-free noise model | done | every channel matches paper Sec. III; exact location counts match hand counts on both circuits; zero-noise identity; records preserved in both bases | `noise.py`, `tests/test_udaya_noise.py` |
| 3 | Scenario registry with provenance | done | immutable reference; every parameter labeled measured / assumed / derived / synthetic | `scenarios.py`, ASSUMPTIONS.md |
| 4 | Timing model | done | reproduces 1 ms and 2 ms; parallel layers counted once; fixed and per-layer time separated | `models.py`, RESULTS.md A3 |
| 5 | Resource accounting | done for memory; formulas only for end-to-end | Table 4 footprints reproduced; whole-block rounding; Eqs. (32)-(33) verified by hand | `resources.py`, RESULTS.md A1 |
| 6 | Sensitivity analysis | **partly** | (a) fault budget per scenario, exact; (b) decoder-backed logical error per scenario with ≥ 100 failures or a stated bound | (a) done: RESULTS.md A2, A4. (b) **not done**: only the baseline and one elevated-noise point were sampled, giving bounds |
| 7 | Figures | done for the analytic set | regenerated from recorded data by one command | `docs/udaya/figures/` (4 analytic, 1 provisional) |
| 8 | Documentation, notebook, handoff | done | documents match the committed code and data; anything measured ad hoc is labeled unrecorded | `docs/udaya/`; second review in VALIDATION.md |
| 9 | Reproduction of the paper's logical error rates | **not done** | failure rates with intervals that resolve the paper's values, with its decoders or equivalent | needs cluster-scale sampling |
| 10 | End-to-end resource comparison | **not done** | paper's 1,904 to 3,584 atom range reproduced or the gap explained | needs algorithm volumes |
| 11 | Atom loss (optional) | not started | loss-aware circuit semantics and a decoder validated on a toy case | |

## What remains, in priority order

1. **Production sampling with an accurate decoder** (simulation owner). Baseline in both bases to
   ≥ 100 failures per cell, then the one-channel, idle and literature-anchored scenarios. *Done
   when:* each cell has ≥ 100 failures or a stated bound from a fixed shot count, the decoder has
   been compared with Tesseract on the low-weight fault check, and its low-confidence events are recorded.
2. **The team's surface-code circuit** (Harman) in place of Stim's generated one. *Done when:* the
   noise-location test is updated to its structure and the baseline is rerun.
3. **Matched-reliability comparison.** Choose the surface distance whose logical error matches the
   bicycle code's, then compare space-time cost. *Done when:* both error rates are quoted with intervals.
4. **End-to-end resources** from Eqs. (32)-(33) with the algorithm owner's volumes and factory
   counts. *Done when:* milestone 10's criterion is met.
5. **Timing with sourced durations.** Replace the lumped 0.25 ms per layer with gate, move, readout
   and reset times for a specific layout, including the longer moves of the bicycle schedule.
   *Done when:* each duration has an entry in ASSUMPTIONS.md.
6. **Biased and loss noise** (optional). Z-biased idle and CZ channels; heralded loss.

Items 1 to 4 depend on teammates (HANDOFF.md). Items 5 and 6 I can do alone; 5 needs a trap layout
to be agreed.

## Known limitations

- Memory experiments only. No transversal gates, no magic-state preparation, no rotations.
- Pauli noise only. No loss, leakage, crosstalk or coherent error.
- Sampled results are bounds from a few thousand shots with a decoder that is not the paper's.
- The surface results use Stim's circuit, which has H gates that a direct \|+> preparation would not.
- Cycle times are the paper's assumptions; measured rounds are currently about 4.5 times longer.
- The architectures are compared at the paper's code distances, not at equal logical error.

## Open questions

1. Is the paper's two-qubit channel the uniform 15-Pauli depolarizing channel? "Total strength p" suggests so; the paper does not say.
2. Does the paper's surface baseline at p = 1e-3 use the uniform model or the biased hardware model of the earlier paper?
3. Which of the two conflicting surface-STAR gate errors (Fig. 5 caption vs Sec. III.2) is right?
4. Do the quoted qubit counts include the two-instance doubling?
5. How long are the atom moves in the Table 2 schedule for a concrete trap layout?
