"""Normative catalog and pure geometry tests for NBR 6355 Ue sections."""

from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from freecad.SteelStructures.paths import CATALOGS_DIR
from freecad.SteelStructures.profiles import (
    ArcSegment2D, ColdFormedPath2D, ProfileLibrary, ProfileRef,
    CatalogValidationError, SectionGeometryError, build_section_geometry, build_ue_mean_path,
    nbr_6355_expected_internal_radius, physical_section_properties,
    ue_derived_dimensions, ue_normative_properties,
)
from freecad.SteelStructures.profiles.validation import validate_catalog_payload


CATALOG_ID = "abnt-nbr-6355-2012-a3"
SERIES_ID = "ue-nbr-6355"
CATALOG_PATH = CATALOGS_DIR / "abnt_nbr_6355_2012_a3.json"


class UeCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = ProfileLibrary(CATALOGS_DIR)
        cls.profiles = cls.library.list_profiles(series_id=SERIES_ID)

    def test_normative_identity_and_no_fictitious_manufacturer(self):
        self.assertEqual(len(self.profiles), 85)
        metadata = self.profiles[0].catalog
        self.assertIsNone(metadata.manufacturer)
        self.assertEqual(metadata.issuer.id, "abnt")
        self.assertEqual(metadata.issuer.name, "Associação Brasileira de Normas Técnicas")
        self.assertIn("ABNT NBR 6355:2012", metadata.standard_references)
        self.assertIn("Anexo A (informativo)", metadata.standard_references)
        self.assertIn("Tabela A.3", metadata.standard_references)
        self.assertIn("aço sem revestimento", metadata.source.notes)

    def test_exact_profile_and_base_geometry_counts(self):
        self.assertEqual(len({profile.designation for profile in self.profiles}), 85)
        bases = {(p.geometry["bw"], p.geometry["bf"], p.geometry["D"])
                 for p in self.profiles}
        self.assertEqual(len(bases), 14)

    def test_exact_thicknesses_by_base_geometry(self):
        expected = {
            (50, 25, 10): (1.20, 1.50, 2.00, 2.25, 2.65, 3.00),
            (75, 40, 15): (1.20, 1.50, 2.00, 2.25, 2.65, 3.00),
            (100, 40, 17): (1.20, 1.50, 2.00, 2.25, 2.65, 3.00, 3.35),
            (100, 50, 17): (1.20, 1.50, 2.00, 2.25, 2.65, 3.00, 3.35),
            (125, 50, 17): (2.00, 2.25, 2.65, 3.00, 3.35, 3.75),
            (150, 60, 20): (2.00, 2.25, 2.65, 3.00, 3.35, 3.75, 4.25, 4.75),
            (200, 75, 20): (2.00, 2.25),
            (200, 75, 25): (2.65, 3.00, 3.35, 3.75, 4.25, 4.75),
            (200, 75, 30): (6.30,),
            (200, 100, 25): (2.65, 3.00, 3.35, 3.75, 4.25, 4.75),
            (250, 85, 25): (2.00, 2.25, 2.65, 3.00, 3.35, 3.75, 4.25, 4.75, 6.30),
            (250, 100, 25): (2.65, 3.00, 3.35, 3.75, 4.25, 4.75),
            (300, 85, 25): (2.00, 2.25, 2.65, 3.00, 3.35, 3.75, 4.25, 4.75, 6.30),
            (300, 100, 25): (2.65, 3.00, 3.35, 3.75, 4.25, 4.75),
        }
        actual = {}
        for profile in self.profiles:
            key = tuple(profile.geometry[name] for name in ("bw", "bf", "D"))
            actual.setdefault(key, []).append(profile.geometry["t"])
        self.assertEqual({key: tuple(values) for key, values in actual.items()}, expected)

    def test_all_published_properties_are_preserved(self):
        required = {"ix", "wx", "rx", "x0", "iy", "wy", "ry", "it", "cw", "r0"}
        for profile in self.profiles:
            with self.subTest(profile=profile.designation):
                self.assertEqual(set(profile.section_properties), required)
                self.assertIsNotNone(profile.physical_properties.mass_per_length_kg_m)
                self.assertIsNotNone(profile.physical_properties.area_mm2)
                self.assertIn("x", profile.centroid)
                self.assertEqual(profile.geometry["t"], profile.geometry["tn"])
                self.assertEqual(profile.geometry["ri"], profile.geometry["tn"])
                self.assertEqual(profile.geometry_status, "released")

    def test_mass_area_radii_and_resistant_moduli_consistency(self):
        for profile in self.profiles:
            area_cm2 = profile.physical_properties.area_mm2 / 100.0
            mass = profile.physical_properties.mass_per_length_kg_m
            props = profile.section_properties
            bw_cm = profile.geometry["bw"] / 10.0
            bf_cm = profile.geometry["bf"] / 10.0
            xg_cm = profile.centroid["x"] / 10.0
            with self.subTest(profile=profile.designation):
                self.assertLessEqual(abs(mass - 0.785 * area_cm2), 0.007)
                self.assertLessEqual(abs(props["rx"] / 10.0 - math.sqrt(props["ix"] / 10_000.0 / area_cm2)), 0.009)
                self.assertLessEqual(abs(props["ry"] / 10.0 - math.sqrt(props["iy"] / 10_000.0 / area_cm2)), 0.006)
                self.assertLessEqual(abs(props["wx"] / 1_000.0 - (props["ix"] / 10_000.0) / (bw_cm / 2.0)), 0.02)
                extreme = max(xg_cm, bf_cm - xg_cm)
                self.assertLessEqual(abs(props["wy"] / 1_000.0 - (props["iy"] / 10_000.0) / extreme), 0.08)

    def test_a3_requires_equal_uncoated_and_nominal_thickness(self):
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        validate_catalog_payload(payload, CATALOG_PATH)
        within_tolerance = copy.deepcopy(payload)
        within_tolerance["profiles"][0]["geometry"]["t"] += 5.0e-10
        validate_catalog_payload(within_tolerance, Path("a3-tolerance.json"))

        inconsistent = copy.deepcopy(payload)
        inconsistent["profiles"][0]["geometry"]["t"] = 1.10
        with self.assertRaises(CatalogValidationError) as caught:
            validate_catalog_payload(inconsistent, Path("a3-invalid.json"))
        message = str(caught.exception)
        self.assertIn("Tabela A.3, aço sem revestimento, exige t = tn", message)
        self.assertNotIn("fabricante", message.casefold())

    def test_other_future_condition_does_not_inherit_a3_thickness_rule(self):
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        payload["catalog"]["id"] = "future-coated-ue"
        payload["profiles"][0]["geometry"]["t"] = 1.10
        metadata, _categories, _series, profiles = validate_catalog_payload(
            payload, Path("future-coated-ue.json")
        )
        self.assertIsNone(metadata.manufacturer)
        self.assertEqual(profiles[0].geometry["tn"], 1.20)
        self.assertEqual(profiles[0].geometry["t"], 1.10)


class UeNormativeMathTests(unittest.TestCase):
    def test_derived_relations_and_radius_rule(self):
        dims = ue_derived_dimensions(bw=150, bf=60, D=20, t=3, ri=3)
        self.assertEqual((dims.a, dims.am), (138.0, 147.0))
        self.assertEqual((dims.b, dims.bm), (48.0, 57.0))
        self.assertEqual((dims.c, dims.cm), (14.0, 18.5))
        self.assertEqual((dims.rm, dims.re), (4.5, 6.0))
        self.assertAlmostEqual(dims.u1, 1.571 * 4.5)
        self.assertEqual(nbr_6355_expected_internal_radius(6.3), 6.3)
        self.assertEqual(nbr_6355_expected_internal_radius(8.0), 12.0)

    def test_three_normative_controls(self):
        controls = (
            ((50, 25, 10, 1.20, 1.20),
             (1.3453344, 0.931566159313253, 5.236390713834897, 1.226263110789006)),
            ((150, 60, 20, 3.00, 3.00),
             (8.708340, 1.920000826793625, 298.0697706616756, 41.93982499118188)),
            ((300, 100, 25, 4.75, 4.75),
             (24.64174125, 2.704923246850504, 3269.5588672030362, 291.4880833769925)),
        )
        for inputs, expected in controls:
            result = ue_normative_properties(
                bw=inputs[0], bf=inputs[1], D=inputs[2], t=inputs[3], ri=inputs[4]
            )
            with self.subTest(inputs=inputs):
                for actual, target in zip(
                    (result.area_mm2 / 100.0, result.xg_mm / 10.0,
                     result.ix_mm4 / 10_000.0, result.iy_mm4 / 10_000.0),
                    expected,
                ):
                    self.assertAlmostEqual(actual, target, places=5)

    def test_all_85_normative_results_match_published_rounding(self):
        library = ProfileLibrary(CATALOGS_DIR)
        profiles = library.list_profiles(series_id=SERIES_ID)
        self.assertEqual(len(profiles), 85)
        for profile in profiles:
            geometry = profile.geometry
            result = ue_normative_properties(
                bw=geometry["bw"], bf=geometry["bf"], D=geometry["D"],
                t=geometry["t"], ri=geometry["ri"],
            )
            calculated = {
                "A": result.area_mm2 / 100.0,
                "Xg": result.xg_mm / 10.0,
                "Ix": result.ix_mm4 / 10_000.0,
                "Iy": result.iy_mm4 / 10_000.0,
            }
            published = {
                "A": profile.physical_properties.area_mm2 / 100.0,
                "Xg": profile.centroid["x"] / 10.0,
                "Ix": profile.section_properties["ix"] / 10_000.0,
                "Iy": profile.section_properties["iy"] / 10_000.0,
            }
            for name in calculated:
                with self.subTest(profile=profile.designation, property=name):
                    self.assertLessEqual(
                        abs(calculated[name] - published[name]), 0.0050001
                    )

    def test_invalid_dimensions_are_rejected(self):
        for values in (
            dict(bw=50, bf=25, D=10, t=0, ri=1),
            dict(bw=50, bf=25, D=10, t=1, ri=-1),
            dict(bw=5, bf=25, D=10, t=3, ri=3),
            dict(bw=50, bf=5, D=10, t=3, ri=3),
            dict(bw=50, bf=25, D=5, t=3, ri=3),
        ):
            with self.subTest(values=values), self.assertRaises(SectionGeometryError):
                ue_derived_dimensions(**values)


class UeGeometryTests(unittest.TestCase):
    CONTROLS = (
        ((50, 25, 10, 1.20, 1.20), (1.345317, 0.931562, 5.232324, 1.229155)),
        ((150, 60, 20, 3.00, 3.00), (8.708230, 1.919987, 297.692256, 42.050310)),
        ((300, 100, 25, 4.75, 4.75), (24.641465, 2.704898, 3263.667459, 292.271972)),
    )

    def test_mean_path_segment_order_continuity_tangency_and_radii(self):
        folded = build_ue_mean_path(bw=150, bf=60, D=20, t=3, ri=3)
        self.assertIsInstance(folded, ColdFormedPath2D)
        self.assertEqual(len(folded.mean_path.segments), 9)
        arcs = tuple(segment for segment in folded.mean_path.segments
                     if isinstance(segment, ArcSegment2D))
        self.assertEqual(len(arcs), 4)
        self.assertTrue(all(math.isclose(arc.sweep, math.pi / 2.0) for arc in arcs))
        self.assertTrue(all(math.isclose(arc.radius, 4.5) for arc in arcs))
        self.assertEqual((folded.inner_radius, folded.mean_radius, folded.outer_radius),
                         (3.0, 4.5, 6.0))
        for previous, current in zip(folded.mean_path.segments, folded.mean_path.segments[1:]):
            self.assertEqual(previous.end, current.start)

    def test_physical_controls_are_distinct_from_normative_values(self):
        for inputs, expected in self.CONTROLS:
            bw, bf, D, t, ri = inputs
            folded = build_ue_mean_path(bw=bw, bf=bf, D=D, t=t, ri=ri)
            contour = folded.physical_contour()
            props = physical_section_properties(contour)
            actual = (props.area / 100.0, props.centroid_x / 10.0,
                      props.ix / 10_000.0, props.iy / 10_000.0)
            with self.subTest(inputs=inputs):
                self.assertTrue(contour.closed)
                self.assertEqual(len(contour.segments), 20)
                for value, target in zip(actual, expected):
                    self.assertAlmostEqual(value, target, places=4)

    def test_all_catalog_profiles_build_centered_closed_geometry(self):
        library = ProfileLibrary(CATALOGS_DIR)
        for profile in library.list_profiles(series_id=SERIES_ID):
            geometry = build_section_geometry(profile)
            props = physical_section_properties(geometry.outer_path)
            with self.subTest(profile=profile.designation):
                self.assertTrue(geometry.outer_path.closed)
                self.assertFalse(geometry.inner_paths)
                self.assertEqual(len(geometry.outer_path.segments), 20)
                self.assertAlmostEqual(props.centroid_x, 0.0, places=8)
                self.assertAlmostEqual(props.centroid_y, 0.0, places=8)
                self.assertAlmostEqual(geometry.bounds.width, profile.geometry["bf"], places=7)
                self.assertAlmostEqual(geometry.bounds.height, profile.geometry["bw"], places=7)

    def test_semantic_stations_are_centered_mean_line_tangencies(self):
        for inputs in (
                (50, 25, 10, 1.20, 1.20),
                (150, 60, 20, 3.00, 3.00),
                (300, 85, 25, 2.25, 2.25)):
            bw, bf, D, t, ri = inputs
            folded = build_ue_mean_path(bw=bw, bf=bf, D=D, t=t, ri=ri)
            profile = next(
                item for item in ProfileLibrary(CATALOGS_DIR).list_profiles(series_id=SERIES_ID)
                if tuple(item.geometry[name] for name in ("bw", "bf", "D", "t"))
                == (bw, bf, D, t)
            )
            geometry = build_section_geometry(profile)
            stations = dict(geometry.dimension_stations)
            upper = folded.mean_path.segments[2]
            lower = folded.mean_path.segments[6]
            dx, dy = geometry.bounds.min_x, geometry.bounds.min_y
            with self.subTest(inputs=inputs):
                self.assertAlmostEqual(stations["flange_lip_tangent_x"],
                                       upper.start.x + dx)
                self.assertAlmostEqual(stations["flange_web_tangent_x"],
                                       upper.end.x + dx)
                self.assertNotIn("upper_flange_mean_y", stations)
                self.assertNotIn("lower_flange_mean_y", stations)
                self.assertAlmostEqual(upper.start.x + dx, lower.end.x + dx)
                self.assertAlmostEqual(upper.end.x + dx, lower.start.x + dx)
                self.assertAlmostEqual(upper.start.y + dy,
                                       -(lower.start.y + dy))


if __name__ == "__main__":
    unittest.main()
