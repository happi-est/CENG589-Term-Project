from __future__ import annotations

from pathlib import Path

from meshfix.io import Mesh
from meshfix.quality import QUALITY_COLORS, classify_mesh_faces, count_labels


def write_quality_ply(
    mesh: Mesh,
    path: str | Path,
    *,
    needle_angle_deg: float = 5.0,
    cap_angle_deg: float = 175.0,
    low_aspect_threshold: float = 0.05,
) -> dict[str, int]:
    """Export a PLY with per-face colors based on triangle quality."""
    path = Path(path)
    labels = classify_mesh_faces(
        mesh,
        needle_angle_deg=needle_angle_deg,
        cap_angle_deg=cap_angle_deg,
        low_aspect_threshold=low_aspect_threshold,
    )
    counts = count_labels(labels)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("ply\n")
        handle.write("format ascii 1.0\n")
        handle.write("comment quality legend: good=gray needle=red low_aspect=orange cap=purple zero_area=black\n")
        handle.write(f"element vertex {len(mesh.vertices)}\n")
        handle.write("property float x\n")
        handle.write("property float y\n")
        handle.write("property float z\n")
        handle.write(f"element face {len(mesh.faces)}\n")
        handle.write("property list uchar int vertex_indices\n")
        handle.write("property uchar red\n")
        handle.write("property uchar green\n")
        handle.write("property uchar blue\n")
        handle.write("property uchar alpha\n")
        handle.write("end_header\n")
        for x, y, z in mesh.vertices:
            handle.write(f"{x:.12g} {y:.12g} {z:.12g}\n")
        for face, label in zip(mesh.faces, labels):
            red, green, blue, alpha = QUALITY_COLORS[label]
            handle.write(
                f"3 {face[0]} {face[1]} {face[2]} {red} {green} {blue} {alpha}\n"
            )

    return counts

