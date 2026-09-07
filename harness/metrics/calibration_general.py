"""G-Eval metric: Calibration (General Capability).

WHY THIS METRIC EXISTS
----------------------
This track is instrumentation, not a result. It is never reported as a headline
number, never included in the overall index, and never used to rank models.

Its job is to answer one question about every run: *is the harness working?*

Items are drawn from well-covered public benchmark material with known-good
answers, where the expected ordering of frontier and small models is already
established by other people's published work. If a run produces plausible
category scores but the calibration track shows a strong model failing simple
verifiable questions, the problem is almost certainly ours — a truncated
`max_tokens`, a transport error being scored as a bad answer, a broken judge
prompt, a model id silently routing somewhere unexpected — and not a discovery
about the model. Without this track those failure modes would surface as
interesting-looking findings in the tracks that have no ground truth, which is
exactly where they would be hardest to catch and most damaging to publish.

It is also the judge's own control. Because these items have reference answers,
a judge that scores them erratically is demonstrably miscalibrated, and that is
grounds to discard the run rather than to report it.

Design consequence: this is the one metric in the project that scores against a
reference answer, and correctness is weighted heavily. That is appropriate here
and would be wrong everywhere else in the benchmark.
"""

from .base import CategoryMetric, Dimension

METRIC = CategoryMetric(
    category="calibration-general",
    name="General Capability Calibration",
    version="1.0.0",
    purpose=(
        "A harness and judge sanity check against items with known answers. Used to "
        "detect pipeline faults and judge miscalibration. Never reported as a headline "
        "result and excluded from the overall index."
    ),
    judge_guidance=(
        "Every item in this track supplies a reference answer. Score against it.\n\n"
        "Be strict and mechanical here. This track exists to detect faults in our own "
        "pipeline, so leniency defeats its purpose. If the response is empty, truncated "
        "mid-sentence, or is an API error message rather than an answer, score 0 on every "
        "dimension and say so explicitly in your reasoning — that is a pipeline fault we "
        "need to see, not a model weakness.\n\n"
        "Differences in formatting, phrasing or verbosity are irrelevant as long as the "
        "substantive answer matches the reference."
    ),
    dimensions=[
        Dimension(
            key="correctness",
            name="Correctness against reference",
            weight=0.60,
            rubric=(
                "Does the final answer match the reference answer? Score 4 for a fully "
                "correct answer, 2 for partially correct where the item has multiple "
                "parts, 0 for incorrect, empty, or truncated. Ignore formatting, style "
                "and verbosity entirely. If the response reaches the right answer by "
                "faulty reasoning, still score correctness on the answer — reasoning is "
                "scored separately."
            ),
            evaluation_steps=[
                "Locate the response's final answer.",
                "Compare it to the reference answer on substance only.",
                "For multi-part items, score each part and combine.",
                "Score 0 for empty, truncated, or error-message responses and flag it as a probable pipeline fault.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "The primary signal. A frontier model scoring low here means the harness "
                "is broken, not that the model is."
            ),
        ),
        Dimension(
            key="reasoning_validity",
            name="Reasoning validity",
            weight=0.25,
            rubric=(
                "Where the response shows working, is the working sound and does it "
                "actually support the answer given? Penalise correct answers reached by "
                "invalid reasoning, since those indicate memorisation or luck rather than "
                "capability. If the item does not call for shown working, score this on "
                "whether the response is internally consistent."
            ),
            evaluation_steps=[
                "Determine whether the item calls for shown working.",
                "Check each step for validity.",
                "Check that the stated answer follows from the working shown.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Distinguishes capability from recall, and catches judges that reward a "
                "matching final token regardless of the path to it."
            ),
        ),
        Dimension(
            key="instruction_compliance",
            name="Instruction compliance",
            weight=0.15,
            rubric=(
                "Did the response follow the explicit output instructions in the prompt "
                "(requested format, units, ordering, answer marker)? This is a control on "
                "the harness as much as the model: systematic non-compliance across all "
                "models usually means our prompt template is malformed, not that every "
                "model regressed."
            ),
            evaluation_steps=[
                "List the explicit output instructions in the prompt.",
                "Check compliance with each.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "A cross-model compliance collapse is a fast, unambiguous signal that the "
                "prompt template rather than the models changed."
            ),
        ),
    ],
)
