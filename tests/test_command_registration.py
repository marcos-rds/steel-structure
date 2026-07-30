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

    class FakeControl:
        def __init__(self):
            self.active_value = None
            self.active_calls = 0
            self.show_calls = []
            self.show_failures = []
            self.close_calls = 0
            self.taskPanel = object()
            self.task_view_visible = True

        def activeDialog(self):
            self.active_calls += 1
            return self.active_value

        def showDialog(self, panel):
            self.show_calls.append(panel)
            if self.show_failures:
                failure = self.show_failures.pop(0)
                if failure is not None:
                    raise failure

        def closeDialog(self):
            self.close_calls += 1

    class FakeSelection:
        def getSelectionEx(self):
            return []

        def clearSelection(self):
            pass

        def addSelection(self, _member):
            pass

    messages = types.SimpleNamespace(
        information_calls=[],
        warning_calls=[],
        critical_calls=[],
    )
    messages.information = lambda *args: messages.information_calls.append(args)
    messages.warning = lambda *args: messages.warning_calls.append(args)
    messages.critical = lambda *args: messages.critical_calls.append(args)

    freecad = types.ModuleType("FreeCAD")
    freecad.Gui = types.SimpleNamespace(
        addCommand=lambda *_args: None,
        Control=FakeControl(),
        Selection=FakeSelection(),
        getMainWindow=lambda: object(),
    )
    freecad.Vector = lambda *coordinates: coordinates
    freecad.ActiveDocument = None
    freecad.newDocument = lambda _name: types.SimpleNamespace(Objects=[])
    freecad.Console = types.SimpleNamespace(
        PrintWarning=lambda *_args: None,
        PrintError=lambda *_args: None,
    )
    pyside = types.ModuleType("PySide")
    pyside.QtGui = types.SimpleNamespace(QColor=FakeColor)
    pyside.QtWidgets = types.SimpleNamespace(
        QDialog=FakeDialog,
        QMessageBox=messages,
    )

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
        for name in list(sys.modules):
            if name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


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


class TaskDialogActivationTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_commands_module()
        self.control = self.module.Gui.Control
        self.document = types.SimpleNamespace(Objects=[])
        self.module.App.ActiveDocument = self.document
        self.controllers = []
        self.panels = []
        self.fallback_calls = []

        module = self.module
        controllers = self.controllers
        panels = self.panels

        class FakeController:
            def __init__(self, document):
                self.document = document
                self.state = module.ControllerState.INACTIVE
                self.stop_calls = 0
                controllers.append(self)

            def start(self):
                self.state = module.ControllerState.READY_NUMERIC

            def stop(self):
                self.stop_calls += 1
                self.state = module.ControllerState.INACTIVE

        class FakePanel:
            def __init__(self, document, controller, start, end, on_closed):
                self.document = document
                self.controller = controller
                self.start = start
                self.end = end
                self._on_closed = on_closed
                self._closed = False
                self.shutdown_calls = 0
                self.request_close_calls = 0
                controller.start()
                panels.append(self)

            def shutdown(self):
                if self._closed:
                    return
                self._closed = True
                self.shutdown_calls += 1
                self.controller.stop()
                callback = self._on_closed
                self._on_closed = None
                if callback is not None:
                    callback(self)

            def request_close(self):
                self.request_close_calls += 1
                self.shutdown()

        self.module.MemberController = FakeController
        self.module.MemberTaskPanel = FakePanel
        self.module._run_numeric_fallback = (
            lambda *args: self.fallback_calls.append(args)
        )
        self.module._active_member_panel = None

    def activate(self):
        self.module.CreateMemberCommand().Activated()

    def test_active_dialog_none_allows_opening(self):
        self.control.active_value = None
        self.activate()
        self.assertEqual(len(self.control.show_calls), 1)
        self.assertIs(self.module._active_member_panel, self.panels[0])

    def test_active_dialog_false_allows_opening(self):
        self.control.active_value = False
        self.activate()
        self.assertEqual(len(self.control.show_calls), 1)
        self.assertIs(self.module._active_member_panel, self.panels[0])

    def test_real_active_dialog_blocks_without_closing_other_panel(self):
        self.control.active_value = object()
        self.activate()
        self.assertEqual(self.control.show_calls, [])
        self.assertEqual(self.control.close_calls, 0)
        self.assertIsNone(self.module._active_member_panel)

    def test_active_dialog_function_is_called(self):
        self.activate()
        self.assertEqual(self.control.active_calls, 1)

    def test_visible_empty_task_tab_does_not_block(self):
        self.control.active_value = False
        self.assertIsNotNone(self.control.taskPanel)
        self.assertTrue(self.control.task_view_visible)
        self.activate()
        self.assertEqual(len(self.control.show_calls), 1)

    def test_stale_inactive_member_session_is_discarded(self):
        stale_controller = types.SimpleNamespace(
            state=self.module.ControllerState.INACTIVE
        )
        stale_panel = types.SimpleNamespace(
            controller=stale_controller,
            shutdown_calls=0,
        )

        def shutdown():
            stale_panel.shutdown_calls += 1

        stale_panel.shutdown = shutdown
        self.module._active_member_panel = stale_panel
        self.activate()
        self.assertEqual(stale_panel.shutdown_calls, 1)
        self.assertIs(self.module._active_member_panel, self.panels[0])

    def test_truly_active_member_session_blocks_duplicate(self):
        active_panel = types.SimpleNamespace(
            controller=types.SimpleNamespace(
                state=self.module.ControllerState.READY_NUMERIC
            )
        )
        self.module._active_member_panel = active_panel
        self.activate()
        self.assertEqual(self.control.show_calls, [])
        self.assertIs(self.module._active_member_panel, active_panel)

    def test_show_dialog_failure_cleans_session(self):
        self.control.show_failures = [RuntimeError("falha controlada")]
        self.activate()
        self.assertIsNone(self.module._active_member_panel)
        self.assertEqual(self.panels[0].shutdown_calls, 1)
        self.assertIs(
            self.controllers[0].state,
            self.module.ControllerState.INACTIVE,
        )
        self.assertEqual(len(self.fallback_calls), 1)

    def test_second_attempt_after_show_failure_can_open(self):
        self.control.show_failures = [RuntimeError("primeira falha"), None]
        self.activate()
        self.assertIsNone(self.module._active_member_panel)
        self.activate()
        self.assertEqual(len(self.control.show_calls), 2)
        self.assertIs(self.module._active_member_panel, self.panels[1])

    def test_global_session_is_cleared_and_command_can_reopen(self):
        self.activate()
        first = self.panels[0]
        first.shutdown()
        self.assertIsNone(self.module._active_member_panel)
        self.activate()
        self.assertEqual(len(self.control.show_calls), 2)
        self.assertIs(self.module._active_member_panel, self.panels[1])

    def test_close_member_task_panel_closes_owned_session(self):
        self.activate()
        panel = self.panels[0]
        self.assertTrue(self.module.close_member_task_panel())
        self.assertEqual(panel.request_close_calls, 1)
        self.assertIsNone(self.module._active_member_panel)

    def test_close_member_task_panel_does_not_close_other_tool(self):
        self.control.active_value = object()
        self.assertFalse(self.module.close_member_task_panel())
        self.assertEqual(self.control.close_calls, 0)

    def test_workbench_deactivation_requests_owned_panel_close(self):
        source = INIT_GUI_PATH.read_text(encoding="utf-8")
        self.assertIn("commands.close_member_task_panel()", source)


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
        panel_source = (
            PROJECT_ROOT
            / "freecad"
            / "BancadaFCSteel"
            / "interactive"
            / "member_task_panel.py"
        ).read_text(encoding="utf-8")
        self.assertIn("designation=self.profile_designation", panel_source)
        self.assertNotIn("designation=self.profile.currentText()", panel_source)

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
