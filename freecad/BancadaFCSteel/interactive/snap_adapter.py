# SPDX-License-Identifier: LGPL-2.1-or-later
"""Adapter for FreeCAD Draft snapping, with the validated endpoint fallback."""

from __future__ import annotations

import math
import re
import traceback
from dataclasses import dataclass

import FreeCAD as App


SNAP_TOLERANCE_PX = 12
_COMPONENT_RE = re.compile(r"^(Vertex|Edge)(\d+)$", re.IGNORECASE)
_NATIVE_LABELS = {
    "endpoint": "extremidade",
    "midpoint": "ponto médio",
    "center": "centro",
    "angle": "ângulo",
    "intersection": "interseção",
    "perpendicular": "perpendicular",
    "extension": "extensão",
    "parallel": "paralelo",
    "special": "ponto especial",
    "passive": "próximo",
    "ortho": "ortogonal",
    "grid": "grade",
}


@dataclass(frozen=True)
class SnapResult:
    point: object
    snapped: bool
    snap_type: str | None = None
    object_name: str | None = None
    subelement_name: str | None = None
    projected: bool = False
    native: bool = False
    mechanism: str = "projection"


def global_subelement(obj, subelement_name):
    """Return a globally transformed Part subshape, or None if not guaranteed."""
    getter = getattr(obj, "getSubObject", None)
    if getter is None:
        return None
    try:
        return getter(subelement_name)
    except Exception:
        return None


class BasicEndpointSnapAdapter:
    """Validated V1 resolver, used only if the native Draft Snapper fails."""

    def __init__(self, tolerance_px=SNAP_TOLERANCE_PX):
        self.tolerance_px = float(tolerance_px)

    def resolve(self, view, screen_position, document=None, **_options):
        position = _position(screen_position)
        if position is None:
            return None
        try:
            candidates = self._candidates(view, position, document)
        except Exception:
            _report_error("erro ao interpretar candidato do fallback")
            candidates = []
        if candidates:
            result = min(candidates, key=lambda item: item[:3])[3]
            return SnapResult(
                point=result.point,
                snapped=True,
                snap_type=result.snap_type,
                object_name=result.object_name,
                subelement_name=result.subelement_name,
                projected=False,
                native=False,
                mechanism="endpoint-fallback",
            )
        return self._projected(view, position)

    def _candidates(self, view, position, document):
        candidates = []
        for info in self._object_infos(view, position):
            parsed = self._parse_info(info)
            if parsed is None:
                continue
            document_name, object_name, component = parsed
            if document is None or (
                document_name and document_name != getattr(document, "Name", None)
            ):
                continue
            obj = document.getObject(object_name)
            if obj is None or getattr(obj, "Document", document) is not document:
                continue
            view_object = getattr(obj, "ViewObject", None)
            if view_object is not None and not getattr(view_object, "Visibility", True):
                continue
            if not hasattr(obj, "Shape"):
                continue
            match = _COMPONENT_RE.match(component)
            if match is None:
                continue
            subshape = global_subelement(obj, component)
            if subshape is None:
                continue
            if match.group(1).lower() == "vertex":
                points = ((getattr(subshape, "Point", None), component, 0),)
            else:
                points = tuple(
                    (
                        getattr(vertex, "Point", None),
                        f"{component}.Endpoint{index + 1}",
                        1,
                    )
                    for index, vertex in enumerate(getattr(subshape, "Vertexes", ()))
                )
            for point, subelement, priority in points:
                candidate = self._candidate(
                    view, position, point, object_name, subelement, priority
                )
                if candidate is not None:
                    candidates.append(candidate)
        return candidates

    def _candidate(self, view, cursor, point, object_name, subelement, priority):
        if point is None:
            return None
        try:
            screen = view.getPointOnScreen(point)
            screen = float(screen[0]), float(screen[1])
        except (AttributeError, IndexError, TypeError, ValueError):
            return None
        distance = math.hypot(screen[0] - cursor[0], screen[1] - cursor[1])
        if distance > self.tolerance_px:
            return None
        result = SnapResult(
            point=App.Vector(point),
            snapped=True,
            snap_type="endpoint",
            object_name=object_name,
            subelement_name=subelement,
            mechanism="endpoint-fallback",
        )
        return distance, priority, (object_name.casefold(), subelement.casefold()), result

    @staticmethod
    def _object_infos(view, position):
        getter = getattr(view, "getObjectsInfo", None)
        if getter is not None:
            try:
                infos = getter(position)
                if isinstance(infos, (list, tuple)):
                    return [item for item in infos if isinstance(item, dict)]
            except Exception:
                pass
        getter = getattr(view, "getObjectInfo", None)
        if getter is None:
            return []
        info = getter(position)
        return [info] if isinstance(info, dict) else []

    @staticmethod
    def _parse_info(info):
        lowered = {str(key).casefold(): value for key, value in info.items()}
        object_name = lowered.get("object")
        component = lowered.get("component")
        if not isinstance(object_name, str) or not isinstance(component, str):
            return None
        document_name = lowered.get("document")
        return (
            str(document_name) if document_name is not None else None,
            object_name,
            component,
        )

    @staticmethod
    def _projected(view, position):
        try:
            point = view.getPoint(*position)
        except Exception:
            return None
        if point is None:
            return None
        return SnapResult(point=App.Vector(point), snapped=False, projected=True)


class DraftSnapToolbarManager:
    """Show the existing native toolbar without changing layout or snap modes."""

    OBJECT_NAME = "Draft Snap"
    TITLES = ("Draft Snap", "Encaixe de Draft")

    def __init__(self, gui_module):
        self.gui = gui_module
        self.toolbar = None
        self.was_visible = None
        self.user_changed_visibility = False
        self._changing_visibility = False
        self._signal_connected = False

    def find(self):
        main_window = self.gui.getMainWindow()
        try:
            from PySide import QtWidgets

            toolbar_type = QtWidgets.QToolBar
        except Exception:
            toolbar_type = object
        finder = getattr(main_window, "findChild", None)
        toolbar = finder(toolbar_type, self.OBJECT_NAME) if finder else None
        if toolbar is None:
            children = getattr(main_window, "findChildren", lambda _type: [])(
                toolbar_type
            )
            for candidate in children:
                title = str(candidate.windowTitle())
                if title in self.TITLES:
                    toolbar = candidate
                    break
        self.toolbar = toolbar
        return toolbar

    def show(self):
        toolbar = self.find()
        if toolbar is None:
            return False
        self.was_visible = bool(toolbar.isVisible())
        signal = getattr(toolbar, "visibilityChanged", None)
        if signal is not None and not self._signal_connected:
            try:
                signal.connect(self._visibility_changed)
                self._signal_connected = True
            except Exception:
                pass
        if not self.was_visible:
            self._changing_visibility = True
            try:
                toolbar.show()
            finally:
                self._changing_visibility = False
        return True

    def _visibility_changed(self, _visible):
        if not self._changing_visibility:
            self.user_changed_visibility = True

    def restore(self):
        toolbar = self.toolbar
        if toolbar is None or self.user_changed_visibility:
            return
        visible = bool(toolbar.isVisible())
        if self.was_visible is True and not visible:
            self._changing_visibility = True
            try:
                toolbar.show()
            finally:
                self._changing_visibility = False
        elif self.was_visible is False and visible:
            self._changing_visibility = True
            try:
                toolbar.hide()
            finally:
                self._changing_visibility = False


class SnapAdapter:
    """Use ``Gui.Snapper.snap`` first and the endpoint V1 only as fallback."""

    def __init__(self, gui_module=None, fallback=None):
        if gui_module is None:
            import FreeCADGui as gui_module
        self.gui = gui_module
        self.fallback = fallback or BasicEndpointSnapAdapter()
        self.toolbar = DraftSnapToolbarManager(gui_module)
        self.native_available = False
        self._reported_native_error = False
        self._native_init_attempted = False
        self._started = False

    def start(self):
        if self._started:
            return self.native_available
        self.native_available = self._ensure_native_snapper() is not None
        if self.native_available and not self.toolbar.show():
            _print_warning("barra nativa 'Draft Snap' não encontrada")
        self._started = True
        return self.native_available

    def stop(self):
        if not self._started:
            return
        snapper = getattr(self.gui, "Snapper", None)
        try:
            if self.native_available and snapper is not None:
                self.toolbar._changing_visibility = True
                try:
                    snapper.off()
                finally:
                    self.toolbar._changing_visibility = False
        finally:
            self.toolbar.restore()
            self._started = False

    def _ensure_native_snapper(self):
        snapper = getattr(self.gui, "Snapper", None)
        if snapper is not None:
            return snapper
        if self._native_init_attempted:
            return None
        self._native_init_attempted = True
        try:
            import DraftTools  # noqa: F401 - official Draft GUI initialization
        except Exception:
            self._report_native_error()
            return None
        return getattr(self.gui, "Snapper", None)

    def event_options(self, event):
        try:
            from draftguitools import gui_tool_utils

            return (
                bool(
                    gui_tool_utils.has_mod(
                        event, gui_tool_utils.get_mod_snap_key()
                    )
                ),
                bool(
                    gui_tool_utils.has_mod(
                        event, gui_tool_utils.get_mod_constrain_key()
                    )
                ),
            )
        except Exception:
            return (
                _event_flag(event, "CtrlDown", "ctrlDown", "ControlDown"),
                _event_flag(event, "ShiftDown", "shiftDown"),
            )

    def resolve(
        self,
        view,
        screen_position,
        document=None,
        lastpoint=None,
        active=False,
        constrain=False,
    ):
        position = _position(screen_position)
        if position is None:
            return None
        snapper = self._ensure_native_snapper()
        if snapper is not None:
            self.native_available = True
            try:
                self.toolbar._changing_visibility = True
                try:
                    point = snapper.snap(
                        position,
                        lastpoint=lastpoint,
                        active=bool(active),
                        constrain=bool(constrain),
                        noTracker=True,
                    )
                finally:
                    self.toolbar._changing_visibility = False
                if point is not None:
                    return self._native_result(
                        point, snapper, self._native_snap_active(active)
                    )
            except Exception:
                self._report_native_error()
        return self.fallback.resolve(view, position, document=document)

    @staticmethod
    def _native_result(point, snapper, active=True):
        mode = getattr(snapper, "cursorMode", None)
        mode = str(mode).casefold() if mode else None
        info = getattr(snapper, "snapInfo", None)
        info = info if isinstance(info, dict) else {}
        snapped = mode in _NATIVE_LABELS and (
            mode != "passive" or (bool(info) and active)
        )
        return SnapResult(
            point=App.Vector(point),
            snapped=snapped,
            snap_type=mode if snapped else None,
            object_name=info.get("Object"),
            subelement_name=info.get("Component") or info.get("SubName"),
            projected=not snapped,
            native=True,
            mechanism="draft",
        )

    @staticmethod
    def _native_snap_active(active):
        if active:
            return True
        try:
            from draftutils import params

            return bool(params.get_param("alwaysSnap"))
        except Exception:
            return False

    def status_message(self, result):
        if result.native:
            if result.snapped:
                return f"Snap nativo: {_NATIVE_LABELS.get(result.snap_type, result.snap_type)}"
            return "Ponto no plano de trabalho, sem snap geométrico."
        if result.snapped:
            return (
                "Sistema de snap: fallback de extremidade — "
                f"{result.object_name}/{result.subelement_name}"
            )
        return "Sistema de snap: somente projeção"

    def _report_native_error(self):
        if not self._reported_native_error:
            _report_error("Snapper nativo indisponível; usando fallback")
            self._reported_native_error = True


def _position(position):
    try:
        return int(position[0]), int(position[1])
    except (IndexError, TypeError, ValueError):
        return None


def _event_flag(event, *names):
    for name in names:
        if name in event:
            return bool(event[name])
    return False


def _report_error(context):
    try:
        App.Console.PrintError(
            f"Metal Structure: {context}:\n{traceback.format_exc()}\n"
        )
    except Exception:
        pass


def _print_warning(message):
    try:
        App.Console.PrintWarning(f"Metal Structure: {message}.\n")
    except Exception:
        pass
