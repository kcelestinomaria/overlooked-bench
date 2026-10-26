"""G-Eval metric: Software Engineering in Production.

WHY THIS METRIC EXISTS
----------------------
Coding benchmarks score whether code passes tests in a sandbox. The work most
engineering teams actually ask a model for is different: a design, a migration
plan, a review, a runbook, for *this* team, on *this* infrastructure, inside
*this* budget. The answer is only useful if that team could execute it.

The failure this metric is built to catch is *unconstrained architecture*: the
model produces the answer it would give with unlimited headcount, an empty
infrastructure diagram and no bill. Told "no new services", it adds Redis. Told
the instance class is frozen, it proposes a blue/green cutover that provisions
a second database. Told two developers and three weeks, it writes a quarter's
roadmap. Nothing in it is wrong in the abstract. None of it can ship.

It is the engineering analogue of resource transposition in `org-enterprise`,
and it is scored the same way: `constraint_fidelity` is weighted highest and
scored strictly. Violating "no new services" is wrong the way an off-by-one
budget is wrong, however good the architecture.

THE CONSTRAINT CHECKS
---------------------
Every item in this track lists its hard constraints with a yes/no `check`
question (YES = broken). The judge answers every check and quotes the response
as evidence, in a `constraint_checks` block alongside the dimension scores. Those
verdicts drive the violation-rate charts, so they are deliberately narrower than
the dimension scores: a check asks only whether one rule was broken, never
whether the design was good.

A judge's verdict is one opinion. `harness/constraint_check.py` asks the same
questions of a second, non-generative evaluation model, and a violation is
reported as *confirmed* only when both agree. See METHODOLOGY.md section 4b.

WHAT IS NOT SCORED
------------------
No dimension rewards a preferred architecture, language or vendor. A monolith
is not better than microservices; a Postgres counter is not better than Redis.
When the prompt forbids Redis, the use of Redis is a constraint violation, not a
style judgement - and when the prompt does not forbid it, it is not penalised.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from .base import CategoryMetric, Dimension

# Verdict vocabulary the judge must use per constraint. `relaxed_explicitly` is
# a separate verdict, not a violation: a response that says "this cannot be done
# inside the constraint, and here is why" has done the right thing, and the
# charts must not count it alongside silent violations.
CONSTRAINT_VERDICTS = ("kept", "violated", "relaxed_explicitly", "not_addressed")

METRIC = CategoryMetric(
    category="software-engineering-production",
    name="Software Engineering in Production",
    version="1.0.0",
    purpose=(
        "Measures whether a model's engineering output - a design, migration plan, "
        "code review, incident review or runbook - could be executed by the team "
        "described, on the infrastructure it already runs, inside its stated budget, "
        "headcount, timeline, uptime and legal constraints."
    ),
    judge_guidance=(
        "Score this as the engineering lead who has to execute the plan on Monday with "
        "exactly the team, infrastructure and budget stated, and no others.\n\n"
        "A sophisticated, well-architected answer that breaks a stated constraint is a "
        "FAILURE on constraint_fidelity, not a partial success. Do not let technical "
        "fluency carry the score. Equally, do not reward or penalise any architecture, "
        "language, database or vendor for its own sake: only whether it fits the "
        "constraints and would work.\n\n"
        "CONSTRAINT CHECKS. The prompt context below lists hard constraints, each with a "
        "yes/no check question where YES means the response broke it. In addition to the "
        "dimension scores, your JSON object MUST include a top-level key "
        "\"constraint_checks\" mapping every constraint id to an object with:\n"
        "  \"verdict\": one of \"kept\", \"violated\", \"relaxed_explicitly\", "
        "\"not_addressed\";\n"
        "  \"evidence\": a short VERBATIM quote copied character-for-character from the "
        "response (at most 40 words) that supports the verdict, or an empty string if "
        "the verdict is \"kept\" or \"not_addressed\" and no single passage shows it.\n"
        "Use \"violated\" when the answer to the check is YES and the response does not "
        "acknowledge it is breaking the constraint. Use \"relaxed_explicitly\" when the "
        "response says the constraint cannot be met and justifies relaxing it. Use "
        "\"not_addressed\" only when the response never engages with what the "
        "constraint governs. Quotes are checked against the response text by a program; "
        "a paraphrase will be discarded.\n\n"
        "Where the item includes rubric notes listing required elements, score against "
        "them explicitly."
    ),
    dimensions=[
        Dimension(
            key="constraint_fidelity",
            name="Fidelity to stated constraints",
            weight=0.35,
            rubric=(
                "Does the response respect every hard constraint the prompt states - no "
                "new services or vendors, existing stack, budget, headcount, timeline, "
                "uptime or maintenance window, legal and retention rules? Score 0 if any "
                "central constraint is silently violated, however good the rest is. Score "
                "4 if every constraint is respected AND the response shows the arithmetic "
                "(capacity, cost, runway, effort) that lets the reader check it. If a "
                "constraint genuinely cannot be met, saying so explicitly and justifying "
                "the relaxation is a 3 or 4; quietly exceeding it is a 0."
            ),
            evaluation_steps=[
                "List every hard constraint stated in the prompt.",
                "For each, find where the response honours or breaks it - including indirectly, e.g. a technique that provisions a new instance.",
                "Where money, capacity, effort or time is involved, check the arithmetic adds up.",
                "Distinguish an explicit, justified relaxation from a silent violation.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "The constraints are the task. A plan that breaks them is a plan for a "
                "different team, and this is the failure generic quality scoring rewards."
            ),
        ),
        Dimension(
            key="production_realism",
            name="Production realism",
            weight=0.25,
            rubric=(
                "Would this work in production, operated by the team described? Reward "
                "attention to failure modes that matter at the stated scale: locking and "
                "load on shared databases, retries and idempotency, partial failure, "
                "rollback, observability of the change itself, data volumes, and the "
                "operational burden placed on a team of this size and skill mix. "
                "Penalise designs that are correct only on a whiteboard, that ignore the "
                "stated numbers, or that assume operational capacity the team lacks."
            ),
            evaluation_steps=[
                "Identify the stated scale, infrastructure and team skill mix.",
                "Check whether the proposal accounts for load, locking, retries, partial failure and rollback where relevant.",
                "Check whether the operational burden fits the team described.",
                "Note any technically incorrect claim about the named technologies.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Separates a design that survives contact with production from one that "
                "only reads well. Technical errors about the named stack land here."
            ),
        ),
        Dimension(
            key="actionability",
            name="Actionability of the deliverable",
            weight=0.20,
            rubric=(
                "Did the response produce the thing asked for - a plan, a review with "
                "corrected code, a runbook with exact commands, a post-incident review "
                "with costed actions - in a form the team could start on immediately? "
                "Penalise descriptions of how one would approach the task, lists of "
                "considerations, and plans with no sequence, owners, estimates or "
                "verification steps. Score 4 when an engineer could execute it with only "
                "light editing."
            ),
            evaluation_steps=[
                "Identify the deliverable the prompt requested.",
                "Check whether the response produced it or described producing it.",
                "Check for sequence, concrete commands or code, estimates and verification steps where they apply.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "A team under these constraints asked because it lacks the capacity to "
                "turn a framework into a plan."
            ),
        ),
        Dimension(
            key="maintainability",
            name="Maintainability and handover",
            weight=0.20,
            rubric=(
                "Will the result still be operable in six months by the people who will "
                "own it? Reward solutions proportionate to the team, that leave clear "
                "seams, tests, documentation and observability, and that state the risks "
                "and debt being accepted. Penalise added complexity the team cannot "
                "maintain, unowned moving parts, unsafe shortcuts left unflagged, and code "
                "that is clever where it should be obvious."
            ),
            evaluation_steps=[
                "Identify who will own the result after delivery, per the prompt.",
                "Check whether the added complexity is proportionate to that team.",
                "Check whether risks and accepted debt are stated rather than hidden.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Most production cost arrives after launch. A plan that ships but cannot "
                "be maintained by the stated team has moved the failure, not removed it."
            ),
        ),
    ],
)
