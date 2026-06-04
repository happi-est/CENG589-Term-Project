from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from meshfix.io import Mesh
from meshfix.quality import triangle_quality
from meshfix.curvature import sizing_field


Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]


@dataclass
class RemeshIterationStats:
    iteration: int
    splits: int
    collapses: int
    flips: int
    vertices: int
    faces: int


@dataclass
class RemeshResult:
    mesh: Mesh
    target_length: float
    stats: list[RemeshIterationStats]


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


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


def _distance(a: Vec3, b: Vec3) -> float:
    return _norm(_sub(a, b))


def _squared_distance(a: Vec3, b: Vec3) -> float:
    diff = _sub(a, b)
    return _dot(diff, diff)


def _midpoint(a: Vec3, b: Vec3) -> Vec3:
    return _mul(_add(a, b), 0.5)


def _area(vertices: list[Vec3], face: Face) -> float:
    a, b, c = (vertices[index] for index in face)
    return 0.5 * _norm(_cross(_sub(b, a), _sub(c, a)))


def _area_epsilon(vertices: list[Vec3]) -> float:
    if not vertices:
        return 1e-14
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    diagonal = _norm((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
    return max(1e-14, diagonal * diagonal * 1e-14)


def _edge_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _face_edges(face: Face) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    return ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))


def _unique_edges(faces: list[Face]) -> set[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    for face in faces:
        for a, b in _face_edges(face):
            edges.add(_edge_key(a, b))
    return edges


def _edge_faces(faces: list[Face]) -> dict[tuple[int, int], list[int]]:
    result: dict[tuple[int, int], list[int]] = {}
    for face_index, face in enumerate(faces):
        for a, b in _face_edges(face):
            result.setdefault(_edge_key(a, b), []).append(face_index)
    return result


def _neighbors(faces: list[Face], vertex_count: int) -> list[set[int]]:
    result = [set() for _ in range(vertex_count)]
    for a, b, c in faces:
        result[a].update((b, c))
        result[b].update((a, c))
        result[c].update((a, b))
    return result


def _edge_opposites(faces: list[Face], incident_faces: list[int], edge: tuple[int, int]) -> set[int]:
    opposites: set[int] = set()
    for face_index in incident_faces:
        for vertex in faces[face_index]:
            if vertex not in edge:
                opposites.add(vertex)
    return opposites


def _boundary_vertices(faces: list[Face]) -> set[int]:
    boundary: set[int] = set()
    for (a, b), incident in _edge_faces(faces).items():
        if len(incident) == 1:
            boundary.update((a, b))
    return boundary


def _cleanup_mesh(mesh: Mesh) -> Mesh:
    vertices = list(mesh.vertices)
    area_epsilon = _area_epsilon(vertices)
    clean_faces: list[Face] = []
    seen_faces: set[tuple[int, int, int]] = set()

    for face in mesh.faces:
        if len(set(face)) != 3:
            continue
        if _area(vertices, face) <= area_epsilon:
            continue
        key = tuple(sorted(face))
        if key in seen_faces:
            continue
        seen_faces.add(key)
        clean_faces.append(face)

    used = sorted({index for face in clean_faces for index in face})
    remap = {old: new for new, old in enumerate(used)}
    compact_vertices = [vertices[index] for index in used]
    compact_faces = [
        (remap[face[0]], remap[face[1]], remap[face[2]]) for face in clean_faces
    ]
    return Mesh(compact_vertices, compact_faces, source=mesh.source)


def estimate_target_length(mesh: Mesh, percentile: float = 25.0) -> float:
    lengths = sorted(
        _distance(mesh.vertices[a], mesh.vertices[b])
        for a, b in _unique_edges(mesh.faces)
        if _distance(mesh.vertices[a], mesh.vertices[b]) > 0
    )
    if not lengths:
        return 1.0
    index = int(max(0, min(len(lengths) - 1, len(lengths) * percentile / 100.0)))
    return lengths[index]


def split_selected_edges(mesh: Mesh, split_edges: set[tuple[int, int]]) -> tuple[Mesh, int]:
    vertices = list(mesh.vertices)
    if not split_edges:
        return mesh, 0

    midpoint_indices: dict[tuple[int, int], int] = {}
    for a, b in sorted(split_edges):
        midpoint_indices[(a, b)] = len(vertices)
        vertices.append(_midpoint(vertices[a], vertices[b]))

    new_faces: list[Face] = []

    for face in mesh.faces:
        a, b, c = face
        edge_ab = _edge_key(a, b)
        edge_bc = _edge_key(b, c)
        edge_ca = _edge_key(c, a)
        has_ab = edge_ab in midpoint_indices
        has_bc = edge_bc in midpoint_indices
        has_ca = edge_ca in midpoint_indices
        split_count = sum((has_ab, has_bc, has_ca))

        if split_count == 0:
            new_faces.append(face)
            continue

        midpoint_ab = midpoint_indices.get(edge_ab)
        midpoint_bc = midpoint_indices.get(edge_bc)
        midpoint_ca = midpoint_indices.get(edge_ca)

        if split_count == 1:
            if has_ab:
                assert midpoint_ab is not None
                new_faces.extend([(a, midpoint_ab, c), (midpoint_ab, b, c)])
            elif has_bc:
                assert midpoint_bc is not None
                new_faces.extend([(b, midpoint_bc, a), (midpoint_bc, c, a)])
            else:
                assert midpoint_ca is not None
                new_faces.extend([(c, midpoint_ca, b), (midpoint_ca, a, b)])
            continue

        if split_count == 2:
            if has_ab and has_ca:
                assert midpoint_ab is not None and midpoint_ca is not None
                new_faces.extend(
                    [
                        (a, midpoint_ab, midpoint_ca),
                        (midpoint_ab, b, c),
                        (midpoint_ab, c, midpoint_ca),
                    ]
                )
            elif has_ab and has_bc:
                assert midpoint_ab is not None and midpoint_bc is not None
                new_faces.extend(
                    [
                        (b, midpoint_bc, midpoint_ab),
                        (midpoint_bc, c, a),
                        (midpoint_bc, a, midpoint_ab),
                    ]
                )
            else:
                assert midpoint_bc is not None and midpoint_ca is not None
                new_faces.extend(
                    [
                        (c, midpoint_ca, midpoint_bc),
                        (midpoint_ca, a, b),
                        (midpoint_ca, b, midpoint_bc),
                    ]
                )
            continue

        assert midpoint_ab is not None and midpoint_bc is not None and midpoint_ca is not None
        new_faces.extend(
            [
                (a, midpoint_ab, midpoint_ca),
                (b, midpoint_bc, midpoint_ab),
                (c, midpoint_ca, midpoint_bc),
                (midpoint_ab, midpoint_bc, midpoint_ca),
            ]
        )

    return _cleanup_mesh(Mesh(vertices, new_faces, source=mesh.source)), len(split_edges)


def split_long_edges(mesh: Mesh, target_length: float, factor: float = 4.0 / 3.0) -> tuple[Mesh, int]:
    threshold = factor * target_length
    split_edges = {
        edge
        for edge in _unique_edges(mesh.faces)
        if _distance(mesh.vertices[edge[0]], mesh.vertices[edge[1]]) > threshold
    }
    return split_selected_edges(mesh, split_edges)


def _collapse_is_safe(
    vertices: list[Vec3],
    faces: list[Face],
    edge: tuple[int, int],
    replacement: Vec3,
    area_epsilon: float,
) -> bool:
    a, b = edge
    for face in faces:
        contains_a = a in face
        contains_b = b in face
        if contains_a and contains_b:
            continue
        if not contains_a and not contains_b:
            continue

        candidate = tuple(a if index == b else index for index in face)
        if len(set(candidate)) != 3:
            return False

        old_position = vertices[a]
        vertices[a] = replacement
        new_area = _area(vertices, candidate)
        vertices[a] = old_position
        if new_area <= area_epsilon:
            return False

    return True


def collapse_short_edges(
    mesh: Mesh,
    target_length: float,
    factor: float = 4.0 / 5.0,
    preserve_boundary: bool = True,
) -> tuple[Mesh, int]:
    threshold = factor * target_length
    vertices = list(mesh.vertices)
    faces = list(mesh.faces)
    edge_to_faces = _edge_faces(faces)
    boundary_edges = {edge for edge, incident in edge_to_faces.items() if len(incident) == 1}
    neighbor_sets = _neighbors(faces, len(vertices))
    area_epsilon = _area_epsilon(vertices)

    edges = sorted(
        (
            (_distance(vertices[a], vertices[b]), a, b)
            for a, b in _unique_edges(faces)
        ),
        key=lambda item: item[0],
    )
    parent = list(range(len(vertices)))
    used: set[int] = set()
    collapses = 0

    for length, a, b in edges:
        if length >= threshold:
            break
        key = _edge_key(a, b)
        if preserve_boundary and key in boundary_edges:
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


def collapse_edges_by_thresholds(
    mesh: Mesh,
    edge_thresholds: dict[tuple[int, int], float],
    preserve_boundary: bool = True,
) -> tuple[Mesh, int]:
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
            (_distance(vertices[a], vertices[b]), a, b, threshold)
            for (a, b), threshold in edge_thresholds.items()
            if a < len(vertices) and b < len(vertices)
        ),
        key=lambda item: item[0],
    )

    for length, a, b, threshold in edges:
        if length >= threshold:
            continue
        key = _edge_key(a, b)
        if preserve_boundary and key in boundary_edges:
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


def _valence_error(neighbor_sets: list[set[int]], boundary: set[int]) -> int:
    error = 0
    for vertex, neighbors in enumerate(neighbor_sets):
        target = 4 if vertex in boundary else 6
        error += (len(neighbors) - target) ** 2
    return error


def _single_valence_error(vertex: int, valence: int, boundary: set[int]) -> int:
    target = 4 if vertex in boundary else 6
    return (valence - target) ** 2


def flip_edges(mesh: Mesh) -> tuple[Mesh, int]:
    faces = list(mesh.faces)
    vertices = list(mesh.vertices)
    existing_edges = _unique_edges(faces)
    neighbor_sets = _neighbors(faces, len(vertices))
    boundary = _boundary_vertices(faces)
    area_epsilon = _area_epsilon(vertices)
    used_faces: set[int] = set()
    flips = 0

    for edge, incident in list(_edge_faces(faces).items()):
        if len(incident) != 2:
            continue
        u, v = edge
        first_index, second_index = incident
        if first_index in used_faces or second_index in used_faces:
            continue
        first = faces[first_index]
        second = faces[second_index]
        if u not in first or v not in first or u not in second or v not in second:
            continue
        opposite_first = [index for index in first if index not in edge]
        opposite_second = [index for index in second if index not in edge]
        if len(opposite_first) != 1 or len(opposite_second) != 1:
            continue
        a = opposite_first[0]
        b = opposite_second[0]
        if a == b or _edge_key(a, b) in existing_edges:
            continue

        old_mesh = Mesh(vertices, [first, second])
        old_min_angle = min(triangle_quality(old_mesh, face).min_angle for face in old_mesh.faces)
        proposed_first = (a, b, u)
        proposed_second = (b, a, v)
        if _area(vertices, proposed_first) <= area_epsilon:
            continue
        if _area(vertices, proposed_second) <= area_epsilon:
            continue

        before_error = sum(
            _single_valence_error(vertex, len(neighbor_sets[vertex]), boundary)
            for vertex in (u, v, a, b)
        )
        after_error = (
            _single_valence_error(u, len(neighbor_sets[u]) - 1, boundary)
            + _single_valence_error(v, len(neighbor_sets[v]) - 1, boundary)
            + _single_valence_error(a, len(neighbor_sets[a]) + 1, boundary)
            + _single_valence_error(b, len(neighbor_sets[b]) + 1, boundary)
        )

        candidate_mesh = Mesh(vertices, [proposed_first, proposed_second])
        new_min_angle = min(
            triangle_quality(candidate_mesh, face).min_angle for face in candidate_mesh.faces
        )

        if after_error < before_error and new_min_angle + 1e-9 >= old_min_angle:
            existing_edges.remove(edge)
            existing_edges.add(_edge_key(a, b))
            faces[first_index] = proposed_first
            faces[second_index] = proposed_second
            neighbor_sets[u].discard(v)
            neighbor_sets[v].discard(u)
            neighbor_sets[a].add(b)
            neighbor_sets[b].add(a)
            used_faces.update((first_index, second_index))
            flips += 1

    return _cleanup_mesh(Mesh(vertices, faces, source=mesh.source)), flips


def smooth_vertices(mesh: Mesh, amount: float = 0.2, preserve_boundary: bool = True) -> Mesh:
    vertices = list(mesh.vertices)
    faces = list(mesh.faces)
    neighbors = _neighbors(faces, len(vertices))
    boundary = _boundary_vertices(faces) if preserve_boundary else set()
    new_vertices: list[Vec3] = []

    for index, vertex in enumerate(vertices):
        if index in boundary or not neighbors[index]:
            new_vertices.append(vertex)
            continue
        average = _mul(
            tuple(
                sum(vertices[neighbor][axis] for neighbor in neighbors[index])
                for axis in range(3)
            ),
            1.0 / len(neighbors[index]),
        )
        new_vertices.append(_add(_mul(vertex, 1.0 - amount), _mul(average, amount)))

    return _cleanup_mesh(Mesh(new_vertices, faces, source=mesh.source))


def _closest_point_on_triangle(point: Vec3, a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    ab = _sub(b, a)
    ac = _sub(c, a)
    ap = _sub(point, a)
    d1 = _dot(ab, ap)
    d2 = _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a

    bp = _sub(point, b)
    d3 = _dot(ab, bp)
    d4 = _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return _add(a, _mul(ab, v))

    cp = _sub(point, c)
    d5 = _dot(ab, cp)
    d6 = _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return _add(a, _mul(ac, w))

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return _add(b, _mul(_sub(c, b), w))

    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    return _add(a, _add(_mul(ab, v), _mul(ac, w)))


def project_to_surface(
    mesh: Mesh,
    reference: Mesh,
    *,
    preserve_boundary: bool = True,
) -> Mesh:
    """Project vertices to the closest point on a reference triangle mesh."""
    boundary = _boundary_vertices(mesh.faces) if preserve_boundary else set()
    reference_triangles = [
        (
            reference.vertices[face[0]],
            reference.vertices[face[1]],
            reference.vertices[face[2]],
        )
        for face in reference.faces
    ]
    projected_vertices: list[Vec3] = []

    for index, vertex in enumerate(mesh.vertices):
        if index in boundary:
            projected_vertices.append(vertex)
            continue

        best_point = vertex
        best_distance = float("inf")
        for a, b, c in reference_triangles:
            candidate = _closest_point_on_triangle(vertex, a, b, c)
            distance = _squared_distance(vertex, candidate)
            if distance < best_distance:
                best_distance = distance
                best_point = candidate
        projected_vertices.append(best_point)

    return _cleanup_mesh(Mesh(projected_vertices, mesh.faces, source=mesh.source))


def uniform_remesh(
    mesh: Mesh,
    *,
    target_length: Optional[float] = None,
    iterations: int = 5,
    do_collapse: bool = True,
    do_flip: bool = True,
    do_smooth: bool = True,
    smooth_amount: float = 0.2,
    project: bool = True,
    reference_mesh: Optional[Mesh] = None,
) -> RemeshResult:
    if target_length is None:
        target_length = estimate_target_length(mesh)

    current = _cleanup_mesh(mesh)
    reference = reference_mesh if reference_mesh else current
    stats: list[RemeshIterationStats] = []

    for iteration in range(1, iterations + 1):
        current, splits = split_long_edges(current, target_length)
        collapses = 0
        if do_collapse:
            current, collapses = collapse_short_edges(current, target_length)
        flips = 0
        if do_flip:
            current, flips = flip_edges(current)
        if do_smooth:
            current = smooth_vertices(current, amount=smooth_amount)
            if project:
                current = project_to_surface(current, reference)
        stats.append(
            RemeshIterationStats(
                iteration=iteration,
                splits=splits,
                collapses=collapses,
                flips=flips,
                vertices=len(current.vertices),
                faces=len(current.faces),
            )
        )

    return RemeshResult(mesh=current, target_length=target_length, stats=stats)


def adaptive_remesh(
    mesh: Mesh,
    *,
    epsilon: float = 0.002,
    min_length: float = 0.025,
    max_length: float = 0.075,
    iterations: int = 5,
) -> RemeshResult:
    current = _cleanup_mesh(mesh)
    stats: list[RemeshIterationStats] = []

    for iteration in range(1, iterations + 1):
        sizes, _ = sizing_field(
            current,
            epsilon=epsilon,
            min_length=min_length,
            max_length=max_length,
        )
        split_edges: set[tuple[int, int]] = set()
        for edge in _unique_edges(current.faces):
            a, b = edge
            target = min(sizes[a], sizes[b])
            if _distance(current.vertices[a], current.vertices[b]) > (4.0 / 3.0) * target:
                split_edges.add(edge)
        current, splits = split_selected_edges(current, split_edges)

        sizes, _ = sizing_field(
            current,
            epsilon=epsilon,
            min_length=min_length,
            max_length=max_length,
        )
        thresholds: dict[tuple[int, int], float] = {}
        for edge in _unique_edges(current.faces):
            a, b = edge
            thresholds[edge] = (4.0 / 5.0) * min(sizes[a], sizes[b])
        current, collapses = collapse_edges_by_thresholds(current, thresholds)

        stats.append(
            RemeshIterationStats(
                iteration=iteration,
                splits=splits,
                collapses=collapses,
                flips=0,
                vertices=len(current.vertices),
                faces=len(current.faces),
            )
        )

    return RemeshResult(mesh=current, target_length=0.0, stats=stats)


def format_remesh_stats(stats: list[RemeshIterationStats]) -> str:
    if not stats:
        return ""
    columns = [
        ("iter", lambda s: str(s.iteration)),
        ("splits", lambda s: str(s.splits)),
        ("collapses", lambda s: str(s.collapses)),
        ("flips", lambda s: str(s.flips)),
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
