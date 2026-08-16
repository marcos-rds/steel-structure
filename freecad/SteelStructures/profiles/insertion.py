# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insertion references derived from the shared section geometry."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import Point2D, SectionGeometry2D


@dataclass(frozen=True)
class InsertionReference:
    id: str
    label: str
    point: Point2D


_I_LABELS = (
    ("centroid", "Centroide"),
    ("left", "Face esquerda"),
    ("right", "Face direita"),
    ("top", "Face superior"),
    ("bottom", "Face inferior"),
    ("top_left", "Canto superior esquerdo"),
    ("top_right", "Canto superior direito"),
    ("bottom_left", "Canto inferior esquerdo"),
    ("bottom_right", "Canto inferior direito"),
)


def section_insertion_references(geometry: SectionGeometry2D):
    """Return stable references supported by one section typology."""
    bounds = geometry.bounds
    key = (geometry.geometry_type, geometry.geometry_variant)
    if key == ("equal_angle", "equal_leg"):
        # Segment 3 starts at the re-entrant corner in the canonical L contour.
        inner = geometry.outer_path.segments[3].start
        values = (
            ("centroid", "Centroide", geometry.origin),
            ("outer_corner", "Quina externa", Point2D(bounds.min_x, bounds.min_y)),
            ("top_tip", "Ponta superior", Point2D(bounds.min_x, bounds.max_y)),
            ("right_tip", "Ponta direita", Point2D(bounds.max_x, bounds.min_y)),
            ("inner_corner", "Quina interna", inner),
        )
    elif key == ("i_section", "parallel_flange"):
        x0, y0 = geometry.origin.x, geometry.origin.y
        points = {
            "centroid": Point2D(x0, y0),
            "left": Point2D(bounds.min_x, y0),
            "right": Point2D(bounds.max_x, y0),
            "top": Point2D(x0, bounds.max_y),
            "bottom": Point2D(x0, bounds.min_y),
            "top_left": Point2D(bounds.min_x, bounds.max_y),
            "top_right": Point2D(bounds.max_x, bounds.max_y),
            "bottom_left": Point2D(bounds.min_x, bounds.min_y),
            "bottom_right": Point2D(bounds.max_x, bounds.min_y),
        }
        values = tuple((identifier, label, points[identifier]) for identifier, label in _I_LABELS)
    else:
        values = (("centroid", "Centroide", geometry.origin),)
    return tuple(InsertionReference(*value) for value in values)


def insertion_reference(geometry: SectionGeometry2D, value: str):
    """Resolve a stable id or current label, falling back to the centroid."""
    references = section_insertion_references(geometry)
    return next(
        (item for item in references if value in (item.id, item.label)), references[0]
    )


def insertion_translation(geometry: SectionGeometry2D, value: str):
    point = insertion_reference(geometry, value).point
    return -point.x, -point.y


__all__ = [
    "InsertionReference", "insertion_reference", "insertion_translation",
    "section_insertion_references",
]
