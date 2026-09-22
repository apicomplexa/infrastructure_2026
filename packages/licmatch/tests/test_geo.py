"""The distance term's floor: metres, and the rounding the register introduces."""
from __future__ import annotations

import unittest

import numpy as np

from licmatch import haversine_m


class TestHaversine(unittest.TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(haversine_m(64.54, 40.53, 64.54, 40.53), 0.0, places=6)

    def test_one_arcsecond_of_latitude(self):
        # Why the address floor exists: a register converting degrees-minutes-
        # seconds is already ~31 m out on one arcsecond of rounding, which is
        # less than the width of a building plot.
        d = haversine_m(64.54, 40.53, 64.54 + 1 / 3600, 40.53)
        self.assertTrue(30.0 < d < 32.0, d)

    def test_broadcasts(self):
        a = np.array([64.54, 64.55])[:, None]
        b = np.array([64.54, 64.56, 64.58])[None, :]
        d = haversine_m(a, np.full_like(a, 40.53), b, np.full_like(b, 40.53))
        self.assertEqual(d.shape, (2, 3))

    def test_nan_propagates(self):
        # A register row without a coordinate must fall out of the geo route
        # rather than land at distance zero.
        self.assertTrue(np.isnan(haversine_m(64.54, 40.53, np.nan, np.nan)))


if __name__ == "__main__":
    unittest.main()
