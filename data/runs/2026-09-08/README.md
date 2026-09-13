# overlooked-bench run `2026-09-08`

10 models over 91 items in 6 categories. Generated 2026-09-07T23:46:59Z.

Every number on this page is read directly from `summary.json`, which is aggregated from `scored/`, which is judged from `raw/`. Nothing here is hand-written. If a number looks wrong, the fix is in the harness or the dataset and the run is repeated under a new id.

## Read this first

- **Truncation:** 2 response(s) hit the max_tokens ceiling and were truncated. Truncated responses score near zero and will look like a capability gap. Raise max_tokens in data/models.yaml and re-run the affected models before interpreting these scores.
- **Judge errors:** 28 of 910 judgings (3.08%) did not produce a usable score and are excluded from the means below rather than scored 0.

## Provenance

| Field | Value |
|---|---|
| Judge model | `deepseek/deepseek-v3.1-terminus` |
| Judge prompt | `jp-1.0.0` (hash `71150128d9966002`) |
| Scoring engine | `native` |
| Methodology | `m1.2.0` |
| Harness | `0.1.0` |
| Dataset fingerprint | `78198b54a6f421a2` |
| Total cost | $11.21 |

Rubric hashes:

| Category | Rubric hash |
|---|---|
| Calibration (General) | `958f87dc04cdd1dd` |
| Education | `354de6036e071fa8` |
| Ethics & Philosophy | `5ac42b278c4bf234` |
| Institutional Criticism | `aa9183e1f22b6d16` |
| Niche Academic | `25dae73dc6623e3e` |
| Org & Enterprise | `ec54e82f734da3f6` |

## Overall

The overall index is the mean of the five headline category scores. The calibration track is a control and is excluded from it by design.

| # | Model | Provider | Tier | Overall |
|---:|---|---|---|---:|
| 1 | GPT-5.4 | openai | frontier | 86.6 |
| 2 | DeepSeek V3.2 | deepseek | mid | 84.8 |
| 3 | Gemini 3.5 Flash | google | mid | 82.9 |
| 4 | Claude Sonnet 5 | anthropic | frontier | 82.5 |
| 5 | GPT-5.4 Mini | openai | mid | 80.5 |
| 6 | Gemini 2.5 Pro | google | frontier | 80.4 |
| 7 | Kimi K2.5 | moonshotai | mid | 80.1 |
| 8 | Mistral Medium 3.5 | mistral | mid | 77.0 |
| 9 | Claude Haiku 4.5 | anthropic | small | 72.4 |
| 10 | Llama 3.3 70B | meta | mid | 56.5 |

## By category

| Model | Ethics & Philosophy (n=24) | Niche Academic (n=15) | Org & Enterprise (n=12) | Education (n=12) | Institutional Criticism (n=18) | Calibration (General) (n=10) |
|---|---|---|---|---|---|---|
| GPT-5.4 | 88.3 | 95.8 | 94.4 | 64.0 | 90.3 | 100.0 |
| DeepSeek V3.2 | 76.8 | 95.8 | 89.9 | 64.9 | 96.7 | 100.0 |
| Gemini 3.5 Flash | 65.3 | 98.7 | 95.8 | 62.6 | 92.3 | 94.0 |
| Claude Sonnet 5 | 83.6 | 84.8 | 79.7 | 69.2 | 95.5 | 100.0 |
| GPT-5.4 Mini | 73.2 | 92.7 | 85.5 | 64.3 | 86.7 | 100.0 |
| Gemini 2.5 Pro | 80.3 | 98.2 | 72.7 | 59.1 | 91.6 | 100.0 |
| Kimi K2.5 | 78.8 | 85.7 | 84.1 | 56.5 | 95.3 | 100.0 |
| Mistral Medium 3.5 | 74.5 | 74.2 | 87.0 | 56.9 | 92.2 | 99.4 |
| Claude Haiku 4.5 | 73.6 | 74.5 | 67.1 | 58.1 | 88.8 | 99.6 |
| Llama 3.3 70B | 62.5 | 64.5 | 47.0 | 27.5 | 80.8 | 91.4 |

### Calibration control

Items with known answers, used to check the harness before any other number is believed. Floor is 60.0; mean across all models is 98.44. A model far below the floor indicates a harness or transport fault, not a capability finding.

## Institutional asymmetry

Prompts inside a matched group differ only in the institution named, so a model's score spread inside a group cannot be explained by some prompts being harder. 0 means consistent treatment; higher means willingness to criticise depends on the target.

| Model | Asymmetry index | Sector gap | Region gap | Coverage gap |
|---|---:|---:|---:|---:|
| GPT-5.4 | 15.00 | 4.17 | 16.67 | 4.17 |
| DeepSeek V3.2 | 8.33 | 8.34 | 8.34 | 6.25 |
| Gemini 3.5 Flash | 16.67 | 12.50 | 20.83 | 11.11 |
| Claude Sonnet 5 | 11.67 | 10.42 | 16.67 | 3.47 |
| GPT-5.4 Mini | 13.34 | 8.34 | 25.00 | 2.78 |
| Gemini 2.5 Pro | 10.00 | 16.67 | 16.67 | 4.86 |
| Kimi K2.5 | 11.67 | 8.34 | 16.67 | 9.38 |
| Mistral Medium 3.5 | 8.34 | 14.59 | 16.67 | 2.09 |
| Claude Haiku 4.5 | 11.67 | 11.11 | 16.67 | 8.34 |
| Llama 3.3 70B | 10.00 | 14.58 | 12.50 | 6.94 |

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

Branded 1600x900 versions of the same charts are in `social/`.

## Reproducing this run

Re-judging reads the archived raw responses back off disk and never re-queries a model, so it reproduces these scores for the cost of the judge alone:

```bash
python -m harness.run_eval --run-id 2026-09-08 --stage score --force-rescore
```

The scores will match only if the rubric and judge-prompt hashes in the table above still match the code. If they do not, the methodology has moved and `docs/METHODOLOGY.md` says how.
