"""Contracts for the shared Steel Structures quick-color palette."""

from __future__ import annotations

import unittest
from pathlib import Path

from freecad.SteelStructures.appearance import (
    STEEL_COLOR_PALETTE, matching_palette_index,
)


ROOT = Path(__file__).resolve().parents[1]
MENU = ROOT / "freecad/SteelStructures/interactive/quick_color_menu.py"
OPTIONS = ROOT / "freecad/SteelStructures/interactive/profile_options_widget.py"
COLUMN = ROOT / "freecad/SteelStructures/interactive/column_task_panel.py"
MEMBER = ROOT / "freecad/SteelStructures/interactive/draft_member_tool.py"
ORIENTATION = ROOT / "freecad/SteelStructures/interactive/section_orientation_preview.py"


class QuickColorPaletteTests(unittest.TestCase):
    def test_palette_is_centralized_valid_unique_and_named(self):
        expected = (
            ("Azul", (47, 125, 225), "#2F7DE1"),
            ("Turquesa", (18, 174, 181), "#12AEB5"),
            ("Verde", (53, 184, 90), "#35B85A"),
            ("Amarelo", (229, 195, 47), "#E5C32F"),
            ("Laranja", (240, 138, 50), "#F08A32"),
            ("Vermelho", (227, 75, 75), "#E34B4B"),
            ("Magenta", (217, 79, 163), "#D94FA3"),
            ("Violeta", (132, 87, 217), "#8457D9"),
        )
        self.assertEqual(len(STEEL_COLOR_PALETTE), 8)
        self.assertEqual(len({preset.rgb for preset in STEEL_COLOR_PALETTE}), 8)
        self.assertEqual(
            tuple((preset.name, preset.rgb, preset.hex) for preset in STEEL_COLOR_PALETTE),
            expected,
        )
        self.assertFalse(
            any("cinza" in preset.name.casefold() for preset in STEEL_COLOR_PALETTE)
        )
        self.assertNotIn((0, 0, 0), {preset.rgb for preset in STEEL_COLOR_PALETTE})
        self.assertNotIn((255, 255, 255), {preset.rgb for preset in STEEL_COLOR_PALETTE})
        for preset in STEEL_COLOR_PALETTE:
            self.assertTrue(all(0 <= component <= 255 for component in preset.rgb))
            self.assertRegex(preset.hex, r"^#[0-9A-F]{6}$")

    def test_exact_preset_is_marked_but_custom_color_is_not_approximated(self):
        for index, preset in enumerate(STEEL_COLOR_PALETTE):
            self.assertEqual(matching_palette_index(preset.rgb), index)
        self.assertIsNone(matching_palette_index((184, 184, 194)))
        self.assertIsNone(matching_palette_index((55, 111, 165)))

    def test_matching_rejects_coercible_and_structurally_invalid_rgb_values(self):
        self.assertEqual(matching_palette_index((47, 125, 225)), 0)
        for value in (
            (47.0, 125, 225),
            (47.9, 125, 225),
            ("47", "125", "225"),
            (47, 125),
            (47, 125, 225, 0),
            (-1, 125, 225),
            (256, 125, 225),
        ):
            with self.subTest(value=value):
                self.assertIsNone(matching_palette_index(value))

    def test_popup_is_native_compact_accessible_and_keyboard_focusable(self):
        source = MENU.read_text(encoding="utf-8")
        self.assertIn("class QuickColorMenu(QtWidgets.QMenu):", source)
        self.assertIn("QtWidgets.QWidgetAction", source)
        self.assertIn("QtWidgets.QToolButton", source)
        self.assertIn("index // 4, index % 4", source)
        self.assertIn("button.setToolTip(preset.name)", source)
        self.assertIn("button.setAccessibleName(preset.name)", source)
        self.assertIn("QtCore.Qt.StrongFocus", source)
        self.assertIn("self.buttons[0].setFocus()", source)
        self.assertIn('self.addAction("Mais cores...")', source)

    def test_checked_state_uses_shape_and_custom_color_checks_nothing(self):
        source = MENU.read_text(encoding="utf-8")
        self.assertIn("button.setCheckable(True)", source)
        self.assertIn("QToolButton:checked { border: 3px solid", source)
        self.assertIn("button.setChecked(button_index == index)", source)
        self.assertIn("matching_palette_index", source)

    def test_swatch_opens_popup_and_both_paths_share_color_application(self):
        source = OPTIONS.read_text(encoding="utf-8")
        self.assertIn("color_button.clicked.connect(self._show_quick_color_menu)", source)
        self.assertIn("quick_color_menu.colorSelected.connect(self._apply_color)", source)
        self.assertIn("quick_color_menu.moreColorsRequested.connect(self._choose_color)", source)
        self.assertIn("self.quick_color_menu.popup(position)", source)
        choose = source.split("    def _choose_color", 1)[1].split(
            "    def _show_quick_color_menu", 1
        )[0]
        self.assertIn("self._apply_color(selected)", choose)
        apply = source.split("    def _apply_color", 1)[1].split(
            "    def _update_color_button", 1
        )[0]
        self.assertIn("self._update_color_button()", apply)
        self.assertIn("self.colorChanged.emit()", apply)

    def test_member_and_column_share_control_and_orientation_preview_stays_colorless(self):
        self.assertIn("ProfileOptionsWidget", MEMBER.read_text(encoding="utf-8"))
        self.assertIn("ProfileOptionsWidget", COLUMN.read_text(encoding="utf-8"))
        self.assertIn("colorChanged.connect(on_preview_changed)", COLUMN.read_text(encoding="utf-8"))
        orientation = ORIENTATION.read_text(encoding="utf-8")
        self.assertNotIn("STEEL_COLOR_PALETTE", orientation)
        self.assertNotIn("member_color", orientation)


if __name__ == "__main__":
    unittest.main()
