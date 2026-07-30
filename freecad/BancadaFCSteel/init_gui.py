# SPDX-License-Identifier: LGPL-2.1-or-later
from FreeCAD import Gui

from .paths import WORKBENCH_ICON


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

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MetalStructureWorkbench())
