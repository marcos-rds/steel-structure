"""Behavioral tests for the numeric task-panel foundation."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = PROJECT_ROOT / "freecad" / "BancadaFCSteel"
CONTROLLER_PATH = PACKAGE_DIR / "interactive" / "member_controller.py"
PANEL_PATH = PACKAGE_DIR / "interactive" / "member_task_panel.py"
COMMANDS_PATH = PACKAGE_DIR / "commands.py"


class Vector:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def sub(self, other):
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    @property
    def Length(self):
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5


class FakeSelection:
    def __init__(self):
        self.clear_count = 0
        self.selected = []

    def clearSelection(self):
        self.clear_count += 1

    def addSelection(self, member):
        self.selected.append(member)


class FakeDocument:
    def __init__(self):
        self.Objects = []
        self.opened = []
        self.commits = 0
        self.aborts = 0

    def openTransaction(self, name):
        self.opened.append(name)

    def commitTransaction(self):
        self.commits += 1

    def abortTransaction(self):
        self.aborts += 1


def _load_interactive_modules():
    package_name = "_metal_interactive_test"
    interactive_name = f"{package_name}.interactive"
    package = types.ModuleType(package_name)
    package.__path__ = [str(PACKAGE_DIR)]
    interactive = types.ModuleType(interactive_name)
    interactive.__path__ = [str(PACKAGE_DIR / "interactive")]

    selection = FakeSelection()
    control = types.SimpleNamespace(
        close_calls=0,
        close_error=None,
    )

    def close_dialog():
        control.close_calls += 1
        if control.close_error is not None:
            raise control.close_error

    control.closeDialog = close_dialog
    gui = types.SimpleNamespace(Selection=selection, Control=control)
    freecad = types.ModuleType("FreeCAD")
    freecad.Gui = gui
    freecad.Vector = Vector
    freecad.Console = types.SimpleNamespace(PrintError=lambda *_args: None)

    member = types.ModuleType(f"{package_name}.member")
    member.create_member = lambda **_kwargs: None
    member.ELEMENT_TYPES = ["Membro", "Pilar", "Viga", "Contraventamento"]
    member.INSERTION_OPTIONS = ["Centroide"]
    catalog = types.ModuleType(f"{package_name}.profile_catalog")
    pyside = types.ModuleType("PySide")
    pyside.QtGui = types.SimpleNamespace()
    pyside.QtWidgets = types.SimpleNamespace()

    injected = {
        package_name: package,
        interactive_name: interactive,
        f"{package_name}.member": member,
        f"{package_name}.profile_catalog": catalog,
        "FreeCAD": freecad,
        "PySide": pyside,
    }
    previous = {name: sys.modules.get(name) for name in injected}
    sys.modules.update(injected)
    controller_spec = importlib.util.spec_from_file_location(
        f"{interactive_name}.member_controller",
        CONTROLLER_PATH,
    )
    controller = importlib.util.module_from_spec(controller_spec)
    sys.modules[controller_spec.name] = controller
    controller_spec.loader.exec_module(controller)

    panel_spec = importlib.util.spec_from_file_location(
        f"{interactive_name}.member_task_panel",
        PANEL_PATH,
    )
    panel = importlib.util.module_from_spec(panel_spec)
    sys.modules[panel_spec.name] = panel
    panel_spec.loader.exec_module(panel)

    def cleanup():
        for name in list(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module

    return controller, panel, selection, control, cleanup


class MemberControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (
            cls.controller_module,
            cls.panel_module,
            cls.selection,
            _control,
            cls.cleanup,
        ) = _load_interactive_modules()

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()

    def setUp(self):
        self.selection.clear_count = 0
        self.selection.selected.clear()
        self.document = FakeDocument()
        self.factory_calls = []

        def factory(**kwargs):
            self.factory_calls.append(kwargs)
            member = types.SimpleNamespace(
                Label=kwargs["display_name"],
                DisplayName=kwargs["display_name"],
                PropertiesList=["DisplayName"],
                Profile=kwargs["designation"],
            )
            self.document.Objects.append(member)
            return member

        self.controller = self.controller_module.MemberController(
            self.document,
            member_factory=factory,
            selection=self.selection,
        )

    def options(self, **overrides):
        values = {
            "start": Vector(0, 0, 0),
            "end": Vector(1000, 2000, 3000),
            "designation": "W 150 x 13,0",
            "element_type": "Membro",
            "insertion": "Centroide",
            "rotation": 15.0,
            "color": (0.7, 0.8, 0.9),
            "display_name": "Membro 001 - W150x13,0",
        }
        values.update(overrides)
        return self.controller_module.MemberCreationOptions(**values)

    def test_state_lifecycle(self):
        state = self.controller_module.ControllerState
        self.assertEqual(
            [item.name for item in state],
            ["INACTIVE", "READY_NUMERIC", "CREATING", "STOPPING"],
        )
        self.assertIs(self.controller.state, state.INACTIVE)
        self.controller.start()
        self.assertIs(self.controller.state, state.READY_NUMERIC)
        self.controller.stop()
        self.assertIs(self.controller.state, state.INACTIVE)

    def test_factory_runs_while_controller_is_creating(self):
        observed_states = []

        def observing_factory(**kwargs):
            observed_states.append(self.controller.state)
            member = types.SimpleNamespace(
                Label=kwargs["display_name"],
                DisplayName=kwargs["display_name"],
                PropertiesList=["DisplayName"],
            )
            self.document.Objects.append(member)
            return member

        self.controller._member_factory = observing_factory
        self.controller.start()
        self.controller.create(self.options())
        self.assertEqual(
            observed_states,
            [self.controller_module.ControllerState.CREATING],
        )

    def test_valid_numeric_creation_uses_one_transaction_and_selection(self):
        self.controller.start()
        result = self.controller.create(self.options())
        self.assertEqual(self.document.opened, ["Criar elemento estrutural"])
        self.assertEqual(self.document.commits, 1)
        self.assertEqual(self.document.aborts, 0)
        self.assertIs(self.selection.selected[-1], result.member)
        self.assertEqual(result.member.Profile, "W 150 x 13,0")

    def test_coincident_points_are_rejected_before_transaction(self):
        self.controller.start()
        point = Vector(10, 20, 30)
        with self.assertRaisesRegex(ValueError, "devem ser diferentes"):
            self.controller.create(self.options(start=point, end=point))
        self.assertEqual(self.document.opened, [])
        self.assertEqual(self.factory_calls, [])

    def test_commit_on_success_and_abort_on_failure(self):
        self.controller.start()
        self.controller.create(self.options())
        self.assertEqual((self.document.commits, self.document.aborts), (1, 0))

        def failing_factory(**_kwargs):
            raise RuntimeError("falha controlada")

        failing = self.controller_module.MemberController(
            self.document,
            member_factory=failing_factory,
            selection=self.selection,
        )
        failing.start()
        with self.assertRaisesRegex(RuntimeError, "falha controlada"):
            failing.create(self.options(display_name="Membro 002 - W150x13,0"))
        self.assertEqual(self.document.aborts, 1)
        self.assertIs(
            failing.state,
            self.controller_module.ControllerState.READY_NUMERIC,
        )

    def test_repeated_creation_preserves_options_and_updates_default_name(self):
        self.controller.start()
        options = self.options()
        first = self.controller.create(options)
        second = self.controller.create(
            self.options(display_name=first.next_default_name)
        )
        self.assertEqual(len(self.factory_calls), 2)
        for call in self.factory_calls:
            self.assertEqual(call["designation"], "W 150 x 13,0")
            self.assertEqual(call["element_type"], "Membro")
            self.assertEqual(call["insertion"], "Centroide")
            self.assertEqual(call["rotation"], 15.0)
            self.assertEqual(call["color"], (0.7, 0.8, 0.9))
        self.assertEqual(first.next_default_name, "Membro 002 - W150x13,0")
        self.assertEqual(second.next_default_name, "Membro 003 - W150x13,0")
        self.assertEqual(self.document.commits, 2)

    def test_custom_name_is_forwarded_unchanged(self):
        self.controller.start()
        self.controller.create(self.options(display_name="Pilar principal"))
        self.assertEqual(self.factory_calls[0]["display_name"], "Pilar principal")

    def test_canonical_designation_is_sent_to_member_factory(self):
        self.controller.start()
        self.controller.create(self.options())
        self.assertEqual(
            self.factory_calls[0]["designation"],
            "W 150 x 13,0",
        )
        self.assertEqual(
            self.controller_module.compact_profile_designation("W 150 x 13,0"),
            "W150x13,0",
        )

    def test_stop_is_idempotent_and_releases_document(self):
        panel = object()
        self.controller.attach_panel(panel)
        self.controller.start()
        self.controller.stop()
        self.controller.stop()
        self.assertIs(
            self.controller.state,
            self.controller_module.ControllerState.INACTIVE,
        )
        self.assertIsNone(self.controller.document)
        self.assertIsNone(self.controller.panel)


class MemberTaskPanelLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (
            cls.controller_module,
            cls.panel_module,
            _selection,
            cls.control,
            cls.cleanup,
        ) = _load_interactive_modules()

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()

    def test_shutdown_closes_session_once(self):
        controller = types.SimpleNamespace(stop_count=0)

        def stop():
            controller.stop_count += 1

        controller.stop = stop
        callbacks = []
        panel = self.panel_module.MemberTaskPanel.__new__(
            self.panel_module.MemberTaskPanel
        )
        panel.controller = controller
        panel._closed = False
        panel._close_requested = False
        panel._on_closed = callbacks.append
        panel.document = object()
        panel.shutdown()
        panel.shutdown()
        self.assertEqual(controller.stop_count, 1)
        self.assertEqual(callbacks, [panel])
        self.assertIsNone(panel._on_closed)

    def test_reject_uses_safe_shutdown(self):
        controller = types.SimpleNamespace(stop=lambda: None)
        panel = self.panel_module.MemberTaskPanel.__new__(
            self.panel_module.MemberTaskPanel
        )
        panel.controller = controller
        panel._closed = False
        panel._close_requested = False
        panel._on_closed = None
        panel.document = object()
        before = self.control.close_calls
        self.assertTrue(panel.reject())
        self.assertTrue(panel._closed)
        self.assertEqual(self.control.close_calls, before)

    def test_request_close_calls_freecad_close_dialog(self):
        controller = types.SimpleNamespace(stop=lambda: None)
        panel = self.panel_module.MemberTaskPanel.__new__(
            self.panel_module.MemberTaskPanel
        )
        panel.controller = controller
        panel.document = object()
        panel._closed = False
        panel._close_requested = False
        panel._on_closed = None
        before = self.control.close_calls
        panel.request_close()
        self.assertEqual(self.control.close_calls, before + 1)
        self.assertTrue(panel._closed)

    def test_close_failure_still_cleans_internal_state(self):
        stop_calls = []
        panel = self.panel_module.MemberTaskPanel.__new__(
            self.panel_module.MemberTaskPanel
        )
        panel.controller = types.SimpleNamespace(
            stop=lambda: stop_calls.append(True)
        )
        panel.document = object()
        panel._closed = False
        panel._close_requested = False
        panel._on_closed = None
        self.control.close_error = RuntimeError("falha controlada")
        try:
            panel.request_close()
        finally:
            self.control.close_error = None
        self.assertTrue(panel._closed)
        self.assertEqual(stop_calls, [True])
        self.assertIsNone(panel.controller)
        self.assertIsNone(panel.document)

    def test_two_close_requests_are_safe(self):
        panel = self.panel_module.MemberTaskPanel.__new__(
            self.panel_module.MemberTaskPanel
        )
        panel.controller = types.SimpleNamespace(stop=lambda: None)
        panel.document = object()
        panel._closed = False
        panel._close_requested = False
        panel._on_closed = None
        before = self.control.close_calls
        panel.request_close()
        panel.request_close()
        self.assertEqual(self.control.close_calls, before + 1)

    def test_document_deletion_requests_close(self):
        document = object()
        panel = self.panel_module.MemberTaskPanel.__new__(
            self.panel_module.MemberTaskPanel
        )
        panel.document = document
        calls = []
        panel.request_close = lambda: calls.append(True)
        panel.slotDeletedDocument(document)
        panel.slotDeletedDocument(object())
        self.assertEqual(calls, [True])


class MemberTaskPanelNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (
            cls.controller_module,
            cls.panel_module,
            _selection,
            _control,
            cls.cleanup,
        ) = _load_interactive_modules()

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()

    class LineEdit:
        def __init__(self, panel, text=""):
            self.panel = panel
            self.value = text
            self.blocked = False

        def blockSignals(self, blocked):
            previous = self.blocked
            self.blocked = blocked
            return previous

        def setText(self, value):
            self.value = value
            if not self.blocked:
                self.panel._mark_name_custom(value)

        def text(self):
            return self.value

    class Combo:
        def __init__(self, value):
            self.value = value

        def currentText(self):
            return self.value

        def currentData(self):
            return self.value

    def panel(self, element_type="Contraventamento", designation="W 150 x 13,0"):
        panel = self.panel_module.MemberTaskPanel.__new__(
            self.panel_module.MemberTaskPanel
        )
        panel.document = types.SimpleNamespace(Objects=[])
        panel._name_custom = False
        panel._updating_name_programmatically = False
        panel.name_edit = self.LineEdit(panel)
        panel.element_type = self.Combo(element_type)
        panel.profile = self.Combo(designation)
        return panel

    def test_manual_edit_enables_custom_mode(self):
        panel = self.panel()
        panel._mark_name_custom("teste1")
        self.assertTrue(panel._name_custom)

    def test_type_change_before_creation_preserves_custom_name(self):
        panel = self.panel()
        panel.name_edit.value = "teste1"
        panel._mark_name_custom("teste1")
        panel.element_type.value = "Viga"
        panel._refresh_default_name()
        self.assertEqual(panel.name_edit.text(), "teste1")

    def test_profile_change_before_creation_preserves_custom_name(self):
        panel = self.panel()
        panel.name_edit.value = "teste1"
        panel._mark_name_custom("teste1")
        panel.profile.value = "W 200 x 26,6"
        panel._refresh_default_name()
        self.assertEqual(panel.name_edit.text(), "teste1")

    def test_success_resets_custom_mode_and_uses_next_automatic_name(self):
        panel = self.panel()
        panel.name_edit.value = "teste1"
        panel._name_custom = True
        panel.status_label = types.SimpleNamespace(setText=lambda _value: None)
        result = types.SimpleNamespace(
            member=types.SimpleNamespace(Label="teste1"),
            next_default_name="Contraventamento 002 - W150x13,0",
        )
        panel.controller = types.SimpleNamespace(create=lambda _options: result)
        panel.creation_options = lambda: object()
        panel._create()
        self.assertFalse(panel._name_custom)
        self.assertEqual(
            panel.name_edit.text(),
            "Contraventamento 002 - W150x13,0",
        )
        self.assertNotEqual(panel.name_edit.text(), "teste1")

    def test_type_and_profile_changes_after_success_recalculate_automatic_name(self):
        panel = self.panel()
        panel.document.Objects.append(
            types.SimpleNamespace(
                Label="Contraventamento 001 - W150x13,0",
                DisplayName="Contraventamento 001 - W150x13,0",
                PropertiesList=["DisplayName"],
            )
        )
        panel._name_custom = False
        panel.element_type.value = "Viga"
        panel._refresh_default_name()
        self.assertEqual(panel.name_edit.text(), "Viga 001 - W150x13,0")
        panel.profile.value = "W 200 x 26,6"
        panel._refresh_default_name()
        self.assertEqual(panel.name_edit.text(), "Viga 001 - W200x26,6")

    def test_creation_failure_preserves_custom_name_and_mode(self):
        panel = self.panel()
        panel.name_edit.value = "teste1"
        panel._name_custom = True
        panel.status_label = types.SimpleNamespace(setText=lambda _value: None)
        panel.controller = types.SimpleNamespace(
            create=lambda _options: (_ for _ in ()).throw(ValueError("erro"))
        )
        panel.creation_options = lambda: object()
        panel._create()
        self.assertTrue(panel._name_custom)
        self.assertEqual(panel.name_edit.text(), "teste1")

    def test_programmatic_name_change_does_not_enable_custom_mode(self):
        panel = self.panel()
        panel._set_name_programmatically("Membro 001 - W150x13,0")
        self.assertFalse(panel._name_custom)
        self.assertEqual(panel.name_edit.text(), "Membro 001 - W150x13,0")

    def test_numbering_remains_independent_by_type(self):
        panel = self.panel()
        panel.document.Objects.extend(
            [
                types.SimpleNamespace(
                    Label="Membro 004 - W150x13,0",
                    PropertiesList=[],
                ),
                types.SimpleNamespace(
                    Label="Pilar 002 - W150x13,0",
                    PropertiesList=[],
                ),
            ]
        )
        panel.element_type.value = "Membro"
        panel._refresh_default_name()
        self.assertEqual(panel.name_edit.text(), "Membro 005 - W150x13,0")
        panel.element_type.value = "Pilar"
        panel._refresh_default_name()
        self.assertEqual(panel.name_edit.text(), "Pilar 003 - W150x13,0")


class InteractiveScopeTests(unittest.TestCase):
    def test_command_opens_task_panel_and_guards_exclusive_session(self):
        source = COMMANDS_PATH.read_text(encoding="utf-8")
        self.assertIn("Gui.Control.showDialog(panel)", source)
        self.assertIn("dialog = Gui.Control.activeDialog()", source)
        self.assertIn("if dialog is None or dialog is False:", source)
        self.assertIn("_active_member_panel", source)
        self.assertEqual(source.count('Gui.addCommand("BFC_CreateMember"'), 1)

    def test_panel_contains_required_numeric_fields_and_buttons(self):
        source = PANEL_PATH.read_text(encoding="utf-8")
        for expected in (
            '"Criar elemento estrutural"',
            '"Nome:"',
            '"Tipo do elemento:"',
            '"Categoria do perfil:"',
            '"Série do perfil:"',
            '"Perfil:"',
            '"Inserção:"',
            '"Rotação da seção:"',
            '"Cor:"',
            '"Ponto inicial"',
            '"Ponto final"',
            'QPushButton("Criar")',
            'QPushButton("Fechar")',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_compact_text_and_canonical_item_data_are_separate(self):
        source = PANEL_PATH.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            r"self\.profile\.addItem\(\s*"
            r"compact_profile_designation\(designation\),\s*designation,\s*\)",
        )
        self.assertIn("designation = self.profile.currentData()", source)

    def test_no_callbacks_coin_draft_or_future_modules_exist(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                CONTROLLER_PATH,
                PANEL_PATH,
                COMMANDS_PATH,
            )
        )
        for forbidden in (
            "addEventCallback",
            "removeEventCallback",
            "pivy",
            "Coin",
            "Draft",
            "SnapAdapter",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)
        self.assertFalse((PANEL_PATH.parent / "point_capture.py").exists())
        self.assertFalse((PANEL_PATH.parent / "preview_tracker.py").exists())


if __name__ == "__main__":
    unittest.main()
