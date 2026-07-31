# SPDX-License-Identifier: LGPL-2.1-or-later
import FreeCAD as App
from FreeCAD import Gui
from PySide import QtCore
from PySide.QtCore import QT_TRANSLATE_NOOP

from .paths import WORKBENCH_ICON


def _metal_structure_is_active():
    try:
        workbench = Gui.activeWorkbench()
    except Exception:
        return False
    if getattr(workbench, "MenuText", None) == "Metal Structure":
        return True
    name = getattr(workbench, "name", None)
    try:
        return callable(name) and name() == "MetalStructureWorkbench"
    except Exception:
        return False


def _activate_native_draft_interface():
    """Activate Draft's existing GUI services without recreating its toolbar."""
    try:
        import DraftTools  # noqa: F401
        draft_toolbar = getattr(Gui, "draftToolBar", None)
        if draft_toolbar is not None and hasattr(draft_toolbar, "Activated"):
            draft_toolbar.Activated()
        Gui.Control.clearTaskWatcher()
        snapper = getattr(Gui, "Snapper", None)
        if snapper is not None and hasattr(snapper, "show"):
            snapper.show()
    except Exception:
        return False
    return True


def ensure_draft_snap_toolbar_visible():
    """Restore Snapper visibility after a native tool finishes."""
    if not _metal_structure_is_active():
        return False
    if getattr(App, "activeDraftCommand", None) is not None:
        return False
    snapper = getattr(Gui, "Snapper", None)
    if snapper is None or not hasattr(snapper, "show"):
        return False
    snapper.show()
    return True


def schedule_draft_snap_toolbar_visible():
    QtCore.QTimer.singleShot(0, ensure_draft_snap_toolbar_visible)


class MetalStructureWorkbench(Gui.Workbench):
    """Workbench registration and GUI composition."""

    MenuText = "Metal Structure"
    ToolTip = "Modelagem paramétrica de estruturas metálicas"
    Icon = WORKBENCH_ICON

    def Initialize(self):
        from . import commands  # noqa: F401 - registers FreeCAD commands
        import DraftTools  # noqa: F401 - registers official Draft commands
        from draftutils import init_tools

        member_commands = ["BFC_CreateMember"]
        self.snapbar = init_tools.get_draft_snap_commands()
        self.appendToolbar("Metal Structure - Elementos", member_commands)
        self.appendToolbar(QT_TRANSLATE_NOOP("Workbench", "Draft Snap"), self.snapbar)
        self.appendMenu("Metal Structure", member_commands)

    def Activated(self):
        _activate_native_draft_interface()

    def Deactivated(self):
        from . import commands

        commands.close_member_tool()
        draft_toolbar = getattr(Gui, "draftToolBar", None)
        if draft_toolbar is not None and hasattr(draft_toolbar, "Deactivated"):
            draft_toolbar.Deactivated()
        Gui.Control.clearTaskWatcher()
        snapper = getattr(Gui, "Snapper", None)
        if snapper is not None and hasattr(snapper, "hide"):
            snapper.hide()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MetalStructureWorkbench())
