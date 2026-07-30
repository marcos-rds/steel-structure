# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lightweight axial preview implemented with a persistent Coin3D tree."""

from __future__ import annotations


class PreviewTracker:
    """Own one temporary line attached to one FreeCAD view."""

    def __init__(self, view, coin_module=None):
        if coin_module is None:
            from pivy import coin as coin_module
        self.view = view
        self._root = coin_module.SoSeparator()
        self._style = coin_module.SoDrawStyle()
        self._style.lineWidth = 2.0
        self._color = coin_module.SoBaseColor()
        self._color.rgb = (1.0, 0.75, 0.0)
        self._coordinates = coin_module.SoCoordinate3()
        self._line = coin_module.SoLineSet()
        self._line.numVertices.setValues(0, 1, [2])
        for node in (self._style, self._color, self._coordinates, self._line):
            self._root.addChild(node)
        self._attached = False
        self._visible = False
        self._detached = False

    @property
    def root(self):
        return self._root

    def attach(self):
        if self._detached:
            raise RuntimeError("Um PreviewTracker destacado não pode ser reutilizado.")
        if not self._attached:
            self.view.getSceneGraph().addChild(self._root)
            self._attached = True

    @staticmethod
    def _xyz(point):
        return float(point.x), float(point.y), float(point.z)

    def update(self, start, end):
        self.attach()
        self._coordinates.point.setValues(
            0, 2, [self._xyz(start), self._xyz(end)]
        )
        self._line.numVertices.setValues(0, 1, [2])
        self._visible = True

    def hide(self):
        if self._attached:
            self._line.numVertices.setValues(0, 1, [0])
        self._visible = False

    def detach(self):
        if not self._attached:
            return
        try:
            graph = self.view.getSceneGraph()
            find_child = getattr(graph, "findChild", None)
            if find_child is None or find_child(self._root) >= 0:
                graph.removeChild(self._root)
        finally:
            self._attached = False
            self._visible = False
            self._detached = True
