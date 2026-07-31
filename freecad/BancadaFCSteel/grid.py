# SPDX-License-Identifier: LGPL-2.1-or-later
"""Minimal parametric FreeCAD object for a structural grid."""

from __future__ import annotations

import FreeCAD as App
import Part

from .grid_geometry import build_grid_geometry


IDENTIFICATION_OPTIONS = ("Numeric", "Alphabetic", "Custom")
_GEOMETRY_PROPERTIES = {
    "XSpacings",
    "YSpacings",
    "XStartExtension",
    "XEndExtension",
    "YStartExtension",
    "YEndExtension",
    "XAxisIdentification",
    "YAxisIdentification",
    "XAxisLabels",
    "YAxisLabels",
}
_READ_ONLY_PROPERTIES = (
    "GridType",
    "SchemaVersion",
    "OverallLengthX",
    "OverallLengthY",
    "DisplayedLengthX",
    "DisplayedLengthY",
    "XAxisCount",
    "YAxisCount",
    "IntersectionCount",
    "IntersectionPoints",
    "IntersectionKeys",
)


def _add_property(obj, property_type: str, name: str, group: str, description: str) -> bool:
    """Add one property if absent and report whether it was created."""
    if name in obj.PropertiesList:
        return False
    obj.addProperty(property_type, name, group, description)
    return True


def _millimetres(value) -> float:
    return float(getattr(value, "Value", value))


def _length_list(values) -> list[float]:
    return [_millimetres(value) for value in values]


def _set_enumeration(obj, name: str, selected: str) -> None:
    setattr(obj, name, list(IDENTIFICATION_OPTIONS))
    setattr(obj, name, selected)


def _console_error(message: str) -> None:
    try:
        App.Console.PrintError(f"Metal Structure: erro ao atualizar Grid Estrutural: {message}\n")
    except Exception:
        pass


def _build_compound(result):
    """Build valid local topology, replacing zero-length axes with vertices."""
    edges = []
    vertex_points = []
    seen_vertices = set()
    for axis in result.x_axes + result.y_axes:
        if axis.start != axis.end:
            edges.append(Part.makeLine(App.Vector(*axis.start), App.Vector(*axis.end)))
        elif axis.start not in seen_vertices:
            seen_vertices.add(axis.start)
            vertex_points.append(axis.start)
    vertices = [Part.Vertex(App.Vector(*point)) for point in vertex_points]
    return Part.makeCompound(edges + vertices)


class StructuralGridProxy:
    """FreeCAD adapter around the pure structural-grid geometry contract."""

    def __init__(self, obj):
        self._updating = True
        obj.Proxy = self
        try:
            self._setup_properties(obj)
        finally:
            self._updating = False

    def _setup_properties(self, obj) -> None:
        created = {}
        created["GridType"] = _add_property(obj, "App::PropertyString", "GridType", "Identity", "Tipo estável do objeto.")
        created["SchemaVersion"] = _add_property(obj, "App::PropertyInteger", "SchemaVersion", "Identity", "Versão do esquema de propriedades.")
        created["DisplayName"] = _add_property(obj, "App::PropertyString", "DisplayName", "Identity", "Nome exibido na árvore do documento.")

        for name in ("XSpacings", "YSpacings"):
            created[name] = _add_property(obj, "App::PropertyLengthList", name, "Grid", "Espaçamentos consecutivos entre eixos.")
        for name in ("XStartExtension", "XEndExtension", "YStartExtension", "YEndExtension"):
            created[name] = _add_property(obj, "App::PropertyLength", name, "Grid", "Extensão da linha de eixo.")

        for name in ("XAxisIdentification", "YAxisIdentification"):
            created[name] = _add_property(obj, "App::PropertyEnumeration", name, "Identification", "Esquema de identificação dos eixos.")
        for name in ("XAxisLabels", "YAxisLabels"):
            created[name] = _add_property(obj, "App::PropertyStringList", name, "Identification", "Identificadores dos eixos.")

        result_types = {
            "OverallLengthX": "App::PropertyLength",
            "OverallLengthY": "App::PropertyLength",
            "DisplayedLengthX": "App::PropertyLength",
            "DisplayedLengthY": "App::PropertyLength",
            "XAxisCount": "App::PropertyInteger",
            "YAxisCount": "App::PropertyInteger",
            "IntersectionCount": "App::PropertyInteger",
            "IntersectionPoints": "App::PropertyVectorList",
            "IntersectionKeys": "App::PropertyStringList",
        }
        for name, property_type in result_types.items():
            created[name] = _add_property(obj, property_type, name, "Results", "Resultado calculado do grid.")

        if created["GridType"]:
            obj.GridType = "StructuralGrid"
        if created["SchemaVersion"]:
            obj.SchemaVersion = 1
        if created["DisplayName"]:
            obj.DisplayName = obj.Label
        if created["XSpacings"]:
            obj.XSpacings = [6000.0, 6000.0]
        if created["YSpacings"]:
            obj.YSpacings = [5000.0, 5000.0]
        for name in ("XStartExtension", "XEndExtension", "YStartExtension", "YEndExtension"):
            if created[name]:
                setattr(obj, name, 0.0)
        if created["XAxisIdentification"]:
            _set_enumeration(obj, "XAxisIdentification", "Numeric")
        if created["YAxisIdentification"]:
            _set_enumeration(obj, "YAxisIdentification", "Alphabetic")
        if created["XAxisLabels"]:
            obj.XAxisLabels = []
        if created["YAxisLabels"]:
            obj.YAxisLabels = []

        for name in _READ_ONLY_PROPERTIES:
            obj.setEditorMode(name, 1)

    def execute(self, obj) -> None:
        if getattr(self, "_updating", False):
            return
        self._updating = True
        try:
            x_scheme = str(obj.XAxisIdentification).lower()
            y_scheme = str(obj.YAxisIdentification).lower()
            result = build_grid_geometry(
                _length_list(obj.XSpacings),
                _length_list(obj.YSpacings),
                _millimetres(obj.XStartExtension),
                _millimetres(obj.XEndExtension),
                _millimetres(obj.YStartExtension),
                _millimetres(obj.YEndExtension),
                x_scheme,
                y_scheme,
                list(obj.XAxisLabels) if x_scheme == "custom" else None,
                list(obj.YAxisLabels) if y_scheme == "custom" else None,
            )
            shape = _build_compound(result)
            x_labels = [axis.identifier for axis in result.x_axes]
            y_labels = [axis.identifier for axis in result.y_axes]
            points = [App.Vector(*item.point) for item in result.intersections]
            keys = [f"{x_labels[item.x_index]}/{y_labels[item.y_index]}" for item in result.intersections]
            overall_length_x = result.overall_length_x
            overall_length_y = result.overall_length_y
            displayed_length_x = result.displayed_length_x
            displayed_length_y = result.displayed_length_y
            x_axis_count = len(result.x_axes)
            y_axis_count = len(result.y_axes)
            intersection_count = len(result.intersections)

            obj.OverallLengthX = overall_length_x
            obj.OverallLengthY = overall_length_y
            obj.DisplayedLengthX = displayed_length_x
            obj.DisplayedLengthY = displayed_length_y
            obj.XAxisCount = x_axis_count
            obj.YAxisCount = y_axis_count
            obj.IntersectionCount = intersection_count
            obj.IntersectionPoints = points
            obj.IntersectionKeys = keys
            if x_scheme != "custom":
                obj.XAxisLabels = x_labels
            if y_scheme != "custom":
                obj.YAxisLabels = y_labels
            obj.Shape = shape
        except Exception as exc:
            _console_error(str(exc))
        finally:
            self._updating = False

    def onChanged(self, obj, prop: str) -> None:
        if getattr(self, "_updating", False):
            return
        self._updating = True
        try:
            if prop == "DisplayName" and "DisplayName" in obj.PropertiesList:
                value = str(obj.DisplayName)
                if obj.Label != value:
                    obj.Label = value
            elif prop == "Label" and "DisplayName" in obj.PropertiesList:
                value = str(obj.Label)
                if obj.DisplayName != value:
                    obj.DisplayName = value
            elif prop in _GEOMETRY_PROPERTIES:
                self._updating = False
                self.execute(obj)
        except Exception as exc:
            _console_error(str(exc))
        finally:
            self._updating = False


def create_grid(
    document,
    x_spacings=None,
    y_spacings=None,
    x_start_extension=0.0,
    x_end_extension=0.0,
    y_start_extension=0.0,
    y_end_extension=0.0,
    x_identification="Numeric",
    y_identification="Alphabetic",
    x_labels=None,
    y_labels=None,
    display_name=None,
):
    """Create and recompute one ``Part::FeaturePython`` structural grid."""
    if document is None or not callable(getattr(document, "addObject", None)):
        raise ValueError("A valid FreeCAD document is required.")
    obj = document.addObject("Part::FeaturePython", "StructuralGrid")
    proxy = StructuralGridProxy(obj)
    proxy._updating = True
    try:
        if x_spacings is not None:
            obj.XSpacings = list(x_spacings)
        if y_spacings is not None:
            obj.YSpacings = list(y_spacings)
        obj.XStartExtension = x_start_extension
        obj.XEndExtension = x_end_extension
        obj.YStartExtension = y_start_extension
        obj.YEndExtension = y_end_extension
        _set_enumeration(obj, "XAxisIdentification", x_identification)
        _set_enumeration(obj, "YAxisIdentification", y_identification)
        if x_labels is not None:
            obj.XAxisLabels = list(x_labels)
        if y_labels is not None:
            obj.YAxisLabels = list(y_labels)
        if display_name is not None:
            obj.DisplayName = str(display_name)
            obj.Label = str(display_name)
    finally:
        proxy._updating = False
    recompute = getattr(document, "recompute", None)
    if callable(recompute):
        recompute()
    else:
        proxy.execute(obj)
    return obj


__all__ = ["StructuralGridProxy", "create_grid"]
