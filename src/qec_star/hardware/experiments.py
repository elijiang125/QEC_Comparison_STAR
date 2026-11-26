"""Reproducible memory experiments under a hardware scenario.

A thin, deterministic runner for *pilot-scale* decoder-backed studies: it
samples a noisy Stim circuit with fixed seeds, decodes with BP+OSD from the
`ldpc` package, and stores everything needed to reproduce and audit a data
point. It is not a replacement for the simulation owner's pipeline.

Statistics: one shot yields one sample, "failed" if ANY logical observable is
predicted wrongly. The k observables of a block are correlated, so they are
never counted as k independent samples; per-observable counts are stored as
descriptive data only.
"""
import hashlib
import json
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from importlib.metadata import version
from math import sqrt
from pathlib import Path

import numpy as np

from ..circuits import memory_experiment
from .models import NoiseProfile
from .noise import decorate_stim_memory, noise_census
from .scenarios import REGISTRY_VERSION, SCENARIOS

# BP+OSD is what the installed `ldpc` package provides. The paper used
# relay-BP and MLE (bicycle) and MWPF (surface). BP+OSD is measurably
# inadequate for the bicycle-chain circuit (see `low_weight_fault_failures`
# and docs/udaya/VALIDATION.md), so results from it are pilot data only.
DECODER = {"name": "ldpc.BpOsdDecoder", "max_iter": 30, "bp_method": "ms",
           "ms_scaling_factor": 0.625, "osd_method": "osd0", "osd_order": 0}


def _decoder_for(circuit, decoder: dict):
    """(BP+OSD decoder, check matrix, observables matrix) for a noisy circuit."""
    from ldpc.bposd_decoder import BpOsdDecoder
    from ldpc.ckt_noise.dem_matrices import detector_error_model_to_check_matrices
    # Hyperedges are kept whole: BP+OSD works on the full check matrix.
    m = detector_error_model_to_check_matrices(
        circuit.detector_error_model(decompose_errors=False), allow_undecomposed_hyperedges=True)
    options = {k: v for k, v in decoder.items() if k != "name"}
    return (BpOsdDecoder(m.check_matrix, error_channel=list(m.priors), **options),
            m.check_matrix, m.observables_matrix)


def low_weight_fault_failures(circuit, weight: int, samples: int, *, seed: int = 0,
                              decoder: dict = None) -> int:
    """How many random weight-`weight` fault sets the decoder gets wrong.

    Picks `samples` random sets of `weight` distinct error mechanisms from the
    circuit's detector error model, decodes their syndrome, and counts wrong
    logical predictions. For a circuit of fault distance d, a sound decoder
    must return 0 for every weight <= (d-1)/2, so this is a deterministic
    acceptance test for a decoder, independent of Monte Carlo statistics.
    """
    bposd, H, L = _decoder_for(circuit, decoder or DECODER)
    rng = np.random.default_rng(seed)
    failures = 0
    for _ in range(samples):
        e = np.zeros(H.shape[1], dtype=np.uint8)
        e[rng.choice(H.shape[1], weight, replace=False)] = 1
        failures += bool(((L @ bposd.decode(((H @ e) % 2).astype(np.uint8)) + L @ e) % 2).any())
    return failures


@dataclass(frozen=True)
class Cell:
    """One point of an experiment grid."""
    experiment: str                 # e.g. "E1"
    architecture: str               # "bicycle" or "surface_reference"
    code: tuple                     # (l, m) for bicycle, (d,) for surface
    basis: str                      # "X" or "Z"
    rounds: int
    noise: NoiseProfile
    scenario_id: str = "custom"

    def circuit(self):
        """The noiseless memory circuit for this cell."""
        import stim
        if self.basis not in ("X", "Z"):
            raise ValueError("basis must be 'X' or 'Z'")
        if self.architecture == "bicycle":
            l, m = self.code
            return memory_experiment(l, m, self.rounds, basis=self.basis)
        if self.architecture == "surface_reference":
            # TEMPORARY stand-in until the team's surface-code circuit exists:
            # Stim's generated rotated memory circuit, with no built-in noise.
            (d,) = self.code
            return stim.Circuit.generated(f"surface_code:rotated_memory_{self.basis.lower()}",
                                          distance=d, rounds=self.rounds)
        raise ValueError(f"unknown architecture {self.architecture!r}")

    def noisy_circuit(self):
        return decorate_stim_memory(self.circuit(), self.noise)


def wilson_interval(failures: int, shots: int, z: float = 1.959963984540054):
    """Wilson score interval for a binomial proportion (95% by default)."""
    if shots <= 0 or not 0 <= failures <= shots:
        raise ValueError("need 0 <= failures <= shots and shots > 0")
    p = failures / shots
    denom = 1 + z*z/shots
    centre = (p + z*z/(2*shots)) / denom
    half = z * sqrt(p*(1-p)/shots + z*z/(4*shots*shots)) / denom
    # The bounds are exact at the ends; avoid rounding noise there.
    return (0.0 if failures == 0 else centre - half), (1.0 if failures == shots else centre + half)


def per_round_rate(shot_failure: float, rounds: int) -> float:
    """Per-round failure rate r with (1 - 2r)^rounds = 1 - 2P.

    Assumes independent, symmetric logical flips each round, so that an even
    number of flips cancels. Valid for P < 1/2; a derived summary, not data.
    """
    if not 0 <= shot_failure < 0.5:
        raise ValueError("shot_failure must be in [0, 0.5)")
    return (1 - (1 - 2*shot_failure) ** (1/rounds)) / 2


def _decode_chunk(circuit_text: str, decoder: dict, shots: int, seed: int):
    """Sample and decode one chunk; returns (failures, per-observable failures)."""
    import stim
    circuit = stim.Circuit(circuit_text)
    bposd, _, L = _decoder_for(circuit, decoder)
    dets, obs = circuit.compile_detector_sampler(seed=seed).sample(shots, separate_observables=True)
    wrong = np.empty_like(obs)
    for i, syndrome in enumerate(dets):
        wrong[i] = (L @ bposd.decode(syndrome.astype(np.uint8))) % 2 != obs[i]
    return int(wrong.any(axis=1).sum()), wrong.sum(axis=0).tolist()


def source_commit() -> str:
    """Current git commit, with '-dirty' if tracked files are modified."""
    try:
        root = Path(__file__).parent
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root,
                               capture_output=True, text=True, check=True).stdout.strip()
        return head + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


@dataclass(frozen=True)
class StopRule:
    """Stop once `max_failures` are seen or `max_shots` are spent.

    Chunks run in waves of `workers`; the rule is checked between waves, so
    the shot count is a deterministic function of the seeds and this rule.
    Stopping on a failure count biases the estimate slightly upward
    (order 1/max_failures); with the default 100 this is about 1%.
    """
    max_shots: int = 100_000
    max_failures: int = 100
    chunk_shots: int = 1_000
    workers: int = 8
    seed: int = 20261125


def run_cell(cell: Cell, rule: StopRule = StopRule(), *, pool=None, decoder: dict = DECODER) -> dict:
    """Run one cell to its stopping rule and return a self-describing record."""
    noisy = cell.noisy_circuit()
    text = str(noisy)
    digest = hashlib.sha256(text.encode()).hexdigest()
    # Seeds depend on the circuit and chunk index only, never on scheduling.
    seeds = np.random.SeedSequence([rule.seed, int(digest[:16], 16)])
    own_pool = pool is None
    pool = pool or ProcessPoolExecutor(rule.workers)
    start = time.time()
    chunks, shots, failures = [], 0, 0
    per_observable = np.zeros(noisy.num_observables, dtype=np.int64)
    try:
        while shots < rule.max_shots and failures < rule.max_failures:
            wave = min(rule.workers, -(-(rule.max_shots - shots) // rule.chunk_shots))
            children = [int(s.generate_state(1)[0]) for s in seeds.spawn(wave)]
            for seed, (f, per_obs) in zip(children, pool.map(
                    _decode_chunk, [text]*wave, [decoder]*wave, [rule.chunk_shots]*wave, children)):
                chunks.append({"seed": seed, "shots": rule.chunk_shots, "failures": f})
                shots += rule.chunk_shots
                failures += f
                per_observable += per_obs
    finally:
        if own_pool:
            pool.shutdown()
    low, high = wilson_interval(failures, shots)
    return {
        "experiment": cell.experiment, "architecture": cell.architecture, "code": list(cell.code),
        "basis": cell.basis, "rounds": cell.rounds, "scenario_id": cell.scenario_id,
        "registry_version": REGISTRY_VERSION, "noise": asdict(cell.noise),
        "noise_locations": dict(noise_census(noisy)),
        "num_detectors": noisy.num_detectors, "num_observables": noisy.num_observables,
        "circuit_sha256": digest, "decoder": decoder, "stop_rule": asdict(rule),
        "shots": shots, "failures": failures, "shot_failure_rate": failures / shots,
        "wilson95": [low, high], "per_observable_failures": per_observable.tolist(),
        "chunks": chunks, "runtime_seconds": round(time.time() - start, 3),
        "source_commit": source_commit(),
        "versions": {"python": platform.python_version(),
                     **{p: version(p) for p in ("stim", "ldpc", "numpy")}},
    }


def run_grid(cells, out_path, rule: StopRule = StopRule(), *, decoder: dict = DECODER,
             progress: bool = False) -> list:
    """Run cells in order, appending one JSON line per cell to out_path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with ProcessPoolExecutor(rule.workers) as pool, out_path.open("a") as fh:
        for cell in cells:
            record = run_cell(cell, rule, pool=pool, decoder=decoder)
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            records.append(record)
            if progress:
                print(cell.experiment, cell.scenario_id, cell.architecture, cell.code, cell.basis,
                      f"{record['failures']}/{record['shots']}", f"{record['runtime_seconds']}s", flush=True)
    return records


def load_records(path) -> list:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def pilot_cells() -> list:
    """The pilot grid (experiments E1-E5 of docs/udaya/RESEARCH.md).

    Rounds are 3d as in the paper. The surface cells use the temporary Stim
    reference circuit. One-factor-at-a-time and idle cells use the Z basis
    only, to keep the pilot small.
    """
    codes = [("bicycle", (3, 7), 18), ("surface_reference", (5,), 15), ("surface_reference", (7,), 21)]
    cells = []
    for sid in ("uniform/p0.0005", "paper/p1e-3", "uniform/p0.002"):
        experiment = "E1" if sid.startswith("paper") else "E2"
        for arch, code, rounds in codes + [("surface_reference", (9,), 27)]:
            for basis in "ZX":
                cells.append(Cell(experiment, arch, code, basis, rounds, SCENARIOS[sid].noise, sid))
    for sid in sorted(SCENARIOS):
        experiment = {"asym/two_qubit": "E3", "asym/measurement": "E4", "asym/idle": "E4",
                      "lit/rb87_mixed": "E4"}.get(sid.rsplit("_x", 1)[0])
        if experiment:
            cells += [Cell(experiment, arch, code, "Z", rounds, SCENARIOS[sid].noise, sid)
                      for arch, code, rounds in codes]
    for t2 in ("1500", "150"):
        for arch, code, rounds in codes:
            sid = f"idle/t2_{t2}ms/{'bicycle' if arch == 'bicycle' else 'surface'}"
            cells.append(Cell("E5", arch, code, "Z", rounds, SCENARIOS[sid].noise, sid))
    return cells
