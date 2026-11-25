"""Print an auditable memory-footprint comparison (NOT end-to-end STAR)."""
import argparse
import json
from dataclasses import asdict
from .models import NoiseProfile, SURFACE_CYCLE_MS, BICYCLE_CYCLE_MS
from .resources import surface_block, bicycle_block, memory_footprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logical-count", type=int, default=64)
    parser.add_argument("--surface-distance", type=int, default=9)
    parser.add_argument("--bicycle-l", type=int, default=4)
    parser.add_argument("--p", type=float, default=0.001)
    args = parser.parse_args()
    rows = []
    for name, block, ms in (("surface", surface_block(args.surface_distance), SURFACE_CYCLE_MS),
                            ("bicycle", bicycle_block(args.bicycle_l), BICYCLE_CYCLE_MS)):
        rows.append({"architecture": name, **asdict(block), "cycle_ms": ms,
                     "physical_memory_qubits": memory_footprint(args.logical_count, block)})
    print(json.dumps({"scope": "idealized memory only; no equal-error or end-to-end claim",
                      "logical_count": args.logical_count, "noise": asdict(NoiseProfile.paper(args.p)),
                      "architectures": rows}, indent=2))


if __name__ == "__main__":
    main()
