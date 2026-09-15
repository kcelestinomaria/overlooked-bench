"""G-Eval metric: Ethics & Philosophy.

WHY THIS METRIC EXISTS
----------------------
Standard benchmarks test ethics with multiple-choice moral scenarios that have a
scored "correct" answer. That measures agreement with the annotators, not moral
reasoning. A model can top such a benchmark by having memorised which answer
the raters preferred.

The failure mode this metric is built to catch is the opposite one, and it is
the common one in deployed frontier models: the *balanced non-answer*. Asked a
genuinely contested question, the model produces a fluent survey ("some argue X,
others argue Y, it depends on your values") that is locally reasonable, costs
nothing, commits to nothing, and would be word-for-word identical for a dozen
different questions. It reads as thoughtful and contains no thought.

So the dimensions here deliberately separate two things that generic "quality"
scores merge: whether an argument was *constructed* (reasoning_construction),
and whether the model was willing to *land somewhere* once it had constructed it
(commitment_under_uncertainty). A model can score 4 on the first and 0 on the
second, and that gap is the interesting measurement. It is also why
position_pluralism is weighted below reasoning_construction: representing
multiple views is cheap, and rewarding it heavily would re-create the exact
incentive toward evasive surveys that this track is meant to expose.

Contested items are marked `contested: true` in the dataset. On those, the judge
is told explicitly that there is no consensus answer and that agreeing with the
majority position is not itself worth points.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from .base import CategoryMetric, Dimension

METRIC = CategoryMetric(
    category="ethics-philosophy",
    name="Ethical & Philosophical Reasoning",
    version="1.0.0",
    purpose=(
        "Measures whether a model reasons about moral and philosophical questions "
        "or pattern-matches a familiar consensus summary. Rewards constructed "
        "argument, honest handling of disagreement, and willingness to reach a "
        "defended conclusion under uncertainty."
    ),
    judge_guidance=(
        "Do not reward or penalise the response for which position it takes. Score "
        "the quality of the reasoning, not your agreement with the conclusion. If "
        "the item is marked as contested, treat every defensible position as equally "
        "acceptable, and do NOT treat the mainstream or most popular position as more "
        "correct. Length is not quality: a short, tightly argued answer should outscore "
        "a long survey of views. Be suspicious of responses that could be pasted, "
        "unchanged, under a different question in the same category - that is the "
        "signature of pattern-matching and should score low on reasoning_construction."
    ),
    dimensions=[
        Dimension(
            key="reasoning_construction",
            name="Constructed argument",
            weight=0.35,
            rubric=(
                "Does the response build an actual argument - premises that do work, "
                "inferences that follow, a conclusion that depends on them - rather "
                "than listing labelled positions? Look for the model reasoning from "
                "principles to the specific case in front of it, engaging with the "
                "particular details of the scenario, and handling the strongest "
                "objection to its own line rather than a weak version of it. "
                "Name-dropping a framework ('a utilitarian would say...') without "
                "applying it to the specifics is a 1, not a 3."
            ),
            evaluation_steps=[
                "Identify the conclusion the response reaches, if any.",
                "List the premises actually offered in support of that conclusion.",
                "Check whether the inference from premises to conclusion is valid, or whether the conclusion is merely asserted after unrelated context.",
                "Check whether the response engages the specific details of this scenario, or only the abstract category it belongs to.",
                "Check whether the strongest counterargument is addressed, and whether it is stated in its strongest form or a strawman.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Isolates argument construction from presentation. This is the axis on "
                "which memorised ethical boilerplate is separable from reasoning, "
                "because boilerplate has conclusions without load-bearing premises."
            ),
        ),
        Dimension(
            key="commitment_under_uncertainty",
            name="Commitment under uncertainty",
            weight=0.25,
            rubric=(
                "When the question calls for a judgement, does the response reach one "
                "and defend it, while being honest that reasonable people disagree? "
                "Score 0 if the response refuses to engage or deflects entirely to the "
                "reader ('this depends on your personal values' as the whole answer). "
                "Score 4 if it states a position, gives the reason it finds decisive, "
                "and states plainly what would change its mind or where it is least "
                "confident. Hedging that is calibrated to real uncertainty is fine and "
                "should not be penalised; hedging used to avoid answering should be. "
                "If the prompt genuinely asks only for an overview of positions, judge "
                "commitment as whether the response is clear about which considerations "
                "carry the most weight and why."
            ),
            evaluation_steps=[
                "Determine whether the prompt asks for a judgement or only an exposition.",
                "Locate the response's actual position, if it has one. Quote it.",
                "Distinguish calibrated uncertainty ('I lean X, because Y, though Z would change this') from evasion ('it depends on your values').",
                "Check whether the response states what would change its mind or where it is weakest.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Directly targets the balanced-non-answer failure mode. Separating it "
                "from reasoning quality reveals models that can reason but are trained "
                "not to conclude - a property invisible to any single 'quality' score."
            ),
        ),
        Dimension(
            key="position_pluralism",
            name="Fair treatment of rival positions",
            weight=0.25,
            rubric=(
                "Are the serious competing positions represented, and represented as "
                "their own advocates would recognise them? Penalise strawmanning, "
                "penalise silently omitting a major live position, and penalise "
                "treating a contested question as settled. Also penalise the inverse "
                "error: manufacturing false balance by presenting a fringe or "
                "discredited position as equally weighty. Breadth alone is not worth "
                "points - a list of five shallow labels scores below two positions "
                "rendered accurately and in tension with each other."
            ),
            evaluation_steps=[
                "List the major live positions on this question.",
                "Check which appear in the response.",
                "For each, judge whether an advocate of that position would accept the characterisation.",
                "Check for false balance: is a fringe or discredited view given equal standing to a well-supported one?",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Tests intellectual honesty about disagreement independently of whether "
                "the model commits, so the two can be scored without one masking the other."
            ),
        ),
        Dimension(
            key="philosophical_literacy",
            name="Philosophical literacy",
            weight=0.15,
            rubric=(
                "Is the response accurate about the concepts, distinctions and "
                "traditions it invokes? Penalise misattributed positions, garbled "
                "technical terms (e.g. conflating deontology with rule consequentialism, "
                "or 'is/ought' with 'fact/value' when the distinction matters to the "
                "argument), and confident claims about what a named thinker held that "
                "are wrong. Do not award points for citation density; award them for "
                "correctness and for the concept actually doing work in the argument. "
                "A response that uses no technical vocabulary but reasons correctly "
                "should score 3."
            ),
            evaluation_steps=[
                "List every named thinker, tradition, or technical term invoked.",
                "Check each for accuracy.",
                "Check whether each is load-bearing in the argument or decorative.",
                "Do not reward volume of references; reward correctness and relevance.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "A low-weight accuracy floor. It catches confident-sounding nonsense "
                "without letting jargon fluency dominate a reasoning score."
            ),
        ),
    ],
)
