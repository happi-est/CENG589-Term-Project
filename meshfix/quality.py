from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from meshfix.io import Mesh


Vec3 = tuple[float, float, float]


@dataclass
class TriangleQuality:
    area: float
    min_angle: float
    max_angle: float
    aspect_ratio: float
    shortest_edge: float
    longest_edge: float


@dataclass
class MeshQualitySummary:
    name: str
    vertex_count: int
    face_count: int
    min_angle: float
    avg_min_angle: float
    max_angle: float
    avg_aspect_ratio: float
    low_aspect_count: int
    needle_like_count: int
    cap_like_count: int
    near_zero_area_count: int
    bad_triangle_count: int
    source: Optional[Path] = None

    def as_csv_row(self) -> list[str]:
        return [
            self.name,
            str(self.vertex_count),
            str(self.face_count),
            f"{self.min_angle:.6f}",
            f"{self.avg_min_angle:.6f}",
            f"{self.max_angle:.6f}",
            f"{self.avg_aspect_ratio:.6f}",
            str(self.low_aspect_count),
            str(self.needle_like_count),
            str(self.cap_like_count),
            str(self.near_zero_area_count),
            str(self.bad_triangle_count),
        ]


CSV_HEADER = [
    "name",
    "vertices",
    "faces",
    "min_angle_deg",
    "avg_min_angle_deg",
    "max_angle_deg",
    "avg_aspect_ratio",
    "low_aspect_count",
    "needle_like_count",
    "cap_like_count",
    "near_zero_area_count",
    "bad_triangle_count",
]


QUALITY_COLORS = {
    "good": (185, 190, 198, 255),
    "needle": (220, 52, 70, 255),
    "low_aspect": (241, 137, 45, 255),
    "cap": (126, 87, 194, 255),
    "zero_area": (20, 24, 31, 255),
}


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _safe_angle(a: Vec3, b: Vec3, c: Vec3) -> float:
    first = _sub(a, b)
    second = _sub(c, b)
    denom = _norm(first) * _norm(second)
    if denom == 0:
        return 0.0
    cosine = max(-1.0, min(1.0, _dot(first, second) / denom))
    return math.degrees(math.acos(cosine))


def _bbox_diagonal(vertices: list[Vec3]) -> float:
    if not vertices:
        return 0.0
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    return _norm((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))


def triangle_quality(mesh: Mesh, face: tuple[int, int, int]) -> TriangleQuality:
    a, b, c = (mesh.vertices[index] for index in face)
    edge_lengths = [_norm(_sub(a, b)), _norm(_sub(b, c)), _norm(_sub(c, a))]
    shortest = min(edge_lengths)
    longest = max(edge_lengths)
    aspect_ratio = 0.0 if longest == 0 else shortest / longest
    area = 0.5 * _norm(_cross(_sub(b, a), _sub(c, a)))
    angles = [_safe_angle(b, a, c), _safe_angle(a, b, c), _safe_angle(a, c, b)]
    return TriangleQuality(
        area=area,
        min_angle=min(angles),
        max_angle=max(angles),
        aspect_ratio=aspect_ratio,
        shortest_edge=shortest,
        longest_edge=longest,
    )


def analyze_mesh(
    mesh: Mesh,
    *,
    needle_angle_deg: float = 5.0,
    cap_angle_deg: float = 175.0,
    low_aspect_threshold: float = 0.05,
    area_epsilon_factor: float = 1e-14,
) -> MeshQualitySummary:
    qualities = [triangle_quality(mesh, face) for face in mesh.faces]
    name = mesh.source.name if mesh.source else "<memory>"

    if not qualities:
        return MeshQualitySummary(
            name=name,
            vertex_count=len(mesh.vertices),
            face_count=0,
            min_angle=0.0,
            avg_min_angle=0.0,
            max_angle=0.0,
            avg_aspect_ratio=0.0,
            low_aspect_count=0,
            needle_like_count=0,
            cap_like_count=0,
            near_zero_area_count=0,
            bad_triangle_count=0,
            source=mesh.source,
        )

    bbox_diag = _bbox_diagonal(mesh.vertices)
    area_epsilon = max(area_epsilon_factor, bbox_diag * bbox_diag * area_epsilon_factor)

    low_aspect_count = sum(q.aspect_ratio < low_aspect_threshold for q in qualities)
    needle_like_count = sum(
        q.min_angle < needle_angle_deg or q.aspect_ratio < low_aspect_threshold
        for q in qualities
    )
    cap_like_count = sum(q.max_angle > cap_angle_deg for q in qualities)
    near_zero_area_count = sum(q.area <= area_epsilon for q in qualities)
    bad_triangle_count = sum(
        q.min_angle < needle_angle_deg
        or q.aspect_ratio < low_aspect_threshold
        or q.max_angle > cap_angle_deg
        or q.area <= area_epsilon
        for q in qualities
    )

    return MeshQualitySummary(
        name=name,
        vertex_count=len(mesh.vertices),
        face_count=len(mesh.faces),
        min_angle=min(q.min_angle for q in qualities),
        avg_min_angle=sum(q.min_angle for q in qualities) / len(qualities),
        max_angle=max(q.max_angle for q in qualities),
        avg_aspect_ratio=sum(q.aspect_ratio for q in qualities) / len(qualities),
        low_aspect_count=low_aspect_count,
        needle_like_count=needle_like_count,
        cap_like_count=cap_like_count,
        near_zero_area_count=near_zero_area_count,
        bad_triangle_count=bad_triangle_count,
        source=mesh.source,
    )


def classify_triangle(
    quality: TriangleQuality,
    *,
    area_epsilon: float,
    needle_angle_deg: float = 5.0,
    cap_angle_deg: float = 175.0,
    low_aspect_threshold: float = 0.05,
) -> str:
    """Return the dominant quality label for one triangle."""
    if quality.area <= area_epsilon:
        return "zero_area"
    if quality.max_angle > cap_angle_deg:
        return "cap"
    if quality.min_angle < needle_angle_deg:
        return "needle"
    if quality.aspect_ratio < low_aspect_threshold:
        return "low_aspect"
    return "good"


def classify_mesh_faces(
    mesh: Mesh,
    *,
    needle_angle_deg: float = 5.0,
    cap_angle_deg: float = 175.0,
    low_aspect_threshold: float = 0.05,
    area_epsilon_factor: float = 1e-14,
) -> list[str]:
    """Classify every face as good, needle, low_aspect, cap, or zero_area."""
    bbox_diag = _bbox_diagonal(mesh.vertices)
    area_epsilon = max(area_epsilon_factor, bbox_diag * bbox_diag * area_epsilon_factor)
    return [
        classify_triangle(
            triangle_quality(mesh, face),
            area_epsilon=area_epsilon,
            needle_angle_deg=needle_angle_deg,
            cap_angle_deg=cap_angle_deg,
            low_aspect_threshold=low_aspect_threshold,
        )
        for face in mesh.faces
    ]


def count_labels(labels: list[str]) -> dict[str, int]:
    counts = {label: 0 for label in QUALITY_COLORS}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return counts


def format_summary_table(summaries: list[MeshQualitySummary]) -> str:
    columns = [
        ("mesh", lambda s: s.name),
        ("V", lambda s: str(s.vertex_count)),
        ("F", lambda s: str(s.face_count)),
        ("min angle", lambda s: f"{s.min_angle:.2f}"),
        ("avg min", lambda s: f"{s.avg_min_angle:.2f}"),
        ("max angle", lambda s: f"{s.max_angle:.2f}"),
        ("aspect<.05", lambda s: str(s.low_aspect_count)),
        ("needle-like", lambda s: str(s.needle_like_count)),
        ("cap-like", lambda s: str(s.cap_like_count)),
        ("bad", lambda s: str(s.bad_triangle_count)),
    ]
    rows = [[getter(summary) for _, getter in columns] for summary in summaries]
    widths = [
        max(len(title), *(len(row[index]) for row in rows))
        for index, (title, _) in enumerate(columns)
    ]
    header = "  ".join(title.ljust(widths[index]) for index, (title, _) in enumerate(columns))
    divider = "  ".join("-" * width for width in widths)
    body = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    ]
    return "\n".join([header, divider, *body])
