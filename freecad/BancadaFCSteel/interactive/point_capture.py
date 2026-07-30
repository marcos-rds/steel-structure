# SPDX-License-Identifier: LGPL-2.1-or-later
"""Basic two-point event capture for a FreeCAD 3D view."""

from __future__ import annotations

import traceback


class PointCapture:
    """Register and symmetrically remove view callbacks."""

    EVENT_TYPES = ("SoLocation2Event", "SoMouseButtonEvent", "SoKeyboardEvent")

    def __init__(
        self,
        view,
        on_move,
        on_click,
        on_escape,
        on_status=None,
        is_view_current=None,
        on_view_lost=None,
        on_error=None,
        snap_adapter=None,
        document=None,
        lastpoint_provider=None,
    ):
        self.view = view
        self._on_move = on_move
        self._on_click = on_click
        self._on_escape = on_escape
        self._on_status = on_status
        self._is_view_current = is_view_current
        self._on_view_lost = on_view_lost
        self._on_error = on_error
        if snap_adapter is None:
            from .snap_adapter import SnapAdapter
            snap_adapter = SnapAdapter()
        self._snap_adapter = snap_adapter
        self._document = document
        self._lastpoint_provider = lastpoint_provider
        self._callbacks = []
        self._accept_events = False
        self._started_once = False

    def is_active(self):
        return bool(self._callbacks)

    def start(self):
        if self.is_active():
            return
        if self._started_once:
            raise RuntimeError("Uma instância encerrada de PointCapture não pode ser reutilizada.")
        starter = getattr(self._snap_adapter, "start", None)
        if starter is not None:
            starter()
        handlers = (self._location_event, self._mouse_event, self._keyboard_event)
        registered = []
        try:
            for event_type, handler in zip(self.EVENT_TYPES, handlers):
                callback_id = self.view.addEventCallback(event_type, handler)
                registered.append((self.view, event_type, callback_id))
        except Exception:
            for view, event_type, callback_id in reversed(registered):
                try:
                    view.removeEventCallback(event_type, callback_id)
                except Exception:
                    pass
            stopper = getattr(self._snap_adapter, "stop", None)
            if stopper is not None:
                stopper()
            raise
        self._callbacks = registered
        self._accept_events = True
        self._started_once = True

    def deactivate(self):
        """Immediately ignore events while retaining native registrations."""
        self._accept_events = False

    def stop(self):
        self.deactivate()
        first_error = None
        for registration in tuple(self._callbacks):
            view, event_type, callback_id = registration
            try:
                view.removeEventCallback(event_type, callback_id)
            except Exception as exc:
                if first_error is None:
                    first_error = exc
            else:
                self._callbacks.remove(registration)
        if not self._callbacks:
            stopper = getattr(self._snap_adapter, "stop", None)
            if stopper is not None:
                try:
                    stopper()
                except Exception as exc:
                    if first_error is None:
                        first_error = exc
        if first_error is not None:
            raise first_error

    @staticmethod
    def _value(event, *names):
        for name in names:
            if name in event:
                return event[name]
        return None

    @classmethod
    def _position(cls, event):
        value = cls._value(event, "Position", "position", "Pos", "pos")
        if value is None:
            x = cls._value(event, "X", "x")
            y = cls._value(event, "Y", "y")
            if x is None or y is None:
                return None
            return int(x), int(y)
        try:
            return int(value[0]), int(value[1])
        except (KeyError, IndexError, TypeError, ValueError):
            x, y = getattr(value, "x", None), getattr(value, "y", None)
            x = x() if callable(x) else x
            y = y() if callable(y) else y
            if x is None or y is None:
                return None
            return int(x), int(y)

    def resolve_point(self, position, event=None):
        """Resolve a screen position through snap or view projection."""
        if position is None:
            return None
        try:
            options = getattr(
                self._snap_adapter, "event_options", lambda _event: (False, False)
            )(event or {})
            lastpoint = (
                self._lastpoint_provider()
                if self._lastpoint_provider is not None
                else None
            )
            result = self._snap_adapter.resolve(
                self.view,
                position,
                self._document,
                lastpoint=lastpoint,
                active=options[0],
                constrain=options[1],
            )
        except Exception:
            self._report_traceback()
            try:
                from .snap_adapter import SnapResult

                projected = self.view.getPoint(*position)
                result = (
                    SnapResult(point=projected, snapped=False, projected=True)
                    if projected is not None
                    else None
                )
            except Exception:
                result = None
        if result is not None and self._on_status is not None:
            status = getattr(self._snap_adapter, "status_message", None)
            if status is not None:
                self._on_status(status(result))
            elif result.snapped:
                self._on_status(
                    "Snap: extremidade — "
                    f"{result.object_name}/{result.subelement_name}"
                )
            else:
                self._on_status(
                    "Ponto projetado pela vista, sem snap geométrico."
                )
        return result

    def _view_is_current(self):
        if not self._accept_events:
            return False
        if self._is_view_current is None:
            return True
        try:
            current = bool(self._is_view_current())
        except Exception:
            current = False
        if not current and self._on_view_lost is not None:
            self._on_view_lost()
        return current

    def _guard_event(self, handler, event):
        try:
            handler(event)
        except Exception as exc:
            self.deactivate()
            self._report_traceback()
            if self._on_error is not None:
                try:
                    self._on_error(exc)
                except Exception:
                    self._report_traceback()

    @staticmethod
    def _report_traceback():
        message = traceback.format_exc()
        try:
            import FreeCAD as App
            App.Console.PrintError(
                "Metal Structure: exceção em callback da captura 3D:\n"
                f"{message}\n"
            )
        except Exception:
            pass

    def _location_event(self, event):
        self._guard_event(self._process_location_event, event)

    def _process_location_event(self, event):
        if not self._view_is_current():
            return
        point = self.resolve_point(self._position(event), event)
        if point is not None:
            self._on_move(point)

    def _mouse_event(self, event):
        self._guard_event(self._process_mouse_event, event)

    def _process_mouse_event(self, event):
        if not self._view_is_current():
            return
        button = self._value(event, "Button", "button")
        state = self._value(event, "State", "state")
        if str(button).upper() not in ("BUTTON1", "LEFT", "LEFTBUTTON", "1"):
            return
        if str(state).upper() not in ("DOWN", "PRESSED", "PRESS", "1", "TRUE"):
            return
        point = self.resolve_point(self._position(event), event)
        if point is not None:
            self._on_click(point)

    def _keyboard_event(self, event):
        self._guard_event(self._process_keyboard_event, event)

    def _process_keyboard_event(self, event):
        if not self._view_is_current():
            return
        key = self._value(event, "Key", "key")
        state = self._value(event, "State", "state")
        if str(key).upper() not in ("ESCAPE", "ESC"):
            return
        if state is not None and str(state).upper() not in (
            "DOWN", "PRESSED", "PRESS", "1", "TRUE"
        ):
            return
        self._on_escape()
