"""Stage 2 of the chart pipeline: branded social cards, rendered unattended.

    python charts/render_social.py --run-id 2026-09-08

Takes each raw chart from `data/runs/<id>/charts/`, drops it into the fixed
branded template, and screenshots it to `data/runs/<id>/social/<name>.png` at
1600x900 via Playwright.

WHY THIS IS CODE AND NOT A DESIGN TOOL
--------------------------------------
The obvious alternative is exporting the chart and finishing it by hand in a
design tool. That breaks two things this project depends on. It puts a manual
step between the scored data and the published image, so the image can no longer
be regenerated from a checkout — and a number that cannot be regenerated cannot
be audited. And it does not survive a monthly cadence: the first busy month, the
cards do not get made, or they get made differently.

So the branding lives in a Jinja template under version control, and the only
way to change how a card looks is a commit.

Output names are predictable — `<chart-name>.png`, matching the raw chart — so a
posting workflow can pick up `ethics-philosophy.png` without renaming anything.

Requires a one-time browser install:  python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "data" / "runs"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

CARD_WIDTH = 1600
CARD_HEIGHT = 900

REPO_URL = "github.com/overlooked-bench/overlooked-bench"

# One line, written for someone who is seeing this image with no caption and no
# context, forwarded from someone they follow. It has to answer "what am I
# looking at and why should I believe it" on its own.
DEFAULT_METHODOLOGY_NOTE = (
    "Scored by an LLM judge against published per-category rubrics. Every raw model "
    "response, every judge score, and the judge's own reasoning are committed to the "
    "repository for this run — the numbers above are checkable, not asserted."
)

# Per-chart taglines. Keyed by chart filename stem.
TAGLINES: dict[str, str] = {
    "overall": "What frontier models do outside the benchmarked world",
    "ethics-philosophy": "Reasoning on contested moral questions — not multiple choice",
    "niche-academic": "Domains with thin literatures and no ground truth to memorise",
    "org-enterprise": "Tasks for small, non-US, and non-profit organisations",
    "education": "The teacher workload and the pathways that are not university",
    "institutional-criticism": "Who gets criticised, and who gets the benefit of the doubt",
    "calibration-general": "Control track — confirms the harness works, not a result",
    "institutional-asymmetry": "Who gets criticised, and who gets the benefit of the doubt",
    "criticism-vs-asymmetry": "Willingness to criticise, and how unevenly it is applied",
    "trend-overall": "Tracked monthly, same rubrics, same judge",
    "trend-institutional-criticism": "Tracked monthly, same rubrics, same judge",
}


def load_summary(run_id: str) -> dict[str, Any]:
    path = RUNS_DIR / run_id / "summary.json"
    if not path.exists():
        raise SystemExit(f"ERROR: no summary at {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def render_html(
    env: Environment, chart_path: Path, summary: dict[str, Any], methodology_note: str
) -> str:
    b64 = base64.b64encode(chart_path.read_bytes()).decode("ascii")
    stem = chart_path.stem
    template = env.get_template("social_card.html.j2")
    return template.render(
        title=stem,
        tagline=TAGLINES.get(stem, "Benchmarking what the benchmarks miss"),
        run_id=summary["run_id"],
        n_models=summary["n_models"],
        n_items=sum(summary["item_counts"].values()),
        methodology_note=methodology_note,
        repo_url=REPO_URL,
        chart_b64=b64,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render branded social cards from raw charts.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--charts", default="", help="Input dir (default: data/runs/<id>/charts)")
    parser.add_argument("--out", default="", help="Output dir (default: data/runs/<id>/social)")
    parser.add_argument("--keep-html", action="store_true",
                        help="Also write the intermediate HTML, for debugging the template")
    args = parser.parse_args(argv)

    summary = load_summary(args.run_id)
    charts_dir = Path(args.charts) if args.charts else RUNS_DIR / args.run_id / "charts"
    out_dir = Path(args.out) if args.out else RUNS_DIR / args.run_id / "social"

    chart_files = sorted(charts_dir.glob("*.png"))
    if not chart_files:
        print(f"ERROR: no charts in {charts_dir}. Run generate_charts.py first.", file=sys.stderr)
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "ERROR: Playwright is not installed.\n"
            "  pip install -r requirements.txt\n"
            "  python -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,  # a missing template variable must fail the build,
        autoescape=True,            # not render a card with a blank field
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    note = summary.get("methodology_note") or DEFAULT_METHODOLOGY_NOTE
    written: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--force-color-profile=srgb", "--font-render-hinting=none"])
        page = browser.new_page(
            viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT},
            device_scale_factor=1,
        )
        for chart in chart_files:
            html = render_html(env, chart, summary, note)
            if args.keep_html:
                (out_dir / f"{chart.stem}.html").write_text(html, encoding="utf-8")
            page.set_content(html, wait_until="load")
            # The chart is an inline data URI, so there is no network wait — but
            # give the layout one frame to settle before capturing.
            page.wait_for_timeout(120)
            target = out_dir / f"{chart.stem}.png"
            page.screenshot(path=str(target), clip={
                "x": 0, "y": 0, "width": CARD_WIDTH, "height": CARD_HEIGHT,
            })
            written.append(target)
            print(f"  wrote {target.relative_to(REPO_ROOT)}  ({CARD_WIDTH}x{CARD_HEIGHT})")
        browser.close()

    print(f"{len(written)} social card(s) written to {out_dir.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
