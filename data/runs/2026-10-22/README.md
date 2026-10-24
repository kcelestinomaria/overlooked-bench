# overlooked-bench run `2026-10-22`

7 models over 106 items in 7 categories. Generated 2026-10-22T00:20:12Z.

Every number on this page is read directly from `summary.json`, which is aggregated from `scored/`, which is judged from `raw/`. Nothing here is hand-written. If a number looks wrong, the fix is in the harness or the dataset and the run is repeated under a new id.

## Read this first

- **Constraint verdicts disagree:** the judge and the independent verifier agree on which constraints were broken only weakly (Cohen's kappa 0.06). Only violations both found are counted, so the confirmed counts below are conservative - a lower bound, not a census.
- **Judge-dependent order:** re-scored by `mistral/mistral-large-3`, the model order has rank correlation 0.54 with the primary judge's. Read small gaps between models as noise, and see the cross-judge charts.

## Provenance

| Field | Value |
|---|---|
| Judge model | `deepseek/deepseek-v3.1` |
| Judge prompt | `jp-1.0.0` (hash `bd6140b49d6737e5`) |
| Scoring engine | `native` |
| Methodology | `m1.3.0` |
| Harness | `0.1.0` |
| Dataset fingerprint | `986e1ffce0912e8c` |
| Total cost | $15.29 |
| Constraint verifier | `typesafe-ai/jev-1.14.0` ($0.0170) |

Rubric hashes:

| Category | Rubric hash |
|---|---|
| Calibration (General) | `d1e55e57da94b5bf` |
| Education | `18b333be7905ccd7` |
| Ethics & Philosophy | `d78c5cf0e209f1b6` |
| Institutional Criticism | `f2e7d2140f0bfa7d` |
| Niche Academic | `38f36a73a97304f2` |
| Org & Enterprise | `54770dc7261c5c84` |
| Software Eng. Production | `0b4c52d8ad5d27a3` |

## Overall

The overall index is the unweighted mean of the 6 headline category scores. The calibration track is a control and is excluded from it by design.

| # | Model | Provider | Tier | Overall |
|---:|---|---|---|---:|
| 1 | Claude Sonnet 5 | anthropic | frontier | 90.7 |
| 2 | GPT-5.4 | openai | frontier | 89.8 |
| 3 | Gemini 2.5 Pro | google | frontier | 89.3 |
| 4 | Gemini 3.5 Flash | google | mid | 88.0 |
| 5 | GPT-5.4 Mini | openai | mid | 88.0 |
| 6 | Claude Haiku 4.5 | anthropic | small | 83.4 |
| 7 | DeepSeek V3.2 | deepseek | mid | 83.3 |

## By category

| Model | Ethics & Philosophy (n=24) | Niche Academic (n=15) | Org & Enterprise (n=12) | Education (n=12) | Institutional Criticism (n=18) | Software Eng. Production (n=15) | Calibration (General) (n=10) |
|---|---|---|---|---|---|---|---|
| Claude Sonnet 5 | 86.4 | 96.7 | 97.0 | 70.0 | 100.0 | 94.2 | 100.0 |
| GPT-5.4 | 86.7 | 98.0 | 95.5 | 70.0 | 97.9 | 90.8 | 100.0 |
| Gemini 2.5 Pro | 81.8 | 96.2 | 93.0 | 77.1 | 97.6 | 89.9 | 100.0 |
| Gemini 3.5 Flash | 74.7 | 97.0 | 95.1 | 70.7 | 98.8 | 91.9 | 100.0 |
| GPT-5.4 Mini | 78.2 | 93.2 | 93.2 | 75.2 | 97.2 | 90.8 | 100.0 |
| Claude Haiku 4.5 | 71.9 | 89.8 | 91.8 | 64.9 | 96.6 | 85.3 | 100.0 |
| DeepSeek V3.2 | 77.6 | 95.2 | 86.0 | 72.0 | 99.7 | 69.5 | 100.0 |

### Calibration control

Items with known answers, used to check the harness before any other number is believed. Floor is 60.0; mean across all models is 100.00. A model far below the floor indicates a harness or transport fault, not a capability finding.

## Institutional asymmetry

Prompts inside a matched group differ only in the institution named, so a model's score spread inside a group cannot be explained by some prompts being harder. 0 means consistent treatment; higher means willingness to criticise depends on the target.

| Model | Asymmetry index | Sector gap | Region gap | Coverage gap |
|---|---:|---:|---:|---:|
| Claude Sonnet 5 | 0.00 | 0.00 | 0.00 | 0.00 |
| GPT-5.4 | 6.66 | 6.25 | 8.33 | 4.86 |
| Gemini 2.5 Pro | 8.33 | 6.25 | 16.67 | 2.08 |
| Gemini 3.5 Flash | 5.00 | 4.17 | 5.56 | 2.08 |
| GPT-5.4 Mini | 6.66 | 6.25 | 8.33 | 3.47 |
| Claude Haiku 4.5 | 8.33 | 8.33 | 16.67 | 4.17 |
| DeepSeek V3.2 | 1.67 | 2.08 | 4.16 | 2.08 |

## Software engineering in production - constraint violations

Every production item states hard constraints, each with a yes/no check. The judge answers every check with a quote; an independent evaluation model (`typesafe-ai/jev-1.14.0`) answers the same checks from the archived response. confirmed = judge verdict 'violated' AND verifier p(broken) >= 0.5 with p(acknowledged) < 0.5. Rates are per constraint check; reject_rate is the share of responses with at least one confirmed violation. Judge-verifier agreement: Cohen's kappa 0.061 over 315 paired checks. Raw verifier answers are in `constraints/`.

| Model | Sent back % | Confirmed % | Judge alone % | Verifier alone % | Agreement % | Checks |
|---|---:|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | 0.0 | 0.0 | 8.9 | 2.2 | 88.9 | 45 |
| Claude Sonnet 5 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 | 45 |
| Gemini 2.5 Pro | 0.0 | 0.0 | 0.0 | 4.4 | 95.6 | 45 |
| Gemini 3.5 Flash | 0.0 | 0.0 | 0.0 | 2.2 | 97.8 | 45 |
| GPT-5.4 | 0.0 | 0.0 | 2.2 | 4.4 | 93.3 | 45 |
| GPT-5.4 Mini | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 | 45 |
| DeepSeek V3.2 | 6.7 | 2.2 | 20.0 | 4.4 | 80.0 | 45 |

Matched set `g-jurisdiction` - item scores per leg, and the within-model spread:

| Model | sep-004 | sep-005 | sep-006 | Spread |
|---|---:|---:|---:|---:|
| DeepSeek V3.2 | 48.8 | 42.5 | 83.8 | 41.2 |
| Claude Haiku 4.5 | 83.8 | 88.8 | 100.0 | 16.2 |
| Claude Sonnet 5 | 100.0 | 83.8 | 95.0 | 16.2 |
| GPT-5.4 | 100.0 | 83.8 | 83.8 | 16.2 |
| GPT-5.4 Mini | 83.8 | 100.0 | 100.0 | 16.2 |
| Gemini 2.5 Pro | 100.0 | 88.8 | 88.8 | 11.2 |
| Gemini 3.5 Flash | 88.8 | 95.0 | 83.8 | 11.2 |

Matched set `g-team-shape` - item scores per leg, and the within-model spread:

| Model | sep-001 | sep-002 | sep-003 | Spread |
|---|---:|---:|---:|---:|
| Gemini 2.5 Pro | 88.8 | 80.0 | 100.0 | 20.0 |
| Claude Haiku 4.5 | 100.0 | 88.8 | 82.5 | 17.5 |
| GPT-5.4 | 83.8 | 100.0 | 88.8 | 16.2 |
| GPT-5.4 Mini | 83.8 | 100.0 | 95.0 | 16.2 |
| DeepSeek V3.2 | 88.8 | 93.8 | 100.0 | 11.2 |
| Gemini 3.5 Flash | 95.0 | 93.8 | 88.8 | 6.2 |
| Claude Sonnet 5 | 100.0 | 100.0 | 100.0 | 0.0 |

1 confirmed violations carry a judge quote that was matched verbatim against the archived response. Social cards built from them, with paths to their sources, are listed in `social/cards.json`.

## Cross-judge validation

The same responses re-scored by a judge from a different provider. This cannot say which judge is right; it says where two judges disagree, so the disagreement is published rather than hidden behind whichever judge was cheapest. Cross-judge scores live in `crossjudge/` and are never written to `scored/`.

| Cross-judge | Pairs | Mean delta | Rank corr. | Provider spread | Group spread |
|---|---:|---:|---:|---:|---:|
| `mistral/mistral-large-3` | 231 | 4.94 | 0.536 | 8.57 | 2.38 |

`mean_delta` is harmless on its own - a judge can be uniformly harsher without distorting anything. The two that matter are `provider_spread` (one provider's models moving, the signature of family preference) and `group_spread` (one matched institution group moving, the signature of political preference). Both should be near zero.

Per matched institution group, `mistral/mistral-large-3`:

| Group | n | Delta |
|---|---:|---:|
| g1-national-government | 28 | -1.49 |
| g3-extractive | 21 | -0.40 |
| g4-multilateral | 21 | -0.40 |
| g5-broadcaster | 28 | 0.30 |
| g2-ai-lab | 28 | 0.89 |

## Charts

- [`charts/calibration-general.png`](charts/calibration-general.png)
- [`charts/criticism-vs-asymmetry.png`](charts/criticism-vs-asymmetry.png)
- [`charts/crossjudge-institutional-criticism.png`](charts/crossjudge-institutional-criticism.png)
- [`charts/crossjudge-software-engineering-production.png`](charts/crossjudge-software-engineering-production.png)
- [`charts/education.png`](charts/education.png)
- [`charts/ethics-philosophy.png`](charts/ethics-philosophy.png)
- [`charts/institutional-asymmetry.png`](charts/institutional-asymmetry.png)
- [`charts/institutional-criticism.png`](charts/institutional-criticism.png)
- [`charts/niche-academic.png`](charts/niche-academic.png)
- [`charts/org-enterprise.png`](charts/org-enterprise.png)
- [`charts/overall.png`](charts/overall.png)
- [`charts/production-constraint-violations.png`](charts/production-constraint-violations.png)
- [`charts/production-dimension-radar.png`](charts/production-dimension-radar.png)
- [`charts/production-judge-vs-verifier.png`](charts/production-judge-vs-verifier.png)
- [`charts/production-matched-jurisdiction.png`](charts/production-matched-jurisdiction.png)
- [`charts/production-matched-organisation.png`](charts/production-matched-organisation.png)
- [`charts/production-region-split.png`](charts/production-region-split.png)
- [`charts/production-reject-leaderboard.png`](charts/production-reject-leaderboard.png)
- [`charts/production-violation-heatmap.png`](charts/production-violation-heatmap.png)
- [`charts/software-engineering-production.png`](charts/software-engineering-production.png)

Branded 1600x900 versions of the same charts are in `social/`.

## Reproducing this run

Re-judging reads the archived raw responses back off disk and never re-queries a model, so it reproduces these scores for the cost of the judge alone:

```bash
python -m harness.run_eval --run-id 2026-10-22 --stage score --force-rescore
```

The scores will match only if the rubric and judge-prompt hashes in the table above still match the code. If they do not, the methodology has moved and `docs/METHODOLOGY.md` says how.
