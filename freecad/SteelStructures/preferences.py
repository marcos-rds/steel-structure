# SPDX-License-Identifier: LGPL-2.1-or-later
"""Persistent user preferences for structural creation tools."""

from __future__ import annotations

import math
from dataclasses import dataclass

import FreeCAD as App

from . import profile_catalog
from .member import INSERTION_OPTIONS


PREFERENCES_ROOT = "User parameter:BaseApp/Preferences/Mod/SteelStructures"
MEMBER_PREFERENCES = f"{PREFERENCES_ROOT}/CreateMember"
COLUMN_PREFERENCES = f"{PREFERENCES_ROOT}/CreateColumn"
DEFAULT_COLOR = (184.0 / 255.0, 184.0 / 255.0, 194.0 / 255.0)
DEFAULT_ROTATION = 0.0
DEFAULT_COLUMN_HEIGHT = 3000.0
DEFAULT_CONTINUE = True
MEMBER_ELEMENT_TYPES = ("Membro", "Viga", "Contraventamento")
ROTATION_MIN = -3600.0
ROTATION_MAX = 3600.0
HEIGHT_MAX = 1000000.0

_INSERTION_KEYS = {
    "Centroide": "center",
    "Face esquerda": "left",
    "Face direita": "right",
    "Face superior": "top",
    "Face inferior": "bottom",
    "Canto superior esquerdo": "top_left",
    "Canto superior direito": "top_right",
    "Canto inferior esquerdo": "bottom_left",
    "Canto inferior direito": "bottom_right",
    "Quina externa": "outer_corner",
    "Ponta superior": "top_tip",
    "Ponta direita": "right_tip",
    "Quina interna": "inner_corner",
}
_INSERTIONS_BY_KEY = {key: label for label, key in _INSERTION_KEYS.items()}


@dataclass(frozen=True)
class MemberCreationSettings:
    category: str
    series: str
    designation: str
    insertion: str
    rotation: float
    color: tuple[float, float, float]
    element_type: str


@dataclass(frozen=True)
class ColumnCreationSettings:
    category: str
    series: str
    designation: str
    insertion: str
    rotation: float
    color: tuple[float, float, float]
    height: float
    continue_creating: bool


def _default_profile():
    for category in profile_catalog.categories():
        for series in profile_catalog.series_for_category(category):
            designations = profile_catalog.designations(category, series)
            if designations:
                return profile_catalog.get(designations[0])
    raise RuntimeError("Nenhum perfil válido foi encontrado no catálogo.")


def _valid_profile(category, series, designation):
    try:
        profile = profile_catalog.get(str(designation))
    except (KeyError, TypeError, ValueError):
        return _default_profile()
    if profile.category != str(category) or profile.series != str(series):
        return _default_profile()
    return profile


def _profile_insertion_options(profile):
    resolver = getattr(profile_catalog, "insertion_options", None)
    return tuple(resolver(profile)) if resolver is not None else tuple(INSERTION_OPTIONS)


def _finite_in_range(value, default, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) and minimum <= number <= maximum else default


def _color(group):
    values = tuple(group.GetFloat(key, default) for key, default in zip(
        ("ColorRed", "ColorGreen", "ColorBlue"), DEFAULT_COLOR
    ))
    if all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values):
        return values
    return DEFAULT_COLOR


def _shared_settings(group):
    default = _default_profile()
    profile = _valid_profile(
        group.GetString("Category", default.category),
        group.GetString("Series", default.series),
        group.GetString("Designation", default.designation),
    )
    insertion = _INSERTIONS_BY_KEY.get(group.GetString("Insertion", "center"), "Centroide")
    valid_insertions = _profile_insertion_options(profile) or tuple(INSERTION_OPTIONS)
    if insertion not in valid_insertions:
        insertion = valid_insertions[0]
    rotation = _finite_in_range(
        group.GetFloat("RotationAngle", DEFAULT_ROTATION), DEFAULT_ROTATION,
        ROTATION_MIN, ROTATION_MAX,
    )
    return profile, insertion, rotation, _color(group)


def load_member_creation_settings():
    try:
        group = App.ParamGet(MEMBER_PREFERENCES)
        profile, insertion, rotation, color = _shared_settings(group)
        element_type = group.GetString("ElementType", "Membro")
    except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError):
        profile = _default_profile()
        insertion, rotation, color, element_type = (
            "Centroide", DEFAULT_ROTATION, DEFAULT_COLOR, "Membro"
        )
    if element_type not in MEMBER_ELEMENT_TYPES:
        element_type = "Membro"
    return MemberCreationSettings(
        profile.category, profile.series, profile.designation, insertion,
        rotation, color, element_type,
    )


def load_column_creation_settings():
    try:
        group = App.ParamGet(COLUMN_PREFERENCES)
        profile, insertion, rotation, color = _shared_settings(group)
        height = _finite_in_range(
            group.GetFloat("Height", DEFAULT_COLUMN_HEIGHT), DEFAULT_COLUMN_HEIGHT,
            0.01, HEIGHT_MAX,
        )
        continue_creating = bool(group.GetBool("ContinueCreating", DEFAULT_CONTINUE))
    except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError):
        profile = _default_profile()
        insertion, rotation, color = "Centroide", DEFAULT_ROTATION, DEFAULT_COLOR
        height, continue_creating = DEFAULT_COLUMN_HEIGHT, DEFAULT_CONTINUE
    return ColumnCreationSettings(
        profile.category, profile.series, profile.designation, insertion,
        rotation, color, height, continue_creating,
    )


def _save_shared(group, settings):
    profile = _valid_profile(settings.category, settings.series, settings.designation)
    valid_insertions = _profile_insertion_options(profile) or tuple(INSERTION_OPTIONS)
    insertion = settings.insertion if settings.insertion in valid_insertions else valid_insertions[0]
    rotation = _finite_in_range(
        settings.rotation, DEFAULT_ROTATION, ROTATION_MIN, ROTATION_MAX
    )
    color = settings.color
    if (len(color) != 3 or not all(
            math.isfinite(float(value)) and 0.0 <= float(value) <= 1.0
            for value in color)):
        color = DEFAULT_COLOR
    group.SetString("Category", profile.category)
    group.SetString("Series", profile.series)
    group.SetString("Designation", profile.designation)
    group.SetString("Insertion", _INSERTION_KEYS[insertion])
    group.SetFloat("RotationAngle", rotation)
    for key, value in zip(("ColorRed", "ColorGreen", "ColorBlue"), color):
        group.SetFloat(key, float(value))


def save_member_creation_settings(settings):
    try:
        group = App.ParamGet(MEMBER_PREFERENCES)
        _save_shared(group, settings)
        element_type = settings.element_type if settings.element_type in MEMBER_ELEMENT_TYPES else "Membro"
        group.SetString("ElementType", element_type)
    except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError):
        return False
    return True


def save_column_creation_settings(settings):
    try:
        group = App.ParamGet(COLUMN_PREFERENCES)
        _save_shared(group, settings)
        height = _finite_in_range(
            settings.height, DEFAULT_COLUMN_HEIGHT, 0.01, HEIGHT_MAX
        )
        group.SetFloat("Height", height)
        group.SetBool("ContinueCreating", bool(settings.continue_creating))
    except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError):
        return False
    return True


__all__ = [
    "COLUMN_PREFERENCES", "MEMBER_PREFERENCES", "PREFERENCES_ROOT",
    "ColumnCreationSettings", "MemberCreationSettings",
    "load_column_creation_settings", "load_member_creation_settings",
    "save_column_creation_settings", "save_member_creation_settings",
]
