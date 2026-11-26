# Integration: what the hardware layer needs and provides

`qec_star.hardware` sits between the QEC circuits and the simulation pipeline. It never builds or
modifies a QEC circuit; it adds noise to one and accounts for time and atoms.

## Adding noise to a circuit

```python
from qec_star.circuits import memory_experiment
from qec_star.hardware import SCENARIOS
from qec_star.hardware.noise import decorate_stim_memory, noise_census

clean = memory_experiment(3, 7, rounds=18, basis="Z")        # QEC team's noiseless circuit
scenario = SCENARIOS["paper/p1e-3"]                          # or any other registry entry
noisy = decorate_stim_memory(clean, scenario.noise)           # flat stim.Circuit
dem = noisy.detector_error_model(decompose_errors=False)      # hand to the decoder
print(noise_census(noisy))                                    # {'two_qubit': 6048, 'prep': 798, ...}
```

Guarantees, all covered by tests:

- measurement records, detectors and observables are identical to the input;
- `noisy.without_noise() == clean.flattened()`;
- with an all-zero profile the output equals `clean.flattened()`;
- every inserted channel is tagged with its origin (`prep`, `one_qubit`, `two_qubit`, `idle`, `cycle_idle`).

## What a circuit must look like

| Requirement | Why |
|---|---|
| No noise instructions and no measurement arguments | prevents noise being applied twice |
| `TICK` between layers | a layer is what lies between two TICKs; idle noise is defined per layer |
| In a layer with two-qubit gates, each qubit used at most once | otherwise "idle during the layer" is undefined |
| Two-qubit gates and measurements in different layers | keeps `idle` and `cycle_idle` separate |
| Gates from: `R RX RY`, `M MX MY`, `MR MRX MRY`, `H S S_DAG X Y Z H_XY H_YZ`, `CX CY CZ SWAP` | anything else raises `ValueError` |
| No feedback (`CX rec[-1] 3`) and no inverted targets | not modeled |

`REPEAT` blocks are accepted and unrolled. Qubits that no instruction touches are not charged idle
noise; pass `active_qubits=` to add spectator atoms explicitly.

The team's `memory_experiment` and Stim's generated surface-code circuits both satisfy this as they are.

## Dependencies on teammates

| I need | From | Status | Used for |
|---|---|---|---|
| Noiseless bicycle-chain memory circuit | QEC (Epameinondas) | available (`circuits.py`) | all bicycle results |
| Noiseless surface-code memory circuit with the same conventions | surface baseline (Harman) | **missing**; Stim's generated circuit is a labeled stand-in (`surface_reference`) | all surface results |
| A decoder that passes the low-weight fault check on the bicycle circuit | simulation owner | **missing**; BP+OSD from `ldpc` fails it (see VALIDATION.md) | any logical error rate worth quoting |
| Transversal-gate and magic-state circuits | QEC | missing | noise beyond memory |
| Logical qubit count, V_RZ, V_Cliff, factory count and size, error budget | Hamiltonian / algorithm owner | missing | end-to-end resources with Eqs. (32)-(33) |
| Logical error rate per round at matched conditions | simulation owner | missing | a fair space-time comparison |

## What I provide

| For | Object | Notes |
|---|---|---|
| Simulation owner | `decorate_stim_memory`, `SCENARIOS`, `noise_census`, `expected_faults` | scenario id and registry version go into every record |
| Simulation owner | `experiments.low_weight_fault_failures` | deterministic acceptance test for a decoder |
| Simulation owner | `experiments.run_cell` / `run_grid` | pilot-scale runner with seeds and provenance; replaceable by the real pipeline |
| Algorithm owner | `star_resources`, `star_data_qubits` | paper Eqs. (32)-(33); you supply volumes and factories |
| Everyone | `allocate`, `memory_footprint`, `CycleTiming` | exact atom counts and cycle-time budgets |

## Record format

`run_grid` appends one JSON object per line. Fields: `experiment`, `architecture`, `code`, `basis`,
`rounds`, `scenario_id`, `registry_version`, `noise`, `noise_locations`, `num_detectors`,
`num_observables`, `circuit_sha256`, `decoder`, `stop_rule`, `shots`, `failures`,
`shot_failure_rate`, `wilson95`, `per_observable_failures`, `chunks` (seed, shots, failures each),
`runtime_seconds`, `source_commit`, `versions`.

A shot fails if any logical observable is predicted wrongly. `per_observable_failures` is descriptive
only: the observables of one block are correlated and are not independent samples.

## Open questions for the team

1. Which branch is the integration target? `udaya` is based on `epa-branch` at `0dc22d9`.
2. Will the surface-code circuit prepare and measure X ancillas directly (`RX`/`MX`) or through H gates? This changes its noise count by 80 locations per round at d = 9.
3. Which decoder will the simulation pipeline use for the bicycle code (relay-BP, BP+OSD with stronger settings, an MLE solver)?
4. Should the comparison keep the paper's pairing (surface d = 9 against bicycle d = 6), or match logical error rates first?
