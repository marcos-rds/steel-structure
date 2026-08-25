# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure helpers used to render section geometry in technical previews."""

from .geometry import ArcSegment2D


def section_outline_points(geometry):
    """Return the canonical outline as points, sampling only curved segments."""
    points = [geometry.outer_path.segments[0].start]
    for segment in geometry.outer_path.segments:
        if isinstance(segment, ArcSegment2D):
            points.extend(segment.sampled_points())
        else:
            points.append(segment.end)
    return tuple(points)


__all__ = ["section_outline_points"]
