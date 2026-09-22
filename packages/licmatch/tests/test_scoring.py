"""The matrix must compute exactly what the one-pair formula says it does.

`pair_score()` is the published definition; `score_matrix()` is an optimisation
of it.  An optimisation that quietly disagrees with its definition is the whole
class of defect this test exists to catch, so the two are compared on every pair
of a small fixture rather than on a hand-picked one.
"""
from __future__ import annotations

import unittest

import numpy as np

from licmatch import (DEFAULTS, ROUTE_ADDR, ROUTE_GEO, ROUTE_NONE, MatchParams,
                      accepted, fascia_name, holder_name, home_city_re,
                      pair_score, parse_address_fields, parse_address_line,
                      score_matrix, side)

CITY = home_city_re("Архангельск")

# Four objects and four register rows, written the way each source writes them.
OBJECTS = [
    ("Пятёрочка, супермаркет", "Архангельск, улица Тимме, 2 к5", 64.5490, 40.5310),
    ("Магнит", "Архангельск, набережная Северной Двины, 55", 64.5350, 40.5170),
    ("Бристоль", "Архангельск, Ленинградский проспект, 356 к4", 64.5100, 40.5600),
    ("Причал, магазин", "Лесная речка, Лахтинское шоссе, 17", 64.6200, 40.4400),
]
REGISTRY = [
    ('ООО "Агроторг"', "Тимме Я. Улица", "2", "", "5", 64.5491, 40.5311),
    ('АО "Тандер"', "Северной Двины Набережная", "55", "", "", 64.5351, 40.5169),
    ('ООО "Альбион-2002"', "Ленинградский пр-кт", "356", "", "4", np.nan, np.nan),
    ('ООО "ЛОЙ"', "Лахтинское ш", "17", "Лесная речка", "", np.nan, np.nan),
]


def build_sides(params: MatchParams = DEFAULTS):
    a = side([parse_address_line(v[1], CITY) for v in OBJECTS],
             [fascia_name(v[0]) for v in OBJECTS],
             [v[2] for v in OBJECTS], [v[3] for v in OBJECTS])
    b = side([parse_address_fields(r[1], r[2], CITY, r[3], r[4]) for r in REGISTRY],
             [holder_name(r[0]) for r in REGISTRY],
             [r[5] for r in REGISTRY], [r[6] for r in REGISTRY])
    return a, b


class TestMatrixMatchesFormula(unittest.TestCase):
    def setUp(self):
        self.a, self.b = build_sides()
        self.top_a = [parse_address_line(v[1], CITY) for v in OBJECTS]
        self.top_b = [parse_address_fields(r[1], r[2], CITY, r[3], r[4])
                      for r in REGISTRY]
        self.s = score_matrix(self.a, self.b, DEFAULTS)

    def test_every_admitted_pair_agrees_with_pair_score(self):
        for i in range(len(OBJECTS)):
            for j in range(len(REGISTRY)):
                if self.s.method[i, j] == ROUTE_NONE:
                    self.assertTrue(np.isnan(self.s.score[i, j]))
                    continue
                d = (None if self.s.method[i, j] == ROUTE_ADDR
                     else float(self.s.distance[i, j]))
                expected = pair_score(self.top_a[i], self.top_b[j],
                                      self.a["name_key"][i], self.b["name_key"][j],
                                      d, DEFAULTS)
                with self.subTest(i=i, j=j):
                    self.assertAlmostEqual(float(self.s.score[i, j]), expected, places=5)

    def test_address_term_agrees_with_address_score(self):
        from licmatch import address_score
        for i in range(len(OBJECTS)):
            for j in range(len(REGISTRY)):
                with self.subTest(i=i, j=j):
                    self.assertAlmostEqual(
                        float(self.s.addr[i, j]),
                        address_score(self.top_a[i], self.top_b[j]), places=5)


class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.a, self.b = build_sides()
        self.s = score_matrix(self.a, self.b, DEFAULTS)

    def test_true_pairs_are_on_the_diagonal(self):
        ok = accepted(self.s, DEFAULTS)
        for i in range(4):
            self.assertTrue(ok[i, i], f"pair {i} refused")

    def test_coordinate_rows_take_the_geo_route(self):
        self.assertEqual(self.s.method[0, 0], ROUTE_GEO)
        self.assertEqual(self.s.method[1, 1], ROUTE_GEO)

    def test_coordinateless_rows_take_the_address_route(self):
        self.assertEqual(self.s.method[2, 2], ROUTE_ADDR)
        self.assertEqual(self.s.method[3, 3], ROUTE_ADDR)
        self.assertTrue(np.isnan(self.s.distance[2, 2]))

    def test_distance_term_dropped_not_zeroed_on_the_address_route(self):
        # Scored as a zero, a perfect address+name pair would reach only 0.70
        # and the 0.75 "strong" tier would be unreachable without coordinates.
        self.assertGreater(float(self.s.score[3, 3]), 0.75)

    def test_far_away_pair_is_refused(self):
        far = np.isnan(self.s.score)
        self.assertTrue(far[0, 1] or not accepted(self.s, DEFAULTS)[0, 1])


class TestFloors(unittest.TestCase):
    def test_address_floor_refuses_the_neighbouring_building(self):
        # Same street, 8 m away, a different house number: the combined score
        # clears `accept`, and only the address floor stops it.
        a = side([parse_address_line("Архангельск, улица Тимме, 2", CITY)],
                 ["пятерочка"], [64.5490], [40.5310])
        b = side([parse_address_fields("Тимме Я. Улица", "4", CITY)],
                 ["пятерочка"], [64.5491], [40.5310])
        s = score_matrix(a, b, DEFAULTS)
        self.assertGreaterEqual(float(s.score[0, 0]), DEFAULTS.accept)
        self.assertFalse(bool(accepted(s, DEFAULTS)[0, 0]))
        unguarded = MatchParams(addr_min=0.0)
        self.assertTrue(bool(accepted(s, unguarded)[0, 0]))

    def test_params_reject_impossible_settings(self):
        with self.assertRaises(ValueError):
            MatchParams(w_addr=-1)
        with self.assertRaises(ValueError):
            MatchParams(max_m=0)
        with self.assertRaises(ValueError):
            MatchParams(w_addr=0, w_name=0)


class TestNameTerm(unittest.TestCase):
    def test_alias_bridges_holder_and_fascia(self):
        self.assertEqual(holder_name('АО "Тандер"'), "магнит")
        self.assertEqual(fascia_name("Магнит, супермаркет"), "магнит")

    def test_legal_boilerplate_dropped(self):
        self.assertEqual(
            holder_name('Общество с ограниченной ответственностью «ЛОЙ» '
                        'Сокращенно: ООО "ЛОЙ"'), "лой")

    def test_unknown_name_scores_but_does_not_decide(self):
        # An object whose name says nothing still matches on address alone:
        # the name weight is 0.20, the address floor does the work.
        a = side([parse_address_line("Архангельск, улица Тимме, 2 к5", CITY)],
                 [""], [64.5490], [40.5310])
        b = side([parse_address_fields("Тимме Я. Улица", "2", CITY, "", "5")],
                 ["агроторг"], [64.5491], [40.5311])
        s = score_matrix(a, b, DEFAULTS)
        self.assertEqual(float(s.name[0, 0]), 0.0)
        self.assertTrue(bool(accepted(s, DEFAULTS)[0, 0]))


if __name__ == "__main__":
    unittest.main()
