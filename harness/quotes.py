"""Verbatim-quote checking.

A quote that appears on a chart or a social card has to be something the model
actually wrote. Judges paraphrase, tidy punctuation and occasionally invent, so
no judge-supplied quote is trusted until a program has found it in the archived
raw response.

Matching ignores only what cannot change meaning: whitespace runs, markdown
emphasis and code markers, and typographic quote and dash variants. Anything
else that differs - a word, a number, a unit - fails the match, and the quote is
discarded rather than repaired.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import re

_TRANSLATE = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
})
_MARKUP = re.compile(r"[*_`#>]+")
_SPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    text = (text or "").translate(_TRANSLATE)
    text = _MARKUP.sub("", text)
    return _SPACE.sub(" ", text).strip().lower()


def quote_in_text(quote: str, text: str, min_chars: int = 12) -> bool:
    """True if `quote` occurs in `text` after normalisation.

    Very short quotes are rejected outright: "use Redis" can match a sentence
    that says "do not use Redis", and a card built on that would be a lie.
    Trailing ellipses the judge may add are tolerated by matching each
    ellipsis-separated fragment in order.
    """
    q = normalise(quote).strip(" .")
    if len(q) < min_chars:
        return False
    hay = normalise(text)
    pos = 0
    for frag in [f.strip() for f in re.split(r"\.\.\.|…", q) if f.strip()]:
        found = hay.find(frag, pos)
        if found < 0:
            return False
        pos = found + len(frag)
    return True
