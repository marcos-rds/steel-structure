# SPDX-License-Identifier: LGPL-2.1-or-later
from FreeCAD import Gui

from .paths import WORKBENCH_ICON


def _ensure_native_draft_snap_toolbar(workbench):
    """Create Draft's own snap toolbar through Draft's official initializer."""
    try:
        import DraftTools  # noqa: F401 - initializes commands and Gui.Snapper
        from draftutils import init_tools
        from PySide import QtWidgets
        from PySide.QtCore import QT_TRANSLATE_NOOP

        main_window = Gui.getMainWindow()
        if main_window.findChild(QtWidgets.QToolBar, "Draft Snap") is None:
            init_tools.init_toolbar(
                workbench,
                QT_TRANSLATE_NOOP("Workbench", "Draft Snap"),
                init_tools.get_draft_snap_commands(),
            )
    except Exception:
        # Numeric creation remains available even if Draft is not installed.
        return False
    return True


class MetalStructureWorkbench(Gui.Workbench):
    """Workbench registration and GUI composition."""

    MenuText = "Metal Structure"
    ToolTip = "Modelagem paramétrica de estruturas metálicas"
    Icon = WORKBENCH_ICON

    def Initialize(self):
        from . import commands  # noqa: F401 - registers FreeCAD commands

        member_commands = ["BFC_CreateMember"]
        self.appendToolbar("Metal Structure - Elementos", member_commands)
        self.appendMenu("Metal Structure", member_commands)
        _ensure_native_draft_snap_toolbar(self)

    def Activated(self):
        pass

    def Deactivated(self):
        from . import commands

        commands.close_member_task_panel()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MetalStructureWorkbench())
