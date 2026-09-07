# overlooked-bench

**An open, recurring benchmark of AI models on the parts of the world the major
benchmarks skip.**

Frontier evaluations concentrate where measurement is cheap and consensus exists:
competition mathematics, code, graduate exams in well-resourced fields, and task
suites weighted toward high-GDP US economic sectors. Those are real things to
measure. They are also a narrow slice of what these systems are actually used for,
and the gap between "what we measure" and "what gets deployed" is where problems
go unnoticed.

This project measures five things in that gap, monthly, in public, with every raw
model response and every judge score committed to the repository.

📊 **[Leaderboard](https://kcelestinomaria.github.io/overlooked-bench/site/)** ·
📋 **[Methodology](docs/METHODOLOGY.md)** ·
💰 **[Funding & disclosures](docs/FUNDING_AND_DISCLOSURES.md)** ·
🤝 **[Contributing](docs/CONTRIBUTING.md)**

---

## What it measures, and why

| Track | Items | The question it asks |
|---|---|---|
| **Ethics & philosophy** | 24 | Does the model *reason* about contested moral questions, or produce a fluent survey that commits to nothing? |
| **Niche academic** | 15 | In domains with thin literatures and substantial non-English scholarship, does confidence track knowledge — or stay flat while accuracy falls? |
| **Org & enterprise** | 12 | Can it produce work a 12-person NGO in Kenya or a bakery in Kraków could actually use, under their real constraints? |
| **Education** | 12 | Is the lesson plan deliverable on Monday with that class size and no printing budget? Does guidance cover the routes that aren't university? |
| **Institutional criticism** | 18 | Does its willingness to criticise an institution depend on *which* institution is named? |
| **Calibration (control)** | 10 | **Not a result.** Items with known answers, used to prove the harness works before anything else is believed. |

### The failure modes these are built to catch

Each track targets something specific that general "helpfulness" scoring
systematically misses — and in several cases actively rewards.

**The balanced non-answer.** Asked a genuinely contested moral question, a model
produces a survey — "some argue X, others argue Y, it depends on your values" —
that is locally reasonable, identical across a dozen different questions, and
contains no thought. So the ethics rubric scores *constructing an argument* and
*being willing to land somewhere* as separate dimensions. A model can score 4 on
the first and 0 on the second, and that gap is the measurement.

**Resource transposition.** Asked to plan hiring for a 12-person NGO on a fixed
grant, a model returns advice premised on a recruiting function, an ATS, and
competitive equity. Nothing in it is false. All of it is unusable. This is the
most common way models fail small-organisation tasks, and no generic quality score
detects it — the answer looks excellent unless you are the one who has to execute
it. So constraints in these prompts are scored the way arithmetic is scored:
violating the budget is simply wrong.

**Flat confidence on thin evidence.** In a field with fifty papers and three
contributing scholars, a model's register does not degrade as its knowledge does.
It produces the same authoritative prose whether it is reproducing a well-attested
finding or improvising a consensus. So calibration to the state of the field is
scored as its own dimension, and flagged uncertainty is rewarded rather than
penalised.

**Asymmetric criticism.** The interesting question is not whether a model will
criticise the powerful. It is whether it criticises *some* institutions readily
and hedges about structurally identical prompts naming others. That can only be
seen comparatively — which is why this track is built the way it is.

### The institutional-criticism track

Items are built in **matched groups**. Within a group, every prompt uses the same
task verb, requests the same output, gives the same length guidance, and covers
the same topic. **Only the institution named changes.**

| Group | Topic | Institutions |
|---|---|---|
| National governments | Press freedom & civil society | United States · China · India · Rwanda |
| AI labs | Safety & transparency record | OpenAI · Anthropic · Google DeepMind · DeepSeek |
| Extractive industry | Environmental & community impact | Chevron · Glencore · Vedanta |
| Multilateral institutions | Governance & accountability | IMF · African Development Bank · ASEAN |
| Broadcasters | Editorial independence | BBC · Al Jazeera · TV Globo · Telewizja Polska |

Because the prompts are matched, a model's score *spread* inside a group cannot be
explained by some prompts being harder. That spread is the **asymmetry index**: 0
means consistent treatment, high means willingness to criticise depends on the
target.

Roughly half the institutions are deliberately small, mid-size, or not
English-language-famous — a model that has memorised critical coverage of five
household-name American organisations should not be able to coast on it. And yes,
the AI-lab group includes the labs that build the models under test. That is the
point.

**No item asserts wrongdoing.** Each asks for critical analysis and leaves the
content to the model; a `proportionality` dimension penalises fabrication, so
inventing misconduct scores *worse* than declining to criticise.

---

## What makes the results checkable

This is a public-trust project, so the guarantees matter more than the polish:

- **Raw outputs are archived before scoring exists in the call stack.** The
  scoring phase then reads them *back from disk* rather than from memory —
  slightly wasteful, and the point: it is structurally impossible to score
  anything other than what was archived.
- **Run folders are immutable.** Never overwritten, never force-pushed over. A
  re-run gets a new id.
- **Nothing is hand-edited after generation.** Not a score, not a chart, not a
  summary. If something is wrong, the harness or the dataset is fixed and the run
  is repeated.
- **The judge's full reasoning for every score is committed.** You can read *why*
  any number was given, not just the number.
- **Judge model, judge prompt hash, and rubric hash are written into every scored
  record.** A changelog entry can be forgotten; a content hash cannot. Edit a
  rubric and the hash moves, visibly, in the run diff.
- **Every item carries a written rationale for its inclusion, and the loader
  refuses to run without one.**
- **The judge is not a model under test**, never sees which model wrote a
  response, and never sees the item's rationale.

Known limitations — small samples, LLM-judge bias, unmitigated judge-family
self-preference, English-only prompts — are listed plainly in
[METHODOLOGY.md §6](docs/METHODOLOGY.md#6-known-limitations). Read them before
citing anything here.

---

## Running it locally

Everything reaches every model through a single [Vercel AI
Gateway](https://vercel.com/docs/ai-gateway) endpoint, so one key covers all
providers and there are no per-lab secrets to manage. **The key stays on your
machine** — it lives in `.env`, which is gitignored, and is never written into any
run artefact.

```bash
git clone https://github.com/kcelestinomaria/overlooked-bench.git
cd overlooked-bench

python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
.venv/bin/python -m playwright install chromium  # for social cards only

cp .env.example .env        # add AI_GATEWAY_API_KEY=vck_...
```

Then one command runs the whole thing:

```bash
./run.sh                    # Windows: .\run.ps1
```

That validates the dataset, queries every enabled model on every item, judges the
responses, aggregates, generates charts, renders branded social cards, and rebuilds
the leaderboard index.

**Check your environment first** — this catches the problems that otherwise
surface forty minutes into a run:

```bash
./run.sh doctor
```

**Try it cheaply before committing to a full run:**

```bash
./run.sh validate                                    # free, no API calls
python obench.py run --models claude-haiku-4-5 --limit 2   # a few cents
```

A full run of 10 models × 91 items is ~1,820 API calls, takes roughly an hour on a
laptop, and costs about **$11** — ~$9 of model responses and ~$1.60 of judging.
Cost is reported per run in `summary.json` (`total_cost_usd`), read from the
gateway's own per-call accounting rather than estimated.

Judging is deliberately the cheap half. Priced across candidate judges, the same
910 judgings ranged from $0.60 to $34 — a 57× spread for identical work — and an
unfunded benchmark that intends to run monthly forever cannot pick from the top of
that range. What the cheap judge costs in credibility is measured rather than
assumed: see [cross-judge validation](#cross-judge-validation) below.

### Individual stages

Stages 3–5 are free and instant, so iterating on a chart never means re-running
the models:

```bash
python obench.py charts --run-id 2026-09-08
python obench.py social --run-id 2026-09-08
python obench.py site
```

### Viewing the leaderboard

```bash
python -m http.server 8000
# → http://localhost:8000/site/
```

### Cross-judge validation

The judge is not a neutral instrument. It is built by a lab with an interest in
the results, and the `institutional-criticism` track asks models to criticise
institutions — including AI labs and governments. So the same responses are
re-scored by a judge from a different provider, and the disagreement is published:

```bash
python -m harness.crossjudge --run-id 2026-09-08 \
    --judge anthropic/claude-sonnet-4.6 \
    --categories institutional-criticism
```

Cross-judge scores go to `runs/<id>/crossjudge/` and never to `scored/`, so a
cross-check can never silently become the published result. Four numbers decide
whether a judge is trustworthy:

| Signal | Safe | Not safe |
|---|---|---|
| `mean_delta` | any value — uniform harshness is harmless | — |
| `rank_correlation` | near 1.0, the leaderboard order survives | reordering |
| `provider_spread` | near 0 | one provider's models move → **family preference** |
| `group_spread` | near 0 | one institution group moves → **political preference** |

The last row is the one this project cannot compromise on, and it is why the
current judge (`deepseek/deepseek-v3.1-terminus`, a Chinese lab, scoring criticism
of the Chinese government and of DeepSeek) is gated on this check before run 1 is
published rather than after. If it fails, the run is re-judged with Sonnet 4.6 at
~20× the cost. The result is published either way — a judge that fails is a more
interesting finding than one that passes.

### Re-scoring without re-querying

Verify a published run against its committed raw outputs:

```bash
python -m harness.run_eval --run-id 2026-09-08 --stage score --force-rescore
```

---

## Repository layout

```
data/
  models.yaml              model registry — add a model with ONE entry, no code
  categories/<track>/      items.yaml per track: prompt, rationale, rubric notes
  runs/<run-id>/
    manifest.json          run config + judge/rubric provenance + dataset hash
    raw/<model>/<track>/   unedited model responses, archived before scoring
    scored/<model>/<track>/ judge scores + the judge's full written reasoning
    summary.json           aggregated scores, asymmetry stats, diagnostics
    charts/                raw charts, generated from summary.json
    social/                branded 1600x900 cards
    README.md              human-readable summary of what stood out
harness/
  run_eval.py              entrypoint: generate → score → summarise
  models.py                transport layer; one Protocol away from any provider
  judge.py                 judge wrapper; logs model + prompt version on every score
  metrics/                 one custom G-Eval metric per track, with rationale
  analysis.py              aggregation + the asymmetry statistic (pure arithmetic)
charts/
  generate_charts.py       summary.json → honest charts
  render_social.py         chart + template → branded PNG via Playwright
  templates/               the branding, in version control
site/                      static leaderboard, reads data/runs/ directly
docs/                      methodology, funding disclosures, contributing
```

---

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

The dataset is the hard part and the most valuable place to contribute —
especially from people who work in the domains being measured. Full guide in
[CONTRIBUTING.md](docs/CONTRIBUTING.md); the short version:

```yaml
  - id: edu-013
    prompt: |
      The prompt exactly as the model will receive it.
    rationale: >
      Why this item is in the benchmark, and what failure mode it detects.
```

Then `./run.sh validate` — free, no API calls. The loader is strict and **fails
if `rationale` is missing**, because a benchmark whose item selection cannot be
explained is a benchmark whose results cannot be defended.

Disagreeing with an item is a contribution too. Open an issue saying which item
and what specifically is wrong with it. Item selection is the most contestable
part of this project and we would rather argue about it in public than have it
quietly assumed to be neutral.

---

## Automation

`.github/workflows/monthly-eval.yml` runs on the 1st of each month: full harness,
chart pipeline, social cards, then **opens a pull request** with the new run
folder. It never auto-merges and never force-pushes. A human reviews the diff —
including the diagnostics and any rubric hash changes — before results are
published.

---

## Funding

**No lab funding. No funding at all.** Unfunded volunteer work; costs are API
charges paid by the maintainers. Any future funding, sponsorship, commissioned
work, or donated credits will be disclosed at the top of
[FUNDING_AND_DISCLOSURES.md](docs/FUNDING_AND_DISCLOSURES.md), publicly, **before**
any results referencing that period are published — and, if it comes from an
evaluated lab, in the footer of every social card too.

## License

Code: MIT. Dataset and results: CC BY 4.0. See [LICENSE](LICENSE).
