"""Tests for basic two-point capture and the lightweight axial preview."""

from __future__ import annotations

import importlib.util
import types
import unittest
from pathlib import Path

from test_interactive_creation import FakeDocument, Vector, _load_interactive_modules


ROOT = Path(__file__).resolve().parents[1]
INTERACTIVE = ROOT / "freecad" / "BancadaFCSteel" / "interactive"


def load_file(filename, module_name):
    spec = importlib.util.spec_from_file_location(module_name, INTERACTIVE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeView:
    def __init__(self):
        self.added = []
        self.removed = []
        self.graph = FakeGraph()
        self.fail_point = False

    def addEventCallback(self, event_type, handler):
        callback_id = len(self.added) + 10
        self.added.append((event_type, handler, callback_id))
        return callback_id

    def removeEventCallback(self, event_type, callback_id):
        self.removed.append((event_type, callback_id))

    def getPoint(self, x, y):
        if self.fail_point:
            raise RuntimeError("sem projeção")
        return Vector(x, y, 0)

    def getSceneGraph(self):
        return self.graph


class FakeGraph:
    def __init__(self):
        self.added = []
        self.removed = []

    def addChild(self, node):
        self.added.append(node)

    def removeChild(self, node):
        self.removed.append(node)


class Field:
    def __init__(self):
        self.values = []

    def setValues(self, *args):
        self.values.append(args)


class Node:
    def __init__(self):
        self.children = []

    def addChild(self, node):
        self.children.append(node)


class DrawStyle(Node):
    pass


class Color(Node):
    pass


class Coordinates(Node):
    def __init__(self):
        super().__init__()
        self.point = Field()


class Line(Node):
    def __init__(self):
        super().__init__()
        self.numVertices = Field()


class PointSet(Node):
    def __init__(self):
        super().__init__()
        self.numPoints = 0


COIN = types.SimpleNamespace(
    SoSeparator=Node,
    SoDrawStyle=DrawStyle,
    SoBaseColor=Color,
    SoCoordinate3=Coordinates,
    SoLineSet=Line,
    SoPointSet=PointSet,
)


class ProjectAdapter:
    def __init__(self):
        self.calls = []

    def resolve(self, view, position, document=None):
        self.calls.append((position, document))
        if view.fail_point:
            return None
        point = view.getPoint(*position)
        return types.SimpleNamespace(point=point, snapped=False, projected=True)


class PointCaptureTests(unittest.TestCase):
    def setUp(self):
        self.module = load_file("point_capture.py", "_point_capture_test")
        self.view = FakeView()
        self.moves, self.clicks, self.escapes, self.messages = [], [], [], []
        self.capture = self.module.PointCapture(
            self.view,
            self.moves.append,
            self.clicks.append,
            lambda: self.escapes.append(True),
            self.messages.append,
            snap_adapter=ProjectAdapter(),
        )
        self.capture._accept_events = True

    def test_registers_three_callbacks_once_and_stores_ids(self):
        self.capture.start()
        self.capture.start()
        self.assertEqual([item[0] for item in self.view.added], list(self.capture.EVENT_TYPES))
        self.assertEqual(len(self.capture._callbacks), 3)

    def test_removal_is_symmetric_and_stop_idempotent(self):
        self.capture.start()
        expected = [(kind, callback_id) for kind, _handler, callback_id in self.view.added]
        self.capture.stop()
        self.capture.stop()
        self.assertEqual(self.view.removed, expected)
        self.assertFalse(self.capture.is_active())

    def test_left_press_confirms_but_release_and_other_buttons_do_not(self):
        self.capture._mouse_event({"Button": "BUTTON1", "State": "DOWN", "Position": (2, 3)})
        self.capture._mouse_event({"Button": "BUTTON1", "State": "UP", "Position": (4, 5)})
        self.capture._mouse_event({"Button": "BUTTON2", "State": "DOWN", "Position": (6, 7)})
        self.capture._mouse_event({"Button": "BUTTON3", "State": "DOWN", "Position": (8, 9)})
        self.assertEqual([(r.point.x, r.point.y) for r in self.clicks], [(2, 3)])

    def test_movement_and_escape_are_forwarded(self):
        self.capture._location_event({"position": [10, 20]})
        self.capture._keyboard_event({"key": "ESCAPE", "state": "PRESSED"})
        self.assertEqual((self.moves[0].point.x, self.moves[0].point.y), (10, 20))
        self.assertEqual(self.escapes, [True])
        self.assertIn("projetado", self.messages[0])

    def test_resolution_failure_does_not_invent_or_forward_point(self):
        self.view.fail_point = True
        self.capture._location_event({"Position": (1, 2)})
        self.capture._mouse_event({"Button": "BUTTON1", "State": "DOWN"})
        self.assertEqual((self.moves, self.clicks), ([], []))

    def test_view_loss_stops_capture_without_forwarding_event(self):
        lost = []
        capture = self.module.PointCapture(
            self.view,
            self.moves.append,
            self.clicks.append,
            lambda: None,
            is_view_current=lambda: False,
            on_view_lost=lambda: lost.append(True),
            snap_adapter=ProjectAdapter(),
        )
        capture._accept_events = True
        capture._location_event({"Position": (1, 2)})
        self.assertEqual(self.moves, [])
        self.assertEqual(lost, [True])

    def test_forwarding_exception_uses_error_cleanup_callback(self):
        errors = []
        capture = self.module.PointCapture(
            self.view,
            lambda _point: (_ for _ in ()).throw(RuntimeError("erro")),
            self.clicks.append,
            lambda: None,
            on_error=errors.append,
            snap_adapter=ProjectAdapter(),
        )
        capture._accept_events = True
        capture._location_event({"Position": (1, 2)})
        self.assertEqual(str(errors[0]), "erro")

    def test_events_are_ignored_after_deactivation(self):
        self.capture.deactivate()
        self.capture._location_event({"Position": (1, 2)})
        self.capture._mouse_event(
            {"Button": "BUTTON1", "State": "DOWN", "Position": (1, 2)}
        )
        self.capture._keyboard_event({"Key": "ESCAPE", "State": "DOWN"})
        self.assertEqual((self.moves, self.clicks, self.escapes), ([], [], []))

    def test_new_instance_gets_new_callback_identifiers(self):
        self.capture.start()
        old_ids = [item[2] for item in self.capture._callbacks]
        self.capture.stop()
        second = self.module.PointCapture(
            self.view,
            self.moves.append,
            self.clicks.append,
            lambda: None,
            snap_adapter=ProjectAdapter(),
        )
        second.start()
        new_ids = [item[2] for item in second._callbacks]
        self.assertTrue(set(old_ids).isdisjoint(new_ids))

    def test_movement_and_click_resolve_independently_without_extra_callbacks(self):
        adapter = ProjectAdapter()
        capture = self.module.PointCapture(
            self.view,
            self.moves.append,
            self.clicks.append,
            lambda: None,
            snap_adapter=adapter,
        )
        capture.start()
        capture._location_event({"Position": (4, 5)})
        capture._mouse_event(
            {"Button": "BUTTON1", "State": "DOWN", "Position": (4, 5)}
        )
        self.assertEqual(len(adapter.calls), 2)
        self.assertEqual(len(self.view.added), 3)


class PreviewTrackerTests(unittest.TestCase):
    def setUp(self):
        self.module = load_file("preview_tracker.py", "_preview_tracker_test")
        self.view = FakeView()
        self.tracker = self.module.PreviewTracker(self.view, COIN)

    def test_attach_and_updates_reuse_one_tree(self):
        root = self.tracker.root
        self.tracker.attach()
        self.tracker.attach()
        self.tracker.update(Vector(0, 0, 0), Vector(1, 2, 3))
        self.tracker.update(Vector(1, 1, 1), Vector(4, 5, 6))
        self.assertEqual(self.view.graph.added, [root])
        self.assertIs(self.tracker.root, root)
        self.assertEqual(len(self.tracker._coordinates.point.values), 2)

    def test_hide_and_detach_are_idempotent_and_use_same_view(self):
        self.tracker.update(Vector(0, 0, 0), Vector(1, 0, 0))
        self.tracker.hide()
        self.assertEqual(self.tracker._line.numVertices.values[-1][-1], [0])
        self.tracker.detach()
        self.tracker.detach()
        self.assertEqual(self.view.graph.removed, [self.tracker.root])

    def test_snap_marker_is_created_once_updated_in_place_and_hidden(self):
        marker = self.tracker._marker
        coordinates = self.tracker._marker_coordinates
        self.tracker.show_snap_marker(Vector(1, 2, 3))
        self.tracker.show_snap_marker(Vector(4, 5, 6))
        self.assertIs(self.tracker._marker, marker)
        self.assertEqual(len(coordinates.point.values), 2)
        self.assertEqual(marker.numPoints, 1)
        self.tracker.hide_snap_marker()
        self.assertEqual(marker.numPoints, 0)


class InteractiveControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module, cls.panel_module, cls.selection, _control, cls.cleanup = (
            _load_interactive_modules()
        )

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()

    def setUp(self):
        self.document = FakeDocument()
        self.calls = []

        def factory(**kwargs):
            self.calls.append(kwargs)
            member = types.SimpleNamespace(
                Label=kwargs["display_name"],
                PropertiesList=[],
            )
            self.document.Objects.append(member)
            return member

        self.controller = self.module.MemberController(
            self.document, factory, self.selection
        )
        self.capture = types.SimpleNamespace(
            starts=0, stops=0, deactivations=0,
            start=lambda: setattr(self.capture, "starts", self.capture.starts + 1),
            stop=lambda: setattr(self.capture, "stops", self.capture.stops + 1),
            deactivate=lambda: setattr(
                self.capture, "deactivations", self.capture.deactivations + 1
            ),
        )
        self.preview = types.SimpleNamespace(
            attaches=0, hides=0, marker_hides=0, detaches=0, updates=[],
            attach=lambda: setattr(self.preview, "attaches", self.preview.attaches + 1),
            hide=lambda: setattr(self.preview, "hides", self.preview.hides + 1),
            hide_snap_marker=lambda: setattr(
                self.preview, "marker_hides", self.preview.marker_hides + 1
            ),
            show_snap_marker=lambda point: setattr(self.preview, "marker_point", point),
            detach=lambda: setattr(self.preview, "detaches", self.preview.detaches + 1),
            update=lambda a, b: self.preview.updates.append((a, b)),
        )
        self.panel = FakePanel(self.module)
        self.panel.module_controller = self.controller
        self.controller.attach_panel(self.panel)
        self.controller.start()

    def test_capture_transitions_click_move_and_continuous_creation(self):
        state = self.module.ControllerState
        self.controller.start_capture(self.capture, self.preview)
        self.assertIs(self.controller.state, state.WAITING_FIRST_POINT)
        start, end = Vector(0, 0, 0), Vector(100, 20, 5)
        self.controller.handle_click(start)
        self.assertIs(self.controller.state, state.WAITING_SECOND_POINT)
        self.controller.handle_mouse_move(end)
        self.assertEqual(self.preview.updates, [(start, end)])
        self.controller.handle_click(end)
        self.assertIs(self.controller.state, state.WAITING_FIRST_POINT)
        self.assertEqual((self.document.commits, len(self.calls)), (1, 1))
        self.assertEqual(self.panel.successes, 1)

    def test_movement_before_first_click_updates_start_without_preview(self):
        point = Vector(12, 34, 56)
        self.controller.start_capture(self.capture, self.preview)
        self.controller.handle_mouse_move(point)
        self.assertIs(self.panel.candidate_start, point)
        self.assertEqual(self.preview.updates, [])

    def test_coincident_click_is_rejected_without_transaction(self):
        point = Vector(1, 2, 3)
        self.controller.start_capture(self.capture, self.preview)
        self.controller.handle_click(point)
        with self.assertRaises(ValueError):
            self.controller.handle_click(point)
        self.assertEqual(self.document.opened, [])

    def test_numeric_creation_keeps_capture_and_returns_to_first_point(self):
        self.controller.start_capture(self.capture, self.preview)
        self.controller.handle_click(Vector(5, 5, 5))
        result = self.controller.create(
            self.module.MemberCreationOptions(
                Vector(0, 0, 0),
                Vector(100, 0, 0),
                "W 150 x 13,0",
                "Membro",
                "Centroide",
                0.0,
                (0.7, 0.7, 0.7),
                "Membro 001 - W150x13,0",
            )
        )
        self.assertIsNotNone(result.member)
        self.assertIs(
            self.controller.state,
            self.module.ControllerState.WAITING_FIRST_POINT,
        )
        self.assertEqual(self.capture.stops, 0)
        self.assertEqual(self.preview.detaches, 0)

    def test_escape_cancels_segment_then_closes_tool(self):
        state = self.module.ControllerState
        self.controller.start_capture(self.capture, self.preview)
        self.controller.handle_click(Vector(0, 0, 0))
        self.controller.cancel_current_segment()
        self.assertIs(self.controller.state, state.WAITING_FIRST_POINT)
        self.controller.cancel_current_segment()
        self.assertIs(self.controller.state, state.INACTIVE)
        self.assertEqual((self.capture.stops, self.preview.detaches), (1, 1))

    def test_first_escape_keeps_callbacks_and_tracker_attached(self):
        self.controller.start_capture(self.capture, self.preview)
        self.controller.handle_click(Vector(0, 0, 0))
        self.controller.cancel_current_segment()
        self.assertEqual(self.capture.stops, 0)
        self.assertEqual(self.preview.detaches, 0)
        self.assertEqual(self.preview.hides, 2)

    def test_second_escape_defers_cleanup_and_ignores_pending_events(self):
        queued = []
        self.controller.start_capture(
            self.capture, self.preview, lambda callback: queued.append(callback)
        )
        self.controller.cancel_current_segment()
        self.assertIs(self.controller.state, self.module.ControllerState.STOPPING)
        self.assertTrue(self.controller.capture_stop_pending)
        self.assertEqual((self.capture.stops, self.preview.detaches), (0, 0))
        self.controller.handle_click(Vector(0, 0, 0))
        self.controller.handle_mouse_move(Vector(1, 0, 0))
        self.assertEqual(self.preview.updates, [])
        queued.pop()()
        self.assertEqual((self.capture.stops, self.preview.detaches), (1, 1))
        self.assertIs(self.controller.state, self.module.ControllerState.INACTIVE)

    def test_callbacks_are_removed_before_preview_detach(self):
        order = []
        self.capture.stop = lambda: order.append("callbacks")
        self.preview.detach = lambda: order.append("preview")
        self.controller.start_capture(self.capture, self.preview)
        self.controller.stop_capture()
        self.assertEqual(order, ["callbacks", "preview"])

    def test_references_are_retained_until_native_cleanup_finishes(self):
        observed = []
        self.capture.stop = lambda: observed.append(
            (
                "callbacks",
                self.controller.point_capture is self.capture,
                self.controller.preview_tracker is self.preview,
            )
        )
        self.preview.detach = lambda: observed.append(
            (
                "preview",
                self.controller.point_capture is self.capture,
                self.controller.preview_tracker is self.preview,
            )
        )
        self.controller.start_capture(self.capture, self.preview)
        self.controller.stop_capture()
        self.assertEqual(
            observed,
            [("callbacks", True, True), ("preview", True, True)],
        )

    def test_stale_deferred_task_does_not_stop_new_capture(self):
        queued = []
        self.controller.start_capture(
            self.capture, self.preview, lambda callback: queued.append(callback)
        )
        self.controller.request_stop_capture()
        self.controller.stop_capture()
        new_capture = types.SimpleNamespace(
            starts=0, stops=0, deactivations=0,
            start=lambda: setattr(new_capture, "starts", new_capture.starts + 1),
            stop=lambda: setattr(new_capture, "stops", new_capture.stops + 1),
            deactivate=lambda: setattr(
                new_capture, "deactivations", new_capture.deactivations + 1
            ),
        )
        new_preview = types.SimpleNamespace(
            attaches=0, hides=0, detaches=0,
            attach=lambda: setattr(new_preview, "attaches", new_preview.attaches + 1),
            hide=lambda: setattr(new_preview, "hides", new_preview.hides + 1),
            detach=lambda: setattr(new_preview, "detaches", new_preview.detaches + 1),
        )
        self.controller.start_capture(new_capture, new_preview)
        queued.pop()()
        self.assertIs(self.controller.point_capture, new_capture)
        self.assertEqual(new_capture.stops, 0)

    def test_panel_close_during_pending_cleanup_invalidates_task(self):
        queued = []
        self.controller.start_capture(
            self.capture, self.preview, lambda callback: queued.append(callback)
        )
        self.controller.request_stop_capture()
        self.controller.stop()
        queued.pop()()
        self.assertIs(self.controller.state, self.module.ControllerState.INACTIVE)
        self.assertEqual(self.capture.stops, 1)

    def test_capture_can_restart_with_fresh_resources_after_stop(self):
        self.controller.start_capture(self.capture, self.preview)
        self.controller.stop_capture()
        fresh_capture = types.SimpleNamespace(
            starts=0, stops=0, deactivations=0,
            start=lambda: setattr(fresh_capture, "starts", fresh_capture.starts + 1),
            stop=lambda: setattr(fresh_capture, "stops", fresh_capture.stops + 1),
            deactivate=lambda: setattr(
                fresh_capture, "deactivations", fresh_capture.deactivations + 1
            ),
        )
        fresh_preview = types.SimpleNamespace(
            attaches=0, hides=0, detaches=0,
            attach=lambda: setattr(fresh_preview, "attaches", fresh_preview.attaches + 1),
            hide=lambda: setattr(fresh_preview, "hides", fresh_preview.hides + 1),
            detach=lambda: setattr(fresh_preview, "detaches", fresh_preview.detaches + 1),
        )
        self.assertTrue(self.controller.start_capture(fresh_capture, fresh_preview))
        self.assertIs(self.controller.point_capture, fresh_capture)

    def test_panel_has_no_manual_capture_buttons(self):
        panel = self.panel_module.MemberTaskPanel.__new__(
            self.panel_module.MemberTaskPanel
        )
        panel.capture_state_label = types.SimpleNamespace(setText=lambda _text: None)
        panel.update_capture_state(self.module.ControllerState.STOPPING)
        self.assertFalse(hasattr(panel, "capture_button"))
        self.assertFalse(hasattr(panel, "stop_capture_button"))

    def test_failure_preserves_name_and_second_point_state(self):
        self.controller._member_factory = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("erro"))
        self.panel.custom = True
        self.panel.name = "teste1"
        self.controller.start_capture(self.capture, self.preview)
        self.controller.handle_click(Vector(0, 0, 0))
        with self.assertRaises(RuntimeError):
            self.controller.handle_click(Vector(1, 0, 0))
        self.assertTrue(self.panel.custom)
        self.assertEqual(self.panel.name, "teste1")
        self.assertIs(self.controller.state, self.module.ControllerState.WAITING_SECOND_POINT)
        self.assertEqual(self.document.aborts, 1)

    def test_stop_cleans_resources_and_is_idempotent(self):
        self.controller.start_capture(self.capture, self.preview)
        self.controller.stop()
        self.controller.stop()
        self.assertEqual((self.capture.stops, self.preview.detaches), (1, 1))
        self.assertIs(self.controller.state, self.module.ControllerState.INACTIVE)

    def test_snap_metadata_and_exact_points_are_used_then_cleared(self):
        self.controller.start_capture(self.capture, self.preview)
        start = types.SimpleNamespace(
            point=Vector(10, 20, 30), snapped=True, snap_type="endpoint",
            object_name="A", subelement_name="Vertex1",
        )
        end = types.SimpleNamespace(
            point=Vector(40, 50, 60), snapped=True, snap_type="endpoint",
            object_name="B", subelement_name="Edge1.Endpoint2",
        )
        self.controller.handle_click(start)
        self.assertIs(self.controller._interactive_start_snap, start)
        self.controller.handle_mouse_move(end)
        self.assertIs(self.controller._interactive_candidate_snap, end)
        self.controller.handle_click(end)
        self.assertEqual(
            (
                self.calls[0]["start"].x,
                self.calls[0]["start"].y,
                self.calls[0]["end"].z,
            ),
            (10, 20, 60),
        )
        self.assertIsNone(self.controller._interactive_start_snap)
        self.assertIsNone(self.controller._interactive_end_snap)

    def test_escape_clears_snap_metadata_and_marker(self):
        self.controller.start_capture(self.capture, self.preview)
        snapped = types.SimpleNamespace(
            point=Vector(1, 2, 3), snapped=True, snap_type="endpoint",
            object_name="A", subelement_name="Vertex1",
        )
        self.controller.handle_click(snapped)
        self.controller.handle_mouse_move(snapped)
        self.controller.cancel_current_segment()
        self.assertIsNone(self.controller._interactive_start_snap)
        self.assertIsNone(self.controller._interactive_candidate_snap)
        self.assertGreater(self.preview.marker_hides, 0)


class FakePanel:
    def __init__(self, module):
        self.module = module
        self.states = []
        self.successes = 0
        self.custom = False
        self.name = "Membro 001 - W150x13,0"
        self.close_requests = 0
        self.candidate_start = None

    def update_capture_state(self, state):
        self.states.append(state)

    def update_captured_start(self, _point):
        pass

    def update_candidate_point(self, _point):
        pass

    def update_candidate_start(self, point):
        self.candidate_start = point

    def creation_options(self, start=None, end=None):
        return self.module.MemberCreationOptions(
            start, end, "W 150 x 13,0", "Membro", "Centroide", 0.0,
            (0.7, 0.7, 0.7), self.name,
        )

    def interactive_creation_succeeded(self, result):
        self.successes += 1
        self.custom = False
        self.name = result.next_default_name

    def request_close(self):
        self.close_requests += 1
        self.module_controller.stop()

if __name__ == "__main__":
    unittest.main()
