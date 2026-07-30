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
        result = self.module.SnapAdapter().resolve(view, (11, 10), self.document)
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
        result = self.module.SnapAdapter().resolve(view, (1, 2), self.document)
        self.assertTrue(result.snapped)
        self.assertEqual(result.subelement_name, "Edge1.Endpoint1")

    def test_endpoint_outside_tolerance_uses_projection(self):
        point = Vector(0, 0, 0)
        edge = types.SimpleNamespace(Vertexes=[types.SimpleNamespace(Point=point)])
        self.add_object({"Edge1": edge})
        view = FakeView([self.info("Edge1")], {id(point): (30, 30)})
        result = self.module.SnapAdapter(12).resolve(view, (0, 0), self.document)
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
        result = self.module.SnapAdapter().resolve(view, (5, 5), self.document)
        self.assertEqual(result.subelement_name, "Vertex2")

    def test_invalid_objects_and_components_fall_back_safely(self):
        cases = [
            ([], self.info("Vertex1")),
            ([("hidden", {"Vertex1": types.SimpleNamespace(Point=Vector(0, 0, 0))})],
             self.info("Vertex1")),
        ]
        result = self.module.SnapAdapter().resolve(
            FakeView([cases[0][1]]), (1, 1), self.document
        )
        self.assertTrue(result.projected)
        self.add_object(visible=False)
        result = self.module.SnapAdapter().resolve(
            FakeView([self.info("Vertex1")]), (1, 1), self.document
        )
        self.assertTrue(result.projected)
        self.add_object(shape=False)
        result = self.module.SnapAdapter().resolve(
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
        result = self.module.SnapAdapter().resolve(view, (0, 0), self.document)
        self.assertEqual(
            (result.point.x, result.point.y, result.point.z), (101, 202, 303)
        )

    def test_parser_error_does_not_interrupt_projection_fallback(self):
        self.add_object()
        view = FakeView()
        view.infos = [{"Object": "Beam", "Component": "Vertex1"}]
        original = self.module.SnapAdapter._parse_info
        self.module.SnapAdapter._parse_info = staticmethod(
            lambda _info: (_ for _ in ()).throw(RuntimeError("parser"))
        )
        try:
            result = self.module.SnapAdapter().resolve(view, (2, 3), self.document)
        finally:
            self.module.SnapAdapter._parse_info = original
        self.assertTrue(result.projected)
        self.assertIn("RuntimeError: parser", self.console.errors[0])


if __name__ == "__main__":
    unittest.main()
