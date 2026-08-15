"""Presentation contracts for catalog values shown by Profile Browser."""

from __future__ import annotations

import unittest

from freecad.SteelStructures.paths import CATALOGS_DIR
from freecad.SteelStructures.profiles import ProfileLibrary
from freecad.SteelStructures.profiles.presentation import (
    format_engineering_value, profile_basic_rows, profile_dimension_rows,
    profile_preview_dimension_rows, profile_property_groups, profile_source_rows,
)


class ProfilePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = ProfileLibrary(CATALOGS_DIR)
        cls.series = {item.id: item.name for item in cls.library.list_series()}

    def get(self, text):
        return self.library.search(text)[0]

    @staticmethod
    def row_map(rows):
        return {row.label: row.value for row in rows}

    def group_map(self, profile):
        return {group.title: self.row_map(group.rows) for group in profile_property_groups(profile)}

    def test_canonical_unit_conversions_and_pt_br_format(self):
        self.assertEqual(format_engineering_value(6700, 0.01, "cm²", 1), "67,0 cm²")
        self.assertEqual(format_engineering_value(119090000, 1e-4, "cm⁴"), "11.909 cm⁴")
        self.assertEqual(format_engineering_value(236422000000, 1e-6, "cm⁶"), "236.422 cm⁶")

    def test_w310x52_complete_presentation(self):
        profile = self.get("W310x52")
        basic = self.row_map(profile_basic_rows(profile, self.series[profile.series_id]))
        source = self.row_map(profile_source_rows(profile))
        dimensions = self.row_map(profile_dimension_rows(profile))
        groups = self.group_map(profile)
        self.assertEqual(basic["Fabricante"], "Gerdau")
        self.assertNotIn("Massa linear", basic)
        self.assertEqual(source["Designação imperial"], "W 12 x 35")
        self.assertEqual(dimensions, {
            "d": "317 mm", "bf": "167 mm", "tw": "7,6 mm", "tf": "13,2 mm",
            "h": "291 mm", "d'": "271 mm",
        })
        self.assertEqual(groups["Físicas"]["Área"], "67,0 cm²")
        self.assertEqual(groups["Eixo X-X"]["Ix"], "11.909 cm⁴")
        self.assertEqual(groups["Eixo X-X"]["Wx"], "751,4 cm³")
        self.assertEqual(groups["Eixo Y-Y"]["Iy"], "1.026 cm⁴")
        self.assertEqual(groups["Torção / estabilidade"]["It"], "31,81 cm⁴")
        self.assertEqual(groups["Torção / estabilidade"]["Cw"], "236.422 cm⁶")
        self.assertEqual(groups["Físicas"]["Massa linear"], "52,0 kg/m")
        all_rows = list(basic.values()) + list(source.values())
        all_rows += [value for group in groups.values() for value in group.values()]
        self.assertEqual(all_rows.count("52,0 kg/m"), 1)

    def test_w_preview_principal_dimensions_are_complete_and_formatted(self):
        cases = {
            "W150x13": {"d": "148 mm", "bf": "100 mm", "tw": "4,3 mm", "tf": "4,9 mm"},
            "W310x52": {"d": "317 mm", "bf": "167 mm", "tw": "7,6 mm", "tf": "13,2 mm"},
            "HP310x132": {"d": "314 mm", "bf": "313 mm", "tw": "18,3 mm", "tf": "18,3 mm"},
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                rows = self.row_map(profile_preview_dimension_rows(self.get(query)))
                self.assertEqual(rows, expected)

    def test_unsupported_families_have_no_preview_dimensions(self):
        for query in ("I3x8.48", "U6x12.2", "T2x1/4", "L50x5"):
            with self.subTest(query=query):
                self.assertEqual(profile_preview_dimension_rows(self.get(query)), ())

    def test_hp_markers_availability_and_equivalent(self):
        profile = self.get("HP310x132")
        rows = self.row_map(profile_source_rows(profile))
        self.assertEqual(rows["Marcadores do catálogo"], "H, *")
        self.assertEqual(rows["Disponibilidade"], "Sob encomenda")
        self.assertEqual(rows["Designação imperial"], "HP 12 x 89")

    def test_u_t_and_angle_dynamic_fields(self):
        u = self.get("U6x12.2")
        t = self.get("T2x1/4")
        angle = self.get("L50x5")
        self.assertEqual(set(self.row_map(profile_dimension_rows(u))), {"d", "bf", "tw", "tf"})
        self.assertEqual(set(self.row_map(profile_dimension_rows(t))), {"d", "bf", "tw", "tf"})
        self.assertEqual(set(self.row_map(profile_dimension_rows(angle))), {"b", "t"})
        angle_groups = self.group_map(angle)
        self.assertEqual(angle_groups["Centroide / eixos principais"]["x do centroide"], "1,42 cm")
        self.assertEqual(angle_groups["Centroide / eixos principais"]["rz mín."], "0,97 cm")

    def test_source_standards_are_only_exposed_for_supported_w_hp_geometry(self):
        w_source = self.row_map(profile_source_rows(self.get("W310x52")))
        u_source = self.row_map(profile_source_rows(self.get("U6x12.2")))
        self.assertEqual(w_source["Revisão"], "01/23")
        self.assertIn("ABNT NBR 15980", w_source["Normas"])
        self.assertNotIn("Normas", u_source)
        self.assertNotIn("Material", u_source)


if __name__ == "__main__":
    unittest.main()
