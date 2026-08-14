"""Search normalization tests for typed profile catalogs."""

from __future__ import annotations

import unittest

from freecad.SteelStructures.paths import CATALOGS_DIR
from freecad.SteelStructures.profiles import ProfileLibrary


class ProfileSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = ProfileLibrary(CATALOGS_DIR)

    def test_w310_variants_return_all_w310_profiles(self):
        for query in ("W310", "w310", "W 310"):
            with self.subTest(query=query):
                result = self.library.search(query)
                self.assertEqual(len(result), 18)
                self.assertTrue(all("W 310" in item.designation for item in result))

    def test_mass_fragment_and_compact_designations_find_w310x52(self):
        for query in ("52", "W310X52", "W310x52,0", "W310x52.0", "W 310 X 52.0"):
            with self.subTest(query=query):
                self.assertIn("W 310 x 52,0", [item.designation for item in self.library.search(query)])

    def test_missing_text_returns_empty_result(self):
        self.assertEqual(self.library.search("not-a-profile"), ())

    def test_w_and_hp_metric_and_imperial_aliases(self):
        cases = {
            "W610x217": "W 610 x 217,0",
            "W24x146": "W 610 x 217,0",
            "HP310x132": "HP 310 x 132,0",
            "HP12x89": "HP 310 x 132,0",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertIn(expected, [item.designation for item in self.library.search(query)])
