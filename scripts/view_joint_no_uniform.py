from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import polyscope as ps


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meshfix.io import Mesh, read_off
from meshfix.quality import QUALITY_COLORS, classify_mesh_faces, count_labels


VARIANTS = {
    "input": ROOT / "submission" / "EsadMazi_CENG589_Project" / "inputs" / "joint_input.off",
    "reference": ROOT / "submission" / "EsadMazi_CENG589_Project" / "inputs" / "joint_output.off",
    "old_uniform_final": ROOT / "outputs" / "meshes" / "joint_adaptive_final.off",
    "direct_adaptive_cleanup": ROOT
    / "outputs"
    / "meshes"
    / "joint_input_direct_adaptive_cleanup_i8.off",
}


def _arrays(mesh: Mesh) -> tuple[np.ndarray, np.ndarray]:
    return np.asarray(mesh.vertices, dtype=float), np.asarray(mesh.faces, dtype=np.int32)


def _normalize(vertices: np.ndarray, center: np.ndarray, scale: float, column: int, gap: float) -> np.ndarray:
    return (vertices - center) / scale + np.array([column * gap, 0.0, 0.0])


def _quality_colors(labels: list[str]) -> np.ndarray:
    return np.asarray(
        [[channel / 255.0 for channel in QUALITY_COLORS[label][:3]] for label in labels],
        dtype=float,
    )


def _bad_centroids(vertices: np.ndarray, faces: np.ndarray, labels: list[str]) -> tuple[np.ndarray, np.ndarray]:
    points = []
    colors = []
    for face, label in zip(faces, labels):
        if label == "good":
            continue
        points.append(vertices[face].mean(axis=0))
        colors.append([channel / 255.0 for channel in QUALITY_COLORS[label][:3]])
    if not points:
        return np.zeros((0, 3)), np.zeros((0, 3))
    return np.asarray(points, dtype=float), np.asarray(colors, dtype=float)


def _register_variant(
    name: str,
    mesh: Mesh,
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    mode: str,
    marker_radius: float,
) -> None:
    surface = ps.register_surface_mesh(
        name,
        vertices,
        faces,
        color=(0.72, 0.78, 0.86),
        edge_color=(0.04, 0.04, 0.04),
        edge_width=0.75,
        smooth_shade=False,
    )
    surface.set_material("clay")

    labels = classify_mesh_faces(mesh)
    counts = count_labels(labels)
    if mode == "quality":
        surface.add_color_quantity("triangle quality", _quality_colors(labels), defined_on="faces", enabled=True)
        points, colors = _bad_centroids(vertices, faces, labels)
        if len(points) > 0:
            cloud = ps.register_point_cloud(f"{name} bad markers", points)
            cloud.set_point_render_mode("sphere")
            cloud.set_radius(marker_radius, relative=True)
            cloud.add_color_quantity("bad type", colors, enabled=True)
            cloud.set_material("wax")

    bad = sum(value for label, value in counts.items() if label != "good")
    print(
        f"{name}: V={len(mesh.vertices)}, F={len(mesh.faces)}, bad={bad} "
        f"(needle={counts['needle']}, low_aspect={counts['low_aspect']}, cap={counts['cap']})"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="View joint input, reference, old uniform-based final, and no-uniform candidate side by side.",
    )
    parser.add_argument(
        "--mode",
        choices=["quality", "wireframe"],
        default="quality",
        help="quality colors bad triangles; wireframe only compares shape.",
    )
    parser.add_argument("--marker-radius", type=float, default=0.006)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    meshes = [(name, read_off(path)) for name, path in VARIANTS.items()]
    all_vertices = np.vstack([np.asarray(mesh.vertices, dtype=float) for _, mesh in meshes])
    center = (all_vertices.min(axis=0) + all_vertices.max(axis=0)) * 0.5
    scale = np.max(all_vertices.max(axis=0) - all_vertices.min(axis=0))
    if scale == 0:
        scale = 1.0

    ps.init()
    ps.set_ground_plane_mode("none")

    offset = -(len(meshes) - 1) / 2.0
    for column, (name, mesh) in enumerate(meshes):
        vertices, faces = _arrays(mesh)
        vertices = _normalize(vertices, center, scale, column + offset, gap=1.25)
        _register_variant(
            name,
            mesh,
            vertices,
            faces,
            mode=args.mode,
            marker_radius=args.marker_radius,
        )

    print()
    print("Order: input | instructor reference | old uniform-based final | no-uniform candidate")
    print("Legend: gray=good, red=needle, orange=low_aspect, purple=cap, black=zero_area")
    ps.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
