# SPDX-License-Identifier: LGPL-2.1-or-later
"""Interactive creation infrastructure for Metal Structure."""

from .member_controller import (
    ControllerState,
    MemberController,
    MemberCreationOptions,
    compact_profile_designation,
    next_default_label,
)
from .point_capture import PointCapture
from .preview_tracker import PreviewTracker
from .snap_adapter import (
    SNAP_TOLERANCE_PX,
    BasicEndpointSnapAdapter,
    DraftSnapToolbarManager,
    SnapAdapter,
    SnapResult,
)
try:
    from .draft_member_tool import StructuralMemberDraftTool, draft_native_available
except ImportError:
    StructuralMemberDraftTool = None
    draft_native_available = lambda: False

__all__ = [
    "ControllerState",
    "MemberController",
    "MemberCreationOptions",
    "compact_profile_designation",
    "next_default_label",
    "PointCapture",
    "PreviewTracker",
    "SNAP_TOLERANCE_PX",
    "BasicEndpointSnapAdapter",
    "DraftSnapToolbarManager",
    "SnapAdapter",
    "SnapResult",
    "StructuralMemberDraftTool",
    "draft_native_available",
]
