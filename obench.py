"""overlooked-bench - one command for the whole pipeline.

    python obench.py run                     # full pipeline, today's date as run id
    python obench.py run --run-id 2026-10-01 # ...or a specific run id

`run` executes every stage in order and stops at the first failure:

    1. validate  dataset + config (no API calls, no cost)
    2. eval      generate raw responses, judge them, write summary.json
    3. charts    raw charts from summary.json
    4. social    branded 1600x900 cards via Playwright
    5. readme    human-readable summary written into the run folder
    6. site      rebuild the run index the leaderboard reads

Individual stages are runnable on their own - useful because stages 3-5 are free
and instant, so iterating on a chart never means re-running the models:

    python obench.py charts --run-id 2026-09-08
    python obench.py social --run-id 2026-09-08
    python obench.py site
    python obench.py validate
    python obench.py doctor

The API key is read from `.env` in the repo root and never leaves this machine.
It is not written into any run artefact, and `.env` is gitignored.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _run(label: str, args: list[str]) -> int:
    print(f"\n\033[1;34m==>\033[0m \033[1m{label}\033[0m")
    print(f"    {' '.join(args[1:])}\n")
    return subprocess.call(args, cwd=REPO_ROOT)


def cmd_validate(_: argparse.Namespace) -> int:
    return _run("Validating dataset and config", [PY, "-m", "harness.run_eval", "--dry-run"])


def cmd_doctor(_: argparse.Namespace) -> int:
    """Check the things that actually go wrong, before a long run does."""
    print("\n\033[1moverlooked-bench doctor\033[0m\n")
    ok = True

    print(f"  python            {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        print("    \033[31mFAIL\033[0m Python 3.11+ required")
        ok = False

    for mod in ("openai", "yaml", "matplotlib", "jinja2", "rich", "dotenv"):
        try:
            __import__(mod)
            print(f"  import {mod:<12} ok")
        except ImportError:
            print(f"  import {mod:<12} \033[31mMISSING\033[0m - pip install -r requirements.txt")
            ok = False

    try:
        import deepeval  # noqa: F401
        print("  import deepeval    ok (cross-validation engine available)")
    except ImportError:
        print("  import deepeval    \033[33mmissing\033[0m - the default `native` engine still works")

    env_file = REPO_ROOT / ".env"
    print(f"\n  .env              {'found' if env_file.exists() else 'NOT FOUND'}")
    if not env_file.exists():
        print("    \033[33mwarn\033[0m copy .env.example to .env and add your key")

    from harness.config import load_env, load_registry
    load_env()
    key = os.environ.get("AI_GATEWAY_API_KEY", "")
    if key:
        print(f"  AI_GATEWAY_API_KEY set ({key[:8]}...{key[-4:]}, {len(key)} chars)")
    else:
        print("  AI_GATEWAY_API_KEY \033[31mNOT SET\033[0m")
        ok = False

    try:
        registry = load_registry()
        enabled = registry.enabled_models()
        providers = sorted({m.provider for m in enabled})
        print(f"\n  models enabled    {len(enabled)} across {len(providers)} providers")
        print(f"    providers       {', '.join(providers)}")
        print(f"  judge             {registry.judge.model_id} ({registry.judge.prompt_version})")
        if any(m.model_id == registry.judge.model_id for m in enabled):
            print("    \033[33mwarn\033[0m the judge is also a model under test - see METHODOLOGY.md section 2")
    except Exception as exc:  # noqa: BLE001
        print(f"  registry          \033[31mFAILED\033[0m {exc}")
        ok = False

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            browser.close()
        print("  playwright        chromium ok")
    except Exception:  # noqa: BLE001
        print("  playwright        \033[33mnot ready\033[0m - python -m playwright install chromium")

    # Built outside the f-string: backslash escapes inside f-string expressions
    # are a syntax error before Python 3.12, and this project supports 3.11.
    verdict = "\033[32mAll required checks passed.\033[0m" if ok else "\033[31mSome checks failed.\033[0m"
    print(f"\n  {verdict}\n")
    return 0 if ok else 1


def cmd_eval(args: argparse.Namespace) -> int:
    cmd = [PY, "-m", "harness.run_eval", "--run-id", args.run_id]
    if args.models:
        cmd += ["--models", args.models]
    if args.categories:
        cmd += ["--categories", args.categories]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    if args.judge_engine:
        cmd += ["--judge-engine", args.judge_engine]
    if args.concurrency:
        cmd += ["--concurrency", str(args.concurrency)]
    return _run(f"Evaluating (run {args.run_id})", cmd)


def cmd_charts(args: argparse.Namespace) -> int:
    return _run("Generating charts",
                [PY, "charts/generate_charts.py", "--run-id", args.run_id])


def cmd_social(args: argparse.Namespace) -> int:
    return _run("Rendering branded social cards",
                [PY, "charts/render_social.py", "--run-id", args.run_id])


def cmd_readme(args: argparse.Namespace) -> int:
    return _run("Writing run README",
                [PY, "-m", "harness.run_readme", "--run-id", args.run_id])


def cmd_site(_: argparse.Namespace) -> int:
    return _run("Rebuilding site run index", [PY, "site/build_site.py"])


def cmd_run(args: argparse.Namespace) -> int:
    started = time.time()
    stages = [
        ("validate", cmd_validate),
        ("eval", cmd_eval),
        ("charts", cmd_charts),
        ("social", cmd_social),
        ("readme", cmd_readme),
        ("site", cmd_site),
    ]
    if args.skip:
        skip = {s.strip() for s in args.skip.split(",")}
        stages = [(name, fn) for name, fn in stages if name not in skip]

    for name, fn in stages:
        code = fn(args)
        if code != 0:
            print(f"\n\033[31mStage '{name}' failed (exit {code}). Stopping.\033[0m")
            print("Nothing already written has been modified - raw responses and any "
                  "scores already produced are still on disk, and re-running resumes "
                  "from where this stopped.")
            return code

    mins = (time.time() - started) / 60
    run_path = Path("data/runs") / args.run_id
    print(f"\n\033[32mDone in {mins:.1f} min.\033[0m")
    print(f"  results   {run_path}/summary.json")
    print(f"  charts    {run_path}/charts/")
    print(f"  social    {run_path}/social/")
    print("\nPreview the leaderboard:")
    print("  python -m http.server 8000   ->   http://localhost:8000/site/")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="obench",
        description="overlooked-bench pipeline runner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    today = time.strftime("%Y-%m-%d")

    def add_run_id(p: argparse.ArgumentParser) -> None:
        p.add_argument("--run-id", default=today, help=f"Run id (default: {today})")

    p_run = sub.add_parser("run", help="Full pipeline: validate, eval, charts, social, site")
    add_run_id(p_run)
    p_run.add_argument("--models", default="", help="Comma-separated model keys")
    p_run.add_argument("--categories", default="", help="Comma-separated categories")
    p_run.add_argument("--limit", type=int, default=0, help="Max items per category")
    p_run.add_argument("--judge-engine", default="", choices=["", "native", "deepeval"])
    p_run.add_argument("--concurrency", type=int, default=0)
    p_run.add_argument("--skip", default="", help="Comma-separated stages to skip")
    p_run.set_defaults(func=cmd_run)

    p_eval = sub.add_parser("eval", help="Evaluation only")
    add_run_id(p_eval)
    p_eval.add_argument("--models", default="")
    p_eval.add_argument("--categories", default="")
    p_eval.add_argument("--limit", type=int, default=0)
    p_eval.add_argument("--judge-engine", default="", choices=["", "native", "deepeval"])
    p_eval.add_argument("--concurrency", type=int, default=0)
    p_eval.set_defaults(func=cmd_eval)

    p_charts = sub.add_parser("charts", help="Raw charts only")
    add_run_id(p_charts)
    p_charts.set_defaults(func=cmd_charts)

    p_social = sub.add_parser("social", help="Branded social cards only")
    add_run_id(p_social)
    p_social.set_defaults(func=cmd_social)

    p_readme = sub.add_parser("readme", help="Human-readable run README only")
    add_run_id(p_readme)
    p_readme.set_defaults(func=cmd_readme)

    sub.add_parser("site", help="Rebuild the site run index").set_defaults(func=cmd_site)
    sub.add_parser("validate", help="Validate dataset and config, no API calls").set_defaults(
        func=cmd_validate)
    sub.add_parser("doctor", help="Check environment, keys, and model registry").set_defaults(
        func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    raise SystemExit(main())
