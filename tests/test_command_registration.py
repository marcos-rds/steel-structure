"""Static command and presentation tests that run without FreeCAD or PySide."""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_PATH = PROJECT_ROOT / "freecad" / "BancadaFCSteel" / "commands.py"
INIT_GUI_PATH = PROJECT_ROOT / "freecad" / "BancadaFCSteel" / "init_gui.py"
MEMBER_PATH = PROJECT_ROOT / "freecad" / "BancadaFCSteel" / "member.py"


def _source(path=COMMANDS_PATH):
    return path.read_text(encoding="utf-8")


def _tree(path=COMMANDS_PATH):
    return ast.parse(_source(path), filename=str(path))


def _class(tree, name):
    return next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name
    )


def _method(class_node, name):
    return next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _command_registrations():
    registrations = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call) or len(node.args) < 2:
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "Gui"
            and node.func.attr == "addCommand"
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            registrations.append(node.args[0].value)
    return registrations


def _load_commands_module():
    package_name = "_metal_structure_test_package"
    package = types.ModuleType(package_name)
    package.__path__ = [str(COMMANDS_PATH.parent)]

    profile_catalog = types.ModuleType(f"{package_name}.profile_catalog")
    member = types.ModuleType(f"{package_name}.member")
    member.ELEMENT_TYPES = ["Membro", "Pilar", "Viga", "Contraventamento"]
    member.INSERTION_OPTIONS = ["Centroide"]
    member.create_member = lambda **_kwargs: None
    paths = types.ModuleType(f"{package_name}.paths")
    paths.MEMBER_ICON = "CreateMember.svg"

    class FakeDialog:
        def __init__(self, _parent=None):
            pass

    class FakeColor:
        def __init__(self, *_rgb):
            pass

    freecad = types.ModuleType("FreeCAD")
    freecad.Gui = types.SimpleNamespace(addCommand=lambda *_args: None)
    freecad.Vector = lambda *coordinates: coordinates
    pyside = types.ModuleType("PySide")
    pyside.QtGui = types.SimpleNamespace(QColor=FakeColor)
    pyside.QtWidgets = types.SimpleNamespace(QDialog=FakeDialog)

    injected = {
        package_name: package,
        f"{package_name}.profile_catalog": profile_catalog,
        f"{package_name}.member": member,
        f"{package_name}.paths": paths,
        "FreeCAD": freecad,
        "PySide": pyside,
    }
    previous = {name: sys.modules.get(name) for name in injected}
    sys.modules.update(injected)
    try:
        spec = importlib.util.spec_from_file_location(
            f"{package_name}.commands", COMMANDS_PATH
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module
        sys.modules.pop(f"{package_name}.commands", None)


class CommandRegistrationTests(unittest.TestCase):
    def test_only_generic_command_is_registered(self):
        self.assertEqual(_command_registrations(), ["BFC_CreateMember"])

    def test_specialized_commands_are_not_registered(self):
        registrations = _command_registrations()
        self.assertNotIn("BFC_CreateColumn", registrations)
        self.assertNotIn("BFC_CreateBeam", registrations)

    def test_workbench_menu_and_toolbar_use_only_generic_command(self):
        tree = _tree(INIT_GUI_PATH)
        assignment = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "member_commands"
                for target in node.targets
            )
        )
        self.assertEqual(
            [item.value for item in assignment.value.elts],
            ["BFC_CreateMember"],
        )

    def test_public_text_is_create_structural_element(self):
        command = _class(_tree(), "CreateMemberCommand")
        resources = _method(command, "GetResources")
        source = ast.get_source_segment(_source(), resources)
        self.assertIn('"MenuText": "Criar elemento estrutural"', source)

    def test_command_class_has_exactly_one_activated_method(self):
        command = _class(_tree(), "CreateMemberCommand")
        activated = [
            node
            for node in command.body
            if isinstance(node, ast.FunctionDef) and node.name == "Activated"
        ]
        self.assertEqual(len(activated), 1)

    def test_element_type_field_remains_selectable_and_starts_as_member(self):
        dialog = _class(_tree(), "MemberDialog")
        build_ui = ast.get_source_segment(_source(), _method(dialog, "_build_ui"))
        self.assertIn("self.element_type = QtWidgets.QComboBox()", build_ui)
        self.assertIn("self.element_type.addItems(ELEMENT_TYPES)", build_ui)
        self.assertIn('self.element_type.setCurrentText("Membro")', build_ui)
        self.assertIn("self.element_type.currentTextChanged.connect", build_ui)
        self.assertIn('form.addRow("Tipo do elemento:", self.element_type)', build_ui)

    def test_dialog_uses_requested_window_title(self):
        dialog = _class(_tree(), "MemberDialog")
        initializer = ast.get_source_segment(_source(), _method(dialog, "__init__"))
        self.assertIn(
            'setWindowTitle("Metal Structure — Criar elemento estrutural")',
            initializer,
        )

    def test_specialized_command_parameters_and_icons_are_absent(self):
        source = _source()
        self.assertNotIn("default_element_type", source)
        self.assertNotIn("COLUMN_ICON", source)
        self.assertNotIn("BEAM_ICON", source)


class ProfilePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commands = _load_commands_module()

    def test_compact_designation(self):
        self.assertEqual(
            self.commands.compact_profile_designation("W 150 x 13,0"),
            "W150x13,0",
        )

    def test_multiple_spaces_are_removed(self):
        self.assertEqual(
            self.commands.compact_profile_designation("  W   200  x  26,6 "),
            "W200x26,6",
        )

    def test_decimal_comma_is_preserved(self):
        self.assertEqual(
            self.commands.compact_profile_designation("W 200 x 26,6"),
            "W200x26,6",
        )

    def test_combo_visible_text_is_compact_and_item_data_is_canonical(self):
        dialog = _class(_tree(), "MemberDialog")
        method = ast.get_source_segment(_source(), _method(dialog, "_series_changed"))
        self.assertIn("self.profile.addItem(", method)
        self.assertIn("compact_profile_designation(designation)", method)
        self.assertRegex(method, r"compact_profile_designation\(designation\),\s+designation,")

    def test_canonical_item_data_drives_member_creation(self):
        dialog = _class(_tree(), "MemberDialog")
        profile_property = ast.get_source_segment(
            _source(), _method(dialog, "profile_designation")
        )
        self.assertIn("self.profile.currentData()", profile_property)
        activated = ast.get_source_segment(
            _source(), _method(_class(_tree(), "CreateMemberCommand"), "Activated")
        )
        self.assertIn("designation=dialog.profile_designation", activated)
        self.assertNotIn("designation=dialog.profile.currentText()", activated)

    def test_catalog_lookup_and_profile_property_keep_canonical_designation(self):
        source = _source(MEMBER_PATH)
        tree = _tree(MEMBER_PATH)
        create_member = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "create_member"
        )
        method = ast.get_source_segment(source, create_member)
        self.assertIn("profile_catalog.get(designation)", method)
        self.assertIn("obj.Profile = designation", method)


class AutomaticNumberingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commands = _load_commands_module()

    @staticmethod
    def document(*objects):
        return types.SimpleNamespace(Objects=list(objects))

    @staticmethod
    def member(label, display_name=None):
        properties = ["DisplayName"] if display_name is not None else []
        return types.SimpleNamespace(
            Label=label,
            DisplayName=display_name,
            PropertiesList=properties,
        )

    def next_label(self, document, element_type, designation="W 200 x 26,6"):
        return self.commands._next_default_label(document, element_type, designation)

    def test_sequences_are_independent_for_all_element_types(self):
        document = self.document(
            self.member("Pilar 001 - W200x26,6"),
            self.member("Viga 001 - W200x26,6"),
            self.member("Membro 001 - W200x26,6"),
            self.member("Contraventamento 001 - W200x26,6"),
        )
        for element_type in ("Pilar", "Viga", "Membro", "Contraventamento"):
            with self.subTest(element_type=element_type):
                self.assertEqual(
                    self.next_label(document, element_type),
                    f"{element_type} 002 - W200x26,6",
                )

    def test_automatic_name_uses_compact_designation(self):
        self.assertEqual(
            self.next_label(self.document(), "Membro", "W 150 x 13,0"),
            "Membro 001 - W150x13,0",
        )

    def test_increment_uses_highest_existing_number(self):
        document = self.document(
            self.member("Pilar 002 - W200x26,6"),
            self.member("Pilar 009 - W250x32,7"),
            self.member("Pilar 004 - W310x38,7"),
        )
        self.assertEqual(
            self.next_label(document, "Pilar"),
            "Pilar 010 - W200x26,6",
        )

    def test_custom_names_do_not_interfere_with_sequence(self):
        document = self.document(
            self.member("Pilar principal"),
            self.member("Meu Pilar 999"),
        )
        self.assertEqual(
            self.next_label(document, "Pilar"),
            "Pilar 001 - W200x26,6",
        )

    def test_custom_name_guard_is_preserved(self):
        dialog = _class(_tree(), "MemberDialog")
        refresh = ast.get_source_segment(
            _source(), _method(dialog, "_refresh_default_name")
        )
        self.assertIn("if self._name_custom", refresh)
        self.assertIn("self._name_custom = True", _source())


if __name__ == "__main__":
    unittest.main()
