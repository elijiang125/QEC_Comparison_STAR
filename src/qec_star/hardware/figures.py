"""Figures for the hardware workstream, generated only from recorded data.

Analytic figures (1-3) come from exact counting and the timing model; their
plotted numbers are also written to `analytic.json`. Pilot figures (4-5) are
drawn from the JSON-lines records of `experiments.run_grid` and are labeled
as decoder-limited pilot data.
"""
import json
from math import exp, log, sqrt
from pathlib import Path

from .experiments import Cell, load_records
from .models import BICYCLE_CYCLE_MS, SURFACE_CYCLE_MS, CycleTiming, NoiseProfile
from .noise import noise_census
from .resources import bicycle_block, break_even_cycle_ratio, memory_footprint, surface_block

INK, MUTED, GRID = "#191919", "#666666", "#e6e6e6"
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac"
CHANNEL_COLOURS = {"two_qubit": BLUE, "measurement": ORANGE, "prep": AQUA,
                   "one_qubit": YELLOW, "idle": MAGENTA}
CODE_STYLE = {("bicycle", (3, 7)): ("bicycle [[42,6,6]]", ORANGE, "o"),
              ("surface_reference", (5,)): ("surface d=5 (Stim reference)", BLUE, "s"),
              ("surface_reference", (7,)): ("surface d=7 (Stim reference)", AQUA, "^"),
              ("surface_reference", (9,)): ("surface d=9 (Stim reference)", "#6a4ce2", "D")}


def _axes(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.set_title(title, color=INK, loc="left", fontsize=10)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def per_round_fault_locations(architecture: str, code: tuple) -> dict:
    """Noise locations added by one more syndrome round, per channel (exact)."""
    probe = NoiseProfile(.5, .5, .5, .5, .5)
    counts = [noise_census(Cell("fig", architecture, code, "Z", r, probe).noisy_circuit()) for r in (3, 4)]
    return {c: counts[1][c] - counts[0][c] for c in CHANNEL_COLOURS}


def analytic_tables() -> dict:
    """Every number behind figures 1-3."""
    surface, b6, b8 = surface_block(9), bicycle_block(3), bicycle_block(4)
    counts = list(range(1, 129))
    budget = {}
    for label, arch, code, block, cycle in (("surface d=9", "surface_reference", (9,), surface, SURFACE_CYCLE_MS),
                                            ("bicycle [[56,8,6]]", "bicycle", (4, 7), b8, BICYCLE_CYCLE_MS)):
        locations = per_round_fault_locations(arch, code)
        budget[label] = {"locations_per_round": locations, "logical": block.logical, "cycle_ms": cycle,
                         "per_logical_per_round": {c: n / block.logical for c, n in locations.items()}}
    fixed = [0, 250, 500, 1000, 2000, 4000]
    return {
        "memory_footprint": {"logical_count": counts,
                             "surface d=9": [memory_footprint(n, surface) for n in counts],
                             "bicycle [[42,6,6]]": [memory_footprint(n, b6) for n in counts],
                             "bicycle [[56,8,6]]": [memory_footprint(n, b8) for n in counts]},
        "fault_budget": budget,
        "cycle_ratio_vs_fixed_overhead_us": {
            "fixed_us": fixed,
            "ratio": [CycleTiming(8, 0, 250, f).cycle_us / CycleTiming(4, 0, 250, f).cycle_us for f in fixed]},
        "memory_break_even_cycle_ratio": {str(n): break_even_cycle_ratio(n, surface, b8)
                                          for n in (9, 64)},
    }


def _fig_memory(plt, t, out):
    fig, ax = plt.subplots(figsize=(6.4, 4))
    m = t["memory_footprint"]
    for label, colour in (("surface d=9", BLUE), ("bicycle [[42,6,6]]", AQUA), ("bicycle [[56,8,6]]", ORANGE)):
        ax.step(m["logical_count"], m[label], where="post", color=colour, linewidth=2, label=label)
    ax.set_yscale("log")
    _axes(ax, "logical qubits stored", "physical qubits (data + check ancillas)",
          "Memory footprint with whole-block allocation (exact count; no factories or spares)")
    ax.legend(frameon=False, labelcolor=INK)
    return _save(fig, out / "fig1_memory_footprint.png")


def _fig_budget(plt, t, out):
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    labels = list(t["fault_budget"])
    left = [0.0] * len(labels)
    for channel, colour in CHANNEL_COLOURS.items():
        values = [t["fault_budget"][l]["per_logical_per_round"][channel] for l in labels]
        ax.barh(labels, values, left=left, color=colour, edgecolor="white", linewidth=2, height=0.5,
                label=channel.replace("_", "-"))
        left = [a + b for a, b in zip(left, values)]
    for y, total in enumerate(left):
        ax.text(total + 8, y, f"{total:g}", va="center", color=INK, fontsize=9)
    _axes(ax, "noise locations per logical qubit per syndrome round", "",
          "Where faults can occur (exact count; multiply by p for expected faults)")
    ax.set_xlim(0, max(left) * 1.12)
    ax.legend(frameon=False, ncols=5, loc="upper center", bbox_to_anchor=(0.5, -0.32), labelcolor=INK,
              fontsize=8)
    return _save(fig, out / "fig2_fault_budget.png")


def _fig_timing(plt, t, out):
    fig, (left, right) = plt.subplots(1, 2, figsize=(9.6, 3.8))
    c = t["cycle_ratio_vs_fixed_overhead_us"]
    left.plot([f / 1000 for f in c["fixed_us"]], c["ratio"], color=ORANGE, linewidth=2, marker="o", markersize=6)
    left.annotate("paper: 2.0 (no fixed term)", (0, 2), (0.35, 1.93), color=INK, fontsize=8)
    left.set_ylim(1, 2.1)
    _axes(left, "fixed time per round, e.g. readout + reset (ms)", "bicycle / surface cycle time",
          "Cycle ratio, with 0.25 ms per entangling layer")
    ratios = [r / 4 for r in range(4, 65)]
    for n, colour in (("9", AQUA), ("64", ORANGE)):
        star = t["memory_break_even_cycle_ratio"][n]
        right.plot(ratios, [star / r for r in ratios], color=colour, linewidth=2,
                   label=f"{n} logical qubits (break-even at {star:g})")
    right.axhline(1, color=INK, linewidth=1)
    right.axvline(2, color=MUTED, linewidth=1, linestyle=":")
    right.annotate("paper cycle ratio", (2, 9), (2.4, 9), color=MUTED, fontsize=8)
    right.set_yscale("log")
    _axes(right, "bicycle / surface cycle time", "surface / bicycle qubit-seconds per round",
          "Memory space-time ratio (above 1: bicycle cheaper)")
    right.legend(frameon=False, labelcolor=INK, fontsize=8)
    return _save(fig, out / "fig3_timing_sensitivity.png")


def _style(record):
    return CODE_STYLE[(record["architecture"], tuple(record["code"]))]


def _fig_pilot_uniform(plt, records, out):
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4), sharey=True)
    for ax, basis in zip(axes, "ZX"):
        rows = [r for r in records if r["experiment"] in ("E1", "E2") and r["basis"] == basis]
        for key in CODE_STYLE:
            series = sorted((r for r in rows if (r["architecture"], tuple(r["code"])) == key),
                            key=lambda r: r["noise"]["two_qubit"])
            if not series:
                continue
            label, colour, marker = CODE_STYLE[key]
            seen = [r for r in series if r["failures"]]
            ax.errorbar([r["noise"]["two_qubit"] for r in seen], [r["shot_failure_rate"] for r in seen],
                        yerr=[[r["shot_failure_rate"] - r["wilson95"][0] for r in seen],
                              [r["wilson95"][1] - r["shot_failure_rate"] for r in seen]],
                        color=colour, marker=marker, markersize=6, linewidth=2, capsize=3, label=label)
            none = [r for r in series if not r["failures"]]     # zero failures: plot the 95% upper bound
            ax.scatter([r["noise"]["two_qubit"] for r in none], [r["wilson95"][1] for r in none],
                       marker="v", facecolors="none", edgecolors=colour, s=45)
        ax.set_xscale("log")
        ax.set_yscale("log")
        _axes(ax, "uniform physical error probability p", "failure probability per shot (3d rounds)" if basis == "Z" else "",
              f"{basis}-basis memory")
    axes[0].legend(frameon=False, labelcolor=INK, fontsize=8)
    fig.suptitle("PILOT, decoder-limited (BP+OSD-0): any-observable failure per shot, 95% Wilson intervals; "
                 "hollow triangles are upper bounds with zero failures", fontsize=8, color=MUTED, x=0.01, ha="left")
    return _save(fig, out / "fig4_pilot_uniform_noise.png")


def _fig_pilot_sensitivity(plt, records, out):
    base = {(r["architecture"], tuple(r["code"])): r for r in records
            if r["scenario_id"] == "paper/p1e-3" and r["basis"] == "Z"}
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True)
    for ax, channel in zip(axes, ("two_qubit", "measurement", "idle")):
        for key, b in base.items():
            if not b["failures"]:
                continue
            label, colour, marker = CODE_STYLE[key]
            points = [(1.0, 1.0, 1.0, 1.0)]
            for r in records:
                if (r["scenario_id"].startswith(f"asym/{channel}_x") and r["failures"]
                        and (r["architecture"], tuple(r["code"])) == key):
                    ratio = r["shot_failure_rate"] / b["shot_failure_rate"]
                    # 95% interval of a ratio of two binomial proportions (log-normal approximation)
                    se = sqrt(1/r["failures"] - 1/r["shots"] + 1/b["failures"] - 1/b["shots"])
                    points.append((float(r["scenario_id"].rsplit("_x", 1)[1]), ratio,
                                   ratio * exp(-1.96 * se), ratio * exp(1.96 * se)))
            points.sort()
            x, y = [p[0] for p in points], [p[1] for p in points]
            ax.errorbar(x, y, yerr=[[p[1] - p[2] for p in points], [p[3] - p[1] for p in points]],
                        color=colour, marker=marker, markersize=6, linewidth=2, capsize=3, label=label)
        ax.set_xscale("log", base=2)
        ax.set_yscale("log", base=2)
        ax.set_xticks([0.5, 1, 2, 4], ["0.5x", "1x", "2x", "4x"])
        _axes(ax, f"{channel.replace('_', '-')} error, relative to 1e-3",
              "failure probability relative to baseline" if channel == "two_qubit" else "",
              f"only {channel.replace('_', '-')} varied")
    axes[0].legend(frameon=False, labelcolor=INK, fontsize=8)
    fig.suptitle("PILOT, decoder-limited (BP+OSD-0), Z basis: one channel scaled, all others at 1e-3; "
                 "95% intervals", fontsize=8, color=MUTED, x=0.01, ha="left")
    return _save(fig, out / "fig5_pilot_channel_sensitivity.png")


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    return path


def make_figures(pilot_path, out_dir) -> list:
    """Write all figures (and analytic.json) into out_dir; returns the paths."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables = analytic_tables()
    (out / "analytic.json").write_text(json.dumps(tables, indent=1) + "\n")
    paths = [out / "analytic.json", _fig_memory(plt, tables, out), _fig_budget(plt, tables, out),
             _fig_timing(plt, tables, out)]
    records = load_records(pilot_path)
    paths += [_fig_pilot_uniform(plt, records, out), _fig_pilot_sensitivity(plt, records, out)]
    plt.close("all")
    return paths
