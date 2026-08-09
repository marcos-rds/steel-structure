"""Behavioral and structural tests for the column-specific panel contract."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "freecad/BancadaFCSteel/interactive/column_task_panel.py"


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def add(self, other):
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)


class ColumnGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PANEL.read_text(encoding="utf-8")
        tree = ast.parse(cls.source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "column_top"
        )
        module = ast.Module(body=[function], type_ignores=[])
        namespace = {}
        exec(compile(module, str(PANEL), "exec"), namespace)
        cls.column_top = staticmethod(namespace["column_top"])

    def assertVector(self, vector, expected):
        self.assertEqual((vector.x, vector.y, vector.z), expected)

    def test_origin_and_default_height(self):
        self.assertVector(self.column_top(Vector(), 3000), (0.0, 0.0, 3000.0))

    def test_nonzero_xyz_base(self):
        self.assertVector(
            self.column_top(Vector(1000, 2000, 3000), 4000),
            (1000.0, 2000.0, 7000.0),
        )

    def test_direction_is_always_global_positive_z(self):
        base = Vector(-50, 80, 125)
        top = self.column_top(base, 6000)
        self.assertEqual((top.x - base.x, top.y - base.y, top.z - base.z), (0, 0, 6000))

    def test_zero_is_rejected(self):
        with self.assertRaises(ValueError):
            self.column_top(Vector(), 0)

    def test_negative_is_rejected(self):
        with self.assertRaises(ValueError):
            self.column_top(Vector(), -1)

    def test_panel_default_and_minimum_are_explicit(self):
        self.assertIn("DEFAULT_COLUMN_HEIGHT = 3000.0", self.source)
        self.assertIn("MIN_COLUMN_HEIGHT = 0.01", self.source)
        self.assertIn("self.height.setRange(MIN_COLUMN_HEIGHT", self.source)

    def test_panel_composes_existing_profile_selector(self):
        self.assertIn('ProfileOptionsWidget(document, element_types=("Pilar",))', self.source)
        self.assertIn('setCurrentText("Pilar")', self.source)
        self.assertIn("creation_options", self.source)

    def test_geometry_is_visually_inserted_before_profile_options(self):
        geometry = self.source.index("layout.addWidget(geometry)")
        profile = self.source.index("layout.addWidget(self.profile_options)")
        self.assertLess(geometry, profile)

    def test_height_and_profile_changes_are_connected_to_preview(self):
        for signal in (
            "height.valueChanged", "profile.currentIndexChanged",
            "insertion.currentIndexChanged", "rotation.valueChanged",
            "color_button.clicked",
        ):
            self.assertIn(signal, self.source)


if __name__ == "__main__":
    unittest.main()
