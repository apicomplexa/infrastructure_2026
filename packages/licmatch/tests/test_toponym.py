"""The parser and the address term, on the pairs the two sources actually write."""
from __future__ import annotations

import unittest

from licmatch import (Toponym, address_score, home_city_re, house_parts,
                      parse_address_fields, parse_address_line, stem,
                      street_similarity, street_toponym)

CITY = home_city_re("Архангельск")


def line(v: str) -> Toponym:
    return parse_address_line(v, CITY)


def fields(street: str, house: str, settlement: str = "", block: str = "") -> Toponym:
    return parse_address_fields(street, house, CITY, settlement, block)


class TestStemming(unittest.TestCase):
    def test_one_ending_trimmed(self):
        self.assertEqual(stem("северной"), "северн")
        self.assertEqual(stem("воскресенская"), "воскресенск")

    def test_never_below_four_characters(self):
        # "тимме" loses its ending down to four characters and stops there;
        # "мира" is already at the floor and is left whole.
        self.assertEqual(stem("тимме"), "тимм")
        self.assertEqual(stem("мира"), "мира")
        self.assertEqual(stem("ул"), "ул")

    def test_digits_untouched(self):
        self.assertEqual(stem("2026"), "2026")


class TestStreetToponym(unittest.TestCase):
    def test_type_word_in_either_position(self):
        self.assertEqual(street_toponym("Троицкий пр-кт")[0], "пр")
        self.assertEqual(street_toponym("проспект Ломоносова")[0], "пр")
        self.assertEqual(street_toponym("Северной Двины Набережная")[0], "наб")

    def test_initials_dropped(self):
        self.assertEqual(street_toponym("Тимме Я. Улица"), ("ул", "тимм"))
        self.assertEqual(street_toponym("улица Тимме"), ("ул", "тимм"))

    def test_line_is_not_a_street_type(self):
        # "линия" belongs to the name: one source writes "3-я линия ул", the
        # other "3-я линия".  Folding it as a type would strip it on one side.
        self.assertIn("лини", street_toponym("3-я линия ул")[1])
        self.assertIn("лини", street_toponym("3-я линия")[1])


class TestHouseParts(unittest.TestCase):
    def test_block_spellings(self):
        self.assertEqual(house_parts("356 к4"), ("356", "4"))
        self.assertEqual(house_parts("45/3"), ("45", "3"))
        self.assertEqual(house_parts("13 с1"), ("13", "1"))
        self.assertEqual(house_parts("2", "5"), ("2", "5"))

    def test_house_letter_joins_the_suffix(self):
        self.assertEqual(house_parts("12а"), ("12", "а"))

    def test_trailing_word_is_not_a_block(self):
        # "49 киоск": the "к" of киоск must not read as корпус.
        self.assertEqual(house_parts("49 киоск"), ("49", ""))


class TestParsedLines(unittest.TestCase):
    def test_city_is_dropped_in_every_spelling(self):
        for v in ("Архангельск, улица Тимме, 2 к5",
                  "г Архангельск, улица Тимме, 2 к5",
                  "городской округ Архангельск, улица Тимме, 2 к5"):
            self.assertEqual(line(v).settlement, "", v)

    def test_settlement_kept(self):
        self.assertEqual(line("Лесная речка, Лахтинское шоссе, 17").settlement,
                         "лесн речк")

    def test_street_found_by_type_not_by_position(self):
        t = line("Лесная речка, Лахтинское шоссе, 17")
        self.assertEqual((t.street_type, t.house), ("ш", "17"))

    def test_line_without_any_type_word(self):
        t = line("Архангельск, Тимме Я., 29")
        self.assertEqual((t.street, t.house), ("тимм", "29"))

    def test_house_and_block_in_separate_slots(self):
        self.assertEqual(line("Архангельск, Ленинградский проспект, 356, 4").house, "356")


class TestCrossSourcePairs(unittest.TestCase):
    """The four pairs docs/METHODOLOGY.md quotes as the reason for the parser."""

    PAIRS = [
        ("Архангельск, набережная Северной Двины, 55", ("Северной Двины Набережная", "55", "", "")),
        ("Архангельск, улица Тимме, 2 к5", ("Тимме Я. Улица", "2", "", "5")),
        ("Архангельск, Ленинградский проспект, 356 к4", ("Ленинградский пр-кт", "356", "", "4")),
        ("Лесная речка, Лахтинское шоссе, 17", ("Лахтинское ш", "17", "Лесная речка", "")),
    ]

    def test_each_pair_clears_the_address_floor(self):
        for left, right in self.PAIRS:
            a, b = line(left), fields(right[0], right[1], right[2], right[3])
            with self.subTest(left=left):
                self.assertGreaterEqual(address_score(a, b), 0.72)

    def test_same_door_scores_one(self):
        a = line("Архангельск, набережная Северной Двины, 55")
        b = fields("Северной Двины Набережная", "55")
        self.assertAlmostEqual(address_score(a, b), 1.0, places=6)


class TestAddressFloorSeparatesNeighbours(unittest.TestCase):
    def test_neighbouring_house_is_refused(self):
        a = line("Архангельск, улица Тимме, 2")
        b = fields("Тимме Я. Улица", "4")
        self.assertAlmostEqual(address_score(a, b), 0.60, places=6)
        self.assertLess(address_score(a, b), 0.72)

    def test_house_written_on_one_side_only_is_admitted(self):
        a = line("Архангельск, улица Тимме, 2")
        b = fields("Тимме Я. Улица", "")
        self.assertAlmostEqual(address_score(a, b), 0.72, places=6)

    def test_street_type_conflict_penalised(self):
        same = address_score(line("Архангельск, улица Победы, 10"),
                             fields("Победы ул", "10"))
        clash = address_score(line("Архангельск, улица Победы, 10"),
                              fields("Победы пр-кт", "10"))
        self.assertLess(clash, same)

    def test_settlement_conflict_penalised(self):
        same_street = fields("Лахтинское ш", "17", "Талаги")
        self.assertLess(address_score(line("Лесная речка, Лахтинское шоссе, 17"),
                                      same_street), 0.72)


class TestStreetSimilarity(unittest.TestCase):
    def test_subset_is_not_a_full_match(self):
        s = street_similarity("побед", "40 лет велик побед")
        self.assertLess(s, 1.0)
        self.assertGreater(s, 0.4)

    def test_empty_side_scores_zero(self):
        self.assertEqual(street_similarity("", "побед"), 0.0)


if __name__ == "__main__":
    unittest.main()
