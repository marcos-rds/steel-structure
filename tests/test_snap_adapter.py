"""Tests for the basic vertex and edge-endpoint snap adapter."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "freecad" / "BancadaFCSteel" / "interactive" / "snap_adapter.py"
)


class Vector:
    def __init__(self, x, y=None, z=None):
        if y is None:
            x, y, z = x.x, x.y, x.z
        self.x, self.y, self.z = x, y, z


class FakeObject:
    def __init__(self, document, subelements=None, visible=True, shape=True):
        self.Document = document
        self.ViewObject = types.SimpleNamespace(Visibility=visible)
        if shape:
            self.Shape = object()
        self._subelements = subelements or {}
        self.calls = []

    def getSubObject(self, name):
        self.calls.append(name)
        return self._subelements.get(name)


class FakeDocument:
    def __init__(self, name="Doc"):
        self.Name = name
        self.objects = {}

    def getObject(self, name):
        return self.objects.get(name)


class FakeView:
    def __init__(self, infos=(), projection=None):
        self.infos = infos
        self.projection = projection or {}
        self.projected = Vector(90, 80, 70)
        self.info_error = None

    def getObjectsInfo(self, _position):
        if self.info_error:
            raise self.info_error
        return self.infos

    def getObjectInfo(self, _position):
        return None

    def getPointOnScreen(self, point):
        return self.projection[id(point)]

    def getPoint(self, _x, _y):
        return self.projected


def load_module():
    old = sys.modules.get("FreeCAD")
    console = types.SimpleNamespace(errors=[], PrintError=lambda message: console.errors.append(message))
    sys.modules["FreeCAD"] = types.SimpleNamespace(Vector=Vector, Console=console)
    name = "_snap_adapter_test"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

    def cleanup():
        sys.modules.pop(name, None)
        if old is None:
            sys.modules.pop("FreeCAD", None)
        else:
            sys.modules["FreeCAD"] = old

    return module, console, cleanup


class SnapAdapterTests(unittest.TestCase):
    def setUp(self):
        self.module, self.console, self.cleanup = load_module()
        self.document = FakeDocument()

    def tearDown(self):
        self.cleanup()

    @staticmethod
    def info(component, obj="Beam", document="Doc"):
        return {"Document": document, "Object": obj, "Component": component}

    def add_object(self, subelements=None, **kwargs):
        obj = FakeObject(self.document, subelements, **kwargs)
        self.document.objects["Beam"] = obj
        return obj

    def test_valid_vertex_returns_exact_global_point_and_metadata(self):
        point = Vector(1, 2, 3)
        obj = self.add_object({"Vertex1": types.SimpleNamespace(Point=point)})
        view = FakeView([self.info("Vertex1")], {id(point): (10, 10)})
        result = self.module.BasicEndpointSnapAdapter().resolve(view, (11, 10), self.document)
        self.assertTrue(result.snapped)
        self.assertEqual((result.point.x, result.point.y, result.point.z), (1, 2, 3))
        self.assertEqual((result.snap_type, result.object_name, result.subelement_name),
                         ("endpoint", "Beam", "Vertex1"))
        self.assertEqual(obj.calls, ["Vertex1"])

    def test_edge_chooses_nearest_endpoint_within_tolerance(self):
        first, second = Vector(0, 0, 0), Vector(100, 0, 0)
        edge = types.SimpleNamespace(
            Vertexes=[types.SimpleNamespace(Point=first), types.SimpleNamespace(Point=second)]
        )
        self.add_object({"Edge1": edge})
        view = FakeView([self.info("Edge1")], {id(first): (3, 4), id(second): (20, 20)})
        result = self.module.BasicEndpointSnapAdapter().resolve(view, (1, 2), self.document)
        self.assertTrue(result.snapped)
        self.assertEqual(result.subelement_name, "Edge1.Endpoint1")

    def test_endpoint_outside_tolerance_uses_projection(self):
        point = Vector(0, 0, 0)
        edge = types.SimpleNamespace(Vertexes=[types.SimpleNamespace(Point=point)])
        self.add_object({"Edge1": edge})
        view = FakeView([self.info("Edge1")], {id(point): (30, 30)})
        result = self.module.BasicEndpointSnapAdapter(12).resolve(view, (0, 0), self.document)
        self.assertFalse(result.snapped)
        self.assertTrue(result.projected)
        self.assertEqual((result.point.x, result.point.y), (90, 80))

    def test_explicit_vertex_wins_equal_distance_and_result_is_deterministic(self):
        point = Vector(1, 0, 0)
        vertex = types.SimpleNamespace(Point=point)
        edge = types.SimpleNamespace(Vertexes=[types.SimpleNamespace(Point=point)])
        self.add_object({"Vertex2": vertex, "Edge1": edge})
        view = FakeView(
            [self.info("Edge1"), self.info("Vertex2")], {id(point): (5, 5)}
        )
        result = self.module.BasicEndpointSnapAdapter().resolve(view, (5, 5), self.document)
        self.assertEqual(result.subelement_name, "Vertex2")

    def test_invalid_objects_and_components_fall_back_safely(self):
        cases = [
            ([], self.info("Vertex1")),
            ([("hidden", {"Vertex1": types.SimpleNamespace(Point=Vector(0, 0, 0))})],
             self.info("Vertex1")),
        ]
        result = self.module.BasicEndpointSnapAdapter().resolve(
            FakeView([cases[0][1]]), (1, 1), self.document
        )
        self.assertTrue(result.projected)
        self.add_object(visible=False)
        result = self.module.BasicEndpointSnapAdapter().resolve(
            FakeView([self.info("Vertex1")]), (1, 1), self.document
        )
        self.assertTrue(result.projected)
        self.add_object(shape=False)
        result = self.module.BasicEndpointSnapAdapter().resolve(
            FakeView([self.info("Face1")]), (1, 1), self.document
        )
        self.assertTrue(result.projected)

    def test_transformed_subobject_is_not_placed_twice(self):
        global_point = Vector(101, 202, 303)
        obj = self.add_object(
            {"Vertex1": types.SimpleNamespace(Point=global_point)}
        )
        obj.Placement = types.SimpleNamespace(Base=Vector(1000, 1000, 1000))
        view = FakeView([self.info("Vertex1")], {id(global_point): (0, 0)})
        result = self.module.BasicEndpointSnapAdapter().resolve(view, (0, 0), self.document)
        self.assertEqual(
            (result.point.x, result.point.y, result.point.z), (101, 202, 303)
        )

    def test_parser_error_does_not_interrupt_projection_fallback(self):
        self.add_object()
        view = FakeView()
        view.infos = [{"Object": "Beam", "Component": "Vertex1"}]
        original = self.module.BasicEndpointSnapAdapter._parse_info
        self.module.BasicEndpointSnapAdapter._parse_info = staticmethod(
            lambda _info: (_ for _ in ()).throw(RuntimeError("parser"))
        )
        try:
            result = self.module.BasicEndpointSnapAdapter().resolve(view, (2, 3), self.document)
        finally:
            self.module.BasicEndpointSnapAdapter._parse_info = original
        self.assertTrue(result.projected)
        self.assertIn("RuntimeError: parser", self.console.errors[0])


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, value):
        for callback in self.callbacks:
            callback(value)


class FakeToolbar:
    def __init__(self, object_name="Draft Snap", title="Encaixe de Draft", visible=False):
        self.object_name = object_name
        self.title = title
        self.visible = visible
        self.visibilityChanged = Signal()
        self.show_calls = self.hide_calls = 0

    def objectName(self):
        return self.object_name

    def windowTitle(self):
        return self.title

    def isVisible(self):
        return self.visible

    def show(self):
        self.show_calls += 1
        self.visible = True
        self.visibilityChanged.emit(True)

    def hide(self):
        self.hide_calls += 1
        self.visible = False
        self.visibilityChanged.emit(False)


class FakeMainWindow:
    def __init__(self, toolbars=()):
        self.toolbars = list(toolbars)
        self.find_names = []

    def findChild(self, _kind, name):
        self.find_names.append(name)
        return next(
            (toolbar for toolbar in self.toolbars if toolbar.objectName() == name),
            None,
        )

    def findChildren(self, _kind):
        return self.toolbars


class FakeNativeSnapper:
    def __init__(self, point=None, mode="endpoint", info=None):
        self.point = point or Vector(7, 8, 9)
        self.cursorMode = mode
        self.snapInfo = info or {"Object": "Beam", "Component": "Vertex1"}
        self.calls = []
        self.off_calls = 0

    def snap(self, position, **options):
        self.calls.append((position, options))
        return self.point

    def off(self):
        self.off_calls += 1


class NativeDraftSnapTests(unittest.TestCase):
    def setUp(self):
        self.module, _console, self.cleanup = load_module()
        self.toolbar = FakeToolbar()
        self.window = FakeMainWindow([self.toolbar])
        self.snapper = FakeNativeSnapper()
        self.gui = types.SimpleNamespace(
            Snapper=self.snapper, getMainWindow=lambda: self.window
        )

    def tearDown(self):
        self.cleanup()

    def test_existing_snapper_is_reused_and_native_result_has_priority(self):
        fallback = types.SimpleNamespace(
            calls=0,
            resolve=lambda *_args, **_kwargs: setattr(fallback, "calls", fallback.calls + 1),
        )
        adapter = self.module.SnapAdapter(self.gui, fallback)
        self.assertTrue(adapter.start())
        result = adapter.resolve(
            object(), (4, 5), lastpoint=Vector(1, 2, 3),
            active=True, constrain=True,
        )
        self.assertTrue(result.native)
        self.assertEqual((result.point.x, result.point.y, result.point.z), (7, 8, 9))
        position, options = self.snapper.calls[0]
        self.assertEqual(position, (4, 5))
        self.assertEqual(options["lastpoint"].x, 1)
        self.assertTrue(options["active"])
        self.assertTrue(options["constrain"])
        self.assertTrue(options["noTracker"])
        self.assertEqual(fallback.calls, 0)

    def test_native_modes_are_forwarded_as_metadata(self):
        modes = (
            "endpoint", "midpoint", "center", "angle", "intersection",
            "perpendicular", "extension", "parallel", "special", "passive",
            "ortho", "grid",
        )
        adapter = self.module.SnapAdapter(self.gui)
        for mode in modes:
            self.snapper.cursorMode = mode
            result = adapter.resolve(object(), (0, 0), active=True)
            self.assertEqual(result.snap_type, mode)
            self.assertTrue(result.snapped)

    def test_working_plane_result_is_native_but_not_geometric(self):
        self.snapper.cursorMode = None
        self.snapper.snapInfo = None
        result = self.module.SnapAdapter(self.gui).resolve(object(), (0, 0))
        self.assertTrue(result.native)
        self.assertFalse(result.snapped)
        self.assertTrue(result.projected)

    def test_native_error_uses_endpoint_fallback(self):
        self.snapper.snap = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("native")
        )
        expected = self.module.SnapResult(
            point=Vector(1, 1, 1), snapped=True, mechanism="endpoint-fallback"
        )
        fallback = types.SimpleNamespace(resolve=lambda *_args, **_kwargs: expected)
        result = self.module.SnapAdapter(self.gui, fallback).resolve(object(), (0, 0))
        self.assertIs(result, expected)

    def test_toolbar_lookup_prefers_object_name_and_restores_visibility(self):
        manager = self.module.DraftSnapToolbarManager(self.gui)
        self.assertTrue(manager.show())
        self.assertEqual(self.window.find_names, ["Draft Snap"])
        self.assertEqual(self.toolbar.show_calls, 1)
        manager.restore()
        self.assertEqual(self.toolbar.hide_calls, 1)

    def test_toolbar_title_fallback_reuses_existing_toolbar(self):
        self.toolbar.object_name = "translated_object"
        manager = self.module.DraftSnapToolbarManager(self.gui)
        self.assertIs(manager.find(), self.toolbar)
        self.assertEqual(self.window.toolbars, [self.toolbar])

    def test_user_visibility_change_is_not_overwritten(self):
        manager = self.module.DraftSnapToolbarManager(self.gui)
        manager.show()
        self.toolbar.visibilityChanged.emit(False)
        manager.restore()
        self.assertEqual(self.toolbar.hide_calls, 0)

    def test_initially_visible_toolbar_is_restored_after_native_cleanup(self):
        self.toolbar.visible = True
        manager = self.module.DraftSnapToolbarManager(self.gui)
        manager.show()
        manager._changing_visibility = True
        self.toolbar.hide()
        manager._changing_visibility = False
        manager.restore()
        self.assertTrue(self.toolbar.visible)

    def test_stop_calls_off_and_does_not_modify_snap_modes(self):
        active_snaps = ["Lock", "Endpoint"]
        self.snapper.active_snaps = active_snaps
        adapter = self.module.SnapAdapter(self.gui)
        adapter.start()
        adapter.stop()
        adapter.stop()
        self.assertEqual(self.snapper.active_snaps, active_snaps)
        self.assertEqual(self.snapper.off_calls, 1)

    def test_missing_toolbar_does_not_disable_native_snap(self):
        self.window.toolbars = []
        adapter = self.module.SnapAdapter(self.gui)
        self.assertTrue(adapter.start())
        self.assertTrue(adapter.resolve(object(), (1, 2)).native)


if __name__ == "__main__":
    unittest.main()
