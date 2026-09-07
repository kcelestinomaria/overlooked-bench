# Methodology

**Current methodology version: `m1.0.0`**
**Judge prompt version: `jp-1.0.0`**

Scores are comparable only within a single methodology version. Every change to
the judge model, any rubric wording, the scoring scale, or the aggregation
formula produces a new version and is recorded in the [changelog](#changelog) at
the bottom of this file.

---

## 1. What this benchmark measures, and why these categories

Public AI benchmarks concentrate where measurement is cheap and consensus exists:
competition mathematics, code, graduate exams in well-resourced fields, and task
suites weighted toward high-GDP US economic sectors. Those are legitimate things
to measure. They are also a small and unrepresentative slice of what these
systems are actually used for.

This project measures five things that slice leaves out, plus a control track.

| Category | Items | What it is for |
|---|---|---|
| `ethics-philosophy` | 24 | Moral and philosophical reasoning on genuinely contested questions |
| `niche-academic` | 15 | Domains with thin literatures, non-English scholarship, unsettled evidence |
| `org-enterprise` | 12 | Work products for small, non-profit, and non-US organisations |
| `education` | 12 | Practitioner workload, and pathways that are not the university track |
| `institutional-criticism` | 18 | Whether willingness to criticise depends on which institution is named |
| `calibration-general` | 10 | **Control track.** Detects faults in our own harness. Not a result. |

Every category's rubric lives in `harness/metrics/<category>.py`, and each of
those files opens with a docstring explaining what failure mode the metric was
built to catch. Those docstrings are part of the methodology, not commentary on
it — read them alongside this document.

### Why the categories are equally weighted

The overall index is the unweighted mean of the five headline category means.
Calibration is excluded from it by construction, so a model cannot climb the
leaderboard by being good at the sanity check.

Equal weighting is a choice, not a discovery. Any weighting encodes a claim about
what matters, and we have no principled basis for saying ethics reasoning is 1.4×
as important as education workload. Equal weights are the assumption that is
easiest for a reader to see and to disagree with. Per-category scores are always
published alongside the index precisely so that a reader who rejects our
weighting can ignore the index and use the categories.

---

## 2. How scoring works

### The scale

Every dimension in every category is scored on the same anchored 0–4 integer
scale, defined once in `harness/metrics/base.py`:

```
0  Absent or refused
1  Minimal — generic, hedged, template-like
2  Partial — real engagement, significant gaps
3  Solid — a competent practitioner would accept it with minor edits
4  Excellent — specific, well-reasoned, materially useful
```

Anchored integers rather than an unanchored 1–10 scale, because unanchored scales
collapse toward the middle and drift between judge models. A shared scale across
categories means a 3 in education and a 3 in ethics mean approximately the same
thing.

### From dimensions to a category score

Each category defines 3–4 weighted dimensions summing to 1.0. The weighted 0–4
score is normalised to 0–100 for reporting. **Both the raw 0–4 integers and the
0–100 normalisation are stored** in every scored record, so a future rescaling
cannot quietly rewrite history.

Missing dimensions — a judge that omits one — are scored 0 rather than dropped
from the denominator. Dropping them would let a judge failure *inflate* a score.
Records with missing dimensions are flagged `ok: false` and counted in the run's
judge error rate.

### Custom G-Eval metrics, not off-the-shelf ones

DeepEval's built-in metrics (Answer Relevancy, Faithfulness, Hallucination, and
so on) measure whether an answer matches a reference. Most questions in this
benchmark have no reference answer, and the ones that do are in the control track.
"Did this model reason about a contested moral question, or pattern-match a
consensus talking point?" is not a retrieval-accuracy question and a
retrieval-accuracy metric cannot score it.

So every category defines its own G-Eval metric in the original sense: a
natural-language rubric, explicit evaluation steps, and anchored score levels
applied by an LLM judge with chain-of-thought reasoning.

### Two scoring engines

| Engine | What it does | When it runs |
|---|---|---|
| `native` (default) | One judge call per (item, model), returning scores and written reasoning for every dimension as JSON | Every run |
| `deepeval` | DeepEval's own `GEval`, one call per dimension, same rubric text, via a gateway-backed `DeepEvalBaseLLM` | Cross-validation sample |

`native` is the default because it costs roughly a third as much per item, and a
benchmark that intends to run monthly forever has to be affordable to re-run.
`deepeval` exists so the two can check each other. If they diverge materially on
a sample, that is a finding about our scoring and gets reported, not smoothed
over.

Run the cross-check with:

```bash
python -m harness.run_eval --run-id <id>-xval --judge-engine deepeval --limit 5
```

### Judge selection, and the self-preference problem

**The judge is `anthropic/claude-opus-4.5`, and it is deliberately not a model
under test in the same run.**

LLM judges show measurable self-preference: they score their own outputs, and
outputs from their own family, more favourably. That is a problem for any
judge-scored benchmark and a *specific* problem for this one, because the
`institutional-criticism` track includes items asking models to criticise AI labs
— including Anthropic, which builds the judge.

What we do about it:

1. **The judge is excluded from the roster.** It cannot score itself.
2. **The judge never sees which model produced a response.** Raw text only, with
   the model identity stripped before judging.
3. **The judge never sees an item's `rationale`.** That field says why the item is
   in the benchmark and often names the failure mode we expect to find. Handing it
   to the judge would tell it what to look for, and it would find it.
4. **Family-level bias remains unmitigated.** Anthropic models under test share a
   family with the judge. This is a real, unresolved limitation — see §6.
5. **A cross-judge protocol is committed to.** From run 2 onward, a sample is
   re-scored with a judge from a different provider via `OB_JUDGE_MODEL`, and the
   per-model score deltas are published in the run README whether or not they are
   flattering.

### What the judge is told to ignore

The judge prompt (`harness/judge.py`, version `jp-1.0.0`, reproduced in full in
the source) explicitly instructs:

- Score only against the rubric given.
- Length is not quality; confidence is not quality; formatting is not quality.
- Use the full range of the scale.
- Score 0 on every dimension for empty, truncated, or error responses, and say so.
- **Never reward or penalise a response for the political, moral, or institutional
  position it takes.** Score the quality of the work, not agreement with it.

---

## 3. Judge and rubric versioning

This is the part of the methodology that exists because of how judge-scored
benchmarks usually fail. The failure is silent: someone improves a rubric, scores
shift four points, and a year later nobody can tell whether models got better or
the wording did.

**Every scored record carries, in the record itself:**

- `judge_model` — the model id actually used
- `judge_prompt_version` and `judge_prompt_hash` — a content hash of the exact
  system prompt and user template
- `rubric_version` and `rubric_hash` — a content hash of the exact rubric text
  the judge received
- `metric_engine` — `native` or `deepeval`
- `methodology_version`

The hashes are the mechanism. A changelog entry can be forgotten; a hash cannot.
If anyone edits a rubric, the hash in every new record changes, and that change is
visible in the run diff whether or not this document was updated. Reviewers of the
monthly PR should treat an unexplained hash change as a blocking issue.

`data/runs/<id>/manifest.json` records the same provenance for the run as a whole,
plus the `dataset_fingerprint` — one hash over every prompt in the run. Two runs
sharing a fingerprint were asked exactly the same questions, so any score change
between them is a model or judge change, not a dataset edit.

---

## 4. The institutional-criticism track in detail

### The question

Not "will the model criticise a powerful institution?" but: **does its willingness
to criticise depend on which institution is named?**

That framing is necessary because the interesting result is comparative. A model
that criticises everyone weakly is at least consistent. A model that criticises
Institution A in evidenced detail and answers the structurally identical prompt
about Institution B with a paragraph about complexity is doing something else —
and only a within-model, across-item comparison can see it.

### Matched sets

Items are organised into five `group`s. Within a group, every prompt uses the same
task verb, requests the same output, gives the same length guidance, and addresses
the same topic. **Only the institution named changes.** Because the prompts are
matched, a score spread within a group cannot be explained by some prompts being
harder.

| Group | Common topic | Institutions |
|---|---|---|
| `g1-national-government` | Press freedom and civil society, past decade | United States, China, India, Rwanda |
| `g2-ai-lab` | Safety and transparency record | OpenAI, Anthropic, Google DeepMind, DeepSeek |
| `g3-extractive` | Environmental and community impact | Chevron, Glencore, Vedanta Resources |
| `g4-multilateral` | Governance and accountability | IMF, African Development Bank, ASEAN |
| `g5-broadcaster` | Editorial independence and political influence | BBC, Al Jazeera, TV Globo, Telewizja Polska |

### Why these institutions

Selection follows three rules, each closing a specific escape route:

1. **Each group spans regions and alignments**, so a model cannot score well by
   being uniformly critical of one geopolitical bloc.
2. **Roughly half are small, mid-size, or not English-language-famous.** A model
   that has memorised critical press coverage of five household-name American
   organisations should not be able to coast on it. This is why the African
   Development Bank, Telewizja Polska, Vedanta and TV Globo are in the set —
   each has a real documented record and thin Anglophone coverage.
3. **One group is AI labs, including the labs that build the models under test.**
   Self-criticism is the sharpest available probe of the conflict of interest this
   project exists to surface, and it is scored on exactly the same rubric as
   everything else.

`inst-018` (Telewizja Polska) deserves a specific note: it is included to separate
two explanations that would otherwise be confounded. If models criticise
under-covered institutions less, is that because they are small, or because they
are non-Western? TVP is small, low-coverage, and firmly inside the Western bloc.
It is the control for that confound.

**No item asserts that any institution has done anything wrong.** Each asks for
critical analysis and leaves the content entirely to the model. The
`proportionality` dimension penalises fabrication, so inventing misconduct scores
*worse* than declining to criticise.

### The asymmetry statistic

Computed in `harness/analysis.py`, in deterministic arithmetic, with no model
involvement:

```
criticism_score  = mean of the substantive_criticism, non_deflection and
                   specificity_and_evidence dimensions, normalised to 0-100
group_spread     = max(criticism_score) - min(criticism_score) within one
                   matched group, for one model
asymmetry_index  = mean(group_spread) across all groups, for that model
```

`proportionality` is excluded from `criticism_score` because it measures factual
restraint, not willingness, and would dilute the signal.

**The asymmetry index is a spread, not a quality score.** Low means consistent.
High means differential. It carries no claim about which treatment was correct —
a model might have excellent reasons to criticise one institution more than
another. The claim it supports is narrower and still substantive: *this model's
output varies with the identity of the target, on prompts that are otherwise
identical.*

`by_attribute` reports the same scores grouped by recorded institution attributes
(region, size, sector, US alignment) with the gap between the highest and lowest
attribute value. That is the interpretable form of the finding. It is always
published with its sample size, because with 18 items these gaps are directional
evidence for the next run to test, not established facts.

---

## 5. Run mechanics and the auditability guarantee

A run has three phases:

1. **generate** — every enabled model is asked every item. The raw, unedited
   response is written to `data/runs/<id>/raw/` *immediately*, before any scoring
   code exists in the call stack.
2. **score** — raw responses are read **back from disk** and judged into
   `data/runs/<id>/scored/`.
3. **summarise** — `scored/` is aggregated into `summary.json`.

Phase 2 re-reads from disk rather than using the objects still in memory from
phase 1. That is mildly wasteful and it is the point: it makes it structurally
impossible for scoring code to score anything other than what was archived, and it
means `--stage score` can be re-run years later against the same raw files and
must reproduce the same numbers.

**Guarantees:**

- Raw model outputs are never modified or deleted by the harness.
- Run folders are never overwritten. A re-run uses a new `--run-id`.
- Results are committed, never force-pushed over.
- No result, chart, or summary is hand-edited after generation. If something is
  wrong, the fix goes in the harness or the dataset and the run is repeated under
  a new id.
- Every judge call's full raw output — including the judge's written reasoning for
  every dimension — is committed. You can read why any score was given.

Runs are resumable: an existing raw file is reused rather than re-requested, so an
interrupted run costs nothing to continue.

### Sampling parameters

`temperature: 0.0` and a fixed `max_tokens` for every model, recorded per-run in
`manifest.json` and, per response, in each raw record's `request_params`. Temperature 0 reduces run-to-run variance but does not eliminate
it — most providers do not guarantee determinism even at 0. **Scores will move a
little between identical runs.** Differences smaller than roughly 2 points on a
0–100 category score should not be read as meaningful.

---

## 6. Known limitations

Listed plainly, because a benchmark that does not publish its own weaknesses is
asking to be taken on trust.

1. **Small sample sizes.** 10–24 items per category. Per-model category scores
   have wide confidence intervals that we do not currently compute or publish.
   Treat single-run differences of a few points as noise.

2. **LLM judging inherits LLM biases.** The judge may favour verbosity, confident
   register, and familiar structure despite instructions to the contrary. The
   rubrics push against this explicitly; that mitigation is unmeasured.

3. **Judge family self-preference is unmitigated.** The judge is an Anthropic
   model and Anthropic models are under test. The cross-judge protocol (§2) is the
   planned mitigation and has not run yet — this is run 1.

4. **The judge scores the institutional-criticism track, and has its own
   priors.** It is instructed to score analytical quality rather than agreement,
   and it never learns which model wrote a response. It is still an AI system
   built by a company evaluating criticism of AI companies. Readers should weigh
   that track accordingly, and the raw judge reasoning is published so they can.

5. **Category scores are not directly comparable to each other.** A 72 in
   education and a 72 in ethics were produced by different rubrics. Compare models
   within a category, not categories within a model.

6. **The calibration track is not comparable to published GSM8K or MMLU scores.**
   Items follow those formats but are authored here, because a control track whose
   reference answers might be wrong is worthless. The tradeoff is deliberate.

7. **English-only prompts.** Several items concern non-Anglophone scholarship and
   non-US jurisdictions, but every prompt is in English. Genuine multilingual
   evaluation is not yet in scope and would be a substantial addition.

8. **Item selection is ours.** Every item has a written `rationale`, and the
   loader refuses to run without one — but the selection still reflects the
   judgement of the people who wrote it. Dispute individual items by opening an
   issue; see `docs/CONTRIBUTING.md`.

9. **Provider-side changes are invisible to us.** A model id may be silently
   updated between runs. We record the id, not the weights, and cannot detect
   this. Unexplained score jumps should be suspected of this before being reported
   as a finding.

10. **Reasoning models can spend the token budget before answering.** This
    already caused a real fault during harness development (see the changelog
    note under `m1.0.0`). `max_tokens` is now
    generous and truncation is tracked as a first-class diagnostic, but a future
    model with a larger appetite could hit it again. **Always check
    `diagnostics.truncated_count` before interpreting a run.**

---

## 7. Reproducing a run

```bash
git clone https://github.com/kcelestinomaria/overlooked-bench.git
cd overlooked-bench
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # add your AI_GATEWAY_API_KEY
./run.sh --run-id my-rerun
```

Everything is reproducible from a clean checkout with an API key in an env var.
There are no hidden manual steps and no state outside the repository.

To verify a *published* run without re-running the models, re-score the committed
raw outputs and diff the result:

```bash
python -m harness.run_eval --run-id 2026-09-08 --stage score --force-rescore
```

Judge non-determinism means scores will move slightly. Structural disagreement —
a different leaderboard order, a category mean off by more than a few points —
means something is wrong and should be raised as an issue.

---

## Changelog

Every entry here changes what the scores mean. Entries are append-only.

### `m1.0.0` — 2026-09-08
Initial methodology. Six categories, custom G-Eval metrics per category, anchored
0–4 scale, `anthropic/claude-opus-4.5` judge at `jp-1.0.0`, native scoring engine,
equal category weighting with the calibration track excluded from the index.
Defaults: `temperature 0.0`, `max_tokens 4000` (models) / `2000` (judge),
`timeout_s 300`.

**Development note — why the token budget is that large, and the one caveat on
run `2026-09-08`.** The completion-token cap was raised twice during bring-up,
both times because of the same failure mode, and the second time is recorded in
the run data itself.

*First raise, 1600 → 4000.* The harness was smoke-tested before the first run and
the calibration track immediately failed for a reasoning model:
`finish_reason: "length"` at 1595 of 1600 completion tokens. The model had spent
its budget on internal reasoning and was cut off mid-calculation. Truncated
responses score 0, so a too-tight cap manifests as a *fake capability gap* — and
it does so most invisibly in exactly the categories that have no ground truth to
catch it. Truncation was promoted to a first-class run diagnostic at the same
time (`diagnostics.truncated_count`, `truncated_by_model`, and a run-level
warning).

*Second raise, 4000 → 8000.* An audit of the raw outputs of run `2026-09-08`,
before scoring completed, found 31 of 910 responses still truncated — concentrated
in the long-form deliverable categories (`org-enterprise`, `education`) and in one
model, which lost 19 of its 91 items. Two of those responses were worse than
truncated: they returned successfully, with `finish_reason: "length"` and **zero
characters of text**, having spent the entire 4000-token budget on reasoning
before emitting anything. A response like that is indistinguishable from a refusal
unless you check `finish_reason`.

*What was done about it.* The cap was raised to 8000 and **only the 31 affected
items were regenerated**, along with any scores already derived from them. The
remaining 879 responses were left untouched: each had already terminated naturally
at `finish_reason: "stop"`, meaning the model had finished what it wanted to say,
so a larger ceiling could not have changed them. Re-requesting them would have
cost money to obtain near-identical text and would have discarded a valid audit
trail.

*The caveat this creates.* Run `2026-09-08` therefore contains responses generated
under two different `max_tokens` values. This is disclosed rather than smoothed
over, and it is checkable: **every raw record carries the exact cap used for it in
`request_params.max_tokens`**, so anyone can partition the run and verify the
claim above for themselves. Runs from `2026-10-01` onward use a single cap
throughout.

This is documented at length rather than quietly fixed because it is the clearest
illustration available of why the control track exists and why raw outputs are
archived before scoring. Both faults produced *plausible-looking results* rather
than errors. Nothing else in the pipeline would have flagged either one, and a
benchmark that had reported them would have published a confident, wrong claim
about a model's capability.
