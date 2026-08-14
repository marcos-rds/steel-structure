# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schema-v2 validation and canonical unit conversion."""

from __future__ import annotations

import math
import re
from decimal import Decimal
from pathlib import Path

from .models import (
    CatalogMetadata,
    CatalogSource,
    CategoryDefinition,
    ManufacturerDefinition,
    PhysicalProperties,
    ProfileDefinition,
    ProfileRef,
    SeriesDefinition,
    immutable_mapping,
)

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
UNIT_FACTORS = {
    "length": {"mm": 1.0},
    "centroid": {"mm": 1.0, "cm": 10.0},
    "radius_of_gyration": {"mm": 1.0, "cm": 10.0},
    "area": {"mm2": 1.0, "cm2": 100.0},
    "mass_per_length": {"kg/m": 1.0},
    "section_modulus": {"mm3": 1.0, "cm3": 1_000.0},
    "second_moment_of_area": {"mm4": 1.0, "cm4": 10_000.0},
    "warping_constant": {"mm6": 1.0, "cm6": 1_000_000.0},
    "surface_area_per_length": {"m2/m": 1.0},
    "dimensionless": {"1": 1.0},
}
SECTION_PROPERTY_QUANTITIES = {
    "ix": "second_moment_of_area",
    "iy": "second_moment_of_area",
    "j": "second_moment_of_area",
    "it": "second_moment_of_area",
    "wx": "section_modulus",
    "wy": "section_modulus",
    "zx": "section_modulus",
    "zy": "section_modulus",
    "rx": "radius_of_gyration",
    "ry": "radius_of_gyration",
    "rt": "radius_of_gyration",
    "rz_min": "radius_of_gyration",
    "cw": "warping_constant",
    "slenderness_flange": "dimensionless",
    "slenderness_web": "dimensionless",
}

AVAILABILITY_STATUSES = {"standard", "made_to_order"}


class CatalogError(Exception):
    """Base error for the typed profile-catalog API."""


class CatalogValidationError(CatalogError):
    """Raised when a catalog does not satisfy schema v2."""


class ProfileNotFoundError(CatalogError):
    """Raised when a ProfileRef is not present in the library."""


def _error(path: Path, catalog_id: str, message: str) -> CatalogValidationError:
    return CatalogValidationError(f"{path.name} [{catalog_id}]: {message}")


def _mapping(value, path, catalog_id, field):
    if not isinstance(value, dict):
        raise _error(path, catalog_id, f"{field} deve ser um objeto")
    return value


def _list(value, path, catalog_id, field):
    if not isinstance(value, list):
        raise _error(path, catalog_id, f"{field} deve ser uma lista")
    return value


def _string(value, path, catalog_id, field, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _error(path, catalog_id, f"{field} deve ser uma string não vazia")
    return value.strip()


def _id(value, path, catalog_id, field):
    value = _string(value, path, catalog_id, field)
    if not value.isascii() or not ID_PATTERN.fullmatch(value):
        raise _error(path, catalog_id, f"{field} possui ID inválido: {value!r}")
    return value


def _number(value, path, catalog_id, field, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(path, catalog_id, f"{field} deve ser numérico")
    result = float(value)
    if not math.isfinite(result):
        raise _error(path, catalog_id, f"{field} não pode ser NaN ou infinito")
    if positive and result <= 0.0:
        raise _error(path, catalog_id, f"{field} deve ser positivo")
    return result


def convert_to_canonical(value, quantity: str, unit: str) -> float:
    """Convert a finite value to the canonical mm-based internal system."""
    if quantity not in UNIT_FACTORS or unit not in UNIT_FACTORS[quantity]:
        raise CatalogValidationError(
            f"unidade desconhecida para {quantity}: {unit!r}"
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CatalogValidationError(f"valor não numérico para {quantity}")
    result = float(value)
    if not math.isfinite(result):
        raise CatalogValidationError(f"valor não finito para {quantity}")
    return float(Decimal(str(value)) * Decimal(str(UNIT_FACTORS[quantity][unit])))


def _validate_units(raw, path, catalog_id):
    raw = _mapping(raw, path, catalog_id, "units")
    required = ("length", "mass_per_length", "area")
    units = {}
    for quantity in required:
        unit = _string(raw.get(quantity), path, catalog_id, f"units.{quantity}")
        if unit not in UNIT_FACTORS[quantity]:
            raise _error(
                path, catalog_id,
                f"units.{quantity} possui unidade desconhecida: {unit!r}",
            )
        units[quantity] = unit
    for quantity, unit in raw.items():
        if quantity not in UNIT_FACTORS:
            raise _error(path, catalog_id, f"grupo de unidade desconhecido: {quantity!r}")
        if unit not in UNIT_FACTORS[quantity]:
            raise _error(path, catalog_id, f"units.{quantity} possui unidade desconhecida: {unit!r}")
        units[quantity] = unit
    return immutable_mapping(units)


def validate_catalog_payload(payload, path: Path):
    """Validate one schema-v2 payload and build immutable domain objects."""
    path = Path(path)
    if not isinstance(payload, dict):
        raise _error(path, "unknown", "a raiz deve ser um objeto")
    if payload.get("schema_version") != 2:
        raise _error(path, "unknown", "schema_version deve ser 2")

    raw_catalog = _mapping(payload.get("catalog"), path, "unknown", "catalog")
    catalog_id = _id(raw_catalog.get("id"), path, "unknown", "catalog.id")
    manufacturer_raw = _mapping(
        raw_catalog.get("manufacturer"), path, catalog_id, "catalog.manufacturer"
    )
    manufacturer = ManufacturerDefinition(
        id=_id(manufacturer_raw.get("id"), path, catalog_id, "manufacturer.id"),
        name=_string(manufacturer_raw.get("name"), path, catalog_id, "manufacturer.name"),
    )
    source_raw = _mapping(raw_catalog.get("source"), path, catalog_id, "catalog.source")
    source = CatalogSource(
        source_name=_string(source_raw.get("source_name"), path, catalog_id, "source.source_name"),
        source_revision=_string(source_raw.get("source_revision"), path, catalog_id, "source.source_revision", True),
        source_url=_string(source_raw.get("source_url"), path, catalog_id, "source.source_url", True),
        source_date=_string(source_raw.get("source_date"), path, catalog_id, "source.source_date", True),
        notes=_string(source_raw.get("notes"), path, catalog_id, "source.notes", True),
    )
    units = _validate_units(payload.get("units"), path, catalog_id)
    metadata = CatalogMetadata(
        id=catalog_id,
        name=_string(raw_catalog.get("name"), path, catalog_id, "catalog.name"),
        catalog_version=_string(raw_catalog.get("catalog_version"), path, catalog_id, "catalog.catalog_version"),
        manufacturer=manufacturer,
        source=source,
        units=units,
        standard_references=tuple(
            _string(value, path, catalog_id, "catalog.standard_references")
            for value in _list(raw_catalog.get("standard_references", []), path, catalog_id, "catalog.standard_references")
        ),
        material_notes=_string(raw_catalog.get("material_notes"), path, catalog_id, "catalog.material_notes", True),
    )

    categories = []
    category_ids = set()
    for index, raw in enumerate(_list(payload.get("categories"), path, catalog_id, "categories")):
        raw = _mapping(raw, path, catalog_id, f"categories[{index}]")
        category_id = _id(raw.get("id"), path, catalog_id, f"categories[{index}].id")
        if category_id in category_ids:
            raise _error(path, catalog_id, f"categoria duplicada: {category_id}")
        category_ids.add(category_id)
        categories.append(CategoryDefinition(catalog_id, category_id, _string(raw.get("name"), path, catalog_id, f"categories[{index}].name")))

    series = []
    series_by_id = {}
    for index, raw in enumerate(_list(payload.get("series"), path, catalog_id, "series")):
        raw = _mapping(raw, path, catalog_id, f"series[{index}]")
        series_id = _id(raw.get("id"), path, catalog_id, f"series[{index}].id")
        if series_id in series_by_id:
            raise _error(path, catalog_id, f"série duplicada: {series_id}")
        category_id = _id(raw.get("category_id"), path, catalog_id, f"series[{index}].category_id")
        if category_id not in category_ids:
            raise _error(path, catalog_id, f"série {series_id} referencia categoria inexistente: {category_id}")
        definition = SeriesDefinition(
            catalog_id, series_id, category_id,
            _string(raw.get("name"), path, catalog_id, f"series[{index}].name"),
            _string(raw.get("family"), path, catalog_id, f"series[{index}].family"),
            _string(raw.get("geometry_type"), path, catalog_id, f"series[{index}].geometry_type"),
            _string(raw.get("geometry_variant"), path, catalog_id, f"series[{index}].geometry_variant", True),
            _string(raw.get("geometry_notes"), path, catalog_id, f"series[{index}].geometry_notes", True),
        )
        series_by_id[series_id] = definition
        series.append(definition)

    profiles = []
    profile_ids = set()
    designations_by_series = set()
    for index, raw in enumerate(_list(payload.get("profiles"), path, catalog_id, "profiles")):
        raw = _mapping(raw, path, catalog_id, f"profiles[{index}]")
        profile_id = _id(raw.get("id"), path, catalog_id, f"profiles[{index}].id")
        if profile_id in profile_ids:
            raise _error(path, catalog_id, f"perfil duplicado: {profile_id}")
        profile_ids.add(profile_id)
        series_id = _id(raw.get("series_id"), path, catalog_id, f"profiles[{index}].series_id")
        if series_id not in series_by_id:
            raise _error(path, catalog_id, f"perfil {profile_id} referencia série inexistente: {series_id}")
        series_definition = series_by_id[series_id]
        designation = _string(raw.get("designation"), path, catalog_id, f"profiles[{index}].designation")
        designation_key = (series_id, designation)
        if designation_key in designations_by_series:
            raise _error(path, catalog_id, f"designação duplicada na série {series_id}: {designation!r}")
        designations_by_series.add(designation_key)
        geometry_type = _string(raw.get("geometry_type"), path, catalog_id, f"profiles[{index}].geometry_type")
        geometry_raw = _mapping(raw.get("geometry"), path, catalog_id, f"profiles[{index}].geometry")
        geometry = {}
        if geometry_type in {"i_section", "channel_section", "tee_section"}:
            for parameter in ("d", "bf", "tw", "tf"):
                geometry[parameter] = convert_to_canonical(
                    _number(geometry_raw.get(parameter), path, catalog_id, f"profiles[{index}].geometry.{parameter}", True),
                    "length", units["length"],
                )
            for parameter in ("h", "d_prime"):
                if parameter in geometry_raw:
                    geometry[parameter] = convert_to_canonical(
                        _number(geometry_raw.get(parameter), path, catalog_id, f"profiles[{index}].geometry.{parameter}", True),
                        "length", units["length"],
                    )
            if geometry["tw"] >= geometry["bf"]:
                raise _error(path, catalog_id, f"perfil {profile_id}: tw deve ser menor que bf")
            if geometry_type in {"i_section", "channel_section"} and 2.0 * geometry["tf"] >= geometry["d"]:
                raise _error(path, catalog_id, f"perfil {profile_id}: 2*tf deve ser menor que d")
            if geometry_type == "tee_section" and geometry["tf"] >= geometry["d"]:
                raise _error(path, catalog_id, f"perfil {profile_id}: tf deve ser menor que d")
        elif geometry_type == "equal_angle":
            for parameter in ("b", "t"):
                geometry[parameter] = convert_to_canonical(
                    _number(geometry_raw.get(parameter), path, catalog_id, f"profiles[{index}].geometry.{parameter}", True),
                    "length", units["length"],
                )
            if geometry["t"] >= geometry["b"]:
                raise _error(path, catalog_id, f"perfil {profile_id}: t deve ser menor que b")
        else:
            raise _error(path, catalog_id, f"geometry_type não suportado: {geometry_type!r}")

        physical_raw = _mapping(raw.get("physical_properties", {}), path, catalog_id, f"profiles[{index}].physical_properties")
        mass = physical_raw.get("mass_per_length")
        area = physical_raw.get("area")
        surface = physical_raw.get("surface_area_per_length")
        physical = PhysicalProperties(
            mass_per_length_kg_m=None if mass is None else convert_to_canonical(
                _number(mass, path, catalog_id, f"profiles[{index}].physical_properties.mass_per_length", True),
                "mass_per_length", units["mass_per_length"],
            ),
            area_mm2=None if area is None else convert_to_canonical(
                _number(area, path, catalog_id, f"profiles[{index}].physical_properties.area", True),
                "area", units["area"],
            ),
            surface_area_per_length_m2_m=None if surface is None else convert_to_canonical(
                _number(surface, path, catalog_id, f"profiles[{index}].physical_properties.surface_area_per_length", True),
                "surface_area_per_length", units["surface_area_per_length"],
            ),
        )
        section_raw = _mapping(raw.get("section_properties", {}), path, catalog_id, f"profiles[{index}].section_properties")
        section = {}
        for key, value in section_raw.items():
            quantity = SECTION_PROPERTY_QUANTITIES.get(key.casefold())
            if quantity is None:
                raise _error(path, catalog_id, f"propriedade de seção desconhecida: {key!r}")
            if quantity not in units:
                raise _error(path, catalog_id, f"units.{quantity} é necessária para {key}")
            section[key] = convert_to_canonical(
                _number(value, path, catalog_id, f"profiles[{index}].section_properties.{key}", True),
                quantity, units[quantity],
            )
        centroid_raw = _mapping(raw.get("centroid", {}), path, catalog_id, f"profiles[{index}].centroid")
        centroid = {}
        for key, value in centroid_raw.items():
            if key != "x":
                raise _error(path, catalog_id, f"coordenada de centroide desconhecida: {key!r}")
            centroid[key] = convert_to_canonical(
                _number(value, path, catalog_id, f"profiles[{index}].centroid.{key}", True),
                "centroid", units.get("centroid", units["length"]),
            )
        aliases_raw = _list(raw.get("aliases", []), path, catalog_id, f"profiles[{index}].aliases")
        aliases = tuple(_string(value, path, catalog_id, f"profiles[{index}].aliases") for value in aliases_raw)
        markers_raw = _list(raw.get("catalog_markers", []), path, catalog_id, f"profiles[{index}].catalog_markers")
        markers = tuple(_string(value, path, catalog_id, f"profiles[{index}].catalog_markers") for value in markers_raw)
        if len(markers) != len(set(markers)):
            raise _error(path, catalog_id, f"perfil {profile_id}: catalog_markers duplicados")
        availability = _string(raw.get("availability_status"), path, catalog_id, f"profiles[{index}].availability_status")
        if availability not in AVAILABILITY_STATUSES:
            raise _error(path, catalog_id, f"perfil {profile_id}: availability_status inválido: {availability!r}")
        profiles.append(ProfileDefinition(
            ref=ProfileRef(catalog_id, profile_id),
            designation=designation,
            equivalent_designation=_string(raw.get("equivalent_designation"), path, catalog_id, f"profiles[{index}].equivalent_designation", True),
            aliases=aliases,
            catalog_markers=markers,
            availability_status=availability,
            series_id=series_id,
            category_id=series_definition.category_id,
            manufacturer=manufacturer,
            family=series_definition.family,
            geometry_type=geometry_type,
            geometry=immutable_mapping(geometry),
            physical_properties=physical,
            section_properties=immutable_mapping(section),
            centroid=immutable_mapping(centroid),
            catalog=metadata,
        ))
    return metadata, tuple(categories), tuple(series), tuple(profiles)
