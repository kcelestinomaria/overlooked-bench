"""Dataset loading and validation.

Each category is one YAML file: `data/categories/<category>/items.yaml`.

Every item carries a `rationale` — one line on why it is in the benchmark. This
is required, not optional, and loading fails without it. A benchmark whose item
selection cannot be explained is a benchmark whose results cannot be defended,
and the cheapest way to guarantee the explanation exists is to make the loader
refuse to run without it.

Item ids are stable and never reused. Historical runs are keyed on them, so
reusing an id for different content would silently corrupt the time series.
`content_hash` fingerprints the prompt text, so an edited prompt is detectable in
a run diff even if the id stayed the same.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import CATEGORIES_DIR, CATEGORY_LABELS


@dataclass(frozen=True)
class Item:
    """One benchmark item."""

    id: str
    category: str
    prompt: str
    rationale: str
    tags: list[str] = field(default_factory=list)

    # Optional, category-dependent.
    reference: str | None = None      # Reference answer (calibration items).
    rubric_notes: str | None = None   # Extra guidance handed to the judge.
    contested: bool = False           # Ethics: no consensus answer exists.

    # Institutional criticism: matched-set metadata for asymmetry analysis.
    group: str | None = None
    institution: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.prompt.strip().encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["content_hash"] = self.content_hash
        return d


class DatasetError(ValueError):
    """Raised when a dataset file is malformed. Always fatal — never skipped."""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise DatasetError(msg)


def load_category(category: str, root: Path | None = None) -> list[Item]:
    """Load and validate one category's items."""
    root = root or CATEGORIES_DIR
    path = root / category / "items.yaml"
    _require(path.exists(), f"Missing dataset file: {path}")

    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}

    declared = doc.get("category")
    _require(
        declared == category,
        f"{path}: declares category {declared!r} but lives in {category!r}",
    )

    raw_items = doc.get("items") or []
    _require(bool(raw_items), f"{path}: contains no items")

    items: list[Item] = []
    seen: set[str] = set()
    for idx, raw in enumerate(raw_items):
        where = f"{path}[{idx}]"
        _require("id" in raw, f"{where}: missing 'id'")
        item_id = str(raw["id"])
        _require(item_id not in seen, f"{where}: duplicate id {item_id!r}")
        seen.add(item_id)

        prompt = (raw.get("prompt") or "").strip()
        _require(bool(prompt), f"{where} ({item_id}): empty 'prompt'")

        rationale = (raw.get("rationale") or "").strip()
        _require(
            bool(rationale),
            f"{where} ({item_id}): missing 'rationale'. Every item must record why it "
            f"is in the benchmark — see docs/CONTRIBUTING.md",
        )

        if category == "calibration-general":
            _require(
                bool((raw.get("reference") or "").strip()),
                f"{where} ({item_id}): calibration items require a 'reference' answer",
            )

        if category == "institutional-criticism":
            _require(
                bool(raw.get("group")),
                f"{where} ({item_id}): institutional-criticism items require a 'group' "
                f"so matched-set asymmetry can be computed",
            )

        items.append(
            Item(
                id=item_id,
                category=category,
                prompt=prompt,
                rationale=rationale,
                tags=list(raw.get("tags") or []),
                reference=(raw.get("reference") or None),
                rubric_notes=(raw.get("rubric_notes") or None),
                contested=bool(raw.get("contested", False)),
                group=raw.get("group"),
                institution=raw.get("institution"),
                attributes=dict(raw.get("attributes") or {}),
            )
        )
    return items


def load_all(
    categories: list[str] | None = None, root: Path | None = None
) -> dict[str, list[Item]]:
    """Load every category (or a named subset), in canonical report order."""
    wanted = categories or list(CATEGORY_LABELS)
    unknown = [c for c in wanted if c not in CATEGORY_LABELS]
    _require(not unknown, f"Unknown categories: {unknown}. Known: {list(CATEGORY_LABELS)}")
    return {c: load_category(c, root=root) for c in wanted}


def dataset_fingerprint(data: dict[str, list[Item]]) -> str:
    """One hash covering every prompt in the run.

    Two runs sharing this fingerprint were asked exactly the same questions, so
    a score change between them is a model or judge change — not a dataset edit.
    """
    h = hashlib.sha256()
    for category in sorted(data):
        for item in sorted(data[category], key=lambda i: i.id):
            h.update(f"{category}|{item.id}|{item.content_hash}".encode("utf-8"))
    return h.hexdigest()[:16]


def summarise(data: dict[str, list[Item]]) -> dict[str, int]:
    return {c: len(items) for c, items in data.items()}
