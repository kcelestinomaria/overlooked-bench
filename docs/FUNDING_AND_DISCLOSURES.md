# Funding and disclosures

## Current status

**As of 2026-09-08, this project has no funding from any AI laboratory, model
provider, or company whose products it evaluates.**

It has no funding from anyone else either. It is unfunded volunteer work. Costs
are API charges only — approximately tens of US dollars per monthly run, paid
personally by the maintainers.

No lab has reviewed, previewed, commissioned, sponsored, or been consulted on the
design of this benchmark, the selection of its items, or the presentation of its
results. No model provider has been given advance access to results before
publication.

---

## The commitment

This section is the point of the document, and it is binding on the maintainers.

1. **Any funding, grant, sponsorship, commissioned work, paid consulting, equity,
   or in-kind support — including donated API credits — from any AI lab, model
   provider, or party with a material interest in the results will be disclosed
   at the top of this file, publicly, BEFORE any results referencing that period
   are published.**

2. Disclosure will name the funder, the amount or nature of the support, the date
   it began, and what it is for. Not "supported by industry partners."

3. If a lab whose models are evaluated here becomes a funder, that fact will
   additionally appear:
   - in the README, above the leaderboard link,
   - in the run README of every affected run,
   - in the footer of every social card generated for those runs.

   Someone who encounters a chart on social media with no other context should be
   able to see it.

4. **No funder gets advance access to results, review rights over the
   methodology, or any influence on item selection.** If a prospective funder
   requires any of those, the funding will be declined and the approach will be
   disclosed here anyway.

5. If any maintainer takes employment with, or a financial position in, a lab
   whose models are evaluated here, that is disclosed under
   [Maintainer interests](#maintainer-interests) and that maintainer recuses
   themselves from item selection and rubric changes affecting that lab.

6. **This file is append-only for historical entries.** Superseded statements are
   struck through, not deleted. A reader must be able to reconstruct what was
   disclosed at the time any past run was published.

---

## Maintainer interests

| Maintainer | Relevant interests | As of |
|---|---|---|
| _(maintainer)_ | None declared | 2026-09-08 |

Fill this in honestly, including small holdings and past employment. "Relevant"
means any relationship with an organisation appearing in `data/models.yaml` or in
the `institutional-criticism` dataset.

---

## Infrastructure and vendor relationships

Disclosed because they are relationships even when they are not funding.

| Vendor | Role | Paid? | Notes |
|---|---|---|---|
| Vercel AI Gateway | Single API endpoint used to reach every evaluated model | Yes — standard metered pricing, paid by maintainers | No commercial relationship beyond paying published rates. Vercel does not build models evaluated here and has no visibility into or influence over results. |
| GitHub | Code hosting, CI, results publication | Free tier | Standard public-repository terms. |

If any of these becomes a sponsored or discounted arrangement, it moves to the
funding section above and triggers the full disclosure requirement.

---

## The conflict we cannot design away

The judge is an AI model, built by a company whose models this benchmark also
evaluates, and one track explicitly asks models to criticise AI labs — including
that company, and to criticise the government of the country it operates in.

There is no version of this project that avoids the problem. Every capable judge
is built by a lab with an interest in the outcome. What we do instead:

- The judge is **excluded from the evaluated roster** so it never scores itself.
- The judge **never sees which model produced a response.**
- The judge's **complete reasoning for every score is committed** to the repo, so
  a reader who suspects bias can go and read the actual justification rather than
  taking a number on faith.
- A **cross-judge check using a different provider's model** re-scores the same
  responses, and the deltas are published **whether or not they are flattering to
  the primary judge.** This runs in run 1, not later: the primary judge
  (`deepseek/deepseek-v3.1-terminus`) is made by a Chinese lab, and the
  institutional-criticism track asks models to criticise the Chinese government
  and DeepSeek itself. That entire track is re-scored by
  `anthropic/claude-sonnet-4.6` before results are published, and the run falls
  back to that judge if the check fails. See
  [METHODOLOGY.md §2](METHODOLOGY.md#judge-selection-and-the-self-preference-problem).

This is mitigation, not a solution. It is described in full in
[METHODOLOGY.md §2](METHODOLOGY.md#judge-selection-and-the-self-preference-problem)
and listed among the known limitations in §6.

---

## Corrections

Errors found in published results are corrected by **adding** a new run or a
correction note, never by editing a published run in place. Run folders are
immutable once committed. Corrections are listed here with the date and what
changed.

_No corrections to date._

---

## How to raise a concern

If you believe this project has an undisclosed conflict of interest, or that a
result has been shaped by one, open a public issue. Concerns about funding and
independence are handled in public, not by email.
