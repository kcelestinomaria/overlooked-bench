"""G-Eval metric: Niche Academic Domains.

WHY THIS METRIC EXISTS
----------------------
Frontier benchmarks sample academic ability from a narrow band: competition
mathematics, physics, competitive programming, US-curriculum science, and
graduate exam questions in fields with large English-language corpora. Those are
chosen because they have unambiguous answers and abundant test material, not
because they represent scholarship.

This track samples the other end: fields with small literatures, fields whose
scholarship is mostly not in English, fields where the state of knowledge is
genuinely unsettled, and fields that are regionally rather than globally
studied. Historical linguistics of under-documented language families, regional
agronomy, archival palaeography, area-specific legal history, ethnomusicology,
non-Western medical traditions studied academically.

The failure mode here is distinctive and is why `scholarly_calibration` carries
real weight. On a thin literature, a model's fluency does not degrade even as its
knowledge does - it produces the same confident register whether it is
reproducing a well-attested finding or improvising. A model that says "the
evidence here is contested and my recollection of the specific chronology is
weak" is more useful to a researcher than one that invents a tidy consensus, and
a metric that scored only correctness would rank them the other way round.

`field_situatedness` exists because the second failure mode is subtler: answering
a question in a regional field using the framework of the dominant Anglophone
adjacent field, which produces text that is not exactly wrong but that no
scholar in that field would have written.
"""

from .base import CategoryMetric, Dimension

METRIC = CategoryMetric(
    category="niche-academic",
    name="Niche Academic Domain Competence",
    version="1.0.0",
    purpose=(
        "Measures substantive competence in academic domains that are under-represented "
        "in mainstream benchmarks, and whether the model's confidence "
        "tracks its actual knowledge as the literature thins."
    ),
    judge_guidance=(
        "Where the item supplies reference material or rubric notes, treat that as "
        "authoritative and score against it. Where it does not, use your own domain "
        "knowledge, and where your own knowledge is genuinely insufficient to verify a "
        "claim, say so in your reasoning and score conservatively rather than guessing.\n\n"
        "Do not reward length or academic register. A confident, well-organised, "
        "plausible-sounding answer that is substantively hollow is the specific failure "
        "this track exists to detect, and should score LOW - lower than a shorter answer "
        "that is accurate about less.\n\n"
        "Explicit, well-placed uncertainty is a positive signal, not a hedge. Penalise it "
        "only when it is used to avoid engaging at all."
    ),
    dimensions=[
        Dimension(
            key="domain_accuracy",
            name="Domain accuracy",
            weight=0.40,
            rubric=(
                "Are the substantive claims correct? Check names, chronology, "
                "terminology, mechanisms, and the attribution of positions to scholars "
                "or schools. Penalise invented citations, invented technical terms, and "
                "invented consensus especially heavily - in a thin literature these are "
                "difficult for a non-specialist reader to detect, which makes them more "
                "damaging than in a well-covered field, not less."
            ),
            evaluation_steps=[
                "Extract every substantive factual claim.",
                "Verify each against the item's reference material if provided, otherwise against your own knowledge.",
                "Flag any invented citation, invented term, or claimed consensus you cannot corroborate.",
                "Weight errors by how load-bearing they are to the answer.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "The accuracy floor. Weighted highest because in a thin-literature domain "
                "a reader has the least independent ability to catch an error."
            ),
        ),
        Dimension(
            key="depth_beyond_survey",
            name="Depth beyond encyclopaedia level",
            weight=0.30,
            rubric=(
                "Does the response go past what a general reference article would say? "
                "Look for engagement with methods, evidence, and the specific scholarly "
                "debates within the field; awareness of what is disputed and on what "
                "grounds; and the kind of detail that indicates familiarity with the "
                "literature rather than with summaries of it. An accurate but purely "
                "introductory answer to a specialist question scores 2, not 4."
            ),
            evaluation_steps=[
                "Judge the level the question was pitched at.",
                "Judge the level the answer was pitched at.",
                "Look for engagement with methodology, evidence quality, and internal scholarly debate.",
                "Ask whether a specialist would learn anything, or would recognise this as a summary of a summary.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Separates real domain depth from a well-written general-knowledge "
                "answer. Accuracy alone cannot make that distinction."
            ),
        ),
        Dimension(
            key="scholarly_calibration",
            name="Calibration to the state of the field",
            weight=0.20,
            rubric=(
                "Does the response distinguish what is well established from what is "
                "contested, thinly evidenced, or unknown? Does it flag where its own "
                "knowledge is weak? Score 4 for accurate, specific calibration ('the "
                "dating is secure; the proposed substrate influence is one hypothesis "
                "among several and rests on a small corpus'). Score 0 for uniform "
                "confidence across claims of wildly different evidential status, or for "
                "presenting one scholar's proposal as settled fact. Blanket disclaimers "
                "attached to everything are not calibration and score 1."
            ),
            evaluation_steps=[
                "Identify claims of clearly differing evidential status in the response.",
                "Check whether the response signals that difference.",
                "Distinguish specific, targeted calibration from a blanket disclaimer.",
                "Check whether any genuinely contested point is presented as settled.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "In thin literatures, calibration is the property that determines whether "
                "a model is usable by a researcher at all. It is invisible to accuracy "
                "scoring, which treats a lucky confident guess and a flagged uncertainty "
                "as equivalent."
            ),
        ),
        Dimension(
            key="field_situatedness",
            name="Situated in the right field",
            weight=0.10,
            rubric=(
                "Does the response use the frameworks, terminology and scholarly "
                "conventions of the field actually asked about, or does it answer from "
                "the nearest dominant Anglophone adjacent field? Penalise answers that "
                "silently substitute a Western or Anglophone framing for a question about "
                "a regional scholarly tradition, and answers that ignore non-English "
                "scholarship where it is central to the field."
            ),
            evaluation_steps=[
                "Identify the scholarly tradition the question belongs to.",
                "Check whether the response's vocabulary and framing belong to that tradition.",
                "Note any silent substitution of a dominant adjacent field's framework.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Catches a failure invisible to accuracy checking: an answer that is "
                "locally true but framed so that no scholar in the field would recognise "
                "it as an answer to their question."
            ),
        ),
    ],
)
