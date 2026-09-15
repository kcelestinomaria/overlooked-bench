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
the objects still in memory from phase 1. The redundancy is deliberate: it makes
it structurally impossible for scoring code to score something other than what
was archived, and it means `--stage score` can be
re-run months later against the same raw files and must reproduce the same
numbers. Raw files are never modified or deleted by this program.

Runs are resumable. An existing raw file is reused rather than re-requested, so
an interrupted run costs nothing to continue. `--force-regenerate` starts a fresh
run id instead of overwriting, because overwriting raw output would destroy the
audit trail that makes this project worth trusting.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

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


def usable_raw(rec: dict[str, Any] | None) -> bool:
    """True if an archived raw record is a real answer that can be judged.

    `ok` alone is not enough. A reasoning model can return a transport-level
    success that contains zero characters, having spent its entire completion
    budget on internal reasoning before emitting any visible text - run
    2026-09-08 has exactly that for claude-sonnet-5 on org-001, at 8000
    completion tokens and `finish_reason: length`.

    Such a record is scored 0 on every dimension, which is indistinguishable in
    the leaderboard from a model that answered badly. Worse, the old predicate
    (`rec.get("ok")`) treated it as finished work, so every subsequent resume
    skipped it and the artefact became permanent. Requiring visible text means a
    raised max_tokens ceiling actually re-requests these instead of silently
    inheriting the zero.
    """
    if rec is None or not rec.get("ok"):
        return False
    return bool((rec.get("text") or "").strip())


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Phase 1 - generation
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
    retried = 0
    for spec in models:
        for category, items in items_by_category.items():
            for item in items:
                path = raw_path(root, spec.key, category, item.id)
                if path.exists() and not force:
                    prev = read_json(path)
                    # Resume must not treat a FAILED call as finished work. A
                    # provider outage, a rate limit, or an exhausted account
                    # writes a record with ok=false, and caching that as
                    # "already generated" would bake a transient failure into
                    # the run permanently - every later resume would skip it and
                    # the model would be scored 0 for an error that was ours.
                    if usable_raw(prev):
                        reused += 1
                        continue
                    retried += 1
                jobs.append((spec, item))
    if retried:
        console.print(f"[yellow]Retrying {retried} previously-failed generation(s).[/yellow]")

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


def import_raw(
    root: Path,
    source_run: str,
    models: list[ModelSpec],
    items_by_category: dict[str, list[Item]],
    fingerprint: str,
) -> tuple[int, int]:
    """Copy archived raw responses from an earlier run into this one.

    Run folders are immutable, so a scoring-side fix (a corrected rubric, a
    judge-prompt change, a judge that failed to parse) needs a NEW run id.
    Re-asking every model the same questions to get byte-identical answers would
    cost the full generation budget to change nothing, so the raw archive is
    carried over instead.

    Two guards keep that honest. The dataset fingerprint of the source run must
    match this one, or the responses answer different prompts and the import is
    refused. And only records that pass `usable_raw` are copied, so an empty or
    failed response is re-requested under this run's model config rather than
    inherited. `raw_reused_from` is written into the manifest either way, so a
    reader can always tell which responses this run paid for.
    """
    src_root = run_dir(source_run)
    src_manifest = read_json(src_root / "manifest.json") or {}
    src_fp = src_manifest.get("dataset_fingerprint")
    if src_fp != fingerprint:
        raise SystemExit(
            f"Refusing --raw-from {source_run}: dataset fingerprint {src_fp} does not "
            f"match this run's {fingerprint}. Those responses answer different prompts."
        )

    copied = 0
    skipped = 0
    for spec in models:
        for category, items in items_by_category.items():
            for item in items:
                dest = raw_path(root, spec.key, category, item.id)
                if dest.exists():
                    # Already imported on an earlier invocation. Count it from
                    # the marker written into the record rather than skipping
                    # it, so re-running a later stage reports the same
                    # provenance instead of a misleading zero.
                    existing = read_json(dest) or {}
                    if existing.get("imported_from_run") == source_run:
                        copied += 1
                    else:
                        skipped += 1
                    continue
                rec = read_json(raw_path(src_root, spec.key, category, item.id))
                if not usable_raw(rec):
                    skipped += 1
                    continue
                rec = dict(rec or {})
                rec["imported_from_run"] = source_run
                write_json(dest, rec)
                copied += 1
    return copied, skipped


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
# Phase 2 - scoring
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
    retried = 0

    for spec in models:
        for category, items in items_by_category.items():
            for item in items:
                spath = scored_path(root, spec.key, category, item.id)
                if spath.exists() and not force:
                    prev = read_json(spath)
                    # Same rule as generation: only a SUCCESSFUL score counts as
                    # done. A judge call that 402'd, timed out, or came back
                    # unparseable must be re-judged on the next resume, not
                    # cached as a permanent zero.
                    if prev and prev.get("ok"):
                        cached.append(ScoreRecord(**prev))
                        continue
                    if prev:
                        retried += 1
                raw = read_json(raw_path(root, spec.key, category, item.id))
                # A raw record that failed to generate has no text to judge.
                # Scoring it would manufacture a 0 for a model that was never
                # actually asked; leave it out so the gap stays visible.
                if raw is None or not raw.get("ok"):
                    missing_raw += 1
                    continue
                jobs.append((spec.key, item, raw.get("text", "")))

    if retried:
        console.print(f"[yellow]Re-judging {retried} previously-failed score(s).[/yellow]")

    if missing_raw:
        console.print(
            f"[yellow]{missing_raw} item(s) have no usable raw response and were not "
            f"scored. They are excluded from the run rather than scored 0 - check "
            f"`n` per category in summary.json.[/yellow]"
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
    table = Table(title=f"overlooked-bench {summary['run_id']} - overall index (0-100)")
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
        at = Table(title="Institutional criticism - asymmetry index (0 = consistent)")
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
    p.add_argument("--raw-from", default="",
                   help="Reuse archived raw responses from this run id instead of "
                        "re-querying. Requires an identical dataset fingerprint. Used to "
                        "re-judge a run under a corrected rubric without paying for "
                        "generation twice; recorded in the manifest as raw_reused_from.")
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
        console.print("[green]Dry run OK - config and dataset are valid. No API calls made.[/green]")
        return 0

    missing_keys = sorted({m.api_key_env for m in all_models if not m.api_key})
    if missing_keys:
        console.print(
            f"[red]Missing API key env var(s): {', '.join(missing_keys)}.[/red]\n"
            f"Copy .env.example to .env and fill it in."
        )
        return 2

    root.mkdir(parents=True, exist_ok=True)

    # The manifest is rewritten on every invocation, including a later
    # `--stage score` on an existing run. Provenance already recorded there must
    # survive that rewrite, or a run whose raw output was imported would lose the
    # record of it the moment it was re-judged.
    prior_manifest = read_json(root / "manifest.json") or {}
    imported = prior_manifest.get("raw_reused_from")

    if args.raw_from:
        if args.raw_from == args.run_id:
            console.print("[red]--raw-from must name a different run than --run-id.[/red]")
            return 2
        copied, skipped = import_raw(
            root, args.raw_from, all_models, items_by_category, fingerprint
        )
        imported = {"run_id": args.raw_from, "responses_copied": copied,
                    "responses_regenerated": skipped}
        console.print(
            f"[dim]Imported {copied} raw response(s) from {args.raw_from}; "
            f"{skipped} unusable or missing and will be regenerated.[/dim]"
        )

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
        "raw_reused_from": imported,
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
        console.print("[red]No scores produced - cannot summarise.[/red]")
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
