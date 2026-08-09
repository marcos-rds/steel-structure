"""Numerical rigid-Placement regression tests for structural members."""

from __future__ import annotations

import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMBER = ROOT / "freecad/BancadaFCSteel/member.py"


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        if hasattr(x, "x"): x, y, z = x.x, x.y, x.z
        elif isinstance(x, (tuple, list)): x, y, z = x
        self.x, self.y, self.z = float(x), float(y), float(z)
    @property
    def Length(self): return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
    def add(self, other): return Vector(self.x + other.x, self.y + other.y, self.z + other.z)
    def sub(self, other): return Vector(self.x - other.x, self.y - other.y, self.z - other.z)
    def __mul__(self, value): return Vector(self.x * value, self.y * value, self.z * value)
    def normalize(self):
        length = self.Length; self.x /= length; self.y /= length; self.z /= length


def mat_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def mat_vec(matrix, vector):
    values = (vector.x, vector.y, vector.z)
    return Vector(*(sum(matrix[i][j] * values[j] for j in range(3)) for i in range(3)))


def transpose(matrix): return tuple(tuple(matrix[j][i] for j in range(3)) for i in range(3))


class Rotation:
    def __init__(self, axis=None, value=None, matrix=None):
        if matrix is not None:
            self.matrix = matrix; return
        axis = Vector(axis or Vector(0, 0, 1))
        if isinstance(value, Vector):
            target = Vector(value); target.normalize()
            z = Vector(0, 0, 1)
            cross = Vector(-target.y, target.x, 0)
            dot = target.z
            if cross.Length < 1e-12:
                self.matrix = ((1, 0, 0), (0, 1 if dot > 0 else -1, 0), (0, 0, 1 if dot > 0 else -1))
            else:
                cross.normalize(); self.matrix = self._axis_angle(cross, math.degrees(math.acos(max(-1, min(1, dot)))))
        else:
            self.matrix = self._axis_angle(axis, float(value or 0.0))
    @staticmethod
    def _axis_angle(axis, degrees):
        axis = Vector(axis); axis.normalize(); x, y, z = axis.x, axis.y, axis.z
        angle = math.radians(degrees); c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
        return ((t*x*x+c, t*x*y-s*z, t*x*z+s*y), (t*x*y+s*z, t*y*y+c, t*y*z-s*x),
                (t*x*z-s*y, t*y*z+s*x, t*z*z+c))
    def multiply(self, other): return Rotation(matrix=mat_mul(self.matrix, other.matrix))


class Placement:
    def __init__(self, base=None, rotation=None):
        if isinstance(base, Placement):
            self.Base = Vector(base.Base); self.Rotation = Rotation(matrix=base.Rotation.matrix)
        else:
            self.Base = Vector(base or Vector()); self.Rotation = rotation or Rotation()
    def multiply(self, other):
        return Placement(self.multVec(other.Base), self.Rotation.multiply(other.Rotation))
    def inverse(self):
        inverse_rotation = Rotation(matrix=transpose(self.Rotation.matrix))
        return Placement(mat_vec(inverse_rotation.matrix, self.Base) * -1, inverse_rotation)
    def multVec(self, vector): return mat_vec(self.Rotation.matrix, Vector(vector)).add(self.Base)


class Quantity:
    def __init__(self, value): self.Value = float(value)


class Face:
    def __init__(self, _wire): self.translation = Vector()
    def translate(self, vector): self.translation = Vector(vector)
    def extrude(self, vector): return types.SimpleNamespace(local_vector=Vector(vector), face_translation=self.translation)


PROFILE = types.SimpleNamespace(bf=150.0, d=150.0, tw=6.0, tf=9.0, mass_per_m=13.0,
                                manufacturer="Test", family="W", area_cm2=16.6, source="Test")


def load_member():
    package_name = "_member_placement_package"
    package = types.ModuleType(package_name); package.__path__ = [str(MEMBER.parent)]
    app = types.ModuleType("FreeCAD")
    app.Vector, app.Rotation, app.Placement = Vector, Rotation, Placement
    app.Console = types.SimpleNamespace(PrintWarning=lambda *_args: None)
    part = types.ModuleType("Part"); part.Face = Face; part.Shape = lambda: types.SimpleNamespace(empty=True)
    part.makePolygon = lambda points: points
    catalog = types.ModuleType(f"{package_name}.profile_catalog")
    catalog.Profile = object; catalog.get = lambda _name: PROFILE
    paths = types.ModuleType(f"{package_name}.paths"); paths.OBJECT_ICON = "member.svg"
    injected = {package_name: package, "FreeCAD": app, "Part": part,
                f"{package_name}.profile_catalog": catalog, f"{package_name}.paths": paths}
    old = {name: sys.modules.get(name) for name in injected}; sys.modules.update(injected)
    spec = importlib.util.spec_from_file_location(f"{package_name}.member", MEMBER)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    for name, previous in old.items():
        if previous is None: sys.modules.pop(name, None)
        else: sys.modules[name] = previous
    return module


class MemberObject:
    def __init__(self, start, end):
        self.StartPoint, self.EndPoint = Vector(start), Vector(end)
        self.Length = Quantity(self.EndPoint.sub(self.StartPoint).Length); self.MemberLength = 0.0
        self.StartExtension = Quantity(0); self.EndExtension = Quantity(0)
        self.OffsetX = Quantity(0); self.OffsetY = Quantity(0); self.Rotation = Quantity(0)
        self.Profile = "W 150 x 13,0"; self.Insertion = "Centroide"; self.MassPerMeter = 13.0
        self.ElementType = "Membro"
        self.TotalMass = 0.0; self.Placement = Placement()
        self.PropertiesList = ["ProfileCategory", "DisplayName", "Length"]
        self.ExpressionEngine = []
    def getExpression(self, _name): return None


class MemberPlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.member = load_member()

    def proxy(self):
        proxy = self.member.StructuralMemberProxy.__new__(self.member.StructuralMemberProxy)
        proxy._updating = proxy._syncing_length = proxy._syncing_placement = False
        proxy._placement_from_points_pending = True; proxy._last_placement = None
        proxy._last_section_rotation = 0.0; proxy._last_valid_length = None
        return proxy

    def create(self, start, end):
        obj, proxy = MemberObject(start, end), self.proxy(); proxy.execute(obj); return obj, proxy

    def assertVector(self, actual, expected, places=6):
        for value, wanted in zip((actual.x, actual.y, actual.z), expected): self.assertAlmostEqual(value, wanted, places=places)

    def translate(self, obj, proxy, dx, dy, dz):
        moved = Placement(obj.Placement); moved.Base = moved.Base.add(Vector(dx, dy, dz))
        obj.Placement = moved; proxy.onChanged(obj, "Placement")

    def rotate_world(self, obj, proxy, axis, degrees):
        rigid = Placement(Vector(), Rotation(Vector(*axis), degrees))
        obj.Placement = rigid.multiply(obj.Placement); proxy.onChanged(obj, "Placement")

    def test_horizontal_vertical_and_diagonal_creation(self):
        for start, end in (((0, 0, 0), (10, 0, 0)), ((0, 0, 6), (0, 0, 16)), ((1, 2, 3), (4, 6, 15))):
            with self.subTest(start=start, end=end):
                obj, _proxy = self.create(start, end)
                self.assertAlmostEqual(obj.MemberLength, Vector(end).sub(Vector(start)).Length)
                self.assertVector(obj.Placement.Base, start)

    def test_manual_base_xyz_and_repeated_recompute_persist(self):
        for delta in ((7, 0, 0), (0, 8, 0), (0, 0, -3), (7, 8, -3)):
            with self.subTest(delta=delta):
                obj, proxy = self.create((0, 0, 6), (10, 0, 6)); original_length = obj.MemberLength
                self.translate(obj, proxy, *delta); expected_base = Vector(*delta).add(Vector(0, 0, 6))
                for _ in range(3): proxy.execute(obj); self.assertVector(obj.Placement.Base, (expected_base.x, expected_base.y, expected_base.z))
                self.assertVector(obj.StartPoint, (expected_base.x, expected_base.y, expected_base.z))
                self.assertVector(obj.EndPoint, (expected_base.x + 10, expected_base.y, expected_base.z))
                self.assertAlmostEqual(obj.MemberLength, original_length)

    def test_rotation_and_recompute_rotate_global_axis_without_double_transform(self):
        obj, proxy = self.create((0, 0, 0), (10, 0, 0)); original_shape = obj.Shape
        self.rotate_world(obj, proxy, (0, 0, 1), 90)
        self.assertVector(obj.StartPoint, (0, 0, 0)); self.assertVector(obj.EndPoint, (0, 10, 0))
        for _ in range(2): proxy.execute(obj)
        self.assertVector(obj.EndPoint, (0, 10, 0)); self.assertVector(obj.Placement.multVec(Vector(0, 0, 10)), (0, 10, 0))
        self.assertAlmostEqual(obj.MemberLength, 10); self.assertIsNot(obj.Shape, original_shape)

    def test_translation_rotation_orders_and_profile_change_preserve_transform(self):
        for order in ("translate_rotate", "rotate_translate"):
            obj, proxy = self.create((0, 0, 0), (0, 0, 10))
            if order == "translate_rotate":
                self.translate(obj, proxy, 2, 3, 4); self.rotate_world(obj, proxy, (0, 1, 0), 90)
            else:
                self.rotate_world(obj, proxy, (0, 1, 0), 90); self.translate(obj, proxy, 2, 3, 4)
            placement = Placement(obj.Placement); points = (Vector(obj.StartPoint), Vector(obj.EndPoint))
            obj.Profile = "W 200 x 15,0"; proxy.onChanged(obj, "Profile"); proxy.execute(obj)
            self.assertVector(obj.Placement.Base, (placement.Base.x, placement.Base.y, placement.Base.z))
            self.assertVector(obj.StartPoint, (points[0].x, points[0].y, points[0].z))
            self.assertVector(obj.EndPoint, (points[1].x, points[1].y, points[1].z))
            self.assertEqual(obj.Profile, "W 200 x 15,0")

    def test_section_rotation_changes_roll_without_restoring_moved_base(self):
        obj, proxy = self.create((0, 0, 0), (0, 0, 10)); self.translate(obj, proxy, 3, 4, 5)
        before_points = (Vector(obj.StartPoint), Vector(obj.EndPoint)); obj.Rotation = Quantity(35)
        proxy.onChanged(obj, "Rotation"); proxy.execute(obj)
        self.assertVector(obj.Placement.Base, (3, 4, 5)); self.assertVector(obj.StartPoint, (3, 4, 5))
        self.assertVector(obj.EndPoint, (3, 4, 15)); self.assertAlmostEqual(obj.MemberLength, 10)
        self.assertEqual((before_points[0].Length, before_points[1].sub(before_points[0]).Length), (math.sqrt(50), 10))

    def test_direct_start_and_end_edits_remain_authoritative(self):
        obj, proxy = self.create((0, 0, 0), (10, 0, 0))
        obj.StartPoint = Vector(1, 2, 3); proxy.onChanged(obj, "StartPoint"); proxy.execute(obj)
        self.assertVector(obj.Placement.Base, (1, 2, 3)); self.assertAlmostEqual(obj.MemberLength, math.sqrt(94))
        obj.EndPoint = Vector(1, 2, 13); proxy.onChanged(obj, "EndPoint"); proxy.execute(obj)
        self.assertVector(obj.Placement.Base, (1, 2, 3)); self.assertAlmostEqual(obj.MemberLength, 10)

    def test_restore_and_legacy_proxy_preserve_existing_placement(self):
        obj, proxy = self.create((0, 0, 6), (10, 0, 6)); self.translate(obj, proxy, 1, 2, -3)
        restored = self.proxy(); restored.__setstate__(None); restored._setup_properties = lambda _obj: None
        restored.onDocumentRestored(obj); placement = Placement(obj.Placement); restored.execute(obj)
        self.assertVector(obj.Placement.Base, (placement.Base.x, placement.Base.y, placement.Base.z))
        self.assertVector(obj.StartPoint, (1, 2, 3)); self.assertVector(obj.EndPoint, (11, 2, 3))

    def test_existing_column_type_survives_recompute_and_restore(self):
        obj, proxy = self.create((0, 0, 0), (0, 0, 3000))
        obj.ElementType = "Pilar"
        proxy.execute(obj)
        self.assertEqual(obj.ElementType, "Pilar")
        restored = self.proxy(); restored.__setstate__(None)
        restored._setup_properties = lambda _obj: None
        restored.onDocumentRestored(obj)
        restored.execute(obj)
        self.assertEqual(obj.ElementType, "Pilar")

    def test_guards_release_after_sync_exception_and_block_recursion(self):
        obj, proxy = self.create((0, 0, 0), (10, 0, 0)); self.translate(obj, proxy, 1, 0, 0)
        old = proxy._last_placement; proxy._last_placement = types.SimpleNamespace(inverse=lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        proxy.onChanged(obj, "Placement")
        self.assertFalse(proxy._syncing_placement); self.assertFalse(proxy._syncing_length)
        proxy._last_placement = old; proxy.onChanged(obj, "Placement"); self.assertFalse(proxy._syncing_placement)


if __name__ == "__main__":
    unittest.main()
