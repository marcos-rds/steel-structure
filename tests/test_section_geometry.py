"""Pure-Python tests for the two-dimensional section geometry core."""

from __future__ import annotations

import math
import unittest
from dataclasses import FrozenInstanceError, replace

from freecad.SteelStructures.paths import CATALOGS_DIR
from freecad.SteelStructures.profiles import ProfileLibrary, ProfileRef
from freecad.SteelStructures.profiles.geometry import (
    LineSegment2D,
    Point2D,
    SectionBounds2D,
    SectionGeometryError,
    SectionPath2D,
    UnsupportedSectionGeometryError,
    build_equal_angle_section,
    build_parallel_flange_i_section,
    build_section_geometry,
)


CATALOG_ID = "gerdau-construcao-metalica-2023-01"


class GeometryPrimitiveTests(unittest.TestCase):
    def test_points_lines_and_bounds_are_immutable_hashable_and_structural(self):
        first = Point2D(1, 2)
        same = Point2D(1.0, 2.0)
        line = LineSegment2D(first, Point2D(4, 6))
        bounds = SectionBounds2D(-2, 2, -3, 3)
        self.assertEqual(first, same)
        self.assertEqual(hash(first), hash(same))
        self.assertEqual(line.length, 5.0)
        self.assertEqual((bounds.width, bounds.height), (4.0, 6.0))
        self.assertEqual(len({line, LineSegment2D(same, Point2D(4, 6))}), 1)
        with self.assertRaises(FrozenInstanceError):
            first.x = 9

    def test_finite_and_positive_bounds_validation(self):
        for args in ((math.nan, 0), (0, math.inf), ("x", 0)):
            with self.subTest(args=args), self.assertRaises(SectionGeometryError):
                Point2D(*args)
        for args in ((0, 0, -1, 1), (-1, 1, 2, 2), (-math.inf, 1, -1, 1)):
            with self.subTest(args=args), self.assertRaises(SectionGeometryError):
                SectionBounds2D(*args)

    def test_zero_length_line_is_rejected(self):
        point = Point2D(1, 1)
        with self.assertRaisesRegex(SectionGeometryError, "comprimento zero"):
            LineSegment2D(point, point)

    def test_path_requires_continuity_and_explicit_correct_closure(self):
        a, b, c, d = Point2D(0, 0), Point2D(1, 0), Point2D(1, 1), Point2D(0, 1)
        with self.assertRaisesRegex(SectionGeometryError, "descontinuidade"):
            SectionPath2D((LineSegment2D(a, b), LineSegment2D(c, d)), False)
        open_segments = (LineSegment2D(a, b), LineSegment2D(b, c))
        with self.assertRaisesRegex(SectionGeometryError, "não retorna"):
            SectionPath2D(open_segments, True)
        closed_segments = open_segments + (LineSegment2D(c, a),)
        with self.assertRaisesRegex(SectionGeometryError, "closed=True"):
            SectionPath2D(closed_segments, False)
        path = SectionPath2D(closed_segments, True)
        self.assertEqual(path.segments[-1].end, path.segments[0].start)


class ParallelFlangeISectionTests(unittest.TestCase):
    def assert_topology(self, geometry, d, bf, tw, tf):
        self.assertEqual(geometry.geometry_type, "i_section")
        self.assertEqual(geometry.geometry_variant, "parallel_flange")
        self.assertEqual(geometry.inner_paths, ())
        self.assertEqual(len(geometry.outer_path.segments), 12)
        self.assertTrue(geometry.outer_path.closed)
        for index, segment in enumerate(geometry.outer_path.segments):
            following = geometry.outer_path.segments[(index + 1) % 12]
            self.assertEqual(segment.end, following.start)
            self.assertGreater(segment.length, 0.0)
        self.assertGreater(geometry.outer_path.signed_area, 0.0)
        self.assertEqual(geometry.origin, Point2D(0, 0))
        self.assertAlmostEqual(geometry.bounds.min_x, -bf / 2)
        self.assertAlmostEqual(geometry.bounds.max_x, bf / 2)
        self.assertAlmostEqual(geometry.bounds.min_y, -d / 2)
        self.assertAlmostEqual(geometry.bounds.max_y, d / 2)
        self.assertAlmostEqual(geometry.bounds.width, bf)
        self.assertAlmostEqual(geometry.bounds.height, d)
        self.assertAlmostEqual(geometry.area, 2 * bf * tf + (d - 2 * tf) * tw)

    def test_w150_matches_historical_vertex_contract_exactly(self):
        geometry = build_parallel_flange_i_section(d=148, bf=100, tw=4.3, tf=4.9)
        expected = (
            (-50, -74), (50, -74), (50, -69.1), (2.15, -69.1),
            (2.15, 69.1), (50, 69.1), (50, 74), (-50, 74),
            (-50, 69.1), (-2.15, 69.1), (-2.15, -69.1), (-50, -69.1),
        )
        starts = tuple((segment.start.x, segment.start.y) for segment in geometry.outer_path.segments)
        self.assertEqual(starts, expected)
        self.assert_topology(geometry, 148, 100, 4.3, 4.9)

    def test_selected_w_and_hp_dimensions_bounds_symmetry_and_area(self):
        cases = (
            (317, 167, 7.6, 13.2),
            (628, 328, 16.5, 27.7),
            (204, 207, 11.3, 11.3),
            (314, 313, 18.3, 18.3),
        )
        for d, bf, tw, tf in cases:
            with self.subTest(dimensions=(d, bf, tw, tf)):
                geometry = build_parallel_flange_i_section(d=d, bf=bf, tw=tw, tf=tf)
                self.assert_topology(geometry, d, bf, tw, tf)
                points = {segment.start for segment in geometry.outer_path.segments}
                self.assertEqual(points, {Point2D(-p.x, p.y) for p in points})
                self.assertEqual(points, {Point2D(p.x, -p.y) for p in points})

    def test_builder_rejects_invalid_or_non_finite_dimensions(self):
        cases = (
            {"d": 0, "bf": 100, "tw": 4, "tf": 5},
            {"d": 100, "bf": -1, "tw": 4, "tf": 5},
            {"d": 100, "bf": 100, "tw": 100, "tf": 5},
            {"d": 100, "bf": 100, "tw": 4, "tf": 50},
            {"d": math.nan, "bf": 100, "tw": 4, "tf": 5},
            {"d": 100, "bf": math.inf, "tw": 4, "tf": 5},
        )
        for dimensions in cases:
            with self.subTest(dimensions=dimensions), self.assertRaises(SectionGeometryError):
                build_parallel_flange_i_section(**dimensions)


class EqualAngleSectionTests(unittest.TestCase):
    def assert_topology(self, geometry, b, t, centroid_x):
        self.assertEqual(geometry.geometry_type, "equal_angle")
        self.assertEqual(geometry.geometry_variant, "equal_leg")
        self.assertEqual(geometry.inner_paths, ())
        self.assertEqual(len(geometry.outer_path.segments), 6)
        self.assertTrue(geometry.outer_path.closed)
        for index, segment in enumerate(geometry.outer_path.segments):
            following = geometry.outer_path.segments[(index + 1) % 6]
            self.assertEqual(segment.end, following.start)
            self.assertGreater(segment.length, 0.0)
        self.assertGreater(geometry.outer_path.signed_area, 0.0)
        self.assertEqual(geometry.origin, Point2D(0, 0))
        self.assertAlmostEqual(geometry.bounds.min_x, -centroid_x)
        self.assertAlmostEqual(geometry.bounds.max_x, b - centroid_x)
        self.assertAlmostEqual(geometry.bounds.min_y, -centroid_x)
        self.assertAlmostEqual(geometry.bounds.max_y, b - centroid_x)
        self.assertNotAlmostEqual(geometry.bounds.min_x, -geometry.bounds.max_x)
        self.assertAlmostEqual(geometry.area, 2 * b * t - t * t)

    def test_equal_leg_contour_is_one_ccw_six_segment_polygon(self):
        geometry = build_equal_angle_section(b=50, t=5, centroid_x=14.2)
        starts = tuple(
            (segment.start.x, segment.start.y)
            for segment in geometry.outer_path.segments
        )
        self.assertEqual(starts, (
            (-14.2, -14.2), (35.8, -14.2), (35.8, -9.2),
            (-9.2, -9.2), (-9.2, 35.8), (-14.2, 35.8),
        ))
        self.assert_topology(geometry, 50, 5, 14.2)

    def test_builder_rejects_invalid_dimensions_and_centroid(self):
        cases = (
            {"b": 0, "t": 5, "centroid_x": 14},
            {"b": 50, "t": 0, "centroid_x": 14},
            {"b": 50, "t": 50, "centroid_x": 14},
            {"b": 50, "t": 5, "centroid_x": 0},
            {"b": 50, "t": 5, "centroid_x": 50},
            {"b": math.inf, "t": 5, "centroid_x": 14},
            {"b": 50, "t": math.nan, "centroid_x": 14},
        )
        for dimensions in cases:
            with self.subTest(dimensions=dimensions), self.assertRaises(SectionGeometryError):
                build_equal_angle_section(**dimensions)


class CatalogGeometryDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = ProfileLibrary(CATALOGS_DIR)

    def get(self, profile_id):
        return self.library.get(ProfileRef(CATALOG_ID, profile_id))

    def test_dispatch_uses_geometry_description_not_commercial_identity(self):
        profile = self.get("w-150x13.0")
        renamed = replace(profile, series_id="unrelated", family="custom")
        self.assertEqual(build_section_geometry(profile), build_section_geometry(renamed))

    def test_same_profile_is_not_mutated_and_build_is_deterministic(self):
        profile = self.get("w-310x52.0")
        before = (dict(profile.geometry), dict(profile.section_properties), profile.geometry_variant)
        first = build_section_geometry(profile)
        second = build_section_geometry(profile)
        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))
        self.assertEqual(before, (dict(profile.geometry), dict(profile.section_properties), profile.geometry_variant))

    def test_five_required_real_profiles_match_catalog_dimensions(self):
        ids = ("w-150x13.0", "w-310x52.0", "w-610x217.0", "hp-200x53.0", "hp-310x132.0")
        for profile_id in ids:
            profile = self.get(profile_id)
            geometry = build_section_geometry(profile)
            with self.subTest(profile=profile_id):
                self.assertAlmostEqual(geometry.bounds.width, profile.geometry["bf"])
                self.assertAlmostEqual(geometry.bounds.height, profile.geometry["d"])
                self.assertEqual(len(geometry.outer_path.segments), 12)

    def test_all_108_w_hp_profiles_build_successfully(self):
        profiles = self.library.list_profiles(series_id="w") + self.library.list_profiles(series_id="hp")
        self.assertEqual(len(profiles), 108)
        geometries = tuple(build_section_geometry(profile) for profile in profiles)
        self.assertEqual(len(geometries), 108)
        self.assertTrue(all(len(item.outer_path.segments) == 12 for item in geometries))

    def test_real_i_u_and_t_remain_explicitly_unsupported(self):
        profile_ids = ("i-3x8.48", "u-3x6.10", "t-2x0.25")
        for profile_id in profile_ids:
            with self.subTest(profile=profile_id), self.assertRaises(UnsupportedSectionGeometryError):
                build_section_geometry(self.get(profile_id))

    def test_required_real_equal_angles_use_catalog_centroid_and_dimensions(self):
        profile_ids = (
            "equal-angle-inch-0.5x0.125", "equal-angle-inch-2x0.25",
            "equal-angle-metric-40x4", "equal-angle-metric-50x5",
            "equal-angle-metric-100x9",
        )
        for profile_id in profile_ids:
            profile = self.get(profile_id)
            before = (dict(profile.geometry), dict(profile.centroid))
            geometry = build_section_geometry(profile)
            with self.subTest(profile=profile_id):
                self.assertEqual(geometry, build_section_geometry(profile))
                self.assertEqual(hash(geometry), hash(build_section_geometry(profile)))
                self.assertEqual(before, (dict(profile.geometry), dict(profile.centroid)))
                self.assertAlmostEqual(geometry.bounds.width, profile.geometry["b"])
                self.assertAlmostEqual(geometry.bounds.height, profile.geometry["b"])
                self.assertAlmostEqual(geometry.bounds.min_x, -profile.centroid["x"])
                self.assertAlmostEqual(geometry.bounds.min_y, -profile.centroid["x"])
                self.assertAlmostEqual(
                    geometry.area,
                    2 * profile.geometry["b"] * profile.geometry["t"]
                    - profile.geometry["t"] ** 2,
                )
                self.assertNotAlmostEqual(
                    geometry.area, profile.physical_properties.area_mm2
                )

    def test_all_80_equal_angles_and_all_188_supported_profiles_build(self):
        angles = (
            self.library.list_profiles(series_id="equal-angle-inch")
            + self.library.list_profiles(series_id="equal-angle-metric")
        )
        self.assertEqual(len(angles), 80)
        geometries = tuple(build_section_geometry(profile) for profile in angles)
        self.assertTrue(all(len(item.outer_path.segments) == 6 for item in geometries))
        supported = (
            self.library.list_profiles(series_id="w")
            + self.library.list_profiles(series_id="hp") + angles
        )
        self.assertEqual(len(supported), 188)
        self.assertEqual(len(tuple(build_section_geometry(profile) for profile in supported)), 188)

    def test_equal_angle_requires_catalog_centroid(self):
        profile = self.get("equal-angle-metric-50x5")
        with self.assertRaisesRegex(SectionGeometryError, "x"):
            build_section_geometry(replace(profile, centroid={}))

    def test_tapered_i_is_not_silently_approximated_as_parallel(self):
        profile = self.get("w-150x13.0")
        with self.assertRaises(UnsupportedSectionGeometryError):
            build_section_geometry(replace(profile, geometry_variant="tapered_flange"))

    def test_simplified_polygon_area_is_independent_from_catalog_area(self):
        profile = self.get("w-150x13.0")
        geometry = build_section_geometry(profile)
        expected = 2 * 100 * 4.9 + (148 - 2 * 4.9) * 4.3
        self.assertAlmostEqual(geometry.area, expected)
        self.assertNotAlmostEqual(geometry.area, profile.physical_properties.area_mm2)


if __name__ == "__main__":
    unittest.main()
