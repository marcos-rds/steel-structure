"""Analytical intersection tests for pure cold-formed geometry."""

from __future__ import annotations

import math
import unittest

from freecad.SteelStructures.profiles import (
    ArcSegment2D, ColdFormedPath2D, LineSegment2D, Point2D,
    SectionGeometryError, SectionPath2D, angle_on_arc,
    arc_arc_intersections, build_ue_mean_path, path_self_intersections,
    segment_arc_intersections, segment_segment_intersections,
)


def point_on_circle(center, radius, angle):
    return Point2D(
        center.x + radius * math.cos(angle),
        center.y + radius * math.sin(angle),
    )


def arc(center, radius, start_angle, end_angle, clockwise=False):
    return ArcSegment2D(
        point_on_circle(center, radius, start_angle),
        point_on_circle(center, radius, end_angle),
        center,
        clockwise,
    )


def tangent_path(commands):
    """Build a compact line/arc path from turtle-like tangent commands."""
    point = Point2D(0, 0)
    heading = 0.0
    segments = []
    for kind, value, radius in commands:
        if kind == "line":
            end = Point2D(
                point.x + value * math.cos(heading),
                point.y + value * math.sin(heading),
            )
            segments.append(LineSegment2D(point, end))
        else:
            sign = 1.0 if value > 0.0 else -1.0
            center = Point2D(
                point.x - sign * radius * math.sin(heading),
                point.y + sign * radius * math.cos(heading),
            )
            next_heading = heading + math.radians(value)
            end = Point2D(
                center.x + sign * radius * math.sin(next_heading),
                center.y - sign * radius * math.cos(next_heading),
            )
            segments.append(ArcSegment2D(point, end, center, value < 0.0))
            heading = next_heading
        point = end
    return SectionPath2D(tuple(segments), False)


class AngularSpanTests(unittest.TestCase):
    def test_counterclockwise_clockwise_and_wrap_membership(self):
        center = Point2D(0, 0)
        wrapped = arc(center, 5, math.radians(350), math.radians(20))
        self.assertTrue(angle_on_arc(0.0, wrapped))
        self.assertFalse(angle_on_arc(math.pi, wrapped))
        clockwise = arc(center, 5, math.radians(20), math.radians(350), True)
        self.assertTrue(angle_on_arc(0.0, clockwise))
        self.assertFalse(angle_on_arc(math.pi, clockwise))


class LineLineIntersectionTests(unittest.TestCase):
    def test_crossing_touch_overlap_and_valid_adjacency(self):
        crossing = segment_segment_intersections(
            LineSegment2D(Point2D(0, 0), Point2D(4, 4)),
            LineSegment2D(Point2D(0, 4), Point2D(4, 0)),
        )
        self.assertEqual(crossing.points, (Point2D(2, 2),))
        self.assertFalse(crossing.overlap)

        touching = segment_segment_intersections(
            LineSegment2D(Point2D(0, 0), Point2D(2, 0)),
            LineSegment2D(Point2D(2, 0), Point2D(2, 2)),
        )
        self.assertEqual(touching.points, (Point2D(2, 0),))

        partial = segment_segment_intersections(
            LineSegment2D(Point2D(0, 0), Point2D(4, 0)),
            LineSegment2D(Point2D(2, 0), Point2D(6, 0)),
        )
        total = segment_segment_intersections(
            LineSegment2D(Point2D(0, 0), Point2D(4, 0)),
            LineSegment2D(Point2D(4, 0), Point2D(0, 0)),
        )
        self.assertTrue(partial.overlap)
        self.assertTrue(total.overlap)

        valid_path = SectionPath2D((
            LineSegment2D(Point2D(0, 0), Point2D(2, 0)),
            LineSegment2D(Point2D(2, 0), Point2D(2, 2)),
        ), False)
        self.assertFalse(path_self_intersections(valid_path))


class LineArcIntersectionTests(unittest.TestCase):
    def setUp(self):
        self.center = Point2D(0, 0)
        self.quarter = arc(self.center, 5, 0.0, math.pi / 2.0)

    def test_secant_tangent_none_and_circle_hit_outside_span(self):
        secant = segment_arc_intersections(
            LineSegment2D(Point2D(3, -1), Point2D(3, 6)), self.quarter
        )
        self.assertEqual(len(secant.points), 1)
        self.assertTrue(math.isclose(secant.points[0].y, 4.0))

        tangent = segment_arc_intersections(
            LineSegment2D(Point2D(-1, 5), Point2D(1, 5)), self.quarter
        )
        self.assertEqual(tangent.points, (Point2D(0, 5),))

        none = segment_arc_intersections(
            LineSegment2D(Point2D(-1, 6), Point2D(1, 6)), self.quarter
        )
        outside_span = segment_arc_intersections(
            LineSegment2D(Point2D(-5, -1), Point2D(-5, 1)), self.quarter
        )
        self.assertFalse(none.intersects)
        self.assertFalse(outside_span.intersects)

    def test_analytical_tangency_rejects_contact_missed_by_old_chords(self):
        # A chord-only proper-crossing test sees no sign change at tangency.
        # The analytical quadratic retains the single contact point.
        tiny_tangent = LineSegment2D(Point2D(5, -0.01), Point2D(5, 0.01))
        almost_quarter = arc(self.center, 5, -0.01, 0.01)
        result = segment_arc_intersections(tiny_tangent, almost_quarter)
        self.assertEqual(result.points, (Point2D(5, 0),))


class ArcArcIntersectionTests(unittest.TestCase):
    def test_two_points_tangency_and_span_filtering(self):
        first = arc(Point2D(0, 0), 5, 0, 0)
        crossing = arc_arc_intersections(first, arc(Point2D(6, 0), 5, 0, 0))
        tangent = arc_arc_intersections(first, arc(Point2D(10, 0), 5, 0, 0))
        self.assertEqual(len(crossing.points), 2)
        self.assertEqual(tangent.points, (Point2D(5, 0),))
        internal_tangent = arc_arc_intersections(
            first, arc(Point2D(3, 0), 2, 0, 0)
        )
        concentric = arc_arc_intersections(
            first, arc(Point2D(0, 0), 3, 0, 0)
        )
        self.assertEqual(internal_tangent.points, (Point2D(5, 0),))
        self.assertFalse(concentric.intersects)

        restricted_first = arc(Point2D(0, 0), 5, math.pi, 3 * math.pi / 2)
        restricted_second = arc(Point2D(6, 0), 5, -math.pi / 2, math.pi / 2)
        outside_spans = arc_arc_intersections(restricted_first, restricted_second)
        self.assertFalse(outside_spans.intersects)

    def test_coincident_overlap_and_disjoint_spans(self):
        center = Point2D(0, 0)
        overlap = arc_arc_intersections(
            arc(center, 5, 0, math.pi),
            arc(center, 5, math.pi / 2, 3 * math.pi / 2),
        )
        disjoint = arc_arc_intersections(
            arc(center, 5, 0, math.pi / 2),
            arc(center, 5, math.pi, 3 * math.pi / 2),
        )
        self.assertTrue(overlap.overlap)
        self.assertFalse(disjoint.intersects)


class PathIntersectionTests(unittest.TestCase):
    def test_open_path_crossing_and_nonadjacent_touch_are_invalid(self):
        crossing = SectionPath2D((
            LineSegment2D(Point2D(0, 0), Point2D(4, 4)),
            LineSegment2D(Point2D(4, 4), Point2D(0, 4)),
            LineSegment2D(Point2D(0, 4), Point2D(4, 0)),
        ), False)
        touching = SectionPath2D((
            LineSegment2D(Point2D(0, 0), Point2D(4, 0)),
            LineSegment2D(Point2D(4, 0), Point2D(4, 2)),
            LineSegment2D(Point2D(4, 2), Point2D(2, 0)),
        ), False)
        self.assertTrue(path_self_intersections(crossing))
        self.assertTrue(path_self_intersections(touching))

    def test_invalid_mean_path_is_rejected_before_offset(self):
        path = tangent_path((
            ("arc", -180, 4), ("arc", 180, 4),
            ("arc", 90, 4), ("arc", 90, 4),
            ("line", 8, 0), ("arc", -180, 4), ("arc", -90, 8),
        ))
        self.assertTrue(path_self_intersections(path))
        with self.assertRaisesRegex(SectionGeometryError, "linha média autointersectante"):
            ColdFormedPath2D(path, 0.5)

    def test_offset_created_self_intersection_is_rejected(self):
        path = tangent_path((
            ("line", 15, 0), ("arc", 135, 4), ("arc", -135, 4),
            ("line", 8, 0), ("arc", -180, 8), ("arc", -90, 4),
            ("arc", 45, 4), ("line", 8, 0),
        ))
        folded = ColdFormedPath2D(path, 6)
        with self.assertRaisesRegex(SectionGeometryError, "contorno físico autointersectante"):
            folded.physical_contour()

    def test_nonpositive_arc_offset_radius_is_rejected(self):
        path = SectionPath2D((arc(Point2D(0, 0), 1, 0, math.pi / 2),), False)
        folded = ColdFormedPath2D(path, 2.1)
        with self.assertRaisesRegex(SectionGeometryError, "raio circular nulo ou negativo"):
            folded.physical_contour()

    def test_normative_ue_mean_path_and_offset_are_valid(self):
        folded = build_ue_mean_path(bw=150, bf=60, D=20, t=3, ri=3)
        self.assertFalse(path_self_intersections(folded.mean_path))
        self.assertFalse(path_self_intersections(folded.physical_contour()))


if __name__ == "__main__":
    unittest.main()
