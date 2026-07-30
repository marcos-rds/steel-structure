# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI-independent controller for structural member creation sessions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from FreeCAD import Gui

from ..member import create_member


class ControllerState(Enum):
    INACTIVE = auto()
    READY_NUMERIC = auto()
    CREATING = auto()
    STOPPING = auto()


@dataclass(frozen=True)
class MemberCreationOptions:
    start: object
    end: object
    designation: str
    element_type: str
    insertion: str
    rotation: float
    color: tuple[float, float, float]
    display_name: str


@dataclass(frozen=True)
class CreationResult:
    member: object
    next_default_name: str


def compact_profile_designation(designation: str) -> str:
    """Return a catalog designation without spaces for display purposes."""
    return "".join(designation.split())


def next_default_label(document, element_type: str, designation: str) -> str:
    """Return the next independent sequence label for an element type."""
    pattern = re.compile(rf"^{re.escape(element_type)}\s+(\d+)\b", re.IGNORECASE)
    highest = 0
    for obj in document.Objects:
        candidates = [str(getattr(obj, "Label", ""))]
        if "DisplayName" in getattr(obj, "PropertiesList", []):
            candidates.append(str(obj.DisplayName))
        for candidate in candidates:
            match = pattern.match(candidate.strip())
            if match:
                highest = max(highest, int(match.group(1)))
    return (
        f"{element_type} {highest + 1:03d} - "
        f"{compact_profile_designation(designation)}"
    )


class MemberController:
    """Own one numeric creation session without depending on Qt widgets."""

    def __init__(
        self,
        document,
        member_factory: Callable = create_member,
        selection=None,
    ):
        self.document = document
        self._member_factory = member_factory
        self._selection = selection if selection is not None else Gui.Selection
        self.panel = None
        self.state = ControllerState.INACTIVE

    def attach_panel(self, panel):
        self.panel = panel

    def start(self):
        if self.state is ControllerState.INACTIVE:
            self.state = ControllerState.READY_NUMERIC

    @staticmethod
    def validate_points(start, end):
        if start.sub(end).Length <= 1e-7:
            raise ValueError("Os pontos inicial e final devem ser diferentes.")

    def create(self, options: MemberCreationOptions) -> CreationResult:
        if self.state is not ControllerState.READY_NUMERIC or self.document is None:
            raise RuntimeError("A sessão de criação não está ativa.")
        self.validate_points(options.start, options.end)
        if not options.designation.strip():
            raise ValueError("Selecione um perfil cadastrado.")

        document = self.document
        self.state = ControllerState.CREATING
        document.openTransaction("Criar elemento estrutural")
        try:
            member = self._member_factory(
                document=document,
                start=options.start,
                end=options.end,
                designation=options.designation,
                element_type=options.element_type,
                insertion=options.insertion,
                rotation=options.rotation,
                color=options.color,
                display_name=options.display_name,
            )
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            self.state = ControllerState.READY_NUMERIC
            raise

        self.state = ControllerState.READY_NUMERIC
        if self._selection is not None:
            try:
                self._selection.clearSelection()
                self._selection.addSelection(member)
            except Exception:
                # Selection is a visual convenience; the object is already
                # committed and must not be reported as a failed creation.
                pass
        return CreationResult(
            member=member,
            next_default_name=next_default_label(
                document,
                options.element_type,
                options.designation,
            ),
        )

    def stop(self):
        if self.state in (ControllerState.INACTIVE, ControllerState.STOPPING):
            return
        self.state = ControllerState.STOPPING
        self.panel = None
        self.document = None
        self._selection = None
        self.state = ControllerState.INACTIVE
