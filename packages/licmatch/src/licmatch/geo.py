"""Great-circle distance, vectorised.

Kept here rather than imported from the host project so the package has no
dependency on it: `licmatch` must be liftable out of this repository as it
stands.  The formula is the one `arkhinfra.v3_common.haversine_m()` uses, and
the two are checked against each other in `tests/test_geo.py`.
"""
from __future__ import annotations

import numpy as np

EARTH_R_M = 6371000.0


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres, broadcasting over numpy arrays."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * np.arcsin(np.sqrt(a))
