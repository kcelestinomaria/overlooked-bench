"""Cross-judge validation: score the same responses with a second judge.

    python -m harness.crossjudge --run-id 2026-09-08 --judge deepseek/deepseek-v3.1-terminus
    python -m harness.crossjudge --run-id 2026-09-08 --judge anthropic/claude-sonnet-4.6 \
        --categories institutional-criticism

METHODOLOGY.md section 2 commits this project to re-scoring a sample with a judge from a
different provider each cycle, and to publishing the deltas whether or not they
are flattering. This is the code that does it.

WHY IT MATTERS MORE THAN A USUAL QA STEP
----------------------------------------
Every judge is built by a lab with an interest in the outcome, and the
`institutional-criticism` track asks models to criticise institutions - including
AI labs, including governments. A judge is not a neutral instrument here. The two
specific risks:

  * Family preference. A judge scores its own family's responses more
    favourably. `bias_by_model` is what detects it: if switching judges moves one
    provider's models and leaves the rest still, that is the signature.

  * Political-content preference. A judge may score criticism of some
    institutions differently from structurally identical criticism of others.
    `bias_by_group` measures exactly that, per matched institution group, which
    is the only place it can be seen.

This tool cannot tell you which judge is *right*. It tells you where two judges
disagree, and how much, so that disagreement gets published instead of hidden
behind whichever judge was cheapest.

Cross-judge scores are written to `runs/<id>/crossjudge/<slug>/` and NEVER to
`scored/`. The primary judge's scores remain the run's published result; nothing
here can silently overwrite them.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .analysis import CRITICISM_DIMENSIONS
from .config import concurrency, load_env, load_registry, run_dir
from .dataset import Item, load_all
from .judge import ScoreRecord, score as judge_score
from .run_eval import raw_path, read_json, scored_path, write_json

console = Console()


def slugify(model_id: str) -> str:
    return model_id.replace("/", "__").replace(".", "-")


def _criticism_score(dims: dict[str, Any]) -> float:
    present = [float(dims[k]) for k in CRITICISM_DIMENSIONS if dims.get(k) is not None]
    if not present:
        return 0.0
    return round(100.0 * sum(present) / (4.0 * len(present)), 2)


def _spearman(a: list[float], b: list[float]) -> float:
    """Rank correlation. The headline question is whether the two judges produce
    the same leaderboard ORDER, which matters more than whether they agree on
    absolute levels - a uniformly harsher judge is harmless, a judge that
    reorders models is not."""
    if len(a) < 2:
        return 0.0

    def ranks(xs: list[float]) -> list[float]:
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        out = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return round(num / den, 4) if den else 0.0


def run_cross(
    run_id: str,
    judge_model: str,
    categories: list[str] | None,
    limit: int,
    models_filter: list[str] | None,
    workers: int,
    engine: str,
) -> dict[str, Any]:
    registry = load_registry()
    root = run_dir(run_id)
    if not root.exists():
        raise SystemExit(f"ERROR: no run at {root}")

    alt_judge = replace(registry.judge, model_id=judge_model)
    primary_model = registry.judge.model_id
    if judge_model == primary_model:
        raise SystemExit(
            f"ERROR: --judge {judge_model} is already the primary judge. "
            f"A cross-check against itself measures nothing."
        )

    out_root = root / "crossjudge" / slugify(judge_model)
    items_by_category = load_all(categories)
    if limit:
        items_by_category = {c: i[:limit] for c, i in items_by_category.items()}

    specs = registry.enabled_models()
    if models_filter:
        specs = [s for s in specs if s.key in models_filter]

    jobs: list[tuple[str, Item, str]] = []
    cached = 0
    for spec in specs:
        for category, items in items_by_category.items():
            for item in items:
                dest = out_root / spec.key / category / f"{item.id}.json"
                if dest.exists() and (read_json(dest) or {}).get("ok"):
                    cached += 1
                    continue
                raw = read_json(raw_path(root, spec.key, category, item.id))
                # Only compare where the PRIMARY judge produced a usable score.
                # Scoring something the primary never scored would compare a
                # number against nothing.
                prim = read_json(scored_path(root, spec.key, category, item.id))
                if not raw or not raw.get("ok") or not prim or not prim.get("ok"):
                    continue
                jobs.append((spec.key, item, raw.get("text", "")))

    console.print(
        f"cross-judge [bold]{judge_model}[/bold] vs primary [bold]{primary_model}[/bold]  "
        f"| {len(jobs)} to score, {cached} cached"
    )

    if jobs:
        def work(model_key: str, item: Item, text: str) -> None:
            rec = judge_score(alt_judge, item, model_key, text, engine=engine)
            write_json(out_root / model_key / item.category / f"{item.id}.json", rec.to_dict())

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(work, mk, it, tx) for mk, it, tx in jobs]
            done = 0
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as exc:  # noqa: BLE001
                    console.print(f"[red]cross-judge error:[/red] {exc}")
                done += 1
                if done % 50 == 0:
                    console.print(f"  {done}/{len(jobs)}")

    return compare(run_id, judge_model, items_by_category, specs, out_root, root)


def compare(
    run_id: str,
    judge_model: str,
    items_by_category: dict[str, list[Item]],
    specs,
    out_root: Path,
    root: Path,
) -> dict[str, Any]:
    """Compare cross-judge scores against the primary ones. Pure arithmetic."""
    registry = load_registry()
    item_index = {i.id: i for items in items_by_category.values() for i in items}

    pairs: list[tuple[str, str, str, float, float]] = []  # model, cat, item, primary, alt
    dim_pairs: dict[str, list[tuple[int, int]]] = defaultdict(list)
    crit: list[tuple[str, str, float, float]] = []  # model, item, primary, alt
    alt_errors = 0

    for spec in specs:
        for category, items in items_by_category.items():
            for item in items:
                prim = read_json(scored_path(root, spec.key, category, item.id))
                alt = read_json(out_root / spec.key / category / f"{item.id}.json")
                if not prim or not alt:
                    continue
                if not alt.get("ok"):
                    alt_errors += 1
                    continue
                pairs.append((spec.key, category, item.id, prim["score"], alt["score"]))
                for dim, val in (prim.get("dimension_scores") or {}).items():
                    if dim in (alt.get("dimension_scores") or {}):
                        dim_pairs[dim].append((int(val), int(alt["dimension_scores"][dim])))
                if category == "institutional-criticism":
                    crit.append((
                        spec.key, item.id,
                        _criticism_score(prim.get("dimension_scores") or {}),
                        _criticism_score(alt.get("dimension_scores") or {}),
                    ))

    if not pairs:
        raise SystemExit("ERROR: no comparable score pairs found.")

    deltas = [alt - prim for _, _, _, prim, alt in pairs]

    by_model: dict[str, list[float]] = defaultdict(list)
    prim_by_model: dict[str, list[float]] = defaultdict(list)
    alt_by_model: dict[str, list[float]] = defaultdict(list)
    for mk, _, _, prim, alt in pairs:
        by_model[mk].append(alt - prim)
        prim_by_model[mk].append(prim)
        alt_by_model[mk].append(alt)

    by_category: dict[str, list[float]] = defaultdict(list)
    for _, cat, _, prim, alt in pairs:
        by_category[cat].append(alt - prim)

    # Matched-group bias: does the second judge move criticism scores for some
    # institution groups and not others? This is the political-preference probe.
    by_group: dict[str, list[float]] = defaultdict(list)
    by_attr: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for mk, item_id, prim, alt in crit:
        item = item_index.get(item_id)
        if item is None:
            continue
        if item.group:
            by_group[item.group].append(alt - prim)
        for attr, value in (item.attributes or {}).items():
            by_attr[attr][str(value)].append(alt - prim)

    model_keys = sorted(prim_by_model)
    rank_corr = _spearman(
        [statistics.fmean(prim_by_model[k]) for k in model_keys],
        [statistics.fmean(alt_by_model[k]) for k in model_keys],
    )

    report = {
        "run_id": run_id,
        "primary_judge": registry.judge.model_id,
        "cross_judge": judge_model,
        "n_pairs": len(pairs),
        "cross_judge_errors": alt_errors,
        "mean_delta": round(statistics.fmean(deltas), 2),
        "mean_abs_delta": round(statistics.fmean([abs(d) for d in deltas]), 2),
        "stdev_delta": round(statistics.stdev(deltas), 2) if len(deltas) > 1 else 0.0,
        "rank_correlation": rank_corr,
        "bias_by_model": {
            k: {
                "mean_delta": round(statistics.fmean(v), 2),
                "primary_mean": round(statistics.fmean(prim_by_model[k]), 2),
                "cross_mean": round(statistics.fmean(alt_by_model[k]), 2),
                "n": len(v),
                "provider": next((s.provider for s in specs if s.key == k), "?"),
            }
            for k, v in sorted(by_model.items())
        },
        "bias_by_category": {
            k: {"mean_delta": round(statistics.fmean(v), 2), "n": len(v)}
            for k, v in sorted(by_category.items())
        },
        "bias_by_group": {
            k: {"mean_delta": round(statistics.fmean(v), 2), "n": len(v)}
            for k, v in sorted(by_group.items())
        },
        "bias_by_institution_attribute": {
            attr: {
                val: {"mean_delta": round(statistics.fmean(v), 2), "n": len(v)}
                for val, v in sorted(vals.items())
            }
            for attr, vals in sorted(by_attr.items())
        },
        "bias_by_dimension": {
            k: {
                "mean_delta_raw_scale": round(
                    statistics.fmean([a - p for p, a in v]), 3
                ),
                "n": len(v),
            }
            for k, v in sorted(dim_pairs.items())
        },
    }

    # A judge swap is safe when levels shift uniformly and the ORDER survives.
    # Provider-specific movement or group-specific movement is not safe.
    provider_deltas: dict[str, list[float]] = defaultdict(list)
    for k, block in report["bias_by_model"].items():
        provider_deltas[block["provider"]].append(block["mean_delta"])
    prov_means = {p: round(statistics.fmean(v), 2) for p, v in provider_deltas.items()}
    report["bias_by_provider"] = prov_means
    report["provider_spread"] = (
        round(max(prov_means.values()) - min(prov_means.values()), 2) if prov_means else 0.0
    )
    group_means = [b["mean_delta"] for b in report["bias_by_group"].values()]
    report["group_spread"] = (
        round(max(group_means) - min(group_means), 2) if len(group_means) > 1 else 0.0
    )
    return report


def print_report(rep: dict[str, Any]) -> None:
    console.rule(f"[bold]cross-judge[/bold] {rep['cross_judge']} vs {rep['primary_judge']}")

    t = Table(title="Agreement")
    t.add_column("Signal"); t.add_column("Value", justify="right"); t.add_column("Reading")
    t.add_row("Pairs compared", str(rep["n_pairs"]), "")
    t.add_row("Cross-judge errors", str(rep["cross_judge_errors"]),
              "high = the cheaper judge cannot follow the rubric format")
    t.add_row("Mean delta", f"{rep['mean_delta']:+.2f}",
              "uniform harshness/leniency - harmless on its own")
    t.add_row("Mean |delta|", f"{rep['mean_abs_delta']:.2f}",
              "per-item disagreement, on the 0-100 scale")
    t.add_row("Rank correlation", f"{rep['rank_correlation']:.3f}",
              "does the leaderboard order survive the swap?")
    t.add_row("Provider spread", f"{rep['provider_spread']:.2f}",
              "family preference - should be near 0")
    t.add_row("Group spread", f"{rep['group_spread']:.2f}",
              "political preference across matched groups - should be near 0")
    console.print(t)

    m = Table(title="Per-model delta (cross - primary)")
    m.add_column("Model"); m.add_column("Provider", style="dim")
    m.add_column("Primary", justify="right"); m.add_column("Cross", justify="right")
    m.add_column("Delta", justify="right", style="bold")
    for k, b in sorted(rep["bias_by_model"].items(), key=lambda kv: kv[1]["mean_delta"]):
        m.add_row(k, b["provider"], f"{b['primary_mean']:.1f}",
                  f"{b['cross_mean']:.1f}", f"{b['mean_delta']:+.1f}")
    console.print(m)

    if rep["bias_by_group"]:
        g = Table(title="Per matched institution group - the political-preference probe")
        g.add_column("Group"); g.add_column("n", justify="right")
        g.add_column("Delta", justify="right", style="bold")
        for k, b in sorted(rep["bias_by_group"].items(), key=lambda kv: kv[1]["mean_delta"]):
            g.add_row(k, str(b["n"]), f"{b['mean_delta']:+.1f}")
        console.print(g)

    console.print(
        "\n[dim]A judge swap is safe when the level shifts uniformly and the order "
        "survives. Movement concentrated in one provider (family preference) or one "
        "institution group (political preference) is not safe, however cheap the "
        "judge is.[/dim]"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="crossjudge",
        description="Re-score archived responses with a second judge and report the deltas.",
    )
    p.add_argument("--run-id", required=True)
    p.add_argument("--judge", required=True, help="Cross-judge model id, e.g. deepseek/deepseek-v3.1-terminus")
    p.add_argument("--categories", default="", help="Comma-separated categories (default: all)")
    p.add_argument("--models", default="", help="Comma-separated model keys (default: all enabled)")
    p.add_argument("--limit", type=int, default=0, help="Max items per category")
    p.add_argument("--concurrency", type=int, default=0)
    p.add_argument("--judge-engine", default="native", choices=["native", "deepeval"])
    p.add_argument("--report-only", action="store_true",
                   help="Recompute the comparison from existing cross-judge scores, no API calls")
    args = p.parse_args(argv)

    load_env()
    categories = [c.strip() for c in args.categories.split(",") if c.strip()] or None
    models_filter = [m.strip() for m in args.models.split(",") if m.strip()] or None

    if args.report_only:
        registry = load_registry()
        specs = registry.enabled_models()
        if models_filter:
            specs = [s for s in specs if s.key in models_filter]
        items = load_all(categories)
        if args.limit:
            items = {c: i[: args.limit] for c, i in items.items()}
        root = run_dir(args.run_id)
        rep = compare(args.run_id, args.judge, items, specs,
                      root / "crossjudge" / slugify(args.judge), root)
    else:
        rep = run_cross(args.run_id, args.judge, categories, args.limit,
                        models_filter, args.concurrency or concurrency(), args.judge_engine)

    out = run_dir(args.run_id) / "crossjudge" / f"report-{slugify(args.judge)}.json"
    write_json(out, rep)
    print_report(rep)
    console.print(f"[green]Report written to {out}[/green]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
