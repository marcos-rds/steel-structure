# SPDX-License-Identifier: LGPL-2.1-or-later
"""Structural member acquisition based directly on FreeCAD Draft Line."""

import FreeCAD as App
from FreeCAD import Gui
from PySide import QtCore

from draftguitools import gui_base_original, gui_lines
from draftutils import gui_utils, todo
from draftutils.messages import _toolmsg

from .member_controller import MemberController
from .profile_options_widget import ProfileOptionsWidget


class StructuralMemberDraftTool(gui_lines.Line):
    """Use Draft Line's UI/events/preview and replace only final creation."""

    def __init__(self, on_closed=None):
        super().__init__(mode="line")
        self._on_closed = on_closed
        self.profile_options = None
        self.controller = None
        self._profile_state = None
        self._segment_cancel_scheduled = False

    def Activated(self, name="StructuralMember", icon="Draft_Line", task_title=None):
        # Line.Activated has no `extra` argument. Creator performs the native
        # command setup; lineUi below remains the installed Draft implementation.
        # "Line" is the registered key expected by Draft's ContinueMode table.
        gui_base_original.Creator.Activated(self, "Line")
        self.controller = MemberController(self.doc)
        self.controller.start()
        self.profile_options = ProfileOptionsWidget(self.doc)
        self.profile_options.restore_state(self._profile_state)
        self.ui.lineUi(title=task_title or "Criar elemento estrutural", icon=icon,
                       extra=self.profile_options)
        self.ui.continueMode = True
        self.ui.continueCmd.setChecked(True)
        self.obj = self.doc.addObject("Part::Feature", "MetalStructureDraftPreview")
        gui_utils.format_object(self.obj)
        self.obj.ViewObject.ShowInTree = False
        self.call = self.view.addEventCallback("SoEvent", self.action)
        _toolmsg("Selecione o primeiro ponto")

    def action(self, arg):
        if arg.get("Type") == "SoKeyboardEvent" and arg.get("Key") == "ESCAPE":
            if arg.get("State") != "DOWN":
                return
            if arg.get("AutoRepeat") or arg.get("IsAutoRepeat"):
                return
            if len(self.node) == 1:
                if not self._segment_cancel_scheduled:
                    self._segment_cancel_scheduled = True
                    QtCore.QTimer.singleShot(0, self._cancel_current_segment)
                return
        return super().action(arg)

    def _cancel_current_segment(self):
        """Reset only Draft Line's current segment outside the Coin callback."""
        self._segment_cancel_scheduled = False
        if App.activeDraftCommand is not self or len(self.node) != 1:
            return
        self.node = []
        self.point = None
        self.pos = []
        self.support = None
        self.removeTemporaryObject()
        if hasattr(Gui, "Snapper"):
            Gui.Snapper.off()
            Gui.Snapper.setTrackers()
        self.obj = self.doc.addObject("Part::Feature", "MetalStructureDraftPreview")
        gui_utils.format_object(self.obj)
        self.obj.ViewObject.ShowInTree = False
        self.ui.mouse = True
        self.ui.new_point = None
        self.ui.last_point = None
        self.ui.redraw()
        self.ui.displayPoint(App.Vector(), None)
        self.ui.setFocus()
        _toolmsg("Selecione o primeiro ponto")

    def finish(self, cont=False, closed=False):
        continue_requested = bool(cont or (cont is None and self.ui and self.ui.continueMode))
        points = list(self.node)
        self.end_callbacks(self.call)
        self.call = None
        self.removeTemporaryObject()
        created = False
        if len(points) == 2 and self.profile_options is not None:
            try:
                result = self.controller.create(self.profile_options.creation_options(points[0], points[1]))
            except Exception as exc:
                App.Console.PrintError(f"Metal Structure: erro ao criar elemento: {exc}\n")
            else:
                self.profile_options.creation_succeeded(result.next_default_name)
                created = True
        if self.profile_options is not None:
            self._profile_state = self.profile_options.state()
        gui_base_original.Creator.finish(self)
        from ..init_gui import schedule_draft_snap_toolbar_visible
        schedule_draft_snap_toolbar_visible()
        if self.controller is not None:
            self.controller.stop()
        if created and continue_requested:
            self.Activated(task_title="Criar elemento estrutural")
        elif self._on_closed is not None:
            self._on_closed(self)

    def removeTemporaryObject(self):
        if self.obj:
            try:
                name = self.obj.Name
            except ReferenceError:
                pass
            else:
                todo.ToDo.delay(self.doc.removeObject, name)
        self.obj = None


def draft_native_available():
    return bool(getattr(Gui, "draftToolBar", None))
