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


INPUT_DIR = ROOT / "submission" / "EsadMazi_CENG589_Project" / "inputs" / "cars"
OUTPUT_DIR = ROOT / "outputs" / "meshes"


def _mesh_arrays(mesh: Mesh) -> tuple[np.ndarray, np.ndarray]:
    return np.asarray(mesh.vertices, dtype=float), np.asarray(mesh.faces, dtype=np.int32)


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


def _pair_transform(
    input_vertices: np.ndarray,
    cleanup_vertices: np.ndarray,
    *,
    row: int,
    col_gap: float,
    row_gap: float,
) -> tuple[np.ndarray, np.ndarray]:
    combined = np.vstack([input_vertices, cleanup_vertices])
    center = (combined.min(axis=0) + combined.max(axis=0)) * 0.5
    scale = np.max(combined.max(axis=0) - combined.min(axis=0))
    if scale == 0:
        scale = 1.0

    input_out = (input_vertices - center) / scale
    cleanup_out = (cleanup_vertices - center) / scale
    input_out += np.array([-col_gap * 0.5, -row * row_gap, 0.0])
    cleanup_out += np.array([col_gap * 0.5, -row * row_gap, 0.0])
    return input_out, cleanup_out


def _register_quality_mesh(
    name: str,
    vertices: np.ndarray,
    faces: np.ndarray,
    labels: list[str],
    *,
    show_markers: bool,
    marker_radius: float,
) -> dict[str, int]:
    surface = ps.register_surface_mesh(
        name,
        vertices,
        faces,
        edge_width=0.55,
        edge_color=(0.04, 0.04, 0.04),
        smooth_shade=False,
    )
    surface.set_material("clay")
    surface.add_color_quantity(
        "triangle quality",
        _quality_colors(labels),
        defined_on="faces",
        enabled=True,
    )

    counts = count_labels(labels)
    if show_markers:
        points, colors = _bad_centroids(vertices, faces, labels)
        if len(points) > 0:
            cloud = ps.register_point_cloud(f"{name} bad triangle markers", points)
            cloud.set_point_render_mode("sphere")
            cloud.set_radius(marker_radius, relative=True)
            cloud.add_color_quantity("bad type", colors, enabled=True)
            cloud.set_material("wax")
    return counts


def _register_car(car_id: int, row: int, *, show_markers: bool, marker_radius: float) -> None:
    input_mesh = read_off(INPUT_DIR / f"car{car_id}.off")
    cleanup_mesh = read_off(OUTPUT_DIR / f"car{car_id}_targeted_cleanup.off")

    input_vertices, input_faces = _mesh_arrays(input_mesh)
    cleanup_vertices, cleanup_faces = _mesh_arrays(cleanup_mesh)
    input_vertices, cleanup_vertices = _pair_transform(
        input_vertices,
        cleanup_vertices,
        row=row,
        col_gap=1.45,
        row_gap=1.45,
    )

    input_labels = classify_mesh_faces(input_mesh)
    cleanup_labels = classify_mesh_faces(cleanup_mesh)
    input_counts = _register_quality_mesh(
        f"car{car_id} input quality",
        input_vertices,
        input_faces,
        input_labels,
        show_markers=show_markers,
        marker_radius=marker_radius,
    )
    cleanup_counts = _register_quality_mesh(
        f"car{car_id} targeted cleanup quality",
        cleanup_vertices,
        cleanup_faces,
        cleanup_labels,
        show_markers=show_markers,
        marker_radius=marker_radius,
    )

    print(
        f"car{car_id}: bad triangles "
        f"{sum(v for k, v in input_counts.items() if k != 'good')} -> "
        f"{sum(v for k, v in cleanup_counts.items() if k != 'good')}"
    )
    print(
        "       input   "
        f"needle={input_counts['needle']}, low_aspect={input_counts['low_aspect']}, "
        f"cap={input_counts['cap']}, zero_area={input_counts['zero_area']}"
    )
    print(
        "       cleanup "
        f"needle={cleanup_counts['needle']}, low_aspect={cleanup_counts['low_aspect']}, "
        f"cap={cleanup_counts['cap']}, zero_area={cleanup_counts['zero_area']}"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare original and targeted-cleanup car meshes with bad triangles highlighted.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--car", type=int, choices=[1, 2, 3, 4], help="Car id to view.")
    group.add_argument("--all", action="store_true", help="View all four car pairs in one scene.")
    parser.add_argument(
        "--no-markers",
        action="store_true",
        help="Only color faces; do not draw centroid markers on bad triangles.",
    )
    parser.add_argument(
        "--marker-radius",
        type=float,
        default=0.004,
        help="Relative radius for bad-triangle markers.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    ps.init()
    ps.set_ground_plane_mode("none")

    car_ids = [1, 2, 3, 4] if args.all else [args.car]
    for row, car_id in enumerate(car_ids):
        _register_car(
            car_id,
            row,
            show_markers=not args.no_markers,
            marker_radius=args.marker_radius,
        )

    print()
    print("Left column: original input mesh")
    print("Right column: targeted cleanup mesh")
    print("Legend: gray=good, red=needle, orange=low_aspect, purple=cap, black=zero_area")
    print("Bright dots mark bad triangle centroids so tiny triangles are visible at full-model scale.")
    ps.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
