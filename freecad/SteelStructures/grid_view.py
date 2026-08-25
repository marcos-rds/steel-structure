# SPDX-License-Identifier: LGPL-2.1-or-later
"""Localized Coin3D presentation for Structural Grid objects."""

from __future__ import annotations

import math
import numbers

try:
    from pivy import coin
except ImportError:  # Allows headless unit tests and delayed GUI loading.
    coin = None


VIEW_GROUP = "Grid Appearance"
LABEL_POSITIONS = ("Start", "End", "Both")
SAFE_FONT_FALLBACK = "Sans"
_VIEW_DATA_PROPERTIES = frozenset({
    "GridType", "SchemaVersion", "DisplayName", "XSpacings", "YSpacings",
    "XStartExtension", "XEndExtension", "YStartExtension", "YEndExtension",
    "XAxisIdentification", "YAxisIdentification", "XAxisLabels", "YAxisLabels",
    "OverallLengthX", "OverallLengthY", "DisplayedLengthX", "DisplayedLengthY",
    "XAxisCount", "YAxisCount", "IntersectionCount", "IntersectionPoints",
    "IntersectionKeys",
})


def _add_property(view, kind, name, description):
    if name in getattr(view, "PropertiesList", ()):
        return False
    view.addProperty(kind, name, VIEW_GROUP, description)
    return True


def _number(value):
    return float(getattr(value, "Value", value))


def _data_schema_ready(obj):
    try:
        return obj is not None and _VIEW_DATA_PROPERTIES.issubset(set(obj.PropertiesList))
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        return False


def _rgb3(value) -> tuple[float, float, float]:
    """Convert QColor, PropertyColor, RGB or RGBA into normalized Coin RGB."""
    if all(callable(getattr(value, name, None)) for name in ("redF", "greenF", "blueF")):
        components = (value.redF(), value.greenF(), value.blueF())
    else:
        raw = getattr(value, "Value", value)
        try:
            components = tuple(raw)
        except (TypeError, ValueError):
            components = ()
        if len(components) not in (3, 4):
            raise ValueError("color must contain exactly RGB or RGBA components")
        components = components[:3]
    integer_scale = all(isinstance(component, numbers.Integral) and not isinstance(component, bool)
                        for component in components)
    try:
        result = tuple(float(component) for component in components)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("color components must be finite numbers") from exc
    if len(result) != 3 or not all(math.isfinite(component) for component in result):
        raise ValueError("color components must be three finite numbers")
    if any(component < 0.0 for component in result):
        raise ValueError("color components cannot be negative")
    if any(component > 1.0 for component in result):
        if not integer_scale or not all(component <= 255.0 for component in result):
            raise ValueError("color components exceed the supported range")
        result = tuple(component / 255.0 for component in result)
    return result


def _view_warning(message):
    try:
        import FreeCAD as App
        App.Console.PrintWarning("Steel Structures: " + message + "\n")
    except Exception:
        pass


def _font_catalog(font_database=None, application=None):
    """Return unique sorted font families and the current application family."""
    if font_database is None or application is None:
        try:
            from PySide import QtGui, QtWidgets
            font_database = font_database or QtGui.QFontDatabase
            application = application or QtWidgets.QApplication
        except ImportError:
            pass
    try:
        default = str(application.font().family()).strip()
    except Exception:
        default = ""
    try:
        families = [str(item).strip() for item in font_database.families()]
    except Exception:
        families = []
    if default:
        families.append(default)
    unique = {family.casefold(): family for family in families if family}
    options = sorted(unique.values(), key=str.casefold)
    if not options:
        options = [default or SAFE_FONT_FALLBACK]
    selected = default if default in options else options[0]
    return options, selected


def _property_type(view, name):
    getter = getattr(view, "getTypeIdOfProperty", None)
    if callable(getter):
        try:
            return str(getter(name))
        except Exception:
            pass
    record = getattr(view, "records", {}).get(name)
    return str(record[0]) if record else ""


def _setup_font_property(view):
    """Create or migrate FontName and populate it once per attach/restoration."""
    previous = str(getattr(view, "FontName", "") or "")
    property_type = _property_type(view, "FontName")
    if property_type and property_type != "App::PropertyEnumeration":
        remover = getattr(view, "removeProperty", None)
        if callable(remover):
            remover("FontName")
    if "FontName" not in getattr(view, "PropertiesList", ()):
        view.addProperty("App::PropertyEnumeration", "FontName", VIEW_GROUP,
                         "Fonte dos identificadores do grid.")
    options, default = _font_catalog()
    selected = previous if previous in options else default
    view.FontName = options
    view.FontName = selected
    return options, selected


def _bottom_label_offset(label_offset, font_size):
    """Effective bottom offset including provisional SoText2 baseline space."""
    offset = max(0.0, float(label_offset))
    size = max(0.0, float(font_size))
    bottom_extra = max(0.75 * offset, (size / 14.0) * 200.0)
    return offset + bottom_extra


def _label_justification(side):
    return "RIGHT" if side == "left" else "LEFT" if side == "right" else "CENTER"


def _label_position(side, axis_coordinate, boundary, label_offset, font_size):
    offset = max(0.0, float(label_offset))
    if side == "bottom":
        offset = _bottom_label_offset(offset, font_size)
    if side in ("bottom", "left"):
        return ((axis_coordinate, boundary - offset) if side == "bottom"
                else (boundary - offset, axis_coordinate))
    return ((axis_coordinate, boundary + offset) if side == "top"
            else (boundary + offset, axis_coordinate))


def _safe_draw_style(view, value="Dashdot"):
    """Select a supported draw style without making grid creation fail."""
    try:
        view.DrawStyle = value
        return
    except Exception:
        pass
    for fallback in ("Dashdot", "Dashed", "Solid"):
        try:
            view.DrawStyle = fallback
            return
        except Exception:
            continue


class StructuralGridViewProvider:
    """View-only points visibility and non-serialized Coin text labels."""

    def __init__(self, view_object=None):
        self._root = None
        self._labels = None
        self._points = None
        self._visible_point_size = 5.0
        self._changing = False
        if view_object is not None:
            self.attach(view_object)

    def attach(self, view):
        self.ViewObject = view
        view.Proxy = self
        created = {
            "ShowIntersections": _add_property(view, "App::PropertyBool", "ShowIntersections", "Exibir ou ocultar os pontos de interseção do grid"),
            "IntersectionPointColor": _add_property(view, "App::PropertyColor", "IntersectionPointColor", "Cor dos pontos de interseção do grid."),
            "IntersectionPointSize": _add_property(view, "App::PropertyFloat", "IntersectionPointSize", "Tamanho dos pontos de interseção do grid."),
            "ShowLabels": _add_property(view, "App::PropertyBool", "ShowLabels", "Exibe os identificadores dos eixos."),
            "LabelPosition": _add_property(view, "App::PropertyEnumeration", "LabelPosition", "Extremidades que recebem identificadores."),
            "FontSize": _add_property(view, "App::PropertyFloat", "FontSize", "Tamanho dos identificadores."),
            "TextColor": _add_property(view, "App::PropertyColor", "TextColor", "Cor dos identificadores."),
            "LabelOffset": _add_property(view, "App::PropertyLength", "LabelOffset", "Afastamento dos identificadores."),
        }
        if created["IntersectionPointColor"]:
            view.IntersectionPointColor = ((0.96, 0.75, 0.24) if created["ShowIntersections"]
                                           else getattr(view, "PointColor", (0.96, 0.75, 0.24)))
        if created["IntersectionPointSize"]:
            old_size = getattr(view, "PointSize", 5.0)
            view.IntersectionPointSize = 5.0 if created["ShowIntersections"] else float(old_size)
        if created["ShowIntersections"]: view.ShowIntersections = True
        if created["ShowLabels"]: view.ShowLabels = True
        if created["LabelPosition"]:
            view.LabelPosition = list(LABEL_POSITIONS)
            view.LabelPosition = "Both"
        _setup_font_property(view)
        if created["FontSize"]: view.FontSize = 14.0
        if created["TextColor"]: view.TextColor = (0.95, 0.95, 0.95)
        if created["LabelOffset"]: view.LabelOffset = 250.0
        if created["ShowIntersections"]:
            try: view.LineColor = (0.31, 0.59, 0.90)
            except Exception: pass
            try: view.LineWidth = 1.0
            except Exception: pass
            _safe_draw_style(view)
        # Part's native vertex presentation exposes edge endpoints. Grid points
        # are rendered exclusively by our Coin node below.
        try: view.PointSize = 0.0
        except Exception: pass
        set_editor_mode = getattr(view, "setEditorMode", None)
        if callable(set_editor_mode):
            for native_name in ("PointColor", "PointSize"):
                try: set_editor_mode(native_name, 2)
                except Exception: pass
        try:
            self._build_scene()
            self._update_scene()
        except Exception:
            self.detach(view)
            raise

    def detach(self, _view=None):
        view = getattr(self, "ViewObject", None)
        if self._root is not None:
            scene_root = getattr(view, "RootNode", None)
            if scene_root is not None:
                try:
                    scene_root.removeChild(self._root)
                except Exception:
                    pass
        self._root = None
        self._labels = None
        self._points = None
        if view is not None and getattr(view, "Proxy", None) is self:
            try:
                view.Proxy = None
            except Exception:
                pass
        self.ViewObject = None

    def _build_scene(self):
        if coin is None:
            return
        self._root = coin.SoSeparator()
        self._points = coin.SoSeparator()
        self._labels = coin.SoSeparator()
        self._root.addChild(self._points)
        self._root.addChild(self._labels)
        # Add to the existing FeaturePython scene so its normal line rendering
        # remains active; labels are not a replacement display mode.
        scene_root = getattr(self.ViewObject, "RootNode", None)
        if scene_root is not None:
            scene_root.addChild(self._root)

    def _label_specs(self):
        obj = getattr(self.ViewObject, "Object", None)
        if not _data_schema_ready(obj):
            return []
        xs, ys = [0.0], [0.0]
        for value in obj.XSpacings: xs.append(xs[-1] + _number(value))
        for value in obj.YSpacings: ys.append(ys[-1] + _number(value))
        x0, x1 = -_number(obj.XStartExtension), xs[-1] + _number(obj.XEndExtension)
        y0, y1 = -_number(obj.YStartExtension), ys[-1] + _number(obj.YEndExtension)
        offset = _number(self.ViewObject.LabelOffset)
        positions = str(self.ViewObject.LabelPosition)
        font_size = float(self.ViewObject.FontSize)
        specs = []
        for x, label in zip(xs, obj.XAxisLabels):
            if positions in ("Start", "Both"):
                px, py = _label_position("bottom", x, y0, offset, font_size)
                specs.append((px, py, str(label), _label_justification("bottom"), "bottom"))
            if positions in ("End", "Both"):
                px, py = _label_position("top", x, y1, offset, font_size)
                specs.append((px, py, str(label), _label_justification("top"), "top"))
        for y, label in zip(ys, obj.YAxisLabels):
            if positions in ("Start", "Both"):
                px, py = _label_position("left", y, x0, offset, font_size)
                specs.append((px, py, str(label), _label_justification("left"), "left"))
            if positions in ("End", "Both"):
                px, py = _label_position("right", y, x1, offset, font_size)
                specs.append((px, py, str(label), _label_justification("right"), "right"))
        return specs

    def _update_points(self, view):
        if self._points is None:
            return
        self._points.removeAllChildren()
        if not bool(getattr(view, "ShowIntersections", True)):
            return
        obj = getattr(view, "Object", None)
        points = list(getattr(obj, "IntersectionPoints", ())) if _data_schema_ready(obj) else []
        if not points:
            return
        color = coin.SoBaseColor()
        try:
            point_rgb = _rgb3(view.IntersectionPointColor)
        except ValueError as exc:
            point_rgb = (0.96, 0.75, 0.24)
            _view_warning(f"cor dos pontos inválida; usando padrão seguro ({exc}).")
        color.rgb.setValue(*point_rgb)
        style = coin.SoDrawStyle(); style.pointSize = float(view.IntersectionPointSize)
        coordinates = coin.SoCoordinate3()
        coordinates.point.setValues(0, len(points), [(_number(p.x), _number(p.y), _number(p.z)) for p in points])
        point_set = coin.SoPointSet(); point_set.numPoints = len(points)
        for node in (color, style, coordinates, point_set): self._points.addChild(node)

    def _update_scene(self):
        if self._changing:
            return
        view = getattr(self, "ViewObject", None)
        if view is None:
            return
        if not _data_schema_ready(getattr(view, "Object", None)):
            if self._points is not None: self._points.removeAllChildren()
            if self._labels is not None: self._labels.removeAllChildren()
            return
        self._changing = True
        try:
            self._update_points(view)
            if self._labels is None:
                return
            self._labels.removeAllChildren()
            if not bool(getattr(view, "ShowLabels", True)):
                return
            color = coin.SoBaseColor()
            try:
                rgb = _rgb3(view.TextColor)
            except ValueError as exc:
                rgb = (0.95, 0.95, 0.95)
                _view_warning(f"cor de texto inválida; usando padrão seguro ({exc}).")
            color.rgb.setValue(*rgb)
            self._labels.addChild(color)
            for x, y, text, justification, _side in self._label_specs():
                separator = coin.SoSeparator()
                translation = coin.SoTranslation(); translation.translation.setValue(x, y, 0.0)
                font = coin.SoFont(); font.size = float(view.FontSize)
                if str(view.FontName): font.name = str(view.FontName)
                label = coin.SoText2(); label.string = text
                label.justification = getattr(coin.SoText2, justification)
                for node in (translation, font, label): separator.addChild(node)
                self._labels.addChild(separator)
        finally:
            self._changing = False

    def updateData(self, _obj, prop):
        if prop in {"XSpacings", "YSpacings", "XStartExtension", "XEndExtension", "YStartExtension",
                    "YEndExtension", "XAxisLabels", "YAxisLabels", "XAxisIdentification",
                    "YAxisIdentification", "IntersectionPoints", "Placement"}:
            self._update_scene()

    def onChanged(self, view, prop):
        if prop in {"ShowIntersections", "ShowLabels", "LabelPosition", "FontName", "FontSize",
                    "TextColor", "LabelOffset", "IntersectionPointSize", "IntersectionPointColor"}:
            self._update_scene()

    def onDocumentRestored(self, view):
        self.ViewObject = view
        _setup_font_property(view)
        if self._root is None:
            self._build_scene()
        self._update_scene()

    def getIcon(self):
        from .paths import GRID_OBJECT_ICON
        return GRID_OBJECT_ICON

    def __getstate__(self): return None
    def __setstate__(self, _state):
        self._root = self._labels = self._points = None
        self._visible_point_size = 5.0
        self._changing = False


__all__ = ["StructuralGridViewProvider", "LABEL_POSITIONS"]
