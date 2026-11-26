# Hardware and noise modeling workstream (Udaya)

Branch `udaya`, based on `epa-branch` at `0dc22d9`, with the surface-code baseline merged from
`origin/harman` at `f377d22`. Primary paper:
[Ismail et al., arXiv:2606.25011v1](https://arxiv.org/html/2606.25011v1).

**Question.** Does the bicycle-chain qLDPC STAR architecture keep its space-time advantage over
surface-code STAR once hardware overhead and non-uniform noise are considered?

**Where things stand.** The noise model, timing model, scenario registry, resource accounting and
experiment runner are implemented and tested. The analytic results (footprints, fault budgets,
timing and break-even) are validated. The sampled results are provisional: a small fixed-shot run
with the Tesseract decoder gives upper bounds on the logical failure rate, not estimates, and the paper's
logical error rates are not reproduced. Details are in [RESULTS.md](RESULTS.md) and
[VALIDATION.md](VALIDATION.md); what is needed from teammates is in [HANDOFF.md](HANDOFF.md).

## Scope

This workstream owns hardware assumptions, noise channels, cycle-time and atom accounting, and the
hardware sensitivity analysis. It consumes the QEC team's bicycle-chain circuit and the surface-code
owner's surface circuit, and does not build parity-check matrices, syndrome schedules, decoders,
the production simulations, the Hamiltonian compilation, or the non-Clifford simulation.

## Quick start

```sh
python3.12 -m venv .venv && source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pip install tesseract-decoder               # optional decoder (2 tests and `validate` need it)
python -m pytest -q                                   # 311 tests (add -m slow for one more)
python -m qec_star.hardware --logical-count 64        # memory footprint of both architectures
python -m qec_star.hardware scenarios                 # the scenario registry, as JSON
python -m qec_star.hardware figures --out docs/udaya/figures
python -m qec_star.hardware validate --grid surface --out NEW_FILE.jsonl --workers 12
```

`validate` takes about an hour on 12 cores and needs a new output file (it refuses to add to
existing results). The other commands
take seconds. The notebook `docs/udaya/hardware_models.ipynb` walks through the models with
editable parameters; it needs `jupyter`.

## Layout

| Path | Contents |
|---|---|
| `src/qec_star/hardware/models.py` | `NoiseProfile`, `CycleTiming`, fidelity and dephasing conversions |
| `src/qec_star/hardware/noise.py` | `decorate_stim_memory`: adds noise to a noiseless Stim circuit; `noise_census` |
| `src/qec_star/hardware/scenarios.py` | versioned registry of noise and timing scenarios with provenance |
| `src/qec_star/hardware/resources.py` | exact block accounting; the paper's Eqs. (32)-(33) |
| `src/qec_star/hardware/experiments.py` | fixed-shot runner, statistics, provenance, low-weight fault check |
| `src/qec_star/hardware/figures.py` | figures from recorded data |
| `tests/test_udaya_*.py` | 213 tests, 68 of them on the team's surface circuit |
| `src/qec_star/surface.py`, `tests/test_surface.py` | the surface-code owner's baseline, unchanged |
| `results/udaya/` | raw sampling records and a README describing them |
| `docs/udaya/figures/` | six figures and `analytic.json` |
| `docs/udaya/hardware_models.ipynb` | executed demonstration notebook |

## Documents

| File | Read it for |
|---|---|
| [RESULTS.md](RESULTS.md) | findings, figures, and methodology and limitations text for the paper |
| [RESEARCH.md](RESEARCH.md) | what the paper and the hardware literature say; the experiment matrix |
| [ASSUMPTIONS.md](ASSUMPTIONS.md) | every parameter with its source and evidence class |
| [VALIDATION.md](VALIDATION.md) | what was tested and how; the decoder check |
| [INTEGRATION.md](INTEGRATION.md) | interfaces, circuit requirements, dependencies on teammates |
| [HANDOFF.md](HANDOFF.md) | what each teammate can use now and what is needed from them |
| [ROADMAP.md](ROADMAP.md) | status, remaining work and acceptance criteria |

## Working rules

- The paper baseline (`paper/p1e-3`) is never edited. Anything else is a separately named scenario.
- No number enters the code without an entry in ASSUMPTIONS.md.
- Results are stored with seeds, configuration, commit and decoder settings. Nothing is plotted that is not in a recorded file.
- Teammates' modules and tests are not modified. Problems found in them are reported with a minimal reproduction.
- No pull request until the team confirms the integration branch.
