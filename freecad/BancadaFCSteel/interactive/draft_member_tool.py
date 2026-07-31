# SPDX-License-Identifier: LGPL-2.1-or-later
"""Structural member acquisition based directly on FreeCAD Draft Line."""

import FreeCAD as App
from FreeCAD import Gui
from PySide import QtCore, QtGui
from draftguitools import gui_base_original, gui_lines
from draftutils import gui_utils, todo
from draftutils.messages import _toolmsg

from .member_controller import MemberController
from .profile_options_widget import ProfileOptionsWidget
from ..paths import MEMBER_ICON


TOOL_NEW = "NEW"
TOOL_ACTIVE = "ACTIVE"
TOOL_FINISHING = "FINISHING"
TOOL_FINISHED = "FINISHED"


class StructuralMemberDraftTool(gui_lines.Line):
    """Use Draft Line's UI/events/preview and replace only final creation."""

    def __init__(self, on_closed=None):
        super().__init__(mode="line")
        self._on_closed = on_closed
        self.profile_options = None
        self.controller = None
        self._task_icon = MEMBER_ICON
        self._last_input_stage = None
        self._stage_update_pending = False
        self._stage_generation = 0
        self._tool_active = False
        self._lifecycle_state = TOOL_NEW
        self._closed_notified = False

    def is_active(self):
        """Return whether this exact native Line instance owns the session."""
        return self._lifecycle_state == TOOL_ACTIVE and self._tool_active

    def Activated(self, name="StructuralMember", icon=None, task_title=None):
        if self._lifecycle_state != TOOL_NEW:
            raise RuntimeError(
                f"StructuralMemberDraftTool cannot activate from {self._lifecycle_state}"
            )
        self._lifecycle_state = TOOL_ACTIVE
        # Line.Activated has no `extra` argument. Creator performs the native
        # command setup; lineUi below remains the installed Draft implementation.
        # "Line" is the registered key expected by Draft's ContinueMode table.
        gui_base_original.Creator.Activated(self, "Line")
        self._stage_generation += 1
        self._stage_update_pending = False
        self._tool_active = True
        self.controller = MemberController(self.doc)
        self.controller.start()
        self.profile_options = ProfileOptionsWidget(self.doc)
        self.ui.lineUi(title="Primeiro ponto do elemento estrutural", icon="Draft_Draft",
                       extra=self.profile_options)
        self._task_icon = icon or MEMBER_ICON
        self.ui.baseWidget.setWindowTitle("Primeiro ponto do elemento estrutural")
        self.ui.baseWidget.setWindowIcon(QtGui.QIcon(self._task_icon))
        self._last_input_stage = None
        self._update_point_input_stage()
        self._schedule_stage_update()
        self.ui.continueMode = True
        self.ui.continueCmd.setChecked(self.ui.continueMode)
        self.obj = self.doc.addObject("Part::Feature", "MetalStructureDraftPreview")
        gui_utils.format_object(self.obj)
        self.obj.ViewObject.ShowInTree = False
        self.call = self.view.addEventCallback("SoEvent", self.action)
        _toolmsg("Selecione o primeiro ponto")

    def _apply_point_stage_ui(self):
        """Apply one coherent title/icon/control state to Draft's own widgets."""
        if App.activeDraftCommand is not self or self.ui is None:
            return
        first = len(self.node) == 0
        stage = "first" if first else "next"
        title = "Primeiro ponto do elemento estrutural" if first else "Próximo ponto"

        base = self.ui.baseWidget
        base.setWindowTitle(title)
        base.setWindowIcon(QtGui.QIcon(self._task_icon))

        for name in ("labellength", "lengthValue", "labelangle", "angleValue", "angleLock"):
            widget = getattr(self.ui, name, None)
            if widget is not None:
                widget.setVisible(not first)
        self._last_input_stage = stage

    def _update_point_input_stage(self):
        """Synchronize the native point-entry presentation with Line.node."""
        if App.activeDraftCommand is not self or self.ui is None:
            return
        first = len(self.node) == 0
        stage = "first" if first else "next"
        if stage == self._last_input_stage:
            return
        self._apply_point_stage_ui()

    def _schedule_stage_update(self):
        """Consolidate stage synchronization after Draft finishes its event."""
        if not self._tool_active or self._stage_update_pending:
            return
        self._stage_update_pending = True
        generation = self._stage_generation
        QtCore.QTimer.singleShot(0, lambda: self._run_stage_update(generation))

    def _run_stage_update(self, generation):
        if generation != self._stage_generation:
            return
        self._stage_update_pending = False
        if not self._tool_active or App.activeDraftCommand is not self:
            return
        self._last_input_stage = None
        self._update_point_input_stage()

    def action(self, arg):
        result = super().action(arg)
        self._schedule_stage_update()
        return result

    def numericInput(self, numx, numy, numz):
        result = super().numericInput(numx, numy, numz)
        self._schedule_stage_update()
        return result

    def drawUpdate(self, point):
        super().drawUpdate(point)
        self._schedule_stage_update()

    def finish(self, cont=False, closed=False):
        if self._lifecycle_state in (TOOL_FINISHING, TOOL_FINISHED):
            return
        if self._lifecycle_state != TOOL_ACTIVE:
            raise RuntimeError(
                f"StructuralMemberDraftTool cannot finish from {self._lifecycle_state}"
            )
        continue_requested = bool(cont or (cont is None and self.ui and self.ui.continueMode))
        points = list(self.node)
        created = False
        if len(points) == 2 and self.profile_options is not None:
            try:
                result = self.controller.create(
                    self.profile_options.creation_options(points[0], points[1])
                )
            except Exception as exc:
                App.Console.PrintError(f"Metal Structure: erro ao criar elemento: {exc}\n")
            else:
                self.profile_options.creation_succeeded(result.next_default_name)
                created = True
        if created and continue_requested:
            self._reset_segment_for_continue()
            return
        self._terminate_native_session()

    def _reset_segment_for_continue(self):
        """Acquire another member without closing or rebuilding Draft's UI."""
        self.node = []
        self.point = None
        self.pos = []
        self.support = None
        self.constrain = None

        accept_point_input = getattr(self.ui, "acceptPointInput", None)
        if callable(accept_point_input):
            accept_point_input()
        else:
            # FreeCAD 1.1.3 exposes the input-ready state directly.
            self.ui.mouse = True
        self.ui.mask = None
        self.ui.alock = False
        if hasattr(Gui, "Snapper"):
            Gui.Snapper.mask = None
        angle_lock = getattr(self.ui, "angleLock", None)
        if angle_lock is not None:
            angle_lock.setChecked(False)
        self.ui.reset_ui_values()

        zero_length = App.Units.Quantity(0, App.Units.Length).UserString
        zero_angle = App.Units.Quantity(0, App.Units.Angle).UserString
        for name in ("xValue", "yValue", "zValue", "lengthValue"):
            widget = getattr(self.ui, name, None)
            if widget is not None:
                blocked = widget.blockSignals(True)
                try:
                    if name in ("xValue", "yValue", "zValue"):
                        widget.setEnabled(True)
                    widget.setText(zero_length)
                finally:
                    widget.blockSignals(blocked)
        angle_value = getattr(self.ui, "angleValue", None)
        if angle_value is not None:
            blocked = angle_value.blockSignals(True)
            try:
                angle_value.setText(zero_angle)
            finally:
                angle_value.blockSignals(blocked)

        if self.obj is not None:
            self.obj.ViewObject.Visibility = False
        self._stage_generation += 1
        self._stage_update_pending = False
        self._last_input_stage = None
        self._apply_point_stage_ui()
        _toolmsg("Selecione o primeiro ponto")
        self.update_hints()

    def _terminate_native_session(self):
        """Perform the terminal Draft cleanup exactly once."""
        self._lifecycle_state = TOOL_FINISHING
        self._tool_active = False
        self._stage_generation += 1
        self._stage_update_pending = False
        try:
            self.end_callbacks(self.call)
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
        """Release a partially initialized native session without fallback."""
        if self._lifecycle_state == TOOL_FINISHED:
            self._notify_closed()
            return
        self._lifecycle_state = TOOL_FINISHING
        self._tool_active = False
        self._stage_generation += 1
        self._stage_update_pending = False
        try:
            call = getattr(self, "call", None)
            if call is not None:
                self.end_callbacks(call)
                self.call = None
            self.removeTemporaryObject()
            if (not skip_native_ui_cleanup and App.activeDraftCommand is self
                    and getattr(self, "ui", None) is not None):
                gui_base_original.Creator.finish(self)
            elif App.activeDraftCommand is self:
                App.activeDraftCommand = None
        finally:
            controller = getattr(self, "controller", None)
            if controller is not None:
                controller.stop()
            self._lifecycle_state = TOOL_FINISHED
            self._notify_closed()

    def _notify_closed(self):
        if self._closed_notified:
            return
        self._closed_notified = True
        if self._on_closed is not None:
            self._on_closed(self)

    def removeTemporaryObject(self):
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
