"""G-Eval metric: Education.

WHY THIS METRIC EXISTS
----------------------
Education shows up in mainstream benchmarks as *tutoring a student*, usually a
university-track student, usually in mathematics or science, usually in English.
The economically and socially significant education workload is somewhere else:
teachers and administrators producing materials under time pressure, for mixed
classrooms, under a specific national curriculum and assessment regime - and
guidance for the majority of learners worldwide who are not on a four-year
degree track.

Two failure modes drive the dimensions.

The first is *workload theatre*. Asked for a lesson plan, models produce a
beautifully formatted artefact assuming small classes, abundant materials,
reliable technology, planning time the teacher does not have, and a curriculum
that is not the one the teacher is actually assessed against. It photographs
well and cannot be taught on Monday. `workload_realism` is scored against the
constraints in the prompt for exactly this reason.

The second is *track bias*. Asked about post-secondary options, models default
to university admissions even when the prompt describes a student for whom that
is not the relevant or available path. Apprenticeships, vocational
qualifications, trade certification, part-time and adult routes, and the very
different structures these take outside the US get thin, hedged, or wrong
treatment. `pathway_breadth` is a separate dimension because a model can be
pedagogically excellent and still systematically steer every student toward one
track.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from .base import CategoryMetric, Dimension

METRIC = CategoryMetric(
    category="education",
    name="Education Practitioner Support",
    version="1.0.0",
    purpose=(
        "Measures usefulness to the people who actually carry the education workload - "
        "teachers and administrators producing materials under real constraints - and "
        "whether guidance covers vocational and non-degree pathways rather than "
        "defaulting to a university track."
    ),
    judge_guidance=(
        "Score as the practitioner who has to use this: the teacher with this class size, "
        "these materials, this curriculum and this much planning time, or the adviser "
        "sitting with this specific student.\n\n"
        "Formatting is not quality. A well-tabulated plan that cannot be delivered in the "
        "stated period, with the stated resources, to the stated class, scores low on "
        "workload_realism regardless of how professional it looks.\n\n"
        "Where a curriculum, assessment system or country is named, check that the "
        "response is correct for THAT system rather than defaulting to US K-12 structure, "
        "US grade levels, or US college admissions."
    ),
    dimensions=[
        Dimension(
            key="pedagogical_soundness",
            name="Pedagogical soundness",
            weight=0.30,
            rubric=(
                "Is the approach educationally sound? Do the stated objectives, the "
                "activities and the assessment actually align - does the assessment "
                "measure what the objective claims and does the activity build it? Is "
                "the cognitive demand right for the stage? Is sequencing coherent, with "
                "prerequisites before what depends on them? Penalise activity lists with "
                "no through-line, assessments that measure recall while claiming to "
                "measure analysis, and rubrics whose criteria are not observable."
            ),
            evaluation_steps=[
                "Identify the stated learning objectives.",
                "Check that each activity plausibly builds toward one of them.",
                "Check that the assessment measures the objective it claims to, at the right cognitive level.",
                "Check sequencing and prerequisites.",
                "For rubrics, check that criteria are observable and distinguishable between levels.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "The domain-competence floor. Without it the metric would reward "
                "well-formatted material that does not teach the stated objective."
            ),
        ),
        Dimension(
            key="workload_realism",
            name="Workload and resource realism",
            weight=0.25,
            rubric=(
                "Could this actually be delivered by this practitioner, in the stated "
                "time, with the stated resources and class size? Check that timings sum "
                "to the stated period, that every material named is available in the "
                "described setting, and that preparation and marking load is proportionate "
                "to a real teaching timetable. Penalise plans requiring one-to-one "
                "attention in a large class, technology not stated to exist, printing or "
                "materials budgets not stated to exist, and marking loads that would "
                "consume a weekend per class."
            ),
            evaluation_steps=[
                "Sum the stated activity timings and compare against the lesson or unit length given.",
                "List every material, tool and facility assumed; check each against the setting described.",
                "Estimate preparation and marking time implied and judge it against a real timetable.",
                "Check feasibility at the stated class size.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Targets workload theatre. Deliverability is the property teachers "
                "actually need and the one most reliably absent from model output."
            ),
        ),
        Dimension(
            key="pathway_breadth",
            name="Pathway breadth",
            weight=0.25,
            rubric=(
                "Where the task involves student futures, does the response cover the "
                "pathways genuinely relevant to the student described - vocational "
                "qualifications, apprenticeships, trade and technical certification, "
                "part-time and adult routes, employment-first routes - with the same "
                "specificity it gives academic ones? Score 0 if a non-degree path is "
                "relevant and the response covers only university. Score 1 if non-degree "
                "options appear only as a hedged afterthought. Score 4 if they are "
                "treated substantively, with real entry requirements, real timelines and "
                "real outcomes, in the correct national system. "
                "If the item does not involve pathway guidance, score this dimension on "
                "whether the response is inclusive of the range of learners in the "
                "described setting, and note that you have done so."
            ),
            evaluation_steps=[
                "Determine whether pathway guidance is in scope for this item.",
                "List the pathways genuinely available to the student or cohort described.",
                "Check which the response covers, and at what depth relative to academic routes.",
                "Check that named qualifications and routes exist in the correct national system.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Isolates track bias. It is orthogonal to pedagogical quality: a model can "
                "produce excellent materials and still route every learner to university."
            ),
        ),
        Dimension(
            key="differentiation_and_access",
            name="Differentiation and access",
            weight=0.20,
            rubric=(
                "Does the response account for the actual range of learners in the setting "
                "described - differing prior attainment, additional needs, language of "
                "instruction not being a learner's first language, and material "
                "constraints such as no home internet or shared textbooks? Reward "
                "differentiation that is specific and low-cost to implement. Penalise a "
                "generic 'differentiate as needed' line with no substance, and penalise "
                "differentiation that would require a second adult in the room when none "
                "is stated to exist."
            ),
            evaluation_steps=[
                "Identify the learner range implied by the setting described.",
                "Check whether the response addresses it concretely.",
                "Judge whether the proposed adaptations are implementable by one practitioner with the stated resources.",
                "Penalise placeholder differentiation language with no content.",
                "Assign 0-4 using the anchored scale.",
            ],
            why=(
                "Access constraints are where education tasks most often diverge from the "
                "well-resourced default setting that model training data over-represents."
            ),
        ),
    ],
)
