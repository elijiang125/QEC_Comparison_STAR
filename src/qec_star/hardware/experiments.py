"""Reproducible memory experiments under a hardware scenario.

A thin, deterministic runner for small decoder-backed studies: it samples a
noisy Stim circuit with fixed seeds, decodes, and stores everything needed to
reproduce and audit a data point. It is not a replacement for the simulation
owner's pipeline.

Statistics: the number of shots is fixed before sampling, so an ordinary
binomial interval applies. One shot yields one sample, "failed" if ANY logical
observable is predicted wrongly. The k observables of a block are correlated
and are never counted as k independent samples; per-observable counts are
stored as descriptive data only.
"""
import hashlib
import json
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
from math import sqrt
from pathlib import Path

import numpy as np

from ..circuits import memory_experiment
from .models import NoiseProfile
from .noise import decorate_stim_memory, noise_census
from .scenarios import REGISTRY_VERSION, SCENARIOS

# Decoder configurations, by name. Neither is the paper's (relay-BP and MLE for
# the bicycle chain, MWPF for the surface code).
#   tesseract: Google's search-based most-likely-error decoder; optional
#              dependency (`pip install tesseract-decoder`). Passes the
#              low-weight fault check on the bicycle circuit.
#   bposd0:    BP + OSD-0 from `ldpc`, a project dependency. FAILS that check;
#              kept so the failure can be reproduced. See docs/udaya/VALIDATION.md.
DECODERS = {
    "tesseract": {"name": "tesseract", "det_beam": 5, "pqlimit": 200_000},
    "bposd0": {"name": "bposd0", "max_iter": 30, "bp_method": "ms", "ms_scaling_factor": 0.625,
               "osd_method": "osd0", "osd_order": 0},
}


def dem_logical_collisions(dem) -> int:
    """Detector patterns that different error mechanisms map to different observables.

    Decoders that merge mechanisms by detector pattern alone (`ldpc`'s matrix
    conversion, Tesseract's `merge_errors`) keep only one logical effect per
    pattern, which silently discards the other. Zero means merging is safe.
    """
    effects = {}
    for op in dem.flattened():
        if op.type == "error":
            targets = op.targets_copy()
            dets = frozenset(t.val for t in targets if t.is_relative_detector_id())
            obs = frozenset(t.val for t in targets if t.is_logical_observable_id())
            effects.setdefault(dets, set()).add(obs)
    return sum(len(v) > 1 for v in effects.values())


def predictor(circuit, decoder: dict):
    """A function mapping one shot's detection events to predicted observable flips."""
    dem = circuit.detector_error_model(decompose_errors=False)
    if dem_logical_collisions(dem):
        raise ValueError("detector error model has mechanisms with equal detectors but different "
                         "observables; these decoders would merge them")
    options = {k: v for k, v in decoder.items() if k != "name"}
    n_obs = dem.num_observables
    if decoder["name"] == "tesseract":
        try:
            from tesseract_decoder import tesseract
        except ImportError as e:
            raise ImportError("install the optional decoder: pip install tesseract-decoder") from e
        search = tesseract.TesseractDecoder(tesseract.TesseractConfig(dem, **options))
        return lambda dets: np.asarray(search.decode(dets.astype(bool)), dtype=np.uint8)[:n_obs]
    if decoder["name"] == "bposd0":
        from ldpc.bposd_decoder import BpOsdDecoder
        from ldpc.ckt_noise.dem_matrices import detector_error_model_to_check_matrices
        # Hyperedges are kept whole: BP+OSD works on the full check matrix.
        m = detector_error_model_to_check_matrices(dem, allow_undecomposed_hyperedges=True)
        bposd = BpOsdDecoder(m.check_matrix, error_channel=list(m.priors), **options)
        return lambda dets: np.asarray((m.observables_matrix @ bposd.decode(dets.astype(np.uint8))) % 2,
                                       dtype=np.uint8)
    raise ValueError(f"unknown decoder {decoder['name']!r}")


def low_weight_fault_failures(circuit, weight: int, samples: int, *, seed: int = 0,
                              decoder: dict = DECODERS["tesseract"]) -> int:
    """How many random weight-`weight` fault sets the decoder gets wrong.

    Picks `samples` random sets of `weight` distinct error mechanisms from the
    circuit's detector error model, decodes their combined detection events,
    and counts wrong logical predictions. For a circuit of fault distance d, a
    sound decoder returns 0 for every weight <= (d-1)/2. This is an acceptance
    test for a decoder that does not depend on Monte Carlo statistics. It
    samples fault sets, so passing it is necessary, not sufficient.
    """
    dem = circuit.detector_error_model(decompose_errors=False)
    errors = [op.targets_copy() for op in dem.flattened() if op.type == "error"]
    predict = predictor(circuit, decoder)
    rng = np.random.default_rng(seed)
    failures = 0
    for _ in range(samples):
        dets = np.zeros(dem.num_detectors, dtype=np.uint8)
        obs = np.zeros(dem.num_observables, dtype=np.uint8)
        for i in rng.choice(len(errors), weight, replace=False):
            for t in errors[i]:
                if t.is_relative_detector_id():
                    dets[t.val] ^= 1
                elif t.is_logical_observable_id():
                    obs[t.val] ^= 1
        failures += bool((predict(dets) != obs).any())
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
    """Wilson score interval for a binomial proportion (95% by default).

    Valid when `shots` was fixed before sampling. If sampling stopped because
    a failure count was reached, the estimate is biased and this interval
    under-covers; label such data accordingly.
    """
    if shots <= 0 or not 0 <= failures <= shots:
        raise ValueError("need 0 <= failures <= shots and shots > 0")
    p = failures / shots
    denom = 1 + z*z/shots
    centre = (p + z*z/(2*shots)) / denom
    half = z * sqrt(p*(1-p)/shots + z*z/(4*shots*shots)) / denom
    # The bounds are exact at the ends; avoid rounding noise there.
    return (0.0 if failures == 0 else centre - half), (1.0 if failures == shots else centre + half)


def per_round_rate(shot_failure: float, rounds: int) -> float:
    """Per-round flip rate r of ONE logical observable: (1 - 2r)^rounds = 1 - 2P.

    Assumes independent, symmetric flips of that observable each round, so an
    even number of flips cancels. Valid for P < 1/2. Do not apply it to the
    "any observable failed" block rate, which is not a single parity bit.
    """
    if not 0 <= shot_failure < 0.5:
        raise ValueError("shot_failure must be in [0, 0.5)")
    return (1 - (1 - 2*shot_failure) ** (1/rounds)) / 2


def _decode_chunk(circuit_text: str, decoder: dict, shots: int, seed: int):
    """Sample and decode one chunk; returns (failures, per-observable failures)."""
    import stim
    circuit = stim.Circuit(circuit_text)
    predict = predictor(circuit, decoder)
    dets, obs = circuit.compile_detector_sampler(seed=seed).sample(shots, separate_observables=True)
    wrong = np.array([predict(d) != o for d, o in zip(dets, obs)])
    return int(wrong.any(axis=1).sum()), wrong.sum(axis=0).tolist()


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=Path(__file__).parent, capture_output=True,
                          text=True, check=True).stdout.strip()


def code_revision() -> dict:
    """Identify the simulation code, independently of documentation commits.

    source_tree is git's hash of the committed `src/qec_star` directory: it
    changes only when the package changes, so results from different commits
    with the same source_tree were produced by identical code. `dirty` is true
    if the package has uncommitted changes (then source_tree does not describe
    what ran).
    """
    try:
        package = Path(__file__).parent.parent
        prefix = _git("rev-parse", "--show-prefix").removesuffix("hardware/").rstrip("/")
        return {"commit": _git("rev-parse", "HEAD"), "source_tree": _git("rev-parse", f"HEAD:{prefix}"),
                "dirty": bool(_git("status", "--porcelain", "--", str(package)))}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unknown", "source_tree": "unknown", "dirty": None}


def _versions() -> dict:
    out = {"python": platform.python_version()}
    for package in ("stim", "ldpc", "numpy", "scipy", "tesseract-decoder"):
        try:
            out[package] = version(package)
        except PackageNotFoundError:
            out[package] = None
    return out


@dataclass(frozen=True)
class SamplingPlan:
    """A fixed number of shots, split into chunks with their own seeds.

    The shot count never depends on the outcomes, and the seeds depend only
    on `seed`, the circuit and the chunk index, so a result is reproducible
    on any number of workers.
    """
    shots: int = 20_000
    chunk_shots: int = 100
    workers: int = 8
    seed: int = 20261125

    def __post_init__(self):
        for name in ("shots", "chunk_shots", "workers"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")

    def chunk_sizes(self) -> list:
        full, rest = divmod(self.shots, self.chunk_shots)
        return [self.chunk_shots] * full + ([rest] if rest else [])


def run_cell(cell: Cell, plan: SamplingPlan = SamplingPlan(), *, pool=None,
             decoder: dict = DECODERS["tesseract"]) -> dict:
    """Sample exactly plan.shots shots of one cell and return a self-describing record."""
    noisy = cell.noisy_circuit()
    text = str(noisy)
    digest = hashlib.sha256(text.encode()).hexdigest()
    sizes = plan.chunk_sizes()
    seeds = [int(s.generate_state(1)[0])
             for s in np.random.SeedSequence([plan.seed, int(digest[:16], 16)]).spawn(len(sizes))]
    own_pool = pool is None
    pool = pool or ProcessPoolExecutor(plan.workers)
    start = time.time()
    try:
        results = list(pool.map(_decode_chunk, [text]*len(sizes), [decoder]*len(sizes), sizes, seeds))
    finally:
        if own_pool:
            pool.shutdown()
    failures = sum(f for f, _ in results)
    low, high = wilson_interval(failures, plan.shots)
    return {
        "experiment": cell.experiment, "architecture": cell.architecture, "code": list(cell.code),
        "basis": cell.basis, "rounds": cell.rounds, "scenario_id": cell.scenario_id,
        "registry_version": REGISTRY_VERSION, "noise": asdict(cell.noise),
        "noise_locations": dict(noise_census(noisy)),
        "num_detectors": noisy.num_detectors, "num_observables": noisy.num_observables,
        "circuit_sha256": digest, "decoder": decoder, "design": "fixed_shots",
        "sampling_plan": asdict(plan),
        "shots": plan.shots, "failures": failures, "shot_failure_rate": failures / plan.shots,
        "wilson95": [low, high],
        "per_observable_failures": np.sum([per for _, per in results], axis=0).tolist(),
        "chunks": [{"seed": seed, "shots": n, "failures": f}
                   for seed, n, (f, _) in zip(seeds, sizes, results)],
        "runtime_seconds": round(time.time() - start, 3),
        "code_revision": code_revision(), "versions": _versions(),
    }


def run_grid(cells, out_path, plan: SamplingPlan = SamplingPlan(), *,
             decoder: dict = DECODERS["tesseract"], shots_for=None, progress: bool = False) -> list:
    """Run cells in order, appending one JSON line per cell to out_path.

    shots_for(cell) may return a shot count for that cell (fixed in advance,
    e.g. fewer shots for expensive circuits); otherwise plan.shots is used.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with ProcessPoolExecutor(plan.workers) as pool, out_path.open("a") as fh:
        for cell in cells:
            shots = shots_for(cell) if shots_for else plan.shots
            cell_plan = SamplingPlan(shots, plan.chunk_shots, plan.workers, plan.seed)
            record = run_cell(cell, cell_plan, pool=pool, decoder=decoder)
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            records.append(record)
            if progress:
                print(cell.experiment, cell.scenario_id, cell.architecture, cell.code, cell.basis,
                      f"{record['failures']}/{record['shots']}", f"{record['runtime_seconds']}s", flush=True)
    return records


def load_records(path) -> list:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def validation_cells() -> list:
    """A small grid that a laptop can decode soundly in under an hour.

    E1: the paper baseline (p = 1e-3, r = 3d rounds, both bases).
    E2: one elevated uniform noise level (p = 2e-3, Z basis).
    Channel-by-channel sweeps (E3-E5) need far more shots than this at the
    failure rates a sound decoder gives, and are left to the production pipeline.
    """
    codes = [("bicycle", (3, 7), 18), ("surface_reference", (5,), 15),
             ("surface_reference", (7,), 21), ("surface_reference", (9,), 27)]
    cells = [Cell("E1", arch, code, basis, rounds, SCENARIOS["paper/p1e-3"].noise, "paper/p1e-3")
             for arch, code, rounds in codes for basis in "ZX"]
    cells += [Cell("E2", arch, code, "Z", rounds, SCENARIOS["uniform/p0.002"].noise, "uniform/p0.002")
              for arch, code, rounds in codes]
    return cells


def validation_shots(cell: Cell) -> int:
    """Shots per cell, fixed in advance from measured decoding cost (not from outcomes)."""
    if cell.architecture != "bicycle":
        return 40_000
    return 6_000 if cell.noise.two_qubit <= 1e-3 else 2_400
