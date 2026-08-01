# SPDX-License-Identifier: LGPL-2.1-or-later
"""Task panel for the first local Structural Grid visual prototype."""

from __future__ import annotations

from PySide import QtCore, QtGui, QtWidgets

from ..grid_geometry import build_grid_geometry


SCHEMES = {
    "Numérica": "Numeric",
    "Alfabética": "Alphabetic",
    "Personalizada": "Custom",
}


def standard_buttons_value(button_box):
    """Return FreeCAD's integer mask for legacy and PySide6 enum APIs."""
    standard = getattr(button_box, "StandardButton", button_box)
    buttons = standard.Ok | standard.Cancel
    return int(getattr(buttons, "value", buttons))


class _EscapeEventFilter(QtCore.QObject):
    """QObject bridge that routes Escape to a safe panel callback."""

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback
        self._triggered = False

    def eventFilter(self, watched, event):
        event_types = {
            getattr(QtCore.QEvent, "KeyPress", None),
            getattr(QtCore.QEvent, "ShortcutOverride", None),
        }
        qt_key = getattr(QtCore.Qt, "Key", QtCore.Qt)
        escape = getattr(qt_key, "Key_Escape", getattr(QtCore.Qt, "Key_Escape", None))
        if event.type() in event_types and event.key() == escape:
            accept = getattr(event, "accept", None)
            if callable(accept):
                accept()
            callback = self._callback
            if callback is not None and not self._triggered:
                self._triggered = True
                callback()
            return True
        return super().eventFilter(watched, event)

    def clear(self):
        self._callback = None


def parse_custom_identifiers(text, count):
    """Parse comma-separated labels; mathematical validation remains centralized."""
    values = [value.strip() for value in str(text).split(",")]
    if str(text).strip() == "":
        values = []
    # This call is deliberately the single source of count/empty/duplicate validation.
    build_grid_geometry([], [1.0] * max(count - 1, 0), y_identifier_scheme="custom", y_identifiers=values)
    return values


class SpacingEditor(QtWidgets.QGroupBox):
    """Independent editable list of positive spacings for one axis family."""

    def __init__(self, title, defaults, on_change, parent=None):
        super().__init__(title, parent)
        self._on_change = on_change
        layout = QtWidgets.QVBoxLayout(self)
        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(self.list)
        buttons = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QPushButton("Adicionar")
        self.duplicate_button = QtWidgets.QPushButton("Duplicar")
        self.remove_button = QtWidgets.QPushButton("Remover")
        for button in (self.add_button, self.duplicate_button, self.remove_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.summary = QtWidgets.QLabel()
        layout.addWidget(self.summary)
        self.add_button.clicked.connect(self.add_spacing)
        self.duplicate_button.clicked.connect(self.duplicate_spacing)
        self.remove_button.clicked.connect(self.remove_spacing)
        for value in defaults:
            self._append(value)
        self._update_summary()

    def _append(self, value):
        item = QtWidgets.QListWidgetItem()
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 1.0e9)
        spin.setDecimals(2)
        spin.setSuffix(" mm")
        spin.setValue(float(value))
        spin.valueChanged.connect(self._changed)
        item.setSizeHint(spin.sizeHint())
        self.list.addItem(item)
        self.list.setItemWidget(item, spin)
        self.list.setCurrentItem(item)

    def set_values(self, values):
        self.list.clear()
        for value in values:
            self._append(value)
        self._changed()

    def values(self):
        return [self.list.itemWidget(self.list.item(i)).value() for i in range(self.list.count())]

    def _changed(self, _value=None):
        self._update_summary()
        self._on_change()

    def _update_summary(self):
        values = self.values()
        self.summary.setText(f"{len(values) + 1} eixos • total: {sum(values):g} mm")

    def add_spacing(self):
        values = self.values()
        self._append(values[-1] if values else 1000.0)
        self._changed()

    def duplicate_spacing(self):
        row = self.list.currentRow()
        values = self.values()
        self._append(values[row] if 0 <= row < len(values) else (values[-1] if values else 1000.0))
        self._changed()

    def remove_spacing(self):
        row = self.list.currentRow()
        if row < 0 and self.list.count():
            row = self.list.count() - 1
        if row >= 0:
            self.list.takeItem(row)
            self._changed()


class GridTaskPanel:
    """Own one preview object until the FreeCAD task dialog accepts or rejects it."""

    def __init__(self, document, grid_object, on_closed=None):
        self.document = document
        self.grid_object = grid_object
        self._on_closed = on_closed
        self._closed = False
        self._initializing = True
        self._last_error = None
        self._escape_filter = None
        self._escape_filter_target = None
        self.form = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(self.form)

        general = QtWidgets.QGroupBox("Geral")
        general_form = QtWidgets.QFormLayout(general)
        self.name_edit = QtWidgets.QLineEdit("Grid Estrutural")
        self.reset_button = QtWidgets.QPushButton("Redefinir padrões")
        general_form.addRow("Nome do grid:", self.name_edit)
        general_form.addRow(self.reset_button)
        root.addWidget(general)

        self.x_editor = SpacingEditor("Vãos em X", [6000, 6000], self.update_preview)
        self.y_editor = SpacingEditor("Vãos em Y", [5000, 5000], self.update_preview)
        root.addWidget(self.x_editor)
        root.addWidget(self.y_editor)

        extensions = QtWidgets.QGroupBox("Extensões")
        extension_form = QtWidgets.QFormLayout(extensions)
        self.extensions = {}
        for key, label in (("XStartExtension", "Início em X:"), ("XEndExtension", "Fim em X:"),
                           ("YStartExtension", "Início em Y:"), ("YEndExtension", "Fim em Y:")):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.0, 1.0e9)
            spin.setDecimals(2)
            spin.setSuffix(" mm")
            spin.setValue(1000.0)
            self.extensions[key] = spin
            extension_form.addRow(label, spin)
        root.addWidget(extensions)

        identification = QtWidgets.QGroupBox("Identificação")
        identification_form = QtWidgets.QFormLayout(identification)
        self.x_scheme, self.y_scheme = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        for combo in (self.x_scheme, self.y_scheme):
            combo.addItems(list(SCHEMES))
        self.x_scheme.setCurrentText("Numérica")
        self.y_scheme.setCurrentText("Alfabética")
        self.x_labels, self.y_labels = QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
        self.x_labels.setPlaceholderText("Ex.: 1, 2, 3")
        self.y_labels.setPlaceholderText("Ex.: A, B, C")
        self.x_labels.textChanged.connect(self.update_preview)
        self.y_labels.textChanged.connect(self.update_preview)
        identification_form.addRow("Eixos X:", self.x_scheme)
        identification_form.addRow("Identificadores X:", self.x_labels)
        identification_form.addRow("Eixos Y:", self.y_scheme)
        identification_form.addRow("Identificadores Y:", self.y_labels)
        root.addWidget(identification)

        appearance = QtWidgets.QGroupBox("Aparência")
        appearance_form = QtWidgets.QFormLayout(appearance)
        self.line_color = QtGui.QColor(80, 150, 230)
        current_view = getattr(grid_object, "ViewObject", None)
        point_rgb = tuple(getattr(current_view, "IntersectionPointColor", (245 / 255, 190 / 255, 60 / 255)))[:3]
        try:
            self.point_color = QtGui.QColor.fromRgbF(*(float(component) for component in point_rgb))
        except Exception:
            self.point_color = QtGui.QColor(245, 190, 60)
        self.line_color_button = QtWidgets.QPushButton("Escolher cor")
        self.point_color_button = QtWidgets.QPushButton("Escolher cor")
        self.line_width = QtWidgets.QDoubleSpinBox()
        self.line_width.setRange(1.0, 20.0)
        self.line_width.setValue(1.0)
        self.show_points = QtWidgets.QCheckBox()
        self.show_points.setChecked(bool(getattr(current_view, "ShowIntersections", True)))
        self.point_size = QtWidgets.QDoubleSpinBox()
        self.point_size.setRange(1.0, 30.0)
        self.point_size.setValue(float(getattr(current_view, "IntersectionPointSize", 5.0)))
        self.line_color_button.clicked.connect(lambda: self._choose_color("line"))
        self.point_color_button.clicked.connect(lambda: self._choose_color("point"))
        self.show_labels = QtWidgets.QCheckBox()
        self.show_labels.setChecked(True)
        self.label_position = QtWidgets.QComboBox()
        self.label_position.addItems(["Start", "End", "Both"])
        self.label_position.setCurrentText("Both")
        self.font_size = QtWidgets.QDoubleSpinBox()
        self.font_size.setRange(1.0, 200.0)
        self.font_size.setValue(14.0)
        self.text_color = QtGui.QColor(242, 242, 242)
        self.text_color_button = QtWidgets.QPushButton("Escolher cor")
        self.text_color_button.clicked.connect(lambda: self._choose_color("text"))
        appearance_form.addRow("Cor das linhas:", self.line_color_button)
        appearance_form.addRow("Espessura das linhas:", self.line_width)
        appearance_form.addRow("Exibir pontos:", self.show_points)
        appearance_form.addRow("Cor dos pontos:", self.point_color_button)
        appearance_form.addRow("Tamanho dos pontos:", self.point_size)
        appearance_form.addRow("Exibir identificadores:", self.show_labels)
        appearance_form.addRow("Posição:", self.label_position)
        appearance_form.addRow("Tamanho do texto:", self.font_size)
        appearance_form.addRow("Cor do texto:", self.text_color_button)
        root.addWidget(appearance)

        self.validation_message = QtWidgets.QLabel()
        self.validation_message.setWordWrap(True)
        root.addWidget(self.validation_message)
        root.addStretch(1)
        # Connect only after every identification and appearance widget exists.
        for combo in (self.x_scheme, self.y_scheme): combo.currentTextChanged.connect(self._identification_changed)
        for spin in self.extensions.values(): spin.valueChanged.connect(self.update_preview)
        for widget in (self.line_width, self.point_size, self.font_size): widget.valueChanged.connect(self.update_preview)
        for widget in (self.show_points, self.show_labels): widget.toggled.connect(self.update_preview)
        self.label_position.currentTextChanged.connect(self.update_preview)
        self.name_edit.textChanged.connect(self.update_preview)
        self.reset_button.clicked.connect(self.reset_defaults)
        try:
            self._install_escape_filter()
            self._initializing = False
            self._identification_changed()
            self._refresh_color_buttons()
            self.update_preview()
        except Exception:
            self._remove_escape_filter()
            raise

    def _choose_color(self, target):
        current = {"line": self.line_color, "point": self.point_color, "text": self.text_color}[target]
        selected = QtWidgets.QColorDialog.getColor(current, self.form, "Escolher cor")
        if selected.isValid():
            if target == "line":
                self.line_color = selected
            elif target == "point":
                self.point_color = selected
            else:
                self.text_color = selected
            self._refresh_color_buttons()
            self.update_preview()

    def _refresh_color_buttons(self):
        self.line_color_button.setStyleSheet("background-color: %s" % self.line_color.name())
        self.point_color_button.setStyleSheet("background-color: %s" % self.point_color.name())
        self.text_color_button.setStyleSheet("background-color: %s" % self.text_color.name())

    def _identification_changed(self, _value=None):
        self.x_labels.setVisible(SCHEMES[self.x_scheme.currentText()] == "Custom")
        self.y_labels.setVisible(SCHEMES[self.y_scheme.currentText()] == "Custom")
        if not self._initializing:
            self.update_preview()

    def _labels(self, combo, edit, count):
        if SCHEMES[combo.currentText()] != "Custom":
            return None
        return parse_custom_identifiers(edit.text(), count)

    def _values(self):
        x_values, y_values = self.x_editor.values(), self.y_editor.values()
        x_scheme, y_scheme = SCHEMES[self.x_scheme.currentText()], SCHEMES[self.y_scheme.currentText()]
        x_labels = self._labels(self.x_scheme, self.x_labels, len(x_values) + 1)
        y_labels = self._labels(self.y_scheme, self.y_labels, len(y_values) + 1)
        extension_values = {name: spin.value() for name, spin in self.extensions.items()}
        # Validate the exact proposed state before mutating the preview object.
        build_grid_geometry(x_values, y_values, x_identifier_scheme=x_scheme.lower(),
                            y_identifier_scheme=y_scheme.lower(), x_identifiers=x_labels,
                            y_identifiers=y_labels, **{
                                "x_start_extension": extension_values["XStartExtension"],
                                "x_end_extension": extension_values["XEndExtension"],
                                "y_start_extension": extension_values["YStartExtension"],
                                "y_end_extension": extension_values["YEndExtension"],
                            })
        return x_values, y_values, x_scheme, y_scheme, x_labels, y_labels, extension_values

    def update_preview(self, _value=None):
        try:
            x, y, xs, ys, xl, yl, extensions = self._values()
        except Exception as exc:
            self._last_error = str(exc)
            self.validation_message.setText("Entrada inválida: " + str(exc))
            self.validation_message.setStyleSheet("color: #c33")
            self._set_accept_enabled(False)
            return False
        obj = self.grid_object
        obj.Proxy._updating = True
        try:
            obj.DisplayName = self.name_edit.text().strip() or "Grid Estrutural"
            obj.Label = obj.DisplayName
            obj.XSpacings, obj.YSpacings = x, y
            obj.XAxisIdentification, obj.YAxisIdentification = xs, ys
            obj.XAxisLabels, obj.YAxisLabels = xl or [], yl or []
            for name, value in extensions.items():
                setattr(obj, name, value)
        finally:
            obj.Proxy._updating = False
        self.document.recompute()
        view = getattr(obj, "ViewObject", None)
        if view is not None:
            view.LineColor = self.line_color.redF(), self.line_color.greenF(), self.line_color.blueF()
            view.LineWidth = self.line_width.value()
            view.IntersectionPointColor = self.point_color.redF(), self.point_color.greenF(), self.point_color.blueF()
            view.IntersectionPointSize = self.point_size.value()
            view.ShowIntersections = self.show_points.isChecked()
            view.ShowLabels = self.show_labels.isChecked()
            view.LabelPosition = self.label_position.currentText()
            view.FontSize = self.font_size.value()
            view.TextColor = self.text_color.redF(), self.text_color.greenF(), self.text_color.blueF()
            try:
                view.DrawStyle = "Dashdot"
            except Exception:
                pass
        self._last_error = None
        self.validation_message.setText("")
        self._set_accept_enabled(True)
        return True

    def _set_accept_enabled(self, enabled):
        """Best-effort access to FreeCAD's standard OK button after dialog creation."""
        try:
            window = self.form.window()
            button_box = window.findChild(QtWidgets.QDialogButtonBox)
            if button_box is not None:
                button = button_box.button(QtWidgets.QDialogButtonBox.Ok)
                if button is not None:
                    button.setEnabled(bool(enabled))
        except Exception:
            pass

    def isValid(self):
        return self._last_error is None

    def accept(self):
        if not self.update_preview():
            return False
        try:
            self.document.commitTransaction()
            return True
        finally:
            self._finish(True)

    def reject(self):
        if self._closed:
            return True
        try:
            name = getattr(self.grid_object, "Name", None)
            if name is not None and callable(getattr(self.document, "removeObject", None)):
                self.document.removeObject(name)
            self.document.abortTransaction()
            if callable(getattr(self.document, "recompute", None)):
                self.document.recompute()
            return True
        finally:
            self._finish(False)

    def _install_escape_filter(self):
        application = QtWidgets.QApplication.instance()
        if application is None:
            raise RuntimeError("QApplication não está disponível para capturar Esc.")
        event_filter = _EscapeEventFilter(self.reject, application)
        try:
            application.installEventFilter(event_filter)
        except Exception:
            event_filter.clear()
            event_filter.deleteLater()
            raise
        self._escape_filter = event_filter
        self._escape_filter_target = application

    def _remove_escape_filter(self):
        event_filter = self._escape_filter
        if event_filter is None:
            return
        target = self._escape_filter_target
        if target is not None:
            try:
                target.removeEventFilter(event_filter)
            except Exception:
                pass
        event_filter.clear()
        try:
            event_filter.deleteLater()
        except Exception:
            pass
        self._escape_filter_target = None
        self._escape_filter = None

    def _finish(self, accepted):
        if self._closed:
            return
        self._closed = True
        self._remove_escape_filter()
        callback, self._on_closed = self._on_closed, None
        self.grid_object = None
        if callback:
            callback(self, accepted)

    def reset_defaults(self):
        self.name_edit.setText("Grid Estrutural")
        self.x_editor.set_values([6000.0, 6000.0])
        self.y_editor.set_values([5000.0, 5000.0])
        self.x_scheme.setCurrentText("Numérica")
        self.y_scheme.setCurrentText("Alfabética")
        for spin in self.extensions.values(): spin.setValue(1000.0)
        self.line_width.setValue(1.0)
        self.show_points.setChecked(True)
        self.point_size.setValue(5.0)
        self.show_labels.setChecked(True)
        self.label_position.setCurrentText("Both")
        self.font_size.setValue(14.0)
        self.update_preview()

    def getStandardButtons(self):
        return standard_buttons_value(QtWidgets.QDialogButtonBox)


__all__ = ["GridTaskPanel", "SpacingEditor", "parse_custom_identifiers", "standard_buttons_value"]
