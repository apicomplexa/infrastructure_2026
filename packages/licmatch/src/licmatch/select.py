"""From a scored matrix to one chosen counterpart per object, and to counts.

Two decisions live here, and they are separate on purpose:

* **Admission** -- which pairs clear the floors.  Every admitted register row
  counts toward the per-object tallies, because "how many licences sit at this
  address" is a different question from "which one do we quote".
* **Choice** -- which single admitted row is copied out.  A preferred row (in
  practice: a licence in force) beats every non-preferred one whatever their
  scores, so a per-object status can never read "archived" while a live row sits
  at the same address.

Tallies are over **distinct keys**, not over matrix rows: a register that files
one licence once per status change would otherwise count it several times.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

from .scoring import DEFAULTS, ROUTE_NAMES, MatchParams, Scores, accepted

# How far a preferred counterpart is lifted above a non-preferred one.  Any
# value above the score range (0..1) has the same effect; 2.0 keeps the lifted
# values readable in a debugger.
PREFER_LIFT = 2.0


@dataclass(frozen=True)
class Selection:
    """One row per object: the chosen counterpart, its terms, and the tallies."""
    accepted: np.ndarray                      # (n_a x n_b) bool
    pick: np.ndarray                          # (n_a,) column index into side b
    hit: np.ndarray                           # (n_a,) whether anything was admitted
    score: np.ndarray                         # gathered terms, NaN where no hit
    addr: np.ndarray
    name: np.ndarray
    distance: np.ndarray
    house: np.ndarray
    method: np.ndarray                        # "geo" / "address" / "" as objects
    counts: Mapping[str, np.ndarray] = field(default_factory=dict)
    keys: Mapping[str, list[set]] = field(default_factory=dict)

    def joined(self, group: str, sep: str = "; ") -> list[str]:
        """The distinct keys of one group per object, sorted and joined."""
        return [sep.join(sorted(s)) for s in self.keys[group]]

    def take(self, values: Sequence, empty="") -> np.ndarray:
        """Gather a side-b column onto the objects, `empty` where there is no hit."""
        vals = np.asarray(values, dtype=object)
        return np.where(self.hit, vals[self.pick], empty)


def _gather(matrix: np.ndarray, rows: np.ndarray, pick: np.ndarray,
            hit: np.ndarray) -> np.ndarray:
    return np.where(hit, matrix[rows, pick], np.nan)


def select(scores: Scores, params: MatchParams = DEFAULTS, *,
           prefer: np.ndarray | None = None,
           keys: Sequence | None = None,
           groups: Mapping[str, np.ndarray | None] | None = None) -> Selection:
    """Choose one counterpart per object and tally the admitted ones.

    ``prefer``  boolean mask over side b: preferred rows outrank every
                non-preferred admitted row whatever their scores.
    ``keys``    side-b identifiers to count distinctly (a licence number, say).
    ``groups``  named boolean masks over side b; each yields a count column and
                a key set per object.  A mask of ``None`` means "every admitted
                row", which is how the plain match count is asked for.
    """
    ok = accepted(scores, params)
    n_a, n_b = ok.shape
    rows = np.arange(n_a)

    ranked = np.where(ok, np.nan_to_num(scores.score, nan=0.0), -1.0)
    if prefer is not None:
        prefer = np.asarray(prefer, dtype=bool)
        if prefer.shape != (n_b,):
            raise ValueError(f"prefer must have shape ({n_b},), got {prefer.shape}")
        ranked = np.where(ok & prefer[None, :], ranked + PREFER_LIFT, ranked)
    pick = np.argmax(ranked, axis=1) if n_b else np.zeros(n_a, dtype=int)
    hit = ok[rows, pick] if n_b else np.zeros(n_a, dtype=bool)

    counts: dict[str, np.ndarray] = {}
    key_sets: dict[str, list[set]] = {}
    if groups:
        if keys is None:
            raise ValueError("groups need keys to count distinctly")
        key_arr = np.asarray(keys, dtype=object)
        for gname, mask in groups.items():
            m = ok if mask is None else (ok & np.asarray(mask, dtype=bool)[None, :])
            sets = [set(key_arr[np.flatnonzero(r)]) for r in m]
            key_sets[gname] = sets
            counts[gname] = np.array([len(s) for s in sets], dtype=int)

    methods = np.array(["", ROUTE_NAMES[0], ROUTE_NAMES[1]], dtype=object)
    return Selection(
        accepted=ok, pick=pick, hit=hit,
        score=_gather(scores.score, rows, pick, hit),
        addr=_gather(scores.addr, rows, pick, hit),
        name=_gather(scores.name, rows, pick, hit),
        distance=_gather(scores.distance, rows, pick, hit),
        house=_gather(scores.house, rows, pick, hit),
        method=np.where(hit, methods[scores.method[rows, pick] + 1], ""),
        counts=counts, keys=key_sets,
    )


def claimed_keys(selection: Selection, group: str) -> set:
    """Every side-b key any object claimed in one group -- the reverse direction.

    "Which register rows did the export account for" is the question a coverage
    check asks, and it is not the complement of the forward one: one row can be
    claimed by many objects and many rows by none.
    """
    out: set = set()
    for s in selection.keys[group]:
        out |= s
    return out
