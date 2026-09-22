"""Choice, preference and the distinct-key tallies."""
from __future__ import annotations

import unittest

import numpy as np

from licmatch import (DEFAULTS, claimed_keys, fascia_name, holder_name,
                      home_city_re, parse_address_fields, parse_address_line,
                      score_matrix, select, side)

CITY = home_city_re("Архангельск")

# One object; four register rows at its address.  Two of them are the same
# licence filed twice (one status change), one is a live licence with a poorer
# name, one sits in the next building.
OBJECT = ("Пятёрочка, супермаркет", "Архангельск, улица Тимме, 2 к5", 64.5490, 40.5310)
ROWS = [
    # holder, street, house, block, lat, lon, licence_no, in_force
    ('ООО "Агроторг"', "Тимме Я. Улица", "2", "5", 64.5491, 40.5311, "L-1", False),
    ('ООО "Агроторг"', "Тимме Я. Улица", "2", "5", 64.5491, 40.5311, "L-1", False),
    ('ООО "Квартал"', "Тимме Я. Улица", "2", "5", 64.5491, 40.5311, "L-2", True),
    ('ООО "Сосед"', "Тимме Я. Улица", "4", "", 64.5492, 40.5313, "L-3", True),
]


def build():
    a = side([parse_address_line(OBJECT[1], CITY)], [fascia_name(OBJECT[0])],
             [OBJECT[2]], [OBJECT[3]])
    b = side([parse_address_fields(r[1], r[2], CITY, "", r[3]) for r in ROWS],
             [holder_name(r[0]) for r in ROWS],
             [r[4] for r in ROWS], [r[5] for r in ROWS])
    return a, b


KEYS = [r[6] for r in ROWS]
ACTIVE = np.array([r[7] for r in ROWS], dtype=bool)


class TestSelection(unittest.TestCase):
    def setUp(self):
        a, b = build()
        self.s = score_matrix(a, b, DEFAULTS)
        self.sel = select(self.s, DEFAULTS, prefer=ACTIVE, keys=KEYS,
                          groups={"matched": None, "active": ACTIVE})

    def test_neighbour_is_not_admitted(self):
        self.assertFalse(bool(self.sel.accepted[0, 3]))

    def test_counts_are_over_distinct_keys(self):
        # Three admitted rows, two distinct licences.
        self.assertEqual(int(self.sel.accepted[0].sum()), 3)
        self.assertEqual(int(self.sel.counts["matched"][0]), 2)
        self.assertEqual(int(self.sel.counts["active"][0]), 1)

    def test_preferred_row_is_chosen_over_a_better_scoring_one(self):
        # The archived Агроторг row scores higher (the alias makes its name
        # match), yet the live licence must be the one reported.
        best_by_score = int(np.nanargmax(np.where(self.sel.accepted[0],
                                                  self.s.score[0], np.nan)))
        self.assertIn(best_by_score, (0, 1))
        self.assertEqual(int(self.sel.pick[0]), 2)
        self.assertTrue(bool(self.sel.hit[0]))

    def test_take_gathers_the_chosen_row(self):
        self.assertEqual(self.sel.take(KEYS)[0], "L-2")

    def test_joined_keys_are_sorted_and_deduplicated(self):
        self.assertEqual(self.sel.joined("matched")[0], "L-1; L-2")

    def test_claimed_keys_is_the_reverse_direction(self):
        self.assertEqual(claimed_keys(self.sel, "matched"), {"L-1", "L-2"})


class TestNoPreference(unittest.TestCase):
    def test_without_prefer_the_best_score_wins(self):
        a, b = build()
        s = score_matrix(a, b, DEFAULTS)
        sel = select(s, DEFAULTS, keys=KEYS, groups={"matched": None})
        self.assertIn(int(sel.pick[0]), (0, 1))

    def test_unmatched_object_reports_no_hit(self):
        a = side([parse_address_line("Архангельск, улица Нет Такой, 999", CITY)],
                 ["ничего"], [65.9], [41.9])
        _, b = build()
        sel = select(score_matrix(a, b, DEFAULTS), DEFAULTS, keys=KEYS,
                     groups={"matched": None})
        self.assertFalse(bool(sel.hit[0]))
        self.assertEqual(int(sel.counts["matched"][0]), 0)
        self.assertEqual(sel.take(KEYS)[0], "")
        self.assertTrue(np.isnan(sel.score[0]))
        self.assertEqual(sel.method[0], "")


class TestGuards(unittest.TestCase):
    def test_groups_without_keys_is_an_error(self):
        a, b = build()
        s = score_matrix(a, b, DEFAULTS)
        with self.assertRaises(ValueError):
            select(s, DEFAULTS, groups={"matched": None})

    def test_prefer_shape_is_checked(self):
        a, b = build()
        s = score_matrix(a, b, DEFAULTS)
        with self.assertRaises(ValueError):
            select(s, DEFAULTS, prefer=np.array([True]))


if __name__ == "__main__":
    unittest.main()
