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
    elif key in (("i_section", "parallel_flange"),
                 ("i_section", "tapered_flange")):
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
    elif key == ("channel_section", "tapered_flange"):
        # Semantic U references come from its canonical right-opening contour.
        rear_bottom = geometry.outer_path.segments[0].start
        lower_tip = geometry.outer_path.segments[0].end
        inner_web_bottom = geometry.outer_path.segments[5].start
        upper_tip = geometry.outer_path.segments[10].start
        rear_top = geometry.outer_path.segments[10].end
        web_mid_x = (rear_bottom.x + inner_web_bottom.x) / 2.0
        values = (
            ("centroid", "Centroide", geometry.origin),
            ("web_center", "Centro da alma", Point2D(web_mid_x, 0.0)),
            ("web_back", "Face externa da alma", Point2D(rear_bottom.x, 0.0)),
            ("rear_top", "Canto superior traseiro", rear_top),
            ("rear_bottom", "Canto inferior traseiro", rear_bottom),
            ("flange_top_tip", "Ponta superior da mesa", upper_tip),
            ("flange_bottom_tip", "Ponta inferior da mesa", lower_tip),
        )
    elif key == ("tee_section", "standard_tee"):
        values = (
            ("centroid", "Centroide", geometry.origin),
            ("top", "Face superior", Point2D(geometry.origin.x, bounds.max_y)),
            ("bottom", "Ponta inferior da alma", Point2D(geometry.origin.x, bounds.min_y)),
            ("top_left", "Canto superior esquerdo", Point2D(bounds.min_x, bounds.max_y)),
            ("top_right", "Canto superior direito", Point2D(bounds.max_x, bounds.max_y)),
        )
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
