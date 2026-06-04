from __future__ import annotations

import math
from dataclasses import dataclass

from meshfix.io import Mesh


Vec3 = tuple[float, float, float]


@dataclass
class SizingStats:
    min_length: float
    max_length: float
    avg_length: float
    min_curvature: float
    max_curvature: float
    avg_curvature: float


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a: Vec3, scalar: float) -> Vec3:
    return (a[0] * scalar, a[1] * scalar, a[2] * scalar)


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


def _normalize(a: Vec3) -> Vec3:
    length = _norm(a)
    if length == 0:
        return (0.0, 0.0, 0.0)
    return (a[0] / length, a[1] / length, a[2] / length)


def _distance(a: Vec3, b: Vec3) -> float:
    return _norm(_sub(a, b))


def _face_normal_and_area(mesh: Mesh, face: tuple[int, int, int]) -> tuple[Vec3, float]:
    a, b, c = (mesh.vertices[index] for index in face)
    normal = _cross(_sub(b, a), _sub(c, a))
    double_area = _norm(normal)
    return _normalize(normal), 0.5 * double_area


def vertex_normals(mesh: Mesh) -> list[Vec3]:
    normals = [(0.0, 0.0, 0.0) for _ in mesh.vertices]
    for face in mesh.faces:
        normal, area = _face_normal_and_area(mesh, face)
        weighted = _mul(normal, area)
        for vertex in face:
            normals[vertex] = _add(normals[vertex], weighted)
    return [_normalize(normal) for normal in normals]


def _neighbors(mesh: Mesh) -> list[set[int]]:
    result = [set() for _ in mesh.vertices]
    for a, b, c in mesh.faces:
        result[a].update((b, c))
        result[b].update((a, c))
        result[c].update((a, b))
    return result


def curvature_proxy(mesh: Mesh) -> list[float]:
    """Estimate curvature from normal variation over one-ring edges.

    Dunyach et al. derive edge lengths from maximum absolute curvature. This
    project uses a simple discrete proxy: the largest vertex-normal change per
    unit edge length in the one-ring.
    """
    normals = vertex_normals(mesh)
    neighbors = _neighbors(mesh)
    values: list[float] = []
    for index, vertex in enumerate(mesh.vertices):
        max_value = 0.0
        for neighbor in neighbors[index]:
            edge_length = _distance(vertex, mesh.vertices[neighbor])
            if edge_length == 0:
                continue
            normal_change = _norm(_sub(normals[index], normals[neighbor]))
            max_value = max(max_value, normal_change / edge_length)
        values.append(max_value)
    return values


def sizing_field(
    mesh: Mesh,
    *,
    epsilon: float,
    min_length: float,
    max_length: float,
) -> tuple[list[float], SizingStats]:
    curvatures = curvature_proxy(mesh)
    lengths: list[float] = []
    for curvature in curvatures:
        if curvature <= 1e-12:
            length = max_length
        else:
            value = (6.0 * epsilon / curvature) - (3.0 * epsilon * epsilon)
            length = math.sqrt(value) if value > 0.0 else min_length
        lengths.append(max(min_length, min(max_length, length)))

    if not lengths:
        return [], SizingStats(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    return lengths, SizingStats(
        min_length=min(lengths),
        max_length=max(lengths),
        avg_length=sum(lengths) / len(lengths),
        min_curvature=min(curvatures),
        max_curvature=max(curvatures),
        avg_curvature=sum(curvatures) / len(curvatures),
    )


def format_sizing_stats(stats: SizingStats) -> str:
    return (
        f"sizing min={stats.min_length:.6f}, "
        f"avg={stats.avg_length:.6f}, "
        f"max={stats.max_length:.6f}; "
        f"curvature min={stats.min_curvature:.6f}, "
        f"avg={stats.avg_curvature:.6f}, "
        f"max={stats.max_curvature:.6f}"
    )

