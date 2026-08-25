# SPDX-License-Identifier: LGPL-2.1-or-later
"""Typed structural-profile catalog domain API."""

from .catalog import ProfileLibrary, canonicalize_designation, normalize_search_text
from .geometry import (
    ArcSegment2D,
    GeometryTemporarilyUnavailableError,
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
    build_standard_tee_section,
    build_tapered_flange_i_section,
    build_tapered_flange_channel_section,
    build_section_geometry,
    geometry_is_released,
)
from .insertion import (
    InsertionReference, insertion_reference, insertion_translation,
    section_insertion_references,
)
from .effective_properties import (
    GeometricSectionProperties, resolve_effective_section_properties,
    section_geometric_properties,
)
from .models import (
    CatalogMetadata,
    CatalogSource,
    CategoryDefinition,
    ManufacturerDefinition,
    PhysicalProperties,
    ProfileDefinition,
    ProfileRef,
    SectionPropertyOverride,
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
    "CatalogValidationError", "CategoryDefinition", "ArcSegment2D", "LineSegment2D",
    "ManufacturerDefinition", "PathSegment2D", "Point2D",
    "GeometryTemporarilyUnavailableError", "geometry_is_released",
    "PhysicalProperties", "ProfileDefinition", "ProfileLibrary",
    "ProfileNotFoundError", "ProfileRef", "SectionBounds2D",
    "SectionPropertyOverride",
    "SectionGeometry2D", "SectionGeometryError", "SectionPath2D",
    "SeriesDefinition", "UnsupportedSectionGeometryError",
    "build_equal_angle_section", "build_parallel_flange_i_section",
    "build_standard_tee_section",
    "build_tapered_flange_i_section",
    "build_tapered_flange_channel_section",
    "build_section_geometry",
    "InsertionReference", "insertion_reference", "insertion_translation",
    "section_insertion_references",
    "canonicalize_designation", "convert_to_canonical", "normalize_search_text",
    "GeometricSectionProperties", "resolve_effective_section_properties",
    "section_geometric_properties",
]
