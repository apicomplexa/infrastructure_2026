"""Trade names on one side, licence holders on the other, reduced to one key.

A register names the licence *holder*, a directory export names the *shop*.  For
the chains that carry most of a city's licences the two never resemble each
other -- АО "Тандер" is Магнит on the street -- and no fuzzy metric can bridge
that, so the handful that matter are mapped explicitly and everything else is
stripped of legal and trade boilerplate and compared as it stands.

This is why the name term carries the smallest weight of the three in
`scoring`: it is a tie-breaker between licences at one address, never the
evidence that the address is right.
"""
from __future__ import annotations

import re

from .text import fold

# Only unambiguous, publicly known operator -> fascia pairs belong here.
# Anything uncertain is left out and simply scores low on the name term.
# Keys are written hyphenless, which is how `name_key()` looks them up, so
# "Альбион-2002" and "Альбион 2002" reach the same fascia.
RU_RETAIL_ALIASES = {
    "тандер": "магнит",
    "агроторг": "пятерочка",
    "альбион 2002": "бристоль",
    "альфа м": "красное&белое",
    "винлаб запад": "винлаб",
    "винлаб северо запад": "винлаб",
    "новабев архангельск": "винлаб",
    "бэст прайс": "fix price",
    "торгсервис 29": "светофор",
}

# Words a directory appends to a fascia ("Пятёрочка, супермаркет") and legal
# boilerplate a register prepends.  Both are noise on the name term.
TRADE_AND_LEGAL_NOISE = frozenset({
    "магазин", "супермаркет", "гипермаркет", "минимаркет", "маркет", "киоск",
    "павильон", "кафе", "бар", "ресторан", "паб", "столовая", "кулинария",
    "пекарня", "кофейня", "продуктовый", "торговая", "торговый", "компания",
    "фирма", "сеть", "отдел", "точка", "продажи", "розничные", "сервисный",
    "центр", "дом", "ооо", "оао", "зао", "ао", "ип", "пао", "тс", "тд", "по",
    "общество", "ограниченной", "ответственностью", "акционерное",
    "закрытое", "открытое", "публичное", "потребительское",
})

# Russian charters carry the full name and then repeat it short:
# 'Общество с ограниченной ответственностью «ЛОЙ» Сокращенно: ООО "ЛОЙ"'.
SHORT_NAME_MARKER = "сокращенно:"


def name_key(text: str, *, aliases=RU_RETAIL_ALIASES,
             noise=TRADE_AND_LEGAL_NOISE) -> str:
    """A folded name reduced to its distinctive part, alias applied."""
    s = re.sub(r"[^0-9a-zа-я&\- ]+", " ", text)
    toks = [t for t in s.split() if t not in noise and len(t) > 1]
    out = " ".join(toks).strip()
    return aliases.get(out.replace("-", " "), out)


def holder_name(v, *, aliases=RU_RETAIL_ALIASES,
                noise=TRADE_AND_LEGAL_NOISE) -> str:
    """A register's holder name reduced to its distinctive part.

    'Общество с ограниченной ответственностью «ЛОЙ» Сокращенно: ООО "ЛОЙ"' -> "лой".
    """
    return name_key(fold(v).split(SHORT_NAME_MARKER)[-1], aliases=aliases, noise=noise)


def fascia_name(v, *, aliases=RU_RETAIL_ALIASES,
                noise=TRADE_AND_LEGAL_NOISE) -> str:
    """An export's fascia reduced the same way, trade descriptor removed."""
    return name_key(fold(v), aliases=aliases, noise=noise)
