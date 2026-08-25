# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure calculated section properties and catalog-backed effective values."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .geometry import ArcSegment2D, LineSegment2D, build_section_geometry
from .models import ProfileDefinition, immutable_mapping


@dataclass(frozen=True)
class GeometricSectionProperties:
    area: float
    centroid_x: float
    centroid_y: float
    ix: float
    iy: float


def _segment_state(segment, parameter):
    if isinstance(segment, LineSegment2D):
        dx = segment.end.x - segment.start.x
        dy = segment.end.y - segment.start.y
        return segment.start.x + dx * parameter, segment.start.y + dy * parameter, dx, dy
    if isinstance(segment, ArcSegment2D):
        angle = segment.start_angle + segment.sweep * parameter
        cosine, sine = math.cos(angle), math.sin(angle)
        rate = segment.sweep
        return (
            segment.center.x + segment.radius * cosine,
            segment.center.y + segment.radius * sine,
            -segment.radius * sine * rate,
            segment.radius * cosine * rate,
        )
    raise TypeError(f"segmento não suportado: {type(segment).__name__}")


def _adaptive_simpson(function, depth=18):
    start, end, middle = 0.0, 1.0, 0.5
    f_start, f_middle, f_end = function(start), function(middle), function(end)
    whole = (f_start + 4.0 * f_middle + f_end) / 6.0
    tolerance = max(1e-10, abs(whole) * 1e-12)

    def refine(left, right, f_left, f_mid, f_right, estimate, tol, remaining):
        center = (left + right) / 2.0
        left_mid, right_mid = (left + center) / 2.0, (center + right) / 2.0
        f_left_mid, f_right_mid = function(left_mid), function(right_mid)
        left_value = (center - left) * (f_left + 4.0 * f_left_mid + f_mid) / 6.0
        right_value = (right - center) * (f_mid + 4.0 * f_right_mid + f_right) / 6.0
        combined = left_value + right_value
        if remaining <= 0 or abs(combined - estimate) <= 15.0 * tol:
            return combined + (combined - estimate) / 15.0
        return (
            refine(left, center, f_left, f_left_mid, f_mid,
                   left_value, tol / 2.0, remaining - 1)
            + refine(center, right, f_mid, f_right_mid, f_right,
                     right_value, tol / 2.0, remaining - 1)
        )

    return refine(start, end, f_start, f_middle, f_end, whole, tolerance, depth)


def _path_integrals(path):
    totals = [0.0] * 5
    for segment in path.segments:
        def integrate(index):
            def value(parameter):
                x, y, dx, dy = _segment_state(segment, parameter)
                return (
                    0.5 * (x * dy - y * dx),
                    0.5 * x * x * dy,
                    -0.5 * y * y * dx,
                    -(y ** 3) * dx / 3.0,
                    (x ** 3) * dy / 3.0,
                )[index]
            return _adaptive_simpson(value)
        for index in range(5):
            totals[index] += integrate(index)
    return tuple(totals)


def section_geometric_properties(geometry):
    """Return centroidal area moments from the exact line/arc contour."""
    paths = ((geometry.outer_path, 1.0),) + tuple(
        (path, -1.0) for path in geometry.inner_paths
    )
    totals = [0.0] * 5
    for path, desired_sign in paths:
        values = _path_integrals(path)
        factor = desired_sign * (1.0 if values[0] >= 0.0 else -1.0)
        for index, value in enumerate(values):
            totals[index] += factor * value
    area, first_x, first_y, ix_origin, iy_origin = totals
    if area <= 0.0:
        raise ValueError("geometria deve possuir área positiva")
    centroid_x, centroid_y = first_x / area, first_y / area
    return GeometricSectionProperties(
        area, centroid_x, centroid_y,
        ix_origin - area * centroid_y ** 2,
        iy_origin - area * centroid_x ** 2,
    )


def resolve_effective_section_properties(profile: ProfileDefinition):
    """Apply one centralized, catalog-declared calculated-property decision."""
    override = profile.section_property_override
    if override is None:
        return profile
    if override.basis != "nominal_revit_geometry":
        raise ValueError(f"base de propriedade efetiva não suportada: {override.basis}")
    geometry = build_section_geometry(profile)
    calculated = section_geometric_properties(geometry)
    half_width = max(
        abs(geometry.bounds.min_x - calculated.centroid_x),
        abs(geometry.bounds.max_x - calculated.centroid_x),
    )
    values = {
        "iy": calculated.iy,
        "wy": calculated.iy / half_width,
        "ry": math.sqrt(calculated.iy / calculated.area),
    }
    effective = dict(profile.section_properties)
    for name in override.properties:
        effective[name] = values[name]
    return replace(profile, section_properties=immutable_mapping(effective))


__all__ = [
    "GeometricSectionProperties", "resolve_effective_section_properties",
    "section_geometric_properties",
]
