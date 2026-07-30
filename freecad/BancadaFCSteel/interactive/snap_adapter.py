# SPDX-License-Identifier: LGPL-2.1-or-later
"""Geometric vertex and edge-endpoint snapping for the active 3D view."""

from __future__ import annotations

import math
import re
import traceback
from dataclasses import dataclass

import FreeCAD as App


SNAP_TOLERANCE_PX = 12
_COMPONENT_RE = re.compile(r"^(Vertex|Edge)(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class SnapResult:
    point: object
    snapped: bool
    snap_type: str | None = None
    object_name: str | None = None
    subelement_name: str | None = None
    projected: bool = False


def global_subelement(obj, subelement_name):
    """Return a globally transformed Part subshape, or None if not guaranteed."""
    getter = getattr(obj, "getSubObject", None)
    if getter is None:
        return None
    try:
        return getter(subelement_name)
    except Exception:
        return None


class SnapAdapter:
    """Resolve only explicit vertices and endpoints of picked edges."""

    def __init__(self, tolerance_px=SNAP_TOLERANCE_PX):
        self.tolerance_px = float(tolerance_px)

    def resolve(self, view, screen_position, document=None):
        position = self._position(screen_position)
        if position is None:
            return None
        try:
            candidates = self._candidates(view, position, document)
        except Exception:
            self._report_parser_error()
            candidates = []
        if candidates:
            return min(candidates, key=lambda item: item[:3])[3]
        return self._projected(view, position)

    @staticmethod
    def _position(position):
        try:
            return int(position[0]), int(position[1])
        except (IndexError, TypeError, ValueError):
            return None

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
            kind = match.group(1).lower()
            subshape = global_subelement(obj, component)
            if subshape is None:
                continue
            if kind == "vertex":
                point = getattr(subshape, "Point", None)
                if point is not None:
                    candidate = self._candidate(
                        view, position, point, object_name, component, 0
                    )
                    if candidate is not None:
                        candidates.append(candidate)
            else:
                for index, vertex in enumerate(getattr(subshape, "Vertexes", ())):
                    point = getattr(vertex, "Point", None)
                    if point is None:
                        continue
                    candidate = self._candidate(
                        view,
                        position,
                        point,
                        object_name,
                        f"{component}.Endpoint{index + 1}",
                        1,
                    )
                    if candidate is not None:
                        candidates.append(candidate)
        return candidates

    def _candidate(self, view, cursor, point, object_name, subelement, priority):
        screen = self._screen_point(view, point)
        if screen is None:
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
            projected=False,
        )
        key = (object_name.casefold(), subelement.casefold())
        return distance, priority, key, result

    @staticmethod
    def _screen_point(view, point):
        try:
            value = view.getPointOnScreen(point)
            return float(value[0]), float(value[1])
        except (AttributeError, IndexError, TypeError, ValueError):
            return None

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
        document_name = lowered.get("document")
        if not isinstance(object_name, str) or not isinstance(component, str):
            return None
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
        return SnapResult(
            point=App.Vector(point),
            snapped=False,
            projected=True,
        )

    @staticmethod
    def _report_parser_error():
        try:
            App.Console.PrintError(
                "Metal Structure: erro ao interpretar candidato de snap:\n"
                f"{traceback.format_exc()}\n"
            )
        except Exception:
            pass
