from __future__ import annotations

from dataclasses import dataclass

from meshfix.io import Mesh
from meshfix.remesh import _edge_faces


@dataclass
class TopologySummary:
    name: str
    vertex_count: int
    face_count: int
    edge_count: int
    boundary_edge_count: int
    nonmanifold_edge_count: int
    euler_characteristic: int


def analyze_topology(mesh: Mesh) -> TopologySummary:
    edge_to_faces = _edge_faces(mesh.faces)
    return TopologySummary(
        name=mesh.source.name if mesh.source else "<memory>",
        vertex_count=len(mesh.vertices),
        face_count=len(mesh.faces),
        edge_count=len(edge_to_faces),
        boundary_edge_count=sum(1 for incident in edge_to_faces.values() if len(incident) == 1),
        nonmanifold_edge_count=sum(1 for incident in edge_to_faces.values() if len(incident) > 2),
        euler_characteristic=len(mesh.vertices) - len(edge_to_faces) + len(mesh.faces),
    )


def format_topology_table(summaries: list[TopologySummary]) -> str:
    columns = [
        ("mesh", lambda s: s.name),
        ("V", lambda s: str(s.vertex_count)),
        ("F", lambda s: str(s.face_count)),
        ("E", lambda s: str(s.edge_count)),
        ("boundary", lambda s: str(s.boundary_edge_count)),
        ("nonmanifold", lambda s: str(s.nonmanifold_edge_count)),
        ("euler", lambda s: str(s.euler_characteristic)),
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

