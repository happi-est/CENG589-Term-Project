from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import polyscope as ps


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meshfix.io import read_off

INPUT_DIR = ROOT / "submission" / "EsadMazi_CENG589_Project" / "inputs" / "cars"
OUTPUT_DIR = ROOT / "outputs" / "meshes"


def _load_vertices(path: Path) -> tuple[np.ndarray, np.ndarray]:
    mesh = read_off(path)
    return np.asarray(mesh.vertices, dtype=float), np.asarray(mesh.faces, dtype=np.int32)


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


def _register_mesh(name: str, vertices: np.ndarray, faces: np.ndarray, color: tuple[float, float, float]) -> None:
    surface = ps.register_surface_mesh(
        name,
        vertices,
        faces,
        color=color,
        edge_width=1.0,
        edge_color=(0.03, 0.03, 0.03),
        smooth_shade=False,
    )
    surface.set_material("clay")


def _register_car(car_id: int, row: int) -> None:
    input_path = INPUT_DIR / f"car{car_id}.off"
    cleanup_path = OUTPUT_DIR / f"car{car_id}_targeted_cleanup.off"
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    if not cleanup_path.exists():
        raise FileNotFoundError(cleanup_path)

    input_vertices, input_faces = _load_vertices(input_path)
    cleanup_vertices, cleanup_faces = _load_vertices(cleanup_path)
    input_vertices, cleanup_vertices = _pair_transform(
        input_vertices,
        cleanup_vertices,
        row=row,
        col_gap=1.45,
        row_gap=1.45,
    )

    _register_mesh(f"car{car_id} input", input_vertices, input_faces, (0.72, 0.80, 0.90))
    _register_mesh(f"car{car_id} targeted cleanup", cleanup_vertices, cleanup_faces, (0.70, 0.86, 0.72))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="View car input/targeted-cleanup meshes side by side with visible wireframes.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--car", type=int, choices=[1, 2, 3, 4], help="Car id to view.")
    group.add_argument("--all", action="store_true", help="View all four car pairs in one scene.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    ps.init()
    ps.set_ground_plane_mode("none")

    car_ids = [1, 2, 3, 4] if args.all else [args.car]
    for row, car_id in enumerate(car_ids):
        _register_car(car_id, row)

    print("Left column: original input mesh")
    print("Right column: targeted cleanup mesh")
    print("Wireframe is enabled with black mesh edges.")
    ps.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
