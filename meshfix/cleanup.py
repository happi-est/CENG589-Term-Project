from __future__ import annotations

from dataclasses import dataclass

from meshfix.io import Mesh
from meshfix.quality import analyze_mesh, triangle_quality
from meshfix.remesh import (
    _cleanup_mesh,
    _collapse_is_safe,
    _distance,
    _edge_faces,
    _edge_key,
    _edge_opposites,
    _midpoint,
    _neighbors,
    _area_epsilon,
    split_selected_edges,
)


@dataclass
class CleanupIterationStats:
    iteration: int
    bad_before: int
    collapse_edges: int
    split_edges: int
    collapses: int
    splits: int
    vertices: int
    faces: int


@dataclass
class CleanupResult:
    mesh: Mesh
    stats: list[CleanupIterationStats]


def _longest_edge(mesh: Mesh, face: tuple[int, int, int]) -> tuple[int, int]:
    edges = [(face[0], face[1]), (face[1], face[2]), (face[2], face[0])]
    a, b = max(edges, key=lambda edge: _distance(mesh.vertices[edge[0]], mesh.vertices[edge[1]]))
    return _edge_key(a, b)


def _shortest_edge(mesh: Mesh, face: tuple[int, int, int]) -> tuple[int, int]:
    edges = [(face[0], face[1]), (face[1], face[2]), (face[2], face[0])]
    a, b = min(edges, key=lambda edge: _distance(mesh.vertices[edge[0]], mesh.vertices[edge[1]]))
    return _edge_key(a, b)


def _bad_face_operations(
    mesh: Mesh,
    *,
    needle_angle_deg: float,
    cap_angle_deg: float,
    low_aspect_threshold: float,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    collapse_edges: set[tuple[int, int]] = set()
    split_edges: set[tuple[int, int]] = set()
    for face in mesh.faces:
        quality = triangle_quality(mesh, face)
        if quality.max_angle > cap_angle_deg:
            split_edges.add(_longest_edge(mesh, face))
        elif quality.min_angle < needle_angle_deg or quality.aspect_ratio < low_aspect_threshold:
            collapse_edges.add(_shortest_edge(mesh, face))
    return collapse_edges, split_edges


def _collapse_selected_edges(mesh: Mesh, selected_edges: set[tuple[int, int]]) -> tuple[Mesh, int]:
    vertices = list(mesh.vertices)
    faces = list(mesh.faces)
    edge_to_faces = _edge_faces(faces)
    boundary_edges = {edge for edge, incident in edge_to_faces.items() if len(incident) == 1}
    neighbor_sets = _neighbors(faces, len(vertices))
    area_epsilon = _area_epsilon(vertices)
    parent = list(range(len(vertices)))
    used: set[int] = set()
    collapses = 0

    edges = sorted(
        (
            (_distance(vertices[a], vertices[b]), a, b)
            for a, b in selected_edges
            if a < len(vertices) and b < len(vertices)
        ),
        key=lambda item: item[0],
    )

    for _, a, b in edges:
        key = _edge_key(a, b)
        if key in boundary_edges:
            continue
        incident_faces = edge_to_faces.get(key, [])
        if len(incident_faces) != 2:
            continue
        common_neighbors = neighbor_sets[a].intersection(neighbor_sets[b])
        if common_neighbors != _edge_opposites(faces, incident_faces, key):
            continue
        if a in used or b in used:
            continue
        replacement = _midpoint(vertices[a], vertices[b])
        if not _collapse_is_safe(vertices, faces, (a, b), replacement, area_epsilon):
            continue
        vertices[a] = replacement
        parent[b] = a
        used.update((a, b))
        used.update(neighbor_sets[a])
        used.update(neighbor_sets[b])
        collapses += 1

    if collapses == 0:
        return mesh, 0

    collapsed_faces = [
        (parent[face[0]], parent[face[1]], parent[face[2]]) for face in faces
    ]
    return _cleanup_mesh(Mesh(vertices, collapsed_faces, source=mesh.source)), collapses


def cleanup_degenerate(
    mesh: Mesh,
    *,
    iterations: int = 3,
    needle_angle_deg: float = 5.0,
    cap_angle_deg: float = 175.0,
    low_aspect_threshold: float = 0.05,
) -> CleanupResult:
    current = mesh
    stats: list[CleanupIterationStats] = []

    for iteration in range(1, iterations + 1):
        summary = analyze_mesh(
            current,
            needle_angle_deg=needle_angle_deg,
            cap_angle_deg=cap_angle_deg,
            low_aspect_threshold=low_aspect_threshold,
        )
        collapse_edges, split_edges = _bad_face_operations(
            current,
            needle_angle_deg=needle_angle_deg,
            cap_angle_deg=cap_angle_deg,
            low_aspect_threshold=low_aspect_threshold,
        )
        if not collapse_edges and not split_edges:
            stats.append(
                CleanupIterationStats(
                    iteration=iteration,
                    bad_before=summary.bad_triangle_count,
                    collapse_edges=0,
                    split_edges=0,
                    collapses=0,
                    splits=0,
                    vertices=len(current.vertices),
                    faces=len(current.faces),
                )
            )
            break

        current, collapses = _collapse_selected_edges(current, collapse_edges)
        _, split_edges_after_collapse = _bad_face_operations(
            current,
            needle_angle_deg=needle_angle_deg,
            cap_angle_deg=cap_angle_deg,
            low_aspect_threshold=low_aspect_threshold,
        )
        current, splits = split_selected_edges(current, split_edges_after_collapse)
        stats.append(
            CleanupIterationStats(
                iteration=iteration,
                bad_before=summary.bad_triangle_count,
                collapse_edges=len(collapse_edges),
                split_edges=len(split_edges_after_collapse),
                collapses=collapses,
                splits=splits,
                vertices=len(current.vertices),
                faces=len(current.faces),
            )
        )

    return CleanupResult(mesh=current, stats=stats)


def format_cleanup_stats(stats: list[CleanupIterationStats]) -> str:
    if not stats:
        return ""
    columns = [
        ("iter", lambda s: str(s.iteration)),
        ("bad before", lambda s: str(s.bad_before)),
        ("collapse edges", lambda s: str(s.collapse_edges)),
        ("split edges", lambda s: str(s.split_edges)),
        ("collapses", lambda s: str(s.collapses)),
        ("splits", lambda s: str(s.splits)),
        ("V", lambda s: str(s.vertices)),
        ("F", lambda s: str(s.faces)),
    ]
    rows = [[getter(stat) for _, getter in columns] for stat in stats]
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
