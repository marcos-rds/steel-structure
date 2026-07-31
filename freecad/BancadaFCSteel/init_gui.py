# SPDX-License-Identifier: LGPL-2.1-or-later
from FreeCAD import Gui
from PySide import QtCore, QtWidgets

from .paths import WORKBENCH_ICON


_draft_snap_toolbar_initialized = False


def _find_native_draft_snap_toolbar():
    main_window = Gui.getMainWindow()
    toolbar = main_window.findChild(QtWidgets.QToolBar, "Draft Snap")
    if toolbar is not None:
        return toolbar
    for candidate in main_window.findChildren(QtWidgets.QToolBar):
        if candidate.windowTitle() in ("Draft Snap", "Encaixe de Draft"):
            return candidate
    return None


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


def _ensure_native_draft_snap_toolbar(workbench):
    """Create Draft's own snap toolbar through Draft's official initializer."""
    try:
        import DraftTools  # noqa: F401 - initializes commands and Gui.Snapper
        from draftutils import init_tools
        from PySide.QtCore import QT_TRANSLATE_NOOP

        global _draft_snap_toolbar_initialized
        toolbar = _find_native_draft_snap_toolbar()
        if toolbar is None and not _draft_snap_toolbar_initialized:
            init_tools.init_toolbar(
                workbench,
                QT_TRANSLATE_NOOP("Workbench", "Draft Snap"),
                init_tools.get_draft_snap_commands(),
            )
            _draft_snap_toolbar_initialized = True
            toolbar = _find_native_draft_snap_toolbar()
        if toolbar is not None:
            toolbar.setVisible(True)
    except Exception:
        # Numeric creation remains available even if Draft is not installed.
        return False
    return True


def ensure_draft_snap_toolbar_visible():
    """Show Draft's existing native snap toolbar while this workbench is active."""
    if not _metal_structure_is_active():
        return False
    toolbar = _find_native_draft_snap_toolbar()
    if toolbar is None:
        return False
    toolbar.setVisible(True)
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

        member_commands = ["BFC_CreateMember"]
        self.appendToolbar("Metal Structure - Elementos", member_commands)
        self.appendMenu("Metal Structure", member_commands)
        _ensure_native_draft_snap_toolbar(self)

    def Activated(self):
        _ensure_native_draft_snap_toolbar(self)
        schedule_draft_snap_toolbar_visible()

    def Deactivated(self):
        from . import commands

        commands.close_member_task_panel()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MetalStructureWorkbench())
