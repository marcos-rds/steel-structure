"""Insertion-reference contracts for typology-specific section geometry."""

import unittest

from freecad.SteelStructures.paths import CATALOGS_DIR
from freecad.SteelStructures.profiles import (
    ProfileLibrary, build_section_geometry, insertion_translation,
    section_insertion_references,
)


class SectionInsertionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = ProfileLibrary(CATALOGS_DIR)

    def geometry(self, designation):
        return build_section_geometry(self.library.search(designation)[0])

    def test_equal_angle_references_use_real_centroidal_points(self):
        expected_ids = (
            "centroid", "outer_corner", "top_tip", "right_tip", "inner_corner",
        )
        expected_labels = (
            "Centroide", "Quina externa", "Ponta superior", "Ponta direita", "Quina interna",
        )
        for designation in ("L40x3", "L100x9", "L1/2x1/8", "L2x1/4", "L6x1/2", "L8x3/4"):
            geometry = self.geometry(designation)
            references = section_insertion_references(geometry)
            points = {item.id: item.point for item in references}
            inner = geometry.outer_path.segments[3].start
            with self.subTest(designation=designation):
                self.assertEqual(tuple(item.id for item in references), expected_ids)
                self.assertEqual(tuple(item.label for item in references), expected_labels)
                self.assertEqual((points["centroid"].x, points["centroid"].y), (0.0, 0.0))
                self.assertEqual((points["outer_corner"].x, points["outer_corner"].y),
                                 (geometry.bounds.min_x, geometry.bounds.min_y))
                self.assertEqual((points["top_tip"].x, points["top_tip"].y),
                                 (geometry.bounds.min_x, geometry.bounds.max_y))
                self.assertEqual((points["right_tip"].x, points["right_tip"].y),
                                 (geometry.bounds.max_x, geometry.bounds.min_y))
                self.assertEqual(points["inner_corner"], inner)

    def test_every_reference_translation_places_its_point_on_axis(self):
        for designation in ("L40x3", "L100x9"):
            geometry = self.geometry(designation)
            for reference in section_insertion_references(geometry):
                tx, ty = insertion_translation(geometry, reference.id)
                with self.subTest(designation=designation, insertion=reference.id):
                    self.assertAlmostEqual(reference.point.x + tx, 0.0)
                    self.assertAlmostEqual(reference.point.y + ty, 0.0)

    def test_w_hp_labels_and_offsets_remain_unchanged(self):
        geometry = self.geometry("W310x52")
        references = section_insertion_references(geometry)
        self.assertEqual(tuple(item.label for item in references), (
            "Centroide", "Face esquerda", "Face direita", "Face superior", "Face inferior",
            "Canto superior esquerdo", "Canto superior direito",
            "Canto inferior esquerdo", "Canto inferior direito",
        ))
        self.assertEqual(insertion_translation(geometry, "Face superior"),
                         (0.0, -geometry.bounds.max_y))


if __name__ == "__main__":
    unittest.main()
