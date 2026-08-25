"""Presentation contracts for catalog values shown by Profile Browser."""

from __future__ import annotations

import unittest

from freecad.SteelStructures.paths import CATALOGS_DIR
from freecad.SteelStructures.profiles import ProfileLibrary
from freecad.SteelStructures.profiles.presentation import (
    format_engineering_value, profile_basic_rows, profile_dimension_rows,
    profile_preview_dimension_rows, profile_property_groups, profile_source_groups,
    profile_source_rows,
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

    def source_group_map(self, profile):
        return {group.title: self.row_map(group.rows) for group in profile_source_groups(profile)}

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

    def test_t_preview_uses_four_nominal_dimensions(self):
        self.assertEqual(self.row_map(profile_preview_dimension_rows(self.get("T2x1/4"))), {
            "d": "50,8 mm", "bf": "50,8 mm", "tw": "6,35 mm", "tf": "6,35 mm",
        })

    def test_tapered_i_exposes_revit_parameters_and_four_preview_dimensions(self):
        profile = self.get("I3x8.48")
        dimensions = self.row_map(profile_dimension_rows(profile))
        self.assertEqual(set(dimensions), {
            "d", "bf", "tw", "tf", "TL", "r1", "r2", "Ângulo da mesa",
        })
        self.assertEqual(dimensions["TL"], "13,71 mm")
        self.assertEqual(dimensions["Ângulo da mesa"], "9,46 °")
        self.assertEqual(self.row_map(profile_preview_dimension_rows(profile)), {
            "d": "76,2 mm", "bf": "59,18 mm", "tw": "4,32 mm", "tf": "6,6 mm",
        })
        source = self.source_group_map(profile)
        self.assertEqual(source["Geometria"]["Origem"], "BIM oficial Gerdau — Revit")
        self.assertEqual(
            source["Geometria"]["Definição"],
            "SA 9,46° · r1 7 mm · r2 3 mm · TL por tipo",
        )
        geometry_rows = next(
            group.rows for group in profile_source_groups(profile)
            if group.title == "Geometria"
        )
        self.assertIn("Perfil-I-Revit_1.zip", geometry_rows[0].tooltip)

    def test_i_3x9_68_shows_effective_values_and_traces_reported_values(self):
        profile = self.get("I3x9.68")
        weak_axis = self.group_map(profile)["Eixo Y-Y"]
        self.assertEqual(weak_axis, {
            "Iy": "21,11 cm⁴", "Wy": "6,90 cm³", "ry": "1,31 cm",
        })
        source = self.source_group_map(profile)["Observação técnica — eixo Y-Y"]
        self.assertEqual(
            source["Usado"],
            "Iy 21,11 cm⁴ · Wy 6,90 cm³ · ry 1,31 cm",
        )
        self.assertEqual(
            source["Publicado"],
            "Iy 45,6 cm⁴ · Wy 11,48 cm³ · ry 1,92 cm",
        )
        self.assertEqual(
            source["Status"],
            "Propriedades efetivas calculadas da geometria nominal Revit",
        )
        self.assertIn("eventual esclarecimento da Gerdau", source["Confirmação"])

    def test_source_summary_is_compact_and_consistent_across_families(self):
        cases = {
            "W310x52": ("Fonte", "Geometria"),
            "HP310x132": ("Fonte", "Geometria"),
            "I3x8.48": ("Fonte", "Geometria"),
            "U6x12.2": ("Fonte", "Geometria"),
            "U3x7.44": ("Fonte", "Geometria", "Observação técnica"),
            "L50x5": ("Fonte", "Geometria"),
            "L2x1/4": ("Fonte", "Geometria"),
            "T2x1/4": ("Fonte", "Geometria"),
        }
        for query, expected_titles in cases.items():
            with self.subTest(query=query):
                groups = profile_source_groups(self.get(query))
                self.assertEqual(tuple(group.title for group in groups), expected_titles)
                rows = tuple(row for group in groups for row in group.rows)
                self.assertTrue(all(row.value for row in rows))
                self.assertNotIn("Notas", {row.label for row in rows})
                self.assertNotIn("Notas geométricas", {row.label for row in rows})

    def test_source_summary_preserves_complete_catalog_text_in_tooltips(self):
        for query in ("W310x52", "I3x8.48", "U6x12.2", "L50x5"):
            with self.subTest(query=query):
                profile = self.get(query)
                rows = tuple(
                    row for group in profile_source_groups(profile) for row in group.rows
                )
                visible_values = {row.value for row in rows}
                self.assertNotIn(profile.catalog.source.notes, visible_values)
                self.assertTrue(any(
                    profile.catalog.source.notes in (row.tooltip or "") for row in rows
                ))
                if profile.geometry_notes:
                    self.assertNotIn(profile.geometry_notes, visible_values)
                    self.assertTrue(any(
                        profile.geometry_notes in (row.tooltip or "") for row in rows
                    ))

    def test_pending_u_and_released_t_expose_short_operational_status(self):
        pending = self.source_group_map(self.get("U10x30.8"))["Observação técnica"]
        self.assertEqual(pending, {
            "Status": "Geometria em revisão técnica",
            "Motivo": "Inconsistência entre fontes Gerdau",
        })
        tee = self.source_group_map(self.get("T2x1/4"))["Geometria"]
        self.assertEqual(tee, {
            "Definição": "Seção nominal retangular",
            "Concordância": "Não parametrizada na fonte",
        })

    def test_equal_angle_preview_dimensions_are_b_and_t(self):
        cases = {
            "L2x1/4": {"b": "50,8 mm", "t": "6,35 mm"},
            "L50x5": {"b": "50 mm", "t": "5 mm"},
            "L100x9": {"b": "100 mm", "t": "9 mm"},
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(
                    self.row_map(profile_preview_dimension_rows(self.get(query))), expected
                )

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
        self.assertEqual(set(self.row_map(profile_dimension_rows(u))), {
            "d", "bf", "tw", "tf", "r1", "r2", "Ângulo da mesa",
        })
        self.assertEqual(self.row_map(profile_dimension_rows(u))["Ângulo da mesa"], "8,3 °")
        self.assertEqual(set(self.row_map(profile_dimension_rows(t))), {"d", "bf", "tw", "tf"})
        t_extra = self.group_map(t)["Centroide / propriedades adicionais"]
        self.assertEqual(t_extra["Distância da face superior ao centroide"], "1,5 cm")
        self.assertNotIn("x do centroide", t_extra)
        self.assertEqual(set(self.row_map(profile_dimension_rows(angle))), {"b", "t"})
        self.assertEqual([row.label for row in profile_dimension_rows(angle)].count("b"), 1)
        angle_groups = self.group_map(angle)
        extra = angle_groups["Centroide / propriedades adicionais"]
        self.assertEqual(extra["x do centroide"], "1,42 cm")
        self.assertEqual(extra["y do centroide"], "1,42 cm")
        self.assertEqual(extra["rz mín."], "0,97 cm")

    def test_u_preview_dimensions_keep_the_four_catalog_symbols(self):
        self.assertEqual(self.row_map(profile_preview_dimension_rows(self.get("U6x12.2"))), {
            "d": "152,4 mm", "bf": "48,77 mm", "tw": "5,08 mm", "tf": "8,71 mm",
        })

    def test_pending_u_keeps_official_dimensions_and_properties_available(self):
        profile = self.get("U3x7.44")
        self.assertEqual(profile.geometry_status, "pending_technical_review")
        self.assertEqual(set(self.row_map(profile_dimension_rows(profile))), {
            "d", "bf", "tw", "tf", "r1", "r2", "Ângulo da mesa",
        })
        groups = self.group_map(profile)
        self.assertIn("Físicas", groups)
        self.assertIn("Eixo X-X", groups)
        self.assertIn("Centroide / propriedades adicionais", groups)

    def test_centroid_y_is_derived_only_for_equal_leg_angles(self):
        for query in ("L40x3", "L50x5", "L100x9", "L2x1/4"):
            rows = self.group_map(self.get(query))["Centroide / propriedades adicionais"]
            self.assertEqual(rows["x do centroide"], rows["y do centroide"])
        for query in ("U6x12.2", "T2x1/4"):
            groups = self.group_map(self.get(query))
            rows = groups.get("Centroide / propriedades adicionais", {})
            self.assertNotIn("y do centroide", rows)

    def test_t_7_8_source_compactly_documents_iy_without_override(self):
        profile = self.get("T7/8x1/8")
        technical = self.source_group_map(profile)["Observação técnica — eixo Y-Y"]
        self.assertEqual(technical["Iy publicado"], "0,33 cm⁴")
        self.assertEqual(technical["Iy geométrico nominal"], "aprox. 0,296 cm⁴")
        self.assertIn("aguardando", technical["Status"])
        self.assertIsNone(profile.section_property_override)

    def test_source_standards_are_only_exposed_for_supported_w_hp_geometry(self):
        w_source = self.row_map(profile_source_rows(self.get("W310x52")))
        u_source = self.row_map(profile_source_rows(self.get("U6x12.2")))
        self.assertEqual(w_source["Revisão"], "01/23")
        self.assertIn("ABNT NBR 15980", w_source["Normas"])
        self.assertNotIn("Normas", u_source)
        self.assertNotIn("Material", u_source)


if __name__ == "__main__":
    unittest.main()
