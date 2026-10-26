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
be regenerated from a checkout - and a number that cannot be regenerated cannot
be audited. And it does not survive a monthly cadence: the first busy month, the
cards do not get made, or they get made differently.

So the branding lives in a Jinja template under version control, and the only
way to change how a card looks is a commit.

Output names are predictable - `<chart-name>.png`, matching the raw chart - so a
posting workflow can pick up `ethics-philosophy.png` without renaming anything.

Requires a one-time browser install:  python -m playwright install chromium
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "data" / "runs"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

CARD_WIDTH = 1600
CARD_HEIGHT = 900

REPO_URL = "github.com/kcelestinomaria/overlooked-bench"

# One line, written for someone who is seeing this image with no caption and no
# context, forwarded from someone they follow. It has to answer "what am I
# looking at and why should I believe it" on its own.
DEFAULT_METHODOLOGY_NOTE = (
    "Scored by an LLM judge against published per-category rubrics. Every raw model "
    "response, every judge score, and the judge's own reasoning are committed to the "
    "repository for this run - the numbers above are checkable, not asserted."
)

# Per-chart taglines. Keyed by chart filename stem.
TAGLINES: dict[str, str] = {
    "overall": "What frontier models do outside the benchmarked world",
    "ethics-philosophy": "Reasoning on contested moral questions - not multiple choice",
    "niche-academic": "Domains with thin literatures and no ground truth to memorise",
    "org-enterprise": "Tasks for small, non-US, and non-profit organisations",
    "education": "The teacher workload and the pathways that are not university",
    "institutional-criticism": "Who gets criticised, and who gets the benefit of the doubt",
    "calibration-general": "Control track - confirms the harness works, not a result",
    "institutional-asymmetry": "Who gets criticised, and who gets the benefit of the doubt",
    "criticism-vs-asymmetry": "Willingness to criticise, and how unevenly it is applied",
    "trend-overall": "Tracked monthly, same rubrics, same judge",
    "trend-institutional-criticism": "Tracked monthly, same rubrics, same judge",
    "software-engineering-production": "Engineering plans a real team could ship, inside its real constraints",
    "production-constraint-violations": "Told the constraint. Broke it anyway.",
    "production-reject-leaderboard": "Plans a constrained team would have to send back",
    "production-judge-vs-verifier": "Why one LLM judge is not enough to call a violation",
    "crossjudge-software-engineering-production": "Same responses, two judges: where the score depends on who scores it",
    "crossjudge-institutional-criticism": "Same responses, two judges: where the score depends on who scores it",
    "production-violation-heatmap": "Every production task, every model, every broken constraint",
    "production-dimension-radar": "Constraint fidelity, realism, actionability, maintainability",
    "production-matched-organisation": "Nairobi, Austin, Lisbon: same task, same constraints",
    "production-matched-jurisdiction": "Germany, California, Kenya: same feature, same constraints",
    "production-region-split": "Does where you are change how the rules are kept?",
}

PRODUCTION = "software-engineering-production"

# A card shows at most this many quote cards, and at most one per model and one
# per item, so a thread cannot be built out of one model's worst afternoon.
MAX_QUOTE_CARDS = 6
MAX_CONTRAST_CARDS = 3
MAX_QUOTE_WORDS = 45

QUOTE_NOTE = (
    "Constraint taken from the prompt. Violation confirmed by the LLM judge AND an "
    "independent evaluation model. The quote is machine-checked as verbatim against "
    "the archived response at the path below - open it and read the whole answer."
)


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


# ---------------------------------------------------------------------------
# Quote, side-by-side and thread cards (software-engineering-production)
# ---------------------------------------------------------------------------


def _production_items() -> dict[str, Any]:
    sys.path.insert(0, str(REPO_ROOT))
    from harness.dataset import load_category
    return {i.id: i for i in load_category(PRODUCTION)}


def _raw_rel(run_id: str, model_key: str, item_id: str) -> str:
    return f"data/runs/{run_id}/raw/{model_key}/{PRODUCTION}/{item_id}.json"


def _raw_text(run_id: str, model_key: str, item_id: str) -> str:
    path = REPO_ROOT / _raw_rel(run_id, model_key, item_id)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("text") or ""


def _opening(text: str, limit: int = 240) -> str:
    """First prose sentence(s) of a response, verbatim, for the 'kept' side.

    Headings, table rows and list markers are skipped so the excerpt is a
    sentence the model wrote, not a title. Cut at a sentence end where possible;
    if a cut is unavoidable it ends in an ellipsis, which a reader recognises
    as an excerpt.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#|>-*`" or line[:2].rstrip(".").isdigit():
            continue
        line = line.replace("**", "")
        if len(line) <= limit:
            return line
        cut = line[:limit]
        end = max(cut.rfind(". "), cut.rfind("; "))
        return cut[: end + 1] if end > 80 else cut.rsplit(" ", 1)[0] + "..."
    return ""


def _prose_lines(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*0123456789. ").replace("**", "").strip()
        if len(line) >= 20 and line[0] not in "#|>`":
            out.append(line)
    return out


def _following_line(text: str, quote: str, limit: int = 160) -> str:
    """The line right after the quoted one, verbatim, so a reader sees what the
    model said next. Shown as context, never as part of the quote."""
    from harness.quotes import normalise
    lines = _prose_lines(text)
    q = normalise(quote)[:40]
    for i, line in enumerate(lines):
        if q and q in normalise(line) and i + 1 < len(lines):
            nxt = lines[i + 1]
            return nxt if len(nxt) <= limit else ""
    return ""


def _relevant_line(text: str, constraint_text: str, limit: int = 240) -> str:
    """For the 'kept' side: the first line that mentions the constraint's own
    figures (e.g. '30' for a 30-day limit), verbatim. Falls back to the
    opening sentence when the constraint carries no number."""
    nums = re.findall(r"\d[\d,.]*", constraint_text)
    for line in _prose_lines(text):
        if nums and any(re.search(rf"(?<![\d]){re.escape(n)}(?![\d])", line) for n in nums):
            return line if len(line) <= limit else line[:limit].rsplit(" ", 1)[0] + "..."
    return _opening(text, limit)


def select_quotes(summary: dict[str, Any], items: dict[str, Any]) -> list[dict[str, Any]]:
    """Pick verified examples, spread across models and items."""
    sys.path.insert(0, str(REPO_ROOT))
    from harness.quotes import quote_in_text

    chosen: list[dict[str, Any]] = []
    seen_models: set[str] = set()
    seen_items: set[str] = set()
    for ex in (summary.get("constraint_violations") or {}).get("examples", []):
        if ex["model_key"] in seen_models or ex["item_id"] in seen_items:
            continue
        if len(ex["evidence"].split()) > MAX_QUOTE_WORDS:
            continue
        # Re-verify at render time against the file on disk, not the summary:
        # the card must be true of the archive as committed.
        try:
            raw = _raw_text(summary["run_id"], ex["model_key"], ex["item_id"])
        except OSError:
            continue
        if not quote_in_text(ex["evidence"], raw):
            continue
        chosen.append(ex)
        seen_models.add(ex["model_key"])
        seen_items.add(ex["item_id"])
        if len(chosen) >= MAX_QUOTE_CARDS:
            break
    return chosen


def takeaway_points(summary: dict[str, Any], items: dict[str, Any]) -> list[dict[str, str]]:
    """The 'what this means' card. Every number is computed here from summary.json."""
    cv = summary.get("constraint_violations") or {}
    bm = cv.get("by_model") or {}
    if not bm:
        return []
    disp = {k: v["display"] for k, v in summary["results"].items()}
    rejects = sorted((b["reject_rate"], k) for k, b in bm.items())
    n_any = sum(1 for b in bm.values() if b["confirmed"] > 0)
    median = rejects[len(rejects) // 2][0]

    # Which single constraint was broken by the most models.
    counts: dict[tuple[str, str], int] = {}
    for ex in cv.get("examples", []):
        counts[(ex["item_id"], ex["constraint_id"])] = counts.get((ex["item_id"], ex["constraint_id"]), 0) + 1
    worst = max(counts.items(), key=lambda kv: kv[1]) if counts else None
    agree = [b["agreement_rate"] for b in bm.values() if b.get("agreement_rate") is not None]
    kappa = cv.get("cohens_kappa_judge_vs_verifier")
    n_tasks = max(b["n_responses"] for b in bm.values())

    # Ties are named as ties: "Best: X" over a six-way tie at 0% would single out
    # one model the data does not single out.
    best_val = rejects[0][0]
    best = [disp[k] for v, k in rejects if v == best_val]
    best_txt = (f"{len(best)} of {len(bm)} models had no confirmed violation"
                if best_val == 0 and len(best) > 1 else
                f"Best: {', '.join(best)} ({best_val:.0f}% sent back)")
    tj = sum(b["judge_violations"] for b in bm.values())
    tv = sum(b["verifier_violations"] for b in bm.values())
    tc = sum(b["confirmed"] for b in bm.values())
    points = [{
        "text": f"{n_any} of {len(bm)} models broke at least one constraint they were explicitly given.",
        "sub": f"The median model's plan would be sent back on {median:.0f}% of {n_tasks} tasks.",
    }, {
        "text": (f"{best_txt}. Most: {disp[rejects[-1][1]]} "
                 f"({rejects[-1][0]:.0f}% of tasks)."),
        "sub": "Same prompts, same rubric, same judge and verifier for every model.",
    }, {
        "text": (f"One LLM judge flagged {tj} violations; an independent verifier flagged {tv}; "
                 f"they agreed on {tc}."),
        "sub": "A benchmark with a single judge would have published its own count. Check the judge.",
    }]
    if worst and worst[1] > 1:
        (iid, cid), n = worst
        c = next(c for c in items[iid].constraints if c["id"] == cid)
        points.append({
            "text": f"Most-broken rule: “{c['text']}” - {n} models, on {iid}.",
            "sub": items[iid].title or "",
        })
    points.append({
        "text": "Spell out your constraints - and check the plan against them before you build it.",
        "sub": (f"Judge and verifier agreed on {sum(agree) / len(agree):.0f}% of checks, "
                f"kappa {kappa if kappa is not None else 'n/a'} on which ones broke a rule. "
                f"Every quote links to the raw response."),
    })
    return points


def render_production_cards(
    page, env: Environment, summary: dict[str, Any], out_dir: Path, note: str
) -> list[dict[str, Any]]:
    """Quote cards, side-by-side cards and a 4-card thread. Returns manifest rows."""
    cv = summary.get("constraint_violations") or {}
    if not cv.get("by_model"):
        return []
    items = _production_items()
    run_id = summary["run_id"]
    disp = {k: v["display"] for k, v in summary["results"].items()}
    label = summary["category_labels"].get(PRODUCTION, PRODUCTION)
    manifest: list[dict[str, Any]] = []

    def shoot(html: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(120)
        page.screenshot(path=str(target), clip={"x": 0, "y": 0, "width": CARD_WIDTH, "height": CARD_HEIGHT})
        print(f"  wrote {target.relative_to(REPO_ROOT)}  ({CARD_WIDTH}x{CARD_HEIGHT})")

    def size(text: str, big: int, small: int, threshold: int) -> int:
        return small if len(text) > threshold else big

    quotes = select_quotes(summary, items)
    for n, ex in enumerate(quotes, 1):
        c_text = ex["constraint_text"]
        html = env.get_template("quote_card.html.j2").render(
            mode="asked_got", title=f"asked-vs-got-{n}", tagline="Asked vs got",
            run_id=run_id, item_id=ex["item_id"], category_label=label,
            item_title=items[ex["item_id"]].title or ex["item_id"],
            constraint_id=ex["constraint_id"], constraint_text=c_text,
            model_display=disp.get(ex["model_key"], ex["model_key"]),
            quote=ex["evidence"], p_broken=f"{ex['verifier_p_broken']:.2f}",
            context=_following_line(_raw_text(run_id, ex["model_key"], ex["item_id"]), ex["evidence"]),
            asked_size=size(c_text, 40, 32, 90), quote_size=size(ex["evidence"], 32, 26, 200),
            methodology_note=QUOTE_NOTE, raw_path=_raw_rel(run_id, ex["model_key"], ex["item_id"]),
            repo_url=REPO_URL,
        )
        target = out_dir / f"asked-vs-got-{n:02d}.png"
        shoot(html, target)
        manifest.append({"card": target.name, "kind": "asked_vs_got", **ex,
                         "raw_path": _raw_rel(run_id, ex["model_key"], ex["item_id"]),
                         "scored_path": f"data/runs/{run_id}/scored/{ex['model_key']}/{PRODUCTION}/{ex['item_id']}.json",
                         "verifier_path": f"data/runs/{run_id}/constraints/{ex['model_key']}/{PRODUCTION}/{ex['item_id']}.json"})

    verified = {(q["model_key"], q["item_id"], q["constraint_id"]) for q in
                (cv.get("examples") or [])}
    n_side = 0
    sys.path.insert(0, str(REPO_ROOT))
    from harness.quotes import quote_in_text
    for con in cv.get("contrasts", []):
        ex = con["violation"]
        if n_side >= MAX_CONTRAST_CARDS or len(ex["evidence"].split()) > MAX_QUOTE_WORDS:
            continue
        if (ex["model_key"], ex["item_id"], ex["constraint_id"]) not in verified:
            continue
        if not quote_in_text(ex["evidence"], _raw_text(run_id, ex["model_key"], ex["item_id"])):
            continue
        left = _relevant_line(_raw_text(run_id, con["kept_by"], con["item_id"]), ex["constraint_text"])
        if not left:
            continue
        n_side += 1
        item = items[con["item_id"]]
        html = env.get_template("quote_card.html.j2").render(
            mode="side_by_side", title=f"side-by-side-{n_side}", tagline="Same task, same constraints",
            run_id=run_id, item_id=con["item_id"], category_label=label,
            item_title=item.title or con["item_id"],
            left_model=disp.get(con["kept_by"], con["kept_by"]), left_excerpt=left,
            left_chips=[f"{c['id']} kept" for c in item.constraints],
            left_score=f"{con['kept_score']:.0f}",
            constraint_id=ex["constraint_id"], constraint_text=ex["constraint_text"],
            model_display=disp.get(ex["model_key"], ex["model_key"]), quote=ex["evidence"],
            p_broken=f"{ex['verifier_p_broken']:.2f}", right_score=f"{ex['item_score']:.0f}",
            asked_size=32, quote_size=size(ex["evidence"] + left, 26, 22, 330),
            methodology_note=QUOTE_NOTE,
            raw_path=(f"{_raw_rel(run_id, con['kept_by'], con['item_id'])}  vs  "
                      f".../{ex['model_key']}/{PRODUCTION}/{ex['item_id']}.json"),
            repo_url=REPO_URL,
        )
        target = out_dir / f"side-by-side-{n_side:02d}.png"
        shoot(html, target)
        manifest.append({"card": target.name, "kind": "side_by_side", "item_id": con["item_id"],
                         "kept_by": con["kept_by"], "kept_excerpt": left, "violation": ex,
                         "raw_paths": [_raw_rel(run_id, con["kept_by"], con["item_id"]),
                                       _raw_rel(run_id, ex["model_key"], ex["item_id"])]})

    points = takeaway_points(summary, items)
    if points:
        html = env.get_template("text_card.html.j2").render(
            title="what-this-means", heading="What this means for production teams",
            points=points, run_id=run_id, n_models=summary["n_models"],
            methodology_version=summary["methodology_version"],
            methodology_note=DEFAULT_METHODOLOGY_NOTE, repo_url=REPO_URL,
        )
        shoot(html, out_dir / "what-this-means.png")
        manifest.append({"card": "what-this-means.png", "kind": "takeaways", "points": points})

    # Thread / carousel: overall -> judge vs verifier -> strongest quote ->
    # takeaways. Copies, not new renders, so the thread is byte-identical to the
    # cards it is made of.
    thread = [out_dir / "overall.png", out_dir / "production-judge-vs-verifier.png",
              out_dir / "asked-vs-got-01.png", out_dir / "what-this-means.png"]
    thread_dir = out_dir / "thread-production"
    thread_dir.mkdir(parents=True, exist_ok=True)
    for i, src in enumerate(thread, 1):
        if src.exists():
            dest = thread_dir / f"{i:02d}-{src.name}"
            dest.write_bytes(src.read_bytes())
            print(f"  wrote {dest.relative_to(REPO_ROOT)}")
    return manifest


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
            # The chart is an inline data URI, so there is no network wait - but
            # give the layout one frame to settle before capturing.
            page.wait_for_timeout(120)
            target = out_dir / f"{chart.stem}.png"
            page.screenshot(path=str(target), clip={
                "x": 0, "y": 0, "width": CARD_WIDTH, "height": CARD_HEIGHT,
            })
            written.append(target)
            print(f"  wrote {target.relative_to(REPO_ROOT)}  ({CARD_WIDTH}x{CARD_HEIGHT})")
        manifest = render_production_cards(page, env, summary, out_dir, note)
        browser.close()

    if manifest:
        # Every quote card's sources, so a reader who sees one card can find the
        # raw response, the judge record and the verifier record behind it.
        with open(out_dir / "cards.json", "w", encoding="utf-8") as fh:
            json.dump({"run_id": summary["run_id"], "cards": manifest}, fh,
                      indent=2, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
        written.extend(out_dir / m["card"] for m in manifest)

    print(f"{len(written)} social card(s) written to {out_dir.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
