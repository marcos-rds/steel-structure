# SPDX-License-Identifier: LGPL-2.1-or-later
"""PySide task panel for numeric structural member creation."""

from __future__ import annotations

import FreeCAD as App
from FreeCAD import Gui
from PySide import QtCore, QtGui, QtWidgets

from .. import profile_catalog
from ..member import ELEMENT_TYPES, INSERTION_OPTIONS
from .member_controller import (
    ControllerState,
    MemberCreationOptions,
    compact_profile_designation,
    next_default_label,
)
from .point_capture import PointCapture
from .preview_tracker import PreviewTracker


class MemberTaskPanel:
    """Task-panel adapter kept open for repeated numeric creation."""

    def __init__(
        self,
        document,
        controller,
        start=None,
        end=None,
        on_closed=None,
    ):
        self.document = document
        self.controller = controller
        self._on_closed = on_closed
        self._closed = False
        self._close_requested = False
        self._name_custom = False
        self._updating_name_programmatically = False
        self._observing_documents = False
        self._color = QtGui.QColor(184, 184, 194)
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Criar elemento estrutural")
        self._build_ui()
        self._set_vector(self.start_boxes, start or App.Vector(0.0, 0.0, 0.0))
        self._set_vector(self.end_boxes, end or App.Vector(0.0, 0.0, 3000.0))
        self._refresh_default_name()
        self._update_validity()
        self.controller.attach_panel(self)
        self.controller.start()
        try:
            App.addDocumentObserver(self)
            self._observing_documents = True
        except Exception:
            self._observing_documents = False

    def _spin(self, value=0.0):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-10000000.0, 10000000.0)
        spin.setDecimals(3)
        spin.setSingleStep(100.0)
        spin.setSuffix(" mm")
        spin.setValue(value)
        return spin

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self.form)
        form_layout = QtWidgets.QFormLayout()

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Nome apresentado na árvore")
        self.name_edit.textEdited.connect(self._mark_name_custom)

        self.element_type = QtWidgets.QComboBox()
        self.element_type.addItems(ELEMENT_TYPES)
        self.element_type.setCurrentText("Membro")
        self.element_type.currentTextChanged.connect(self._refresh_default_name)

        self.category = QtWidgets.QComboBox()
        self.category.addItems(profile_catalog.categories())
        self.category.currentTextChanged.connect(self._category_changed)

        self.series = QtWidgets.QComboBox()
        self.series.currentTextChanged.connect(self._series_changed)

        self.profile = QtWidgets.QComboBox()
        self.profile.currentTextChanged.connect(self._profile_changed)

        self.insertion = QtWidgets.QComboBox()
        self.insertion.addItems(INSERTION_OPTIONS)

        self.rotation = QtWidgets.QDoubleSpinBox()
        self.rotation.setRange(-3600.0, 3600.0)
        self.rotation.setDecimals(2)
        self.rotation.setSuffix("°")
        self.rotation.setToolTip(
            "Rotação da seção em torno do eixo longitudinal do membro."
        )

        self.color_button = QtWidgets.QPushButton("Escolher cor")
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()

        form_layout.addRow("Nome:", self.name_edit)
        form_layout.addRow("Tipo do elemento:", self.element_type)
        form_layout.addRow("Categoria do perfil:", self.category)
        form_layout.addRow("Série do perfil:", self.series)
        form_layout.addRow("Perfil:", self.profile)
        form_layout.addRow("Inserção:", self.insertion)
        form_layout.addRow("Rotação da seção:", self.rotation)
        form_layout.addRow("Cor:", self.color_button)
        main_layout.addLayout(form_layout)

        self._category_changed(self.category.currentText())
        self.start_boxes = self._point_group(main_layout, "Ponto inicial")
        self.end_boxes = self._point_group(main_layout, "Ponto final")

        self.status_label = QtWidgets.QLabel(
            "Informe os pontos inicial e final e clique em Criar."
        )
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)

        self.capture_state_label = QtWidgets.QLabel(
            "Preparando captura na vista..."
        )
        self.capture_state_label.setWordWrap(True)
        main_layout.addWidget(self.capture_state_label)

        button_layout = QtWidgets.QHBoxLayout()
        self.create_button = QtWidgets.QPushButton("Criar")
        self.close_button = QtWidgets.QPushButton("Fechar")
        self.create_button.clicked.connect(self._create)
        self.close_button.clicked.connect(self.request_close)
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

    def _point_group(self, parent_layout, title):
        group = QtWidgets.QGroupBox(title)
        grid = QtWidgets.QGridLayout(group)
        boxes = [self._spin(), self._spin(), self._spin()]
        for column, (label, box) in enumerate(zip(("X", "Y", "Z"), boxes)):
            grid.addWidget(QtWidgets.QLabel(label), 0, column)
            grid.addWidget(box, 1, column)
        parent_layout.addWidget(group)
        return boxes

    def _set_vector(self, boxes, vector):
        for box, value in zip(boxes, (vector.x, vector.y, vector.z)):
            box.setValue(value)

    def _mark_name_custom(self, _text):
        if not self._updating_name_programmatically:
            self._name_custom = True

    def _set_name_programmatically(self, value):
        self._updating_name_programmatically = True
        previous = self.name_edit.blockSignals(True)
        try:
            self.name_edit.setText(value)
        finally:
            self.name_edit.blockSignals(previous)
            self._updating_name_programmatically = False

    def _category_changed(self, _text):
        current = self.series.currentText()
        self.series.blockSignals(True)
        self.series.clear()
        self.series.addItems(
            profile_catalog.series_for_category(self.category.currentText())
        )
        index = self.series.findText(current)
        if index >= 0:
            self.series.setCurrentIndex(index)
        self.series.blockSignals(False)
        self._series_changed(self.series.currentText())

    def _series_changed(self, _text):
        current = self.profile.currentData()
        self.profile.blockSignals(True)
        self.profile.clear()
        for designation in profile_catalog.designations(
            self.category.currentText(),
            self.series.currentText(),
        ):
            self.profile.addItem(
                compact_profile_designation(designation),
                designation,
            )
        index = self.profile.findData(current)
        if index >= 0:
            self.profile.setCurrentIndex(index)
        self.profile.blockSignals(False)
        self._profile_changed(self.profile.currentText())

    def _profile_changed(self, _text):
        self._refresh_default_name()
        self._update_validity()

    def _refresh_default_name(self, _text=None):
        if self._name_custom or not hasattr(self, "profile"):
            return
        designation = self.profile_designation
        if not designation:
            self._set_name_programmatically("")
            return
        self._set_name_programmatically(
            next_default_label(
                self.document,
                self.element_type.currentText(),
                designation,
            )
        )

    def _update_validity(self):
        if hasattr(self, "create_button"):
            self.create_button.setEnabled(bool(self.profile_designation))

    def _choose_color(self):
        selected = QtWidgets.QColorDialog.getColor(
            self._color,
            self.form,
            "Cor do elemento",
        )
        if selected.isValid():
            self._color = selected
            self._update_color_button()

    def _update_color_button(self):
        self.color_button.setStyleSheet(
            "QPushButton { background-color: %s; }" % self._color.name()
        )

    @property
    def profile_designation(self):
        designation = self.profile.currentData()
        return str(designation).strip() if designation is not None else ""

    @property
    def start_point(self):
        return App.Vector(*(box.value() for box in self.start_boxes))

    @property
    def end_point(self):
        return App.Vector(*(box.value() for box in self.end_boxes))

    @property
    def rgb(self):
        return (
            self._color.redF(),
            self._color.greenF(),
            self._color.blueF(),
        )

    @property
    def display_name(self):
        value = self.name_edit.text().strip()
        if value:
            return value
        return next_default_label(
            self.document,
            self.element_type.currentText(),
            self.profile_designation,
        )

    def creation_options(self, start=None, end=None):
        return MemberCreationOptions(
            start=self.start_point if start is None else start,
            end=self.end_point if end is None else end,
            designation=self.profile_designation,
            element_type=self.element_type.currentText(),
            insertion=self.insertion.currentText(),
            rotation=self.rotation.value(),
            color=self.rgb,
            display_name=self.display_name,
        )

    def _create(self):
        try:
            result = self.controller.create(self.creation_options())
        except Exception as exc:
            self.status_label.setText(str(exc))
            App.Console.PrintError(f"Metal Structure: erro ao criar elemento: {exc}\n")
            return

        self.status_label.setText(f"Elemento criado: {result.member.Label}")
        self._name_custom = False
        self._set_name_programmatically(result.next_default_name)

    def _active_view(self):
        gui_document = Gui.activeDocument()
        if gui_document is None:
            raise RuntimeError("Não existe uma vista 3D ativa.")
        return gui_document.activeView()

    def start_automatic_capture(self):
        if self._closed or self.controller is None:
            return
        try:
            view = self._active_view()
            tracker = PreviewTracker(view)
            capture = PointCapture(
                view,
                self.controller.handle_mouse_move,
                self._handle_interactive_click,
                self.controller.cancel_current_segment,
                self._set_projection_status,
                lambda: self._active_view() is view,
                self.controller.request_close_capture,
                self._capture_error,
                document=self.document,
                lastpoint_provider=lambda: self.controller._interactive_start,
            )
            self.controller.start_capture(
                capture,
                tracker,
                lambda callback: QtCore.QTimer.singleShot(0, callback),
                self.request_close,
            )
        except Exception as exc:
            self.status_label.setText(
                "Captura na vista indisponível. Utilize a entrada numérica."
            )
            self.capture_state_label.setText("Captura na vista: indisponível.")
            App.Console.PrintError(
                f"Metal Structure: erro ao iniciar captura: {exc}\n"
            )

    def _handle_interactive_click(self, point):
        try:
            self.controller.handle_click(point)
        except Exception as exc:
            self.status_label.setText(str(exc))
            App.Console.PrintError(
                f"Metal Structure: erro na captura interativa: {exc}\n"
            )

    def _set_projection_status(self, message):
        self.status_label.setText(message)

    def _capture_error(self, exc):
        try:
            self.controller.request_close_capture()
        finally:
            self.status_label.setText(f"Captura encerrada após erro: {exc}")
            App.Console.PrintError(
                f"Metal Structure: captura encerrada após erro: {exc}\n"
            )

    @staticmethod
    def _point_text(point):
        return f"({point.x:.3f}, {point.y:.3f}, {point.z:.3f}) mm"

    def update_captured_start(self, point):
        self._set_vector(self.start_boxes, point)
        self.status_label.setText(
            f"Primeiro ponto: {self._point_text(point)}. "
            "Mova o mouse e clique no ponto final."
        )

    def update_candidate_start(self, point):
        self._set_vector(self.start_boxes, point)

    def update_candidate_point(self, point):
        self._set_vector(self.end_boxes, point)

    def interactive_creation_succeeded(self, result):
        self.status_label.setText(
            f"Elemento criado: {result.member.Label}. Selecione o próximo ponto inicial."
        )
        self._name_custom = False
        self._set_name_programmatically(result.next_default_name)

    def update_capture_state(self, state):
        if not hasattr(self, "capture_state_label"):
            return
        messages = {
            ControllerState.READY_NUMERIC: "Captura na vista: inativa.",
            ControllerState.WAITING_FIRST_POINT: (
                "Captura ativa: clique no primeiro ponto. Esc encerra a ferramenta."
            ),
            ControllerState.WAITING_SECOND_POINT: (
                "Captura ativa: clique no segundo ponto. Esc cancela este segmento."
            ),
            ControllerState.CREATING: "Criando elemento...",
            ControllerState.STOPPING: "Encerrando captura com segurança...",
        }
        self.capture_state_label.setText(messages.get(state, "Captura na vista: inativa."))

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        if getattr(self, "_observing_documents", False):
            try:
                App.removeDocumentObserver(self)
            except Exception:
                pass
            self._observing_documents = False
        controller = self.controller
        if controller is not None:
            controller.stop()
        self.controller = None
        self.document = None
        callback = self._on_closed
        self._on_closed = None
        if callback is not None:
            callback(self)

    def request_close(self):
        if self._closed or self._close_requested:
            return
        self._close_requested = True
        try:
            Gui.Control.closeDialog()
        except Exception as exc:
            App.Console.PrintError(
                f"Metal Structure: erro ao fechar painel de tarefas: {exc}\n"
            )
        finally:
            if not self._closed:
                self.shutdown()

    def close(self):
        self.request_close()

    def reject(self):
        self.shutdown()
        return True

    def accept(self):
        return self.reject()

    def getStandardButtons(self):
        return 0

    def slotDeletedDocument(self, document):
        if document is self.document:
            self.request_close()
