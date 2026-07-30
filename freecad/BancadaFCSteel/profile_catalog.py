# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profile catalog loading, filtering and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .paths import CATALOGS_DIR

# Categories already exposed in the interface. Aço dobrado is intentionally
# empty in v0.2.0 and is ready to receive future catalogs.
KNOWN_CATEGORIES = ["Aço laminado", "Aço dobrado"]


@dataclass(frozen=True)
class Profile:
    category: str
    series: str
    manufacturer: str
    family: str
    designation: str
    mass_per_m: float
    d: float
    bf: float
    tw: float
    tf: float
    area_cm2: float
    source: str


_CACHE: Dict[str, Profile] | None = None


def _catalog_files() -> List[Path]:
    return sorted(CATALOGS_DIR.glob("*.json"))


def _load() -> Dict[str, Profile]:
    result: Dict[str, Profile] = {}
    required = {
        "manufacturer",
        "family",
        "designation",
        "mass_per_m",
        "d",
        "bf",
        "tw",
        "tf",
        "area_cm2",
        "source",
    }

    for path in _catalog_files():
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        default_category = str(payload.get("category", "Aço laminado"))
        default_series = str(payload.get("series", ""))

        for item in payload.get("profiles", []):
            missing = required.difference(item)
            if missing:
                raise ValueError(
                    f"Perfil inválido em {path.name}; campos ausentes: {sorted(missing)}"
                )

            family = str(item["family"])
            category = str(item.get("category", default_category))
            series = str(item.get("series", default_series or f"Perfis {family}"))
            profile = Profile(
                category=category,
                series=series,
                manufacturer=str(item["manufacturer"]),
                family=family,
                designation=str(item["designation"]),
                mass_per_m=float(item["mass_per_m"]),
                d=float(item["d"]),
                bf=float(item["bf"]),
                tw=float(item["tw"]),
                tf=float(item["tf"]),
                area_cm2=float(item["area_cm2"]),
                source=str(item["source"]),
            )

            if min(profile.d, profile.bf, profile.tw, profile.tf, profile.area_cm2) <= 0:
                raise ValueError(f"Dimensão não positiva no perfil {profile.designation}")
            if profile.tw >= profile.bf or 2.0 * profile.tf >= profile.d:
                raise ValueError(f"Geometria incoerente no perfil {profile.designation}")
            if profile.designation in result:
                raise ValueError(f"Designação duplicada: {profile.designation}")
            result[profile.designation] = profile

    if not result:
        raise RuntimeError("Nenhum perfil foi encontrado no catálogo.")
    return result


def profiles() -> Dict[str, Profile]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load()
    return _CACHE


def categories() -> List[str]:
    found = []
    for name in KNOWN_CATEGORIES:
        if name not in found:
            found.append(name)
    for profile in profiles().values():
        if profile.category not in found:
            found.append(profile.category)
    return found


def series_for_category(category: str) -> List[str]:
    result = []
    for profile in profiles().values():
        if profile.category == category and profile.series not in result:
            result.append(profile.series)
    return result


def designations(category: str | None = None, series: str | None = None) -> List[str]:
    result = []
    for profile in profiles().values():
        if category is not None and profile.category != category:
            continue
        if series is not None and profile.series != series:
            continue
        result.append(profile.designation)
    return result


def get(designation: str) -> Profile:
    catalog = profiles()
    if designation not in catalog:
        raise KeyError(f"Perfil não encontrado: {designation}")
    return catalog[designation]
