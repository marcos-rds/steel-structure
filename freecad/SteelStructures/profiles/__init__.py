# SPDX-License-Identifier: LGPL-2.1-or-later
"""Typed structural-profile catalog domain API."""

from .catalog import ProfileLibrary, normalize_search_text
from .geometry import (
    LineSegment2D,
    PathSegment2D,
    Point2D,
    SectionBounds2D,
    SectionGeometry2D,
    SectionGeometryError,
    SectionPath2D,
    UnsupportedSectionGeometryError,
    build_equal_angle_section,
    build_parallel_flange_i_section,
    build_section_geometry,
)
from .insertion import (
    InsertionReference, insertion_reference, insertion_translation,
    section_insertion_references,
)
from .models import (
    CatalogMetadata,
    CatalogSource,
    CategoryDefinition,
    ManufacturerDefinition,
    PhysicalProperties,
    ProfileDefinition,
    ProfileRef,
    SeriesDefinition,
)
from .validation import (
    CatalogError,
    CatalogValidationError,
    ProfileNotFoundError,
    convert_to_canonical,
)

__all__ = [
    "CatalogError", "CatalogMetadata", "CatalogSource",
    "CatalogValidationError", "CategoryDefinition", "LineSegment2D",
    "ManufacturerDefinition", "PathSegment2D", "Point2D",
    "PhysicalProperties", "ProfileDefinition", "ProfileLibrary",
    "ProfileNotFoundError", "ProfileRef", "SectionBounds2D",
    "SectionGeometry2D", "SectionGeometryError", "SectionPath2D",
    "SeriesDefinition", "UnsupportedSectionGeometryError",
    "build_equal_angle_section", "build_parallel_flange_i_section",
    "build_section_geometry",
    "InsertionReference", "insertion_reference", "insertion_translation",
    "section_insertion_references",
    "convert_to_canonical", "normalize_search_text",
]
