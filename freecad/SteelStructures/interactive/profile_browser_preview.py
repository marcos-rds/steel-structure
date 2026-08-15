# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native Qt renderer for pure SectionGeometry2D contours."""

from dataclasses import dataclass
from html import escape

from PySide import QtCore, QtGui, QtWidgets

from ..profiles import SectionGeometry2D


DIMENSIONS_MODE = "dimensions"
PROPERTIES_MODE = "properties"
NEUTRAL_MODE = "neutral"
PREVIEW_MODES = (DIMENSIONS_MODE, PROPERTIES_MODE, NEUTRAL_MODE)
TEXT_LINE_GAP = 2.0
SYMBOL_VALUE_SEPARATOR = "&nbsp;"
GEOMETRY_CLEARANCE_PIXELS = 4.0
MIN_LABEL_CLEARANCE = 5.0
TW_TEXT_OFFSET = 18.0
TF_TEXT_OFFSET = 8.0
LINE_END_PADDING = 8.0
D_OFFSET_PIXELS = 38.0
D_MAX_COMPENSATION_PIXELS = 18.0
BF_OFFSET_PIXELS = 30.0
CANVAS_MARGIN_PIXELS = 12.0
TICK_PIXELS = 4.5
SMALL_EXTENSION_HALF_PIXELS = 7.0
TF_LINE_OFFSET_PIXELS = 14.0
EXTENSION_OVERSHOOT_PIXELS = 4.0
DIMENSION_COLOR = (128, 32, 48)


@dataclass
class _DimensionLabel:
    item: object
    width: float
    height: float


def _clamp(value, minimum, maximum):
    return max(minimum, min(float(value), maximum))


def _ignores_transformations_flag():
    graphics_item = QtWidgets.QGraphicsItem
    flag = getattr(graphics_item, "ItemIgnoresTransformations", None)
    if flag is not None:
        return flag
    return graphics_item.GraphicsItemFlag.ItemIgnoresTransformations


class SectionPreviewView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setMinimumHeight(190)
        self.setMaximumHeight(260)

    def set_geometry(self, geometry, dimension_rows=(), mode=DIMENSIONS_MODE):
        if not isinstance(geometry, SectionGeometry2D):
            raise TypeError("geometry deve ser SectionGeometry2D")
        if mode not in PREVIEW_MODES:
            raise ValueError("modo de preview inválido")
        self.scene().clear()
        path = QtGui.QPainterPath()
        first = geometry.outer_path.segments[0].start
        path.moveTo(first.x, -first.y)
        for segment in geometry.outer_path.segments:
            path.lineTo(segment.end.x, -segment.end.y)
        path.closeSubpath()

        outline = QtGui.QPen(QtGui.QColor(28, 28, 28))
        outline.setCosmetic(True)
        outline.setWidthF(1.35)
        fill = QtGui.QColor(216, 219, 223)
        self.scene().addPath(path, outline, QtGui.QBrush(fill))

        dimensions = {row.label: row.value for row in dimension_rows}
        if mode == DIMENSIONS_MODE and dimensions:
            self._add_dimensions(geometry, dimensions)
        elif mode == PROPERTIES_MODE:
            self._add_axes(geometry)

        visual_bounds = self.scene().itemsBoundingRect()
        scene_units_per_pixel = self._scene_units_per_pixel(geometry.bounds)
        margin_x = CANVAS_MARGIN_PIXELS * scene_units_per_pixel
        margin_y = CANVAS_MARGIN_PIXELS * scene_units_per_pixel
        self.scene().setSceneRect(
            visual_bounds.adjusted(-margin_x, -margin_y, margin_x, margin_y)
        )
        self._fit()

    def _annotation_pen(self, line_style=None):
        pen = QtGui.QPen(QtGui.QColor(*DIMENSION_COLOR))
        pen.setCosmetic(True)
        pen.setWidthF(0.65)
        if line_style is not None:
            pen.setStyle(line_style)
        return pen

    def _scene_units_per_pixel(self, bounds):
        """Estimate model units per visible pixel before fitInView."""
        viewport_getter = getattr(self, "viewport", None)
        viewport = viewport_getter() if callable(viewport_getter) else None
        width = max(float(viewport.width()), 1.0) if viewport is not None else 500.0
        height = max(float(viewport.height()), 1.0) if viewport is not None else 240.0
        return max(bounds.width / (width * 0.58), bounds.height / (height * 0.66), 0.75)

    @staticmethod
    def _d_offset_pixels(bounds):
        """Compensate the final fit compression without changing small profiles."""
        growth = _clamp((bounds.height - 180.0) / 448.0, 0.0, 1.0)
        return D_OFFSET_PIXELS + growth * D_MAX_COMPENSATION_PIXELS

    def _add_dimensions(self, geometry, dimensions, _palette=None):
        """Add four true dimensions without rebuilding the section contour."""
        pen = self._annotation_pen()
        bounds = geometry.bounds
        left, right = bounds.min_x, bounds.max_x
        top, bottom = -bounds.max_y, -bounds.min_y
        scene_units_per_pixel = self._scene_units_per_pixel(bounds)
        offset_x = self._d_offset_pixels(bounds) * scene_units_per_pixel
        offset_y = BF_OFFSET_PIXELS * scene_units_per_pixel
        clearance = GEOMETRY_CLEARANCE_PIXELS * scene_units_per_pixel

        self._add_bf_dimension(
            left, right, top, offset_y, clearance, scene_units_per_pixel,
            dimensions["bf"], pen,
        )
        self._add_d_dimension(
            left, top, bottom, offset_x, clearance, scene_units_per_pixel,
            dimensions["d"], pen,
        )

        web_left = geometry.outer_path.segments[8].end.x
        web_right = geometry.outer_path.segments[3].end.x
        self._add_tw_dimension(
            web_left, web_right, dimensions["tw"], pen
        )

        bottom_flange = geometry.outer_path.segments[1]
        flange_top = -bottom_flange.end.y
        flange_bottom = -bottom_flange.start.y
        self._add_tf_dimension(
            right, flange_top, flange_bottom, clearance, scene_units_per_pixel,
            dimensions["tf"], pen,
        )

    @staticmethod
    def _dimension_parts(symbol, value):
        return f"({symbol})", value.removesuffix(" mm")

    def _add_bf_dimension(self, left, right, top, offset, clearance,
                          scene_units_per_pixel, value, pen):
        line_y = top - offset
        group = self._create_dimension_label(self._dimension_parts("bf", value), pen.color())
        self._position_label(
            group, (left + right) / 2.0, line_y,
            -group.width / 2.0, -TEXT_LINE_GAP - group.height,
        )
        overshoot = EXTENSION_OVERSHOOT_PIXELS * scene_units_per_pixel
        self._line(left, top - clearance, left, line_y - overshoot, pen)
        self._line(right, top - clearance, right, line_y - overshoot, pen)
        self._line(left, line_y, right, line_y, pen)
        self._terminator(left, line_y, pen)
        self._terminator(right, line_y, pen)

    def _add_d_dimension(self, left, top, bottom, offset, clearance,
                         scene_units_per_pixel, value, pen):
        line_x = left - offset
        center_y = (top + bottom) / 2.0
        group = self._create_dimension_label(self._dimension_parts("d", value), pen.color())
        self._position_label(
            group, line_x, center_y, -group.width / 2.0, -group.height / 2.0
        )
        break_half = (
            group.height / 2.0 + MIN_LABEL_CLEARANCE
        ) * scene_units_per_pixel
        overshoot = EXTENSION_OVERSHOOT_PIXELS * scene_units_per_pixel
        self._line(left - clearance, top, line_x - overshoot, top, pen)
        self._line(left - clearance, bottom, line_x - overshoot, bottom, pen)
        self._line(line_x, top, line_x, center_y - break_half, pen)
        self._line(line_x, center_y + break_half, line_x, bottom, pen)
        self._terminator(line_x, top, pen)
        self._terminator(line_x, bottom, pen)

    def _add_tw_dimension(self, web_left, web_right, value, pen):
        line_y = 0.0
        group = self._create_dimension_label(self._dimension_parts("tw", value), pen.color())
        self._position_label(
            group, web_right, line_y,
            TW_TEXT_OFFSET, -TEXT_LINE_GAP - group.height,
        )
        self._device_line(
            web_left, line_y, 0.0, -SMALL_EXTENSION_HALF_PIXELS,
            0.0, SMALL_EXTENSION_HALF_PIXELS, pen,
        )
        self._device_line(
            web_right, line_y, 0.0, -SMALL_EXTENSION_HALF_PIXELS,
            0.0, SMALL_EXTENSION_HALF_PIXELS, pen,
        )
        self._line(web_left, line_y, web_right, line_y, pen)
        self._terminator(web_left, line_y, pen)
        self._terminator(web_right, line_y, pen)
        self._device_line(
            web_right, line_y, 0.0, 0.0,
            TW_TEXT_OFFSET + group.width + LINE_END_PADDING + EXTENSION_OVERSHOOT_PIXELS,
            0.0, pen,
        )

    def _add_tf_dimension(self, right, flange_top, flange_bottom, clearance,
                          scene_units_per_pixel, value, pen):
        line_x = right + TF_LINE_OFFSET_PIXELS * scene_units_per_pixel
        group = self._create_dimension_label(self._dimension_parts("tf", value), pen.color())
        self._position_label(
            group, line_x, (flange_top + flange_bottom) / 2.0,
            TF_TEXT_OFFSET, -group.height / 2.0,
        )
        self._line(right + clearance, flange_top, line_x, flange_top, pen)
        self._line(right + clearance, flange_bottom, line_x, flange_bottom, pen)
        self._device_line(
            line_x, flange_top, 0.0, 0.0, EXTENSION_OVERSHOOT_PIXELS, 0.0, pen
        )
        self._device_line(
            line_x, flange_bottom, 0.0, 0.0, EXTENSION_OVERSHOOT_PIXELS, 0.0, pen
        )
        self._line(line_x, flange_top, line_x, flange_bottom, pen)
        self._terminator(line_x, flange_top, pen)
        self._terminator(line_x, flange_bottom, pen)

    def _add_axes(self, geometry):
        bounds = geometry.bounds
        extension = _clamp(max(bounds.width, bounds.height) * 0.10, 18.0, 48.0)
        x_pen = QtGui.QPen(QtGui.QColor(205, 45, 45))
        y_pen = QtGui.QPen(QtGui.QColor(38, 145, 72))
        for pen in (x_pen, y_pen):
            pen.setCosmetic(True)
            pen.setWidthF(1.05)
            pen.setDashPattern([9.0, 3.0, 2.0, 3.0])
        left, right = bounds.min_x - extension, bounds.max_x + extension
        top, bottom = -bounds.max_y - extension, -bounds.min_y + extension
        self._line(left, 0.0, right, 0.0, x_pen)
        self._line(0.0, top, 0.0, bottom, y_pen)
        self._label_lines(("X",), left, 0.0, x_pen.color(), x_offset=-8.0, bold=True)
        self._label_lines(("X",), right, 0.0, x_pen.color(), x_offset=8.0, bold=True)
        self._label_lines(("Y",), 0.0, top, y_pen.color(), y_offset=-9.0, bold=True)
        self._label_lines(("Y",), 0.0, bottom, y_pen.color(), y_offset=9.0, bold=True)
        radius = _clamp(min(bounds.width, bounds.height) * 0.018, 2.5, 5.0)
        self.scene().addEllipse(
            -radius, -radius, radius * 2.0, radius * 2.0,
            self._annotation_pen(), QtGui.QBrush(QtGui.QColor(255, 255, 255)),
        )

    def _line(self, x1, y1, x2, y2, pen):
        return self.scene().addLine(x1, y1, x2, y2, pen)

    def _device_line(self, anchor_x, anchor_y, x1, y1, x2, y2, pen):
        item = self.scene().addLine(x1, y1, x2, y2, pen)
        item.setPos(anchor_x, anchor_y)
        item.setFlag(_ignores_transformations_flag(), True)
        return item

    def _label_lines(self, lines, center_x, center_y, color, above=False,
                     x_offset=0.0, y_offset=0.0, bold=False):
        """Center every line independently and keep text size in screen pixels."""
        items = []
        total_height = 0.0
        for text in lines:
            item = self.scene().addText(text)
            item.setDefaultTextColor(color)
            if bold:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            item.setFlag(_ignores_transformations_flag(), True)
            rect = item.boundingRect()
            items.append((item, rect))
            total_height += rect.height()
        start_y = center_y - total_height if above else center_y - total_height / 2.0
        start_y += y_offset
        for item, rect in items:
            item.setPos(center_x + x_offset - rect.width() / 2.0, start_y)
            start_y += rect.height()

    def _create_dimension_label(self, parts, color):
        """Create one scale-independent rich label with invariant internal spacing."""
        item = self.scene().addText("")
        item.setDefaultTextColor(color)
        item.setHtml(
            "<span style='background-color:#ffffff'>"
            f"<b>{escape(parts[0])}</b>{SYMBOL_VALUE_SEPARATOR}{escape(parts[1])}</span>"
        )
        item.setFlag(_ignores_transformations_flag(), True)
        rect = item.boundingRect()
        return _DimensionLabel(item, rect.width(), rect.height())

    def _position_label(self, group, anchor_x, anchor_y, local_x, local_y):
        group.item.setPos(anchor_x, anchor_y)
        group.item.setTransform(
            QtGui.QTransform.fromTranslate(local_x, local_y)
        )

    def _terminator(self, x, y, pen):
        self._device_line(
            x, y, -TICK_PIXELS, TICK_PIXELS, TICK_PIXELS, -TICK_PIXELS, pen
        )

    def clear_geometry(self):
        self.scene().clear()

    def _fit(self):
        rect = self.scene().sceneRect()
        if not rect.isEmpty():
            margin = max(rect.width(), rect.height()) * 0.08
            self.fitInView(
                rect.adjusted(-margin, -margin, margin, margin),
                QtCore.Qt.KeepAspectRatio,
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()


__all__ = [
    "DIMENSIONS_MODE", "NEUTRAL_MODE", "PREVIEW_MODES", "PROPERTIES_MODE",
    "SectionPreviewView",
]
