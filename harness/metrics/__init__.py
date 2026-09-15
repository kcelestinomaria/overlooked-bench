"""Custom G-Eval metric registry.

One module per benchmark category. Each exports a `METRIC` of type
`CategoryMetric` carrying its rubric text, scoring scale, dimension weights and
a docstring explaining why the metric measures what it claims to measure.

Adding a category means adding a module here and a dataset folder under
`data/categories/`. Nothing else in the harness needs to change.

RUBRIC HASHING
--------------
`rubric_hash()` fingerprints the exact rubric text handed to the judge. That hash
is written into every scored record. If a rubric is edited, the hash changes and
the change is visible in the run diff, whether or not anyone remembered to update
the changelog. This is deliberate: METHODOLOGY.md records intent, but the hash
is the thing that cannot be forgotten to update.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib

from .base import SCALE_DESCRIPTION, SCALE_MAX, SCALE_MIN, CategoryMetric, Dimension, normalise
from . import (
    calibration_general,
    education,
    ethics_philosophy,
    institutional_criticism,
    niche_academic,
    org_enterprise,
)

REGISTRY: dict[str, CategoryMetric] = {
    m.METRIC.category: m.METRIC
    for m in (
        ethics_philosophy,
        niche_academic,
        org_enterprise,
        education,
        institutional_criticism,
        calibration_general,
    )
}


def get_metric(category: str) -> CategoryMetric:
    try:
        return REGISTRY[category]
    except KeyError as exc:
        known = ", ".join(sorted(REGISTRY))
        raise KeyError(f"No metric for category {category!r}. Known: {known}") from exc


def rubric_hash(category: str) -> str:
    """Content hash of the rubric text as the judge receives it."""
    metric = get_metric(category)
    payload = metric.rubric_block() + "\n" + SCALE_DESCRIPTION
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def all_rubric_hashes() -> dict[str, str]:
    return {cat: rubric_hash(cat) for cat in sorted(REGISTRY)}


__all__ = [
    "REGISTRY",
    "CategoryMetric",
    "Dimension",
    "get_metric",
    "rubric_hash",
    "all_rubric_hashes",
    "normalise",
    "SCALE_DESCRIPTION",
    "SCALE_MIN",
    "SCALE_MAX",
]
