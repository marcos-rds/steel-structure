"""Geometric frame regressions for parametric structural members."""

from __future__ import annotations

import math
import unittest

try:
    from test_member_placement import MemberObject, Placement, Quantity, Vector, load_member
except ModuleNotFoundError:
    from tests.test_member_placement import (
        MemberObject, Placement, Quantity, Vector, load_member,
    )


class MemberOrientationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.member = load_member()

    def proxy(self):
        proxy = self.member.StructuralMemberProxy.__new__(self.member.StructuralMemberProxy)
        proxy._updating = proxy._syncing_length = proxy._syncing_placement = False
        proxy._placement_from_points_pending = True
        proxy._last_placement = None
        proxy._last_section_rotation = 0.0
        proxy._last_valid_length = None
        return proxy

    def create(self, start, end, rotation=0.0, insertion="Centroide",
               element_type="Membro"):
        obj, proxy = MemberObject(start, end), self.proxy()
        obj.Rotation = Quantity(rotation)
        obj.Insertion = insertion
        obj.ElementType = element_type
        proxy.execute(obj)
        return obj, proxy

    def assertVector(self, actual, expected, places=6):
        for value, wanted in zip((actual.x, actual.y, actual.z), expected):
            self.assertAlmostEqual(value, wanted, places=places)

    def transformed(self, obj, vector):
        rotation = obj.Placement.Rotation.matrix
        values = (vector.x, vector.y, vector.z)
        return Vector(*(sum(rotation[i][j] * values[j] for j in range(3)) for i in range(3)))

    def assertFrame(self, obj, longitudinal, vertical):
        expected_longitudinal = Vector(longitudinal); expected_longitudinal.normalize()
        expected_vertical = Vector(vertical); expected_vertical.normalize()
        self.assertVector(self.transformed(obj, Vector(0, 0, 1)),
                          (expected_longitudinal.x, expected_longitudinal.y, expected_longitudinal.z))
        self.assertVector(self.transformed(obj, Vector(0, 1, 0)),
                          (expected_vertical.x, expected_vertical.y, expected_vertical.z))

    def test_horizontal_cardinal_and_required_diagonal_azimuths_keep_section_vertical(self):
        directions = ((10, 0, 0), (0, 10, 0), (-10, 0, 0), (0, -10, 0),
                      (10, 10, 0), (10 * math.cos(math.radians(30)), 5, 0),
                      (-10, 10, 0), (10, -10, 0))
        for direction in directions:
            with self.subTest(direction=direction):
                obj, _ = self.create((0, 0, 0), direction)
                self.assertFrame(obj, direction, (0, 0, 1))

    def test_every_azimuth_keeps_local_section_height_on_global_z(self):
        for degrees in range(0, 360, 15):
            direction = (math.cos(math.radians(degrees)),
                         math.sin(math.radians(degrees)), 0)
            with self.subTest(degrees=degrees):
                obj, _ = self.create((0, 0, 0), direction)
                self.assertFrame(obj, direction, (0, 0, 1))

    def test_global_z_translation_does_not_change_frame(self):
        first, _ = self.create((0, 0, 0), (10, 10, 0))
        moved, _ = self.create((0, 0, 37), (10, 10, 37))
        self.assertEqual(first.Placement.Rotation.matrix, moved.Placement.Rotation.matrix)

    def test_reversed_horizontal_member_has_no_arbitrary_roll(self):
        forward, _ = self.create((0, 0, 0), (10, 6, 0))
        reverse, _ = self.create((10, 6, 0), (0, 0, 0))
        self.assertVector(self.transformed(forward, Vector(0, 1, 0)), (0, 0, 1))
        self.assertVector(self.transformed(reverse, Vector(0, 1, 0)), (0, 0, 1))

    def test_rotation_90_on_diagonal_rotates_only_about_longitudinal_axis(self):
        obj, _ = self.create((0, 0, 0), (10, 10, 0), 90)
        expected = Vector(1, -1, 0); expected.normalize()
        self.assertVector(self.transformed(obj, Vector(0, 1, 0)),
                          (expected.x, expected.y, expected.z))

    def test_rotation_45_on_diagonal_is_relative_to_base_frame(self):
        obj, _ = self.create((0, 0, 0), (10, 10, 0), 45)
        actual = self.transformed(obj, Vector(0, 1, 0))
        self.assertAlmostEqual(actual.z, math.sqrt(0.5), places=6)
        self.assertAlmostEqual(actual.dot(Vector(1, 1, 0)), 0.0, places=6)

    def test_inclined_xz_uses_projected_global_up(self):
        direction = Vector(10, 0, 4); unit = Vector(direction); unit.normalize()
        vertical = Vector(0, 0, 1).sub(unit * unit.z); vertical.normalize()
        obj, _ = self.create((0, 0, 0), direction)
        self.assertFrame(obj, direction, vertical)

    def test_inclined_xyz_uses_projected_global_up(self):
        direction = Vector(10, 7, 4); unit = Vector(direction); unit.normalize()
        vertical = Vector(0, 0, 1).sub(unit * unit.z); vertical.normalize()
        obj, _ = self.create((0, 0, 0), direction)
        self.assertFrame(obj, direction, vertical)

    def test_vertical_column_preserves_approved_identity_frame_and_rotation(self):
        obj, _ = self.create((3, 4, 5), (3, 4, 3005), element_type="Pilar")
        self.assertFrame(obj, (0, 0, 1), (0, 1, 0))
        rolled, _ = self.create((3, 4, 5), (3, 4, 3005), 90)
        self.assertVector(self.transformed(rolled, Vector(0, 1, 0)), (-1, 0, 0))

    def test_nearly_vertical_uses_stable_legacy_fallback(self):
        obj, _ = self.create((0, 0, 0), (1e-9, 0, 10))
        self.assertVector(self.transformed(obj, Vector(0, 0, 1)), (1e-10, 0, 1))

    def test_all_insertion_points_and_offsets_follow_same_section_frame(self):
        for insertion in self.member.INSERTION_OPTIONS:
            with self.subTest(insertion=insertion):
                obj, _ = self.create((0, 0, 0), (10, 10, 0), insertion=insertion)
                self.assertFrame(obj, (10, 10, 0), (0, 0, 1))
                translation = obj.Shape.face_translation
                world_offset = self.transformed(obj, translation)
                self.assertAlmostEqual(world_offset.dot(Vector(1, 1, 0)), 0.0, places=6)
        obj, proxy = self.create((0, 0, 0), (10, 10, 0))
        obj.OffsetX = Quantity(7)
        obj.OffsetY = Quantity(11)
        proxy._placement_from_points_pending = True
        proxy.execute(obj)
        transverse = self.transformed(obj, Vector(1, 0, 0))
        vertical = self.transformed(obj, Vector(0, 1, 0))
        expected = transverse * 7
        expected = expected.add(vertical * 11)
        actual = self.transformed(obj, obj.Shape.face_translation)
        self.assertVector(actual, (expected.x, expected.y, expected.z))

    def test_profile_change_and_recompute_preserve_orientation(self):
        obj, proxy = self.create((0, 0, 0), (10, 6, 0))
        expected = obj.Placement.Rotation.matrix
        obj.Profile = "W 200 x 15,0"
        proxy.onChanged(obj, "Profile")
        for _ in range(3):
            proxy.execute(obj)
            self.assertEqual(obj.Placement.Rotation.matrix, expected)

    def test_manual_placement_remains_external_and_preserved(self):
        obj, proxy = self.create((0, 0, 0), (10, 6, 0))
        manual = Placement(Vector(7, 8, 9), obj.Placement.Rotation)
        obj.Placement = manual
        proxy.onChanged(obj, "Placement")
        expected = obj.Placement.Rotation.matrix
        proxy.execute(obj)
        self.assertEqual(obj.Placement.Rotation.matrix, expected)
        self.assertVector(obj.Placement.Base, (7, 8, 9))


if __name__ == "__main__":
    unittest.main()
