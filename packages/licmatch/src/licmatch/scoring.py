"""The pair score, as one readable function and as the matrix that vectorises it.

A candidate pair (object, register row) is scored

    score = w_addr * address + w_name * name + w_dist * (1 - d / max_m)

with a hard cut at ``d <= max_m``.  Two routes admit a pair:

* the **geo route** -- both sides carry a coordinate and lie within ``max_m``;
* the **address route** -- the register row carries no usable coordinate, so the
  distance term is *dropped* rather than scored as a zero, the two remaining
  terms are renormalised, and they must clear a deliberately higher bar on their
  own (``addr_route_street`` / ``addr_route_house``).

Everything else is refused: `score` is NaN for a pair neither route admits.

`pair_score()` is the definition; `score_matrix()` is the same arithmetic over
every pair at once, and `tests/test_scoring.py` checks the two agree.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from .geo import haversine_m
from .toponym import (ADDR_HOUSE_W, ADDR_STREET_W, SETTLEMENT_CONFLICT,
                      SETTLEMENT_ONE_SIDED, STREET_SET_W, STREET_SORT_W,
                      TYPE_CONFLICT, Toponym, address_score, house_similarity,
                      street_similarity)

ROUTE_NONE, ROUTE_GEO, ROUTE_ADDR = -1, 0, 1
ROUTE_NAMES = {ROUTE_GEO: "geo", ROUTE_ADDR: "address"}

SIDE_COLUMNS = ("settlement", "street_type", "street", "house", "suffix",
                "name_key", "latitude", "longitude")


@dataclass(frozen=True)
class MatchParams:
    """Every number the join can be argued about, in one place.

    The defaults are the calibrated ones (see `docs/METHODOLOGY.md`, §5); a
    caller changes them with `replace()` or by passing keywords, and any run
    that does must say so beside its numbers.
    """
    w_addr: float = 0.50
    w_name: float = 0.20
    w_dist: float = 0.30
    max_m: float = 100.0
    # The floor on the combined score: below it a best match is a register row
    # further than ~80 m away whose name says nothing, which is not evidence.
    accept: float = 0.45
    # The floor on the address term alone, and the reason the join does not rest
    # on the combined score by itself.  Inside max_m the neighbouring building is
    # a candidate too: same street, different house number, addr = 0.60, and at
    # 30 m with any name resemblance that clears any score floor low enough to
    # keep the true matches whose coordinates are poor.  A register converting
    # degrees-minutes-seconds carries ~31 m of latitude per arcsecond of
    # rounding, so distance cannot arbitrate between neighbours -- the house
    # number can.  0.72 is the score of "same street, house number written on one
    # side only"; an explicit house mismatch scores 0.60 and is refused.
    # Set to 0.0 for the unguarded weighted sum.
    addr_min: float = 0.72
    # The address-only route's own bars, on the two terms that survive there.
    addr_route_street: float = 0.90
    addr_route_house: float = 0.85
    # Reported separately: the tier that needs no argument.
    strong: float = 0.75

    def __post_init__(self) -> None:
        if min(self.w_addr, self.w_name, self.w_dist) < 0:
            raise ValueError("weights must be non-negative")
        if self.w_addr + self.w_name <= 0:
            raise ValueError("the address-only route needs w_addr + w_name > 0")
        if self.max_m <= 0:
            raise ValueError("max_m must be positive")

    @property
    def weights(self) -> tuple[float, float, float]:
        return self.w_addr, self.w_name, self.w_dist

    def with_weights(self, w_addr, w_name, w_dist) -> "MatchParams":
        return replace(self, w_addr=w_addr, w_name=w_name, w_dist=w_dist)


DEFAULTS = MatchParams()


def side(toponyms: Iterable[Toponym], names: Iterable[str],
         latitude, longitude) -> pd.DataFrame:
    """One side of the join in the canonical schema the scorer reads.

    This is the whole interface between a source and this package: whatever a
    source's column names, dialect or file format, an adapter parses it into
    toponyms and names and hands the result here.  Nothing downstream can tell
    the two sides apart.
    """
    top = list(toponyms)
    out = pd.DataFrame({
        "settlement": [t.settlement for t in top],
        "street_type": [t.street_type for t in top],
        "street": [t.street for t in top],
        "house": [t.house for t in top],
        "suffix": [t.suffix for t in top],
        "name_key": list(names),
        "latitude": pd.to_numeric(pd.Series(list(latitude)), errors="coerce").to_numpy(),
        "longitude": pd.to_numeric(pd.Series(list(longitude)), errors="coerce").to_numpy(),
    })
    if len(out) != len(top):
        raise ValueError("toponyms, names and coordinates must be the same length")
    return out


def pair_score(a: Toponym, b: Toponym, name_a: str, name_b: str,
               distance_m: float | None, params: MatchParams = DEFAULTS) -> float:
    """The published formula for one pair; `score_matrix()` vectorises exactly this.

    `distance_m is None` takes the address route: the distance term is dropped
    and the two remaining weights are renormalised.  Admission (both floors, and
    the address route's own bars) is `accept()`'s business, not this function's.
    """
    adr = address_score(a, b)
    nam = fuzz.WRatio(name_a, name_b) / 100.0 if (name_a and name_b) else 0.0
    if distance_m is None:
        return (params.w_addr * adr + params.w_name * nam) / (params.w_addr + params.w_name)
    return (params.w_addr * adr + params.w_name * nam
            + params.w_dist * max(0.0, 1.0 - float(distance_m) / params.max_m))


# --------------------------------------------------------------------------
# the vectorised form
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Scores:
    """Dense (n_a x n_b) float32 matrices, one per term of the formula.

    Subscriptable, so a caller may read it either as `s.score` or as
    `s["score"]`.  `score` is NaN wherever neither route admits the pair.
    """
    score: np.ndarray
    addr: np.ndarray
    name: np.ndarray
    street: np.ndarray
    house: np.ndarray
    distance: np.ndarray
    method: np.ndarray            # ROUTE_GEO / ROUTE_ADDR / ROUTE_NONE

    def __getitem__(self, key: str) -> np.ndarray:
        try:
            return getattr(self, key)
        except AttributeError as exc:              # pragma: no cover - typo guard
            raise KeyError(key) from exc

    def as_dict(self) -> Mapping[str, np.ndarray]:
        return {f: getattr(self, f) for f in
                ("score", "addr", "name", "street", "house", "distance", "method")}

    @property
    def shape(self) -> tuple[int, int]:
        return self.score.shape


def _sim_matrix(left: pd.Series, right: pd.Series, scorer):
    """(matrix over the distinct strings, left codes, right codes).

    The pairs number millions and the distinct strings a few hundred, so every
    comparison is done once and then gathered.
    """
    lu, li = np.unique(left.to_numpy(dtype=object), return_inverse=True)
    ru, ri = np.unique(right.to_numpy(dtype=object), return_inverse=True)
    m = process.cdist(list(lu), list(ru), scorer=scorer, workers=-1)
    return np.asarray(m, dtype=np.float32) / 100.0, li, ri


def _codes(left: pd.Series, right: pd.Series):
    """Shared integer coding of two categorical columns; "" gets code -1."""
    vals = pd.Index(pd.unique(pd.concat([left, right], ignore_index=True)))
    lc = vals.get_indexer(pd.Index(left)).astype(np.int32)
    rc = vals.get_indexer(pd.Index(right)).astype(np.int32)
    empty = vals.get_indexer(pd.Index([""]))[0]
    if empty >= 0:
        lc = np.where(lc == empty, -1, lc)
        rc = np.where(rc == empty, -1, rc)
    return lc, rc


def score_matrix(a: pd.DataFrame, b: pd.DataFrame,
                 params: MatchParams = DEFAULTS) -> Scores:
    """Every (a x b) pair scored, as dense float32 matrices.

    Dense on purpose: a city-sized join is a few million pairs, which keeps the
    code the same shape as the formula it implements.  Blocking would buy speed
    at the cost of the one property that makes the result auditable -- that no
    candidate was ever silently withheld from the scorer.
    """
    w_addr, w_name, w_dist = params.weights
    max_m = params.max_m

    sort_m, li, ri = _sim_matrix(a["street"], b["street"], fuzz.token_sort_ratio)
    set_m, _, _ = _sim_matrix(a["street"], b["street"], fuzz.token_set_ratio)
    street = STREET_SORT_W * sort_m[li][:, ri] + STREET_SET_W * set_m[li][:, ri]
    street[a["street"].to_numpy() == "", :] = 0.0
    street[:, b["street"].to_numpy() == ""] = 0.0

    ta, tb = _codes(a["street_type"], b["street_type"])
    street *= np.where((ta[:, None] >= 0) & (tb[None, :] >= 0)
                       & (ta[:, None] != tb[None, :]), TYPE_CONFLICT, 1.0).astype(np.float32)

    hn_a = pd.to_numeric(a["house"], errors="coerce").to_numpy(dtype=np.float64)
    hn_b = pd.to_numeric(b["house"], errors="coerce").to_numpy(dtype=np.float64)
    sa, sb = _codes(a["suffix"], b["suffix"])
    miss_a, miss_b = np.isnan(hn_a)[:, None], np.isnan(hn_b)[None, :]
    same_num = hn_a[:, None] == hn_b[None, :]
    same_suf = sa[:, None] == sb[None, :]
    one_suf = (sa[:, None] < 0) ^ (sb[None, :] < 0)
    house = np.where(
        miss_a & miss_b, 0.5,
        np.where(miss_a | miss_b, 0.3,
                 np.where(~same_num, 0.0,
                          np.where(same_suf, 1.0, np.where(one_suf, 0.85, 0.6))))
    ).astype(np.float32)

    addr = ADDR_STREET_W * street + ADDR_HOUSE_W * house
    ga, gb = _codes(a["settlement"], b["settlement"])
    addr *= np.where((ga[:, None] >= 0) & (gb[None, :] >= 0) & (ga[:, None] != gb[None, :]),
                     SETTLEMENT_CONFLICT,
                     np.where((ga[:, None] >= 0) ^ (gb[None, :] >= 0),
                              SETTLEMENT_ONE_SIDED, 1.0)).astype(np.float32)

    name_m, ni, nj = _sim_matrix(a["name_key"], b["name_key"], fuzz.WRatio)
    name = name_m[ni][:, nj]
    name[a["name_key"].to_numpy() == "", :] = 0.0
    name[:, b["name_key"].to_numpy() == ""] = 0.0

    dist = haversine_m(
        np.asarray(a["latitude"], dtype=float)[:, None],
        np.asarray(a["longitude"], dtype=float)[:, None],
        np.asarray(b["latitude"], dtype=float)[None, :],
        np.asarray(b["longitude"], dtype=float)[None, :],
    ).astype(np.float32)
    near = dist <= max_m
    dscore = np.where(near, 1.0 - dist / max_m, 0.0).astype(np.float32)

    total = w_addr * addr + w_name * name + w_dist * dscore
    # The address-only route: no coordinate exists, so the distance term is
    # dropped rather than scored as a zero, and the two remaining terms must
    # clear a higher bar on their own.
    no_coord = np.isnan(dist)
    addr_route = (no_coord & (street >= params.addr_route_street)
                  & (house >= params.addr_route_house))
    total = np.where(addr_route, (w_addr * addr + w_name * name) / (w_addr + w_name), total)
    total = np.where(near | addr_route, total, np.nan).astype(np.float32)

    return Scores(
        score=total, addr=addr, name=name, street=street, house=house,
        distance=np.where(near, dist, np.nan).astype(np.float32),
        method=np.where(near, ROUTE_GEO,
                        np.where(addr_route, ROUTE_ADDR, ROUTE_NONE)).astype(np.int8),
    )


def accepted(scores: Scores, params: MatchParams = DEFAULTS) -> np.ndarray:
    """The boolean (a x b) mask of pairs clearing **both** floors."""
    return ((np.nan_to_num(scores.score, nan=-1.0) >= params.accept)
            & (scores.addr >= params.addr_min))


__all__ = ["MatchParams", "DEFAULTS", "Scores", "ROUTE_GEO", "ROUTE_ADDR",
           "ROUTE_NONE", "ROUTE_NAMES", "SIDE_COLUMNS", "side", "pair_score",
           "score_matrix", "accepted", "street_similarity", "house_similarity",
           "address_score"]
