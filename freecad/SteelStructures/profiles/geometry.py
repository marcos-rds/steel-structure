# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure two-dimensional geometry for structural profile sections.

Coordinates use millimetres in the local section plane: X is the flange-width
direction, Y is the web-height direction, and a future local Z axis is the
member longitudinal axis.  This module deliberately has no 3D placement,
rotation, insertion-point, FreeCAD, Part or UI concerns.

The current sharp-cornered I-section contour matches the historical member
approximation.  Published radii are unavailable, so no fictitious arcs are
created.  ``PathSegment2D`` permits a future arc primitive to participate in a
path without changing the path and section containers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .models import ProfileDefinition


class SectionGeometryError(ValueError):
    """Raised when section dimensions or path topology are invalid."""


class UnsupportedSectionGeometryError(SectionGeometryError):
    """Raised when a profile's geometry type/variant has no builder yet."""


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SectionGeometryError(f"{name} deve ser numérico")
    result = float(value)
    if not math.isfinite(result):
        raise SectionGeometryError(f"{name} deve ser finito")
    return result


@dataclass(frozen=True)
class Point2D:
    """A finite point in the local section plane, expressed in millimetres."""

    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite(self.x, "x"))
        object.__setattr__(self, "y", _finite(self.y, "y"))


@runtime_checkable
class PathSegment2D(Protocol):
    """Minimal interface shared by straight and future curved path segments."""

    @property
    def start(self) -> Point2D: ...

    @property
    def end(self) -> Point2D: ...


@dataclass(frozen=True)
class LineSegment2D:
    """A non-zero straight segment between two finite points."""

    start: Point2D
    end: Point2D

    def __post_init__(self) -> None:
        if not isinstance(self.start, Point2D) or not isinstance(self.end, Point2D):
            raise SectionGeometryError("segmentos devem usar Point2D")
        if self.start == self.end:
            raise SectionGeometryError("segmento não pode possuir comprimento zero")

    @property
    def length(self) -> float:
        return math.hypot(self.end.x - self.start.x, self.end.y - self.start.y)


@dataclass(frozen=True)
class SectionPath2D:
    """An ordered, continuous path with explicit closure state."""

    segments: tuple[PathSegment2D, ...]
    closed: bool

    def __post_init__(self) -> None:
        segments = tuple(self.segments)
        object.__setattr__(self, "segments", segments)
        if not segments:
            raise SectionGeometryError("caminho deve possuir ao menos um segmento")
        for index, segment in enumerate(segments):
            if not isinstance(segment, PathSegment2D):
                raise SectionGeometryError("segmento não implementa PathSegment2D")
            if index and segments[index - 1].end != segment.start:
                raise SectionGeometryError("caminho possui descontinuidade")
        if self.closed and segments[-1].end != segments[0].start:
            raise SectionGeometryError("caminho fechado não retorna ao ponto inicial")
        if not self.closed and segments[-1].end == segments[0].start:
            raise SectionGeometryError("caminho geometricamente fechado deve declarar closed=True")

    @property
    def signed_area(self) -> float:
        """Return shoelace signed area; CCW closed paths are positive."""
        if not self.closed:
            raise SectionGeometryError("área requer caminho fechado")
        return 0.5 * sum(
            segment.start.x * segment.end.y - segment.end.x * segment.start.y
            for segment in self.segments
        )

    @property
    def area(self) -> float:
        return abs(self.signed_area)


@dataclass(frozen=True)
class SectionBounds2D:
    """Axis-aligned bounds in the local section plane, in millimetres."""

    min_x: float
    max_x: float
    min_y: float
    max_y: float

    def __post_init__(self) -> None:
        for name in ("min_x", "max_x", "min_y", "max_y"):
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        if self.min_x >= self.max_x or self.min_y >= self.max_y:
            raise SectionGeometryError("bounds devem possuir largura e altura positivas")

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y


@dataclass(frozen=True)
class SectionGeometry2D:
    """Deterministic mathematical section geometry, not a CAD shape."""

    geometry_type: str
    geometry_variant: str
    outer_path: SectionPath2D
    inner_paths: tuple[SectionPath2D, ...]
    bounds: SectionBounds2D
    origin: Point2D

    def __post_init__(self) -> None:
        if not self.geometry_type or not self.geometry_variant:
            raise SectionGeometryError("tipo e variante geométrica são obrigatórios")
        if not isinstance(self.outer_path, SectionPath2D) or not self.outer_path.closed:
            raise SectionGeometryError("contorno externo deve ser um SectionPath2D fechado")
        inner_paths = tuple(self.inner_paths)
        object.__setattr__(self, "inner_paths", inner_paths)
        if any(not isinstance(path, SectionPath2D) or not path.closed for path in inner_paths):
            raise SectionGeometryError("contornos internos devem ser caminhos fechados")
        if not isinstance(self.bounds, SectionBounds2D):
            raise SectionGeometryError("bounds deve ser SectionBounds2D")
        if not isinstance(self.origin, Point2D):
            raise SectionGeometryError("origin deve ser Point2D")

    @property
    def signed_area(self) -> float:
        return self.outer_path.signed_area - sum(path.area for path in self.inner_paths)

    @property
    def area(self) -> float:
        return abs(self.signed_area)


def _closed_polygon(points: tuple[Point2D, ...]) -> SectionPath2D:
    if len(points) < 3:
        raise SectionGeometryError("polígono requer ao menos três pontos")
    segments = tuple(
        LineSegment2D(point, points[(index + 1) % len(points)])
        for index, point in enumerate(points)
    )
    return SectionPath2D(segments=segments, closed=True)


def build_parallel_flange_i_section(
    *, d: float, bf: float, tw: float, tf: float
) -> SectionGeometry2D:
    """Build one sharp-cornered, doubly symmetric parallel-flange I section."""
    d = _finite(d, "d")
    bf = _finite(bf, "bf")
    tw = _finite(tw, "tw")
    tf = _finite(tf, "tf")
    if min(d, bf, tw, tf) <= 0.0:
        raise SectionGeometryError("d, bf, tw e tf devem ser positivos")
    if tw >= bf:
        raise SectionGeometryError("tw deve ser menor que bf")
    if 2.0 * tf >= d:
        raise SectionGeometryError("2*tf deve ser menor que d")

    half_b = bf / 2.0
    half_d = d / 2.0
    half_tw = tw / 2.0
    inner_y = half_d - tf
    # Historical member order: lower-left start, then counter-clockwise.
    points = (
        Point2D(-half_b, -half_d),
        Point2D(half_b, -half_d),
        Point2D(half_b, -inner_y),
        Point2D(half_tw, -inner_y),
        Point2D(half_tw, inner_y),
        Point2D(half_b, inner_y),
        Point2D(half_b, half_d),
        Point2D(-half_b, half_d),
        Point2D(-half_b, inner_y),
        Point2D(-half_tw, inner_y),
        Point2D(-half_tw, -inner_y),
        Point2D(-half_b, -inner_y),
    )
    outer_path = _closed_polygon(points)
    return SectionGeometry2D(
        geometry_type="i_section",
        geometry_variant="parallel_flange",
        outer_path=outer_path,
        inner_paths=(),
        bounds=SectionBounds2D(-half_b, half_b, -half_d, half_d),
        origin=Point2D(0.0, 0.0),
    )


def build_section_geometry(profile: ProfileDefinition) -> SectionGeometry2D:
    """Dispatch a typed profile by geometry type and variant."""
    key = (profile.geometry_type, profile.geometry_variant)
    if key != ("i_section", "parallel_flange"):
        raise UnsupportedSectionGeometryError(
            f"geometria de seção ainda não suportada: {key[0]!r} / {key[1]!r}"
        )
    try:
        dimensions = {name: profile.geometry[name] for name in ("d", "bf", "tw", "tf")}
    except KeyError as exc:
        raise SectionGeometryError(f"dimensão ausente: {exc.args[0]}") from exc
    return build_parallel_flange_i_section(**dimensions)


__all__ = [
    "LineSegment2D", "PathSegment2D", "Point2D", "SectionBounds2D",
    "SectionGeometry2D", "SectionGeometryError", "SectionPath2D",
    "UnsupportedSectionGeometryError", "build_parallel_flange_i_section",
    "build_section_geometry",
]
