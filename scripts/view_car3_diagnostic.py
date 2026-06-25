from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polyscope as ps


ROOT = Path(__file__).resolve().parents[1]


def _read_colored_ascii_ply(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with path.open("r", encoding="utf-8") as handle:
        first = handle.readline().strip()
        if first != "ply":
            raise ValueError(f"{path} is not a PLY file")

        vertex_count = None
        face_count = None
        while True:
            line = handle.readline()
            if not line:
                raise ValueError(f"{path} has no end_header")
            line = line.strip()
            if line.startswith("element vertex"):
                vertex_count = int(line.split()[-1])
            elif line.startswith("element face"):
                face_count = int(line.split()[-1])
            elif line == "end_header":
                break

        if vertex_count is None or face_count is None:
            raise ValueError(f"{path} is missing vertex or face count")

        vertices = []
        for _ in range(vertex_count):
            x, y, z = (float(value) for value in handle.readline().split()[:3])
            vertices.append((x, y, z))

        faces = []
        colors = []
        for _ in range(face_count):
            parts = handle.readline().split()
            degree = int(parts[0])
            if degree != 3:
                raise ValueError(f"{path} contains a non-triangle face")
            faces.append(tuple(int(value) for value in parts[1:4]))
            colors.append(tuple(int(value) / 255.0 for value in parts[4:7]))

    return (
        np.asarray(vertices, dtype=float),
        np.asarray(faces, dtype=np.int32),
        np.asarray(colors, dtype=float),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="View car3 diagnostic patch/timeline PLY files.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "car3_diagnostic",
        help="Diagnostic output directory.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--region", type=int, choices=[1, 2, 3, 4], help="Region id to view.")
    group.add_argument("--all", action="store_true", help="View all region timelines.")
    parser.add_argument("--step", type=int, choices=[0, 1, 3, 6, 10], help="View one step patch instead of the timeline.")
    parser.add_argument("--dry-run", action="store_true", help="Parse files and print counts without opening Polyscope.")
    return parser


def _paths(args: argparse.Namespace) -> list[Path]:
    regions = [1, 2, 3, 4] if args.all else [args.region]
    result = []
    for region in regions:
        if args.step is None:
            result.append(args.out_dir / "regions" / f"region_{region:02d}_timeline.ply")
        else:
            result.append(args.out_dir / "regions" / f"region_{region:02d}_step_{args.step:02d}_patch.ply")
    return result


def main() -> int:
    args = _build_parser().parse_args()
    paths = _paths(args)

    loaded = []
    for path in paths:
        vertices, faces, colors = _read_colored_ascii_ply(path)
        loaded.append((path, vertices, faces, colors))
        print(f"{path}: V={len(vertices)}, F={len(faces)}")

    if args.dry_run:
        return 0

    ps.init()
    ps.set_ground_plane_mode("none")
    for path, vertices, faces, colors in loaded:
        mesh = ps.register_surface_mesh(
            path.stem,
            vertices,
            faces,
            edge_color=(0.04, 0.04, 0.04),
            edge_width=0.75,
            smooth_shade=False,
        )
        mesh.set_material("clay")
        mesh.add_color_quantity("diagnostic colors", colors, defined_on="faces", enabled=True)

    print("Legend: gray=good, red=needle, orange=low_aspect, purple=cap, yellow=tracked local face.")
    ps.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
