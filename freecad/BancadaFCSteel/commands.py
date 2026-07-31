# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI commands for Metal Structure."""

from __future__ import annotations

import traceback

import FreeCAD as App
from FreeCAD import Gui
from PySide import QtGui, QtWidgets

from . import profile_catalog
from .interactive.member_controller import (
    ControllerState,
    MemberController,
    compact_profile_designation,
    next_default_label as _next_default_label,
)
from .interactive.member_task_panel import MemberTaskPanel
from .member import ELEMENT_TYPES, INSERTION_OPTIONS, create_member
from .paths import MEMBER_ICON


_active_member_panel = None
_active_member_tool = None


class DraftInterfaceUnavailable(RuntimeError):
    """The installed Draft infrastructure cannot provide the native tool."""


def _get_active_task_dialog():
    """Return a real active task dialog, normalizing False and API failures."""
    try:
        dialog = Gui.Control.activeDialog()
    except Exception:
        return None
    if dialog is None or dialog is False:
        return None
    return dialog


def _member_session_is_active():
    tool = _active_member_tool
    if tool is not None:
        checker = getattr(tool, "is_active", None)
        if callable(checker) and checker() and getattr(App, "activeDraftCommand", None) is tool:
            return True
    panel = _active_member_panel
    if panel is None:
        return False
    controller = getattr(panel, "controller", None)
    return (
        controller is not None
        and getattr(controller, "state", ControllerState.INACTIVE)
        is not ControllerState.INACTIVE
    )


def _discard_stale_member_session():
    global _active_member_panel, _active_member_tool

    tool = _active_member_tool
    if tool is not None:
        checker = getattr(tool, "is_active", None)
        if not callable(checker) or not checker() or getattr(App, "activeDraftCommand", None) is not tool:
            _active_member_tool = None

    panel = _active_member_panel
    if panel is None or _member_session_is_active():
        return
    try:
        panel.shutdown()
    except Exception:
        pass
    finally:
        if _active_member_panel is panel:
            _active_member_panel = None


def _load_native_draft_tool():
    """Load Draft structurally; runtime activation errors are not fallback cases."""
    try:
        import DraftTools  # noqa: F401 - official Draft GUI initialization
        import DraftGui  # noqa: F401 - owns the process-wide DraftToolBar
        from .interactive.draft_member_tool import (
            StructuralMemberDraftTool,
            draft_native_available,
        )
    except (ImportError, AttributeError) as exc:
        raise DraftInterfaceUnavailable(str(exc)) from exc
    try:
        available = StructuralMemberDraftTool is not None and draft_native_available()
    except Exception as exc:
        raise DraftInterfaceUnavailable(str(exc)) from exc
    if not available:
        raise DraftInterfaceUnavailable("Draft UI unavailable")
    return StructuralMemberDraftTool


def _start_native_member_tool(tool_class, document):
    """Start one fresh native session with Draft's process-wide toolbar."""
    global _active_member_tool
    if getattr(App, "activeDraftCommand", None) is not None:
        raise RuntimeError("A Draft command is already active")
    import DraftTools  # noqa: F401 - official Draft initialization
    import DraftGui  # noqa: F401 - creates draftToolBar only when absent
    if not hasattr(Gui, "draftToolBar"):
        raise DraftInterfaceUnavailable("DraftToolBar was not initialized by Draft")
    Gui.Control.clearTaskWatcher()
    tool = tool_class(
        on_closed=_member_draft_tool_closed,
    )
    _active_member_tool = tool
    try:
        tool.Activated(icon=MEMBER_ICON, task_title="Criar elemento estrutural")
    except Exception:
        try:
            tool.abort_activation(skip_native_ui_cleanup=True)
        finally:
            if _active_member_tool is tool:
                _active_member_tool = None
        raise
    return tool


class MemberDialog(QtWidgets.QDialog):
    def __init__(self, document, start=None, end=None, parent=None):
        super().__init__(parent)
        self.document = document
        self.setWindowTitle("Metal Structure — Criar elemento estrutural")
        self.setMinimumWidth(470)
        self._color = QtGui.QColor(184, 184, 194)
        self._name_custom = False
        self._build_ui()
        self._set_vector(self.start_boxes, start or App.Vector(0.0, 0.0, 0.0))
        self._set_vector(self.end_boxes, end or App.Vector(0.0, 0.0, 3000.0))
        self._refresh_default_name()
        self._update_validity()

    def _spin(self, value=0.0):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-10000000.0, 10000000.0)
        spin.setDecimals(3)
        spin.setSingleStep(100.0)
        spin.setSuffix(" mm")
        spin.setValue(value)
        return spin

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

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
        self.rotation.setToolTip("Rotação da seção em torno do eixo longitudinal do membro.")

        self.color_button = QtWidgets.QPushButton("Escolher cor")
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()

        form.addRow("Nome:", self.name_edit)
        form.addRow("Tipo do elemento:", self.element_type)
        form.addRow("Categoria do perfil:", self.category)
        form.addRow("Série do perfil:", self.series)
        form.addRow("Perfil:", self.profile)
        form.addRow("Inserção:", self.insertion)
        form.addRow("Rotação da seção:", self.rotation)
        form.addRow("Cor:", self.color_button)
        main_layout.addLayout(form)

        self._category_changed(self.category.currentText())

        self.start_boxes = self._point_group(main_layout, "Ponto inicial")
        self.end_boxes = self._point_group(main_layout, "Ponto final")

        hint = QtWidgets.QLabel(
            "Dica: selecione dois vértices antes de abrir este comando para preencher os pontos automaticamente."
        )
        hint.setWordWrap(True)
        main_layout.addWidget(hint)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)

    def _mark_name_custom(self, _text):
        self._name_custom = True

    def _category_changed(self, _text):
        current = self.series.currentText()
        self.series.blockSignals(True)
        self.series.clear()
        self.series.addItems(profile_catalog.series_for_category(self.category.currentText()))
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
            self.category.currentText(), self.series.currentText()
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
            self.name_edit.setText("")
            return
        self.name_edit.setText(
            _next_default_label(self.document, self.element_type.currentText(), designation)
        )

    def _update_validity(self):
        if not hasattr(self, "buttons"):
            return
        ok_button = self.buttons.button(QtWidgets.QDialogButtonBox.Ok)
        ok_button.setEnabled(bool(self.profile_designation))

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

    def _choose_color(self):
        selected = QtWidgets.QColorDialog.getColor(self._color, self, "Cor do elemento")
        if selected.isValid():
            self._color = selected
            self._update_color_button()

    def _update_color_button(self):
        self.color_button.setStyleSheet(
            "QPushButton { background-color: %s; }" % self._color.name()
        )

    @property
    def start_point(self):
        return App.Vector(*(box.value() for box in self.start_boxes))

    @property
    def end_point(self):
        return App.Vector(*(box.value() for box in self.end_boxes))

    @property
    def display_name(self):
        value = self.name_edit.text().strip()
        if value:
            return value
        return _next_default_label(
            self.document, self.element_type.currentText(), self.profile_designation
        )

    @property
    def profile_designation(self):
        designation = self.profile.currentData()
        return str(designation).strip() if designation is not None else ""

    @property
    def rgb(self):
        return (
            self._color.redF(),
            self._color.greenF(),
            self._color.blueF(),
        )


class CreateMemberCommand:
    def GetResources(self):
        return {
            "Pixmap": MEMBER_ICON,
            "MenuText": "Criar elemento estrutural",
            "ToolTip": "Cria um elemento estrutural paramétrico entre dois pontos.",
            "Accel": "S, M",
        }

    def IsActive(self):
        return True

    def Activated(self):
        global _active_member_panel, _active_member_tool

        _discard_stale_member_session()

        if _member_session_is_active():
            App.Console.PrintWarning(
                "Metal Structure: A ferramenta Criar elemento estrutural já está ativa.\n"
            )
            return

        active_dialog = _get_active_task_dialog()
        if active_dialog is not None:
            message = (
                "Já existe um painel de tarefas ativo. "
                "Feche-o antes de criar outro elemento estrutural."
            )
            App.Console.PrintWarning(f"Metal Structure: {message}\n")
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(),
                "Metal Structure",
                message,
            )
            return

        document = App.ActiveDocument
        if document is None:
            document = App.newDocument("MetalStructure")

        selected_points = _selected_vertex_points()
        start = selected_points[0] if len(selected_points) >= 1 else App.Vector(0.0, 0.0, 0.0)
        end = selected_points[1] if len(selected_points) >= 2 else App.Vector(0.0, 0.0, 3000.0)

        try:
            tool_class = _load_native_draft_tool()
        except DraftInterfaceUnavailable as exc:
            App.Console.PrintWarning(
                f"Metal Structure: interface Draft indisponível: {exc}\n"
            )
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(),
                "Metal Structure",
                "Interface Draft indisponível. Utilizando entrada numérica.",
            )
            if _open_numeric_task_panel(document, start, end):
                return
            _run_numeric_fallback(document, start, end)
            return

        tool = None
        try:
            tool = _start_native_member_tool(tool_class, document)
        except Exception:
            failed_tool = tool or _active_member_tool
            App.Console.PrintError(
                "Metal Structure: falha inesperada ao ativar a ferramenta nativa:\n"
                + traceback.format_exc()
            )
            try:
                if failed_tool is not None:
                    failed_tool.abort_activation(skip_native_ui_cleanup=True)
            except Exception:
                App.Console.PrintError(
                    "Metal Structure: falha adicional ao limpar a ativação parcial:\n"
                    + traceback.format_exc()
                )
            finally:
                if failed_tool is not None and _active_member_tool is failed_tool:
                    _active_member_tool = None
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(),
                "Metal Structure",
                "Não foi possível iniciar a ferramenta nativa. "
                "Consulte a Vista de relatório.",
            )
            return
        return


def _member_panel_closed(panel):
    global _active_member_panel
    if _active_member_panel is panel:
        _active_member_panel = None


def _member_draft_tool_closed(tool):
    global _active_member_tool
    if _active_member_tool is tool:
        _active_member_tool = None


def _open_numeric_task_panel(document, start, end):
    """Open the validated numeric task panel without starting 3D capture."""
    global _active_member_panel
    controller = None
    panel = None
    try:
        controller = MemberController(document)
        panel = MemberTaskPanel(document=document, controller=controller, start=start,
                                end=end, on_closed=_member_panel_closed)
        Gui.Control.showDialog(panel)
        if controller.state is not ControllerState.INACTIVE and not panel._closed:
            _active_member_panel = panel
        return True
    except Exception:
        if panel is not None:
            panel.shutdown()
        elif controller is not None:
            controller.stop()
        _active_member_panel = None
        return False


def close_member_task_panel():
    """Close only the active task panel owned by Metal Structure."""
    global _active_member_panel, _active_member_tool

    tool = _active_member_tool
    if tool is not None:
        try:
            tool.finish(cont=False)
        finally:
            _active_member_tool = None
        return True

    panel = _active_member_panel
    if panel is None:
        return False
    try:
        panel.request_close()
    finally:
        if not getattr(panel, "_closed", False):
            panel.shutdown()
        if _active_member_panel is panel:
            _active_member_panel = None
    return True


def _run_numeric_fallback(document, start, end):
    parent = Gui.getMainWindow()
    dialog = MemberDialog(document=document, start=start, end=end, parent=parent)
    if dialog.exec() != QtWidgets.QDialog.Accepted:
        return
    if dialog.start_point.sub(dialog.end_point).Length <= 1e-7:
        QtWidgets.QMessageBox.warning(
            parent, "Metal Structure", "Os pontos inicial e final devem ser diferentes."
        )
        return
    if not dialog.profile_designation:
        QtWidgets.QMessageBox.warning(
            parent,
            "Metal Structure",
            "A categoria selecionada ainda não possui perfis cadastrados.",
        )
        return

    document.openTransaction("Criar elemento estrutural")
    try:
        member = create_member(
            document=document,
            start=dialog.start_point,
            end=dialog.end_point,
            designation=dialog.profile_designation,
            element_type=dialog.element_type.currentText(),
            insertion=dialog.insertion.currentText(),
            rotation=dialog.rotation.value(),
            color=dialog.rgb,
            display_name=dialog.display_name,
        )
        document.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(member)
        Gui.activeDocument().activeView().fitAll()
    except Exception as exc:
        document.abortTransaction()
        App.Console.PrintError(f"Metal Structure: erro ao criar membro: {exc}\n")
        QtWidgets.QMessageBox.critical(
            parent, "Metal Structure", f"Não foi possível criar o membro:\n{exc}"
        )


def _selected_vertex_points():
    points = []
    for selection in Gui.Selection.getSelectionEx():
        for subobject in selection.SubObjects:
            if hasattr(subobject, "Point"):
                points.append(App.Vector(subobject.Point))
                if len(points) == 2:
                    return points
    return points


Gui.addCommand("BFC_CreateMember", CreateMemberCommand())
