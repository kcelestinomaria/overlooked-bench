# overlooked-bench run `2026-09-13`

10 models over 91 items in 6 categories. Generated 2026-09-13T17:32:15Z.

Every number on this page is read directly from `summary.json`, which is aggregated from `scored/`, which is judged from `raw/`. Nothing here is hand-written. If a number looks wrong, the fix is in the harness or the dataset and the run is repeated under a new id.

## Read this first

- **Truncation:** 2 response(s) hit the max_tokens ceiling and were truncated. Truncated responses score near zero and will look like a capability gap. Raise max_tokens in data/models.yaml and re-run the affected models before interpreting these scores.
- **Judge errors:** 7 of 910 judgings (0.77%) did not produce a usable score and are excluded from the means below rather than scored 0.

## Provenance

| Field | Value |
|---|---|
| Judge model | `deepseek/deepseek-v3.1-terminus` |
| Judge prompt | `jp-1.0.0` (hash `bd6140b49d6737e5`) |
| Scoring engine | `native` |
| Methodology | `m1.2.1` |
| Harness | `0.1.0` |
| Dataset fingerprint | `78198b54a6f421a2` |
| Total cost | $11.34 |
| Raw responses | 909 reused from run `2026-09-08` (identical dataset fingerprint), 1 regenerated for this run |

Rubric hashes:

| Category | Rubric hash |
|---|---|
| Calibration (General) | `d1e55e57da94b5bf` |
| Education | `18b333be7905ccd7` |
| Ethics & Philosophy | `d78c5cf0e209f1b6` |
| Institutional Criticism | `f2e7d2140f0bfa7d` |
| Niche Academic | `38f36a73a97304f2` |
| Org & Enterprise | `54770dc7261c5c84` |

## Overall

The overall index is the mean of the five headline category scores. The calibration track is a control and is excluded from it by design.

| # | Model | Provider | Tier | Overall |
|---:|---|---|---|---:|
| 1 | GPT-5.4 | openai | frontier | 87.8 |
| 2 | DeepSeek V3.2 | deepseek | mid | 87.2 |
| 3 | Gemini 2.5 Pro | google | frontier | 85.5 |
| 4 | Claude Sonnet 5 | anthropic | frontier | 85.1 |
| 5 | Kimi K2.5 | moonshotai | mid | 84.3 |
| 6 | GPT-5.4 Mini | openai | mid | 83.6 |
| 7 | Gemini 3.5 Flash | google | mid | 82.5 |
| 8 | Mistral Medium 3.5 | mistral | mid | 78.7 |
| 9 | Claude Haiku 4.5 | anthropic | small | 77.6 |
| 10 | Llama 3.3 70B | meta | mid | 56.9 |

## By category

| Model | Ethics & Philosophy (n=24) | Niche Academic (n=15) | Org & Enterprise (n=12) | Education (n=12) | Institutional Criticism (n=18) | Calibration (General) (n=10) |
|---|---|---|---|---|---|---|
| GPT-5.4 | 89.2 | 97.7 | 95.2 | 64.2 | 92.8 | 100.0 |
| DeepSeek V3.2 | 88.1 | 99.7 | 89.1 | 63.8 | 95.4 | 99.4 |
| Gemini 2.5 Pro | 85.3 | 98.7 | 89.3 | 62.3 | 91.9 | 100.0 |
| Claude Sonnet 5 | 85.0 | 98.0 | 90.1 | 58.0 | 94.2 | 100.0 |
| Kimi K2.5 | 78.1 | 96.3 | 93.8 | 55.6 | 97.8 | 100.0 |
| GPT-5.4 Mini | 80.0 | 86.3 | 93.7 | 71.5 | 86.5 | 100.0 |
| Gemini 3.5 Flash | 72.4 | 98.0 | 93.4 | 60.0 | 88.8 | 96.4 |
| Mistral Medium 3.5 | 78.5 | 81.7 | 82.8 | 57.5 | 92.9 | 100.0 |
| Claude Haiku 4.5 | 72.1 | 87.5 | 83.0 | 56.8 | 88.7 | 99.6 |
| Llama 3.3 70B | 62.9 | 60.3 | 47.0 | 32.3 | 82.2 | 91.8 |

### Calibration control

Items with known answers, used to check the harness before any other number is believed. Floor is 60.0; mean across all models is 98.71. A model far below the floor indicates a harness or transport fault, not a capability finding.

## Institutional asymmetry

Prompts inside a matched group differ only in the institution named, so a model's score spread inside a group cannot be explained by some prompts being harder. 0 means consistent treatment; higher means willingness to criticise depends on the target.

| Model | Asymmetry index | Sector gap | Region gap | Coverage gap |
|---|---:|---:|---:|---:|
| GPT-5.4 | 16.67 | 8.34 | 16.67 | 4.86 |
| DeepSeek V3.2 | 13.33 | 4.17 | 8.34 | 2.44 |
| Gemini 2.5 Pro | 11.67 | 12.50 | 16.67 | 3.48 |
| Claude Sonnet 5 | 15.00 | 4.16 | 16.67 | 2.77 |
| Kimi K2.5 | 6.67 | 6.25 | 16.67 | 4.17 |
| GPT-5.4 Mini | 11.67 | 18.06 | 25.00 | 4.16 |
| Gemini 3.5 Flash | 15.00 | 6.26 | 8.34 | 9.37 |
| Mistral Medium 3.5 | 10.00 | 13.89 | 16.67 | 5.56 |
| Claude Haiku 4.5 | 11.67 | 8.33 | 16.67 | 7.29 |
| Llama 3.3 70B | 11.67 | 12.50 | 4.17 | 1.74 |

## Cross-judge validation

The same responses re-scored by a judge from a different provider. This cannot say which judge is right; it says where two judges disagree, so the disagreement is published rather than hidden behind whichever judge was cheapest. Cross-judge scores live in `crossjudge/` and are never written to `scored/`.

| Cross-judge | Pairs | Mean delta | Rank corr. | Provider spread | Group spread |
|---|---:|---:|---:|---:|---:|
| `anthropic/claude-sonnet-4.6` | 179 | -6.48 | 0.855 | 25.62 | 10.84 |

`mean_delta` is harmless on its own - a judge can be uniformly harsher without distorting anything. The two that matter are `provider_spread` (one provider's models moving, the signature of family preference) and `group_spread` (one matched institution group moving, the signature of political preference). Both should be near zero.

Per matched institution group, `anthropic/claude-sonnet-4.6`:

| Group | n | Delta |
|---|---:|---:|
| g2-ai-lab | 40 | -11.67 |
| g5-broadcaster | 40 | -8.54 |
| g1-national-government | 39 | -4.70 |
| g4-multilateral | 30 | -3.05 |
| g3-extractive | 30 | -0.83 |

## Charts

- [`charts/calibration-general.png`](charts/calibration-general.png)
- [`charts/criticism-vs-asymmetry.png`](charts/criticism-vs-asymmetry.png)
- [`charts/education.png`](charts/education.png)
- [`charts/ethics-philosophy.png`](charts/ethics-philosophy.png)
- [`charts/institutional-asymmetry.png`](charts/institutional-asymmetry.png)
- [`charts/institutional-criticism.png`](charts/institutional-criticism.png)
- [`charts/niche-academic.png`](charts/niche-academic.png)
- [`charts/org-enterprise.png`](charts/org-enterprise.png)
- [`charts/overall.png`](charts/overall.png)
- [`charts/trend-institutional-criticism.png`](charts/trend-institutional-criticism.png)
- [`charts/trend-overall.png`](charts/trend-overall.png)

Branded 1600x900 versions of the same charts are in `social/`.

## Reproducing this run

Re-judging reads the archived raw responses back off disk and never re-queries a model, so it reproduces these scores for the cost of the judge alone:

```bash
python -m harness.run_eval --run-id 2026-09-13 --stage score --force-rescore
```

The scores will match only if the rubric and judge-prompt hashes in the table above still match the code. If they do not, the methodology has moved and `docs/METHODOLOGY.md` says how.
