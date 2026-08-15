# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure presentation data for structural profile catalog interfaces."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ProfileDefinition


@dataclass(frozen=True)
class PresentationRow:
    label: str
    value: str
    tooltip: str | None = None


@dataclass(frozen=True)
class PresentationGroup:
    title: str
    rows: tuple[PresentationRow, ...]


_DIMENSION_LABELS = {
    "d": "d", "bf": "bf", "tw": "tw", "tf": "tf",
    "h": "h", "d_prime": "d'", "b": "b", "t": "t",
}
_PROPERTY_SPECS = {
    "ix": ("Ix", 1e-4, "cm⁴", "Momento de inércia em torno do eixo X-X"),
    "wx": ("Wx", 1e-3, "cm³", "Módulo resistente elástico no eixo X-X"),
    "zx": ("Zx", 1e-3, "cm³", "Módulo resistente plástico no eixo X-X"),
    "rx": ("rx", 0.1, "cm", "Raio de giração no eixo X-X"),
    "iy": ("Iy", 1e-4, "cm⁴", "Momento de inércia em torno do eixo Y-Y"),
    "wy": ("Wy", 1e-3, "cm³", "Módulo resistente elástico no eixo Y-Y"),
    "zy": ("Zy", 1e-3, "cm³", "Módulo resistente plástico no eixo Y-Y"),
    "ry": ("ry", 0.1, "cm", "Raio de giração no eixo Y-Y"),
    "rt": ("rt", 0.1, "cm", "Raio efetivo para flambagem lateral com torção"),
    "it": ("It", 1e-4, "cm⁴", "Constante de torção"),
    "cw": ("Cw", 1e-6, "cm⁶", "Constante de empenamento"),
    "rz_min": ("rz mín.", 0.1, "cm", "Raio de giração mínimo"),
    "slenderness_flange": ("bf / 2tf", 1.0, "", None),
    "slenderness_web": ("d' / tw", 1.0, "", None),
}


def format_number(value: float, decimals: int | None = None) -> str:
    """Format a number for pt-BR without changing its stored value."""
    if decimals is None:
        decimals = 0 if float(value).is_integer() else min(2, len(f"{value:.6f}".rstrip("0").split(".")[-1]))
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def format_engineering_value(value: float, scale: float, unit: str, decimals=None) -> str:
    rendered = format_number(value * scale, decimals)
    return f"{rendered} {unit}".rstrip()


def profile_dimension_rows(profile: ProfileDefinition) -> tuple[PresentationRow, ...]:
    return tuple(
        PresentationRow(_DIMENSION_LABELS[key], format_engineering_value(value, 1.0, "mm"))
        for key, value in profile.geometry.items() if key in _DIMENSION_LABELS
    )


def profile_preview_dimension_rows(profile: ProfileDefinition) -> tuple[PresentationRow, ...]:
    """Return only the principal dimensions annotated by the supported preview."""
    if (profile.geometry_type, profile.geometry_variant) != ("i_section", "parallel_flange"):
        return ()
    return tuple(
        PresentationRow(key, format_engineering_value(profile.geometry[key], 1.0, "mm"))
        for key in ("d", "bf", "tw", "tf") if key in profile.geometry
    )


def _property_rows(profile, keys):
    rows = []
    for key in keys:
        if key not in profile.section_properties:
            continue
        label, scale, unit, tooltip = _PROPERTY_SPECS[key]
        rows.append(PresentationRow(
            label, format_engineering_value(profile.section_properties[key], scale, unit), tooltip
        ))
    return tuple(rows)


def profile_property_groups(profile: ProfileDefinition) -> tuple[PresentationGroup, ...]:
    physical = profile.physical_properties
    physical_rows = []
    if physical.mass_per_length_kg_m is not None:
        physical_rows.append(PresentationRow(
            "Massa linear", format_engineering_value(physical.mass_per_length_kg_m, 1.0, "kg/m", 1)
        ))
    if physical.area_mm2 is not None:
        physical_rows.append(PresentationRow(
            "Área", format_engineering_value(physical.area_mm2, 0.01, "cm²", 1)
        ))
    if physical.surface_area_per_length_m2_m is not None:
        physical_rows.append(PresentationRow(
            "Superfície", format_engineering_value(physical.surface_area_per_length_m2_m, 1.0, "m²/m", 2)
        ))
    groups = [PresentationGroup("Físicas", tuple(physical_rows))]
    for title, keys in (
        ("Eixo X-X", ("ix", "wx", "zx", "rx")),
        ("Eixo Y-Y", ("iy", "wy", "zy", "ry")),
        ("Torção / estabilidade", ("rt", "it", "cw", "slenderness_flange", "slenderness_web")),
    ):
        rows = _property_rows(profile, keys)
        if rows:
            groups.append(PresentationGroup(title, rows))
    centroid = []
    if "x" in profile.centroid:
        centroid.append(PresentationRow(
            "x do centroide", format_engineering_value(profile.centroid["x"], 0.1, "cm")
        ))
    rz_rows = _property_rows(profile, ("rz_min",))
    centroid.extend(rz_rows)
    if centroid:
        groups.append(PresentationGroup("Centroide / eixos principais", tuple(centroid)))
    return tuple(group for group in groups if group.rows)


def profile_source_rows(profile: ProfileDefinition) -> tuple[PresentationRow, ...]:
    source = profile.catalog.source
    rows = [
        PresentationRow("Fabricante", profile.manufacturer.name),
        PresentationRow("Catálogo", source.source_name),
    ]
    if source.source_revision:
        rows.append(PresentationRow("Revisão", source.source_revision))
    if profile.equivalent_designation:
        rows.append(PresentationRow("Designação imperial", profile.equivalent_designation))
    if profile.catalog_markers:
        rows.append(PresentationRow("Marcadores do catálogo", ", ".join(profile.catalog_markers)))
    if profile.availability_status == "made_to_order":
        rows.append(PresentationRow("Disponibilidade", "Sob encomenda"))
    if profile.geometry_type == "i_section" and profile.geometry_variant == "parallel_flange":
        if profile.catalog.standard_references:
            rows.append(PresentationRow("Normas", "; ".join(profile.catalog.standard_references)))
        if profile.catalog.material_notes:
            rows.append(PresentationRow("Material", profile.catalog.material_notes))
    if source.notes:
        rows.append(PresentationRow("Notas", source.notes))
    return tuple(rows)


def profile_basic_rows(profile: ProfileDefinition, series_name: str) -> tuple[PresentationRow, ...]:
    rows = [
        PresentationRow("Série", series_name),
        PresentationRow("Fabricante", profile.manufacturer.name),
    ]
    return tuple(rows)


__all__ = [
    "PresentationGroup", "PresentationRow", "format_engineering_value", "format_number",
    "profile_basic_rows", "profile_dimension_rows", "profile_preview_dimension_rows",
    "profile_property_groups", "profile_source_rows",
]
