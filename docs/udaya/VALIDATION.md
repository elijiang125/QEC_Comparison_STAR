# Validation record

What was checked, how, and what the outcome was. Commands assume the repository root and an
environment installed with `python -m pip install -e '.[dev]'` (Python 3.12, Stim 1.16, ldpc 2.4.1).

## Test suite

`python -m pytest -q` runs 186 tests: the 68 that were on `epa-branch` (unchanged) and 118 for this
workstream. All pass. Nothing is skipped for a missing dependency; Stim is imported directly.

| File | What it establishes |
|---|---|
| `tests/test_udaya_noise.py` | channel placement on a hand-written circuit; exact noise-location counts on both real circuits; zero-noise identity; record, detector and observable preservation in X and Z bases; exact unrolling of repeat blocks; explicit rejection of noisy, unsupported or ambiguous input; two sampled rates against closed-form values |
| `tests/test_udaya_hardware.py` | probability and timing validation; fidelity conversion; cycle formula by hand; block footprints against the paper's Table 4; whole-block rounding; break-even ratio; Eqs. (32)-(33) by hand; latency versus throughput; the CLI |
| `tests/test_udaya_scenarios.py` | the reference scenario equals the paper's values and cannot be mutated; every scenario labels every parameter; one-factor scenarios change exactly one channel |
| `tests/test_udaya_experiments.py` | Wilson interval against known values; determinism under fixed seeds; disjoint seeds for different circuits; stopping rule; record contents; pilot grid shape |

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

## Decoder check (important)

The repository's dependencies provide BP+OSD (`ldpc`). It is not adequate for these circuits.

`experiments.low_weight_fault_failures` draws random sets of w error mechanisms from the detector
error model, decodes their syndrome and counts wrong logical predictions. A circuit with fault
distance 5 lets a sound decoder correct every set of 1 or 2 faults.

Bicycle [[42,6,6]], 6 rounds, Z basis, p = 1e-3 (252 detectors, 13,902 mechanisms), seed 0:

| Decoder settings | w = 1 | w = 2 | w = 3 | time per decode |
|---|---|---|---|---|
| min-sum BP, 30 iterations, OSD-0 (pilot setting) | 1 / 300 wrong | 11 / 300 | 17 / 200 | ~20 ms |
| product-sum BP, 200 iterations, OSD-CS order 10 | 0 / 300 | 2 / 300 | 0 / 40 | ~200 ms |

The same pilot setting gets 1 of 200 single faults wrong on Stim's distance-3 surface code, so the
weakness is not specific to the bicycle chain.

Consequences:

- Logical error rates from the pilot are **upper bounds set by the decoder**, not properties of the codes.
- At p = 1e-3 the bicycle memory fails in a few percent of shots with BP+OSD-0. The paper reports
  logical error scales near 1e-7 per logical qubit with relay-BP and MLE. We have not reproduced the
  paper's logical error rates and do not claim to.
- The failure rate falls more slowly with p than the p³ expected of a distance-5 circuit, as it
  must if single and double faults are sometimes miscorrected.
- A decoder for the team's pipeline should return zero failures at w = 1 and w = 2 in this test
  before its Monte Carlo numbers are trusted. The test takes under a minute.

To reproduce:

```python
from qec_star.hardware.experiments import Cell, low_weight_fault_failures
from qec_star.hardware.models import NoiseProfile
circuit = Cell("check", "bicycle", (3, 7), "Z", 6, NoiseProfile.paper()).noisy_circuit()
print([low_weight_fault_failures(circuit, w, 300) for w in (1, 2)])
```

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

A read-only review by Codex was requested on the noise, timing, resource and statistics code before
the results were written up. Its findings and what was done about each are listed in section
"Review findings" below.
