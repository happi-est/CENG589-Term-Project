from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STEPS = [0, 1, 3, 6, 10]


def _read_colored_ascii_ply(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with path.open("r", encoding="utf-8") as handle:
        if handle.readline().strip() != "ply":
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

        vertices = np.array(
            [[float(value) for value in handle.readline().split()[:3]] for _ in range(vertex_count)],
            dtype=float,
        )
        faces = []
        colors = []
        for _ in range(face_count):
            parts = handle.readline().split()
            if int(parts[0]) != 3:
                raise ValueError(f"{path} contains a non-triangle face")
            faces.append([int(value) for value in parts[1:4]])
            colors.append([int(value) / 255.0 for value in parts[4:7]])
    return vertices, np.asarray(faces, dtype=np.int32), np.asarray(colors, dtype=float)


def _project_vertices(vertices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centered = vertices - vertices.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    projected = centered @ vh[:2].T
    depth = centered @ vh[2].T if vh.shape[0] > 2 else np.zeros(len(vertices))
    return projected, depth


def _draw_patch(ax, path: Path, title: str) -> None:
    vertices, faces, colors = _read_colored_ascii_ply(path)
    projected, depth = _project_vertices(vertices)
    face_order = np.argsort(depth[faces].mean(axis=1))
    polys = [projected[faces[index]] for index in face_order]
    face_colors = [colors[index] for index in face_order]

    collection = PolyCollection(polys, facecolors=face_colors, edgecolors=(0.02, 0.02, 0.02), linewidths=0.18)
    ax.add_collection(collection)
    ax.autoscale_view()
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title, fontsize=9)
    ax.axis("off")


def _load_region_summary(csv_path: Path) -> dict[int, dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[int, dict[str, str]] = {}
    for row in rows:
        if row["step"] == "0":
            result[int(row["region_id"])] = row
    return result


def _render_region(region_id: int, out_dir: Path, figure_dir: Path, steps: list[int]) -> Path:
    fig, axes = plt.subplots(1, len(steps), figsize=(10.5, 2.2), dpi=220)
    if len(steps) == 1:
        axes = [axes]

    for ax, step in zip(axes, steps):
        path = out_dir / "regions" / f"region_{region_id:02d}_step_{step:02d}_patch.ply"
        _draw_patch(ax, path, f"step {step}")

    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.25, w_pad=0.15)
    output = figure_dir / f"fig09_car3_region_{region_id:02d}_timeline.png"
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output


def _render_overview(out_dir: Path, figure_dir: Path, steps: list[int]) -> Path:
    summary = _load_region_summary(out_dir / "car3_region_tracking.csv")
    fig, axes = plt.subplots(4, len(steps), figsize=(10.5, 7.6), dpi=220)

    for row, region_id in enumerate([1, 2, 3, 4]):
        for col, step in enumerate(steps):
            path = out_dir / "regions" / f"region_{region_id:02d}_step_{step:02d}_patch.ply"
            title = f"step {step}" if row == 0 else ""
            _draw_patch(axes[row, col], path, title)
        seed = summary[region_id]
        label = f"R{region_id}: {seed['seed_label']} face {seed['seed_face_index']}"
        axes[row, 0].text(
            -0.03,
            0.5,
            label,
            rotation=90,
            va="center",
            ha="right",
            transform=axes[row, 0].transAxes,
            fontsize=8,
        )

    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.35, w_pad=0.15, h_pad=0.25)
    output = figure_dir / "fig09_car3_diagnostic_overview.png"
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render car3 diagnostic PLY patches as report PNG figures.")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "car3_diagnostic")
    parser.add_argument("--figure-dir", type=Path, default=ROOT / "report" / "figures")
    parser.add_argument("--steps", default="0,1,3,6,10")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    steps = [int(item.strip()) for item in args.steps.split(",") if item.strip()]
    outputs = [_render_overview(args.out_dir, args.figure_dir, steps)]
    outputs.extend(_render_region(region_id, args.out_dir, args.figure_dir, steps) for region_id in [1, 2, 3, 4])
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
