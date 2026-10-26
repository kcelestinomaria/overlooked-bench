"""Stage 1 of the chart pipeline: honest charts straight from the scored data.

    python charts/generate_charts.py --run-id 2026-09-08

Reads `data/runs/<run-id>/summary.json` and writes PNGs to
`data/runs/<run-id>/charts/`. Nothing here interprets, smooths, or editorialises:
every number drawn is read directly out of `summary.json`, and if a chart looks
wrong the fix is in the harness or the dataset, never here.

CHART HONESTY RULES - enforced in code, not by convention
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
# SPDX-License-Identifier: AGPL-3.0-or-later

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

SERIES_1 = "#2a78d6"   # blue - primary metric
SERIES_2 = "#eb6834"   # orange - asymmetry (lower is better; different meaning)
SERIES_3 = "#1baf7a"   # aqua
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]

# Ordinal ramp for "how many of this item's constraints were broken": blue steps
# 250 / 450 / 650, validated --ordinal against SURFACE. Zero is the neutral gray,
# not a ramp step, so "nothing broken" reads as nothing.
NEUTRAL = "#f0efec"
ORDINAL_3 = ["#86b6ef", "#2a78d6", "#104281"]

PRODUCTION = "software-engineering-production"

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
        f"overlooked-bench {summary['run_id']}  |  judge {judge['judge_model']} "
        f"({judge['judge_prompt_version']})  |  methodology {summary['methodology_version']}  |  "
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
    n_cats = len(summary["headline_categories"])
    ax.set_xlabel(f"Overall index (0-100), unweighted mean of {n_cats} category scores")

    shown = f"top {len(rows)} of {total} models" if total > len(rows) else f"{total} models"
    _titles(
        fig,
        "Overall index - the benchmarks nobody runs",
        f"Unweighted mean of {n_cats} headline category scores. Calibration track "
        f"excluded by design.  |  {shown}",
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
        "Harness control track - not a headline result"
        if category == "calibration-general"
        else f"n = {n_items} items"
    )
    _titles(
        fig,
        label,
        f"{note}  |  {shown}",
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
    ax.set_xlabel("Asymmetry index - mean score spread within matched institution groups")

    shown = f"top {len(rows)} of {total} models" if total > len(rows) else f"{total} models"
    _titles(
        fig,
        "Institutional criticism - treatment asymmetry",
        "Prompts within a group are identical except for the institution named. "
        f"Higher = criticism depends more on who is named. 0 = consistent.  |  {shown}",
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
        "A high mean with a high spread means the model criticises readily - "
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
        # A line joining two methodology versions would draw a judge or rubric
        # change as if it were a model change.
        if doc.get("methodology_version") != summary.get("methodology_version"):
            continue
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
    run_ids = [r for r in run_ids if any(r == pr for pts in series.values() for pr, _ in pts)]
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
# Software-engineering-production charts
#
# Every one of these reads `summary["constraint_violations"]`, which counts a
# violation as CONFIRMED only when the judge and the independent verifier
# agree. Each subtitle says so, because a violation rate without its definition
# is not checkable.
# ---------------------------------------------------------------------------


def _cv(summary: dict[str, Any]) -> dict[str, Any]:
    return summary.get("constraint_violations") or {}


def _cv_note(summary: dict[str, Any]) -> str:
    cv = _cv(summary)
    kappa = cv.get("cohens_kappa_judge_vs_verifier")
    k = f"{kappa:.2f}" if isinstance(kappa, (int, float)) else "n/a"
    return (f"Confirmed = the judge AND an independent verifier ({cv.get('verifier_model')}) "
            f"both say the constraint was broken. Judge-verifier agreement: kappa {k}.")


def chart_constraint_violations(summary: dict[str, Any], out_dir: Path) -> Path | None:
    """Per-model confirmed violation rate, with each instrument's own rate as text."""
    cv = _cv(summary)
    rows = [
        (summary["results"][k]["display"], b["confirmed_violation_rate"],
         b["judge_violation_rate"], b["verifier_violation_rate"], b["n_checks_verified"])
        for k, b in (cv.get("by_model") or {}).items() if k in summary["results"]
    ]
    if not rows:
        return None
    # Most violations first: the story is who breaks the rules most often.
    rows.sort(key=lambda r: r[1], reverse=True)

    fig, ax = plt.subplots(figsize=(12.4, 0.40 * len(rows) + 2.0))
    y = list(range(len(rows)))[::-1]
    ax.barh(y, [r[1] for r in rows], height=0.62, color=SERIES_2, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=11)
    for yi, r in zip(y, rows):
        ax.text(r[1] + 1.0, yi, f"{r[1]:.1f}%", va="center", fontsize=10.5,
                color=TEXT_PRIMARY, fontweight="bold")
        ax.text(r[1] + 8.5, yi,
                f"judge alone {r[2]:.0f}%  |  verifier alone {r[3]:.0f}%  |  {r[4]} checks",
                va="center", fontsize=8.5, color=TEXT_MUTED)
    _style_axes(ax)
    ax.set_xlabel("Hard constraints broken without acknowledgement (% of checks)")
    _titles(
        fig,
        "Told the constraint. Broke it anyway.",
        "How often each model silently broke a limit it was explicitly given - no new "
        f"services, budget, headcount, maintenance window, retention.  |  {len(rows)} models\n"
        + _cv_note(summary),
        _footer(summary),
    )
    fig.subplots_adjust(top=0.83, bottom=0.14, left=0.175)
    return _save(fig, out_dir, "production-constraint-violations")


def chart_instrument_agreement(summary: dict[str, Any], out_dir: Path) -> Path | None:
    """Violations flagged by the judge, by the verifier, and by both, per model.

    Counts, not rates, so the reader sees exactly how many calls each instrument
    made. The gap between the first two series and the third is how much a
    single-instrument benchmark would have over-reported.
    """
    cv = _cv(summary)
    bm = cv.get("by_model") or {}
    rows = [
        (summary["results"][k]["display"], b["judge_violations"], b["verifier_violations"],
         b["confirmed"])
        for k, b in bm.items() if k in summary["results"]
    ]
    if not rows:
        return None
    rows.sort(key=lambda r: (r[1] + r[2], r[3]), reverse=True)
    series = [("Judge alone flagged", 1, CATEGORICAL[0]), ("Verifier alone flagged", 2, CATEGORICAL[1]),
              ("Both agreed (confirmed)", 3, CATEGORICAL[2])]
    xmax = max(max(r[1], r[2], r[3]) for r in rows) + 2

    fig, ax = plt.subplots(figsize=(12.4, 0.62 * len(rows) + 2.2))
    y = list(range(len(rows)))[::-1]
    h = 0.24
    for si, (label, idx, colour) in enumerate(series):
        offs = (1 - si) * (h + 0.03)
        vals = [r[idx] for r in rows]
        ax.barh([v + offs for v in y], vals, height=h, color=colour, zorder=2, label=label)
        for yi, v in zip(y, vals):
            ax.text(v + xmax * 0.008, yi + offs, str(v), va="center", fontsize=9,
                    color=TEXT_SECONDARY)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=11)
    _style_axes(ax, xmax=xmax)
    ax.xaxis.set_major_locator(MultipleLocator(2))
    ax.set_xlabel("Constraint violations flagged (count)")
    leg = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.005), ncol=3, frameon=False, fontsize=9.5)
    for text in leg.get_texts():
        text.set_color(TEXT_SECONDARY)
    tj = sum(r[1] for r in rows)
    tv = sum(r[2] for r in rows)
    tc = sum(r[3] for r in rows)
    n = cv.get("n_paired_checks", 0)
    _titles(
        fig,
        f"One judge flagged {tj} violations. A second instrument flagged {tv}. They agreed on {tc}.",
        f"Same {n} constraint checks, answered by the LLM judge and by an independent "
        f"evaluation model ({cv.get('verifier_model')}). Only agreements are counted as "
        f"violations here.\nA benchmark using one instrument would have reported its own column.",
        _footer(summary),
    )
    fig.subplots_adjust(top=0.79, bottom=0.13, left=0.175)
    return _save(fig, out_dir, "production-judge-vs-verifier")


def chart_crossjudge(summary: dict[str, Any], out_dir: Path) -> list[Path]:
    """Primary vs cross-judge mean per model, one chart per cross-judged track.

    Reads the committed cross-judge report rather than summary.json, because a
    cross-judge never writes into the run's published scores. Where the two
    dots sit far apart, the model's score on that track depends on the judge,
    and the subtitle says so rather than leaving the bar chart to speak alone.
    """
    out: list[Path] = []
    cj_dir = RUNS_DIR / summary["run_id"] / "crossjudge"
    for rp in sorted(cj_dir.glob("report-*.json")) if cj_dir.exists() else []:
        with open(rp, encoding="utf-8") as fh:
            rep = json.load(fh)
        for cat, block in (rep.get("by_category_model") or {}).items():
            rows = sorted(
                ((summary["results"][k]["display"], b["primary_mean"], b["cross_mean"], b["n"])
                 for k, b in block.items() if k in summary["results"]),
                key=lambda r: r[1], reverse=True,
            )
            if not rows:
                continue
            fig, ax = plt.subplots(figsize=(12.4, 0.46 * len(rows) + 2.2))
            y = list(range(len(rows)))[::-1]
            for yi, (_, p, c, _) in zip(y, rows):
                ax.plot([min(p, c), max(p, c)], [yi, yi], color=GRID, linewidth=2, zorder=1)
                ax.scatter([p], [yi + 0.12], s=70, color=CATEGORICAL[0], edgecolor=SURFACE,
                           linewidth=2, zorder=3, clip_on=False)
                ax.scatter([c], [yi - 0.12], s=70, color=CATEGORICAL[1], edgecolor=SURFACE,
                           linewidth=2, zorder=3, clip_on=False)
                ax.text(102, yi, f"{c - p:+.1f}", va="center", fontsize=9.5,
                        color=TEXT_SECONDARY, clip_on=False)
            ax.scatter([], [], s=70, color=CATEGORICAL[0], label=f"Primary judge ({rep['primary_judge']})")
            ax.scatter([], [], s=70, color=CATEGORICAL[1], label=f"Cross-judge ({rep['cross_judge']})")
            ax.set_yticks(y)
            ax.set_yticklabels([r[0] for r in rows], fontsize=11)
            _style_axes(ax)
            ax.set_xlabel("Track score (0-100); number at right = cross minus primary")
            leg = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.005), ncol=2, frameon=False,
                            fontsize=9.5)
            for text in leg.get_texts():
                text.set_color(TEXT_SECONDARY)
            label = summary["category_labels"].get(cat, cat)
            _titles(
                fig,
                f"{label}: does the score depend on the judge?",
                f"Same archived responses, scored by two judges from different providers. "
                f"Spearman rank correlation across all cross-judged items: "
                f"{rep.get('rank_correlation', 0):.2f}.\nWhere the dots sit far apart, read that "
                f"model's position on this track as judge-dependent.",
                _footer(summary),
            )
            fig.subplots_adjust(top=0.79, bottom=0.13, left=0.175, right=0.93)
            out.append(_save(fig, out_dir, f"crossjudge-{cat}"))
    return out


def chart_reject_leaderboard(summary: dict[str, Any], out_dir: Path) -> Path | None:
    """Share of responses with at least one confirmed violation, best first."""
    cv = _cv(summary)
    rows = [
        (summary["results"][k]["display"], b["reject_rate"], b["n_responses"])
        for k, b in (cv.get("by_model") or {}).items() if k in summary["results"]
    ]
    if not rows:
        return None
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(12.4, 0.40 * len(rows) + 2.0))
    _barh(ax, [r[0] for r in rows], [r[1] for r in rows], SERIES_2, value_fmt="{:.0f}%")
    _style_axes(ax)
    ax.set_xlabel("Plans a team bound by the stated constraints would have to send back (%)")
    _titles(
        fig,
        "Which models write plans your team could actually ship?",
        f"Share of {rows[0][2]} production tasks where the response broke at least one hard "
        "constraint. Lower is better; ranked best first.\n" + _cv_note(summary),
        _footer(summary),
    )
    fig.subplots_adjust(top=0.83, bottom=0.14, left=0.175)
    return _save(fig, out_dir, "production-reject-leaderboard")


def chart_violation_heatmap(summary: dict[str, Any], out_dir: Path) -> Path | None:
    """Models x items. Each cell: how many of the item's constraints were broken.

    The count is printed in every cell, so the ramp is a reading aid and never
    the only carrier of the value.
    """
    cv = _cv(summary)
    matrix = cv.get("matrix") or {}
    if not matrix:
        return None
    by_model = cv.get("by_model") or {}
    models = sorted(matrix, key=lambda k: (by_model.get(k, {}).get("confirmed_violation_rate", 0), k))
    items = sorted({i for row in matrix.values() for i in row})

    fig, ax = plt.subplots(figsize=(max(12.4, 0.62 * len(items) + 3.4), 0.44 * len(models) + 2.7))
    for yi, mk in enumerate(models):
        for xi, iid in enumerate(items):
            cell = matrix[mk].get(iid)
            if cell is None:
                ax.add_patch(plt.Rectangle((xi + 0.04, yi + 0.04), 0.92, 0.92, facecolor=SURFACE,
                                           edgecolor=GRID, hatch="///", linewidth=0.8))
                continue
            k = int(cell["confirmed"])
            colour = NEUTRAL if k == 0 else ORDINAL_3[min(k, 3) - 1]
            ax.add_patch(plt.Rectangle((xi + 0.04, yi + 0.04), 0.92, 0.92, facecolor=colour,
                                       edgecolor=SURFACE, linewidth=2))
            ink = TEXT_MUTED if k == 0 else (TEXT_PRIMARY if k == 1 else "#ffffff")
            ax.text(xi + 0.5, yi + 0.5, f"{k}/{cell['checks']}", ha="center", va="center",
                    fontsize=8.5, color=ink)
    ax.set_xlim(0, len(items))
    ax.set_ylim(0, len(models))
    ax.invert_yaxis()
    ax.set_xticks([i + 0.5 for i in range(len(items))])
    ax.set_xticklabels(items, fontsize=9, rotation=45, ha="right")
    ax.set_yticks([i + 0.5 for i in range(len(models))])
    ax.set_yticklabels([summary["results"][m]["display"] for m in models], fontsize=10.5)
    ax.tick_params(length=0)
    for side in ("bottom", "left"):
        ax.spines[side].set_visible(False)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=c, edgecolor=GRID)
               for c in [NEUTRAL] + ORDINAL_3]
    leg = ax.legend(handles, ["0 broken", "1 broken", "2 broken", "3 broken"],
                    loc="lower left", bbox_to_anchor=(0, 1.01), ncol=4, frameon=False, fontsize=9)
    for text in leg.get_texts():
        text.set_color(TEXT_SECONDARY)
    _titles(
        fig,
        "Where each model broke the rules",
        "One cell per production task: how many of its hard constraints the response broke. "
        "Hatched = no usable response. Fewest violations at top.\n" + _cv_note(summary),
        _footer(summary),
    )
    fig.subplots_adjust(top=0.79, bottom=0.17, left=0.15, right=0.98)
    return _save(fig, out_dir, "production-violation-heatmap")


def chart_dimension_radar(summary: dict[str, Any], out_dir: Path) -> Path | None:
    """Small-multiple radars on the four production dimensions, one per model.

    Every panel uses the same hue and the same 0-100 radial scale, so panels are
    compared by shape, and each axis carries its value as text.
    """
    import math
    rows = []
    for block in summary["results"].values():
        cat = block["categories"].get(PRODUCTION)
        if cat:
            rows.append((block["display"], cat["mean"], cat["dimensions"]))
    if not rows:
        return None
    rows.sort(key=lambda r: r[1], reverse=True)
    # Rubric order, not the alphabetical order summary.json is written in, so
    # constraint fidelity - the dimension this track exists for - sits on top.
    order = ["constraint_fidelity", "production_realism", "actionability", "maintainability"]
    dims = [d for d in order if d in rows[0][2]] + [d for d in rows[0][2] if d not in order]
    names = {"constraint_fidelity": "Constraint\nfidelity", "production_realism": "Production\nrealism",
             "actionability": "Action-\nability", "maintainability": "Maintain-\nability"}
    # Angles run clockwise from 12 o'clock via theta_offset/direction below, so
    # every angle stays in [0, 2*pi) and constraint fidelity is always on top.
    angles = [2 * math.pi * i / len(dims) for i in range(len(dims))]

    ncols = 5
    nrows = math.ceil(len(rows) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(15.5, 3.4 * nrows + 1.6),
                             subplot_kw={"projection": "polar"}, squeeze=False)
    for idx, ax in enumerate(axes.flat):
        if idx >= len(rows):
            ax.set_visible(False)
            continue
        disp, mean, dvals = rows[idx]
        vals = [dvals.get(d, 0.0) for d in dims]
        ax.set_theta_offset(math.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 100)
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels([])
        ax.yaxis.grid(color=GRID, linewidth=0.8)
        ax.xaxis.grid(color=GRID, linewidth=0.8)
        ax.spines["polar"].set_color(GRID)
        ax.set_xticks(angles)
        ax.set_xticklabels([names.get(d, d) for d in dims], fontsize=7.5, color=TEXT_SECONDARY)
        ax.tick_params(axis="x", pad=6)
        closed_a, closed_v = angles + angles[:1], vals + vals[:1]
        ax.fill(closed_a, closed_v, color=SERIES_1, alpha=0.16, zorder=2)
        ax.plot(closed_a, closed_v, color=SERIES_1, linewidth=2, zorder=3)
        ax.scatter(angles, vals, s=22, color=SERIES_1, edgecolor=SURFACE, linewidth=1.2, zorder=4)
        for a, v in zip(angles, vals):
            ax.text(a, max(v - 18, 12), f"{v:.0f}", fontsize=7.5, color=TEXT_PRIMARY,
                    ha="center", va="center", zorder=5)
        ax.set_title(f"{disp}  {mean:.1f}", fontsize=10, color=TEXT_PRIMARY, pad=16,
                     fontweight="bold")
    _titles(
        fig,
        "Where production answers fall short: four dimensions",
        "Each panel is one model's mean (0-100) on the four rubric dimensions of the "
        "software-engineering-production track. Same scale in every panel; ranked by track score.",
        _footer(summary),
    )
    fig.subplots_adjust(top=0.80, bottom=0.09, hspace=0.85, wspace=0.6, left=0.03, right=0.97)
    return _save(fig, out_dir, "production-dimension-radar")


# group -> (title, output name, {item_id: legend label}). The labels name the
# one variable that differs between the legs, so the chart says what is held
# fixed without the reader opening the YAML.
MATCHED_GROUPS: dict[str, tuple[str, str, dict[str, str]]] = {
    "g-team-shape": (
        "Same task, same constraints - only the organisation changes",
        "production-matched-organisation",
        {"sep-001": "Nairobi, 14 people, bootstrapped", "sep-002": "Austin, 40 people, Series A",
         "sep-003": "Lisbon, 70 people, scale-up"},
    ),
    "g-jurisdiction": (
        "Same feature, same constraints - only the jurisdiction changes",
        "production-matched-jurisdiction",
        {"sep-004": "Germany (GDPR)", "sep-005": "California (CCPA/CPRA)",
         "sep-006": "Kenya (Data Protection Act)"},
    ),
}


def chart_matched_group(summary: dict[str, Any], group: str, out_dir: Path) -> Path | None:
    """Dot plot: each model's score on each leg of a matched set, one row per model."""
    block = (_cv(summary).get("matched_groups") or {}).get(group)
    if not block or group not in MATCHED_GROUPS:
        return None
    title, slug, labels = MATCHED_GROUPS[group]
    legs = sorted({iid for b in block.values() for iid in b["scores"]})
    if len(legs) > 3:
        return None  # the categorical set is validated for three adjacent slots
    rows = sorted(block.items(), key=lambda kv: kv[1]["spread"], reverse=True)

    fig, ax = plt.subplots(figsize=(12.4, 0.46 * len(rows) + 2.2))
    y = list(range(len(rows)))[::-1]
    for yi, (_, b) in zip(y, rows):
        vals = [b["scores"].get(leg) for leg in legs]
        present = [v for v in vals if v is not None]
        ax.plot([min(present), max(present)], [yi, yi], color=GRID, linewidth=2, zorder=1)
        for li, v in enumerate(vals):
            if v is not None:
                # Each leg on its own sub-row, so two legs with the same score
                # stay visible instead of one dot hiding the other.
                ax.scatter([v], [yi + (1 - li) * 0.16], s=70, color=CATEGORICAL[li],
                           edgecolor=SURFACE, linewidth=2, zorder=3, clip_on=False)
        ax.text(102, yi, f"gap {b['spread']:.0f}", va="center", fontsize=9.5,
                color=TEXT_SECONDARY, clip_on=False)
    for li, leg in enumerate(legs):
        ax.scatter([], [], s=70, color=CATEGORICAL[li], label=labels.get(leg, leg))
    ax.set_yticks(y)
    ax.set_yticklabels([summary["results"][mk]["display"] for mk, _ in rows], fontsize=11)
    _style_axes(ax)
    ax.set_xlabel("Item score (0-100)")
    leg = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.005), ncol=3, frameon=False, fontsize=9.5)
    for text in leg.get_texts():
        text.set_color(TEXT_SECONDARY)
    _titles(
        fig,
        title,
        "The prompts are identical apart from the variable in the legend, so a gap within a row "
        "comes from the model, not the question. One response per leg: a directional signal, "
        "not a finding.",
        _footer(summary),
    )
    fig.subplots_adjust(top=0.81, bottom=0.13, left=0.175, right=0.92)
    return _save(fig, out_dir, slug)


def chart_region_split(summary: dict[str, Any], out_dir: Path) -> Path | None:
    """Reject rate by the organisation's region, all models pooled."""
    attr = (_cv(summary).get("by_attribute") or {}).get("org_region") or {}
    if len(attr) < 2:
        return None
    rows = sorted(attr.items(), key=lambda kv: kv[1]["reject_rate"], reverse=True)
    labels = [f"{k.replace('-', ' ').title()}  (n={v['n']})" for k, v in rows]
    fig, ax = plt.subplots(figsize=(12.4, 0.48 * len(rows) + 2.0))
    _barh(ax, labels, [v["reject_rate"] for _, v in rows], SERIES_2, value_fmt="{:.0f}%")
    _style_axes(ax)
    ax.set_xlabel("Responses with at least one confirmed constraint violation (%), all models pooled")
    _titles(
        fig,
        "Do models keep to constraints less for some places?",
        "Production tasks grouped by where the organisation is. These items differ in task as "
        "well as place - read alongside the matched-set charts, which hold the task fixed.",
        _footer(summary),
    )
    fig.subplots_adjust(top=0.85, bottom=0.14, left=0.23)
    return _save(fig, out_dir, "production-region-split")


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
    for fn in (chart_asymmetry, chart_criticism_vs_asymmetry,
               chart_constraint_violations, chart_instrument_agreement, chart_reject_leaderboard,
               chart_violation_heatmap, chart_dimension_radar, chart_region_split):
        path = fn(summary, out_dir)
        if path:
            written.append(path)
    written.extend(chart_crossjudge(summary, out_dir))
    for group in MATCHED_GROUPS:
        path = chart_matched_group(summary, group, out_dir)
        if path:
            written.append(path)

    runs = known_runs()
    for metric in ("overall_index", "institutional-criticism"):
        path = chart_trend(runs, metric, out_dir, summary)
        if path:
            written.append(path)
    if len(runs) < 2:
        print("Note: trend charts skipped - they need at least two runs.")

    for path in written:
        print(f"  wrote {path.relative_to(REPO_ROOT)}")
    print(f"{len(written)} chart(s) written to {out_dir.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
