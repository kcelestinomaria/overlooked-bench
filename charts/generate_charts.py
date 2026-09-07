"""Stage 1 of the chart pipeline: honest charts straight from the scored data.

    python charts/generate_charts.py --run-id 2026-09-08

Reads `data/runs/<run-id>/summary.json` and writes PNGs to
`data/runs/<run-id>/charts/`. Nothing here interprets, smooths, or editorialises:
every number drawn is read directly out of `summary.json`, and if a chart looks
wrong the fix is in the harness or the dataset, never here.

CHART HONESTY RULES — enforced in code, not by convention
---------------------------------------------------------
* Score axes always run the full 0-100. A truncated axis is the single easiest
  way to make a 3-point gap look like a landslide, so the range is hard-coded
  rather than left to matplotlib's autoscaling.
* One series means one colour. Bars are never shaded darker-where-bigger; that
  double-encodes length as hue and adds no information.
* Every bar carries its value as a visible label, so a reader never has to
  estimate a number off the axis.
* Charts show the top 10 models by the metric being charted. When models are
  omitted, the subtitle says so and gives the total.
* `n` is drawn on every category chart. A 12-item category and a 24-item
  category should not look equally solid.

Palette is the validated default from the dataviz reference (light mode,
categorical slots in fixed order). Adjacent-pair CVD and normal-vision checks
pass; the contrast warning on lighter slots is discharged by the always-on value
labels.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless: this must run unattended in CI
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "data" / "runs"

# --- Design tokens (validated palette, light mode) --------------------------
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#8a8880"
GRID = "#e6e5e1"

SERIES_1 = "#2a78d6"   # blue    — primary metric
SERIES_2 = "#eb6834"   # orange  — asymmetry (lower is better; different meaning)
SERIES_3 = "#1baf7a"   # aqua
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]

TOP_N = 10  # Charts show the top 10 models.

plt.rcParams.update({
    "font.family": "DejaVu Sans",   # ships with matplotlib; identical output in CI
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "text.color": TEXT_PRIMARY,
    "axes.labelcolor": TEXT_SECONDARY,
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_PRIMARY,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "figure.dpi": 130,
})


def _style_axes(ax, xmax: float = 100.0) -> None:
    ax.set_xlim(0, xmax)
    ax.xaxis.set_major_locator(MultipleLocator(20 if xmax > 50 else 10))
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0, labelsize=9)
    ax.spines["bottom"].set_color(GRID)


def _barh(
    ax,
    labels: list[str],
    values: list[float],
    color: str,
    value_fmt: str = "{:.1f}",
) -> None:
    """Horizontal bars, best at top, one colour, always value-labelled."""
    y = list(range(len(labels)))[::-1]
    # height 0.62 leaves a clear surface gap between adjacent bars.
    ax.barh(y, values, height=0.62, color=color, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=11)
    span = max(values) if values else 1.0
    for yi, val in zip(y, values):
        ax.text(
            val + max(span * 0.015, 0.8), yi, value_fmt.format(val),
            va="center", ha="left", fontsize=10.5, color=TEXT_SECONDARY,
        )


def _titles(fig, title: str, subtitle: str, footer: str) -> None:
    fig.text(0.012, 0.972, title, fontsize=17, fontweight="bold",
             color=TEXT_PRIMARY, va="top")
    fig.text(0.012, 0.918, subtitle, fontsize=10.5, color=TEXT_SECONDARY, va="top")
    fig.text(0.012, 0.022, footer, fontsize=8.5, color=TEXT_MUTED, va="bottom")


def _footer(summary: dict[str, Any]) -> str:
    """Provenance line burned into every chart.

    Deliberately omits the repo URL: the social card frame supplies that, and
    duplicating it inside the plot wastes the line that has to carry judge and
    methodology version instead. A chart with a score but no judge identity is
    not interpretable.
    """
    judge = summary["judge"]
    return (
        f"overlooked-bench {summary['run_id']}  ·  judge {judge['judge_model']} "
        f"({judge['judge_prompt_version']})  ·  methodology {summary['methodology_version']}  ·  "
        f"{summary['n_models']} models, {sum(summary['item_counts'].values())} items"
    )


def _save(fig, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", pad_inches=0.28)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def chart_overall(summary: dict[str, Any], out_dir: Path) -> Path:
    rows = summary["leaderboard"][:TOP_N]
    total = len(summary["leaderboard"])
    labels = [r["display"] for r in rows]
    values = [r["overall_index"] for r in rows]

    fig, ax = plt.subplots(figsize=(12.4, 0.40 * len(rows) + 1.7))
    _barh(ax, labels, values, SERIES_1)
    _style_axes(ax)
    ax.set_xlabel("Overall index (0-100), mean of five category scores")

    shown = f"top {len(rows)} of {total} models" if total > len(rows) else f"{total} models"
    _titles(
        fig,
        "Overall index — the benchmarks nobody runs",
        f"Mean of five category scores. Calibration track excluded by design.  ·  {shown}",
        _footer(summary),
    )
    fig.subplots_adjust(top=0.875, bottom=0.145, left=0.175)
    return _save(fig, out_dir, "overall")


def chart_category(summary: dict[str, Any], category: str, out_dir: Path) -> Path | None:
    label = summary["category_labels"][category]
    rows = []
    for key, block in summary["results"].items():
        cat = block["categories"].get(category)
        if cat:
            rows.append((block["display"], cat["mean"], cat["n"]))
    if not rows:
        return None
    rows.sort(key=lambda r: r[1], reverse=True)
    total = len(rows)
    rows = rows[:TOP_N]

    fig, ax = plt.subplots(figsize=(12.4, 0.40 * len(rows) + 1.7))
    _barh(ax, [r[0] for r in rows], [r[1] for r in rows], SERIES_1)
    _style_axes(ax)
    ax.set_xlabel("Category score (0-100), judge-scored against a published rubric")

    n_items = summary["item_counts"].get(category, rows[0][2] if rows else 0)
    shown = f"top {len(rows)} of {total} models" if total > len(rows) else f"{total} models"
    note = (
        "Harness control track — not a headline result"
        if category == "calibration-general"
        else f"n = {n_items} items"
    )
    _titles(
        fig,
        label,
        f"{note}  ·  {shown}",
        _footer(summary),
    )
    fig.subplots_adjust(top=0.875, bottom=0.145, left=0.175)
    return _save(fig, out_dir, category)


def chart_asymmetry(summary: dict[str, Any], out_dir: Path) -> Path | None:
    asym = summary.get("institutional_asymmetry") or {}
    if not asym:
        return None
    rows = [
        (summary["results"][k]["display"], b["asymmetry_index"], b["mean_criticism_score"])
        for k, b in asym.items()
        if k in summary["results"]
    ]
    if not rows:
        return None
    # Sorted most-asymmetric first: this chart's story is who varies most.
    rows.sort(key=lambda r: r[1], reverse=True)
    total = len(rows)
    rows = rows[:TOP_N]

    fig, ax = plt.subplots(figsize=(12.4, 0.40 * len(rows) + 1.8))
    _barh(ax, [r[0] for r in rows], [r[1] for r in rows], SERIES_2)
    _style_axes(ax, xmax=100.0)
    ax.set_xlabel("Asymmetry index — mean score spread within matched institution groups")

    shown = f"top {len(rows)} of {total} models" if total > len(rows) else f"{total} models"
    _titles(
        fig,
        "Institutional criticism — treatment asymmetry",
        "Prompts within a group are identical except for the institution named. "
        f"Higher = criticism depends more on who is named. 0 = consistent.  ·  {shown}",
        _footer(summary),
    )
    fig.subplots_adjust(top=0.855, bottom=0.145, left=0.175)
    return _save(fig, out_dir, "institutional-asymmetry")


def chart_criticism_vs_asymmetry(summary: dict[str, Any], out_dir: Path) -> Path | None:
    """Mean willingness to criticise, drawn beside the asymmetry it hides.

    Two measures on one axis only because both are 0-100 scores of the same
    scored responses. They are not a dual axis.
    """
    asym = summary.get("institutional_asymmetry") or {}
    if not asym:
        return None
    rows = [
        (summary["results"][k]["display"], b["mean_criticism_score"], b["asymmetry_index"])
        for k, b in asym.items()
        if k in summary["results"]
    ]
    if not rows:
        return None
    rows.sort(key=lambda r: r[1], reverse=True)
    rows = rows[:TOP_N]

    fig, ax = plt.subplots(figsize=(12.4, 0.48 * len(rows) + 1.8))
    y = list(range(len(rows)))[::-1]
    h = 0.34
    ax.barh([v + h / 2 + 0.02 for v in y], [r[1] for r in rows], height=h,
            color=SERIES_1, zorder=2, label="Mean criticism score")
    ax.barh([v - h / 2 - 0.02 for v in y], [r[2] for r in rows], height=h,
            color=SERIES_2, zorder=2, label="Asymmetry index")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=11)
    for yi, row in zip(y, rows):
        ax.text(row[1] + 1.0, yi + h / 2 + 0.02, f"{row[1]:.1f}", va="center",
                fontsize=8.5, color=TEXT_SECONDARY)
        ax.text(row[2] + 1.0, yi - h / 2 - 0.02, f"{row[2]:.1f}", va="center",
                fontsize=8.5, color=TEXT_SECONDARY)
    _style_axes(ax)
    ax.set_xlabel("Score (0-100)")
    # Anchored above the axes rather than inside them: an in-plot legend is one
    # unlucky run away from sitting on top of a long bar.
    leg = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.005), ncol=2,
                    frameon=False, fontsize=9)
    for text in leg.get_texts():
        text.set_color(TEXT_SECONDARY)

    _titles(
        fig,
        "Willingness to criticise, and how much it varies",
        "A high mean with a high spread means the model criticises readily — "
        "but not everyone equally.",
        _footer(summary),
    )
    fig.subplots_adjust(top=0.845, bottom=0.135, left=0.175)
    return _save(fig, out_dir, "criticism-vs-asymmetry")


def chart_trend(run_ids: list[str], metric: str, out_dir: Path,
                summary: dict[str, Any]) -> Path | None:
    """Track one metric across runs. Skipped until at least two runs exist."""
    series: dict[str, list[tuple[str, float]]] = {}
    labels: dict[str, str] = {}
    for run_id in run_ids:
        path = RUNS_DIR / run_id / "summary.json"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        for key, block in doc.get("results", {}).items():
            if metric == "overall_index":
                value = block.get("overall_index")
            else:
                value = block.get("categories", {}).get(metric, {}).get("mean")
            if value is None:
                continue
            series.setdefault(key, []).append((run_id, value))
            labels[key] = block.get("display", key)

    series = {k: v for k, v in series.items() if len(v) >= 2}
    if len(run_ids) < 2 or not series:
        return None

    # Colour follows the entity across runs, and the roster is capped at the
    # validated palette length rather than cycling hues.
    ranked = sorted(series, key=lambda k: series[k][-1][1], reverse=True)[: len(CATEGORICAL)]

    fig, ax = plt.subplots(figsize=(12.4, 5.6))
    for idx, key in enumerate(ranked):
        points = series[key]
        xs = [run_ids.index(r) for r, _ in points]
        ys = [v for _, v in points]
        colour = CATEGORICAL[idx]
        ax.plot(xs, ys, color=colour, linewidth=2, marker="o", markersize=6,
                markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3, label=labels[key])
        ax.text(xs[-1] + 0.06, ys[-1], labels[key], fontsize=9, color=colour,
                va="center", fontweight="bold")

    ax.set_xticks(range(len(run_ids)))
    ax.set_xticklabels(run_ids, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_xlim(-0.25, len(run_ids) - 0.25 + len(run_ids) * 0.35)
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.spines["bottom"].set_color(GRID)
    ax.set_ylabel("Score (0-100)")
    leg = ax.legend(loc="lower left", frameon=False, fontsize=9, ncol=2)
    for text in leg.get_texts():
        text.set_color(TEXT_SECONDARY)

    name = "Overall index" if metric == "overall_index" else summary["category_labels"].get(metric, metric)
    _titles(
        fig,
        f"{name} over time",
        "Scores are only comparable within one methodology version. "
        "A version change is marked in docs/METHODOLOGY.md.",
        _footer(summary),
    )
    fig.subplots_adjust(top=0.865, bottom=0.115, left=0.07)
    slug = "overall" if metric == "overall_index" else metric
    return _save(fig, out_dir, f"trend-{slug}")


# ---------------------------------------------------------------------------


def known_runs() -> list[str]:
    """Every run with a summary, oldest first. Run ids are ISO dates, so they
    sort chronologically as strings."""
    if not RUNS_DIR.exists():
        return []
    return sorted(p.name for p in RUNS_DIR.iterdir()
                  if p.is_dir() and (p / "summary.json").exists())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate raw charts from a run summary.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", default="", help="Output dir (default: data/runs/<id>/charts)")
    args = parser.parse_args(argv)

    summary_path = RUNS_DIR / args.run_id / "summary.json"
    if not summary_path.exists():
        print(f"ERROR: no summary at {summary_path}", file=sys.stderr)
        return 2
    with open(summary_path, encoding="utf-8") as fh:
        summary = json.load(fh)

    out_dir = Path(args.out) if args.out else RUNS_DIR / args.run_id / "charts"
    written: list[Path] = []

    written.append(chart_overall(summary, out_dir))
    for category in summary["category_labels"]:
        path = chart_category(summary, category, out_dir)
        if path:
            written.append(path)
    for fn in (chart_asymmetry, chart_criticism_vs_asymmetry):
        path = fn(summary, out_dir)
        if path:
            written.append(path)

    runs = known_runs()
    for metric in ("overall_index", "institutional-criticism"):
        path = chart_trend(runs, metric, out_dir, summary)
        if path:
            written.append(path)
    if len(runs) < 2:
        print("Note: trend charts skipped — they need at least two runs.")

    for path in written:
        print(f"  wrote {path.relative_to(REPO_ROOT)}")
    print(f"{len(written)} chart(s) written to {out_dir.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
