"""Render a human-readable README.md for a completed run.

    python -m harness.run_readme --run-id 2026-09-13

Reads `runs/<id>/summary.json` and `runs/<id>/manifest.json` and writes
`runs/<id>/README.md`. Like the chart stage, this interprets nothing: every
number it prints is read straight out of the summary, so the page cannot drift
away from the data it describes. Re-running it on the same run is idempotent.

The point of this file is that a reader who lands in a run folder from a link
should be able to see what was run, what the judge was, what the numbers were,
and - above all - what was WRONG with the run, without opening a 3MB JSON blob.
Diagnostics are therefore printed above the results rather than in a footnote.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import run_dir


def _fmt(value: Any, nd: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.{nd}f}"
    return str(value)


def _warnings_block(summary: dict[str, Any]) -> list[str]:
    """Everything a reader should know before believing a number below."""
    diag = summary.get("diagnostics", {})
    out: list[str] = []

    cal_warning = diag.get("calibration_warning")
    below = diag.get("models_below_calibration_floor") or []
    trunc = diag.get("truncation_warning")
    judge_rate = diag.get("judge_error_rate") or 0.0
    gen_rate = diag.get("generation_error_rate") or 0.0

    if cal_warning:
        out.append(f"- **Calibration:** {cal_warning}")
    if below:
        out.append(
            f"- **Calibration floor:** {', '.join(below)} scored below the control "
            f"floor of {diag.get('calibration_floor')}. Treat this run's other "
            f"numbers for those models as unreliable."
        )
    if trunc:
        out.append(f"- **Truncation:** {trunc}")
    if judge_rate:
        out.append(
            f"- **Judge errors:** {diag.get('judge_error_count')} of "
            f"{summary.get('n_models', 0) * sum(summary.get('item_counts', {}).values())} "
            f"judgings ({judge_rate}%) did not produce a usable score and are "
            f"excluded from the means below rather than scored 0."
        )
    if gen_rate:
        out.append(
            f"- **Generation errors:** {diag.get('generation_error_count')} "
            f"({gen_rate}%) model calls failed."
        )

    if not out:
        out.append(
            "- None. The calibration control passed for every model, no response "
            "was truncated, and every judging produced a usable score."
        )
    return out


def render(run_id: str) -> str:
    root = run_dir(run_id)
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    labels = summary.get("category_labels", {})
    headline = summary.get("headline_categories", [])
    results = summary.get("results", {})
    judge = summary.get("judge", {})
    diag = summary.get("diagnostics", {})
    counts = summary.get("item_counts", {})
    asym = summary.get("institutional_asymmetry", {})

    L: list[str] = []
    L.append(f"# overlooked-bench run `{run_id}`")
    L.append("")
    L.append(
        f"{summary.get('n_models')} models over {sum(counts.values())} items in "
        f"{len(counts)} categories. Generated {summary.get('generated_utc')}."
    )
    L.append("")
    L.append(
        "Every number on this page is read directly from `summary.json`, which is "
        "aggregated from `scored/`, which is judged from `raw/`. Nothing here is "
        "hand-written. If a number looks wrong, the fix is in the harness or the "
        "dataset and the run is repeated under a new id."
    )
    L.append("")

    # --- Read this first -----------------------------------------------
    L.append("## Read this first")
    L.append("")
    L.extend(_warnings_block(summary))
    L.append("")

    # --- Provenance ----------------------------------------------------
    L.append("## Provenance")
    L.append("")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append(f"| Judge model | `{judge.get('judge_model')}` |")
    L.append(
        f"| Judge prompt | `{judge.get('judge_prompt_version')}` "
        f"(hash `{judge.get('judge_prompt_hash')}`) |"
    )
    L.append(f"| Scoring engine | `{judge.get('metric_engine')}` |")
    L.append(f"| Methodology | `{summary.get('methodology_version')}` |")
    L.append(f"| Harness | `{summary.get('harness_version')}` |")
    L.append(f"| Dataset fingerprint | `{summary.get('dataset_fingerprint')}` |")
    L.append(f"| Total cost | ${_fmt(summary.get('total_cost_usd'), 2)} |")

    reused = manifest.get("raw_reused_from")
    if reused:
        L.append(
            f"| Raw responses | {reused.get('responses_copied')} reused from run "
            f"`{reused.get('run_id')}` (identical dataset fingerprint), "
            f"{reused.get('responses_regenerated')} regenerated for this run |"
        )
    L.append("")

    rubrics = summary.get("judge", {}).get("rubric_hashes") or manifest.get("rubric_hashes", {})
    if rubrics:
        L.append("Rubric hashes:")
        L.append("")
        L.append("| Category | Rubric hash |")
        L.append("|---|---|")
        for cat in sorted(rubrics):
            L.append(f"| {labels.get(cat, cat)} | `{rubrics[cat]}` |")
        L.append("")

    # --- Leaderboard ---------------------------------------------------
    L.append("## Overall")
    L.append("")
    L.append(
        "The overall index is the mean of the five headline category scores. "
        "The calibration track is a control and is excluded from it by design."
    )
    L.append("")
    L.append("| # | Model | Provider | Tier | Overall |")
    L.append("|---:|---|---|---|---:|")
    for row in summary.get("leaderboard", []):
        L.append(
            f"| {row.get('rank')} | {row.get('display')} | {row.get('provider')} "
            f"| {row.get('tier')} | {_fmt(row.get('overall_index'))} |"
        )
    L.append("")

    # --- Per category --------------------------------------------------
    L.append("## By category")
    L.append("")
    cats = [c for c in headline if c in counts] + (
        ["calibration-general"] if "calibration-general" in counts else []
    )
    header = "| Model | " + " | ".join(
        f"{labels.get(c, c)} (n={counts.get(c)})" for c in cats
    ) + " |"
    L.append(header)
    L.append("|---" * (len(cats) + 1) + "|")
    order = [r["model_key"] for r in summary.get("leaderboard", [])]
    display = {r["model_key"]: r["display"] for r in summary.get("leaderboard", [])}
    for key in order:
        cells = []
        for c in cats:
            block = results.get(key, {}).get("categories", {}).get(c)
            cells.append(_fmt(block.get("mean")) if block else "-")
        L.append(f"| {display.get(key, key)} | " + " | ".join(cells) + " |")
    L.append("")

    # --- Calibration control -------------------------------------------
    means = diag.get("calibration_means") or {}
    if means:
        L.append("### Calibration control")
        L.append("")
        L.append(
            f"Items with known answers, used to check the harness before any other "
            f"number is believed. Floor is {diag.get('calibration_floor')}; mean "
            f"across all models is {_fmt(diag.get('calibration_mean_all_models'), 2)}. "
            f"A model far below the floor indicates a harness or transport fault, "
            f"not a capability finding."
        )
        L.append("")

    # --- Asymmetry -----------------------------------------------------
    if asym:
        L.append("## Institutional asymmetry")
        L.append("")
        L.append(
            "Prompts inside a matched group differ only in the institution named, "
            "so a model's score spread inside a group cannot be explained by some "
            "prompts being harder. 0 means consistent treatment; higher means "
            "willingness to criticise depends on the target."
        )
        L.append("")
        L.append("| Model | Asymmetry index | Sector gap | Region gap | Coverage gap |")
        L.append("|---|---:|---:|---:|---:|")
        for key in order:
            block = asym.get(key)
            if not block:
                continue
            by = block.get("by_attribute", {})
            L.append(
                f"| {display.get(key, key)} | {_fmt(block.get('asymmetry_index'), 2)} "
                f"| {_fmt(by.get('sector', {}).get('gap'), 2)} "
                f"| {_fmt(by.get('region', {}).get('gap'), 2)} "
                f"| {_fmt(by.get('coverage', {}).get('gap'), 2)} |"
            )
        L.append("")

    # --- Cross-judge ---------------------------------------------------
    cj_dir = root / "crossjudge"
    reports = sorted(cj_dir.glob("report-*.json")) if cj_dir.exists() else []
    if reports:
        L.append("## Cross-judge validation")
        L.append("")
        L.append(
            "The same responses re-scored by a judge from a different provider. "
            "This cannot say which judge is right; it says where two judges "
            "disagree, so the disagreement is published rather than hidden behind "
            "whichever judge was cheapest. Cross-judge scores live in "
            "`crossjudge/` and are never written to `scored/`."
        )
        L.append("")
        L.append(
            "| Cross-judge | Pairs | Mean delta | Rank corr. | Provider spread | Group spread |"
        )
        L.append("|---|---:|---:|---:|---:|---:|")
        for rp in reports:
            r = json.loads(rp.read_text(encoding="utf-8"))
            L.append(
                f"| `{r.get('cross_judge')}` | {r.get('n_pairs')} "
                f"| {_fmt(r.get('mean_delta'), 2)} | {_fmt(r.get('rank_correlation'), 3)} "
                f"| {_fmt(r.get('provider_spread'), 2)} | {_fmt(r.get('group_spread'), 2)} |"
            )
        L.append("")
        L.append(
            "`mean_delta` is harmless on its own - a judge can be uniformly harsher "
            "without distorting anything. The two that matter are `provider_spread` "
            "(one provider's models moving, the signature of family preference) and "
            "`group_spread` (one matched institution group moving, the signature of "
            "political preference). Both should be near zero."
        )
        L.append("")
        for rp in reports:
            r = json.loads(rp.read_text(encoding="utf-8"))
            groups = r.get("bias_by_group") or {}
            if groups:
                L.append(f"Per matched institution group, `{r.get('cross_judge')}`:")
                L.append("")
                L.append("| Group | n | Delta |")
                L.append("|---|---:|---:|")
                rows = sorted(groups.items(), key=lambda kv: kv[1].get("mean_delta", 0))
                for name, blk in rows:
                    L.append(
                        f"| {name} | {blk.get('n')} | {_fmt(blk.get('mean_delta'), 2)} |"
                    )
                L.append("")

    # --- Charts --------------------------------------------------------
    charts = sorted((root / "charts").glob("*.png")) if (root / "charts").exists() else []
    if charts:
        L.append("## Charts")
        L.append("")
        for png in charts:
            L.append(f"- [`charts/{png.name}`](charts/{png.name})")
        L.append("")
        if (root / "social").exists():
            L.append("Branded 1600x900 versions of the same charts are in `social/`.")
            L.append("")

    # --- Reproduce -----------------------------------------------------
    L.append("## Reproducing this run")
    L.append("")
    L.append(
        "Re-judging reads the archived raw responses back off disk and never "
        "re-queries a model, so it reproduces these scores for the cost of the "
        "judge alone:"
    )
    L.append("")
    L.append("```bash")
    L.append(f"python -m harness.run_eval --run-id {run_id} --stage score --force-rescore")
    L.append("```")
    L.append("")
    L.append(
        "The scores will match only if the rubric and judge-prompt hashes in the "
        "table above still match the code. If they do not, the methodology has "
        "moved and `docs/METHODOLOGY.md` says how."
    )
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="run_readme")
    p.add_argument("--run-id", required=True)
    args = p.parse_args(argv)

    root = run_dir(args.run_id)
    if not (root / "summary.json").exists():
        print(f"No summary.json in {root} - run the eval stage first.", file=sys.stderr)
        return 1

    out = root / "README.md"
    out.write_text(render(args.run_id), encoding="utf-8")
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
