# Validation record

What was checked, how, and what the outcome was. Commands assume the repository root and an
environment installed with `python -m pip install -e '.[dev]'` (Python 3.12, Stim 1.16, ldpc 2.4.1).

## Test suite

`python -m pytest -q` runs 207 tests: the 62 that were on `epa-branch` (unchanged; one more is
marked slow and deselected by the project's settings) and 145 for this workstream. All pass. Nothing is skipped for a missing dependency; the two tests that use the
optional Tesseract decoder need `pip install tesseract-decoder`.

| File | What it establishes |
|---|---|
| `tests/test_udaya_noise.py` | channel placement on hand-written circuits; exact noise-location counts on both real circuits; zero-noise identity; record, detector and observable preservation in X and Z bases; exact unrolling of repeat blocks; the per-round idle rule; explicit rejection of noisy, unsupported or ambiguous input; two sampled rates against closed-form values |
| `tests/test_udaya_hardware.py` | probability and timing validation; fidelity conversion; cycle formula by hand; block footprints against the paper's Table 4; whole-block rounding; break-even ratio; Eqs. (32)-(33) by hand; rounding of fractional inputs; latency versus throughput; the CLI |
| `tests/test_udaya_scenarios.py` | the reference scenario equals the paper's values and cannot be mutated; every scenario labels every parameter; one-factor scenarios change exactly one channel |
| `tests/test_udaya_experiments.py` | Wilson interval against known values; exact fixed shot counts; determinism under fixed seeds and any worker count; disjoint seeds for different circuits; provenance fields; refusal to append to an existing result file; refusal of detector error models with merged logical effects; the low-weight fault check; **every committed validation record regenerates to the same circuit hash and seeds** |

Expected values in these tests come from hand derivations written next to the assertion, not from
running the implementation.

## Noise model against the paper

Checked statement by statement against Sec. III (table in ASSUMPTIONS.md, section 1).

Noise locations in a full memory experiment, derived by hand and asserted in the tests:

| Circuit | prep | one-qubit | two-qubit | idle | measurement |
|---|---|---|---|---|---|
| bicycle [[42,6,6]], 18 rounds | 42 + 18·42 = 798 | 0 | 18·8·42 = 6,048 | 0 | 18·42 + 42 = 798 |
| surface d = 9, 27 rounds (Stim) | 161 + 27·80 = 2,321 | 27·80 = 2,160 | 27·288 = 7,776 | 27·68 = 1,836 | 27·80 + 81 = 2,241 |

The surface CNOT count per round is the sum of check weights: 64 weight-4 checks and 16 weight-2
checks give 288. Idle locations are 4 layers × 161 atoms − 2 × 288 = 68.

**Finding: the paper's idle channel does nothing to the bicycle-chain memory circuit.** Each of the 8
CNOT layers of Table 2 acts on all four atom arrays, so no atom is ever idle during an entangling
layer. The `asym/idle_*` scenarios therefore produce a bicycle circuit identical to the baseline
(same SHA-256), while the surface circuit has 68 idle locations per round.

## Circuit-level distance of the team's schedule

Stim's `search_for_undetectable_logical_errors` (detection-event sets up to size 6, edges up to
degree 6) on the noisy [[42,6,6]] memory circuit, 2 and 4 rounds, both bases, found an undetectable
logical error of weight 6 and nothing lighter. This is a truncated search, so it gives an upper
bound of 6 and no proof of a lower bound. It is consistent with the paper's stated fault distance of
5 for its chosen schedule and shows no low-weight hook error in the team's implementation of Table 2.

## Low-weight fault check (important)

`experiments.low_weight_fault_failures` draws random sets of w error mechanisms from the detector
error model, decodes their combined detection events and counts wrong logical predictions.

What it does and does not show. In a circuit with fault distance 5, a minimum-weight decoder
corrects every set of 1 or 2 faults. A most-likely-error decoder need not, because the mechanisms
have unequal probabilities: a rare single fault can be less likely than two common faults with the
same detection events. A nonzero count is therefore a warning, not proof of a defect, and a zero
count on a sample certifies nothing. The check is most useful as a comparison of decoders on the same
fault sets, read together with sampled failure rates on the same circuits.

Recorded in `results/udaya/decoder_low_weight_checks.jsonl` (seed 0 unless noted, p = 1e-3, Z basis;
mis-corrected / tried):

| Decoder | bicycle [[42,6,6]], 6 rounds, w = 1 | w = 2 | w = 3 | surface d = 3, w = 1 | surface d = 5, w = 2 | time per decode (bicycle) |
|---|---|---|---|---|---|---|
| Tesseract (`det_beam=5`, `pqlimit=200000`) | 0 / 300 | 0 / 300 | 0 / 150 | 0 / 300 | 0 / 300 | ~0.1 s |
| BP+OSD-0 (min-sum, 30 iterations) | 0 / 300 | **8 / 300** | **15 / 150** | **5 / 300** | 0 / 300 | ~0.03 s |
| BP+OSD, literature settings (min-sum, 10,000 iterations, OSD-CS order 10) | not run | 0 / 100 | not run | not run | not run | ~1.8 s |

The literature-settings row used seeds 0 to 3 with 25 sets each. Not in the committed record: an
earlier ad-hoc run of product-sum BP (200 iterations) with OSD-CS order 10 mis-corrected 2 of 300
double faults, and Codex's independent run on the 18-round circuit found BP+OSD-0 wrong on 4 of 100.

Sampled memory experiments on identical circuits confirm the size of the effect (RESULTS.md, B1):
at p = 1e-3 the 18-round [[42,6,6]] memory fails in 6.9% of shots with BP+OSD-0 and in 0 of 6,000
with Tesseract.

Consequences:

- BP+OSD-0 results are not properties of the codes. The stopped pilot is kept only as evidence of this.
- BP+OSD with literature-strength settings mis-corrected none of 100 double faults but took about
  20 times longer per decode than Tesseract at 6 rounds; we did not sample with it.
- Tesseract with a finite beam is a heuristic. It returns the most likely error only with an
  unbounded search, which we did not use; the Tesseract paper recommends a beam of 15 with beam
  climbing for bicycle codes, and we used the package default of 5. The result files do not record
  its low-confidence flag. The evidence that Tesseract is adequate here is the comparison above and
  the sampled results, not a guarantee.
- We have not reproduced the paper's logical error rates and do not claim to.

Decoder literature and availability (checked 25 November 2026):

| Decoder | Reference | Availability | Fit |
|---|---|---|---|
| Relay-BP | Müller et al., arXiv:2506.01779 | PyPI `relay-bp` 0.2.2, source build with Rust on Python 3.12 | used by the paper; heuristic; needs a per-code parameter interval that nobody has tuned for [[42,6,6]]. Did not build on this machine because the C linker is blocked by an unaccepted Xcode license |
| MLE by integer programming | paper App. C.2 (Gurobi) | Gurobi license; no code released with the paper that we could find | the paper's reference decoder. Tesseract ships a HiGHS-based exact decoder (`tesseract_decoder.simplex`) that could play this role; untested here |
| Tesseract | Beni, Higgott, Shutty, arXiv:2503.10988 | PyPI `tesseract-decoder`, prebuilt wheels, development builds only (we used `0.1.1.dev20261117025421`) | chosen: passes the check, takes Stim detector error models with hyperedges directly |
| BP+OSD | Roffe et al., PRR 2, 043423 (2020) | `ldpc`, already a dependency | OSD-0 is inadequate; literature settings were only spot-checked |
| BP+LSD | Hillmann et al., Nat. Commun. 16, 8214 (2025) | `ldpc` | not tested beyond an unrecorded 300-shot speed comparison, in which it failed as often as BP+OSD-0 |
| MWPF | Wu et al., arXiv:2508.04969 | PyPI `mwpf`, prebuilt wheels | the paper's surface-code decoder; its own paper reports it far worse than BP+OSD on bicycle-type circuit noise |

To reproduce the check:

```python
from qec_star.hardware.experiments import DECODERS, Cell, low_weight_fault_failures
from qec_star.hardware.models import NoiseProfile
circuit = Cell("check", "bicycle", (3, 7), "Z", 6, NoiseProfile.paper()).noisy_circuit()
for name in ("tesseract", "bposd0"):
    print(name, [low_weight_fault_failures(circuit, w, 300, decoder=DECODERS[name]) for w in (1, 2)])
```

## Statistics

- The number of shots per cell is fixed before sampling (`SamplingPlan`), so ordinary binomial
  inference applies. We report Wilson score intervals, which are approximate: their coverage can
  fall below 95% when the expected number of failures is well under one (for example about 89% at
  n = 6,000 and a true rate of 2e-5). An earlier version stopped at 100 failures; that rule also
  biases the estimate upward, and was removed. The pilot file, which used it, is labeled accordingly.
- A shot is one sample. The k observables of a block are correlated (the one bicycle failure we saw
  flipped five of six) and are never pooled.
- `per_round_rate` converts a failure probability to a per-round rate for a single observable only.
  It is not applied to block failure rates.

## Provenance

Every record stores the noisy circuit's SHA-256, the decoder settings, the sampling plan, each
chunk's seed and failure count, package versions, and `code_revision`: the commit, a dirty flag for
the package, and `source_tree`, git's hash of the committed `src/qec_star` directory. The validation
records were produced at commit `0f4322f` with `source_tree` `f351cc7` and a clean package.

Later commits do change the package (figure labels, input validation, stricter rejection of
ambiguous circuits, a hash of the loaded source in new records); `git diff 0f4322f -- src` shows
exactly what. They do not change any recorded circuit: a test rebuilds all 12 validation circuits
with the current code and checks their SHA-256 and seeds against the records.

Limits of this scheme: git describes committed files, not what Python loaded. Records made from now
on also store `loaded_source_sha256`, a hash of the package files at import, and take the revision
before sampling starts. The 31 existing records predate this and rely on the clean-package flag.
`run_grid` refuses to write into a non-empty file, because rerunning with the same seeds would
duplicate trials.

## Resource arithmetic

`python -m qec_star.hardware --logical-count 64` prints 10,304 atoms (64 × 161) for surface d = 9
and 896 (8 blocks × 112) for the bicycle [[56,8,6]] block, a ratio of 11.5, and a qubit-second ratio
per round of 5.75 at the paper's 1 ms and 2 ms cycles. These match the hand calculation and the
paper's per-logical footprints of 161 and 14 (Table 4).

The bicycle k is computed from the team's parity-check matrices with `gf2.css_k` rather than assumed:
k = 4, 6, 8 for l = 2, 3, 4 at m = 7, and 6 for [[66,6,8]] and [[78,6,10]].

We could not reproduce the paper's end-to-end qubit counts (1,904 to 3,584) because they depend on
algorithm volumes and factory allocations that the paper does not tabulate.

## Independent review

Codex reviewed the workstream twice in read-only mode. It did not edit any file. Each finding was checked
before acting on it.

First review (noise, timing, resources, statistics):

| Finding | Verified? | Action |
|---|---|---|
| Per-round idle was charged r times to the bicycle circuit and r − 1 times to the surface circuit | yes, reproduced | rule changed: only qubits used by a later entangling layer are charged; both get r − 1; regression test |
| `per_round_rate` is wrong for "any observable" block rates | yes (two-bit counterexample) | restricted by documentation to a single observable; not used on block rates |
| Stopping on a failure count invalidates the fixed-sample interval | yes | fixed-shot sampling only; stopping rule removed; test that the shot count never depends on outcomes |
| Matrix conversion merges mechanisms with equal detectors and different observables | yes on a constructed example; no such case in our circuits | `dem_logical_collisions` guard refuses such models; tests for the guard and for both circuit families |
| `R 0 0` doubled its preparation noise | yes | repeated targets in one instruction are rejected; tests |
| `max_shots` could be exceeded | yes | superseded: the plan now samples exactly the requested shots; test |
| Fractional D.5 inputs rounded inconsistently | yes | round up per instance, then multiply; test |

It also confirmed as correct: channel placement, `MR(p)` semantics, idle allocation, TICK handling,
repeat-block unrolling, the fidelity conversion, the dephasing formula, Eqs. (32)-(33), the
break-even ratio, seed reproducibility, and the absence of a dtype or overflow bug in the parity
arithmetic.

Second review (whole workstream at commit `8a296d9`, including documents and data). It regenerated
all 31 records and matched their circuit hashes, seeds, counts and intervals, matched
`analytic.json` to the code, and reproduced the decoder checks. Its findings:

| Finding | Verified? | Action |
|---|---|---|
| The merged-effects guard ignored cancellation in decomposed models (`D0 ^ D0 L0`) | yes | targets are combined by parity; regression test with its example |
| "A sound decoder returns 0" is false for a most-likely-error decoder with unequal priors; a sampled pass does not establish soundness | yes (repetition-code counterexample) | the check is now described as a comparative diagnostic everywhere; "sound decoder" wording removed |
| Fixed shots do not give Wilson its nominal coverage; figure 5 did not flag the pilot's intervals | yes | wording corrected; figure legend marks the pilot intervals as nominal |
| Overlap rule in an entangling layer depended on instruction order | yes | rule made order-independent; tests for both orders |
| Test split was 62 + 141, not 68 + 135 | yes | corrected (now 62 + 145) |
| Proportional cycle times do not show the paper left out readout | yes | reworded as a sensitivity calculation |
| "Less sensitive to idle error" is false for duration-derived idle | yes | corrected in RESULTS.md A4 |
| Dephasing-as-depolarizing arithmetic | yes | corrected in ASSUMPTIONS.md |
| The 4 ms figure was a calibration cycle, not a QEC round | accepted on its reading of the source | corrected in ASSUMPTIONS.md |
| Paper's TFIM runtime range | accepted, with a caveat about the HTML rendering | corrected in RESEARCH.md |
| No two-observable regression test for `per_round_rate` | yes | added |
| Cost figures and ad-hoc checks had no committed record | yes | decoder checks committed as a file; costs restated from recorded wall time; unrecorded items labeled as such |
| Provenance described committed, not loaded, code | yes | revision taken before sampling; loaded-source hash added |
| Re-running would append duplicate seeded trials | yes | `run_grid` refuses a non-empty file; test |
| 8/40,000 upper bound rounds to 3.9e-4 | yes | corrected |
| Missing input validation in two helpers | yes | added, with tests |
