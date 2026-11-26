"""Command line for the hardware workstream.

    python -m qec_star.hardware [memory] --logical-count 64
    python -m qec_star.hardware scenarios
    python -m qec_star.hardware validate --out results/udaya/validation_tesseract.jsonl
    python -m qec_star.hardware figures --out docs/udaya/figures
"""
import argparse
import json
import sys
from dataclasses import asdict

from .experiments import DECODERS, SamplingPlan, run_grid, validation_cells, validation_shots
from .models import BICYCLE_CYCLE_MS, SURFACE_CYCLE_MS, NoiseProfile
from .resources import allocate, bicycle_block, memory_spacetime_ratio, surface_block
from .scenarios import SCENARIOS


def memory_report(args) -> dict:
    """Idealized memory footprint; NOT an end-to-end STAR comparison."""
    blocks = {"surface": surface_block(args.surface_distance), "bicycle": bicycle_block(args.bicycle_l)}
    cycle = {"surface": SURFACE_CYCLE_MS, "bicycle": BICYCLE_CYCLE_MS}
    rows = []
    for name, block in blocks.items():
        a = allocate(args.logical_count, block)
        rows.append({"architecture": name, **asdict(block), "cycle_ms": cycle[name], "blocks": a.blocks,
                     "unused_logical": a.unused_logical, "physical_memory_qubits": a.physical})
    return {"scope": "idealized memory only; no equal-error or end-to-end claim",
            "logical_count": args.logical_count, "noise": asdict(NoiseProfile.paper(args.p)),
            "architectures": rows,
            "surface_over_bicycle_qubits": rows[0]["physical_memory_qubits"] / rows[1]["physical_memory_qubits"],
            "surface_over_bicycle_qubit_seconds_per_round": memory_spacetime_ratio(
                args.logical_count, blocks["surface"], blocks["bicycle"], SURFACE_CYCLE_MS, BICYCLE_CYCLE_MS)}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv.insert(0, "memory")
    parser = argparse.ArgumentParser(prog="python -m qec_star.hardware", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    memory = sub.add_parser("memory", help="memory footprint of both architectures")
    memory.add_argument("--logical-count", type=int, default=64)
    memory.add_argument("--surface-distance", type=int, default=9)
    memory.add_argument("--bicycle-l", type=int, default=4)
    memory.add_argument("--p", type=float, default=0.001)
    sub.add_parser("scenarios", help="print the scenario registry as JSON")
    validate = sub.add_parser("validate", help="run the fixed-shot validation grid (under an hour)")
    validate.add_argument("--out", required=True)
    validate.add_argument("--decoder", choices=sorted(DECODERS), default="tesseract")
    validate.add_argument("--workers", type=int, default=8)
    figures = sub.add_parser("figures", help="regenerate figures from recorded data")
    figures.add_argument("--results", default="results/udaya")
    figures.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    if args.command == "memory":
        print(json.dumps(memory_report(args), indent=2))
    elif args.command == "scenarios":
        print(json.dumps([s.to_dict() for s in SCENARIOS.values()], indent=2))
    elif args.command == "validate":
        run_grid(validation_cells(), args.out, SamplingPlan(workers=args.workers),
                 decoder=DECODERS[args.decoder], shots_for=validation_shots, progress=True)
    else:
        from .figures import make_figures
        for path in make_figures(args.results, args.out):
            print(path)


if __name__ == "__main__":
    main()
