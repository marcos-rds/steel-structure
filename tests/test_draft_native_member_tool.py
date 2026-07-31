"""Architecture checks for the FreeCAD Draft-native member tool."""

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "freecad/BancadaFCSteel/interactive/draft_member_tool.py"
OPTIONS = ROOT / "freecad/BancadaFCSteel/interactive/profile_options_widget.py"
COMMANDS = ROOT / "freecad/BancadaFCSteel/commands.py"


class DraftNativeArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TOOL.read_text(encoding="utf-8")
        cls.options = OPTIONS.read_text(encoding="utf-8")
        cls.commands = COMMANDS.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_tool_inherits_installed_draft_line(self):
        self.assertIn("class StructuralMemberDraftTool(gui_lines.Line):", self.source)

    def test_native_line_ui_receives_profile_widget_as_extra(self):
        self.assertIn("self.ui.lineUi(", self.source)
        self.assertIn("extra=self.profile_options", self.source)

    def test_native_line_action_and_getpoint_path_are_reused(self):
        self.assertIn("return super().action(arg)", self.source)
        self.assertNotIn("PointCapture", self.source)
        self.assertNotIn("SnapAdapter", self.source)
        self.assertNotIn("PreviewTracker", self.source)

    def test_only_native_soevent_callback_is_registered(self):
        self.assertEqual(self.source.count('addEventCallback("SoEvent", self.action)'), 1)
        self.assertNotIn("SoLocation2Event", self.source)

    def test_final_creation_uses_member_controller_not_draft_line_commit(self):
        self.assertIn("self.controller.create(", self.source)
        self.assertIn("gui_base_original.Creator.finish(self)", self.source)
        self.assertNotIn("Draft.make_wire", self.source)
        self.assertNotIn("Part::Line", self.source)

    def test_temporary_line_is_hidden_and_removed(self):
        self.assertIn("self.obj.ViewObject.ShowInTree = False", self.source)
        self.assertIn("self.removeTemporaryObject()", self.source)
        self.assertIn("self.doc.removeObject", self.source)

    def test_continue_is_native_and_defaults_enabled(self):
        self.assertIn("self.ui.continueMode = True", self.source)
        self.assertIn("self.ui.continueCmd.setChecked(True)", self.source)
        self.assertIn("self.ui.continueMode", self.source)

    def test_profile_widget_has_no_coordinate_controls(self):
        for forbidden in ("Ponto inicial", "Ponto final", "axis_constraint", "numeric_buffer"):
            self.assertNotIn(forbidden, self.options)

    def test_profile_widget_preserves_canonical_designation(self):
        self.assertIn("compact_profile_designation(designation), designation", self.options)
        self.assertIn("self.profile.currentData()", self.options)

    def test_command_uses_official_draft_initialization_and_safe_fallback(self):
        self.assertIn("import DraftTools", self.commands)
        self.assertIn("Interface Draft indisponível", self.commands)
        self.assertNotIn("panel.start_automatic_capture", self.commands)

    def test_no_custom_axis_filter_or_preview_in_native_tool(self):
        for forbidden in ("eventFilter", "axis_constraint", "numeric_buffer", "SoSeparator"):
            self.assertNotIn(forbidden, self.source)

    def test_escape_with_first_point_resets_segment_before_native_finish(self):
        self.assertIn("len(self.node) == 1", self.source)
        self.assertIn("self.node = []", self.source)

    def test_escape_is_key_down_only_and_ignores_repeat(self):
        self.assertIn('arg.get("State") != "DOWN"', self.source)
        self.assertIn('arg.get("AutoRepeat")', self.source)
        self.assertIn('arg.get("IsAutoRepeat")', self.source)

    def test_first_escape_defers_cleanup_without_finish(self):
        action = self.source.split("    def action(self, arg):", 1)[1].split(
            "    def _cancel_current_segment", 1)[0]
        self.assertIn("QTimer.singleShot(0, self._cancel_current_segment)", action)
        self.assertNotIn("self.finish(", action)

    def test_segment_cleanup_keeps_callback_and_profile_options(self):
        cleanup = self.source.split("    def _cancel_current_segment", 1)[1].split(
            "    def finish", 1)[0]
        self.assertNotIn("end_callbacks", cleanup)
        self.assertNotIn("profile_options =", cleanup)
        self.assertIn("Gui.Snapper.setTrackers()", cleanup)

    def test_second_escape_delegates_to_native_line(self):
        self.assertIn("return super().action(arg)", self.source)

    def test_registered_line_key_is_separate_from_preview_name(self):
        self.assertIn('Creator.Activated(self, "Line")', self.source)
        self.assertIn('addObject("Part::Feature", "MetalStructureDraftPreview")', self.source)
        self.assertNotIn('Creator.Activated(self, "MetalStructureDraftPreview")', self.source)

    def test_native_line_ui_is_initialized_once_per_activation(self):
        activated = self.source.split("    def Activated", 1)[1].split("    def action", 1)[0]
        self.assertEqual(activated.count("self.ui.lineUi("), 1)

    def test_finish_schedules_toolbar_restore(self):
        self.assertIn("schedule_draft_snap_toolbar_visible()", self.source)


if __name__ == "__main__":
    unittest.main()
