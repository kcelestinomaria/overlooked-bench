"""G-Eval metric: Organisational & Enterprise Tasks.

WHY THIS METRIC EXISTS
----------------------
GDPval and similar work measure economically valuable task performance weighted
toward large US firms in high-GDP sectors. That is a defensible thing to measure
and it is not what most organisations are. Most organisations on earth are small,
under-resourced, operating outside the US, and often not firms at all —
nonprofits, cooperatives, family businesses, informal-sector operations,
religious and community institutions, small public bodies.

The specific failure this metric is built to catch is *resource transposition*:
the model produces a genuinely good answer, for a different organisation than the
one described. Asked to plan hiring for a 12-person NGO on a fixed grant, it
returns advice premised on a recruiting function, an ATS, competitive equity
compensation, and a six-month runway of discretionary spend. Nothing in it is
false. All of it is unusable. This is by far the most common way models fail
small-organisation tasks, and no generic helpfulness score detects it, because
the answer looks excellent unless you are the one who has to execute it.

`constraint_fidelity` is therefore weighted highest and scored strictly: the
constraints in these prompts (headcount, budget, jurisdiction, legal form,
timeline) are the task. An answer that violates the budget is wrong in the same
way a wrong arithmetic answer is wrong, and is scored that way.

`jurisdictional_accuracy` is separated out because the second failure is
defaulting to US law and US institutional assumptions regardless of the
jurisdiction named — at-will employment, 501(c)(3) rules, US tax treatment —
which is actively dangerous advice outside the US and is asserted with the same
confidence as everything else.
"""

from .base import CategoryMetric, Dimension

METRIC = CategoryMetric(
    category="org-enterprise",
    name="Organisational & Enterprise Task Competence",
    version="1.0.0",
    purpose=(
        "Measures whether a model can produce work products that are actually usable by "
        "small, resource-constrained, and non-US organisations, rather than advice "
        "silently premised on a large, well-funded US firm."
    ),
    judge_guidance=(
        "Score this as the person who has to execute the plan on Monday, with exactly "
        "the resources stated in the prompt and no others.\n\n"
        "A polished, professional, well-structured deliverable that assumes resources the "
        "organisation does not have is a FAILURE, not a partial success. Do not let "
        "presentation quality carry the score.\n\n"
        "Where the prompt names a jurisdiction other than the United States, check "
        "actively for US assumptions smuggled in as universal ones: at-will employment, "
        "US nonprofit tax categories, US-style payroll and benefits, US contract norms. "
        "Where the item includes rubric notes listing required elements, score against "
        "them explicitly."
    ),
    dimensions=[
        Dimension(
            key="constraint_fidelity",
            name="Fidelity to stated constraints",
            weight=0.30,
            rubric=(
                "Does the response respect every constraint the prompt states — budget, "
                "headcount, timeline, legal form, staff capacity, funding restrictions? "
                "Score 0 if a central constraint is ignored or violated. Score 4 if every "
                "constraint is respected AND the response shows its arithmetic where money "
                "or headcount is involved, so the reader can check it. If the response "
                "must relax a constraint because the task is genuinely infeasible as "
                "stated, saying so explicitly and justifying it is a 3 or 4; silently "
                "exceeding the constraint is a 0."
            ),
            evaluation_steps=[
                "List every constraint stated in the prompt.",
                "For each, find where the response honours or breaks it.",
                "Where money or headcount is involved, check the arithmetic actually adds up.",
                "Distinguish an explicit, justified relaxation of a constraint from a silent violation.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Constraints are the task in this category. Scoring them strictly is what "
                "separates a usable deliverable from a well-written one."
            ),
        ),
        Dimension(
            key="contextual_realism",
            name="Realism for the organisation described",
            weight=0.25,
            rubric=(
                "Is the advice calibrated to an organisation of this size, sector and "
                "resource level? Penalise recommendations that presuppose functions this "
                "organisation does not have (dedicated HR, legal counsel, procurement, a "
                "data team), tooling it could not afford or administer, or process "
                "overhead that would consume the staff time it is meant to save. Reward "
                "recognition of the real constraints of small organisations: role overlap, "
                "volunteer and part-time labour, restricted or lumpy funding, key-person "
                "dependency, no slack."
            ),
            evaluation_steps=[
                "List every capability, role, tool or budget line the response assumes exists.",
                "Check each against the organisation described in the prompt.",
                "Assess whether the process overhead proposed is sustainable at this staffing level.",
                "Check whether small-organisation realities are acknowledged or ignored.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Directly targets resource transposition — the dominant failure mode, and "
                "one that generic quality scoring systematically rewards rather than catches."
            ),
        ),
        Dimension(
            key="actionability",
            name="Actionability of the deliverable",
            weight=0.25,
            rubric=(
                "Did the response produce the thing that was asked for, in usable form? "
                "If a budget was requested, are there line items and totals? If a hiring "
                "plan, are there roles, sequence, salary bands and a rationale? Penalise "
                "responses that describe how one would approach the task instead of doing "
                "it, and responses that stop at a framework or a list of considerations. "
                "Score 4 when the output could be taken into a board or staff meeting with "
                "light editing."
            ),
            evaluation_steps=[
                "Identify the deliverable the prompt requested.",
                "Check whether the response produced it or described the process of producing it.",
                "Check for the concrete components a practitioner would expect in that deliverable.",
                "Judge whether it could be used with light editing.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Meta-advice is the cheapest way to appear helpful without doing the work. "
                "Small organisations asking these questions have no capacity to convert a "
                "framework into a deliverable — that is why they asked."
            ),
        ),
        Dimension(
            key="jurisdictional_accuracy",
            name="Jurisdictional and regulatory accuracy",
            weight=0.20,
            rubric=(
                "Where the task touches law, regulation, tax or employment practice, is "
                "the response correct for the jurisdiction named — and does it avoid "
                "asserting US defaults as universal? Score 0 for confidently wrong "
                "jurisdiction-specific claims. Score 4 for accurate treatment that also "
                "flags where local professional advice is genuinely required and why. "
                "A generic 'consult a lawyer' with no substantive content is a 1: it is a "
                "disclaimer, not an answer. If the prompt does not involve law or "
                "regulation, score this dimension on general factual accuracy instead and "
                "note that you have done so."
            ),
            evaluation_steps=[
                "Identify the jurisdiction and any legal or regulatory claims made.",
                "Verify each against that jurisdiction, not against US practice.",
                "Explicitly check for US assumptions presented as universal.",
                "Judge whether referrals to professional advice are specific and warranted, or used as a substitute for content.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Wrong-jurisdiction legal advice is delivered in the same confident "
                "register as correct advice and is the highest-harm error in this category."
            ),
        ),
    ],
)
