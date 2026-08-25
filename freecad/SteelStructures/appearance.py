# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared Steel Structures appearance choices without Qt dependencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPreset:
    name: str
    rgb: tuple[int, int, int]

    def __post_init__(self):
        if not self.name or len(self.rgb) != 3:
            raise ValueError("predefinição de cor inválida")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255
            for value in self.rgb
        ):
            raise ValueError("componentes RGB devem estar entre 0 e 255")

    @property
    def hex(self):
        return "#%02X%02X%02X" % self.rgb


STEEL_COLOR_PALETTE = (
    ColorPreset("Azul", (47, 125, 225)),
    ColorPreset("Turquesa", (18, 174, 181)),
    ColorPreset("Verde", (53, 184, 90)),
    ColorPreset("Amarelo", (229, 195, 47)),
    ColorPreset("Laranja", (240, 138, 50)),
    ColorPreset("Vermelho", (227, 75, 75)),
    ColorPreset("Magenta", (217, 79, 163)),
    ColorPreset("Violeta", (132, 87, 217)),
)


def matching_palette_index(rgb, palette=STEEL_COLOR_PALETTE):
    """Return the exact preset index; custom colors deliberately match nothing."""
    try:
        value = tuple(rgb)
    except TypeError:
        return None
    if len(value) != 3 or any(
        isinstance(component, bool)
        or not isinstance(component, int)
        or not 0 <= component <= 255
        for component in value
    ):
        return None
    return next((index for index, preset in enumerate(palette) if preset.rgb == value), None)


__all__ = ["ColorPreset", "STEEL_COLOR_PALETTE", "matching_palette_index"]
