"""Main entrypoint for an overlooked-bench evaluation run.

    python -m harness.run_eval --run-id 2026-09-08

PHASES
------
  1. generate  Ask every enabled model every item. Write the raw, unedited
               response to `runs/<id>/raw/` immediately.
  2. score     Read raw responses BACK FROM DISK and judge them into
               `runs/<id>/scored/`.
  3. summarise Aggregate `scored/` into `runs/<id>/summary.json`.

The scoring phase deliberately re-reads raw output from disk rather than using
the objects still in memory from phase 1. That is slightly wasteful and it is
the point: it makes it structurally impossible for scoring code to score
something other than what was archived, and it means `--stage score` can be
re-run months later against the same raw files and must reproduce the same
numbers. Raw files are never modified or deleted by this program.

Runs are resumable. An existing raw file is reused rather than re-requested, so
an interrupted run costs nothing to continue. `--force-regenerate` starts a fresh
run id instead of overwriting, because overwriting raw output would destroy the
audit trail that makes this project worth trusting.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
)
from rich.table import Table

from . import METHODOLOGY_VERSION, __version__
from .analysis import build_summary
from .config import (
    CATEGORY_LABELS, ModelSpec, concurrency, load_env, load_registry, run_dir,
)
from .dataset import Item, dataset_fingerprint, load_all
from .judge import ScoreRecord, judge_provenance, score as judge_score
from .metrics import all_rubric_hashes
from .models import generate

console = Console()


# ---------------------------------------------------------------------------
# Paths & IO
# ---------------------------------------------------------------------------


def raw_path(root: Path, model_key: str, category: str, item_id: str) -> Path:
    return root / "raw" / model_key / category / f"{item_id}.json"


def scored_path(root: Path, model_key: str, category: str, item_id: str) -> Path:
    return root / "scored" / model_key / category / f"{item_id}.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Write-then-rename: a crash mid-write can never leave a half-written record
    # that later reads as valid data.
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Phase 1 — generation
# ---------------------------------------------------------------------------


def phase_generate(
    root: Path,
    models: list[ModelSpec],
    items_by_category: dict[str, list[Item]],
    workers: int,
    force: bool,
) -> list[dict[str, Any]]:
    """Collect raw model responses. Writes each to disk as it arrives."""
    jobs: list[tuple[ModelSpec, Item]] = []
    reused = 0
    for spec in models:
        for category, items in items_by_category.items():
            for item in items:
                path = raw_path(root, spec.key, category, item.id)
                if path.exists() and not force:
                    reused += 1
                    continue
                jobs.append((spec, item))

    if reused:
        console.print(f"[dim]Reusing {reused} raw response(s) already on disk.[/dim]")
    if not jobs:
        console.print("[dim]Nothing to generate.[/dim]")
        return load_raw(root, models, items_by_category)

    def work(spec: ModelSpec, item: Item) -> dict[str, Any]:
        completion = generate(spec, item.prompt)
        record = completion.to_dict()
        record.update(
            {
                "item_id": item.id,
                "category": item.category,
                "item_content_hash": item.content_hash,
                "harness_version": __version__,
                "methodology_version": METHODOLOGY_VERSION,
            }
        )
        # Raw output is archived the moment it exists, before any scoring code
        # has had a chance to touch it.
        write_json(raw_path(root, spec.key, item.category, item.id), record)
        return record

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]Generating"), BarColumn(),
        MofNCompleteColumn(), TimeElapsedColumn(), console=console,
    ) as progress:
        task = progress.add_task("gen", total=len(jobs))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(work, s, i): (s, i) for s, i in jobs}
            for future in as_completed(futures):
                spec, item = futures[future]
                try:
                    rec = future.result()
                    if not rec.get("ok"):
                        console.print(
                            f"[yellow]gen fail[/yellow] {spec.key}/{item.id}: "
                            f"{str(rec.get('error'))[:120]}"
                        )
                except Exception as exc:  # noqa: BLE001
                    console.print(f"[red]gen error[/red] {spec.key}/{item.id}: {exc}")
                progress.advance(task)

    return load_raw(root, models, items_by_category)


def load_raw(
    root: Path, models: list[ModelSpec], items_by_category: dict[str, list[Item]]
) -> list[dict[str, Any]]:
    """Read the archived raw responses back off disk."""
    out: list[dict[str, Any]] = []
    for spec in models:
        for category, items in items_by_category.items():
            for item in items:
                rec = read_json(raw_path(root, spec.key, category, item.id))
                if rec is not None:
                    out.append(rec)
    return out


# ---------------------------------------------------------------------------
# Phase 2 — scoring
# ---------------------------------------------------------------------------


def phase_score(
    root: Path,
    models: list[ModelSpec],
    items_by_category: dict[str, list[Item]],
    judge_spec,
    engine: str,
    workers: int,
    force: bool,
) -> list[ScoreRecord]:
    item_index = {i.id: i for items in items_by_category.values() for i in items}

    jobs: list[tuple[str, Item, str]] = []
    cached: list[ScoreRecord] = []
    missing_raw = 0

    for spec in models:
        for category, items in items_by_category.items():
            for item in items:
                spath = scored_path(root, spec.key, category, item.id)
                if spath.exists() and not force:
                    prev = read_json(spath)
                    if prev:
                        cached.append(ScoreRecord(**prev))
                        continue
                raw = read_json(raw_path(root, spec.key, category, item.id))
                if raw is None:
                    missing_raw += 1
                    continue
                jobs.append((spec.key, item, raw.get("text", "")))

    if missing_raw:
        console.print(
            f"[yellow]{missing_raw} item(s) have no raw response and cannot be scored.[/yellow]"
        )
    if cached:
        console.print(f"[dim]Reusing {len(cached)} existing score(s).[/dim]")

    results: list[ScoreRecord] = list(cached)
    if not jobs:
        return results

    def work(model_key: str, item: Item, text: str) -> ScoreRecord:
        rec = judge_score(judge_spec, item, model_key, text, engine=engine)
        write_json(scored_path(root, model_key, item.category, item.id), rec.to_dict())
        return rec

    with Progress(
        SpinnerColumn(), TextColumn("[bold magenta]Judging  "), BarColumn(),
        MofNCompleteColumn(), TimeElapsedColumn(), console=console,
    ) as progress:
        task = progress.add_task("judge", total=len(jobs))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(work, mk, it, tx): (mk, it) for mk, it, tx in jobs}
            for future in as_completed(futures):
                model_key, item = futures[future]
                try:
                    rec = future.result()
                    results.append(rec)
                    if not rec.ok:
                        console.print(
                            f"[yellow]judge issue[/yellow] {model_key}/{item.id}: {rec.error}"
                        )
                except Exception as exc:  # noqa: BLE001
                    console.print(f"[red]judge error[/red] {model_key}/{item.id}: {exc}")
                progress.advance(task)

    _ = item_index
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_leaderboard(summary: dict[str, Any]) -> None:
    table = Table(title=f"overlooked-bench {summary['run_id']} — overall index (0-100)")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Model")
    table.add_column("Provider", style="dim")
    table.add_column("Overall", justify="right", style="bold")
    for cat in summary["headline_categories"]:
        table.add_column(CATEGORY_LABELS[cat].split(" ")[0][:6], justify="right")

    for row in summary["leaderboard"]:
        block = summary["results"][row["model_key"]]
        cells = [
            str(row["rank"]), row["display"], row["provider"], f"{row['overall_index']:.1f}",
        ]
        for cat in summary["headline_categories"]:
            val = block["categories"].get(cat, {}).get("mean")
            cells.append(f"{val:.1f}" if val is not None else "-")
        table.add_row(*cells)
    console.print(table)

    diag = summary["diagnostics"]
    if diag.get("truncation_warning"):
        console.print(f"[bold red]TRUNCATION WARNING:[/bold red] {diag['truncation_warning']}")
        console.print(f"[red]  affected: {diag['truncated_by_model']}[/red]")
    if diag.get("calibration_warning"):
        console.print(f"[bold red]CALIBRATION WARNING:[/bold red] {diag['calibration_warning']}")
    console.print(
        f"[dim]judge={summary['judge']['judge_model']} "
        f"engine={summary['judge']['metric_engine']} "
        f"methodology={summary['methodology_version']} "
        f"judge_errors={diag['judge_error_rate']}% "
        f"gen_errors={diag['generation_error_rate']}% "
        f"cost=${summary['total_cost_usd']:.2f}[/dim]"
    )

    asym = summary.get("institutional_asymmetry") or {}
    if asym:
        at = Table(title="Institutional criticism — asymmetry index (0 = consistent)")
        at.add_column("Model")
        at.add_column("Mean criticism", justify="right")
        at.add_column("Asymmetry", justify="right", style="bold")
        for key, block in sorted(
            asym.items(), key=lambda kv: kv[1]["asymmetry_index"], reverse=True
        ):
            at.add_row(
                summary["results"][key]["display"],
                f"{block['mean_criticism_score']:.1f}",
                f"{block['asymmetry_index']:.1f}",
            )
        console.print(at)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="run_eval",
        description="Run the overlooked-bench evaluation harness.",
    )
    p.add_argument("--run-id", default=time.strftime("%Y-%m-%d"),
                   help="Run folder name under data/runs/ (default: today, UTC-naive local date)")
    p.add_argument("--models", default="", help="Comma-separated model keys (default: all enabled)")
    p.add_argument("--categories", default="", help="Comma-separated categories (default: all)")
    p.add_argument("--limit", type=int, default=0, help="Max items per category (0 = all)")
    p.add_argument("--judge-engine", default="native", choices=["native", "deepeval"])
    p.add_argument("--stage", default="all", choices=["all", "generate", "score", "summarise"])
    p.add_argument("--concurrency", type=int, default=0, help="Override OB_CONCURRENCY")
    p.add_argument("--force-regenerate", action="store_true",
                   help="Re-request responses already archived. Use a NEW --run-id instead "
                        "unless you intend to replace an in-progress run.")
    p.add_argument("--force-rescore", action="store_true", help="Re-judge already-scored items")
    p.add_argument("--dry-run", action="store_true",
                   help="Validate config and dataset, print the plan, make no API calls")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env()

    registry = load_registry()
    all_models = registry.enabled_models()
    if args.models:
        wanted = [m.strip() for m in args.models.split(",") if m.strip()]
        all_models = [registry.by_key(k) for k in wanted]
    if not all_models:
        console.print("[red]No models selected. Check `enabled:` flags in data/models.yaml.[/red]")
        return 2

    categories = [c.strip() for c in args.categories.split(",") if c.strip()] or None
    items_by_category = load_all(categories)
    if args.limit:
        items_by_category = {c: i[: args.limit] for c, i in items_by_category.items()}

    workers = args.concurrency or concurrency()
    root = run_dir(args.run_id)
    fingerprint = dataset_fingerprint(items_by_category)
    n_items = sum(len(v) for v in items_by_category.values())

    console.rule(f"[bold]overlooked-bench[/bold] run {args.run_id}")
    console.print(
        f"models={len(all_models)}  items={n_items}  calls={len(all_models) * n_items * 2}  "
        f"judge={registry.judge.model_id}  engine={args.judge_engine}  workers={workers}"
    )
    console.print(f"[dim]dataset_fingerprint={fingerprint}  methodology={METHODOLOGY_VERSION}[/dim]")

    if args.dry_run:
        for cat, items in items_by_category.items():
            console.print(f"  {cat}: {len(items)} items")
        console.print("[green]Dry run OK — config and dataset are valid. No API calls made.[/green]")
        return 0

    missing_keys = sorted({m.api_key_env for m in all_models if not m.api_key})
    if missing_keys:
        console.print(
            f"[red]Missing API key env var(s): {', '.join(missing_keys)}.[/red]\n"
            f"Copy .env.example to .env and fill it in."
        )
        return 2

    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "manifest.json", {
        "run_id": args.run_id,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "harness_version": __version__,
        "methodology_version": METHODOLOGY_VERSION,
        "dataset_fingerprint": fingerprint,
        "item_counts": {c: len(i) for c, i in items_by_category.items()},
        "models": [
            {"key": m.key, "model_id": m.model_id, "provider": m.provider,
             "tier": m.tier, "temperature": m.temperature, "max_tokens": m.max_tokens}
            for m in all_models
        ],
        "judge": judge_provenance(registry.judge, args.judge_engine),
        "rubric_hashes": all_rubric_hashes(),
        "limit_per_category": args.limit or None,
        "python": sys.version.split()[0],
    })

    generations: list[dict[str, Any]] = []
    if args.stage in ("all", "generate"):
        generations = phase_generate(
            root, all_models, items_by_category, workers, args.force_regenerate
        )
    else:
        generations = load_raw(root, all_models, items_by_category)

    scores: list[ScoreRecord] = []
    if args.stage in ("all", "score"):
        scores = phase_score(
            root, all_models, items_by_category, registry.judge,
            args.judge_engine, workers, args.force_rescore,
        )
    elif args.stage == "summarise":
        for spec in all_models:
            for category, items in items_by_category.items():
                for item in items:
                    rec = read_json(scored_path(root, spec.key, category, item.id))
                    if rec:
                        scores.append(ScoreRecord(**rec))

    if args.stage == "generate":
        console.print(f"[green]Raw responses archived to {root / 'raw'}[/green]")
        return 0

    if not scores:
        console.print("[red]No scores produced — cannot summarise.[/red]")
        return 1

    summary = build_summary(
        run_id=args.run_id,
        models=all_models,
        items_by_category=items_by_category,
        scores=scores,
        generations=generations,
        judge_block=judge_provenance(registry.judge, args.judge_engine),
        dataset_fingerprint=fingerprint,
    )
    write_json(root / "summary.json", summary)
    print_leaderboard(summary)
    console.print(f"[green]Summary written to {root / 'summary.json'}[/green]")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    raise SystemExit(main())
