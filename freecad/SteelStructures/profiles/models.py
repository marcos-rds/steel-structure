# SPDX-License-Identifier: LGPL-2.1-or-later
"""Immutable domain models for structural profile catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def immutable_mapping(values: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Return a detached, read-only mapping suitable for frozen models."""
    return MappingProxyType(dict(values or {}))


@dataclass(frozen=True)
class ProfileRef:
    catalog_id: str
    profile_id: str


@dataclass(frozen=True)
class CatalogSource:
    source_name: str
    source_revision: str | None = None
    source_url: str | None = None
    source_date: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ManufacturerDefinition:
    id: str
    name: str


@dataclass(frozen=True)
class CatalogMetadata:
    id: str
    name: str
    catalog_version: str
    manufacturer: ManufacturerDefinition
    source: CatalogSource
    units: Mapping[str, str]
    standard_references: tuple[str, ...] = ()
    material_notes: str | None = None


@dataclass(frozen=True)
class CategoryDefinition:
    catalog_id: str
    id: str
    name: str


@dataclass(frozen=True)
class SeriesDefinition:
    catalog_id: str
    id: str
    category_id: str
    name: str
    family: str
    geometry_type: str


@dataclass(frozen=True)
class PhysicalProperties:
    mass_per_length_kg_m: float | None = None
    area_mm2: float | None = None
    surface_area_per_length_m2_m: float | None = None


@dataclass(frozen=True)
class ProfileDefinition:
    ref: ProfileRef
    designation: str
    equivalent_designation: str | None
    aliases: tuple[str, ...]
    catalog_markers: tuple[str, ...]
    availability_status: str
    series_id: str
    category_id: str
    manufacturer: ManufacturerDefinition
    family: str
    geometry_type: str
    geometry: Mapping[str, float]
    physical_properties: PhysicalProperties
    section_properties: Mapping[str, float]
    catalog: CatalogMetadata
