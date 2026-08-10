"""Focused tests for the grid task-panel contract without a real FreeCAD GUI."""

from __future__ import annotations

import ast
import enum
import unittest
from pathlib import Path

from test_grid_geometry import grid as grid_geometry


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "freecad/SteelStructures/interactive/grid_task_panel.py"


class GridTaskPanelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PANEL.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_panel_has_independent_x_and_y_editors_and_sections(self):
        for text in ("Vãos em X", "Vãos em Y", "Extensões", "Identificação", "Aparência"):
            self.assertIn(text, self.source)
        self.assertIn("self.x_editor = SpacingEditor", self.source)
        self.assertIn("self.y_editor = SpacingEditor", self.source)

    def test_spacing_controls_and_summary_are_present(self):
        for control in ("Adicionar", "Duplicar", "Remover", "eixos • total:"):
            self.assertIn(control, self.source)

    def test_positive_spacing_validation_is_delegated_to_geometry_contract(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            grid_geometry.build_grid_geometry([0], [1])
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            grid_geometry.build_grid_geometry([-1], [1])
        self.assertIn("build_grid_geometry(x_values, y_values", self.source)

    def test_all_extension_fields_are_wired(self):
        for name in ("XStartExtension", "XEndExtension", "YStartExtension", "YEndExtension"):
            self.assertIn(name, self.source)

    def test_identification_schemes_and_custom_rules_come_from_geometry(self):
        for label in ("Numérica", "Alfabética", "Personalizada"):
            self.assertIn(label, self.source)
        for bad in ((["A"], 2), (["A", "A"], 2), (["A", " "], 2)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                grid_geometry.normalize_identifiers(bad[0], bad[1], "custom")
        self.assertEqual(grid_geometry.normalize_identifiers([" A ", "B"], 2, "custom"), ("A", "B"))

    def test_preview_mutates_existing_object_and_validates_before_mutation(self):
        method = next(node for node in self.tree.body if isinstance(node, ast.ClassDef) and node.name == "GridTaskPanel")
        update = next(node for node in method.body if isinstance(node, ast.FunctionDef) and node.name == "update_preview")
        calls = [node for node in ast.walk(update) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(call.func, ast.Name) and call.func.id == "create_grid" for call in calls))
        self.assertIn("self._values()", ast.unparse(update))
        self.assertIn("self.document.recompute()", ast.unparse(update))

    def test_invalid_input_preserves_preview_and_validity_blocks_acceptance(self):
        update_source = ast.unparse(next(node for node in ast.walk(self.tree) if isinstance(node, ast.FunctionDef) and node.name == "update_preview"))
        self.assertLess(update_source.index("self._values()"), update_source.index("obj = self.grid_object"))
        self.assertIn("return False", update_source)
        self.assertIn("if not self.update_preview()", self.source)

    def test_visual_properties_and_provisional_defaults(self):
        for prop in ("LineColor", "LineWidth", "PointColor", "PointSize"):
            self.assertIn(prop, self.source)
        self.assertIn("IntersectionPointColor", self.source)
        self.assertIn("IntersectionPointSize", self.source)
        self.assertNotIn("view.PointColor =", self.source)
        self.assertNotIn("view.PointSize =", self.source)
        self.assertIn("self.line_width.setValue(1.0)", self.source)
        self.assertIn("self.point_size.setValue(5.0)", self.source)
        self.assertIn('getattr(current_view, "ShowIntersections", True)', self.source)

    def test_accept_cancel_and_idempotent_cleanup_contract(self):
        for call in ("commitTransaction()", "abortTransaction()", "removeObject(name)"):
            self.assertIn(call, self.source)
        self.assertIn("if self._closed:", self.source)
        self.assertIn("self._remove_escape_filter()", self.source)
        self.assertIn("self._finish(True)", self.source)
        self.assertIn("self._finish(False)", self.source)
        self.assertIn("event_filter.deleteLater()", self.source)

    def test_identification_signals_are_connected_after_both_label_widgets_exist(self):
        labels = self.source.index("self.x_labels, self.y_labels =")
        connection = self.source.index("currentTextChanged.connect(self._identification_changed)")
        self.assertLess(labels, connection)
        self.assertIn("self._initializing", self.source)

    def test_escape_and_visual_view_properties_are_wired(self):
        for text in ("installEventFilter", "Key_Escape", "_EscapeEventFilter(self.reject", "ShowIntersections", "ShowLabels",
                     "LabelPosition", "FontSize", "TextColor", 'view.DrawStyle = "Dashdot"'):
            self.assertIn(text, self.source)

    def test_escape_cancels_once_removes_only_preview_aborts_and_closes(self):
        filter_node = next(node for node in self.tree.body if isinstance(node, ast.ClassDef) and node.name == "_EscapeEventFilter")
        panel_node = next(node for node in self.tree.body if isinstance(node, ast.ClassDef) and node.name == "GridTaskPanel")
        class QObject:
            def __init__(self, parent=None): self.parent = parent
            def eventFilter(self, _watched, _event): return False
            def deleteLater(self): self.deleted = True
        qt = type("Qt", (), {"Key": type("Key", (), {"Key_Escape": 27}), "Key_Escape": 27})
        qt_core = type("QtCore", (), {"QObject": QObject,
                                      "QEvent": type("QEvent", (), {"KeyPress": 6, "ShortcutOverride": 51}), "Qt": qt})
        application = Widget = None
        namespace = {"QtCore": qt_core}
        exec(compile(ast.Module(body=[filter_node, panel_node], type_ignores=[]), str(PANEL), "exec"), namespace)
        panel = namespace["GridTaskPanel"].__new__(namespace["GridTaskPanel"])
        class Widget(QObject):
            def __init__(self): super().__init__(); self.filters = []
            def installEventFilter(self, event_filter):
                if not isinstance(event_filter, QObject):
                    raise TypeError("installEventFilter requires QObject")
                self.filters.append(event_filter)
            def removeEventFilter(self, event_filter): self.filters.remove(event_filter)
            def findChildren(self, kind): return [] if kind is QObject else []
        application = Widget()
        namespace["QtWidgets"] = type("QtWidgets", (), {
            "QApplication": type("QApplication", (), {"instance": staticmethod(lambda: application)})})
        class Document:
            def __init__(self): self.names = ["ConfirmedGrid", "PreviewGrid"]; self.aborted = self.recomputed = 0
            def removeObject(self, name): self.names.remove(name)
            def abortTransaction(self): self.aborted += 1
            def recompute(self): self.recomputed += 1
        document = Document(); closed = []
        panel.document = document
        panel.grid_object = type("Object", (), {"Name": "PreviewGrid"})()
        panel.form = Widget(); panel._closed = False
        panel._on_closed = lambda _panel, accepted: closed.append(accepted)
        panel._escape_filter = None; panel._escape_filter_target = None
        with self.assertRaises(TypeError): panel.form.installEventFilter(panel)
        panel._install_escape_filter()
        self.assertIsInstance(panel._escape_filter, QObject)
        class Event:
            def __init__(self, event_type, key): self.event_type, self.key_value, self.accepted = event_type, key, False
            def type(self): return self.event_type
            def key(self): return self.key_value
            def accept(self): self.accepted = True
        event = Event(51, 27)
        other = type("Event", (), {"type": lambda self: 6, "key": lambda self: 65})()
        focused_widgets = [object() for _name in ("form", "spin", "list", "combo", "custom", "main_window")]
        for focused in focused_widgets:
            self.assertFalse(panel._escape_filter.eventFilter(focused, other))
        event_filter = panel._escape_filter
        self.assertTrue(event_filter.eventFilter(focused_widgets[-1], event))
        self.assertTrue(event.accepted)
        self.assertEqual((document.names, document.aborted, document.recomputed, closed),
                         (["ConfirmedGrid"], 1, 1, [False]))
        self.assertTrue(event_filter.eventFilter(focused_widgets[1], Event(6, 27)))
        self.assertEqual((document.names, document.aborted, closed), (["ConfirmedGrid"], 1, [False]))
        self.assertEqual(application.filters, [])

    def test_standard_buttons_unwrap_pyside6_value_before_int(self):
        function = next(node for node in self.tree.body if isinstance(node, ast.FunctionDef) and node.name == "standard_buttons_value")
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(PANEL), "exec"), namespace)
        class StrictButton(enum.Flag):
            Ok = 1
            Cancel = 2
            def __int__(self):
                raise TypeError("PySide6 StandardButton is not directly convertible")
        box = type("ButtonBox", (), {"StandardButton": StrictButton})
        self.assertEqual(namespace["standard_buttons_value"](box), 3)


if __name__ == "__main__":
    unittest.main()
