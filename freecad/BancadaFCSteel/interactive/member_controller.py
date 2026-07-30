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
    WAITING_FIRST_POINT = auto()
    WAITING_SECOND_POINT = auto()
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
    """Own numeric and basic two-point creation for one task-panel session."""

    def __init__(self, document, member_factory: Callable = create_member, selection=None):
        self.document = document
        self._member_factory = member_factory
        self._selection = selection if selection is not None else Gui.Selection
        self.panel = None
        self.point_capture = None
        self.preview_tracker = None
        self._interactive_start = None
        self._interactive_start_snap = None
        self._interactive_candidate_snap = None
        self._interactive_end_snap = None
        self._capture_generation = 0
        self._pending_stop_generation = None
        self._defer = None
        self._request_close = None
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
        if self.state not in (
            ControllerState.READY_NUMERIC,
            ControllerState.WAITING_FIRST_POINT,
            ControllerState.WAITING_SECOND_POINT,
        ):
            raise RuntimeError("A sessão de criação não está ativa.")
        previous_state = self.state
        success_state = (
            ControllerState.WAITING_FIRST_POINT
            if previous_state in (
                ControllerState.WAITING_FIRST_POINT,
                ControllerState.WAITING_SECOND_POINT,
            )
            else ControllerState.READY_NUMERIC
        )
        result = self._create(options, success_state, previous_state)
        if success_state is ControllerState.WAITING_FIRST_POINT:
            self._interactive_start = None
            self._clear_snap_segment()
            if self.preview_tracker is not None:
                self.preview_tracker.hide()
                self._hide_snap_marker()
            self._notify_state()
        return result

    def _create(self, options, return_state, failure_state=None):
        if self.document is None:
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
            self.state = failure_state or return_state
            raise

        self.state = return_state
        if self._selection is not None:
            try:
                self._selection.clearSelection()
                self._selection.addSelection(member)
            except Exception:
                pass
        return CreationResult(
            member=member,
            next_default_name=next_default_label(
                document, options.element_type, options.designation
            ),
        )

    @property
    def capture_stop_pending(self):
        return self._pending_stop_generation is not None

    def start_capture(
        self,
        point_capture,
        preview_tracker,
        deferred_call=None,
        request_close=None,
    ):
        if self.state is not ControllerState.READY_NUMERIC:
            return False
        self._capture_generation += 1
        generation = self._capture_generation
        self.point_capture = point_capture
        self.preview_tracker = preview_tracker
        self._defer = deferred_call or (lambda callback: callback())
        self._request_close = request_close
        try:
            preview_tracker.attach()
            preview_tracker.hide()
            point_capture.start()
        except Exception:
            try:
                point_capture.stop()
            finally:
                try:
                    preview_tracker.detach()
                finally:
                    self.point_capture = None
                    self.preview_tracker = None
            raise
        self._interactive_start = None
        self._clear_snap_segment()
        self._pending_stop_generation = None
        self.state = ControllerState.WAITING_FIRST_POINT
        self._notify_state()
        return True

    def request_stop_capture(self):
        """Invalidate now and defer native cleanup to the next event-loop cycle."""
        if self.state not in (
            ControllerState.WAITING_FIRST_POINT,
            ControllerState.WAITING_SECOND_POINT,
        ):
            return False
        generation = self._capture_generation
        self.state = ControllerState.STOPPING
        self._pending_stop_generation = generation
        self._interactive_start = None
        self._clear_snap_segment()
        if self.point_capture is not None:
            self.point_capture.deactivate()
        if self.preview_tracker is not None:
            self.preview_tracker.hide()
        self._notify_state()
        self._defer(lambda: self._finish_deferred_stop(generation))
        return True

    def request_close_capture(self):
        """Defer closing the whole task panel outside the native callback."""
        if self.state not in (
            ControllerState.WAITING_FIRST_POINT,
            ControllerState.WAITING_SECOND_POINT,
        ):
            return False
        generation = self._capture_generation
        self.state = ControllerState.STOPPING
        self._pending_stop_generation = generation
        self._interactive_start = None
        self._clear_snap_segment()
        if self.point_capture is not None:
            self.point_capture.deactivate()
        if self.preview_tracker is not None:
            self.preview_tracker.hide()
        self._notify_state()
        self._defer(lambda: self._finish_deferred_close(generation))
        return True

    def _finish_deferred_close(self, generation):
        if (
            generation != self._capture_generation
            or generation != self._pending_stop_generation
        ):
            return
        callback = self._request_close
        if callback is None and self.panel is not None:
            callback = self.panel.request_close
        if callback is not None:
            callback()

    def _finish_deferred_stop(self, generation):
        if (
            generation != self._capture_generation
            or generation != self._pending_stop_generation
        ):
            return
        self._cleanup_capture()
        self._pending_stop_generation = None
        self.state = ControllerState.READY_NUMERIC
        self._notify_state()

    def stop_capture(self):
        """Synchronously clean resources when outside a native event callback."""
        if self.point_capture is None and self.preview_tracker is None:
            if self.state not in (ControllerState.INACTIVE, ControllerState.STOPPING):
                self.state = ControllerState.READY_NUMERIC
                self._notify_state()
            return
        self.state = ControllerState.STOPPING
        self._pending_stop_generation = None
        self._cleanup_capture()
        self.state = ControllerState.READY_NUMERIC
        self._notify_state()

    def _cleanup_capture(self):
        capture, tracker = self.point_capture, self.preview_tracker
        self._interactive_start = None
        self._clear_snap_segment()
        if capture is not None:
            capture.deactivate()
            capture.stop()
        if tracker is not None:
            tracker.detach()
        self.point_capture = None
        self.preview_tracker = None
        self._defer = None
        self._request_close = None

    @staticmethod
    def _resolved_point(result):
        return getattr(result, "point", result)

    def _update_snap_marker(self, result):
        if self.preview_tracker is None:
            return
        if bool(getattr(result, "snapped", False)):
            show_marker = getattr(self.preview_tracker, "show_snap_marker", None)
            if show_marker is not None:
                show_marker(self._resolved_point(result))
        else:
            self._hide_snap_marker()

    def _hide_snap_marker(self):
        if self.preview_tracker is None:
            return
        hide_marker = getattr(self.preview_tracker, "hide_snap_marker", None)
        if hide_marker is not None:
            hide_marker()

    def _clear_snap_segment(self):
        self._interactive_start_snap = None
        self._interactive_candidate_snap = None
        self._interactive_end_snap = None

    def handle_mouse_move(self, result):
        point = self._resolved_point(result)
        if self.state is ControllerState.WAITING_FIRST_POINT:
            self._interactive_candidate_snap = result
            self._update_snap_marker(result)
            if self.panel is not None:
                self.panel.update_candidate_start(point)
        elif self.state is ControllerState.WAITING_SECOND_POINT:
            self._interactive_candidate_snap = result
            self._update_snap_marker(result)
            if self.preview_tracker is not None:
                self.preview_tracker.update(self._interactive_start, point)
            if self.panel is not None:
                self.panel.update_candidate_point(point)

    def handle_click(self, result):
        point = self._resolved_point(result)
        self._update_snap_marker(result)
        if self.state is ControllerState.WAITING_FIRST_POINT:
            self._interactive_start = point
            self._interactive_start_snap = result
            self._interactive_candidate_snap = None
            self.state = ControllerState.WAITING_SECOND_POINT
            if self.panel is not None:
                self.panel.update_captured_start(point)
            self._notify_state()
            return None
        if self.state is not ControllerState.WAITING_SECOND_POINT:
            return None
        self.validate_points(self._interactive_start, point)
        self._interactive_end_snap = result
        return self.create_interactive_member(self._interactive_start, point)

    def create_interactive_member(self, start, end):
        if self.panel is None:
            raise RuntimeError("O painel de criação não está disponível.")
        options = self.panel.creation_options(start=start, end=end)
        try:
            result = self._create(options, ControllerState.WAITING_FIRST_POINT)
        except Exception:
            self.state = ControllerState.WAITING_SECOND_POINT
            raise
        self._interactive_start = None
        self._clear_snap_segment()
        if self.preview_tracker is not None:
            self.preview_tracker.hide()
            self._hide_snap_marker()
        self.panel.interactive_creation_succeeded(result)
        self._notify_state()
        return result

    def cancel_current_segment(self):
        if self.state is ControllerState.WAITING_SECOND_POINT:
            self._interactive_start = None
            self._clear_snap_segment()
            if self.preview_tracker is not None:
                self.preview_tracker.hide()
                self._hide_snap_marker()
            self.state = ControllerState.WAITING_FIRST_POINT
            self._notify_state()
        elif self.state is ControllerState.WAITING_FIRST_POINT:
            self.request_close_capture()

    def _notify_state(self):
        if self.panel is not None:
            self.panel.update_capture_state(self.state)

    def stop(self):
        if self.state is ControllerState.INACTIVE:
            return
        self.state = ControllerState.STOPPING
        self._capture_generation += 1
        self._pending_stop_generation = None
        try:
            self._cleanup_capture()
        except Exception:
            pass
        self.panel = None
        self.document = None
        self._selection = None
        self.state = ControllerState.INACTIVE
