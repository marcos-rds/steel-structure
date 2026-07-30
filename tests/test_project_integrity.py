"""Static tests that do not require FreeCAD to be installed."""

from __future__ import annotations

import ast
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_XML = PROJECT_ROOT / "package.xml"
PACKAGE_INIT = PROJECT_ROOT / "freecad" / "BancadaFCSteel" / "__init__.py"
CATALOG = (
    PROJECT_ROOT
    / "freecad"
    / "BancadaFCSteel"
    / "catalogs"
    / "gerdau_w_initial.json"
)

REQUIRED_PROFILE_FIELDS = {
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
POSITIVE_PROFILE_FIELDS = ("mass_per_m", "d", "bf", "tw", "tf", "area_cm2")
ESSENTIAL_FILES = (
    "package.xml",
    "README.md",
    "LICENSE",
    "freecad/BancadaFCSteel/__init__.py",
    "freecad/BancadaFCSteel/init_gui.py",
    "freecad/BancadaFCSteel/commands.py",
    "freecad/BancadaFCSteel/member.py",
    "freecad/BancadaFCSteel/profile_catalog.py",
    "freecad/BancadaFCSteel/paths.py",
    "freecad/BancadaFCSteel/catalogs/gerdau_w_initial.json",
    "Resources/Icons/BancadaFCSteel.svg",
    "Resources/Icons/CreateMember.svg",
    "Resources/Icons/StructuralMember.svg",
)


def read_internal_version() -> str:
    tree = ast.parse(PACKAGE_INIT.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise AssertionError("__version__ não encontrada")


class PackageMetadataTests(unittest.TestCase):
    def test_package_xml_is_valid(self):
        root = ET.parse(PACKAGE_XML).getroot()
        self.assertEqual(root.tag.rsplit("}", 1)[-1], "package")

    def test_versions_are_synchronized(self):
        root = ET.parse(PACKAGE_XML).getroot()
        manifest_version = root.find("{*}version")
        self.assertIsNotNone(manifest_version)
        self.assertEqual(manifest_version.text.strip(), read_internal_version())


class CatalogIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.profiles = cls.payload["profiles"]

    def test_catalog_is_valid_json_with_profiles(self):
        self.assertIsInstance(self.payload, dict)
        self.assertIsInstance(self.profiles, list)

    def test_catalog_contains_exactly_22_profiles(self):
        self.assertEqual(len(self.profiles), 22)

    def test_designations_are_unique(self):
        designations = [profile["designation"] for profile in self.profiles]
        self.assertEqual(len(designations), len(set(designations)))

    def test_profiles_have_all_required_fields(self):
        for profile in self.profiles:
            with self.subTest(profile=profile.get("designation")):
                self.assertFalse(REQUIRED_PROFILE_FIELDS.difference(profile))

    def test_profile_numeric_values_are_positive(self):
        for profile in self.profiles:
            for field in POSITIVE_PROFILE_FIELDS:
                with self.subTest(profile=profile.get("designation"), field=field):
                    value = profile[field]
                    self.assertIsInstance(value, (int, float))
                    self.assertNotIsInstance(value, bool)
                    self.assertGreater(value, 0)


class ProjectLayoutTests(unittest.TestCase):
    def test_essential_files_exist(self):
        for relative in ESSENTIAL_FILES:
            with self.subTest(path=relative):
                self.assertTrue((PROJECT_ROOT / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
