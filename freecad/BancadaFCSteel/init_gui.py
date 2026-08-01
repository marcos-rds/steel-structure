# SPDX-License-Identifier: LGPL-2.1-or-later
import FreeCAD as App
from FreeCAD import Gui
from PySide import QtCore
from PySide.QtCore import QT_TRANSLATE_NOOP

from .paths import WORKBENCH_ICON


GENERAL_TOOLS_NATIVE = ("Draft_Move", "Draft_Rotate", "Draft_Clone")
GENERAL_TOOLS_ORDER = ("Draft_Move", "BFC_MoveCopy", "Draft_Rotate", "Draft_Clone")
_draft_tools_warning_emitted = False


def _report_missing_draft_commands(missing):
    global _draft_tools_warning_emitted
    if _draft_tools_warning_emitted:
        return
    _draft_tools_warning_emitted = True
    App.Console.PrintWarning(
        "Metal Structure: Ferramentas Gerais do Draft indisponíveis: "
        + ", ".join(missing)
        + ".\n"
    )


def load_general_tools(commands_module):
    """Load official Draft commands and return only working command IDs."""
    try:
        import DraftTools  # noqa: F401 - registers official GUI commands
        available = set(Gui.listCommands())
    except (ImportError, AttributeError, RuntimeError, TypeError):
        _report_missing_draft_commands(GENERAL_TOOLS_NATIVE)
        return []

    move_copy = commands_module.register_move_copy_command()
    available = set(Gui.listCommands())
    wanted = GENERAL_TOOLS_ORDER if move_copy else GENERAL_TOOLS_NATIVE
    result = [command for command in wanted if command in available]
    missing = [command for command in GENERAL_TOOLS_NATIVE if command not in available]
    if missing:
        _report_missing_draft_commands(missing)
    return result


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

        member_commands = ["BFC_CreateMember", "BFC_CreateGrid"]
        self.general_tools = load_general_tools(commands)
        try:
            from draftutils import init_tools
            self.snapbar = init_tools.get_draft_snap_commands()
        except (ImportError, AttributeError, RuntimeError, TypeError):
            self.snapbar = []
        self.appendToolbar("Metal Structure - Elementos", member_commands)
        if self.general_tools:
            self.appendToolbar("Ferramentas Gerais", self.general_tools)
        if self.snapbar:
            self.appendToolbar(QT_TRANSLATE_NOOP("Workbench", "Draft Snap"), self.snapbar)
        self.appendMenu("Metal Structure", member_commands)
        if self.general_tools:
            self.appendMenu("Ferramentas Gerais", self.general_tools)

    def Activated(self):
        _activate_native_draft_interface()

    def Deactivated(self):
        from . import commands

        commands.close_member_tool()
        commands.close_grid_panel()
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
