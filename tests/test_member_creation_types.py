"""Separation between persistent ElementType values and generic creation UI."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIDGET = ROOT / "freecad/SteelStructures/interactive/profile_options_widget.py"
MEMBER = ROOT / "freecad/SteelStructures/member.py"
COLUMN_PANEL = ROOT / "freecad/SteelStructures/interactive/column_task_panel.py"


class MemberCreationTypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.widget_source = WIDGET.read_text(encoding="utf-8")
        cls.member_source = MEMBER.read_text(encoding="utf-8")
        tree = ast.parse(cls.widget_source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "member_creation_element_types"
        )
        function.args.defaults = []
        namespace = {}
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), str(WIDGET), "exec"),
            namespace,
        )
        cls.filter_types = staticmethod(namespace["member_creation_element_types"])

    def test_generic_creation_list_excludes_only_column(self):
        model_types = ("Membro", "Pilar", "Viga", "Contraventamento")
        self.assertEqual(
            self.filter_types(model_types),
            ("Membro", "Viga", "Contraventamento"),
        )

    def test_generic_widget_uses_filtered_list_and_keeps_member_default(self):
        self.assertIn("member_creation_element_types()", self.widget_source)
        self.assertIn('self.element_type.setCurrentText("Membro")', self.widget_source)

    def test_persistent_model_still_accepts_column(self):
        self.assertIn('ELEMENT_TYPES = ["Membro", "Pilar", "Viga", "Contraventamento"]',
                      self.member_source)
        self.assertIn("element_type if element_type in ELEMENT_TYPES", self.member_source)

    def test_column_creation_explicitly_offers_and_selects_column(self):
        source = COLUMN_PANEL.read_text(encoding="utf-8")
        self.assertIn('element_types=("Pilar",)', source)
        self.assertIn('element_type.setCurrentText("Pilar")', source)

    def test_no_schema_migration_or_automatic_conversion_was_added(self):
        self.assertNotIn("member_creation_element_types", self.member_source)
        self.assertNotIn("SchemaVersion", self.widget_source)
        self.assertNotIn("onDocumentRestored", self.widget_source)


if __name__ == "__main__":
    unittest.main()
