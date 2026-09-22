"""Russian text primitives shared by the toponym and name layers.

Nothing here knows about addresses or licences; it is the character-level floor
both of those stand on -- case folding, the yo, quote marks, and one step of
inflectional stemming that stands in for a morphological analyser.
"""
from __future__ import annotations

import re

# Russian inflectional endings, longest first.  Light stemming is what lets
# "Северной Двины" meet "Северная Двина" and "Воскресенская" meet "Воскресенской"
# without a morphological analyser; a token is never cut below four characters,
# which is what keeps short names ("Тимме", "Логинова") intact.
ENDINGS = ("ыми", "ими", "ого", "его", "ому", "ему", "ая", "яя", "ое", "ее",
           "ые", "ие", "ый", "ий", "ой", "ым", "им", "ом", "ых", "их", "ую",
           "юю", "ей", "ов", "ев", "а", "я", "у", "ю", "е", "и", "ы", "о")

MIN_STEM = 4

# Written as code points so the file survives any editor's idea of a quote.
QUOTES = "[" + chr(0xAB) + chr(0xBB) + chr(0x22) + chr(0x27) + chr(0x60) + "]"
_QUOTE_RE = re.compile(QUOTES)
_YO = chr(0x451)


def fold(v) -> str:
    """Lowercase, drop the yo, strip quotes, collapse whitespace.

    Accepts anything: None and a float NaN both fold to "" so callers need no
    null check of their own.
    """
    if v is None:
        return ""
    if isinstance(v, float) and v != v:      # NaN, without importing pandas
        return ""
    s = str(v).lower().replace(_YO, "е")
    return " ".join(_QUOTE_RE.sub(" ", s).split())


def words(s: str) -> list[str]:
    """Alphanumeric tokens, hyphens kept (`3-я`, `Красное&Белое` loses the &)."""
    return re.sub(r"[^0-9a-zа-я\- ]+", " ", s).split()


def stem(token: str) -> str:
    """Trim one inflectional ending, never cutting the token below four chars."""
    if len(token) <= MIN_STEM or token.isdigit():
        return token
    for e in ENDINGS:
        if token.endswith(e) and len(token) - len(e) >= MIN_STEM:
            return token[: -len(e)]
    return token


def stem_all(text: str) -> str:
    """Every token of a folded string stemmed, order preserved."""
    return " ".join(stem(t) for t in text.split())
