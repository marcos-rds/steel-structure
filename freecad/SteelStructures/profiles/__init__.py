# SPDX-License-Identifier: LGPL-2.1-or-later
"""Typed structural-profile catalog domain API."""

from .catalog import ProfileLibrary, normalize_search_text
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
    "CatalogValidationError", "CategoryDefinition", "ManufacturerDefinition",
    "PhysicalProperties", "ProfileDefinition", "ProfileLibrary",
    "ProfileNotFoundError", "ProfileRef", "SeriesDefinition",
    "convert_to_canonical", "normalize_search_text",
]
