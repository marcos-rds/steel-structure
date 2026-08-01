"""Tests for the minimal FreeCAD Structural Grid document object."""

from __future__ import annotations

import ast
import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "freecad/BancadaFCSteel"
GRID_PATH = PACKAGE_PATH / "grid.py"
SUPPORTED_PROPERTY_TYPES = {
    "App::PropertyString",
    "App::PropertyInteger",
    "App::PropertyFloatList",
    "App::PropertyLength",
    "App::PropertyEnumeration",
    "App::PropertyStringList",
    "App::PropertyVectorList",
}


class Quantity:
    def __init__(self, value):
        self.Value = float(getattr(value, "Value", value))

    def __eq__(self, other):
        return self.Value == float(getattr(other, "Value", other))


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def as_tuple(self):
        return self.x, self.y, self.z

    def __eq__(self, other):
        return self.as_tuple() == other.as_tuple()


class Rotation:
    def __init__(self, *args):
        if len(args) == 4:
            self.Q = tuple(float(value) for value in args)
        elif len(args) == 2:
            axis, angle = args
            half = math.radians(float(angle)) / 2.0
            scale = math.sin(half)
            self.Q = (axis.x * scale, axis.y * scale, axis.z * scale, math.cos(half))
        elif len(args) == 1 and isinstance(args[0], Rotation):
            self.Q = tuple(args[0].Q)
        else:
            self.Q = (0.0, 0.0, 0.0, 1.0)


class Placement:
    def __init__(self, base=None, rotation=None):
        if isinstance(base, Placement):
            self.Base = Vector(*base.Base.as_tuple())
            self.Rotation = Rotation(base.Rotation)
        else:
            self.Base = Vector(*(base.as_tuple() if isinstance(base, Vector) else (0, 0, 0)))
            self.Rotation = Rotation(rotation) if isinstance(rotation, Rotation) else Rotation()

    def copy(self):
        return Placement(self)


class FakeConsole:
    errors = []

    @classmethod
    def PrintError(cls, message):
        cls.errors.append(message)


class FakeObject:
    def __init__(self, type_id, name, callbacks_on_add=False):
        object.__setattr__(self, "TypeId", type_id)
        object.__setattr__(self, "Name", name)
        object.__setattr__(self, "Label", name)
        object.__setattr__(self, "Placement", Placement())
        object.__setattr__(self, "PropertiesList", [])
        object.__setattr__(self, "property_records", {})
        object.__setattr__(self, "editor_modes", {})
        object.__setattr__(self, "enum_options", {})
        object.__setattr__(self, "fail_assignments", set())
        object.__setattr__(self, "Proxy", None)
        object.__setattr__(self, "callbacks_on_add", callbacks_on_add)
        object.__setattr__(self, "add_callbacks", [])
        object.__setattr__(self, "placement_assignments", [])
        object.__setattr__(self, "reset_placement_on_shape", False)

    def addProperty(self, property_type, name, group, description):
        if property_type not in SUPPORTED_PROPERTY_TYPES:
            raise TypeError(f"Invalid type {property_type} for property {self.Name}.{name}")
        self.PropertiesList.append(name)
        self.property_records[name] = (property_type, group, description)
        object.__setattr__(self, name, None)
        if self.callbacks_on_add and self.Proxy is not None:
            self.add_callbacks.append(name)
            self.Proxy.onChanged(self, name)

    def setEditorMode(self, name, mode):
        self.editor_modes[name] = mode

    def __setattr__(self, name, value):
        if name in self.__dict__.get("fail_assignments", set()):
            raise RuntimeError(f"deliberate assignment failure: {name}")
        if name == "Placement":
            self.__dict__.get("placement_assignments", []).append(Placement(value))
        if name == "Shape" and self.__dict__.get("reset_placement_on_shape", False):
            self.Placement = Placement()
        record = self.__dict__.get("property_records", {}).get(name)
        if record and record[0] == "App::PropertyEnumeration" and isinstance(value, list):
            self.enum_options[name] = list(value)
            object.__setattr__(self, name, value[0] if value else "")
            return
        if record and record[0] in {"App::PropertyLength", "App::PropertyDistance"}:
            value = Quantity(value)
        elif record and record[0] == "App::PropertyFloatList":
            value = [float(getattr(item, "Value", item)) for item in value]
        object.__setattr__(self, name, value)


class FakeDocument:
    def __init__(self):
        self.calls = []
        self.objects = []
        self.recompute_count = 0
        self.removed = []

    def addObject(self, type_id, name):
        self.calls.append((type_id, name))
        obj = FakeObject(type_id, name)
        self.objects.append(obj)
        return obj

    def recompute(self):
        self.recompute_count += 1
        for obj in self.objects:
            if obj.Proxy is not None:
                obj.Proxy.execute(obj)

    def removeObject(self, name):
        self.removed.append(name)
        self.objects = [obj for obj in self.objects if obj.Name != name]


class FakePart(types.ModuleType):
    def __init__(self):
        super().__init__("Part")
        self.lines = []
        self.vertices = []
        self.compounds = []

    def makeLine(self, start, end):
        if start == end:
            raise ValueError("Part.makeLine does not accept identical points")
        edge = ("edge", start, end)
        self.lines.append(edge)
        return edge

    def Vertex(self, point):
        vertex = ("vertex", point)
        self.vertices.append(vertex)
        return vertex

    def makeCompound(self, edges):
        compound = ("compound", tuple(edges))
        self.compounds.append(compound)
        return compound


def load_modules():
    for name in ("FreeCAD", "Part", "BancadaFCSteel.grid", "BancadaFCSteel.grid_geometry", "BancadaFCSteel"):
        sys.modules.pop(name, None)
    app = types.ModuleType("FreeCAD")
    app.Vector = Vector
    app.Rotation = Rotation
    app.Placement = Placement
    app.Console = FakeConsole
    part = FakePart()
    package = types.ModuleType("BancadaFCSteel")
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules.update({"FreeCAD": app, "Part": part, "BancadaFCSteel": package})
    for short_name in ("grid_geometry", "grid"):
        name = f"BancadaFCSteel.{short_name}"
        spec = importlib.util.spec_from_file_location(name, PACKAGE_PATH / f"{short_name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["BancadaFCSteel.grid"], part


grid, PART = load_modules()


class GridObjectTests(unittest.TestCase):
    def setUp(self):
        PART.lines.clear()
        PART.vertices.clear()
        PART.compounds.clear()
        FakeConsole.errors.clear()
        self.document = FakeDocument()

    def create(self, **kwargs):
        return grid.create_grid(self.document, **kwargs)

    def test_factory_creates_exactly_one_feature_python_with_expected_name_and_proxy(self):
        obj = self.create()
        self.assertEqual(self.document.calls, [("Part::FeaturePython", "StructuralGrid")])
        self.assertEqual((obj.TypeId, obj.Name), ("Part::FeaturePython", "StructuralGrid"))
        self.assertIsInstance(obj.Proxy, grid.StructuralGridProxy)

    def test_property_types_and_groups(self):
        obj = self.create()
        expected = {
            "GridType": ("App::PropertyString", "Identity"), "SchemaVersion": ("App::PropertyInteger", "Identity"),
            "DisplayName": ("App::PropertyString", "Identity"), "XSpacings": ("App::PropertyFloatList", "Grid"),
            "YSpacings": ("App::PropertyFloatList", "Grid"), "XStartExtension": ("App::PropertyLength", "Grid"),
            "XEndExtension": ("App::PropertyLength", "Grid"), "YStartExtension": ("App::PropertyLength", "Grid"),
            "YEndExtension": ("App::PropertyLength", "Grid"), "XAxisIdentification": ("App::PropertyEnumeration", "Identification"),
            "YAxisIdentification": ("App::PropertyEnumeration", "Identification"), "XAxisLabels": ("App::PropertyStringList", "Identification"),
            "YAxisLabels": ("App::PropertyStringList", "Identification"), "OverallLengthX": ("App::PropertyLength", "Results"),
            "OverallLengthY": ("App::PropertyLength", "Results"), "DisplayedLengthX": ("App::PropertyLength", "Results"),
            "DisplayedLengthY": ("App::PropertyLength", "Results"), "XAxisCount": ("App::PropertyInteger", "Results"),
            "YAxisCount": ("App::PropertyInteger", "Results"), "IntersectionCount": ("App::PropertyInteger", "Results"),
            "IntersectionPoints": ("App::PropertyVectorList", "Results"), "IntersectionKeys": ("App::PropertyStringList", "Results"),
        }
        self.assertEqual({name: record[:2] for name, record in obj.property_records.items()}, expected)
        self.assertEqual(obj.property_records["XStartExtension"][0], "App::PropertyLength")
        self.assertEqual(obj.property_records["YEndExtension"][0], "App::PropertyLength")
        self.assertIn("milímetros", obj.property_records["XSpacings"][2])
        self.assertIn("milímetros", obj.property_records["YSpacings"][2])

    def test_double_accepts_only_explicit_real_property_types(self):
        self.assertIn("App::PropertyFloatList", SUPPORTED_PROPERTY_TYPES)
        self.assertNotIn("App::PropertyLengthList", SUPPORTED_PROPERTY_TYPES)
        obj = FakeObject("Part::FeaturePython", "Grid")
        for property_type in SUPPORTED_PROPERTY_TYPES:
            with self.subTest(property_type=property_type):
                obj.addProperty(property_type, property_type.rsplit("Property", 1)[-1], "Test", "")
        with self.assertRaisesRegex(TypeError, "Invalid type App::PropertyLengthList"):
            obj.addProperty("App::PropertyLengthList", "Invalid", "Test", "")

    def test_length_list_adapter_accepts_floats_and_quantities_as_millimetres(self):
        self.assertEqual(grid._length_list([1.5, Quantity(2.25)]), [1.5, 2.25])
        obj = self.create(x_spacings=[1000.0, 2500.0], y_spacings=[Quantity(750.0)])
        self.assertEqual((obj.OverallLengthX.Value, obj.OverallLengthY.Value), (3500.0, 750.0))

    def test_defaults_and_read_only_properties(self):
        obj = self.create()
        self.assertEqual(obj.XSpacings, [6000.0, 6000.0])
        self.assertEqual(obj.YSpacings, [5000.0, 5000.0])
        self.assertTrue(all(getattr(obj, name).Value == 1000 for name in ("XStartExtension", "XEndExtension", "YStartExtension", "YEndExtension")))
        self.assertEqual((obj.GridType, obj.SchemaVersion, obj.DisplayName), ("StructuralGrid", 1, "StructuralGrid"))
        self.assertEqual((obj.XAxisIdentification, obj.YAxisIdentification), ("Numeric", "Alphabetic"))
        self.assertEqual(set(obj.editor_modes), set(grid._READ_ONLY_PROPERTIES))
        self.assertTrue(all(mode == 1 for mode in obj.editor_modes.values()))

    def test_existing_properties_are_not_recreated_or_reset(self):
        obj = FakeObject("Part::FeaturePython", "Existing")
        obj.addProperty("App::PropertyString", "GridType", "Identity", "existing")
        obj.GridType = "keep"
        grid.StructuralGridProxy(obj)
        self.assertEqual(obj.PropertiesList.count("GridType"), 1)
        self.assertEqual(obj.GridType, "keep")

    def test_partial_schema_missing_y_properties_is_repaired_before_execute(self):
        for missing in (("YAxisIdentification",), ("YSpacings",), ("YAxisIdentification", "YSpacings")):
            with self.subTest(missing=missing):
                obj = self.create(); placement = obj.Placement
                for name in missing:
                    obj.PropertiesList.remove(name); obj.property_records.pop(name); object.__delattr__(obj, name)
                FakeConsole.errors.clear(); obj.Proxy.execute(obj)
                self.assertTrue(set(missing).issubset(obj.PropertiesList))
                self.assertIs(obj.Placement, placement)
                self.assertFalse(FakeConsole.errors)

    def test_only_x_properties_and_different_order_receive_missing_defaults_only(self):
        obj = FakeObject("Part::FeaturePython", "Partial")
        obj.addProperty("App::PropertyFloatList", "XSpacings", "Grid", "existing")
        obj.XSpacings = []
        obj.addProperty("App::PropertyEnumeration", "XAxisIdentification", "Identification", "existing")
        obj.XAxisIdentification = list(grid.IDENTIFICATION_OPTIONS); obj.XAxisIdentification = "Custom"
        obj.addProperty("App::PropertyStringList", "XAxisLabels", "Identification", "existing")
        obj.XAxisLabels = ["EIXO-A"]
        grid.StructuralGridProxy(obj)
        self.assertEqual(obj.XSpacings, [])
        self.assertEqual((obj.XAxisIdentification, obj.XAxisLabels), ("Custom", ["EIXO-A"]))
        self.assertEqual(obj.YSpacings, [5000.0, 5000.0])
        self.assertEqual(obj.YAxisIdentification, "Alphabetic")

    def test_add_property_callbacks_are_immediate_but_never_execute_partial_geometry(self):
        obj = FakeObject("Part::FeaturePython", "Callbacks", callbacks_on_add=True)
        proxy = grid.StructuralGridProxy(obj)
        self.assertEqual(set(obj.add_callbacks), set(grid.REQUIRED_GRID_DATA_PROPERTIES))
        self.assertTrue(proxy._schema_complete(obj))
        self.assertFalse(FakeConsole.errors)

    def test_restore_preserves_existing_values_labels_names_placement_and_enum_selection(self):
        obj = self.create(x_spacings=[], y_spacings=[123], x_identification="Custom",
                          y_identification="Custom", x_labels=["X"], y_labels=["Y1", "Y2"],
                          display_name="Grid antigo")
        placement = obj.Placement; label = obj.Label
        obj.PropertiesList.remove("IntersectionKeys"); obj.property_records.pop("IntersectionKeys"); del obj.IntersectionKeys
        proxy = grid.StructuralGridProxy.__new__(grid.StructuralGridProxy); proxy.__setstate__(None); obj.Proxy = proxy
        proxy.onDocumentRestored(obj)
        self.assertEqual((obj.XSpacings, obj.YSpacings), ([], [123.0]))
        self.assertEqual((obj.XAxisIdentification, obj.YAxisIdentification), ("Custom", "Custom"))
        self.assertEqual((obj.XAxisLabels, obj.YAxisLabels), (["X"], ["Y1", "Y2"]))
        self.assertEqual((obj.Label, obj.DisplayName), (label, "Grid antigo"))
        self.assertIs(obj.Placement, placement)
        self.assertEqual(obj.enum_options["XAxisIdentification"], list(grid.IDENTIFICATION_OPTIONS))

    def assertPlacement(self, obj, base, rotation=None):
        self.assertEqual(obj.Placement.Base.as_tuple(), tuple(float(value) for value in base))
        if rotation is not None:
            for actual, expected in zip(obj.Placement.Rotation.Q, rotation.Q):
                self.assertAlmostEqual(actual, expected)

    def restored_proxy(self, obj):
        proxy = grid.StructuralGridProxy.__new__(grid.StructuralGridProxy)
        proxy.__setstate__(None)
        obj.Proxy = proxy
        return proxy

    def test_new_grid_has_identity_placement_without_python_assignment(self):
        obj = self.create()
        self.assertPlacement(obj, (0, 0, 0), Rotation())
        self.assertEqual(obj.placement_assignments, [])

    def test_restore_preserves_all_translations_rotation_and_combination(self):
        cases = (
            ((0, 0, 3000), Rotation()),
            ((1500, 0, 0), Rotation()),
            ((0, -2000, 0), Rotation()),
            ((1500, -2000, 3000), Rotation()),
            ((0, 0, 0), Rotation(Vector(0, 0, 1), 30)),
            ((1500, -2000, 3000), Rotation(Vector(0, 0, 1), 30)),
        )
        for base, rotation in cases:
            with self.subTest(base=base, quaternion=rotation.Q):
                obj = self.create(); obj.Placement = Placement(Vector(*base), rotation)
                obj.placement_assignments.clear()
                proxy = self.restored_proxy(obj); proxy.onDocumentRestored(obj)
                self.assertPlacement(obj, base, rotation)
                self.assertEqual(obj.placement_assignments, [])

    def test_shape_assignment_reset_during_restore_is_detected_and_repaired(self):
        obj = self.create(); obj.Placement = Placement(Vector(1500, -2000, 3000), Rotation(Vector(0, 0, 1), 30))
        expected = obj.Placement.copy(); obj.placement_assignments.clear()
        obj.reset_placement_on_shape = True
        self.restored_proxy(obj).onDocumentRestored(obj)
        self.assertPlacement(obj, expected.Base.as_tuple(), expected.Rotation)
        self.assertEqual(len(obj.placement_assignments), 2)
        self.assertPlacement(types.SimpleNamespace(Placement=obj.placement_assignments[0]), (0, 0, 0), Rotation())

    def test_execute_and_repeated_recomputes_do_not_change_placement(self):
        obj = self.create(); obj.Placement = Placement(Vector(1, 2, 3000), Rotation(Vector(0, 0, 1), 30))
        expected = obj.Placement.copy(); obj.placement_assignments.clear()
        for _ in range(5):
            obj.Proxy.execute(obj)
        self.assertPlacement(obj, expected.Base.as_tuple(), expected.Rotation)
        self.assertEqual(obj.placement_assignments, [])

    def test_schema_setup_enumerations_and_missing_properties_preserve_placement(self):
        for missing in (None, "YSpacings", "YAxisIdentification"):
            with self.subTest(missing=missing):
                obj = self.create(); obj.Placement = Placement(Vector(4, 5, 6), Rotation(Vector(0, 0, 1), 30))
                if missing:
                    obj.PropertiesList.remove(missing); obj.property_records.pop(missing); object.__delattr__(obj, missing)
                expected = obj.Placement.copy(); obj.placement_assignments.clear()
                obj.Proxy._setup_properties(obj, refresh_enumerations=True)
                self.assertTrue(obj.Proxy._ensure_grid_schema(obj, refresh_enumerations=True))
                self.assertPlacement(obj, expected.Base.as_tuple(), expected.Rotation)
                self.assertEqual(obj.placement_assignments, [])

    def test_repeated_restore_old_partial_custom_and_empty_grid_is_idempotent(self):
        obj = self.create(x_spacings=[], y_spacings=[], x_identification="Custom",
                          y_identification="Custom", x_labels=["X"], y_labels=["Y"])
        obj.Placement = Placement(Vector(7, 8, 9), Rotation(Vector(0, 0, 1), 30))
        obj.PropertiesList.remove("YSpacings"); obj.property_records.pop("YSpacings"); del obj.YSpacings
        expected = obj.Placement.copy(); obj.placement_assignments.clear()
        proxy = self.restored_proxy(obj)
        for _ in range(3): proxy.onDocumentRestored(obj)
        self.assertPlacement(obj, expected.Base.as_tuple(), expected.Rotation)
        self.assertEqual(obj.placement_assignments, [])
        self.assertEqual((obj.XAxisIdentification, obj.YAxisIdentification), ("Custom", "Custom"))

    def test_repair_failure_does_not_zero_placement_or_report_view(self):
        obj = self.create(); obj.Placement = Placement(Vector(10, 20, 3000), Rotation())
        obj.PropertiesList.remove("YSpacings"); obj.property_records.pop("YSpacings"); del obj.YSpacings
        obj.fail_assignments.add("YSpacings"); expected = obj.Placement.copy(); obj.placement_assignments.clear()
        self.restored_proxy(obj).onDocumentRestored(obj)
        self.assertPlacement(obj, expected.Base.as_tuple(), expected.Rotation)
        self.assertEqual(obj.placement_assignments, [])
        self.assertFalse(FakeConsole.errors)

    def test_shape_and_intersections_remain_local_without_duplicate_transform(self):
        obj = self.create(x_spacings=[10], y_spacings=[20])
        local_start = obj.Shape[1][0][1]
        self.assertEqual(local_start.as_tuple(), (0, -1000, 0))
        self.assertTrue(all(point.z == 0 for point in obj.IntersectionPoints))
        obj.Placement = Placement(Vector(1500, -2000, 3000), Rotation())
        self.assertEqual(local_start.as_tuple(), (0, -1000, 0))
        self.assertEqual((local_start.x + obj.Placement.Base.x,
                          local_start.y + obj.Placement.Base.y,
                          local_start.z + obj.Placement.Base.z), (1500, -3000, 3000))

    def test_schema_repair_is_idempotent_and_never_duplicates_properties(self):
        obj = self.create(); proxy = obj.Proxy; before = list(obj.PropertiesList)
        for _ in range(5):
            self.assertTrue(proxy._ensure_grid_schema(obj, refresh_enumerations=True))
            proxy.execute(obj)
        self.assertEqual(obj.PropertiesList, before)
        self.assertEqual(len(obj.PropertiesList), len(set(obj.PropertiesList)))
        self.assertFalse(FakeConsole.errors)

    def test_execute_silently_ignores_removed_or_cancelled_object(self):
        class Removed:
            @property
            def PropertiesList(self): raise ReferenceError("object deleted")
        proxy = grid.StructuralGridProxy.__new__(grid.StructuralGridProxy); proxy.__setstate__(None)
        FakeConsole.errors.clear(); proxy.execute(Removed()); proxy.onChanged(Removed(), "YSpacings")
        self.assertFalse(FakeConsole.errors)

    def test_default_geometry_results_shape_and_local_coordinates(self):
        obj = self.create()
        self.assertEqual(obj.Shape[0], "compound")
        self.assertEqual(len(obj.Shape[1]), 6)
        self.assertEqual(len(PART.vertices), 0)
        self.assertEqual((obj.XAxisCount, obj.YAxisCount, obj.IntersectionCount), (3, 3, 9))
        self.assertEqual((obj.OverallLengthX.Value, obj.OverallLengthY.Value), (12000, 10000))
        self.assertEqual((obj.DisplayedLengthX.Value, obj.DisplayedLengthY.Value), (14000, 12000))
        self.assertEqual(obj.Shape[1][0][1].as_tuple(), (0, -1000, 0))
        self.assertEqual(obj.Shape[1][0][2].as_tuple(), (0, 11000, 0))
        self.assertEqual(obj.IntersectionPoints[3].as_tuple(), (6000, 0, 0))
        self.assertEqual(obj.IntersectionKeys[:4], ["1/A", "1/B", "1/C", "2/A"])

    def test_extensions_affect_lines_and_displayed_not_overall_lengths(self):
        obj = self.create(x_spacings=[10], y_spacings=[20], x_start_extension=1, x_end_extension=2, y_start_extension=3, y_end_extension=4)
        self.assertEqual((obj.OverallLengthX.Value, obj.OverallLengthY.Value), (10, 20))
        self.assertEqual((obj.DisplayedLengthX.Value, obj.DisplayedLengthY.Value), (13, 27))
        self.assertEqual(obj.Shape[1][0][1].as_tuple(), (0, -3, 0))
        self.assertEqual(obj.Shape[1][2][1].as_tuple(), (-1, 0, 0))

    def test_empty_x_spacings_use_vertices_without_zero_length_lines(self):
        obj = self.create(x_spacings=[], y_spacings=[10])
        self.assertEqual((obj.XAxisCount, obj.YAxisCount, obj.IntersectionCount), (1, 2, 2))
        self.assertEqual((len(PART.lines), len(PART.vertices)), (3, 0))
        self.assertEqual([item[0] for item in obj.Shape[1]], ["edge", "edge", "edge"])
        self.assertFalse(FakeConsole.errors)

    def test_empty_y_spacings_use_vertices_without_zero_length_lines(self):
        obj = self.create(x_spacings=[10], y_spacings=[])
        self.assertEqual((obj.XAxisCount, obj.YAxisCount, obj.IntersectionCount), (2, 1, 2))
        self.assertEqual((len(PART.lines), len(PART.vertices)), (3, 0))
        self.assertEqual(len(obj.IntersectionPoints), 2)
        self.assertFalse(FakeConsole.errors)

    def test_both_empty_spacings_deduplicate_coincident_degenerate_vertices(self):
        obj = self.create(x_spacings=[], y_spacings=[])
        self.assertEqual((obj.XAxisCount, obj.YAxisCount, obj.IntersectionCount), (1, 1, 1))
        self.assertEqual((len(PART.lines), len(PART.vertices)), (2, 0))
        self.assertEqual([item[0] for item in obj.Shape[1]], ["edge", "edge"])
        self.assertEqual((obj.IntersectionPoints[0].as_tuple(), obj.IntersectionKeys), ((0, 0, 0), ["1/A"]))
        self.assertFalse(FakeConsole.errors)

    def test_zero_extension_degenerate_grid_uses_no_artificial_vertex(self):
        obj = self.create(x_spacings=[], y_spacings=[], x_start_extension=0, x_end_extension=0,
                          y_start_extension=0, y_end_extension=0)
        self.assertEqual(obj.Shape, ("compound", ()))
        self.assertEqual((obj.IntersectionCount, len(obj.IntersectionPoints)), (1, 1))

    def test_automatic_and_valid_custom_identifiers(self):
        automatic = self.create(x_spacings=[1], y_spacings=[1])
        self.assertEqual((automatic.XAxisLabels, automatic.YAxisLabels), (["1", "2"], ["A", "B"]))
        custom = self.create(x_spacings=[1], y_spacings=[], x_identification="Custom", y_identification="Custom", x_labels=["E1", "E2"], y_labels=["N1"])
        self.assertEqual(custom.IntersectionKeys, ["E1/N1", "E2/N1"])

    def test_invalid_input_preserves_last_shape_and_is_reported(self):
        obj = self.create()
        valid_shape = obj.Shape
        obj.XSpacings = [0]
        obj.Proxy.execute(obj)
        self.assertIs(obj.Shape, valid_shape)
        self.assertIn("greater than zero", FakeConsole.errors[-1])

    def test_result_assignment_failure_preserves_shape_and_later_recovers(self):
        obj = self.create()
        valid_shape = obj.Shape
        obj.XSpacings = [100]
        obj.fail_assignments.add("IntersectionPoints")
        obj.Proxy.execute(obj)
        self.assertIs(obj.Shape, valid_shape)
        self.assertIn("deliberate assignment failure", FakeConsole.errors[-1])
        obj.fail_assignments.clear()
        obj.Proxy.execute(obj)
        self.assertIsNot(obj.Shape, valid_shape)
        self.assertEqual(obj.OverallLengthX.Value, 100)

    def test_execute_contains_all_errors(self):
        obj = self.create()
        object.__setattr__(obj, "XSpacings", object())
        obj.Proxy.execute(obj)
        self.assertTrue(FakeConsole.errors)

    def test_on_changed_updates_each_geometry_input_and_recursion_guard(self):
        obj = self.create()
        changes = {
            "XSpacings": [2], "YSpacings": [3], "XStartExtension": 1,
            "XEndExtension": 2, "YStartExtension": 3, "YEndExtension": 4,
            "XAxisIdentification": "Alphabetic", "YAxisIdentification": "Numeric",
        }
        previous = obj.Shape
        for name, value in changes.items():
            setattr(obj, name, value)
            obj.Proxy.onChanged(obj, name)
            self.assertIsNot(obj.Shape, previous)
            previous = obj.Shape
        count = len(PART.compounds)
        obj.Proxy._updating = True
        obj.Proxy.onChanged(obj, "XSpacings")
        self.assertEqual(len(PART.compounds), count)

    def test_on_changed_custom_labels_and_return_to_automatic_schemes(self):
        obj = self.create(x_spacings=[1], y_spacings=[1])
        obj.XAxisIdentification = "Custom"
        obj.XAxisLabels = ["X1", "X2"]
        obj.Proxy.onChanged(obj, "XAxisLabels")
        self.assertEqual(obj.IntersectionKeys[:2], ["X1/A", "X1/B"])
        obj.YAxisIdentification = "Custom"
        obj.YAxisLabels = ["Y1", "Y2"]
        obj.Proxy.onChanged(obj, "YAxisLabels")
        self.assertEqual(obj.IntersectionKeys, ["X1/Y1", "X1/Y2", "X2/Y1", "X2/Y2"])
        obj.XAxisIdentification = "Numeric"
        obj.Proxy.onChanged(obj, "XAxisIdentification")
        obj.YAxisIdentification = "Alphabetic"
        obj.Proxy.onChanged(obj, "YAxisIdentification")
        self.assertEqual((obj.XAxisLabels, obj.YAxisLabels), (["1", "2"], ["A", "B"]))

    def test_label_synchronization_is_bidirectional(self):
        obj = self.create()
        obj.DisplayName = "Grid principal"
        obj.Proxy.onChanged(obj, "DisplayName")
        self.assertEqual(obj.Label, "Grid principal")
        obj.Label = "Grid secundário"
        obj.Proxy.onChanged(obj, "Label")
        self.assertEqual(obj.DisplayName, "Grid secundário")

    def test_factory_parameters_recompute_without_transaction(self):
        obj = self.create(x_spacings=[2, 4], y_spacings=[3], display_name="G1")
        self.assertEqual((obj.XSpacings, obj.YSpacings), ([2.0, 4.0], [3.0]))
        self.assertEqual((obj.Label, obj.DisplayName, self.document.recompute_count), ("G1", "G1", 1))
        self.assertFalse(hasattr(self.document, "openTransaction"))

    def test_factory_recomputes_and_builds_exactly_once(self):
        original = grid.build_grid_geometry
        calls = []
        grid.build_grid_geometry = lambda *args: (calls.append(args), original(*args))[1]
        try:
            self.create()
        finally:
            grid.build_grid_geometry = original
        self.assertEqual((len(calls), self.document.recompute_count, len(PART.compounds)), (1, 1, 1))

    def test_factory_falls_back_to_execute_without_callable_recompute(self):
        class DocumentWithoutRecompute(FakeDocument):
            recompute = None

        document = DocumentWithoutRecompute()
        obj = grid.create_grid(document, x_spacings=[], y_spacings=[])
        self.assertEqual(len(PART.compounds), 1)
        self.assertEqual(obj.IntersectionCount, 1)

    def test_factory_rejects_invalid_document(self):
        for document in (None, object()):
            with self.subTest(document=document), self.assertRaises(ValueError):
                grid.create_grid(document)

    def test_factory_removes_partial_object_when_proxy_installation_fails(self):
        original = grid.StructuralGridProxy
        grid.StructuralGridProxy = lambda _obj: (_ for _ in ()).throw(RuntimeError("proxy failed"))
        try:
            with self.assertRaisesRegex(RuntimeError, "proxy failed"):
                self.create()
        finally:
            grid.StructuralGridProxy = original
        self.assertEqual(self.document.removed, ["StructuralGrid"])
        self.assertEqual(self.document.objects, [])

    def test_factory_removes_partial_object_when_initial_recompute_fails(self):
        self.document.recompute = lambda: (_ for _ in ()).throw(RuntimeError("recompute failed"))
        with self.assertRaisesRegex(RuntimeError, "recompute failed"):
            self.create()
        self.assertEqual(self.document.removed, ["StructuralGrid"])
        self.assertEqual(self.document.objects, [])

    def test_placement_is_native_and_never_recreated_or_applied(self):
        obj = self.create()
        placement = obj.Placement
        obj.Proxy.execute(obj)
        self.assertIs(obj.Placement, placement)
        self.assertNotIn("Placement", obj.PropertiesList)

    def test_only_allowed_runtime_dependencies_are_imported(self):
        tree = ast.parse(GRID_PATH.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        self.assertFalse(imports.intersection({"FreeCADGui", "PySide", "PySide2", "PySide6", "Draft", "pivy", "Coin3D"}))

    def test_execute_uses_mathematical_contract(self):
        obj = self.create()
        original = grid.build_grid_geometry
        calls = []
        grid.build_grid_geometry = lambda *args: (calls.append(args), original(*args))[1]
        try:
            obj.Proxy.execute(obj)
        finally:
            grid.build_grid_geometry = original
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], [6000.0, 6000.0])


if __name__ == "__main__":
    unittest.main()
