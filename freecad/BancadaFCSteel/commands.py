# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI commands for Metal Structure."""

from __future__ import annotations

import traceback

import FreeCAD as App
from FreeCAD import Gui
from PySide import QtWidgets

from .paths import MEMBER_ICON


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
    if tool is None:
        return False
    checker = getattr(tool, "is_active", None)
    return bool(
        callable(checker)
        and checker()
        and getattr(App, "activeDraftCommand", None) is tool
    )


def _discard_stale_member_session():
    global _active_member_tool

    tool = _active_member_tool
    if tool is None:
        return
    checker = getattr(tool, "is_active", None)
    if not callable(checker) or not checker() or getattr(App, "activeDraftCommand", None) is not tool:
        _active_member_tool = None


def _load_native_draft_tool():
    """Load the required native Draft interface."""
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
    """Start one native session with Draft's process-wide toolbar."""
    global _active_member_tool
    if getattr(App, "activeDraftCommand", None) is not None:
        raise RuntimeError("A Draft command is already active")
    import DraftTools  # noqa: F401 - official Draft initialization
    import DraftGui  # noqa: F401 - creates draftToolBar only when absent
    if not hasattr(Gui, "draftToolBar"):
        raise DraftInterfaceUnavailable("DraftToolBar was not initialized by Draft")
    Gui.Control.clearTaskWatcher()
    tool = tool_class(on_closed=_member_draft_tool_closed)
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
        global _active_member_tool

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

        try:
            tool_class = _load_native_draft_tool()
        except DraftInterfaceUnavailable:
            App.Console.PrintError(
                "Metal Structure: interface Draft indisponível:\n"
                + traceback.format_exc()
            )
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(),
                "Metal Structure",
                "Não foi possível iniciar a ferramenta nativa. "
                "Consulte a Vista de relatório.",
            )
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


def _member_draft_tool_closed(tool):
    global _active_member_tool
    if _active_member_tool is tool:
        _active_member_tool = None


def close_member_tool():
    """Close only the active native tool owned by Metal Structure."""
    global _active_member_tool

    tool = _active_member_tool
    if tool is None:
        return False
    try:
        tool.finish(cont=False)
    finally:
        if _active_member_tool is tool:
            _active_member_tool = None
    return True


Gui.addCommand("BFC_CreateMember", CreateMemberCommand())
