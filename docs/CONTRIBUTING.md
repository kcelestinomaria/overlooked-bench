# Contributing

The most valuable contribution to this project is **a good eval item**. The
harness is ordinary software; the dataset is the hard part, and it is where
outside expertise beats ours.

Contributions from people who work in the domains being measured - teachers,
nonprofit staff, small-business operators, area-studies scholars, practitioners
outside the US - are especially wanted, because those are the perspectives that
mainstream benchmarks are missing and we cannot manufacture internally.

---

## Adding an eval item

1. Open `data/categories/<category>/items.yaml`.
2. Append an item. Required fields:

```yaml
  - id: edu-013            # unique, stable, never reused. Prefix by category.
    prompt: |
      The prompt exactly as the model will receive it.
    rationale: >
      One or two lines: why this item is in the benchmark, and what failure
      mode it is designed to detect.
```

3. Optional fields, by situation:

| Field | Use when |
|---|---|
| `tags` | Always helpful. A list of short slugs. |
| `rubric_notes` | The judge needs item-specific guidance - what a competent answer must contain, and what to penalise. Strongly recommended for `org-enterprise` and `education`. |
| `reference` | **Required** for `calibration-general`. The known-correct answer. |
| `contested` | `ethics-philosophy` only. `true` means no consensus answer exists; the judge is then told not to reward agreement with the mainstream position. |
| `group`, `institution`, `attributes` | **Required** for `institutional-criticism`. See below. |

4. Validate before opening a PR - this makes no API calls and costs nothing:

```bash
python -m harness.run_eval --dry-run
```

The loader is strict and will refuse to run on a malformed item. In particular
**it fails if `rationale` is missing.** A benchmark whose item
selection cannot be explained is a benchmark whose results cannot be defended, and
the cheapest way to guarantee the explanation exists is to make the code require
it.

---

## What makes a good item

**Good:**

- It has a **specific failure mode in mind.** You can say in one sentence what a
  bad answer looks like and why a model would produce it.
- A **competent practitioner in the field could grade it** and would agree with
  the rubric.
- It **cannot be answered from a memorised summary.** If the answer is the first
  paragraph of a well-known reference article, it is not testing anything.
- Constraints are **checkable**. "Within a PLN 250,000 budget" is checkable.
  "Cost-effectively" is not.
- It reflects a **real situation someone is actually in**, not a puzzle.

**Not good:**

- Trick questions and gotchas. We are measuring competence, not alertness.
- Items whose "correct" answer is a political position. The rubrics score the
  quality of reasoning, never its conclusion, and an item that only scores well
  for one conclusion is broken.
- Items that need external context the model was not given.
- Anything requiring information that changes week to week.
- Near-duplicates of an existing item. Check the category first.

---

## Adding to `institutional-criticism`

This track has the strictest requirements, because its statistic depends entirely
on the items being properly matched.

**Items must be added in matched sets, never singly.**

A `group` is a set of prompts that are identical in task verb, requested output,
length guidance and topic, and differ *only* in the institution named. That
matching is what licenses the asymmetry statistic: it is the reason a score spread
inside a group can be attributed to the institution rather than to the prompts
being differently hard. A single new item added to an existing group changes what
that group's spread means, so a PR adding one item to `g3-extractive` will be
asked to justify it or to propose a new group instead.

Required fields:

```yaml
  - id: inst-019
    group: g6-university          # matched set this item belongs to
    institution: Name of institution
    prompt: |
      ... identical in structure to every other prompt in the group ...
    rationale: >
      Why THIS institution, in THIS group. Address coverage and alignment
      explicitly.
    attributes:
      region: europe              # north-america | south-america | europe |
                                  # africa | middle-east | south-asia |
                                  # east-asia | southeast-asia | oceania | global
      size: medium                # large | medium | small
      sector: education           # free text, consistent within a group
      us_aligned: "yes"           # "yes" | "no" | partial
      coverage: low               # high | medium | low - Anglophone media salience
```

A new group must span regions and alignments, and must not consist only of
large, high-coverage, English-language-famous institutions. A group of four
American companies measures nothing this project is interested in.

**No item may assert that an institution has done anything wrong.** Ask for
critical analysis; leave the content to the model. The `proportionality` dimension
penalises fabrication, so an item that presupposes misconduct corrupts its own
scoring.

---

## Changing a rubric

Rubrics live in `harness/metrics/<category>.py`.

**Any change to rubric wording is a methodology change.** It invalidates
comparisons with previous runs. Before opening such a PR:

1. Bump the metric's `version`.
2. Bump `METHODOLOGY_VERSION` in `harness/__init__.py`.
3. Add a changelog entry to `docs/METHODOLOGY.md` saying what changed, why, and
   what it means for comparability with earlier runs.
4. Explain in the PR description what the change does to existing scores.

The rubric hash written into every scored record will change automatically, so
the edit is visible in the run diff whether or not you remember step 3. Reviewers
should treat an unexplained rubric hash change as blocking.

Dimension weights must sum to 1.0. The loader raises on import if they do not.

---

## Adding a model

One entry in `data/models.yaml`. No code change:

```yaml
  - key: some-model-v2       # stable slug, NEVER reused for a different model
    provider: somelab
    model_id: somelab/some-model-v2
    display: Some Model v2
    tier: mid                # frontier | mid | small
    api_key_env: AI_GATEWAY_API_KEY
    judge: false
    enabled: true
    notes: Why this model is worth including.
```

`key` is used in filenames and chart labels and historical runs are keyed on it.
Reusing a key for a different underlying model would silently corrupt the time
series, so treat it as permanent.

If a model is not available on the gateway, implement the `Transport` protocol in
`harness/models.py` and register it in `TRANSPORTS`. Call sites do not change.

---

## Running locally

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip
python -m playwright install chromium              # only needed for social cards
cp .env.example .env                               # add AI_GATEWAY_API_KEY
```

Useful invocations while developing:

```bash
# Validate everything, no API calls, no cost
python -m harness.run_eval --dry-run

# Cheap smoke test before a full run
python -m harness.run_eval --run-id smoke --models claude-haiku-4-5 --limit 2

# Re-score existing raw outputs without re-querying models
python -m harness.run_eval --run-id 2026-09-08 --stage score --force-rescore
```

**Never commit a `.env` file.** It is gitignored; keep it that way.

---

## Things that will get a PR rejected

- Editing any file under `data/runs/`. Published runs are immutable. If a run is
  wrong, fix the harness and produce a new run.
- Hand-editing a chart, a summary, or a social card.
- Changing a rubric without a methodology version bump and changelog entry.
- Reusing an existing item `id` or model `key` for different content.
- Adding a single item to an existing `institutional-criticism` group without
  justifying what it does to that group's matching.
- Anything that makes a run depend on state outside the repository.

---

## Disagreeing with an item

Open an issue rather than a PR. Say which item, and what specifically is wrong
with it - the framing, the constraints, the rubric notes, the factual premises.
Item selection is the most contestable part of this project and we would rather
argue about it in public than have it quietly assumed to be neutral.

---

## Licensing your contribution

By opening a pull request you agree that your contribution is licensed under the
licence covering the path you are changing:

| You are changing | Your contribution is licensed under |
|---|---|
| `harness/`, `charts/`, `site/`, `obench.py`, run scripts, workflows | AGPL-3.0-or-later |
| `data/categories/` - benchmark items | CC BY-SA 4.0 |
| `docs/` | CC BY 4.0 |

You keep the copyright in what you wrote. This grant is what lets the project
distribute it, and it is stated here because a benchmark that cannot say what
its items are licensed under cannot be relied on by anyone downstream.

Two specific asks:

- **Do not paste text you do not have the right to license.** Items lifted from
  a textbook, an exam paper, a company's internal documents, or another
  benchmark's dataset cannot be accepted, however good they are. Write the
  prompt yourself.
- **Say so if an item comes from your professional context.** An item drawn from
  real work at a named organisation is often the most valuable kind, and also
  the kind most likely to carry obligations you have not thought about.
  Paraphrase, remove identifying detail, and note in the PR that you have done
  so.

Full detail, including why the three parts differ, is in
[LICENSING.md](../LICENSING.md).
