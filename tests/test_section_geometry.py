"""Pure-Python tests for the two-dimensional section geometry core."""

from __future__ import annotations

import math
import unittest
from dataclasses import FrozenInstanceError, replace

from freecad.SteelStructures.paths import CATALOGS_DIR
from freecad.SteelStructures.profiles import (
    ProfileLibrary, ProfileRef, section_geometric_properties,
)
from freecad.SteelStructures.profiles.geometry import (
    LineSegment2D,
    Point2D,
    SectionBounds2D,
    SectionGeometryError,
    SectionPath2D,
    GeometryTemporarilyUnavailableError,
    UnsupportedSectionGeometryError,
    build_equal_angle_section,
    build_parallel_flange_i_section,
    build_standard_tee_section,
    build_tapered_flange_i_section,
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


class TaperedFlangeISectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = ProfileLibrary(CATALOGS_DIR)

    @staticmethod
    def sampled_metrics(geometry, count=240):
        from freecad.SteelStructures.profiles import ArcSegment2D
        points = [geometry.outer_path.segments[0].start]
        for segment in geometry.outer_path.segments:
            points.extend(
                segment.sampled_points(count)
                if isinstance(segment, ArcSegment2D) else (segment.end,)
            )
        area2 = cx6 = cy6 = ix12 = iy12 = 0.0
        for first, second in zip(points, points[1:]):
            cross = first.x * second.y - second.x * first.y
            area2 += cross
            cx6 += (first.x + second.x) * cross
            cy6 += (first.y + second.y) * cross
            ix12 += (first.y ** 2 + first.y * second.y + second.y ** 2) * cross
            iy12 += (first.x ** 2 + first.x * second.x + second.x ** 2) * cross
        area = area2 / 2.0
        return area, cx6 / (6.0 * area), cy6 / (6.0 * area), ix12 / 12.0, iy12 / 12.0

    def test_small_intermediate_and_large_have_revit_topology_and_tangencies(self):
        from freecad.SteelStructures.profiles import ArcSegment2D
        for profile_id in ("i-3x8.48", "i-5x14.88", "i-6x22.00"):
            profile = self.library.get(ProfileRef(CATALOG_ID, profile_id))
            geometry = build_section_geometry(profile)
            arcs = [segment for segment in geometry.outer_path.segments
                    if isinstance(segment, ArcSegment2D)]
            with self.subTest(profile=profile.designation):
                self.assertEqual((geometry.geometry_type, geometry.geometry_variant),
                                 ("i_section", "tapered_flange"))
                self.assertTrue(geometry.outer_path.closed)
                self.assertEqual(len(geometry.outer_path.segments), 20)
                self.assertEqual(len(arcs), 8)
                self.assertEqual(sorted(round(arc.radius, 7) for arc in arcs),
                                 sorted([7.0] * 4 + [3.0] * 4))
                self.assertAlmostEqual(geometry.bounds.width, profile.geometry["bf"])
                self.assertAlmostEqual(geometry.bounds.height, profile.geometry["d"])
                self.assertEqual(geometry.origin, Point2D(0.0, 0.0))
                for index, arc in enumerate(geometry.outer_path.segments):
                    if not isinstance(arc, ArcSegment2D):
                        continue
                    for tangent, line in (
                        (arc.start, geometry.outer_path.segments[index - 1]),
                        (arc.end, geometry.outer_path.segments[index + 1]),
                    ):
                        radius = (tangent.x - arc.center.x, tangent.y - arc.center.y)
                        direction = (line.end.x - line.start.x, line.end.y - line.start.y)
                        self.assertAlmostEqual(radius[0] * direction[0] + radius[1] * direction[1],
                                               0.0, places=7)

    def test_tf_is_vertical_at_explicit_tl_and_inner_faces_have_revit_angle(self):
        for profile in self.library.list_profiles(series_id="i"):
            geometry = build_section_geometry(profile)
            x_tf = dict(geometry.dimension_stations)["tf_right"]
            slope = geometry.outer_path.segments[7]
            ratio = (x_tf - slope.start.x) / (slope.end.x - slope.start.x)
            inner_y = slope.start.y + ratio * (slope.end.y - slope.start.y)
            with self.subTest(profile=profile.designation):
                self.assertAlmostEqual(
                    x_tf, profile.geometry["bf"] / 2.0 - profile.geometry["tl"],
                )
                self.assertAlmostEqual(
                    geometry.bounds.max_y - inner_y, profile.geometry["tf"], places=9,
                )
                self.assertAlmostEqual(math.degrees(math.atan2(
                    slope.end.y - slope.start.y, slope.end.x - slope.start.x,
                )), 9.46, places=9)

    def test_all_eight_match_independent_area_centroid_and_inertias(self):
        profiles = self.library.list_profiles(series_id="i")
        self.assertEqual(len(profiles), 8)
        for profile in profiles:
            geometry = build_section_geometry(profile)
            area, cx, cy, ix, iy = self.sampled_metrics(geometry)
            area_error = abs(area / profile.physical_properties.area_mm2 - 1.0)
            ix_error = abs(ix / profile.section_properties["ix"] - 1.0)
            iy_reference = (
                profile.reported_section_properties["iy"]
                if profile.ref.profile_id == "i-3x9.68"
                else profile.section_properties["iy"]
            )
            iy_error = abs(iy / iy_reference - 1.0)
            with self.subTest(profile=profile.designation):
                self.assertLessEqual(area_error, 0.005)
                self.assertAlmostEqual(cx, 0.0, places=8)
                self.assertAlmostEqual(cy, 0.0, places=8)
                if profile.ref.profile_id == "i-3x9.68":
                    self.assertLessEqual(ix_error, 0.0225)
                    self.assertGreater(iy_error, 0.50)
                else:
                    self.assertLessEqual(ix_error, 0.004)
                    self.assertLessEqual(iy_error, 0.01)

    def test_all_eight_contours_have_no_sampled_self_intersections(self):
        from freecad.SteelStructures.profiles import ArcSegment2D

        def side(first, second, point):
            return ((second.x - first.x) * (point.y - first.y)
                    - (second.y - first.y) * (point.x - first.x))

        def intersects(a, b, c, d):
            return (side(a, b, c) * side(a, b, d) < -1e-9
                    and side(c, d, a) * side(c, d, b) < -1e-9)

        for profile in self.library.list_profiles(series_id="i"):
            geometry = build_section_geometry(profile)
            points = [geometry.outer_path.segments[0].start]
            for segment in geometry.outer_path.segments:
                points.extend(segment.sampled_points(48)
                              if isinstance(segment, ArcSegment2D) else (segment.end,))
            edges = list(zip(points, points[1:]))
            crossings = [
                (left, right)
                for left, first in enumerate(edges)
                for right, second in enumerate(edges)
                if right > left + 1
                and not (left == 0 and right == len(edges) - 1)
                and intersects(*first, *second)
            ]
            with self.subTest(profile=profile.designation):
                self.assertEqual(crossings, [])

    def test_builder_rejects_missing_space_for_radii_or_invalid_tl(self):
        valid = dict(d=76.2, bf=59.18, tw=4.32, tf=6.6,
                     flange_angle=9.46, r1=7.0, r2=3.0, tl=13.715)
        for changed in ({"tl": 0.0}, {"tl": 30.0}, {"r1": 30.0}, {"r2": 30.0}):
            dimensions = dict(valid, **changed)
            with self.subTest(changed=changed), self.assertRaises(SectionGeometryError):
                build_tapered_flange_i_section(**dimensions)


class StandardTeeSectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = ProfileLibrary(CATALOGS_DIR)

    def test_builder_uses_only_four_dimensions_and_centers_nominal_area(self):
        first = build_standard_tee_section(d=50.8, bf=50.8, tw=6.35, tf=6.35)
        self.assertEqual(len(first.outer_path.segments), 8)
        self.assertTrue(first.outer_path.closed)
        self.assertGreater(first.signed_area, 0.0)
        self.assertEqual((first.bounds.width, first.bounds.height), (50.8, 50.8))
        self.assertAlmostEqual(first.bounds.min_x, -25.4)
        self.assertAlmostEqual(first.bounds.max_x, 25.4)
        self.assertNotAlmostEqual(first.bounds.min_y, -first.bounds.max_y)
        calculated = section_geometric_properties(first)
        self.assertAlmostEqual(calculated.centroid_x, 0.0, places=12)
        self.assertAlmostEqual(calculated.centroid_y, 0.0, places=12)

    def test_all_ten_match_nominal_metrics_and_catalog_with_documented_limits(self):
        expected = {
            "t-0.625x0.125": (0.908844, 0.511827, 0.200006, 0.109523),
            "t-0.75x0.125": (1.110456, 0.591880, 0.360803, 0.187455),
            "t-0.875x0.125": (1.312068, 0.671686, 0.591342, 0.295824),
            "t-1x0.125": (1.514316, 0.751596, 0.905416, 0.440212),
            "t-1.25x0.125": (1.918176, 0.910904, 1.831658, 0.855815),
            "t-1.5x0.125": (2.322036, 1.070019, 3.241310, 1.474976),
            "t-1.25x0.1875": (2.796024, 0.967428, 2.558464, 1.293828),
            "t-1.5x0.1875": (3.400544, 1.127036, 4.575728, 2.223783),
            "t-2x0.1875": (4.609584, 1.445575, 11.333567, 5.241540),
            "t-2x0.25": (6.048375, 1.502833, 14.467836, 7.032035),
        }
        profiles = self.library.list_profiles(series_id="t")
        self.assertEqual(len(profiles), 10)
        area_limits = {
            "t-0.625x0.125": 0.010,
            "t-0.75x0.125": 0.018,
            "t-0.875x0.125": 0.021,
            "t-1x0.125": 0.017,
        }
        for profile in profiles:
            geometry = build_section_geometry(profile)
            values = section_geometric_properties(geometry)
            expected_area, expected_x, expected_ix, expected_iy = expected[profile.ref.profile_id]
            x_from_top = geometry.bounds.max_y / 10.0
            area_cm2 = values.area / 100.0
            ix_cm4, iy_cm4 = values.ix / 10000.0, values.iy / 10000.0
            with self.subTest(profile=profile.designation):
                self.assertEqual(len(geometry.outer_path.segments), 8)
                self.assertAlmostEqual(area_cm2, expected_area, places=6)
                self.assertAlmostEqual(x_from_top, expected_x, places=6)
                self.assertAlmostEqual(ix_cm4, expected_ix, places=6)
                self.assertAlmostEqual(iy_cm4, expected_iy, places=6)
                self.assertAlmostEqual(values.centroid_x, 0.0, places=11)
                self.assertAlmostEqual(values.centroid_y, 0.0, places=11)
                self.assertLessEqual(
                    abs(area_cm2 / (profile.physical_properties.area_mm2 / 100.0) - 1.0),
                    area_limits.get(profile.ref.profile_id, 0.0025),
                )
                self.assertLessEqual(abs(x_from_top * 10.0 / profile.centroid_from_top_flange_face - 1.0), 0.004)
                self.assertLessEqual(abs(ix_cm4 / (profile.section_properties["ix"] / 10000.0) - 1.0), 0.0065)
                if profile.ref.profile_id != "t-0.875x0.125":
                    self.assertLessEqual(abs(iy_cm4 / (profile.section_properties["iy"] / 10000.0) - 1.0), 0.014)

                critical_y = max(abs(geometry.bounds.min_y), abs(geometry.bounds.max_y))
                wx = values.ix / critical_y
                wy = values.iy / (profile.geometry["bf"] / 2.0)
                rx = math.sqrt(values.ix / values.area)
                ry = math.sqrt(values.iy / values.area)
                self.assertLessEqual(abs(wx / profile.section_properties["wx"] - 1.0), 0.023)
                self.assertLessEqual(abs(wy / profile.section_properties["wy"] - 1.0), 0.017)
                self.assertLessEqual(abs(rx / profile.section_properties["rx"] - 1.0), 0.005)
                self.assertLessEqual(abs(ry / profile.section_properties["ry"] - 1.0), 0.011)

                vertices = tuple(segment.start for segment in geometry.outer_path.segments)
                reflected = {(round(-point.x, 10), round(point.y, 10)) for point in vertices}
                self.assertEqual(reflected, {
                    (round(point.x, 10), round(point.y, 10)) for point in vertices
                })
                self.assertNotAlmostEqual(geometry.bounds.max_y, -geometry.bounds.min_y)

                def side(a, b, c):
                    return ((b.x - a.x) * (c.y - a.y)
                            - (b.y - a.y) * (c.x - a.x))

                edges = tuple((segment.start, segment.end)
                              for segment in geometry.outer_path.segments)
                crossings = []
                for left, first in enumerate(edges):
                    for right, second in enumerate(edges):
                        if right <= left + 1 or (left == 0 and right == len(edges) - 1):
                            continue
                        if (side(*first, second[0]) * side(*first, second[1]) < -1e-9
                                and side(*second, first[0]) * side(*second, first[1]) < -1e-9):
                            crossings.append((left, right))
                self.assertEqual(crossings, [])

    def test_tee_geometry_is_independent_from_official_centroid_reference(self):
        profile = self.library.list_profiles(series_id="t")[0]
        baseline = build_section_geometry(profile)
        self.assertEqual(baseline, build_section_geometry(replace(
            profile, centroid_from_top_flange_face=999.0,
        )))

    def test_t_7_8_preserves_reported_iy_without_override_and_remains_buildable(self):
        profile = next(item for item in self.library.list_profiles(series_id="t")
                       if item.ref.profile_id == "t-0.875x0.125")
        geometry = build_section_geometry(profile)
        calculated = section_geometric_properties(geometry)
        self.assertAlmostEqual(calculated.iy / 10000.0, 0.295824, places=6)
        self.assertEqual(profile.section_properties["iy"], 3300.0)
        self.assertEqual(profile.reported_section_properties["iy"], 3300.0)
        self.assertIsNone(profile.section_property_override)
        self.assertEqual(profile.geometry_status, "released")

    def test_builder_rejects_invalid_dimensions_without_imposing_catalog_equalities(self):
        geometry = build_standard_tee_section(d=60, bf=50, tw=5, tf=6)
        self.assertEqual((geometry.bounds.width, geometry.bounds.height), (50.0, 60.0))
        for changes in ({"d": 0}, {"bf": 0}, {"tw": 50}, {"tf": 60}):
            values = dict(d=60, bf=50, tw=5, tf=6)
            values.update(changes)
            with self.subTest(changes=changes), self.assertRaises(SectionGeometryError):
                build_standard_tee_section(**values)


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

    def test_real_t_dispatches_to_standard_tee(self):
        geometry = build_section_geometry(self.get("t-2x0.25"))
        self.assertEqual(
            (geometry.geometry_type, geometry.geometry_variant, len(geometry.outer_path.segments)),
            ("tee_section", "standard_tee", 8),
        )

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

    def test_all_80_equal_angles_and_all_215_released_profiles_build(self):
        angles = (
            self.library.list_profiles(series_id="equal-angle-inch")
            + self.library.list_profiles(series_id="equal-angle-metric")
        )
        self.assertEqual(len(angles), 80)
        geometries = tuple(build_section_geometry(profile) for profile in angles)
        self.assertTrue(all(len(item.outer_path.segments) == 6 for item in geometries))
        all_channels = self.library.list_profiles(series_id="u")
        channels = tuple(profile for profile in all_channels if profile.geometry_status == "released")
        self.assertEqual((len(all_channels), len(channels)), (12, 9))
        supported = (
            self.library.list_profiles(series_id="w")
            + self.library.list_profiles(series_id="hp")
            + self.library.list_profiles(series_id="i")
            + self.library.list_profiles(series_id="t") + channels + angles
        )
        self.assertEqual(len(supported), 215)
        self.assertEqual(len(tuple(build_section_geometry(profile) for profile in supported)), 215)

    def test_small_medium_and_large_u_have_radii_taper_bounds_and_orientation(self):
        from freecad.SteelStructures.profiles import ArcSegment2D
        for profile_id in ("u-3x6.10", "u-8x20.50", "u-12x37.00"):
            profile = self.get(profile_id)
            geometry = build_section_geometry(profile)
            arcs = [segment for segment in geometry.outer_path.segments
                    if isinstance(segment, ArcSegment2D)]
            with self.subTest(profile=profile_id):
                self.assertEqual((geometry.geometry_type, geometry.geometry_variant),
                                 ("channel_section", "tapered_flange"))
                self.assertAlmostEqual(geometry.bounds.width, profile.geometry["bf"])
                self.assertAlmostEqual(geometry.bounds.height, profile.geometry["d"])
                self.assertAlmostEqual(geometry.bounds.min_x, -profile.centroid["x"])
                self.assertEqual(len(arcs), 4)
                self.assertEqual(sorted(round(arc.radius, 6) for arc in arcs),
                                 sorted([profile.geometry["r1"]] * 2 + [profile.geometry["r2"]] * 2))
                self.assertGreater(geometry.signed_area, 0.0)
                self.assertGreater(geometry.bounds.max_x, abs(geometry.bounds.min_x))
                lower, upper = geometry.outer_path.segments[3], geometry.outer_path.segments[7]
                self.assertAlmostEqual(lower.start.x, upper.end.x)
                self.assertAlmostEqual(lower.start.y, -upper.end.y)
                self.assertGreater(upper.end.y, upper.start.y)

                x_tf = (profile.geometry["bf"] + profile.geometry["tw"]) / 2.0
                local_x_tf = x_tf - profile.centroid["x"]
                ratio = (local_x_tf - upper.start.x) / (upper.end.x - upper.start.x)
                inner_y = upper.start.y + ratio * (upper.end.y - upper.start.y)
                self.assertAlmostEqual(profile.geometry["d"] / 2.0 - inner_y,
                                       profile.geometry["tf"], places=9)
                effective_angle = math.degrees(math.atan2(
                    upper.end.y - upper.start.y, upper.end.x - upper.start.x,
                ))
                self.assertAlmostEqual(effective_angle, profile.geometry["flange_angle"], places=9)

                for arc_index, previous_index, next_index in (
                    (2, 1, 3), (4, 3, 5), (6, 5, 7), (8, 7, 9),
                ):
                    arc = geometry.outer_path.segments[arc_index]
                    for tangent, line_index in ((arc.start, previous_index), (arc.end, next_index)):
                        line = geometry.outer_path.segments[line_index]
                        radius = (tangent.x - arc.center.x, tangent.y - arc.center.y)
                        direction = (line.end.x - line.start.x, line.end.y - line.start.y)
                        self.assertAlmostEqual(
                            radius[0] * direction[0] + radius[1] * direction[1],
                            0.0, places=7,
                        )

    def test_all_u_nominal_area_centroid_symmetry_and_no_self_intersection(self):
        from freecad.SteelStructures.profiles import ArcSegment2D

        def polygon(geometry):
            points = []
            for segment in geometry.outer_path.segments:
                if not points:
                    points.append(segment.start)
                points.extend(segment.sampled_points(48) if isinstance(segment, ArcSegment2D)
                              else (segment.end,))
            return points

        def metrics(points):
            cross = [a.x * b.y - b.x * a.y for a, b in zip(points, points[1:])]
            area = sum(cross) / 2.0
            cx = sum((a.x + b.x) * value
                     for a, b, value in zip(points, points[1:], cross)) / (6.0 * area)
            cy = sum((a.y + b.y) * value
                     for a, b, value in zip(points, points[1:], cross)) / (6.0 * area)
            return area, cx, cy

        def intersects(a, b, c, d):
            def side(p, q, r):
                return (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
            return side(a, b, c) * side(a, b, d) < -1e-9 and side(c, d, a) * side(c, d, b) < -1e-9

        channels = tuple(profile for profile in self.library.list_profiles(series_id="u")
                         if profile.geometry_status == "released")
        self.assertEqual(len(channels), 9)
        for profile in channels:
            geometry = build_section_geometry(profile)
            points = polygon(geometry)
            area, cx, cy = metrics(points)
            edges = list(zip(points, points[1:]))
            crossings = [
                (i, j) for i, first in enumerate(edges) for j, second in enumerate(edges)
                if j > i + 1 and not (i == 0 and j == len(edges) - 1)
                and intersects(*first, *second)
            ]
            catalog_area = profile.physical_properties.area_mm2
            with self.subTest(profile=profile.designation):
                self.assertEqual(crossings, [])
                self.assertAlmostEqual(cy, 0.0, places=7)
                self.assertLessEqual(abs(cx), 0.4)
                self.assertLessEqual(abs(area / catalog_area - 1.0), 0.015)
                self.assertAlmostEqual(area, geometry.area, delta=0.08)

    def test_three_pending_u_profiles_remain_catalogued_but_have_no_geometry(self):
        pending_ids = {"u-3x7.44", "u-10x30.80", "u-12x29.76"}
        channels = self.library.list_profiles(series_id="u")
        pending = {profile.ref.profile_id: profile for profile in channels
                   if profile.geometry_status == "pending_technical_review"}
        self.assertEqual(set(pending), pending_ids)
        for profile_id, profile in pending.items():
            with self.subTest(profile=profile_id):
                self.assertGreater(profile.physical_properties.area_mm2, 0.0)
                self.assertIn("x", profile.centroid)
                with self.assertRaisesRegex(
                    GeometryTemporarilyUnavailableError, "inconsistência entre fontes",
                ):
                    build_section_geometry(profile)

    def test_equal_angle_requires_catalog_centroid(self):
        profile = self.get("equal-angle-metric-50x5")
        with self.assertRaisesRegex(SectionGeometryError, "x"):
            build_section_geometry(replace(profile, centroid={}))

    def test_tapered_i_is_not_silently_approximated_as_parallel(self):
        profile = self.get("w-150x13.0")
        with self.assertRaisesRegex(SectionGeometryError, "dimensão ausente"):
            build_section_geometry(replace(profile, geometry_variant="tapered_flange"))

    def test_simplified_polygon_area_is_independent_from_catalog_area(self):
        profile = self.get("w-150x13.0")
        geometry = build_section_geometry(profile)
        expected = 2 * 100 * 4.9 + (148 - 2 * 4.9) * 4.3
        self.assertAlmostEqual(geometry.area, expected)
        self.assertNotAlmostEqual(geometry.area, profile.physical_properties.area_mm2)


if __name__ == "__main__":
    unittest.main()
