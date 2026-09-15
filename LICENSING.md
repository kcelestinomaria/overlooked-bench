# Licensing

overlooked-bench is licensed in three parts, because it contains three different
kinds of thing and they warrant different terms.

| Path | Licence | |
|---|---|---|
| `harness/`, `charts/`, `site/`, `obench.py`, `run.sh`, `run.ps1`, `.github/` | **AGPL-3.0-or-later** | [LICENSE](LICENSE) |
| `data/categories/` - the benchmark items | **CC BY-SA 4.0** | [creativecommons.org/licenses/by-sa/4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `data/runs/` - results, charts, social cards - and `docs/` | **CC BY 4.0** | [creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/) |

Copyright (c) 2026 overlooked-bench contributors.

Attribution for the dataset and results: **"overlooked-bench"**, with a link to
this repository and, where you are quoting numbers, the run id.

---

## Why these three

### The harness is AGPL-3.0

This project's entire claim is that a score cannot change without the change
being visible. Rubric hashes are written into every scored record so that an
edited rubric shows up in the run diff whether or not anyone remembered to
write a changelog entry.

The AGPL says the same thing in licence form. Its network clause means that
running a **modified** version of this harness as a public service obliges you
to publish your modifications. A hosted leaderboard built on altered rubrics
therefore owes its users the diff, which is exactly what this repository owes
its own readers.

Two things this does **not** do, which are commonly assumed:

- **Running the benchmark does not trigger it.** Internal use, including inside
  a company, including on your own unreleased models, is not distribution and
  carries no obligation. Evaluate whatever you like, privately, and publish
  nothing.
- **It does not reach your model.** The AGPL covers this harness. Scoring a
  model with it does not place any obligation on the model, its weights, or its
  training data.

The obligation attaches when you distribute a modified harness, or offer one to
third parties over a network.

### The items are CC BY-SA 4.0

The dataset is the hard part of this project and the most contestable. Item
selection is where a benchmark encodes its judgement about what is worth
measuring, and the point of publishing it is that the judgement can be argued
with.

Share-alike keeps that argument possible. A derived item set - items rewritten,
dropped, added, re-scoped to another region or another set of institutions -
stays under the same terms, so it remains readable and criticisable rather than
disappearing into a product. You may use it commercially. You may not make a
closed derivative of it.

This is stricter than the CC BY the items previously carried. Contributions
made before this change were accepted under CC BY, which permits this
relicensing of the collection; individual contributors retain their own rights
in what they wrote.

### The results are CC BY 4.0

Deliberately the most permissive of the three, and not an oversight.

Scores, deltas and aggregate statistics are substantially **facts about
measurements**, and facts attract thin copyright protection at best. Asserting
strong terms over them would be partly unenforceable and wholly
counterproductive: results exist to be quoted in papers, in journalism, and by
the labs being measured. Attribution is the only thing asked, and the only
thing that matters, because a number quoted without its run id and methodology
version is not checkable.

### Model responses in `data/runs/*/raw/`

These were produced by third-party AI models. They are published as the
evidence for the scores in this repository - the scoring phase reads them back
off disk, so anyone can verify that what was judged is what was archived.

Their copyright status is unsettled, and no claim over them is made here. The
CC BY 4.0 grant above covers this project's selection, arrangement and
presentation of them, not the underlying responses.

---

## The name

The code and the data are free to reuse under the licences above. **The name is
not part of that grant.**

Fork it, modify the rubrics, change the item set, run it on your own roster -
all fine, and the licences are written to make it easy. But publishing results
as "overlooked-bench" numbers when they were not produced by this methodology
makes the published record less trustworthy for everyone, which is the one
thing this project cannot absorb.

If you publish results from a modified version, say plainly that it is
modified, and carry the `methodology_version` and the rubric hashes your run
actually used. Every run artefact in this repository already contains both.

---

## Contamination

No licence prevents a benchmark from being trained on, and this one does not
pretend to. If these items end up in a training corpus the benchmark stops
measuring anything, and that is a technical problem with technical mitigations,
not a legal one.

If you operate a crawler or assemble training data, please exclude
`data/categories/`.

---

## SPDX

Source files carry SPDX identifiers, so licence status is machine-readable and
survives being copied out of the repository:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
```

## Contributing

By submitting a contribution you agree to license it under the licence
governing the path you are contributing to, as set out above. See
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

## Not legal advice

This file explains the maintainers' intent in plain language. Where it and the
licence texts disagree, the licence texts govern.
