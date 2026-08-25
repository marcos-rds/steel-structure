# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compact reusable quick-color popup for Steel Structures task panels."""

from __future__ import annotations

from PySide import QtCore, QtGui, QtWidgets

from ..appearance import STEEL_COLOR_PALETTE, matching_palette_index


class QuickColorMenu(QtWidgets.QMenu):
    colorSelected = QtCore.Signal(object)
    moreColorsRequested = QtCore.Signal()

    def __init__(self, parent=None, presets=STEEL_COLOR_PALETTE):
        super().__init__(parent)
        self.presets = tuple(presets)
        self.buttons = []
        panel = QtWidgets.QWidget(self)
        grid = QtWidgets.QGridLayout(panel)
        spacing = max(round(self.fontMetrics().lineSpacing() * 0.22), 3)
        grid.setContentsMargins(spacing * 2, spacing * 2, spacing * 2, spacing * 2)
        grid.setSpacing(spacing)
        extent = max(round(self.fontMetrics().lineSpacing() * 1.8), 24)
        border = self.palette().color(QtGui.QPalette.Mid).name()
        selected = self.palette().color(QtGui.QPalette.Highlight).name()
        for index, preset in enumerate(self.presets):
            button = QtWidgets.QToolButton(panel)
            button.setCheckable(True)
            button.setAutoRaise(False)
            button.setFixedSize(extent, extent)
            button.setToolTip(preset.name)
            button.setAccessibleName(preset.name)
            button.setFocusPolicy(QtCore.Qt.StrongFocus)
            button.setStyleSheet(
                "QToolButton { background-color: %s; border: 1px solid %s; } "
                "QToolButton:checked { border: 3px solid %s; }"
                % (preset.hex, border, selected)
            )
            button.clicked.connect(
                lambda _checked=False, value=preset.rgb: self._select(value)
            )
            grid.addWidget(button, index // 4, index % 4)
            self.buttons.append(button)
        widget_action = QtWidgets.QWidgetAction(self)
        widget_action.setDefaultWidget(panel)
        self.addAction(widget_action)
        self.addSeparator()
        more_action = self.addAction("Mais cores...")
        more_action.setToolTip("Abrir seletor completo de cores")
        more_action.triggered.connect(self.moreColorsRequested.emit)

    def set_current_color(self, color):
        index = matching_palette_index((color.red(), color.green(), color.blue()), self.presets)
        for button_index, button in enumerate(self.buttons):
            button.setChecked(button_index == index)

    def _select(self, rgb):
        self.colorSelected.emit(tuple(rgb))
        self.close()

    def showEvent(self, event):
        super().showEvent(event)
        if self.buttons:
            self.buttons[0].setFocus()


__all__ = ["QuickColorMenu"]
