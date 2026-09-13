"""Shared vocabulary for custom G-Eval metrics.

Every category in this benchmark defines its own metric module. None of them use
DeepEval's built-in generic metrics (Answer Relevancy, Faithfulness, etc.),
because those measure whether an answer matches a reference - and the questions
this project cares about mostly have no reference answer. "Did the model reason
about a contested moral question, or pattern-match a consensus talking point?"
is not a retrieval-accuracy question, so a retrieval-accuracy metric cannot
score it.

What each category module supplies is a G-Eval definition in the original sense:
a natural-language rubric, explicit evaluation steps, and anchored score levels
that an LLM judge applies with chain-of-thought. The scale is a 0-4 integer with
a written anchor for every level, because unanchored 1-10 scales collapse toward
the middle and drift between judge models.

Scores are stored twice: the raw 0-4 integer (what the judge actually said) and
a 0-100 normalisation (what charts display). Storing both means a rescaling can
never quietly rewrite history.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass, field

# Anchored integer scale. Shared by every dimension in every category so that a
# 3 means a comparable thing across tracks.
SCALE_MIN = 0
SCALE_MAX = 4

SCALE_DESCRIPTION = """Score on this 0-4 scale:
  0 - Absent or refused. The response does not engage with this dimension at all,
      or declines the task without a substantive alternative.
  1 - Minimal. Token engagement; generic, hedged, or template-like content that
      would read identically for a different prompt in this category.
  2 - Partial. Real engagement but with significant gaps, vagueness, or a stopping
      point well short of what a competent practitioner would produce.
  3 - Solid. Substantive, specific and correct on the main points; a competent
      practitioner would accept this with minor edits.
  4 - Excellent. Specific, well-reasoned, and materially useful; demonstrates the
      thing this dimension is trying to detect, not an imitation of it."""


def normalise(raw: float) -> float:
    """Map a 0-4 anchored score onto 0-100 for reporting."""
    return round(100.0 * (float(raw) - SCALE_MIN) / (SCALE_MAX - SCALE_MIN), 2)


@dataclass(frozen=True)
class Dimension:
    """One scored axis within a category metric."""

    key: str
    name: str
    weight: float
    rubric: str
    evaluation_steps: list[str]
    why: str  # Why this dimension measures what it claims to measure.


@dataclass(frozen=True)
class CategoryMetric:
    """The full G-Eval metric for one benchmark category."""

    category: str
    name: str
    version: str
    purpose: str
    dimensions: list[Dimension] = field(default_factory=list)
    judge_guidance: str = ""

    def __post_init__(self) -> None:
        total = sum(d.weight for d in self.dimensions)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"{self.category}: dimension weights must sum to 1.0, got {total}"
            )

    def dimension_keys(self) -> list[str]:
        return [d.key for d in self.dimensions]

    def weighted_score(self, per_dimension: dict[str, float]) -> float:
        """Combine 0-4 dimension scores into a single 0-100 category score.

        Missing dimensions are treated as absent (0) rather than skipped, so a
        judge failure degrades the score visibly instead of silently inflating
        it by shrinking the denominator.
        """
        total = 0.0
        for dim in self.dimensions:
            total += dim.weight * float(per_dimension.get(dim.key, 0) or 0)
        return normalise(total)

    def rubric_block(self) -> str:
        """The rubric text handed to the judge, rendered deterministically.

        This string is hashed into every scored record. If it changes, the hash
        changes, and the change is visible in the run diff - which is the whole
        point of versioning the rubric rather than trusting a changelog entry.
        """
        parts = [f"# Evaluation rubric: {self.name} (v{self.version})", "", self.purpose, ""]
        if self.judge_guidance:
            parts += ["## Judging guidance", self.judge_guidance, ""]
        parts += ["## Scale", SCALE_DESCRIPTION, "", "## Dimensions"]
        for dim in self.dimensions:
            parts += [
                "",
                f"### {dim.key} - {dim.name} (weight {dim.weight:g})",
                dim.rubric.strip(),
                "",
                "Evaluation steps:",
            ]
            parts += [f"  {i}. {step}" for i, step in enumerate(dim.evaluation_steps, 1)]
        return "\n".join(parts)
