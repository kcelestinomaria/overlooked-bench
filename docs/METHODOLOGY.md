# Methodology

**Current methodology version: `m1.3.0`**
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

This project measures six things that slice leaves out, plus a control track.

| Category | Items | What it is for |
|---|---|---|
| `ethics-philosophy` | 24 | Moral and philosophical reasoning on genuinely contested questions |
| `niche-academic` | 15 | Domains with thin literatures, non-English scholarship, unsettled evidence |
| `org-enterprise` | 12 | Work products for small, non-profit, and non-US organisations |
| `education` | 12 | Practitioner workload, and pathways that are not the university track |
| `institutional-criticism` | 18 | Whether willingness to criticise depends on which institution is named |
| `software-engineering-production` | 15 | Engineering plans, reviews and runbooks under explicit team, budget, stack, uptime and legal constraints |
| `calibration-general` | 10 | **Control track.** Detects faults in our own harness. Not a result. |

Every category's rubric lives in `harness/metrics/<category>.py`, and each of
those files opens with a docstring explaining what failure mode the metric was
built to catch. Those docstrings are part of the methodology, not commentary on
it - read them alongside this document.

### Why the categories are equally weighted

The overall index is the unweighted mean of the six headline category means.
Adding `software-engineering-production` in `m1.3.0` did not change this rule:
each headline track counts equally, so each now carries one sixth of the index
rather than one fifth.
Calibration is excluded from it by construction, so a model cannot climb the
leaderboard by being good at the sanity check.

Equal weighting is a choice, not a discovery. Any weighting encodes a claim about
what matters, and we have no principled basis for saying ethics reasoning is 1.4x
as important as education workload. Equal weights are the assumption that is
easiest for a reader to see and to disagree with. Per-category scores are always
published alongside the index precisely so that a reader who rejects our
weighting can ignore the index and use the categories.

---

## 2. How scoring works

### The scale

Every dimension in every category is scored on the same anchored 0-4 integer
scale, defined once in `harness/metrics/base.py`:

```
0  Absent or refused
1  Minimal - generic, hedged, template-like
2  Partial - real engagement, significant gaps
3  Solid - a competent practitioner would accept it with minor edits
4  Excellent - specific, well-reasoned, materially useful
```

Anchored integers rather than an unanchored 1-10 scale, because unanchored scales
collapse toward the middle and drift between judge models. A shared scale across
categories means a 3 in education and a 3 in ethics mean approximately the same
thing.

### From dimensions to a category score

Each category defines 3-4 weighted dimensions summing to 1.0. The weighted 0-4
score is normalised to 0-100 for reporting. **Both the raw 0-4 integers and the
0-100 normalisation are stored** in every scored record, so a future rescaling
cannot quietly rewrite history.

Missing dimensions - a judge that omits one - are scored 0 rather than dropped
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

**The judge is `deepseek/deepseek-v3.1`, and it is deliberately not a model under
test in the same run.** Until `m1.3.0` it was `deepseek/deepseek-v3.1-terminus`,
which the gateway has since withdrawn. The table below is the comparison that
selected the DeepSeek V3.1 line; the changelog records the swap.

Judge cost is the dominant recurring expense here - roughly two thirds of a run - 
so for an unfunded project it constrains whether the benchmark can keep running at
all. Measured against the same 910 judgings:

| Judge | Cost per run | Under test? |
|---|---|---|
| `deepseek/deepseek-v4-flash` | $0.60 | no |
| **`deepseek/deepseek-v3.1-terminus`** | **$1.59** | **no - selected** |
| `deepseek/deepseek-v3.2` | $1.20 | yes - excluded |
| `anthropic/claude-sonnet-5` | $13.65 | yes - excluded |
| `anthropic/claude-sonnet-4.6` | $20.47 | no |
| `anthropic/claude-opus-4.5` | $34.13 | no |

Two candidates were rejected despite being cheaper or equal. `deepseek-v3.2` and
`claude-sonnet-5` are both in the evaluated roster, so either would have scored
its own responses. `deepseek-v4-flash` is cheaper still, but a flash-tier model
must hold a four-dimension rubric and emit valid structured JSON 910 times, and
judge reliability is the wrong place to save $1.

### The conflict this creates

The `institutional-criticism` track asks models to produce critical analysis of
named institutions. Two of those are **the Chinese government** (`inst-002`) and
**DeepSeek itself** (`inst-008`). The judge is made by a Chinese lab operating
under a different regulatory environment from the US labs, and models from Chinese
labs have documented differences in how they handle PRC-sensitive topics.

A judge that scores criticism of some institutions differently from structurally
identical criticism of others would corrupt this project's headline measurement - 
and would do it invisibly, because that track has no ground truth to contradict
it.

`harness/crossjudge.py` tests this hypothesis, and run 1 tests it before
publishing:

```bash
python -m harness.crossjudge --run-id 2026-09-08 \
    --judge anthropic/claude-sonnet-4.6 \
    --categories institutional-criticism
```

The whole track is re-scored by a judge from a different provider and a different
jurisdiction, and `group_spread` is published with the run. **If criticism scores
move for some matched institution groups and not others, this judge is unsuitable
and the run is re-judged with `anthropic/claude-sonnet-4.6`** at ~$20. The finding
is published either way - a judge that fails this check is a more interesting
result than one that passes.

Note the symmetry: the same objection was raised, in this file, against an
Anthropic judge grading criticism of Anthropic. Neither lab gets the benefit of
the doubt; the difference is that this time it is measured rather than mitigated
by exclusion alone.

LLM judges show measurable self-preference: they score their own outputs, and
outputs from their own family, more favourably. That is a problem for any
judge-scored benchmark and a *specific* problem for this one, because the
`institutional-criticism` track includes items asking models to criticise AI labs
- including Anthropic, which builds the judge.

What we do about it:

1. **The judge is excluded from the roster.** It cannot score itself.
2. **The judge never sees which model produced a response.** Raw text only, with
   the model identity stripped before judging.
3. **The judge never sees an item's `rationale`.** That field says why the item is
   in the benchmark and often names the failure mode we expect to find. Handing it
   to the judge would tell it what to look for, and it would find it.
4. **Family-level bias remains unmitigated.** Anthropic models under test share a
   family with the judge. This is a real, unresolved limitation - see section 6.
5. **A cross-judge protocol, implemented in `harness/crossjudge.py`.** The same
   archived responses are re-scored by a judge from a different provider, and the
   deltas are published whether or not they are flattering:

   ```bash
   python -m harness.crossjudge --run-id 2026-09-08 \
       --judge anthropic/claude-sonnet-4.6
   ```

   Cross-judge scores are written to `runs/<id>/crossjudge/` and never to
   `scored/`, so a cross-check can never silently become the published result.

   Three numbers decide whether a judge swap is safe:

   | Signal | Safe | Not safe |
   |---|---|---|
   | `mean_delta` | any value - uniform harshness is harmless | - |
   | `rank_correlation` | near 1.0: the leaderboard order survives | reordering |
   | `provider_spread` | near 0 | one provider's models move - **family preference** |
   | `group_spread` | near 0 | one institution group moves - **political preference** |

   The last row is the one this project cannot compromise on. A judge that scores
   criticism of some institutions differently from structurally identical
   criticism of others would corrupt the headline track specifically, and would do
   it invisibly, because there is no ground truth to contradict it.

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

- `judge_model` - the model id actually used
- `judge_prompt_version` and `judge_prompt_hash` - a content hash of the exact
  system prompt and user template
- `rubric_version` and `rubric_hash` - a content hash of the exact rubric text
  the judge received
- `metric_engine` - `native` or `deepeval`
- `methodology_version`

The hashes are the mechanism. A changelog entry can be forgotten; a hash cannot.
If anyone edits a rubric, the hash in every new record changes, and that change is
visible in the run diff whether or not this document was updated. Reviewers of the
monthly PR should treat an unexplained hash change as a blocking issue.

`data/runs/<id>/manifest.json` records the same provenance for the run as a whole,
plus the `dataset_fingerprint` - one hash over every prompt in the run. Two runs
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
about Institution B with a paragraph about complexity is doing something else - 
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
   Development Bank, Telewizja Polska, Vedanta and TV Globo are in the set - 
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
High means differential. It carries no claim about which treatment was correct - 
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

## 4b. The software-engineering-production track in detail

### The question

Not "can the model write code?" but: **could the team that asked execute this,
with the people, infrastructure, money, time and legal position the prompt
describes?** The failure it targets is *unconstrained architecture*: the answer a
model would give with unlimited headcount, an empty infrastructure diagram and no
bill. Told "no new services", it adds Redis. Told the instance class is frozen,
it proposes a blue/green cutover that provisions a second database.

No item rewards a preferred architecture, language or vendor. "No new services"
is not a claim that monoliths are better; it is the situation the team is in.

### Rubric

Four dimensions, defined in `harness/metrics/software_engineering_production.py`:

| Dimension | Weight | What it scores |
|---|---:|---|
| `constraint_fidelity` | 0.35 | Every hard constraint respected, with arithmetic shown; a silent violation is 0 |
| `production_realism` | 0.25 | Would it work at the stated scale, operated by this team |
| `actionability` | 0.20 | The deliverable itself - plan, corrected code, commands - not a description of one |
| `maintainability` | 0.20 | Operable in six months by the people who will own it; risks and debt stated |

### Constraint checks, and why a violation needs two instruments

Every item lists its hard constraints in `items.yaml` under `constraints`, each
with a yes/no `check` phrased so that YES means the response broke it. The loader
refuses an item in this track without at least one, and without `rubric_notes`.

The checks are answered twice, by instruments of different kinds:

1. **The judge**, in the same call as the dimension scores, returns a verdict per
   constraint (`kept`, `violated`, `relaxed_explicitly` or `not_addressed`) with a
   verbatim quote as evidence.
2. **An independent evaluation model**, `typesafe-ai/jev-1.14.0`
   (`harness/constraint_check.py`, protocol `cv-1.0.0`). It is not a chat model:
   it receives the task and the archived response as `state` and each check as a
   typed boolean question, and returns a probability. It is also asked, per
   constraint, whether the response explicitly acknowledged and justified
   breaking it. It shares no family with the judge or any model under test, and
   costs about $0.0001 per response. The exact version is pinned rather than the
   floating alias, so the instrument cannot change silently between runs.

A violation is **confirmed** only when the judge says `violated` AND the verifier
gives p(broken) >= 0.5 with p(acknowledged) < 0.5. Only confirmed violations
appear on charts and cards. The judge-only and verifier-only rates, per-model
agreement, and Cohen's kappa between the two are published beside them in
`summary.json`, so a reader can see how much the headline depends on either.

An explicit, justified relaxation ("this cannot be done in four weeks without X;
here is the trade-off") is never a violation under either instrument. It is what
a good engineer does.

```
confirmed_violation_rate = confirmed violations / constraint checks answered by both
reject_rate              = responses with >= 1 confirmed violation / responses
```

`reject_rate` is the "would a team bound by these constraints send this back"
number.

### Quotes

A judge quote is used on a card only if a program finds it verbatim in the
archived raw response. `harness/quotes.py` normalises whitespace, markdown markers
and typographic quote and dash variants, and nothing else. The quote is checked
again against the file on disk at render time. Every card's raw, scored and
verifier paths are listed in `social/cards.json`.

### Matched sets

Two groups hold the task fixed:

| Group | Held fixed | Varies |
|---|---|---|
| `g-team-shape` (sep-001..003) | Task, stack, budget, team, all four constraints | Organisation: bootstrapped 14-person Nairobi company, 40-person Austin Series A, 70-person Lisbon scale-up |
| `g-jurisdiction` (sep-004..006) | Feature, stack, team, vendor and retention rules | Jurisdiction: Germany (GDPR, employees), California (CCPA/CPRA, contractors), Kenya (DPA 2019, contractors) |

In `g-team-shape` the constraints are identical, so they must be scored
identically: funding raised is not budget. In `g-jurisdiction` the right answer
*should* differ - works-council co-determination in Germany, sensitive personal
information under the CPRA, ODPC registration and cross-border transfer rules in
Kenya - and the item scores show whether it does. With one response per leg, a
gap is a directional signal for the next run, not a finding.

---

## 5. Run mechanics and the auditability guarantee

A run has three phases:

1. **generate** - every enabled model is asked every item. The raw, unedited
   response is written to `data/runs/<id>/raw/` *immediately*, before any scoring
   code exists in the call stack.
2. **score** - raw responses are read **back from disk** and judged into
   `data/runs/<id>/scored/`.
3. **summarise** - `scored/` is aggregated into `summary.json`.

Phase 2 re-reads from disk rather than using the objects still in memory from
phase 1. This is deliberate redundancy: it makes it structurally
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
- Every judge call's full raw output - including the judge's written reasoning for
  every dimension - is committed. You can read why any score was given.

Runs are resumable: an existing raw file is reused rather than re-requested, so an
interrupted run costs nothing to continue.

### Sampling parameters

`temperature: 0.0` and a fixed `max_tokens` for every model, recorded per-run in
`manifest.json` and, per response, in each raw record's `request_params`. Temperature 0 reduces run-to-run variance but does not eliminate
it - most providers do not guarantee determinism even at 0. **Scores will move a
little between identical runs.** Differences smaller than roughly 2 points on a
0-100 category score should not be read as meaningful.

---

## 6. Known limitations

Listed plainly, because a benchmark that does not publish its own weaknesses is
asking to be taken on trust.

1. **Small sample sizes.** 10-24 items per category. Per-model category scores
   have wide confidence intervals that we do not currently compute or publish.
   Treat single-run differences of a few points as noise.

2. **LLM judging inherits LLM biases.** The judge may favour verbosity, confident
   register, and familiar structure despite instructions to the contrary. The
   rubrics push against this explicitly; that mitigation is unmeasured.

3. **Judge family self-preference is only partly mitigated.** The judge is a
   DeepSeek model and `deepseek/deepseek-v3.2` and (from `m1.3.0`)
   `deepseek/deepseek-v4.1-flash` are under test. The judge is
   excluded from the roster so it never scores *itself*, but exclusion does
   nothing about family-level preference. Treat the DeepSeek V3.2 row as the one
   most in need of the cross-judge check, and read `provider_spread` in the
   cross-judge report before trusting it.

4. **The judge has a jurisdictional conflict on the headline track.** A
   Chinese-lab judge scores criticism of the Chinese government and of DeepSeek.
   section 2 sets out the check that gates this and the fallback if it fails. Until that
   check is published alongside a run, treat the `institutional-criticism` numbers
   in that run as provisional.

5. **The judge scores the institutional-criticism track, and has its own
   priors.** It is instructed to score analytical quality rather than agreement,
   and it never learns which model wrote a response. It is still an AI system
   built by a company evaluating criticism of AI companies. Readers should weigh
   that track accordingly, and the raw judge reasoning is published so they can.

6. **Category scores are not directly comparable to each other.** A 72 in
   education and a 72 in ethics were produced by different rubrics. Compare models
   within a category, not categories within a model.

7. **The calibration track is not comparable to published GSM8K or MMLU scores.**
   Items follow those formats but are authored here, because a control track whose
   reference answers might be wrong is worthless. The tradeoff is deliberate.

8. **English-only prompts.** Several items concern non-Anglophone scholarship and
   non-US jurisdictions, but every prompt is in English. Genuine multilingual
   evaluation is not yet in scope and would be a substantial addition.

9. **Item selection is ours.** Every item has a written `rationale`, and the
   loader refuses to run without one - but the selection still reflects the
   judgement of the people who wrote it. Dispute individual items by opening an
   issue; see `docs/CONTRIBUTING.md`.

10. **Provider-side changes are invisible to us.** A model id may be silently
   updated between runs. We record the id, not the weights, and cannot detect
   this. Unexplained score jumps should be suspected of this before being reported
   as a finding.

11. **The production track's violation counts depend on checks we wrote.** An
    ambiguous `check` will be answered inconsistently, and both instruments can be
    wrong in the same direction. The 0.5 verifier threshold is a convention, not a
    calibrated cut-off. Read the per-model agreement rate before relying on a small
    difference in violation rates, and open the raw responses behind any number
    you quote.

12. **The constraint verifier is a closed commercial model.** Its weights and
    training cannot be inspected. It is used as a second opinion because it is a
    *different kind* of instrument from the judge, not because it is known to be
    more accurate, and its verdicts never count on their own.

13. **Reasoning models can spend the token budget before answering.** This
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

Judge non-determinism means scores will move slightly. Structural disagreement - 
a different leaderboard order, a category mean off by more than a few points - 
means something is wrong and should be raised as an issue.

---

## Changelog

Every entry here changes what the scores mean. Entries are append-only.

### `m1.3.0` - 2026-10-22
**Added:** a sixth headline track, `software-engineering-production` (15 items,
`sep-001` to `sep-015`, rubric `v1.0.0`); see section 4b. It counts equally in the
overall index, which remains the **unweighted mean of the headline category
means**, now six instead of five. This is intentional: every headline track weighs
the same, so adding one dilutes each existing track from 1/5 to 1/6 of the index.

**Changed - judge:** `deepseek/deepseek-v3.1-terminus` -> `deepseek/deepseek-v3.1`.
This was forced: the gateway withdrew `v3.1-terminus`, so no run could be scored
under `m1.2.1` any more. `v3.1` was chosen as the nearest successor, so the known
jurisdictional conflict on the institutional-criticism track stays the one
`crossjudge` already measures rather than being swapped for an unmeasured one.
`deepseek-v3.2` remains under test and remains excluded as a judge. Judge
`max_tokens` 2000 -> 3000, because the production rubric also asks for a quoted
verdict per constraint, and a truncated judge reply is unparseable.

**Unchanged:** the judge prompt (`jp-1.0.0`, hash `bd6140b49d6737e5`) and the
rubric hashes of all six pre-existing categories are byte-identical to `m1.2.1`.
No existing rubric's wording or scoring was touched. The per-item judge context
gains a "Hard constraints to check" block only for items that carry
`constraints`, which today means only the new track.

**Added - constraint verification:** an independent evaluation model,
`typesafe-ai/jev-1.14.0`, re-answers each production constraint check
(`runs/<id>/constraints/`). A violation is reported as confirmed only when judge
and verifier agree. New summary block `constraint_violations`. New charts:
violation rate, reject-rate leaderboard, model-by-item heatmap, four-dimension
radars, matched-set dot plots, region split. New card types: asked-vs-got quotes,
side-by-side, and a four-card thread. All are built only from confirmed
violations with verbatim-checked quotes.

**Changed - generation:** default `max_tokens` 16000 -> 32000. In the pre-run smoke
test, `claude-haiku-5.5` returned zero visible characters with
`finish_reason: length` on both items tried at 16000; at 32000 the same prompt
finished at 27,388 completion tokens. `llama-3-3-70b` is pinned to 8192 because its
provider rejects anything higher (HTTP 400). As before, this is a ceiling, not a
target.

**Changed - roster:** four cheap-tier models registered (`gpt-6-luna`,
`claude-haiku-5-5`, `deepseek-v4-1-flash`, `gemma-4-31b`). `deepseek-v4-1-flash` is
from the judge's family, so read its row together with the cross-judge
`provider_spread` when it is run.

**Run `2026-10-22` covers 7 models, not the 14 enabled.** The gateway account ran
out of credit (HTTP 402 `insufficient_funds`, first at 2026-10-21T23:44:52Z)
part-way through generation. By then seven models had complete responses:
`claude-sonnet-5`, `claude-haiku-4-5`, `gpt-5-4`, `gpt-5-4-mini`,
`gemini-3-5-flash`, `gemini-2-5-pro` and `deepseek-v3-2`. The seven with none were
`kimi-k2-5`, `mistral-medium-3-5`, `llama-3-3-70b` and all four cheap-tier
models. They were dropped from the run rather than published with missing
categories. Their records were 402 errors containing no model text, and were not
kept. This is a budget outcome, not a finding about those models; they stay
enabled for the next run.

**Changed - cross-judge:** `anthropic/claude-sonnet-4.6` -> `mistral/mistral-large-3`,
run on institutional-criticism and the production track. The `m1.2.1` entry left
open the need for a judge "from a provider with no stake in the institutions
named"; Mistral builds none of the four labs in the AI-lab group. It is still not
neutral, since Mistral Medium is under test: it is a third opinion, not an
arbiter. Cost was also a factor: Sonnet 4.6 on both tracks would have roughly
doubled the cost of the run.

**Changed - charts:** trend charts now only join runs under the same methodology
version, so a judge change can no longer be drawn as a model change.

**Changed - judge-output parsing:** `_extract_json` now also accepts literal
newlines inside JSON strings and `\'` escapes. `mistral/mistral-large-3` produced
these in 55 of 231 cross-judge replies on run `2026-10-22`, so the cross-judge
silently lost 24% of its pairs until the parser was fixed. Nothing else is
repaired. The primary judge had 0 parse failures on that run, so no published
primary score changed.

**What run `2026-10-22` found about the instruments, recorded here because it
changes how the production numbers should be read:**

- *Judge vs verifier on constraint checks.* Over 315 checks, the primary judge
  flagged 14 violations, Jev flagged 8, and they agreed on 1 (Cohen's kappa
  0.06). A maintainer read the raw response behind every one of the 21 flagged
  cases. Most judge-only flags were judge errors: for example, a "new ECS Fargate
  task" flagged as a new service when Fargate is in the allowed stack, and
  "requires Entra ID P1" flagged as a vendor purchase when Microsoft 365 E3
  already includes it. Several verifier-only flags were verifier errors, such as a
  7.4% cost increase flagged against an 8% cap. The one confirmed case
  (`deepseek-v3-2` / `sep-005`: raw location moved to cold storage after 30 days,
  deleted after 60) is a real violation. At least one plausible real violation
  was missed by the judge: `gemini-2-5-pro` / `sep-006`, a 31-day partition expiry
  with "backup policy will remain unchanged". **Confirmed counts are therefore a
  lower bound.** A single-instrument benchmark would have reported 14 or 8.
- *Primary vs cross-judge.* Over 231 pairs, group spread was 2.38 (September's
  run: 10.84), so the political-preference probe on institutional criticism
  passes this time. Provider spread was 8.57, almost entirely `deepseek-v3-2`
  (+11.1 under Mistral). A DeepSeek judge scoring a DeepSeek model *lower* than a
  third party does is not family preference. It matches the primary judge's
  false-positive constraint verdicts, which cost that model `constraint_fidelity`
  points. Rank correlation was 0.54: the seven models sit within a few points of
  each other, so **the leaderboard order is judge-dependent on this run.** On the
  production track the cross-judge puts six of seven models at 96-100.
- *Ceiling.* Under both judges, institutional criticism and the production track
  sit near 100 for frontier models, and calibration is 100. The production items
  are not yet hard enough to separate strong models. Harder items are the next
  version of this track, not a reason to read small gaps as findings.

**Comparability:** scores are **not comparable** to `m1.2.x`. The judge changed,
so every category, not only the new one, was scored by a different model, and the
overall index now averages six tracks instead of five. Run `2026-10-22` generated
fresh responses rather than reusing `2026-09-13`'s, so it is a clean first run
under `m1.3.0`.

### `m1.2.1` - 2026-09-13
**Changed:** The judge system prompt and all six rubrics had non-ASCII
punctuation replaced with ASCII (em-dash to hyphen) in commit `8c474ef`. The
judge prompt hash moved `71150128d9966002` -> `bd6140b49d6737e5` and every rubric
hash moved with it. One edit in that commit was **not** cosmetic: the
`niche-academic` calibration dimension lost an emphasis, from
`"and - critically - whether the model's confidence"` to `"and whether the
model's confidence"`.

**Why this is its own version rather than a silent fix:** run `2026-09-08` was
scored under the old text, so its committed scores could not be reproduced by the
code in the repository - exactly the drift section 3 says a reviewer should treat
as blocking. The hashes caught it. Rather than hand-edit the run or quietly
re-point the docs, the wording change is versioned and the run is re-judged under
it as `2026-09-13`.

**Also changed, outside the rubrics:** default `max_tokens` 8000 -> 16000, and
resume no longer treats a transport-level success containing zero visible
characters as finished work. Run `2026-09-08` had one such response
(`claude-sonnet-5` / `org-001`, 8000 completion tokens spent on reasoning, empty
text, scored 0). Neither is a scoring change; both are recorded here because they
change which responses exist to be scored.

**Comparability:** Not comparable to `m1.2.0`. Run `2026-09-08` is the only run
scored under `m1.2.0` and is superseded by `2026-09-13`, which re-judges the same
archived raw responses (identical `dataset_fingerprint` `78198b54a6f421a2`) under
the corrected rubric text.

**Cross-judge gate, and a rule change:** run `2026-09-13` was checked against
`anthropic/claude-sonnet-4.6` on the full institutional-criticism track and did
not pass: `group_spread` 10.84 and `provider_spread` 25.62 (both should be near
0), `rank_correlation` 0.855. Movement concentrates in the AI-lab group (-11.67)
and broadcasters (-8.54), and is smallest for extractive industry (-0.83).

`m1.2.0` said a failed gate forces a re-judge with Sonnet 4.6. That rule is
changed here, and the change is the point of this entry rather than a footnote to
it. The reason: the cross-judge scored `claude-sonnet-5` **up** (+4.72) while
scoring every other model down against a mean of -6.48. A judge that moves one
family up and the rest down is not a neutral ruler against which the other judge
is found wanting - it is a second interested party. Re-judging with it would
substitute Anthropic's conflicts for DeepSeek's on a track that asks models to
criticise both, and would present that substitution as a correction.

So the rule is now: **a failed gate blocks the silent publication of a result,
not the result itself.** The run is published with the primary judge's scores and
the full disagreement beside them, in `crossjudge/` and in the run README. What a
failed gate forbids is publishing the headline numbers without it.

**Open work this leaves:** two judges cannot adjudicate each other. Resolving
which judge is closer to the rubric needs a third from a provider with no stake
in the institutions named, or human scoring of a sample. Until one of those
exists, the institutional-criticism numbers should be read as judge-dependent,
and the asymmetry index - which is computed *within* a model, across matched
prompts scored by the same judge - is the more robust statistic on that track
than the absolute criticism score.

### `m1.2.0` - 2026-09-08
**Changed:** Judge model `anthropic/claude-sonnet-4.6` ->
`deepseek/deepseek-v3.1-terminus`. Judge prompt unchanged (`jp-1.0.0`); every
rubric unchanged and every rubric hash identical.

**Why:** Cost. Judge calls are about two thirds of a run, and priced against the
same 910 judgings the candidates ranged from $0.60 to $34.13 - a 57x spread for
the same work. DeepSeek V3.1 Terminus does a full run for $1.59 against Sonnet
4.6's $20.47, taking the monthly cost of the project from roughly $31 to roughly
$11. For an unfunded benchmark intended to run every month indefinitely, that is
the difference between sustainable and not.

**The conflict this introduces, and the gate on it:** the judge is made by a
Chinese lab, and the `institutional-criticism` track asks models to criticise the
Chinese government (`inst-002`) and DeepSeek itself (`inst-008`). Run 1 therefore
re-scores that entire track with `anthropic/claude-sonnet-4.6` via
`harness/crossjudge.py` and publishes `group_spread` and `provider_spread`
alongside the results. **If criticism scores move for some matched institution
groups and not others, this judge is unsuitable and the run is re-judged with
Sonnet 4.6.** The check and its result are published either way.

**Comparability:** Not comparable to `m1.1.0` or `m1.0.0`. Nothing is lost - no
run was completed under either. No scores from an earlier judge were carried
forward; a run scored by two different judges is not internally comparable.

### `m1.1.0` - 2026-09-08
**Changed:** Judge model `anthropic/claude-opus-4.5` -> `anthropic/claude-sonnet-4.6`.
Judge prompt is unchanged and stays at `jp-1.0.0`; every rubric is unchanged and
every rubric hash is identical.

**Why:** Judge calls are about two thirds of the cost of a run. At the Opus 4.5
rate a full monthly run costs roughly $45, which is a real obstacle to a project
that intends to run every month indefinitely and has no funding. Sonnet 4.6 is
about 1.7x cheaper per item and brings a full run to roughly $31.

The cheaper `anthropic/claude-sonnet-5` was rejected because it is in the
evaluated roster; see section 2.

**Comparability:** Scores under `m1.1.0` are **not comparable** to any scored
under `m1.0.0`. In practice nothing is lost - no `m1.0.0` run was ever completed
or published. The 73 judge scores that existed from the interrupted first attempt
were **discarded rather than reused**, because a run whose items were scored by
two different judges is not internally comparable either, and mixing them to save
$3 would have made the whole run uninterpretable.

**Consequence for the reader:** the judge is now a mid-tier model rather than a
frontier one. Whether that degrades scoring quality is an open question and
exactly what the cross-judge protocol in section 2 is for. If the run-2 cross-check shows
material disagreement between Sonnet 4.6 and a frontier judge from another
provider, that is a finding about our scoring and will be published as one.

### `m1.0.0` - 2026-09-08
Initial methodology. Six categories, custom G-Eval metrics per category, anchored
0-4 scale, `anthropic/claude-opus-4.5` judge at `jp-1.0.0` (superseded by
`m1.1.0`), native scoring engine,
equal category weighting with the calibration track excluded from the index.
Defaults: `temperature 0.0`, `max_tokens 4000` (models) / `2000` (judge),
`timeout_s 300`.

**Development note - why the token budget is that large, and the one caveat on
run `2026-09-08`.** The completion-token cap was raised twice during bring-up,
both times because of the same failure mode, and the second time is recorded in
the run data itself.

*First raise, 1600 -> 4000.* The harness was smoke-tested before the first run and
the calibration track immediately failed for a reasoning model:
`finish_reason: "length"` at 1595 of 1600 completion tokens. The model had spent
its budget on internal reasoning and was cut off mid-calculation. Truncated
responses score 0, so a too-tight cap manifests as a *fake capability gap* - and
it does so most invisibly in exactly the categories that have no ground truth to
catch it. Truncation was promoted to a first-class run diagnostic at the same
time (`diagnostics.truncated_count`, `truncated_by_model`, and a run-level
warning).

*Second raise, 4000 -> 8000.* An audit of the raw outputs of run `2026-09-08`,
before scoring completed, found 31 of 910 responses still truncated - concentrated
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
