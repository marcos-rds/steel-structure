"""Headless integration checks for Profile Browser selection in shared options."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

from freecad.SteelStructures import profile_catalog


ROOT = Path(__file__).resolve().parents[1]


def _load_options_runtime_module():
    root_name = "_profile_options_runtime"
    root = types.ModuleType(root_name)
    root.__path__ = []
    interactive = types.ModuleType(root_name + ".interactive")
    interactive.__path__ = []
    pyside = types.ModuleType("PySide")
    pyside.QtGui = types.SimpleNamespace()
    pyside.QtWidgets = types.SimpleNamespace(
        QGroupBox=object, QDialog=types.SimpleNamespace(Accepted=1)
    )
    member = types.ModuleType(root_name + ".member")
    member.ELEMENT_TYPES = ("Membro", "Pilar")
    member.INSERTION_OPTIONS = ("Centro",)
    preferences = types.ModuleType(root_name + ".preferences")
    preferences.MemberCreationSettings = object
    controller = types.ModuleType(root_name + ".interactive.member_controller")
    controller.MemberCreationOptions = object
    controller.compact_profile_designation = lambda value: value
    controller.next_default_label = lambda *_args: "Membro"
    injected = {
        root_name: root,
        root_name + ".interactive": interactive,
        root_name + ".profile_catalog": profile_catalog,
        root_name + ".member": member,
        root_name + ".preferences": preferences,
        root_name + ".interactive.member_controller": controller,
        "PySide": pyside,
    }
    previous = {name: sys.modules.get(name) for name in injected}
    sys.modules.update(injected)
    path = ROOT / "freecad/SteelStructures/interactive/profile_options_widget.py"
    spec = importlib.util.spec_from_file_location(
        root_name + ".interactive.profile_options_widget", path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
    return module


class _Signal:
    def __init__(self):
        self.values = []

    def emit(self, value):
        self.values.append(value)


class _Combo:
    def __init__(self, items=()):
        self.items = [(value, value) for value in items]
        self.index = 0 if self.items else -1
        self.blocked = False
        self.currentIndexChanged = _Signal()

    def blockSignals(self, blocked):
        previous, self.blocked = self.blocked, blocked
        return previous

    def clear(self):
        self.items = []
        self.index = -1

    def addItems(self, values):
        self.items.extend((value, value) for value in values)
        if self.index < 0 and self.items:
            self.index = 0

    def addItem(self, text, data):
        self.items.append((text, data))
        if self.index < 0:
            self.index = 0

    def findData(self, data):
        return next((i for i, item in enumerate(self.items) if item[1] == data), -1)

    def setCurrentIndex(self, index):
        self.index = index

    def setCurrentText(self, text):
        index = next((i for i, item in enumerate(self.items) if item[0] == text), -1)
        if index >= 0:
            self.index = index

    def currentIndex(self):
        return self.index

    def currentText(self):
        return self.items[self.index][0] if self.index >= 0 else ""

    def currentData(self):
        return self.items[self.index][1] if self.index >= 0 else None


class ProfileOptionsBrowserIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_options_runtime_module()

    def make_widget(self):
        widget = types.SimpleNamespace(
            category=_Combo(profile_catalog.categories()),
            series=_Combo(profile_catalog.series_for_category("Aço Laminado")),
            profile=_Combo(), insertion="Centro", rotation=17.0,
            color=(0.1, 0.2, 0.3), height=4321.0, refreshed=0,
        )
        for designation in profile_catalog.designations("Aço Laminado", "Perfis W"):
            widget.profile.addItem(designation, designation)
        widget.refresh_automatic_name = lambda: setattr(
            widget, "refreshed", widget.refreshed + 1
        )
        widget.set_profile_ref = types.MethodType(
            self.module.ProfileOptionsWidget.set_profile_ref, widget
        )
        return widget

    def test_confirming_hp_updates_three_combos_and_emits_one_profile_change(self):
        widget = self.make_widget()
        selected = profile_catalog.ref_for_designation("HP 310 x 132,0")
        widget.set_profile_ref(selected)
        self.assertEqual(widget.category.currentText(), "Aço Laminado")
        self.assertEqual(widget.series.currentText(), "Perfis HP")
        self.assertEqual(widget.profile.currentData(), "HP 310 x 132,0")
        self.assertEqual(widget.profile.currentIndexChanged.values, [widget.profile.currentIndex()])
        self.assertEqual(widget.refreshed, 1)
        self.assertEqual((widget.insertion, widget.rotation, widget.color, widget.height),
                         ("Centro", 17.0, (0.1, 0.2, 0.3), 4321.0))

    def test_cancel_does_not_read_or_apply_the_dialog_selection(self):
        widget = self.make_widget()
        before = (widget.category.currentText(), widget.series.currentText(), widget.profile.currentData())
        dialog = types.SimpleNamespace(
            exec=lambda: 0,
            selected_profile_ref=lambda: self.fail("selection must not be read after cancel"),
        )
        widget._create_profile_browser_dialog = lambda: dialog
        widget.set_profile_ref = lambda _ref: self.fail("selection must not be applied after cancel")
        self.module.ProfileOptionsWidget._open_profile_browser(widget)
        after = (widget.category.currentText(), widget.series.currentText(), widget.profile.currentData())
        self.assertEqual(after, before)

    def test_insertion_combo_switches_between_w_and_equal_angle_options(self):
        widget = object.__new__(self.module.ProfileOptionsWidget)
        widget.profile = _Combo()
        widget.insertion = _Combo(("Face superior",))
        for designation in profile_catalog.designations("Aço Laminado", "Perfis W"):
            widget.profile.addItem(designation, designation)
        widget.profile.setCurrentIndex(widget.profile.findData("W 150 x 13,0"))
        self.module.ProfileOptionsWidget._refresh_insertion_options(widget)
        self.assertIn("Face superior", [item[0] for item in widget.insertion.items])

        widget.profile.clear()
        for designation in profile_catalog.designations("Aço Laminado", "Cantoneiras - Métricas"):
            widget.profile.addItem(designation, designation)
        widget.profile.setCurrentIndex(widget.profile.findData("L 50 x 5"))
        self.module.ProfileOptionsWidget._refresh_insertion_options(widget)
        self.assertEqual([item[0] for item in widget.insertion.items], [
            "Centroide", "Quina externa", "Ponta superior", "Ponta direita", "Quina interna",
        ])
        self.assertEqual(widget.insertion.currentText(), "Centroide")

        widget.profile.clear()
        for designation in profile_catalog.designations("Aço Laminado", "Perfis W"):
            widget.profile.addItem(designation, designation)
        widget.profile.setCurrentIndex(widget.profile.findData("W 150 x 13,0"))
        self.module.ProfileOptionsWidget._refresh_insertion_options(widget)
        self.assertEqual(widget.insertion.currentText(), "Centroide")


if __name__ == "__main__":
    unittest.main()
