from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meshfix.cleanup import _bad_face_operations, _collapse_selected_edges
from meshfix.io import Mesh, read_off, write_off
from meshfix.quality import (
    QUALITY_COLORS,
    analyze_mesh,
    classify_mesh_faces,
    count_labels,
    triangle_quality,
)
from meshfix.remesh import split_selected_edges


TRACKED_FACE_COLOR = (255, 230, 35, 255)


@dataclass
class StepRecord:
    step: int
    mesh: Mesh
    bad_before: int
    collapse_edges: int
    split_edges: int
    collapses: int
    splits: int


@dataclass
class CandidateRegion:
    region_id: int
    face_index: int
    reason: str
    seed_label: str
    seed_centroid: np.ndarray
    seed_min_angle: float
    seed_max_angle: float
    seed_aspect_ratio: float
    patch_radius: float


@dataclass
class StepCache:
    labels: list[str]
    qualities: list
    centroids: np.ndarray


def _bbox_diagonal(mesh: Mesh) -> float:
    vertices = np.asarray(mesh.vertices, dtype=float)
    extent = vertices.max(axis=0) - vertices.min(axis=0)
    return float(np.linalg.norm(extent))


def _face_centroids(mesh: Mesh) -> np.ndarray:
    vertices = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    return vertices[faces].mean(axis=1)


def _quality_cache(mesh: Mesh) -> tuple[list[str], list]:
    labels = classify_mesh_faces(mesh)
    qualities = [triangle_quality(mesh, face) for face in mesh.faces]
    return labels, qualities


def _bad_count(labels: list[str]) -> int:
    return sum(1 for label in labels if label != "good")


def _run_cleanup_timeline(
    mesh: Mesh,
    *,
    iterations: int,
    needle_angle_deg: float,
    cap_angle_deg: float,
    low_aspect_threshold: float,
) -> list[StepRecord]:
    records = [
        StepRecord(
            step=0,
            mesh=mesh,
            bad_before=analyze_mesh(mesh).bad_triangle_count,
            collapse_edges=0,
            split_edges=0,
            collapses=0,
            splits=0,
        )
    ]
    current = mesh

    for step in range(1, iterations + 1):
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
            records.append(
                StepRecord(
                    step=step,
                    mesh=current,
                    bad_before=summary.bad_triangle_count,
                    collapse_edges=0,
                    split_edges=0,
                    collapses=0,
                    splits=0,
                )
            )
            break

        after_collapse, collapses = _collapse_selected_edges(current, collapse_edges)
        _, split_edges_after_collapse = _bad_face_operations(
            after_collapse,
            needle_angle_deg=needle_angle_deg,
            cap_angle_deg=cap_angle_deg,
            low_aspect_threshold=low_aspect_threshold,
        )
        after_split, splits = split_selected_edges(after_collapse, split_edges_after_collapse)
        current = Mesh(after_split.vertices, after_split.faces, source=mesh.source)
        records.append(
            StepRecord(
                step=step,
                mesh=current,
                bad_before=summary.bad_triangle_count,
                collapse_edges=len(collapse_edges),
                split_edges=len(split_edges_after_collapse),
                collapses=collapses,
                splits=splits,
            )
        )

    return records


def _nearest_face_index(centroids: np.ndarray, point: np.ndarray) -> int:
    distances = np.linalg.norm(centroids - point, axis=1)
    return int(np.argmin(distances))


def _patch_face_indices(
    centroids: np.ndarray,
    point: np.ndarray,
    *,
    radius: float,
    min_faces: int,
    max_faces: int,
) -> list[int]:
    distances = np.linalg.norm(centroids - point, axis=1)
    inside = np.flatnonzero(distances <= radius)
    if len(inside) < min_faces:
        inside = np.argsort(distances)[:min(min_faces, len(distances))]
    if len(inside) > max_faces:
        order = np.argsort(distances[inside])[:max_faces]
        inside = inside[order]
    return [int(index) for index in sorted(inside)]


def _patch_metrics(
    mesh: Mesh,
    labels: list[str],
    qualities: list,
    centroids: np.ndarray,
    region: CandidateRegion,
    *,
    min_faces: int,
    max_faces: int,
) -> dict[str, str | int | float]:
    nearest = _nearest_face_index(centroids, region.seed_centroid)
    patch_indices = _patch_face_indices(
        centroids,
        region.seed_centroid,
        radius=region.patch_radius,
        min_faces=min_faces,
        max_faces=max_faces,
    )
    if nearest not in patch_indices:
        patch_indices.append(nearest)
        patch_indices = sorted(patch_indices)

    patch_labels = [labels[index] for index in patch_indices]
    patch_qualities = [qualities[index] for index in patch_indices]
    counts = count_labels(patch_labels)
    bad = _bad_count(patch_labels)
    nearest_q = qualities[nearest]

    return {
        "patch_face_count": len(patch_indices),
        "patch_bad_count": bad,
        "patch_good_count": counts["good"],
        "patch_needle_count": counts["needle"],
        "patch_low_aspect_count": counts["low_aspect"],
        "patch_cap_count": counts["cap"],
        "patch_zero_area_count": counts["zero_area"],
        "patch_min_angle_deg": min(q.min_angle for q in patch_qualities),
        "patch_avg_min_angle_deg": sum(q.min_angle for q in patch_qualities) / len(patch_qualities),
        "patch_max_angle_deg": max(q.max_angle for q in patch_qualities),
        "tracked_face_index": nearest,
        "tracked_face_label": labels[nearest],
        "tracked_min_angle_deg": nearest_q.min_angle,
        "tracked_max_angle_deg": nearest_q.max_angle,
        "tracked_aspect_ratio": nearest_q.aspect_ratio,
        "tracked_distance_to_seed": float(np.linalg.norm(centroids[nearest] - region.seed_centroid)),
    }


def _candidate_pool(mesh: Mesh, labels: list[str], qualities: list, centroids: np.ndarray) -> list[dict]:
    candidates: list[dict] = []
    for index, (label, quality) in enumerate(zip(labels, qualities)):
        if label == "good":
            continue
        if label == "cap":
            severity = quality.max_angle - 175.0
        else:
            severity = max(5.0 - quality.min_angle, 0.0) + max(0.05 - quality.aspect_ratio, 0.0) * 25.0
        candidates.append(
            {
                "face_index": index,
                "label": label,
                "quality": quality,
                "centroid": centroids[index],
                "severity": severity,
            }
        )
    candidates.sort(key=lambda item: item["severity"], reverse=True)
    return candidates


def _select_regions(
    records: list[StepRecord],
    *,
    count: int,
    radius: float,
    min_faces: int,
    max_faces: int,
    candidate_limit: int,
) -> list[CandidateRegion]:
    start = records[0].mesh
    final = records[-1].mesh
    start_labels, start_qualities = _quality_cache(start)
    final_labels, final_qualities = _quality_cache(final)
    start_centroids = _face_centroids(start)
    final_centroids = _face_centroids(final)
    candidates = _candidate_pool(start, start_labels, start_qualities, start_centroids)

    limited_candidates = candidates[:candidate_limit]
    seen_faces = {candidate["face_index"] for candidate in limited_candidates}
    for candidate in candidates:
        if candidate["label"] == "cap" and candidate["face_index"] not in seen_faces:
            limited_candidates.append(candidate)
            seen_faces.add(candidate["face_index"])

    scored = []
    for candidate in limited_candidates:
        region = CandidateRegion(
            region_id=0,
            face_index=candidate["face_index"],
            reason=candidate["label"],
            seed_label=candidate["label"],
            seed_centroid=candidate["centroid"],
            seed_min_angle=candidate["quality"].min_angle,
            seed_max_angle=candidate["quality"].max_angle,
            seed_aspect_ratio=candidate["quality"].aspect_ratio,
            patch_radius=radius,
        )
        start_metrics = _patch_metrics(
            start,
            start_labels,
            start_qualities,
            start_centroids,
            region,
            min_faces=min_faces,
            max_faces=max_faces,
        )
        final_metrics = _patch_metrics(
            final,
            final_labels,
            final_qualities,
            final_centroids,
            region,
            min_faces=min_faces,
            max_faces=max_faces,
        )
        tracked_is_good = final_metrics["tracked_face_label"] == "good"
        bad_drop = int(start_metrics["patch_bad_count"]) - int(final_metrics["patch_bad_count"])
        score = (
            (10000 if tracked_is_good else 0)
            + bad_drop * 30
            + float(candidate["severity"]) * 10
            - int(final_metrics["patch_bad_count"]) * 4
        )
        scored.append((score, region, start_metrics, final_metrics))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected: list[CandidateRegion] = []

    def far_enough(region: CandidateRegion) -> bool:
        return all(
            float(np.linalg.norm(region.seed_centroid - other.seed_centroid)) >= radius * 2.5
            for other in selected
        )

    def choose(label: str | None = None) -> None:
        if len(selected) >= count:
            return
        for _, region, _, _ in scored:
            if label is not None and region.seed_label != label:
                continue
            if far_enough(region):
                selected.append(region)
                return

    choose("cap")
    while len(selected) < count:
        before = len(selected)
        choose(None)
        if len(selected) == before:
            break

    for index, region in enumerate(selected, start=1):
        region.region_id = index
        if region.seed_label == "cap":
            region.reason = "worst cap-like triangle that becomes locally tracked"
        else:
            region.reason = "skinny needle-like triangle that becomes locally tracked"
    return selected


def _face_color(label: str, *, highlight: bool) -> tuple[int, int, int, int]:
    if highlight:
        return TRACKED_FACE_COLOR
    return QUALITY_COLORS[label]


def _write_colored_patch_ply(
    path: Path,
    mesh: Mesh,
    labels: list[str],
    centroids: np.ndarray,
    region: CandidateRegion,
    *,
    min_faces: int,
    max_faces: int,
    recenter: bool = False,
    x_offset: float = 0.0,
) -> None:
    nearest = _nearest_face_index(centroids, region.seed_centroid)
    patch_indices = _patch_face_indices(
        centroids,
        region.seed_centroid,
        radius=region.patch_radius,
        min_faces=min_faces,
        max_faces=max_faces,
    )
    if nearest not in patch_indices:
        patch_indices.append(nearest)
    patch_indices = sorted(patch_indices)

    vertex_map: dict[int, int] = {}
    patch_vertices: list[tuple[float, float, float]] = []
    patch_faces: list[tuple[int, int, int]] = []
    patch_colors: list[tuple[int, int, int, int]] = []

    for face_index in patch_indices:
        face = mesh.faces[face_index]
        remapped = []
        for old_index in face:
            if old_index not in vertex_map:
                vertex = np.asarray(mesh.vertices[old_index], dtype=float)
                if recenter:
                    vertex = vertex - region.seed_centroid + np.array([x_offset, 0.0, 0.0])
                vertex_map[old_index] = len(patch_vertices)
                patch_vertices.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
            remapped.append(vertex_map[old_index])
        patch_faces.append((remapped[0], remapped[1], remapped[2]))
        patch_colors.append(_face_color(labels[face_index], highlight=face_index == nearest))

    _write_ply(path, patch_vertices, patch_faces, patch_colors)


def _write_ply(
    path: Path,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    colors: list[tuple[int, int, int, int]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("ply\n")
        handle.write("format ascii 1.0\n")
        handle.write("comment quality legend: gray=good red=needle orange=low_aspect purple=cap black=zero_area yellow=tracked local face\n")
        handle.write(f"element vertex {len(vertices)}\n")
        handle.write("property float x\n")
        handle.write("property float y\n")
        handle.write("property float z\n")
        handle.write(f"element face {len(faces)}\n")
        handle.write("property list uchar int vertex_indices\n")
        handle.write("property uchar red\n")
        handle.write("property uchar green\n")
        handle.write("property uchar blue\n")
        handle.write("property uchar alpha\n")
        handle.write("end_header\n")
        for vertex in vertices:
            handle.write(f"{vertex[0]:.12g} {vertex[1]:.12g} {vertex[2]:.12g}\n")
        for face, color in zip(faces, colors):
            handle.write(f"3 {face[0]} {face[1]} {face[2]} {color[0]} {color[1]} {color[2]} {color[3]}\n")


def _write_timeline_ply(
    path: Path,
    records: list[StepRecord],
    caches: dict[int, StepCache],
    region: CandidateRegion,
    report_steps: list[int],
    *,
    min_faces: int,
    max_faces: int,
) -> None:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    colors: list[tuple[int, int, int, int]] = []
    step_lookup = {record.step: record for record in records}
    spacing = region.patch_radius * 3.2

    for slot, step in enumerate(report_steps):
        record = step_lookup[step]
        labels = caches[step].labels
        centroids = caches[step].centroids
        nearest = _nearest_face_index(centroids, region.seed_centroid)
        patch_indices = _patch_face_indices(
            centroids,
            region.seed_centroid,
            radius=region.patch_radius,
            min_faces=min_faces,
            max_faces=max_faces,
        )
        if nearest not in patch_indices:
            patch_indices.append(nearest)
        patch_indices = sorted(patch_indices)

        vertex_map: dict[int, int] = {}
        for face_index in patch_indices:
            face = record.mesh.faces[face_index]
            remapped = []
            for old_index in face:
                if old_index not in vertex_map:
                    vertex = np.asarray(record.mesh.vertices[old_index], dtype=float)
                    vertex = vertex - region.seed_centroid + np.array([slot * spacing, 0.0, 0.0])
                    vertex_map[old_index] = len(vertices)
                    vertices.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
                remapped.append(vertex_map[old_index])
            faces.append((remapped[0], remapped[1], remapped[2]))
            colors.append(_face_color(labels[face_index], highlight=face_index == nearest))

    _write_ply(path, vertices, faces, colors)


def _write_global_csv(path: Path, records: list[StepRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "step",
                "vertices",
                "faces",
                "min_angle_deg",
                "avg_min_angle_deg",
                "max_angle_deg",
                "avg_aspect_ratio",
                "bad_triangle_count",
                "needle_like_count",
                "cap_like_count",
                "collapse_edges",
                "split_edges",
                "collapses",
                "splits",
            ]
        )
        for record in records:
            summary = analyze_mesh(record.mesh)
            writer.writerow(
                [
                    record.step,
                    summary.vertex_count,
                    summary.face_count,
                    f"{summary.min_angle:.6f}",
                    f"{summary.avg_min_angle:.6f}",
                    f"{summary.max_angle:.6f}",
                    f"{summary.avg_aspect_ratio:.6f}",
                    summary.bad_triangle_count,
                    summary.needle_like_count,
                    summary.cap_like_count,
                    record.collapse_edges,
                    record.split_edges,
                    record.collapses,
                    record.splits,
                ]
            )


def _write_region_csv(
    path: Path,
    records: list[StepRecord],
    caches: dict[int, StepCache],
    regions: list[CandidateRegion],
    *,
    min_faces: int,
    max_faces: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "region_id",
            "seed_face_index",
            "reason",
            "seed_label",
            "seed_x",
            "seed_y",
            "seed_z",
            "seed_min_angle_deg",
            "seed_max_angle_deg",
            "seed_aspect_ratio",
            "patch_radius",
            "step",
            "patch_face_count",
            "patch_bad_count",
            "patch_good_count",
            "patch_needle_count",
            "patch_low_aspect_count",
            "patch_cap_count",
            "patch_zero_area_count",
            "patch_min_angle_deg",
            "patch_avg_min_angle_deg",
            "patch_max_angle_deg",
            "tracked_face_index",
            "tracked_face_label",
            "tracked_min_angle_deg",
            "tracked_max_angle_deg",
            "tracked_aspect_ratio",
            "tracked_distance_to_seed",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for region in regions:
            for record in records:
                labels = caches[record.step].labels
                qualities = caches[record.step].qualities
                centroids = caches[record.step].centroids
                metrics = _patch_metrics(
                    record.mesh,
                    labels,
                    qualities,
                    centroids,
                    region,
                    min_faces=min_faces,
                    max_faces=max_faces,
                )
                writer.writerow(
                    {
                        "region_id": region.region_id,
                        "seed_face_index": region.face_index,
                        "reason": region.reason,
                        "seed_label": region.seed_label,
                        "seed_x": f"{region.seed_centroid[0]:.9f}",
                        "seed_y": f"{region.seed_centroid[1]:.9f}",
                        "seed_z": f"{region.seed_centroid[2]:.9f}",
                        "seed_min_angle_deg": f"{region.seed_min_angle:.6f}",
                        "seed_max_angle_deg": f"{region.seed_max_angle:.6f}",
                        "seed_aspect_ratio": f"{region.seed_aspect_ratio:.6f}",
                        "patch_radius": f"{region.patch_radius:.9f}",
                        "step": record.step,
                        **{
                            key: f"{value:.6f}" if isinstance(value, float) else value
                            for key, value in metrics.items()
                        },
                    }
                )


def _write_summary_md(path: Path, records: list[StepRecord], regions: list[CandidateRegion], report_steps: list[int]) -> None:
    lines = [
        "# Car3 Diagnostic Notes",
        "",
        "This diagnostic tracks local bad-triangle regions through targeted cleanup.",
        "Face IDs are not stable after split/collapse operations, so each case is tracked by the original bad triangle centroid.",
        "",
        "Color legend: gray=good, red=needle, orange=low_aspect, purple=cap, black=zero_area, yellow=tracked local face.",
        "",
        "## Global Progress",
        "",
        "| step | vertices | faces | bad triangles | collapses | splits |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for record in records:
        summary = analyze_mesh(record.mesh)
        lines.append(
            f"| {record.step} | {summary.vertex_count} | {summary.face_count} | "
            f"{summary.bad_triangle_count} | {record.collapses} | {record.splits} |"
        )
    lines.extend(["", "## Selected Regions", ""])
    for region in regions:
        lines.extend(
            [
                f"### Region {region.region_id}",
                "",
                f"- Seed face index: `{region.face_index}`",
                f"- Seed label: `{region.seed_label}`",
                f"- Seed min/max angle: `{region.seed_min_angle:.3f}` / `{region.seed_max_angle:.3f}` degrees",
                f"- Seed aspect ratio: `{region.seed_aspect_ratio:.6f}`",
                f"- Patch timeline PLY: `regions/region_{region.region_id:02d}_timeline.ply`",
                f"- Individual patch PLYs use steps: `{', '.join(str(step) for step in report_steps)}`",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_steps(raw: str, max_step: int) -> list[int]:
    result = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        value = int(item)
        if value < 0 or value > max_step:
            raise ValueError(f"Report step {value} is outside 0..{max_step}")
        if value not in result:
            result.append(value)
    if 0 not in result:
        result.insert(0, 0)
    if max_step not in result:
        result.append(max_step)
    return sorted(result)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate car3 targeted-cleanup diagnostics for report case studies.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "submission" / "EsadMazi_CENG589_Project" / "inputs" / "cars" / "car3.off",
    )
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "car3_diagnostic")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--regions", type=int, default=4)
    parser.add_argument("--patch-radius-factor", type=float, default=0.018)
    parser.add_argument("--patch-min-faces", type=int, default=35)
    parser.add_argument("--patch-max-faces", type=int, default=220)
    parser.add_argument("--candidate-limit", type=int, default=320)
    parser.add_argument("--report-steps", default="0,1,3,6,10")
    parser.add_argument("--needle-angle", type=float, default=5.0)
    parser.add_argument("--cap-angle", type=float, default=175.0)
    parser.add_argument("--aspect-threshold", type=float, default=0.05)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    steps_dir = args.out_dir / "steps"
    regions_dir = args.out_dir / "regions"
    steps_dir.mkdir(parents=True, exist_ok=True)
    regions_dir.mkdir(parents=True, exist_ok=True)

    source = read_off(args.input)
    diag = _bbox_diagonal(source)
    patch_radius = diag * args.patch_radius_factor
    report_steps = _parse_steps(args.report_steps, args.iterations)

    print(f"input={args.input}")
    print(f"out_dir={args.out_dir}")
    print(f"bbox_diagonal={diag:.9f}")
    print(f"patch_radius={patch_radius:.9f}")

    records = _run_cleanup_timeline(
        source,
        iterations=args.iterations,
        needle_angle_deg=args.needle_angle,
        cap_angle_deg=args.cap_angle,
        low_aspect_threshold=args.aspect_threshold,
    )
    if records[-1].step < args.iterations:
        report_steps = [step for step in report_steps if step <= records[-1].step]
        if records[-1].step not in report_steps:
            report_steps.append(records[-1].step)

    for record in records:
        write_off(record.mesh, steps_dir / f"car3_step_{record.step:02d}.off")

    print("building per-step quality cache...")
    caches: dict[int, StepCache] = {}
    for record in records:
        labels, qualities = _quality_cache(record.mesh)
        caches[record.step] = StepCache(
            labels=labels,
            qualities=qualities,
            centroids=_face_centroids(record.mesh),
        )

    regions = _select_regions(
        records,
        count=args.regions,
        radius=patch_radius,
        min_faces=args.patch_min_faces,
        max_faces=args.patch_max_faces,
        candidate_limit=args.candidate_limit,
    )
    if not regions:
        raise SystemExit("No bad regions could be selected.")

    _write_global_csv(args.out_dir / "car3_global_steps.csv", records)
    _write_region_csv(
        args.out_dir / "car3_region_tracking.csv",
        records,
        caches,
        regions,
        min_faces=args.patch_min_faces,
        max_faces=args.patch_max_faces,
    )
    _write_summary_md(args.out_dir / "README.md", records, regions, report_steps)

    for region in regions:
        for step in report_steps:
            record = next(item for item in records if item.step == step)
            labels = caches[record.step].labels
            centroids = caches[record.step].centroids
            _write_colored_patch_ply(
                regions_dir / f"region_{region.region_id:02d}_step_{step:02d}_patch.ply",
                record.mesh,
                labels,
                centroids,
                region,
                min_faces=args.patch_min_faces,
                max_faces=args.patch_max_faces,
            )
        _write_timeline_ply(
            regions_dir / f"region_{region.region_id:02d}_timeline.ply",
            records,
            caches,
            region,
            report_steps,
            min_faces=args.patch_min_faces,
            max_faces=args.patch_max_faces,
        )

    final_summary = analyze_mesh(records[-1].mesh)
    print(
        "global bad triangles: "
        f"{analyze_mesh(records[0].mesh).bad_triangle_count} -> {final_summary.bad_triangle_count}"
    )
    print(f"wrote {args.out_dir / 'car3_global_steps.csv'}")
    print(f"wrote {args.out_dir / 'car3_region_tracking.csv'}")
    print(f"wrote {len(regions)} region timelines in {regions_dir}")
    for region in regions:
        print(
            f"region {region.region_id}: face={region.face_index}, "
            f"label={region.seed_label}, min_angle={region.seed_min_angle:.3f}, "
            f"aspect={region.seed_aspect_ratio:.6f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
