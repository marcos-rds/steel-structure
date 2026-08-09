# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click global-Z column acquisition using Draft's native snap pipeline."""

import FreeCAD as App
from FreeCAD import Gui
from PySide import QtGui
from draftguitools import gui_base_original, gui_lines
from draftutils import gui_utils, todo
from draftutils.messages import _toolmsg

from .. import profile_catalog
from ..member import _i_section_face, _insertion_translation
from ..paths import COLUMN_ICON
from .column_task_panel import ColumnTaskPanel, column_top
from .member_controller import MemberController


TOOL_NEW = "NEW"
TOOL_ACTIVE = "ACTIVE"
TOOL_FINISHING = "FINISHING"
TOOL_FINISHED = "FINISHED"


class StructuralColumnDraftTool(gui_lines.Line):
    """Keep Draft's events and snapper, replacing its two-point result."""

    def __init__(self, on_closed=None):
        super().__init__(mode="line")
        self._on_closed = on_closed
        self._closed_notified = False
        self._lifecycle_state = TOOL_NEW
        self._tool_active = False
        self.controller = None
        self.column_panel = None
        self._current_hover_point = None
        self._preview_shape_signature = None
        self._preview_placement_signature = None
        self._preview_color = None

    def is_active(self):
        return self._lifecycle_state == TOOL_ACTIVE and self._tool_active

    def Activated(self, name="StructuralColumn", icon=None, task_title=None):
        if self._lifecycle_state != TOOL_NEW:
            raise RuntimeError("StructuralColumnDraftTool já foi ativada")
        self._lifecycle_state = TOOL_ACTIVE
        gui_base_original.Creator.Activated(self, "Line")
        self._tool_active = True
        self.controller = MemberController(self.doc)
        self.controller.start()
        self.column_panel = ColumnTaskPanel(self.doc, self._preview_options_changed)
        self.ui.lineUi(title="Criar Pilar", icon="Draft_Draft", extra=self.column_panel)
        self.ui.baseWidget.setWindowTitle("Criar Pilar")
        self.ui.baseWidget.setWindowIcon(QtGui.QIcon(icon or COLUMN_ICON))
        self.ui.continueMode = True
        self.ui.continueCmd.setChecked(True)
        self.ui.continueCmd.setText("Continuar criando")
        for name in ("labellength", "lengthValue", "labelangle", "angleValue", "angleLock"):
            widget = getattr(self.ui, name, None)
            if widget is not None:
                widget.setVisible(False)
        self.obj = self.doc.addObject("Part::Feature", "MetalStructureColumnPreview")
        gui_utils.format_object(self.obj)
        self.obj.ViewObject.ShowInTree = False
        self.obj.ViewObject.Transparency = 65
        self._keep_preview_unsnappable()
        self.call = self.view.addEventCallback("SoEvent", self.action)
        _toolmsg("Selecione o ponto da base do pilar")

    def action(self, arg):
        before = len(self.node)
        result = super().action(arg)
        # Draft Line makes its temporary object selectable again on every
        # mouse-button release. Snapper explicitly treats Selectable=False as
        # ineligible, so restore that preview-local invariant after all events.
        self._keep_preview_unsnappable()
        if self.is_active() and arg.get("Type") == "SoLocation2Event":
            # Line.action() has already passed this event through Draft's
            # getPoint/Snapper pipeline and stored the snapped result here.
            self._set_hover_point(self.point)
            return result
        if self.is_active() and before == 0 and len(self.node) == 1:
            self._confirm_base(self.node[0])
        return result

    def _keep_preview_unsnappable(self):
        obj = getattr(self, "obj", None)
        if obj is not None:
            obj.ViewObject.Selectable = False

    def numericInput(self, numx, numy, numz):
        before = len(self.node)
        result = super().numericInput(numx, numy, numz)
        if self.is_active() and before == 0 and len(self.node) == 1:
            self._confirm_base(self.node[0])
        return result

    def drawUpdate(self, point):
        super().drawUpdate(point)
        self._set_hover_point(point)

    @staticmethod
    def _points_equal(first, second, tolerance=1e-7):
        if first is None or second is None:
            return first is second
        return first.sub(second).Length <= tolerance

    def _set_hover_point(self, point):
        if point is None:
            return False
        candidate = App.Vector(point)
        if self._points_equal(candidate, self._current_hover_point):
            return False
        self._current_hover_point = candidate
        self._update_preview()
        return True

    def _preview_options_changed(self, *_args):
        self._update_preview()

    def _update_preview(self):
        if not self.is_active() or self._current_hover_point is None or self.obj is None:
            return
        try:
            options = self.column_panel.profile_options
            profile = profile_catalog.get(options.profile_designation)
            height = self.column_panel.height_value
            insertion = options.insertion.currentText()
            rotation = float(options.rotation.value())
            shape_signature = (options.profile_designation, height, insertion)
            if shape_signature != self._preview_shape_signature:
                face = _i_section_face(profile)
                tx, ty = _insertion_translation(profile, insertion)
                face.translate(App.Vector(tx, ty, 0.0))
                self.obj.Shape = face.extrude(App.Vector(0.0, 0.0, height))
                self._preview_shape_signature = shape_signature

            point = self._current_hover_point
            placement_signature = (point.x, point.y, point.z, rotation)
            if placement_signature != self._preview_placement_signature:
                roll = App.Rotation(App.Vector(0.0, 0.0, 1.0), rotation)
                self.obj.Placement = App.Placement(point, roll)
                self._preview_placement_signature = placement_signature

            color = tuple(options.rgb)
            if color != self._preview_color:
                self.obj.ViewObject.ShapeColor = color
                self._preview_color = color
            self.obj.ViewObject.Visibility = True
        except (KeyError, RuntimeError, ValueError):
            self.obj.ViewObject.Visibility = False

    def _confirm_base(self, base):
        try:
            result = self.controller.create(self.column_panel.creation_options(base))
        except Exception as exc:
            App.Console.PrintError(f"Metal Structure: erro ao criar pilar: {exc}\n")
            self.node = []
            return
        self.column_panel.creation_succeeded(result.next_default_name)
        if self.ui.continueMode:
            self._reset_for_continue()
        else:
            self._terminate_native_session()

    def finish(self, cont=False, closed=False):
        if self._lifecycle_state in (TOOL_FINISHING, TOOL_FINISHED):
            return
        self._terminate_native_session()

    def _reset_for_continue(self):
        self.node = []
        self.point = None
        self.pos = []
        self.support = None
        self.constrain = None
        accept = getattr(self.ui, "acceptPointInput", None)
        if callable(accept):
            accept()
        else:
            self.ui.mouse = True
        self.ui.mask = None
        if hasattr(Gui, "Snapper"):
            Gui.Snapper.mask = None
        self.ui.reset_ui_values()
        self._clear_hover_state()
        _toolmsg("Selecione o ponto da base do pilar")

    def _clear_hover_state(self):
        self._current_hover_point = None
        self._preview_placement_signature = None
        obj = getattr(self, "obj", None)
        if obj is not None:
            obj.ViewObject.Visibility = False

    def _terminate_native_session(self):
        self._lifecycle_state = TOOL_FINISHING
        self._tool_active = False
        self._clear_hover_state()
        try:
            call = getattr(self, "call", None)
            if call is not None:
                self.end_callbacks(call)
                self.call = None
            self.removeTemporaryObject()
            gui_base_original.Creator.finish(self)
            from ..init_gui import schedule_draft_snap_toolbar_visible
            schedule_draft_snap_toolbar_visible()
        finally:
            if self.controller is not None:
                self.controller.stop()
            self._lifecycle_state = TOOL_FINISHED
            self._notify_closed()

    def abort_activation(self, skip_native_ui_cleanup=False):
        if self._lifecycle_state == TOOL_FINISHED:
            self._notify_closed()
            return
        self._lifecycle_state = TOOL_FINISHING
        self._tool_active = False
        self._clear_hover_state()
        try:
            call = getattr(self, "call", None)
            if call is not None:
                self.end_callbacks(call)
                self.call = None
            self.removeTemporaryObject()
            if not skip_native_ui_cleanup and App.activeDraftCommand is self:
                gui_base_original.Creator.finish(self)
            elif App.activeDraftCommand is self:
                App.activeDraftCommand = None
        finally:
            if self.controller is not None:
                self.controller.stop()
            self._lifecycle_state = TOOL_FINISHED
            self._notify_closed()

    def _notify_closed(self):
        if self._closed_notified:
            return
        self._closed_notified = True
        if self._on_closed is not None:
            self._on_closed(self)

    def removeTemporaryObject(self):
        self._current_hover_point = None
        self._preview_shape_signature = None
        self._preview_placement_signature = None
        self._preview_color = None
        obj = getattr(self, "obj", None)
        if obj:
            try:
                name = obj.Name
            except ReferenceError:
                pass
            else:
                todo.ToDo.delay(self.doc.removeObject, name)
        self.obj = None


def draft_native_available():
    return bool(getattr(Gui, "draftToolBar", None))


__all__ = ["StructuralColumnDraftTool", "draft_native_available", "column_top"]
