"""Tests for immutable typed profile-domain models."""

from __future__ import annotations

import unittest

from freecad.SteelStructures.profiles import ProfileRef, convert_to_canonical


class ProfileRefTests(unittest.TestCase):
    def test_structural_equality_hash_and_distinct_ids(self):
        first = ProfileRef("catalog-a", "w-150x13.0")
        same = ProfileRef("catalog-a", "w-150x13.0")
        other_catalog = ProfileRef("catalog-b", "w-150x13.0")
        other_profile = ProfileRef("catalog-a", "w-150x18.0")
        self.assertEqual(first, same)
        self.assertEqual(hash(first), hash(same))
        self.assertNotEqual(first, other_catalog)
        self.assertNotEqual(first, other_profile)
        self.assertIn("catalog-a", repr(first))
        self.assertIn("w-150x13.0", repr(first))

    def test_unit_conversions_use_canonical_mm_based_units(self):
        cases = (
            (16.6, "area", "cm2", 1660.0),
            (148, "length", "mm", 148.0),
            (13, "mass_per_length", "kg/m", 13.0),
            (2, "section_modulus", "cm3", 2000.0),
            (2, "second_moment_of_area", "cm4", 20000.0),
            (2, "warping_constant", "cm6", 2000000.0),
            (2.6, "radius_of_gyration", "cm", 26.0),
            (1.27, "surface_area_per_length", "m2/m", 1.27),
            (10.2, "dimensionless", "1", 10.2),
        )
        for value, quantity, unit, expected in cases:
            with self.subTest(quantity=quantity, unit=unit):
                self.assertEqual(convert_to_canonical(value, quantity, unit), expected)
