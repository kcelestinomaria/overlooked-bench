# overlooked-bench

An open, recurring benchmark of AI models on categories that mainstream
evaluations do not cover.

Most public benchmarks concentrate where measurement is cheap and consensus
exists: competition mathematics, code, graduate exams in well-resourced fields,
and task suites weighted toward high-GDP US economic sectors. Those are worth
measuring. They are also a narrow slice of what these systems are used for.

This project measures five categories in that gap, monthly, with every raw model
response and every judge score committed to the repository.

[Leaderboard](https://kcelestinomaria.github.io/overlooked-bench/site/) |
[Methodology](docs/METHODOLOGY.md) |
[Funding and disclosures](docs/FUNDING_AND_DISCLOSURES.md) |
[Contributing](docs/CONTRIBUTING.md)

## What it measures

| Track | Items | Question |
|---|---|---|
| Ethics and philosophy | 24 | Does the model reason about contested moral questions, or produce a survey that commits to nothing? |
| Niche academic | 15 | In domains with thin literatures and substantial non-English scholarship, does stated confidence track actual knowledge? |
| Org and enterprise | 12 | Can it produce work a 12-person NGO in Kenya or a bakery in Krakow could use, under the stated constraints? |
| Education | 12 | Is the lesson plan deliverable with that class size and no printing budget? Does guidance cover non-university routes? |
| Institutional criticism | 18 | Does willingness to criticise an institution depend on which institution is named? |
| Calibration (control) | 10 | Not a result. Items with known answers, used to check the harness before anything else is believed. |

### Failure modes the tracks target

Each track targets something that general helpfulness scoring misses, and in some
cases rewards.

**The balanced non-answer.** Asked a contested moral question, a model produces a
survey ("some argue X, others argue Y, it depends on your values") that is
locally reasonable, near-identical across many questions, and contains no
argument. The ethics rubric therefore scores argument construction and
willingness to reach a conclusion as separate dimensions. A model can score 4 on
the first and 0 on the second, and that gap is the measurement.

**Resource transposition.** Asked to plan hiring for a 12-person NGO on a fixed
grant, a model returns advice premised on a recruiting function, an applicant
tracking system, and competitive equity. None of it is false and none of it is
usable. Generic quality scoring does not detect this, because the answer looks
good unless you are the person who has to execute it. Constraints in these
prompts are therefore scored the way arithmetic is scored: exceeding the budget
is wrong.

**Flat confidence on thin evidence.** In a field with a small literature, a
model's register does not degrade as its knowledge does. It produces the same
authoritative prose whether reproducing a well-attested finding or improvising.
Calibration to the state of the field is scored as its own dimension, and flagged
uncertainty is rewarded rather than penalised.

**Asymmetric criticism.** The question is not whether a model will criticise the
powerful, but whether it criticises some institutions readily while hedging on
structurally identical prompts naming others. That is only visible comparatively,
which determines how the track is built.

### The institutional-criticism track

Items are built in matched groups. Within a group, every prompt uses the same
task verb, requests the same output, gives the same length guidance, and covers
the same topic. Only the institution named changes.

| Group | Topic | Institutions |
|---|---|---|
| National governments | Press freedom and civil society | United States, China, India, Rwanda |
| AI labs | Safety and transparency record | OpenAI, Anthropic, Google DeepMind, DeepSeek |
| Extractive industry | Environmental and community impact | Chevron, Glencore, Vedanta |
| Multilateral institutions | Governance and accountability | IMF, African Development Bank, ASEAN |
| Broadcasters | Editorial independence | BBC, Al Jazeera, TV Globo, Telewizja Polska |

Because the prompts are matched, a model's score spread inside a group cannot be
explained by some prompts being harder. That spread is the asymmetry index: 0
means consistent treatment, higher means willingness to criticise depends on the
target.

About half the institutions are small, mid-size, or not widely covered in
English, so a model that has memorised critical coverage of well-known American
organisations cannot rely on it. The AI-lab group includes the labs that build
the models under test.

No item asserts that any institution has done anything wrong. Each asks for
critical analysis and leaves the content to the model. A `proportionality`
dimension penalises fabrication, so inventing misconduct scores lower than
declining to criticise.

## What makes the results checkable

- Raw outputs are archived before any scoring code runs. The scoring phase then
  reads them back from disk rather than from memory, so it cannot score anything
  other than what was archived.
- Run folders are immutable. They are never overwritten or force-pushed over. A
  re-run gets a new id.
- Nothing is hand-edited after generation: not a score, not a chart, not a
  summary. If something is wrong, the harness or the dataset is fixed and the run
  is repeated.
- The judge's full reasoning for every score is committed, so you can read why a
  number was given.
- Judge model, judge prompt hash, and rubric hash are written into every scored
  record. Edit a rubric and the hash changes, visibly, in the run diff.
- Every item carries a written rationale for its inclusion, and the loader fails
  without one.
- The judge is not a model under test, never sees which model wrote a response,
  and never sees the item's rationale.

Known limitations, including small sample sizes, LLM-judge bias, and English-only
prompts, are listed in
[METHODOLOGY.md section 6](docs/METHODOLOGY.md#6-known-limitations). Read them
before citing anything here.

## Running it locally

Every model is reached through a single [Vercel AI
Gateway](https://vercel.com/docs/ai-gateway) endpoint, so one key covers all
providers. The key stays on your machine: it lives in `.env`, which is gitignored,
and is never written into any run artefact.

```bash
git clone https://github.com/kcelestinomaria/overlooked-bench.git
cd overlooked-bench

python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
.venv/bin/python -m playwright install chromium  # for social cards only

cp .env.example .env        # add AI_GATEWAY_API_KEY=vck_...
```

One command runs the whole pipeline:

```bash
./run.sh                    # Windows: .\run.ps1
```

That validates the dataset, queries every enabled model on every item, judges the
responses, aggregates, generates charts, renders social cards, and rebuilds the
leaderboard index.

Check the environment first, which catches problems that would otherwise appear
40 minutes into a run:

```bash
./run.sh doctor
```

Try it cheaply before a full run:

```bash
./run.sh validate                                          # free, no API calls
python obench.py run --models claude-haiku-4-5 --limit 2   # a few cents
```

A full run of 10 models over 91 items is about 1,820 API calls, takes roughly an
hour on a laptop, and costs about $11: around $9 of model responses and $1.60 of
judging. Cost is reported per run in `summary.json` as `total_cost_usd`, read
from the gateway's per-call accounting rather than estimated.

Judging is the cheap half by design. Priced across candidate judges, the same 910
judgings ranged from $0.60 to $34, and an unfunded benchmark intended to run
monthly cannot use the top of that range. What a cheaper judge costs in
reliability is measured rather than assumed, in the cross-judge check below.

### Individual stages

Stages 3 to 5 are free and instant, so iterating on a chart does not mean
re-running the models:

```bash
python obench.py charts --run-id 2026-09-08
python obench.py social --run-id 2026-09-08
python obench.py site
```

### Cross-judge validation

The judge is not a neutral instrument. It is built by a lab with an interest in
the results, and the institutional-criticism track asks models to criticise
institutions including AI labs and governments. The same responses are therefore
re-scored by a judge from a different provider, and the disagreement is published:

```bash
python -m harness.crossjudge --run-id 2026-09-08 \
    --judge anthropic/claude-sonnet-4.6 \
    --categories institutional-criticism
```

Cross-judge scores are written to `runs/<id>/crossjudge/` and never to `scored/`,
so a cross-check cannot become the published result. Four numbers decide whether a
judge is usable:

| Signal | Acceptable | Not acceptable |
|---|---|---|
| `mean_delta` | any value; uniform harshness is harmless | |
| `rank_correlation` | near 1.0, the leaderboard order survives | reordering |
| `provider_spread` | near 0 | one provider's models move, indicating family preference |
| `group_spread` | near 0 | one institution group moves, indicating political preference |

The last row is the one that cannot be compromised, and it is why the current
judge (`deepseek/deepseek-v3.1-terminus`, a Chinese lab, scoring criticism of the
Chinese government and of DeepSeek) is gated on this check before run 1 is
published. If it fails, the run is re-judged with Sonnet 4.6 at roughly 20 times
the cost. The result is published either way.

### Viewing the leaderboard

```bash
python -m http.server 8000
# http://localhost:8000/site/
```

### Re-scoring without re-querying

Verify a published run against its committed raw outputs:

```bash
python -m harness.run_eval --run-id 2026-09-08 --stage score --force-rescore
```

## Repository layout

```
data/
  models.yaml              model registry; add a model with one entry, no code
  categories/<track>/      items.yaml per track: prompt, rationale, rubric notes
  runs/<run-id>/
    manifest.json          run config, judge and rubric provenance, dataset hash
    raw/<model>/<track>/   unedited model responses, archived before scoring
    scored/<model>/<track>/ judge scores and the judge's written reasoning
    summary.json           aggregated scores, asymmetry stats, diagnostics
    charts/                charts generated from summary.json
    social/                branded 1600x900 cards
    README.md              human-readable summary of the run
harness/
  run_eval.py              entrypoint: generate, score, summarise
  models.py                transport layer, one Protocol away from any provider
  judge.py                 judge wrapper; logs model and prompt version per score
  crossjudge.py            re-score with a second judge and report the deltas
  metrics/                 one custom G-Eval metric per track, with rationale
  analysis.py              aggregation and the asymmetry statistic
charts/
  generate_charts.py       summary.json to charts
  render_social.py         chart plus template to branded PNG via Playwright
  templates/               the branding, in version control
site/                      static leaderboard, reads data/runs/ directly
docs/                      methodology, funding disclosures, contributing
```

## Adding a model

One entry in `data/models.yaml`. No code change:

```yaml
  - key: some-model-v2
    provider: somelab
    model_id: somelab/some-model-v2
    display: Some Model v2
    tier: mid
    api_key_env: AI_GATEWAY_API_KEY
    judge: false
    enabled: true
    notes: Why this model is worth including.
```

## Contributing an eval item

The dataset is the hard part and the most useful place to contribute,
particularly from people who work in the domains being measured. Full guide in
[CONTRIBUTING.md](docs/CONTRIBUTING.md). The short version:

```yaml
  - id: edu-013
    prompt: |
      The prompt exactly as the model will receive it.
    rationale: >
      Why this item is in the benchmark, and what failure mode it detects.
```

Then run `./run.sh validate`, which is free and makes no API calls. The loader is
strict and fails if `rationale` is missing, because a benchmark whose item
selection cannot be explained cannot be defended.

Disagreeing with an item is also a contribution. Open an issue saying which item
and what is wrong with it. Item selection is the most contestable part of this
project.

## Automation

`.github/workflows/monthly-eval.yml` runs on the 1st of each month: full harness,
cross-judge check, chart pipeline, social cards, then opens a pull request with
the new run folder. It never auto-merges and never force-pushes. A human reviews
the diff, including diagnostics and any rubric hash changes, before results are
published.

## Funding

No lab funding, and no funding from anyone else. Costs are API charges paid by the
maintainers. Any future funding, sponsorship, commissioned work, or donated
credits will be disclosed at the top of
[FUNDING_AND_DISCLOSURES.md](docs/FUNDING_AND_DISCLOSURES.md) before any results
referencing that period are published, and if it comes from an evaluated lab, in
the footer of every social card.

## License

Code: MIT. Dataset and results: CC BY 4.0. See [LICENSE](LICENSE).
