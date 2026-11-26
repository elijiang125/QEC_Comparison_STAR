"""Figures for the hardware workstream, generated only from recorded data.

Figures 1-4 are analytic: exact counting and the timing model, with every
plotted number also written to `analytic.json`. They do not depend on any
decoder. Figure 5 is drawn from the sampled records under results/ and is
labeled provisional, because it depends on the decoder and on a stand-in
surface-code circuit.
"""
import json
from pathlib import Path

from .experiments import Cell, load_records
from .models import BICYCLE_CYCLE_MS, SURFACE_CYCLE_MS, CycleTiming, NoiseProfile
from .noise import noise_census
from .resources import bicycle_block, break_even_cycle_ratio, memory_footprint, surface_block
from .scenarios import SCENARIOS

INK, MUTED, GRID = "#191919", "#666666", "#e6e6e6"
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, VIOLET = "#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#6a4ce2"
CHANNEL_COLOURS = {"two_qubit": BLUE, "measurement": ORANGE, "prep": AQUA,
                   "one_qubit": YELLOW, "idle": MAGENTA}
ARCHITECTURES = {"surface d=9": ("surface_reference", (9,), "surface", BLUE),
                 "bicycle [[56,8,6]]": ("bicycle", (4, 7), "bicycle", ORANGE)}
EXPOSURE_SCENARIOS = ["asym/two_qubit_x2", "asym/two_qubit_x4", "asym/measurement_x2",
                      "asym/measurement_x4", "asym/idle_x2", "asym/idle_x4", "lit/rb87_mixed",
                      "idle/t2_1500ms", "idle/t2_150ms"]
SAMPLED_CODES = {("bicycle", (3, 7)): "bicycle [[42,6,6]]",
                 ("surface_reference", (5,)): "surface d=5",
                 ("surface_reference", (7,)): "surface d=7",
                 ("surface_reference", (9,)): "surface d=9"}


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


def per_round_locations(architecture: str, code: tuple) -> dict:
    """Noise locations added by one more syndrome round, per channel (exact)."""
    probe = NoiseProfile(.5, .5, .5, .5, .5, "probe", .5)
    counts = [noise_census(Cell("fig", architecture, code, "Z", r, probe).noisy_circuit()) for r in (3, 4)]
    return {c: counts[1][c] - counts[0][c] for c in NoiseProfile.CHANNELS}


def expected_faults_per_logical_round(locations: dict, noise: NoiseProfile, logical: int) -> float:
    return sum(n * getattr(noise, channel) for channel, n in locations.items()) / logical


def analytic_tables() -> dict:
    """Every number behind figures 1-4."""
    surface, b6, b8 = surface_block(9), bicycle_block(3), bicycle_block(4)
    blocks = {"surface d=9": surface, "bicycle [[56,8,6]]": b8}
    counts = list(range(1, 129))
    budget, exposure = {}, {label: {} for label in ARCHITECTURES}
    for label, (arch, code, family, _) in ARCHITECTURES.items():
        locations = per_round_locations(arch, code)
        k = blocks[label].logical
        base = expected_faults_per_logical_round(locations, SCENARIOS["paper/p1e-3"].noise, k)
        budget[label] = {"locations_per_round": locations, "logical": k,
                         "cycle_ms": SURFACE_CYCLE_MS if family == "surface" else BICYCLE_CYCLE_MS,
                         "per_logical_per_round": {c: n / k for c, n in locations.items()},
                         "expected_faults_per_logical_round_at_paper_noise": base}
        for sid in EXPOSURE_SCENARIOS:
            noise = SCENARIOS.get(sid, SCENARIOS.get(f"{sid}/{family}")).noise
            exposure[label][sid] = expected_faults_per_logical_round(locations, noise, k) / base
    fixed = [0, 250, 500, 1000, 2000, 4000]
    return {
        "memory_footprint": {"logical_count": counts,
                             "surface d=9": [memory_footprint(n, surface) for n in counts],
                             "bicycle [[42,6,6]]": [memory_footprint(n, b6) for n in counts],
                             "bicycle [[56,8,6]]": [memory_footprint(n, b8) for n in counts]},
        "fault_budget": budget,
        "relative_expected_faults": exposure,
        "cycle_ratio_vs_fixed_overhead_us": {
            "fixed_us": fixed,
            "ratio": [CycleTiming(8, 0, 250, f).cycle_us / CycleTiming(4, 0, 250, f).cycle_us for f in fixed]},
        "memory_break_even_cycle_ratio": {str(n): break_even_cycle_ratio(n, surface, b8) for n in (9, 64)},
    }


def _fig_memory(plt, t, out):
    fig, ax = plt.subplots(figsize=(6.4, 4))
    m = t["memory_footprint"]
    for label, colour in (("surface d=9", BLUE), ("bicycle [[42,6,6]]", AQUA), ("bicycle [[56,8,6]]", ORANGE)):
        ax.step(m["logical_count"], m[label], where="post", color=colour, linewidth=2, label=label)
    ax.set_yscale("log")
    _axes(ax, "logical qubits stored", "physical qubits (data + check ancillas)",
          "Memory footprint with whole-block allocation\n(exact count; no magic-state space or spare atoms)")
    ax.legend(frameon=False, labelcolor=INK)
    return _save(fig, out / "fig1_memory_footprint.png")


def _fig_budget(plt, t, out):
    fig, ax = plt.subplots(figsize=(7, 3.2))
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
          "Where faults can occur under the paper's noise model (exact count)")
    ax.set_xlim(0, max(left) * 1.12)
    ax.legend(frameon=False, ncols=5, loc="upper center", bbox_to_anchor=(0.5, -0.32), labelcolor=INK,
              fontsize=8)
    return _save(fig, out / "fig2_noise_locations.png")


def _fig_timing(plt, t, out):
    fig, (left, right) = plt.subplots(1, 2, figsize=(9.6, 3.8))
    c = t["cycle_ratio_vs_fixed_overhead_us"]
    left.plot([f / 1000 for f in c["fixed_us"]], c["ratio"], color=ORANGE, linewidth=2, marker="o", markersize=6)
    left.annotate("paper: 2.0 (no fixed term)", (0, 2), (0.35, 1.93), color=INK, fontsize=8)
    left.set_ylim(1, 2.1)
    _axes(left, "fixed time per round, e.g. readout + reset (ms)", "bicycle / surface cycle time",
          "Cycle ratio with 0.25 ms per entangling layer")
    ratios = [r / 4 for r in range(4, 65)]
    for n, colour in (("9", AQUA), ("64", ORANGE)):
        star = t["memory_break_even_cycle_ratio"][n]
        right.plot(ratios, [star / r for r in ratios], color=colour, linewidth=2,
                   label=f"{n} logical qubits (break-even at {star:.3g})")
    right.axhline(1, color=INK, linewidth=1)
    right.axvline(2, color=MUTED, linewidth=1, linestyle=":")
    right.annotate("paper cycle ratio", (2, 0.5), (2.3, 0.5), color=MUTED, fontsize=8)
    right.set_yscale("log")
    _axes(right, "bicycle / surface cycle time", "surface / bicycle qubit-seconds per round",
          "Memory space-time ratio (above 1: bicycle cheaper)")
    right.legend(frameon=False, labelcolor=INK, fontsize=8)
    return _save(fig, out / "fig3_timing_and_break_even.png")


def _fig_exposure(plt, t, out):
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    scenarios = EXPOSURE_SCENARIOS[::-1]
    for offset, (label, (_, _, _, colour)) in zip((0.2, -0.2), ARCHITECTURES.items()):
        values = [t["relative_expected_faults"][label][s] for s in scenarios]
        ax.barh([y + offset for y in range(len(scenarios))], values, height=0.36, color=colour,
                edgecolor="white", linewidth=2, label=label)
        for y, v in enumerate(values):
            ax.text(v + 0.03, y + offset, f"{v:.2f}", va="center", color=INK, fontsize=8)
    ax.axvline(1, color=INK, linewidth=1)
    ax.set_yticks(range(len(scenarios)), scenarios)
    _axes(ax, "expected faults per logical qubit per round, relative to the paper baseline", "",
          "How each scenario changes the fault budget (exact; decoder-independent)")
    ax.legend(frameon=False, labelcolor=INK, loc="lower right")
    return _save(fig, out / "fig4_scenario_fault_exposure.png")


def _fig_decoders(plt, results_dir, out):
    """Provisional: sampled failure per shot for the two decoders."""
    files = {"BP+OSD-0 (fails acceptance check)": ("pilot_bposd0_sequential.jsonl", MUTED, "s"),
             "Tesseract (passes acceptance check)": ("validation_tesseract.jsonl", ORANGE, "o")}
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9), sharey=True)
    drawn = False
    for ax, (p, title) in zip(axes, ((1e-3, "p = 1e-3 (paper baseline)"), (2e-3, "p = 2e-3"))):
        for offset, (label, (name, colour, marker)) in zip((-0.12, 0.12), files.items()):
            path = Path(results_dir) / name
            if not path.exists():
                continue
            rows = {(r["architecture"], tuple(r["code"])): r for r in load_records(path)
                    if r["basis"] == "Z" and r["noise"]["two_qubit"] == p
                    and r["scenario_id"] in ("paper/p1e-3", "uniform/p0.002")}
            for x, key in enumerate(SAMPLED_CODES):
                if key not in rows:
                    continue
                r, drawn = rows[key], True
                low, high = r["wilson95"]
                if r["failures"]:
                    ax.errorbar([x + offset], [r["shot_failure_rate"]],
                                yerr=[[r["shot_failure_rate"] - low], [high - r["shot_failure_rate"]]],
                                color=colour, marker=marker, markersize=7, capsize=3, linewidth=2)
                else:                                   # no failures seen: draw the 95% upper bound
                    ax.scatter([x + offset], [high], marker="v", s=60, facecolors="none", edgecolors=colour,
                               linewidths=2)
            ax.plot([], [], color=colour, marker=marker, linestyle="none", label=label)
        ax.set_yscale("log")
        ax.set_xticks(range(len(SAMPLED_CODES)), list(SAMPLED_CODES.values()), fontsize=8)
        _axes(ax, "", "failure probability per shot (3d rounds)" if p == 1e-3 else "", f"Z-basis memory, {title}")
    axes[1].legend(frameon=False, labelcolor=INK, fontsize=8)
    fig.suptitle("PROVISIONAL. Not the paper's decoders; surface circuits are Stim stand-ins. 95% intervals; "
                 "hollow triangles are upper bounds with zero failures.", fontsize=8, color=MUTED, x=0.01, ha="left")
    return _save(fig, out / "fig5_provisional_decoder_comparison.png") if drawn else None


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    return path


def make_figures(results_dir, out_dir) -> list:
    """Write all figures (and analytic.json) into out_dir; returns the paths."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables = analytic_tables()
    (out / "analytic.json").write_text(json.dumps(tables, indent=1) + "\n")
    paths = [out / "analytic.json", _fig_memory(plt, tables, out), _fig_budget(plt, tables, out),
             _fig_timing(plt, tables, out), _fig_exposure(plt, tables, out),
             _fig_decoders(plt, results_dir, out)]
    plt.close("all")
    return [p for p in paths if p]
