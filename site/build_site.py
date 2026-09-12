"""Build the run index the leaderboard site reads.

    python site/build_site.py

The site is otherwise fully static - `index.html`, `styles.css` and `app.js` are
hand-written and never generated. The only thing that needs building is
`data/runs/index.json`, a list of published runs, because a browser cannot
enumerate a directory over HTTP.

Deliberately, this writes the index next to the runs rather than copying run data
into `site/`. The page therefore reads the exact files that constitute the audit
trail, not a transformed copy of them. If the site shows a number, that number is
in the committed `summary.json`, and anyone can diff the two.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "data" / "runs"
INDEX_PATH = RUNS_DIR / "index.json"


def summarise_run(summary: dict[str, Any]) -> dict[str, Any]:
    """The subset of a run the picker needs. Kept small on purpose: the index is
    fetched on every page load, and full summaries are fetched on demand."""
    leader = (summary.get("leaderboard") or [{}])[0]
    diag = summary.get("diagnostics", {})
    return {
        "run_id": summary["run_id"],
        "generated_utc": summary.get("generated_utc"),
        "n_models": summary.get("n_models", 0),
        "n_items": sum(summary.get("item_counts", {}).values()),
        "methodology_version": summary.get("methodology_version"),
        "judge_model": summary.get("judge", {}).get("judge_model"),
        "dataset_fingerprint": summary.get("dataset_fingerprint"),
        "top_model": leader.get("display"),
        "top_score": leader.get("overall_index"),
        "total_cost_usd": summary.get("total_cost_usd"),
        # Surfaced in the index so a reviewer can see a compromised run without
        # opening it.
        "has_warnings": bool(diag.get("calibration_warning") or diag.get("truncation_warning")),
    }


def main() -> int:
    if not RUNS_DIR.exists():
        print(f"ERROR: {RUNS_DIR} does not exist. Run the harness first.", file=sys.stderr)
        return 2

    runs: list[dict[str, Any]] = []
    for path in sorted(RUNS_DIR.iterdir()):
        summary_path = path / "summary.json"
        if not path.is_dir() or not summary_path.exists():
            continue
        with open(summary_path, encoding="utf-8") as fh:
            runs.append(summarise_run(json.load(fh)))

    if not runs:
        print("ERROR: no runs with a summary.json found.", file=sys.stderr)
        return 2

    runs.sort(key=lambda r: r["run_id"], reverse=True)
    payload = {"generated_from": "site/build_site.py", "runs": runs}

    with open(INDEX_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")

    print(f"Wrote {INDEX_PATH.relative_to(REPO_ROOT)} with {len(runs)} run(s):")
    for run in runs:
        flag = "  [WARNINGS]" if run["has_warnings"] else ""
        print(f"  {run['run_id']}  {run['n_models']} models  top={run['top_model']}{flag}")
    print("\nPreview locally:\n  python -m http.server 8000\n  open http://localhost:8000/site/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
