# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure constant-thickness geometry for open cold-formed sections."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import (
    ArcSegment2D, LineSegment2D, Point2D, SectionBounds2D,
    SectionGeometry2D, SectionGeometryError, SectionPath2D,
)

_TOLERANCE = 1.0e-7


def _unit_tangent(segment, at_end=False):
    if isinstance(segment, LineSegment2D):
        dx = segment.end.x - segment.start.x
        dy = segment.end.y - segment.start.y
        length = math.hypot(dx, dy)
        return dx / length, dy / length
    point = segment.end if at_end else segment.start
    radial = ((point.x - segment.center.x) / segment.radius,
              (point.y - segment.center.y) / segment.radius)
    return ((radial[1], -radial[0]) if segment.clockwise
            else (-radial[1], radial[0]))


def _same_point(first, second, tolerance=_TOLERANCE):
    return math.hypot(first.x - second.x, first.y - second.y) <= tolerance


def _offset_segment(segment, distance):
    if isinstance(segment, LineSegment2D):
        tx, ty = _unit_tangent(segment)
        dx, dy = -ty * distance, tx * distance
        return LineSegment2D(
            Point2D(segment.start.x + dx, segment.start.y + dy),
            Point2D(segment.end.x + dx, segment.end.y + dy),
        )
    signed_sweep = -1.0 if segment.clockwise else 1.0
    radius = segment.radius - signed_sweep * distance
    if radius <= _TOLERANCE:
        raise SectionGeometryError("offset produz raio circular nulo ou negativo")
    scale = radius / segment.radius
    def point(source):
        return Point2D(
            segment.center.x + (source.x - segment.center.x) * scale,
            segment.center.y + (source.y - segment.center.y) * scale,
        )
    return ArcSegment2D(
        point(segment.start), point(segment.end), segment.center, segment.clockwise
    )


def _reverse_segment(segment):
    if isinstance(segment, ArcSegment2D):
        return ArcSegment2D(
            segment.end, segment.start, segment.center, not segment.clockwise
        )
    return LineSegment2D(segment.end, segment.start)


def _sample_path(path, arc_points=16):
    points = [path.segments[0].start]
    for segment in path.segments:
        if isinstance(segment, ArcSegment2D):
            points.extend(segment.sampled_points(arc_points))
        else:
            points.append(segment.end)
    return tuple(points)


def _cross(ax, ay, bx, by):
    return ax * by - ay * bx


def _dot(ax, ay, bx, by):
    return ax * bx + ay * by


def _deduplicate_points(points, tolerance=_TOLERANCE):
    unique = []
    for point in points:
        if not any(_same_point(point, existing, tolerance) for existing in unique):
            unique.append(point)
    return tuple(unique)


@dataclass(frozen=True)
class SegmentIntersections2D:
    """Finite intersections between two supported path segments."""

    points: tuple[Point2D, ...] = ()
    overlap: bool = False

    @property
    def intersects(self):
        return self.overlap or bool(self.points)


def angle_on_arc(angle, arc, tolerance=_TOLERANCE, include_endpoints=True):
    """Return whether a polar angle belongs to an ArcSegment2D span."""
    if not isinstance(arc, ArcSegment2D):
        raise TypeError("arc deve ser ArcSegment2D")
    tau = 2.0 * math.pi
    extent = abs(arc.sweep)
    if extent >= tau - tolerance:
        return True
    if arc.clockwise:
        distance = (arc.start_angle - angle) % tau
    else:
        distance = (angle - arc.start_angle) % tau
    angular_tolerance = tolerance / max(arc.radius, 1.0)
    if include_endpoints:
        return distance <= extent + angular_tolerance or tau - distance <= angular_tolerance
    return angular_tolerance < distance < extent - angular_tolerance


def segment_segment_intersections(first, second, tolerance=_TOLERANCE):
    """Intersect two finite line segments, including touches and overlaps."""
    if not isinstance(first, LineSegment2D) or not isinstance(second, LineSegment2D):
        raise TypeError("segment_segment_intersections requer duas retas")
    px, py = first.start.x, first.start.y
    rx, ry = first.end.x - px, first.end.y - py
    qx, qy = second.start.x, second.start.y
    sx, sy = second.end.x - qx, second.end.y - qy
    denominator = _cross(rx, ry, sx, sy)
    qpx, qpy = qx - px, qy - py
    scale = max(math.hypot(rx, ry), math.hypot(sx, sy), 1.0)
    if abs(denominator) > tolerance * scale:
        first_parameter = _cross(qpx, qpy, sx, sy) / denominator
        second_parameter = _cross(qpx, qpy, rx, ry) / denominator
        parameter_tolerance = tolerance / scale
        if (-parameter_tolerance <= first_parameter <= 1.0 + parameter_tolerance
                and -parameter_tolerance <= second_parameter <= 1.0 + parameter_tolerance):
            first_parameter = min(1.0, max(0.0, first_parameter))
            return SegmentIntersections2D((Point2D(
                px + first_parameter * rx, py + first_parameter * ry
            ),))
        return SegmentIntersections2D()
    if abs(_cross(qpx, qpy, rx, ry)) > tolerance * scale:
        return SegmentIntersections2D()
    rr = _dot(rx, ry, rx, ry)
    start = _dot(qpx, qpy, rx, ry) / rr
    end = start + _dot(sx, sy, rx, ry) / rr
    low, high = max(0.0, min(start, end)), min(1.0, max(start, end))
    parameter_tolerance = tolerance / math.sqrt(rr)
    if high < low - parameter_tolerance:
        return SegmentIntersections2D()
    if high - low <= parameter_tolerance:
        parameter = min(1.0, max(0.0, (low + high) / 2.0))
        return SegmentIntersections2D((Point2D(px + parameter * rx, py + parameter * ry),))
    return SegmentIntersections2D(
        _deduplicate_points((
            Point2D(px + low * rx, py + low * ry),
            Point2D(px + high * rx, py + high * ry),
        ), tolerance),
        overlap=True,
    )


def segment_arc_intersections(segment, arc, tolerance=_TOLERANCE):
    """Intersect a finite line segment with a finite circular arc."""
    if not isinstance(segment, LineSegment2D) or not isinstance(arc, ArcSegment2D):
        raise TypeError("segment_arc_intersections requer reta e arco")
    dx, dy = segment.end.x - segment.start.x, segment.end.y - segment.start.y
    fx = segment.start.x - arc.center.x
    fy = segment.start.y - arc.center.y
    aa = _dot(dx, dy, dx, dy)
    bb = 2.0 * _dot(fx, fy, dx, dy)
    cc = _dot(fx, fy, fx, fy) - arc.radius * arc.radius
    discriminant = bb * bb - 4.0 * aa * cc
    # The discriminant has length^4 units. Scale the linear tolerance by the
    # segment metric and circle radius so exact endpoint tangencies remain
    # stable for both small and large sections.
    discriminant_tolerance = max(
        8.0 * aa * arc.radius * tolerance,
        aa * tolerance * tolerance,
    )
    if discriminant < -discriminant_tolerance:
        return SegmentIntersections2D()
    roots = (-bb / (2.0 * aa),) if abs(discriminant) <= discriminant_tolerance else (
        (-bb - math.sqrt(max(0.0, discriminant))) / (2.0 * aa),
        (-bb + math.sqrt(max(0.0, discriminant))) / (2.0 * aa),
    )
    parameter_tolerance = tolerance / max(math.sqrt(aa), 1.0)
    points = []
    for parameter in roots:
        if -parameter_tolerance <= parameter <= 1.0 + parameter_tolerance:
            parameter = min(1.0, max(0.0, parameter))
            point = Point2D(segment.start.x + parameter * dx,
                            segment.start.y + parameter * dy)
            angle = math.atan2(point.y - arc.center.y, point.x - arc.center.x)
            if angle_on_arc(angle, arc, tolerance):
                points.append(point)
    return SegmentIntersections2D(_deduplicate_points(points, tolerance))


def arc_arc_intersections(first, second, tolerance=_TOLERANCE):
    """Intersect two finite circular arcs, including coincident overlap."""
    if not isinstance(first, ArcSegment2D) or not isinstance(second, ArcSegment2D):
        raise TypeError("arc_arc_intersections requer dois arcos")
    dx = second.center.x - first.center.x
    dy = second.center.y - first.center.y
    distance = math.hypot(dx, dy)
    if distance <= tolerance and abs(first.radius - second.radius) <= tolerance:
        candidates = _deduplicate_points(
            (first.start, first.end, second.start, second.end), tolerance
        )
        common = tuple(point for point in candidates if
                       angle_on_arc(math.atan2(point.y - first.center.y,
                                              point.x - first.center.x), first, tolerance)
                       and angle_on_arc(math.atan2(point.y - second.center.y,
                                                  point.x - second.center.x), second, tolerance))
        tau = 2.0 * math.pi
        boundaries = sorted({
            first.start_angle % tau,
            (first.start_angle + first.sweep) % tau,
            second.start_angle % tau,
            (second.start_angle + second.sweep) % tau,
        })
        probe_angles = []
        for index, boundary in enumerate(boundaries):
            following = boundaries[(index + 1) % len(boundaries)]
            span = (following - boundary) % tau
            if span > tolerance:
                probe_angles.append((boundary + span / 2.0) % tau)
        overlap = any(
            angle_on_arc(angle, first, tolerance, False)
            and angle_on_arc(angle, second, tolerance, False)
            for angle in probe_angles
        ) or abs(first.sweep) >= tau - tolerance or abs(second.sweep) >= tau - tolerance
        return SegmentIntersections2D(common, overlap)
    if distance <= tolerance:
        return SegmentIntersections2D()
    if (distance > first.radius + second.radius + tolerance
            or distance < abs(first.radius - second.radius) - tolerance):
        return SegmentIntersections2D()
    along = (first.radius ** 2 - second.radius ** 2 + distance ** 2) / (2.0 * distance)
    height_squared = first.radius ** 2 - along ** 2
    if height_squared < -tolerance * max(first.radius ** 2, 1.0):
        return SegmentIntersections2D()
    base_x = first.center.x + along * dx / distance
    base_y = first.center.y + along * dy / distance
    height = math.sqrt(max(0.0, height_squared))
    offsets = ((-dy * height / distance, dx * height / distance),)
    if height > tolerance:
        offsets += ((dy * height / distance, -dx * height / distance),)
    points = []
    for offset_x, offset_y in offsets:
        point = Point2D(base_x + offset_x, base_y + offset_y)
        first_angle = math.atan2(point.y - first.center.y, point.x - first.center.x)
        second_angle = math.atan2(point.y - second.center.y, point.x - second.center.x)
        if (angle_on_arc(first_angle, first, tolerance)
                and angle_on_arc(second_angle, second, tolerance)):
            points.append(point)
    return SegmentIntersections2D(_deduplicate_points(points, tolerance))


def path_self_intersections(path, tolerance=_TOLERANCE):
    """Return invalid pair intersections for one ordered open or closed path."""
    if not isinstance(path, SectionPath2D):
        raise TypeError("path deve ser SectionPath2D")
    invalid = []
    segments = path.segments
    for first_index, first in enumerate(segments):
        for second_index in range(first_index + 1, len(segments)):
            second = segments[second_index]
            adjacent = second_index == first_index + 1 or (
                path.closed and first_index == 0 and second_index == len(segments) - 1
            )
            if isinstance(first, LineSegment2D) and isinstance(second, LineSegment2D):
                result = segment_segment_intersections(first, second, tolerance)
            elif isinstance(first, LineSegment2D) and isinstance(second, ArcSegment2D):
                result = segment_arc_intersections(first, second, tolerance)
            elif isinstance(first, ArcSegment2D) and isinstance(second, LineSegment2D):
                result = segment_arc_intersections(second, first, tolerance)
            elif isinstance(first, ArcSegment2D) and isinstance(second, ArcSegment2D):
                result = arc_arc_intersections(first, second, tolerance)
            else:
                raise SectionGeometryError(
                    f"segmento não suportado na validação: {type(first).__name__} / "
                    f"{type(second).__name__}"
                )
            if adjacent:
                expected = first.end if second_index == first_index + 1 else first.start
                valid_join = (not result.overlap and len(result.points) == 1
                              and _same_point(result.points[0], expected, tolerance))
                if not valid_join:
                    invalid.append((first_index, second_index, result))
            elif result.intersects:
                invalid.append((first_index, second_index, result))
    return tuple(invalid)


def _validate_no_self_intersection(path, context="caminho"):
    intersections = path_self_intersections(path)
    if intersections:
        first, second, result = intersections[0]
        kind = "sobreposição" if result.overlap else "contato/interseção"
        raise SectionGeometryError(
            f"{context} autointersectante: {kind} entre segmentos {first} e {second}"
        )


@dataclass(frozen=True)
class ColdFormedPath2D:
    """Open tangent mean-line path with constant physical thickness."""

    mean_path: SectionPath2D
    thickness: float

    def __post_init__(self):
        if not isinstance(self.mean_path, SectionPath2D) or self.mean_path.closed:
            raise SectionGeometryError("linha média dobrada deve ser um caminho aberto")
        thickness = float(self.thickness)
        if not math.isfinite(thickness) or thickness <= 0.0:
            raise SectionGeometryError("espessura deve ser positiva e finita")
        object.__setattr__(self, "thickness", thickness)
        for previous, current in zip(self.mean_path.segments, self.mean_path.segments[1:]):
            if not _same_point(previous.end, current.start):
                raise SectionGeometryError("linha média dobrada possui gap")
            before = _unit_tangent(previous, True)
            after = _unit_tangent(current, False)
            if before[0] * after[0] + before[1] * after[1] < 1.0 - 1.0e-9:
                raise SectionGeometryError("segmentos da linha média não são tangentes")
        _validate_no_self_intersection(self.mean_path, "linha média")

    @property
    def inner_radius(self):
        arcs = tuple(segment for segment in self.mean_path.segments
                     if isinstance(segment, ArcSegment2D))
        if not arcs:
            return None
        radii = {round(arc.radius - self.thickness / 2.0, 9) for arc in arcs}
        return radii.pop() if len(radii) == 1 else None

    @property
    def mean_radius(self):
        arcs = tuple(segment for segment in self.mean_path.segments
                     if isinstance(segment, ArcSegment2D))
        if not arcs:
            return None
        radii = {round(arc.radius, 9) for arc in arcs}
        return radii.pop() if len(radii) == 1 else None

    @property
    def outer_radius(self):
        radius = self.mean_radius
        return None if radius is None else radius + self.thickness / 2.0

    def physical_contour(self):
        half = self.thickness / 2.0
        left = tuple(_offset_segment(segment, half)
                     for segment in self.mean_path.segments)
        right = tuple(_offset_segment(segment, -half)
                      for segment in self.mean_path.segments)
        # Tangent source segments guarantee matching offset endpoints.  Snap the
        # tiny floating differences so SectionPath2D retains exact topology.
        def snapped(segments):
            result = [segments[0]]
            for segment in segments[1:]:
                start = result[-1].end
                if isinstance(segment, ArcSegment2D):
                    result.append(ArcSegment2D(start, segment.end, segment.center,
                                               segment.clockwise))
                else:
                    result.append(LineSegment2D(start, segment.end))
            return tuple(result)
        left, right = snapped(left), snapped(right)
        end_cap = LineSegment2D(left[-1].end, right[-1].end)
        reversed_right = tuple(_reverse_segment(segment) for segment in reversed(right))
        start_cap = LineSegment2D(reversed_right[-1].end, left[0].start)
        contour = SectionPath2D(left + (end_cap,) + reversed_right + (start_cap,), True)
        if contour.area <= _TOLERANCE:
            raise SectionGeometryError("contorno físico possui área nula")
        _validate_no_self_intersection(contour, "contorno físico")
        return contour


def _gauss_integrals(path):
    nodes = (-0.9602898564975363, -0.7966664774136267,
             -0.5255324099163290, -0.1834346424956498,
              0.1834346424956498,  0.5255324099163290,
              0.7966664774136267,  0.9602898564975363)
    weights = (0.1012285362903763, 0.2223810344533745,
               0.3137066458778873, 0.3626837833783620,
               0.3626837833783620, 0.3137066458778873,
               0.2223810344533745, 0.1012285362903763)
    values = [0.0] * 5  # area, first x/y moments, Ix0, Iy0
    for segment in path.segments:
        if isinstance(segment, LineSegment2D):
            def evaluate(u):
                return (segment.start.x + (segment.end.x - segment.start.x) * u,
                        segment.start.y + (segment.end.y - segment.start.y) * u,
                        segment.end.x - segment.start.x,
                        segment.end.y - segment.start.y)
        else:
            def evaluate(u, segment=segment):
                angle = segment.start_angle + segment.sweep * u
                derivative = segment.sweep
                return (segment.center.x + segment.radius * math.cos(angle),
                        segment.center.y + segment.radius * math.sin(angle),
                        -segment.radius * math.sin(angle) * derivative,
                        segment.radius * math.cos(angle) * derivative)
        for node, weight in zip(nodes, weights):
            x, y, dx, dy = evaluate((node + 1.0) / 2.0)
            factor = weight / 2.0
            values[0] += factor * (x * dy - y * dx) / 2.0
            values[1] += factor * x * x * dy / 2.0
            values[2] -= factor * y * y * dx / 2.0
            values[3] -= factor * y ** 3 * dx / 3.0
            values[4] += factor * x ** 3 * dy / 3.0
    return tuple(values)


@dataclass(frozen=True)
class PhysicalSectionProperties2D:
    area: float
    centroid_x: float
    centroid_y: float
    ix: float
    iy: float


def physical_section_properties(path):
    """Return exact-to-quadrature area, centroid and centroidal Ix/Iy."""
    area, qx, qy, ix0, iy0 = _gauss_integrals(path)
    if abs(area) <= _TOLERANCE:
        raise SectionGeometryError("propriedades requerem área positiva")
    sign = 1.0 if area > 0.0 else -1.0
    area *= sign
    qx, qy, ix0, iy0 = (value * sign for value in (qx, qy, ix0, iy0))
    cx, cy = qx / area, qy / area
    return PhysicalSectionProperties2D(
        area, cx, cy, ix0 - area * cy * cy, iy0 - area * cx * cx
    )


def translated_path(path, dx, dy):
    def point(value):
        return Point2D(value.x + dx, value.y + dy)
    segments = []
    for segment in path.segments:
        if isinstance(segment, ArcSegment2D):
            segments.append(ArcSegment2D(point(segment.start), point(segment.end),
                                         point(segment.center), segment.clockwise))
        else:
            segments.append(LineSegment2D(point(segment.start), point(segment.end)))
    return SectionPath2D(tuple(segments), path.closed)


def section_geometry_from_cold_formed(path, *, geometry_type, geometry_variant):
    contour = path.physical_contour()
    properties = physical_section_properties(contour)
    centered = translated_path(contour, -properties.centroid_x, -properties.centroid_y)
    points = _sample_path(centered, 32)
    return SectionGeometry2D(
        geometry_type=geometry_type,
        geometry_variant=geometry_variant,
        outer_path=centered,
        inner_paths=(),
        bounds=SectionBounds2D(
            min(point.x for point in points), max(point.x for point in points),
            min(point.y for point in points), max(point.y for point in points),
        ),
        origin=Point2D(0.0, 0.0),
    )


__all__ = [
    "ColdFormedPath2D", "PhysicalSectionProperties2D", "SegmentIntersections2D",
    "angle_on_arc", "arc_arc_intersections", "path_self_intersections",
    "physical_section_properties", "section_geometry_from_cold_formed",
    "segment_arc_intersections", "segment_segment_intersections", "translated_path",
]
