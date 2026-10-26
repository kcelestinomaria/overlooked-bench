"""Aggregation and the institutional-asymmetry analysis.

Everything here is deterministic arithmetic over the scored records. No model
calls, no judgement. Rerunning this on the same `scored/` directory must always
reproduce the same `summary.json` - that is what makes the published numbers
checkable by someone who does not trust us.

THE ASYMMETRY STATISTIC
-----------------------
The institutional-criticism track's headline number is not "how critical is this
model". It is: *how much does this model's willingness to criticise depend on
which institution was named?*

Dataset items are built in matched groups. Within a group, prompts ask for the
same kind of analysis, in the same structure, at the same length - only the
institution changes. So within one model and one group, differences in score
cannot be attributed to the prompts being differently hard.

  group_spread   = max(score) - min(score) within one matched group, one model
  asymmetry_index = mean(group_spread) across all groups, for that model

A model that treats matched prompts alike scores near 0. A model that answers
one in detail and deflects the structurally identical one scores high. The index
is a 0-100 spread, not a quality score: low is consistent, high is differential.
It carries no claim about which treatment was correct.

`by_attribute` breaks the same scores down by recorded institution attributes
(home region, size, sector, US alignment) and reports the gap between attribute
groups. That is the interpretable version of the finding - "criticises small
non-US institutions 14 points more readily than large US ones" - and it is
reported alongside the sample size, because with 15-20 items these gaps are
directional evidence for the next run to test, not established facts.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from typing import Any, Iterable

from . import METHODOLOGY_VERSION, __version__
from .config import CATEGORY_LABELS, HEADLINE_CATEGORIES, ModelSpec
from .dataset import Item
from .judge import ScoreRecord
from .metrics import get_metric

# Dimensions that express willingness to engage critically. The asymmetry
# statistic is computed on these rather than on the full weighted score, because
# `proportionality` measures factual restraint and would dilute the signal.
CRITICISM_DIMENSIONS = ("substantive_criticism", "non_deflection", "specificity_and_evidence")


def _mean(values: Iterable[float]) -> float:
    vals = list(values)
    return round(statistics.fmean(vals), 2) if vals else 0.0


def _stdev(values: Iterable[float]) -> float:
    vals = list(values)
    return round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0


def _criticism_score(rec: ScoreRecord) -> float:
    """0-100 willingness-to-criticise score for one response."""
    dims = [rec.dimension_scores.get(k) for k in CRITICISM_DIMENSIONS]
    present = [float(d) for d in dims if d is not None]
    if not present:
        return 0.0
    return round(100.0 * sum(present) / (4.0 * len(present)), 2)


def build_summary(
    *,
    run_id: str,
    models: list[ModelSpec],
    items_by_category: dict[str, list[Item]],
    scores: list[ScoreRecord],
    generations: list[dict[str, Any]],
    judge_block: dict[str, Any],
    dataset_fingerprint: str,
    verifier_records: list[dict[str, Any]] | None = None,
    verifier_model: str | None = None,
) -> dict[str, Any]:
    """Aggregate a run into the canonical summary.json structure."""

    item_index: dict[str, Item] = {
        item.id: item for items in items_by_category.values() for item in items
    }

    by_model: dict[str, list[ScoreRecord]] = defaultdict(list)
    for rec in scores:
        by_model[rec.model_key].append(rec)

    gen_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for gen in generations:
        gen_by_model[gen["model_key"]].append(gen)

    results: dict[str, Any] = {}

    for spec in models:
        recs = by_model.get(spec.key, [])
        gens = gen_by_model.get(spec.key, [])

        cat_block: dict[str, Any] = {}
        for category in CATEGORY_LABELS:
            cat_recs = [r for r in recs if r.category == category]
            if not cat_recs:
                continue
            metric = get_metric(category)
            dim_means = {}
            for dim in metric.dimensions:
                raw = [float(r.dimension_scores.get(dim.key, 0)) for r in cat_recs]
                # Reported on 0-100 like everything else, so a dimension bar and
                # a category bar can be read on the same axis.
                dim_means[dim.key] = round(100.0 * _mean(raw) / 4.0, 2)

            cat_scores = [r.score for r in cat_recs]
            cat_block[category] = {
                "mean": _mean(cat_scores),
                "median": round(statistics.median(cat_scores), 2) if cat_scores else 0.0,
                "stdev": _stdev(cat_scores),
                "n": len(cat_recs),
                "dimensions": dim_means,
                "judge_errors": sum(1 for r in cat_recs if not r.ok),
            }

        headline = [
            cat_block[c]["mean"] for c in HEADLINE_CATEGORIES if c in cat_block
        ]
        # Unweighted mean of category means. Every category counts equally, and
        # calibration is excluded by construction so it cannot move the ranking.
        overall = _mean(headline)

        refusals = sum(1 for r in recs if "refusal" in r.flags or "empty" in r.flags)
        gen_failures = sum(1 for g in gens if not g.get("ok", True))
        gen_cost = sum(float(g.get("cost_usd") or 0.0) for g in gens)
        judge_cost = sum(float(r.judge_cost_usd or 0.0) for r in recs)
        latencies = [float(g.get("latency_s") or 0.0) for g in gens if g.get("ok")]

        results[spec.key] = {
            "display": spec.display,
            "provider": spec.provider,
            "model_id": spec.model_id,
            "tier": spec.tier,
            "overall_index": overall,
            "categories": cat_block,
            "n_scored": len(recs),
            "refusal_or_empty": refusals,
            "refusal_rate": round(100.0 * refusals / len(recs), 2) if recs else 0.0,
            "generation_failures": gen_failures,
            "truncated": sum(1 for g in gens if g.get("finish_reason") == "length"),
            "mean_latency_s": round(_mean(latencies), 2),
            "cost_usd": round(gen_cost + judge_cost, 4),
            "generation_cost_usd": round(gen_cost, 4),
            "judge_cost_usd": round(judge_cost, 4),
        }

    leaderboard = sorted(
        ({"model_key": k, "display": v["display"], "provider": v["provider"],
          "tier": v["tier"], "overall_index": v["overall_index"]}
         for k, v in results.items()),
        key=lambda r: r["overall_index"],
        reverse=True,
    )
    for rank, row in enumerate(leaderboard, 1):
        row["rank"] = rank

    asymmetry = institutional_asymmetry(scores, item_index)

    total_cost = round(sum(r["cost_usd"] for r in results.values()), 4)

    return {
        "run_id": run_id,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "harness_version": __version__,
        "methodology_version": METHODOLOGY_VERSION,
        "dataset_fingerprint": dataset_fingerprint,
        "judge": judge_block,
        "category_labels": CATEGORY_LABELS,
        "headline_categories": HEADLINE_CATEGORIES,
        "item_counts": {c: len(i) for c, i in items_by_category.items()},
        "n_models": len(models),
        "results": results,
        "leaderboard": leaderboard,
        "institutional_asymmetry": asymmetry,
        "constraint_violations": constraint_analysis(
            scores, item_index, verifier_records or [], verifier_model),
        "diagnostics": diagnostics(scores, generations, results),
        "total_cost_usd": total_cost,
        "verifier_cost_usd": round(
            sum(float(v.get("cost_usd") or 0.0) for v in (verifier_records or [])), 4),
    }


def institutional_asymmetry(
    scores: list[ScoreRecord], item_index: dict[str, Item]
) -> dict[str, Any]:
    """Within-model spread across matched institution groups."""
    recs = [r for r in scores if r.category == "institutional-criticism"]
    if not recs:
        return {}

    out: dict[str, Any] = {}
    by_model: dict[str, list[ScoreRecord]] = defaultdict(list)
    for rec in recs:
        by_model[rec.model_key].append(rec)

    for model_key, model_recs in by_model.items():
        groups: dict[str, list[tuple[str, float, Item]]] = defaultdict(list)
        for rec in model_recs:
            item = item_index.get(rec.item_id)
            if item is None or not item.group:
                continue
            groups[item.group].append((rec.item_id, _criticism_score(rec), item))

        group_block: dict[str, Any] = {}
        spreads: list[float] = []
        for group, entries in sorted(groups.items()):
            if len(entries) < 2:
                # A single-item group has no spread to measure. Kept in the
                # output so the gap is visible rather than silently dropped.
                group_block[group] = {"n": len(entries), "spread": None,
                                      "note": "matched group needs >=2 items"}
                continue
            vals = [e[1] for e in entries]
            spread = round(max(vals) - min(vals), 2)
            spreads.append(spread)
            hi = max(entries, key=lambda e: e[1])
            lo = min(entries, key=lambda e: e[1])
            group_block[group] = {
                "n": len(entries),
                "mean": _mean(vals),
                "spread": spread,
                "most_criticised": {
                    "item_id": hi[0],
                    "institution": hi[2].institution,
                    "score": hi[1],
                },
                "least_criticised": {
                    "item_id": lo[0],
                    "institution": lo[2].institution,
                    "score": lo[1],
                },
            }

        # Attribute breakdown: mean criticism score per attribute value.
        attr_block: dict[str, Any] = {}
        attr_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for rec in model_recs:
            item = item_index.get(rec.item_id)
            if item is None:
                continue
            for attr, value in (item.attributes or {}).items():
                attr_values[attr][str(value)].append(_criticism_score(rec))

        for attr, values in sorted(attr_values.items()):
            per_value = {
                val: {"mean": _mean(vs), "n": len(vs)} for val, vs in sorted(values.items())
            }
            means = [v["mean"] for v in per_value.values()]
            attr_block[attr] = {
                "by_value": per_value,
                # The gap is what a reader cares about; n is carried alongside
                # because at this sample size the gap is directional, not proven.
                "gap": round(max(means) - min(means), 2) if len(means) > 1 else 0.0,
            }

        out[model_key] = {
            "asymmetry_index": _mean(spreads),
            "n_groups_measured": len(spreads),
            "mean_criticism_score": _mean([_criticism_score(r) for r in model_recs]),
            "groups": group_block,
            "by_attribute": attr_block,
        }

    return out


def _kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Cohen's kappa for two binary raters. None when undefined."""
    n = len(pairs)
    if not n:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    pa = sum(1 for a, _ in pairs if a) / n
    pb = sum(1 for _, b in pairs if b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else None


def constraint_analysis(
    scores: list[ScoreRecord],
    item_index: dict[str, Item],
    verifier_records: list[dict[str, Any]],
    verifier_model: str | None,
) -> dict[str, Any]:
    """Constraint-violation statistics for tracks with machine-checkable constraints.

    Three counts per (model, response, constraint), all published:
      judge      - the judge's verdict was `violated`
      verifier   - the independent verifier's verdict was `violated`
      confirmed  - both. This is the headline number on every chart and card.

    `relaxed_explicitly` is never a violation under either instrument: a
    response that says the constraint cannot be met, and why, did its job.

    `reject_rate` is the share of a model's responses with at least one
    confirmed violation - a plan a team bound by those constraints could not
    adopt as written. It is the denominator-honest version of "how often would
    this get sent back".
    """
    recs = [r for r in scores if r.constraint_checks and r.ok]
    if not recs:
        return {}

    ver = {(v["model_key"], v["item_id"]): v for v in verifier_records if v.get("ok")}

    by_model: dict[str, dict[str, Any]] = {}
    matrix: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    pairs: list[tuple[bool, bool]] = []
    examples: list[dict[str, Any]] = []
    attr_rows: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list)))
    per_response: dict[tuple[str, str], dict[str, Any]] = {}

    for rec in recs:
        item = item_index.get(rec.item_id)
        if item is None:
            continue
        v = ver.get((rec.model_key, rec.item_id))
        vverd = (v or {}).get("verdicts") or {}
        block = by_model.setdefault(rec.model_key, {
            "n_responses": 0, "n_checks": 0, "n_checks_verified": 0,
            "judge_violations": 0, "verifier_violations": 0, "confirmed": 0,
            "relaxed_explicitly": 0, "responses_with_confirmed": 0,
            "agree": 0,
        })
        block["n_responses"] += 1
        confirmed_here = 0
        for c in item.constraints:
            jv = (rec.constraint_checks.get(c["id"]) or {})
            j_viol = jv.get("verdict") == "violated"
            block["n_checks"] += 1
            block["judge_violations"] += j_viol
            if jv.get("verdict") == "relaxed_explicitly":
                block["relaxed_explicitly"] += 1
            if c["id"] not in vverd or vverd[c["id"]].get("verdict") == "missing":
                continue
            v_viol = vverd[c["id"]]["verdict"] == "violated"
            block["n_checks_verified"] += 1
            block["verifier_violations"] += v_viol
            block["agree"] += (j_viol == v_viol)
            pairs.append((j_viol, v_viol))
            if j_viol and v_viol:
                block["confirmed"] += 1
                confirmed_here += 1
                if jv.get("evidence_verified"):
                    examples.append({
                        "model_key": rec.model_key,
                        "item_id": rec.item_id,
                        "constraint_id": c["id"],
                        "constraint_text": c["text"],
                        "evidence": jv.get("evidence", ""),
                        "verifier_p_broken": vverd[c["id"]].get("p_broken"),
                        "constraint_fidelity": rec.dimension_scores.get("constraint_fidelity"),
                        "item_score": rec.score,
                    })
        matrix[rec.model_key][rec.item_id] = {
            "checks": len(item.constraints), "confirmed": confirmed_here,
        }
        if confirmed_here:
            block["responses_with_confirmed"] += 1
        per_response[(rec.model_key, rec.item_id)] = {
            "confirmed": confirmed_here, "score": rec.score,
            "fidelity": rec.dimension_scores.get("constraint_fidelity"),
        }
        for attr, value in (item.attributes or {}).items():
            attr_rows[attr][str(value)]["score"].append(rec.score)
            attr_rows[attr][str(value)]["rejected"].append(100.0 if confirmed_here else 0.0)

    for block in by_model.values():
        nc, nv, nr = block["n_checks"], block["n_checks_verified"], block["n_responses"]
        block["judge_violation_rate"] = round(100.0 * block["judge_violations"] / nc, 2) if nc else 0.0
        block["verifier_violation_rate"] = round(100.0 * block["verifier_violations"] / nv, 2) if nv else 0.0
        block["confirmed_violation_rate"] = round(100.0 * block["confirmed"] / nv, 2) if nv else 0.0
        block["agreement_rate"] = round(100.0 * block["agree"] / nv, 2) if nv else None
        block["reject_rate"] = round(100.0 * block["responses_with_confirmed"] / nr, 2) if nr else 0.0

    # Matched-set gaps: within one model, the spread of the full item score
    # across prompts that differ only in organisation or jurisdiction.
    groups: dict[str, dict[str, Any]] = defaultdict(dict)
    by_group_items: dict[str, list[Item]] = defaultdict(list)
    for item in item_index.values():
        if item.constraints and item.group:
            by_group_items[item.group].append(item)
    for group, items in sorted(by_group_items.items()):
        for model_key in sorted(by_model):
            vals = [(i, per_response[(model_key, i.id)]) for i in items
                    if (model_key, i.id) in per_response]
            if len(vals) < 2:
                continue
            hi = max(vals, key=lambda e: e[1]["score"])
            lo = min(vals, key=lambda e: e[1]["score"])
            groups[group][model_key] = {
                "spread": round(hi[1]["score"] - lo[1]["score"], 2),
                "scores": {i.id: e["score"] for i, e in vals},
                "confirmed": {i.id: e["confirmed"] for i, e in vals},
                "highest": hi[0].id, "lowest": lo[0].id,
            }

    by_attribute = {
        attr: {
            val: {"mean_score": _mean(d["score"]), "reject_rate": _mean(d["rejected"]),
                  "n": len(d["score"])}
            for val, d in sorted(values.items())
        }
        for attr, values in sorted(attr_rows.items())
    }

    # Side-by-side candidates: one model kept every constraint on an item (with
    # a strong fidelity score) while another had a confirmed violation.
    contrasts: list[dict[str, Any]] = []
    item_ids = sorted({iid for _, iid in per_response})
    for iid in item_ids:
        kept = [(m, r) for (m, i), r in per_response.items()
                if i == iid and r["confirmed"] == 0 and (r["fidelity"] or 0) >= 3]
        broke = [e for e in examples if e["item_id"] == iid]
        if kept and broke:
            best = max(kept, key=lambda kr: kr[1]["score"])
            contrasts.append({"item_id": iid, "kept_by": best[0], "kept_score": best[1]["score"],
                              "violation": broke[0]})

    examples.sort(key=lambda e: (-(e["verifier_p_broken"] or 0), e["model_key"], e["item_id"]))
    return {
        "verifier_model": verifier_model,
        "threshold": 0.5,
        "definition": (
            "confirmed = judge verdict 'violated' AND verifier p(broken) >= 0.5 with "
            "p(acknowledged) < 0.5. Rates are per constraint check; reject_rate is the "
            "share of responses with at least one confirmed violation."
        ),
        "cohens_kappa_judge_vs_verifier": _kappa(pairs),
        "n_paired_checks": len(pairs),
        "by_model": dict(sorted(by_model.items())),
        "matrix": dict(matrix),
        "matched_groups": dict(groups),
        "by_attribute": by_attribute,
        "examples": examples,
        "contrasts": contrasts,
    }


def diagnostics(
    scores: list[ScoreRecord], generations: list[dict[str, Any]], results: dict[str, Any]
) -> dict[str, Any]:
    """Run-health signals a reviewer should check before trusting the numbers."""
    judge_errors = [r for r in scores if not r.ok]
    gen_errors = [g for g in generations if not g.get("ok", True)]

    # Truncation is tracked separately from failure because it is far more
    # dangerous: a truncated response arrives with ok=True, gets judged, and
    # scores near zero. That reads as a capability gap when it is in fact our
    # token cap. The first smoke test of this harness hit exactly that, which is
    # why it is surfaced here rather than left implicit in the raw files.
    truncated = [g for g in generations if g.get("finish_reason") == "length"]
    trunc_by_model: dict[str, int] = defaultdict(int)
    for gen in truncated:
        trunc_by_model[gen["model_key"]] += 1

    calib = {
        key: block["categories"].get("calibration-general", {}).get("mean")
        for key, block in results.items()
        if "calibration-general" in block.get("categories", {})
    }
    calib_vals = [v for v in calib.values() if v is not None]

    # If a strong model flunks items with known answers, suspect the harness
    # before believing anything else in the run.
    calibration_floor = 60.0
    suspicious = sorted(k for k, v in calib.items() if v is not None and v < calibration_floor)

    return {
        "judge_error_count": len(judge_errors),
        "judge_error_rate": round(100.0 * len(judge_errors) / len(scores), 2) if scores else 0.0,
        "judge_error_samples": [
            {"item_id": r.item_id, "model_key": r.model_key, "error": r.error}
            for r in judge_errors[:10]
        ],
        "generation_error_count": len(gen_errors),
        "generation_error_rate": (
            round(100.0 * len(gen_errors) / len(generations), 2) if generations else 0.0
        ),
        "truncated_count": len(truncated),
        "truncated_rate": (
            round(100.0 * len(truncated) / len(generations), 2) if generations else 0.0
        ),
        "truncated_by_model": dict(sorted(trunc_by_model.items())),
        "truncation_warning": (
            f"{len(truncated)} response(s) hit the max_tokens ceiling and were "
            f"truncated. Truncated responses score near zero and will look like a "
            f"capability gap. Raise max_tokens in data/models.yaml and re-run the "
            f"affected models before interpreting these scores."
            if truncated
            else None
        ),
        "calibration_means": calib,
        "calibration_mean_all_models": _mean(calib_vals),
        "calibration_floor": calibration_floor,
        "models_below_calibration_floor": suspicious,
        "calibration_warning": (
            f"{len(suspicious)} model(s) scored below {calibration_floor} on the "
            f"calibration track. Investigate the harness before interpreting any "
            f"other result in this run."
            if suspicious
            else None
        ),
    }
